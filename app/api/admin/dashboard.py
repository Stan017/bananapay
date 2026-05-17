"""Dashboard admin: métricas operativas + contabilidad (P&L, float, fees, gastos)."""

import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.admin.auth import verify_token
from app.integrations.supabase_client import get_supabase
from app.utils.logger import get_logger

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])
logger = get_logger(__name__)


# ─── Schemas de respuesta ─────────────────────────────────────────────────────

class DashboardMetrics(BaseModel):
    float_total: float          # float total combinado
    float_fiat: float           # USD de depósitos bancarios
    float_usdt: float           # USDT de depósitos crypto
    float_usdc: float           # USDC de depósitos crypto
    users_total: int
    users_new_today: int
    deposits_pending: int
    withdrawals_pending: int
    fees_today: float
    fees_month: float
    volume_today: float
    volume_month: float


class PnLEntry(BaseModel):
    date: str
    gross_revenue: float        # fees cobrados
    expenses: float             # gastos registrados ese día
    net: float                  # gross - expenses


class ExpenseIn(BaseModel):
    category: Literal["hosting", "database", "whatsapp", "domain", "redis", "other"]
    description: str
    amount_usd: float
    expense_date: str | None = None   # YYYY-MM-DD, default hoy


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.date.today().isoformat()

def _month_start() -> str:
    d = datetime.date.today()
    return d.replace(day=1).isoformat()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=DashboardMetrics)
async def get_dashboard(token: dict = Depends(verify_token)) -> DashboardMetrics:
    db = get_supabase()
    today = _today()
    month_start = _month_start()

    # Float separado por tipo
    wallets_usd  = db.table("wallets").select("balance").eq("currency", "USD").execute()
    wallets_usdt = db.table("wallets").select("balance").eq("currency", "USDT").execute()
    wallets_usdc = db.table("wallets").select("balance").eq("currency", "USDC").execute()
    float_fiat   = sum(float(w["balance"]) for w in (wallets_usd.data  or []))
    float_usdt   = sum(float(w["balance"]) for w in (wallets_usdt.data or []))
    float_usdc   = sum(float(w["balance"]) for w in (wallets_usdc.data or []))
    float_total  = float_fiat + float_usdt + float_usdc

    # Usuarios
    users_total  = db.table("users").select("id", count="exact").execute().count or 0
    users_today  = db.table("users").select("id", count="exact").gte("created_at", today).execute().count or 0

    # Pendientes
    dep_pending  = db.table("deposits").select("id", count="exact").eq("status", "pending").execute().count or 0
    wd_pending   = db.table("withdrawals").select("id", count="exact").eq("status", "pending").execute().count or 0

    # Fees
    fees_today_res = db.table("withdrawals").select("fee").eq("status", "approved").gte("approved_at", today).execute()
    fees_today = sum(float(r["fee"]) for r in (fees_today_res.data or []))

    fees_month_res = db.table("withdrawals").select("fee").eq("status", "approved").gte("approved_at", month_start).execute()
    fees_month = sum(float(r["fee"]) for r in (fees_month_res.data or []))

    # Volumen (transacciones completadas)
    vol_today_res = db.table("transactions").select("amount").eq("status", "completed").gte("created_at", today).execute()
    volume_today = sum(float(r["amount"]) for r in (vol_today_res.data or []))

    vol_month_res = db.table("transactions").select("amount").eq("status", "completed").gte("created_at", month_start).execute()
    volume_month = sum(float(r["amount"]) for r in (vol_month_res.data or []))

    return DashboardMetrics(
        float_total=float_total,
        float_fiat=float_fiat,
        float_usdt=float_usdt,
        float_usdc=float_usdc,
        users_total=users_total,
        users_new_today=users_today,
        deposits_pending=dep_pending,
        withdrawals_pending=wd_pending,
        fees_today=fees_today,
        fees_month=fees_month,
        volume_today=volume_today,
        volume_month=volume_month,
    )


@router.get("/pnl")
async def get_pnl(
    period: Literal["daily", "monthly"] = Query("daily"),
    from_date: str = Query(default=None, description="YYYY-MM-DD"),
    to_date: str   = Query(default=None, description="YYYY-MM-DD"),
    token: dict = Depends(verify_token),
) -> list[PnLEntry]:
    """
    P&L por día o por mes entre dos fechas.
    Si no se pasan fechas: últimos 30 días (daily) o últimos 12 meses (monthly).
    """
    db = get_supabase()

    if not to_date:
        to_date = _today()
    if not from_date:
        if period == "daily":
            from_date = (datetime.date.today() - datetime.timedelta(days=29)).isoformat()
        else:
            from_date = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()

    # Fees por día (withdrawals aprobados)
    fees_res = (
        db.table("withdrawals")
        .select("fee, approved_at")
        .eq("status", "approved")
        .gte("approved_at", from_date)
        .lte("approved_at", to_date + "T23:59:59")
        .execute()
    )

    # Gastos registrados
    exp_res = (
        db.table("expenses")
        .select("amount_usd, expense_date")
        .gte("expense_date", from_date)
        .lte("expense_date", to_date)
        .execute()
    )

    # Agrupar fees por periodo
    fees_by_period: dict[str, float] = {}
    for row in (fees_res.data or []):
        raw = (row.get("approved_at") or "")[:10]
        key = raw[:7] if period == "monthly" else raw
        fees_by_period[key] = fees_by_period.get(key, 0.0) + float(row["fee"])

    expenses_by_period: dict[str, float] = {}
    for row in (exp_res.data or []):
        raw = (row.get("expense_date") or "")[:10]
        key = raw[:7] if period == "monthly" else raw
        expenses_by_period[key] = expenses_by_period.get(key, 0.0) + float(row["amount_usd"])

    all_keys = sorted(set(list(fees_by_period.keys()) + list(expenses_by_period.keys())))
    result = []
    for key in all_keys:
        gross = fees_by_period.get(key, 0.0)
        exp   = expenses_by_period.get(key, 0.0)
        result.append(PnLEntry(date=key, gross_revenue=gross, expenses=exp, net=gross - exp))

    return result


@router.get("/float")
async def get_float(token: dict = Depends(verify_token)) -> dict:
    """Float en tiempo real: cuánto dinero tienen los usuarios en BananaPay."""
    db = get_supabase()
    # SUM en la DB — no traer todas las filas a Python
    rows = db.table("wallets").select("currency, balance").execute().data or []
    totals: dict[str, float] = {"USD": 0.0, "USDT": 0.0, "USDC": 0.0}
    counts: dict[str, int]   = {"USD": 0,   "USDT": 0,   "USDC": 0}
    for w in rows:
        cur = w.get("currency", "")
        if cur in totals:
            totals[cur] += float(w["balance"])
            counts[cur] += 1
    return {
        "float_usd":   round(totals["USD"],  2),
        "float_usdt":  round(totals["USDT"], 2),
        "float_usdc":  round(totals["USDC"], 2),
        "float_total": round(sum(totals.values()), 2),
        "wallets_usd_count":  counts["USD"],
        "wallets_usdt_count": counts["USDT"],
        "wallets_usdc_count": counts["USDC"],
        "as_of": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@router.get("/fees")
async def get_fees(
    from_date: str = Query(default=None),
    to_date: str   = Query(default=None),
    token: dict = Depends(verify_token),
) -> dict:
    """Fees cobrados en un rango de fechas (default: mes actual)."""
    db = get_supabase()
    if not from_date:
        from_date = _month_start()
    if not to_date:
        to_date = _today()

    res = (
        db.table("withdrawals")
        .select("fee, withdrawal_type, approved_at")
        .eq("status", "approved")
        .gte("approved_at", from_date)
        .lte("approved_at", to_date + "T23:59:59")
        .execute()
    )
    rows = res.data or []
    total = sum(float(r["fee"]) for r in rows)
    by_type: dict[str, float] = {}
    for r in rows:
        t = r.get("withdrawal_type", "unknown")
        by_type[t] = by_type.get(t, 0.0) + float(r["fee"])

    return {
        "total_fees_usd": total,
        "count": len(rows),
        "by_type": by_type,
        "from_date": from_date,
        "to_date": to_date,
    }


# ─── Analytics avanzados ─────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    days: int = Query(default=30, ge=7, le=90),
    token: dict = Depends(verify_token),
) -> dict:
    """
    Datos para las gráficas del dashboard.
    - Volumen diario (depósitos + retiros + transferencias)
    - Tasa de aprobación vs rechazo de depósitos
    - Depósitos por banco
    - Usuarios nuevos por día
    - Tiempo promedio de aprobación de depósitos (minutos)
    """
    db         = get_supabase()
    from_date  = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    today      = _today()

    # ── Volumen diario ────────────────────────────────────────────────────────
    dep_rows = (
        db.table("deposits")
        .select("amount, created_at")
        .eq("status", "approved")
        .gte("created_at", from_date)
        .execute()
    ).data or []

    wd_rows = (
        db.table("withdrawals")
        .select("amount, created_at")
        .in_("status", ["approved", "completed"])
        .gte("created_at", from_date)
        .execute()
    ).data or []

    tx_rows = (
        db.table("transactions")
        .select("amount, created_at, tx_type")
        .eq("status", "completed")
        .eq("tx_type", "transfer")
        .gte("created_at", from_date)
        .execute()
    ).data or []

    # Generar todos los días del rango
    start = datetime.date.fromisoformat(from_date)
    end   = datetime.date.fromisoformat(today)
    all_days = []
    cur = start
    while cur <= end:
        all_days.append(cur.isoformat())
        cur += datetime.timedelta(days=1)

    dep_by_day: dict[str, float] = {d: 0.0 for d in all_days}
    wd_by_day:  dict[str, float] = {d: 0.0 for d in all_days}
    tx_by_day:  dict[str, float] = {d: 0.0 for d in all_days}

    for r in dep_rows:
        day = (r.get("created_at") or "")[:10]
        if day in dep_by_day:
            dep_by_day[day] += float(r["amount"])
    for r in wd_rows:
        day = (r.get("created_at") or "")[:10]
        if day in wd_by_day:
            wd_by_day[day] += float(r["amount"])
    for r in tx_rows:
        day = (r.get("created_at") or "")[:10]
        if day in tx_by_day:
            tx_by_day[day] += float(r["amount"])

    volume_by_day = [
        {
            "date":        d,
            "deposits":    round(dep_by_day[d], 2),
            "withdrawals": round(wd_by_day[d], 2),
            "transfers":   round(tx_by_day[d], 2),
        }
        for d in all_days
    ]

    # ── Tasa aprobación/rechazo depósitos ─────────────────────────────────────
    dep_status = (
        db.table("deposits")
        .select("status")
        .gte("created_at", from_date)
        .execute()
    ).data or []

    rates: dict[str, int] = {"approved": 0, "rejected": 0, "pending": 0}
    for r in dep_status:
        s = r.get("status", "pending")
        rates[s] = rates.get(s, 0) + 1

    # ── Depósitos por banco ───────────────────────────────────────────────────
    bank_rows = (
        db.table("deposits")
        .select("bank_name, amount")
        .eq("status", "approved")
        .gte("created_at", from_date)
        .execute()
    ).data or []

    banks: dict[str, dict] = {}
    for r in bank_rows:
        name = r.get("bank_name") or "Sin banco"
        if name not in banks:
            banks[name] = {"count": 0, "total": 0.0}
        banks[name]["count"] += 1
        banks[name]["total"] += float(r["amount"])

    deposits_by_bank = sorted(
        [{"bank": k, "count": v["count"], "total": round(v["total"], 2)} for k, v in banks.items()],
        key=lambda x: x["total"],
        reverse=True,
    )

    # ── Usuarios nuevos por día ───────────────────────────────────────────────
    user_rows = (
        db.table("users")
        .select("created_at")
        .gte("created_at", from_date)
        .execute()
    ).data or []

    users_by_day: dict[str, int] = {d: 0 for d in all_days}
    for r in user_rows:
        day = (r.get("created_at") or "")[:10]
        if day in users_by_day:
            users_by_day[day] += 1

    new_users_by_day = [{"date": d, "count": users_by_day[d]} for d in all_days]

    # ── Tiempo promedio de aprobación (minutos) ───────────────────────────────
    approved_deps = (
        db.table("deposits")
        .select("created_at, approved_at")
        .eq("status", "approved")
        .not_.is_("approved_at", "null")
        .gte("created_at", from_date)
        .limit(200)
        .execute()
    ).data or []

    approval_times = []
    for r in approved_deps:
        try:
            created  = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            approved = datetime.datetime.fromisoformat(r["approved_at"].replace("Z", "+00:00"))
            mins = (approved - created).total_seconds() / 60
            if 0 < mins < 1440:  # ignorar outliers > 24h
                approval_times.append(mins)
        except Exception:
            pass

    avg_approval_minutes = round(sum(approval_times) / len(approval_times), 1) if approval_times else None

    return {
        "period_days":          days,
        "volume_by_day":        volume_by_day,
        "deposit_rates":        rates,
        "deposits_by_bank":     deposits_by_bank,
        "new_users_by_day":     new_users_by_day,
        "avg_approval_minutes": avg_approval_minutes,
    }


# ─── Expenses ─────────────────────────────────────────────────────────────────

@router.get("/expenses")
async def list_expenses(
    from_date: str = Query(default=None),
    to_date: str   = Query(default=None),
    token: dict = Depends(verify_token),
) -> list:
    db = get_supabase()
    if not from_date:
        from_date = _month_start()
    if not to_date:
        to_date = _today()
    res = (
        db.table("expenses")
        .select("*")
        .gte("expense_date", from_date)
        .lte("expense_date", to_date)
        .order("expense_date", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/expenses")
async def create_expense(body: ExpenseIn, token: dict = Depends(verify_token)) -> dict:
    db = get_supabase()
    payload = {
        "category":      body.category,
        "description":   body.description,
        "amount_usd":    body.amount_usd,
        "expense_date":  body.expense_date or _today(),
        "registered_by": token["sub"],
    }
    res = db.table("expenses").insert(payload).execute()
    logger.info("Gasto registrado: %s $%.2f by=%s", body.category, body.amount_usd, token["sub"])
    return res.data[0]
