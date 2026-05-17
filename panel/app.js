/**
 * BananaPay Admin Panel
 * Vanilla JS — sin frameworks, sin build step.
 * Llama al API de Railway via fetch().
 */

const API = window.BANANAPAY_API_URL || "http://localhost:8000";

// ─── Theme ────────────────────────────────────────────────────────────────────

function initTheme() {
  const saved = localStorage.getItem("bp_theme") || "dark";
  if (saved === "light") document.documentElement.classList.add("light");
  _updateThemeBtn();
}

function toggleTheme() {
  const isLight = document.documentElement.classList.toggle("light");
  localStorage.setItem("bp_theme", isLight ? "light" : "dark");
  _updateThemeBtn();
}

function _updateThemeBtn() {
  const btn = document.getElementById("theme-btn");
  if (!btn) return;
  const isLight = document.documentElement.classList.contains("light");
  btn.textContent = isLight ? "🌙" : "☀️";
  btn.title = isLight ? "Cambiar a oscuro" : "Cambiar a claro";
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem("bp_token");
}

function saveToken(token) {
  localStorage.setItem("bp_token", token);
}

function clearToken() {
  localStorage.removeItem("bp_token");
  localStorage.removeItem("bp_operator");
}

function isLoggedIn() {
  return !!getToken();
}

function guardAuth() {
  if (!isLoggedIn()) {
    window.location.href = "index.html";
  }
}

function logout() {
  clearToken();
  window.location.href = "index.html";
}

// ─── HTTP helpers ─────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = "index.html";
    return null;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || res.statusText);
  }

  return res.json();
}

async function apiPost(path, body) {
  return apiFetch(path, { method: "POST", body: JSON.stringify(body) });
}

async function apiPatch(path, body) {
  return apiFetch(path, { method: "PATCH", body: JSON.stringify(body) });
}

// ─── Historial ────────────────────────────────────────────────────────────────

let _histSection = "deposits";
let _histStatus  = "all";
let _histPage    = 1;

function switchSection(section, btn) {
  _histSection = section;
  _histPage    = 1;
  document.querySelectorAll(".hist-tabs .hist-tab").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const noFilter = ["transfers", "crypto-deposits", "crypto-withdrawals", "fraud-alerts"];
  const filter = document.getElementById("status-filter");
  if (filter) filter.style.display = noFilter.includes(section) ? "none" : "flex";
  loadHistory();
}

function setFilter(status, btn) {
  _histStatus = status;
  _histPage   = 1;
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  loadHistory();
}

async function loadHistory() {
  const wrap = document.getElementById("history-table-wrap");
  if (!wrap) return;
  wrap.innerHTML = '<p class="empty">Cargando...</p>';

  const noStatusFilter = ["transfers", "crypto-deposits", "crypto-withdrawals", "fraud-alerts"];
  let path = `/admin/history/${_histSection}?page=${_histPage}`;
  if (!noStatusFilter.includes(_histSection)) path += `&status=${_histStatus}`;

  const res  = await apiFetch(path).catch(() => null);
  const data = res?.data || [];

  if (!data.length) {
    wrap.innerHTML = '<p class="empty">Sin registros</p>';
    document.getElementById("pagination").innerHTML = "";
    return;
  }

  if (_histSection === "deposits")           wrap.innerHTML = _renderHistDeposits(data);
  if (_histSection === "withdrawals")        wrap.innerHTML = _renderHistWithdrawals(data);
  if (_histSection === "transfers")          wrap.innerHTML = _renderHistTransfers(data);
  if (_histSection === "crypto-deposits")    wrap.innerHTML = _renderHistCryptoDeposits(data);
  if (_histSection === "crypto-withdrawals") wrap.innerHTML = _renderHistCryptoWithdrawals(data);
  if (_histSection === "fraud-alerts")       wrap.innerHTML = _renderHistFraudAlerts(data);

  const pg = document.getElementById("pagination");
  if (pg) {
    pg.innerHTML = `
      ${_histPage > 1 ? `<button class="btn btn-ghost btn-sm" onclick="_histGoPage(${_histPage-1})">← Anterior</button>` : ""}
      <span class="page-info">Página ${_histPage}</span>
      ${data.length === 50 ? `<button class="btn btn-ghost btn-sm" onclick="_histGoPage(${_histPage+1})">Siguiente →</button>` : ""}
    `;
  }
}

function _histGoPage(p) { _histPage = p; loadHistory(); }

function _statusBadge(s) {
  return `<span class="hist-status status-${s}">${s}</span>`;
}

function _renderHistDeposits(list) {
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>Usuario</span><span>Cédula</span><span>Monto</span><span>Banco</span><span>Referencia</span><span>Estado</span><span>Fecha</span>
    </div>
    ${list.map(d => `
    <div class="htable-row">
      <span class="mono small">#${d.id.slice(0,8).toUpperCase()}</span>
      <span>${d.user?.name || "—"}</span>
      <span class="mono small">${d.user?.cedula || "—"}</span>
      <span class="green mono">${fmt(d.amount)}</span>
      <span>${d.bank_name || "—"}</span>
      <span class="mono small">${d.reference_number || "—"}</span>
      <span>${_statusBadge(d.status)}</span>
      <span class="small">${fmtDate(d.created_at)}</span>
    </div>`).join("")}
  </div>`;
}

function _renderHistWithdrawals(list) {
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>Usuario</span><span>Banco</span><span>Cuenta</span><span>Monto</span><span>Fee</span><span>Recibe</span><span>Tipo</span><span>Estado</span><span>Fecha</span>
    </div>
    ${list.map(w => `
    <div class="htable-row">
      <span class="mono small">#${w.id.slice(0,8).toUpperCase()}</span>
      <span>${w.user?.name || "—"}</span>
      <span>${w.bank_name}</span>
      <span class="mono small">${w.account_number}</span>
      <span class="red mono">${fmt(w.amount)}</span>
      <span class="mono small">${fmt(w.fee)}</span>
      <span class="green mono">${fmt(w.amount_received)}</span>
      <span>${w.withdrawal_type === 'instant' ? '⚡' : '🕐'} ${w.withdrawal_type}</span>
      <span>${_statusBadge(w.status)}</span>
      <span class="small">${fmtDate(w.created_at)}</span>
    </div>`).join("")}
  </div>`;
}

function _renderHistTransfers(list) {
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>De</span><span>Para</span><span>Monto</span><span>Fee</span><span>Estado</span><span>Fecha</span>
    </div>
    ${list.map(t => `
    <div class="htable-row">
      <span class="mono small">#${t.id.slice(0,8).toUpperCase()}</span>
      <span>${t.from_user?.name || "—"}<br><span class="mono small">${t.from_user?.phone || ""}</span></span>
      <span>${t.to_user?.name || "—"}<br><span class="mono small">${t.to_user?.phone || ""}</span></span>
      <span class="green mono">${fmt(t.amount)}</span>
      <span class="mono small">${fmt(t.fee)}</span>
      <span>${_statusBadge(t.status)}</span>
      <span class="small">${fmtDate(t.created_at)}</span>
    </div>`).join("")}
  </div>`;
}

function _currencyBadge(currency) {
  if (!currency) return "";
  const cfg = {
    USD:  { bg: "#16a34a20", color: "#16a34a", border: "#16a34a40", label: "💵 USD"  },
    USDT: { bg: "#0891b220", color: "#0891b2", border: "#0891b240", label: "🪙 USDT" },
    USDC: { bg: "#6366f120", color: "#6366f1", border: "#6366f140", label: "🔵 USDC" },
  };
  const c = cfg[currency] || { bg: "#6b728020", color: "#6b7280", border: "#6b728040", label: currency };
  return `<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:${c.bg};color:${c.color};border:1px solid ${c.border};font-weight:600">${c.label}</span>`;
}

function _renderHistCryptoDeposits(list) {
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>Usuario</span><span>Token</span><span>Monto</span><span>TX Hash</span><span>Origen</span><span>Fecha</span>
    </div>
    ${list.map(d => {
      const cur = d.currency || "USDT";
      return `
    <div class="htable-row">
      <span class="mono small">#${(d.id||"").slice(0,8).toUpperCase()}</span>
      <span>${d.user?.name || "—"}<br><span class="mono small">${d.user?.phone || ""}</span></span>
      <span>${_currencyBadge(cur)}</span>
      <span class="green mono">${parseFloat(d.amount_usdt||d.amount||0).toFixed(2)}</span>
      <span class="mono small" title="${d.tx_hash||""}">${(d.tx_hash||"—").slice(0,14)}…</span>
      <span class="mono small" title="${d.from_address||""}">${(d.from_address||"—").slice(0,12)}…</span>
      <span class="small">${fmtDate(d.created_at)}</span>
    </div>`;
    }).join("")}
  </div>`;
}

function _renderHistCryptoWithdrawals(list) {
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>Usuario</span><span>Token</span><span>Monto</span><span>Fee</span><span>Estado</span><span>Fecha</span>
    </div>
    ${list.map(w => {
      const cur = w.currency || "USDT";
      return `
    <div class="htable-row">
      <span class="mono small">#${(w.id||"").slice(0,8).toUpperCase()}</span>
      <span>${w.from_user?.name || "—"}<br><span class="mono small">${w.from_user?.phone || ""}</span></span>
      <span>${_currencyBadge(cur)}</span>
      <span class="red mono">${parseFloat(w.amount||0).toFixed(2)}</span>
      <span class="mono small">${parseFloat(w.fee||0).toFixed(2)}</span>
      <span><span class="hist-status status-${w.status||"completed"}">${w.status||"completed"}</span></span>
      <span class="small">${fmtDate(w.created_at)}</span>
    </div>`;
    }).join("")}
  </div>`;
}

function _renderHistFraudAlerts(list) {
  const LABELS = {
    duplicate_voucher:          "🔁 Comprobante dup.",
    too_many_rejected_deposits: "🔄 Muchos rechazos",
    high_amount_deposit:        "💰 Monto alto dep.",
    new_user_large_deposit:     "👤 Nuevo + monto alto",
    new_user_withdrawal:        "🆕 Nuevo retirando",
    new_bank_account:           "🏦 Nueva cuenta",
    high_amount_withdrawal:     "💸 Monto alto retiro",
  };
  return `<div class="htable">
    <div class="htable-head">
      <span>ID</span><span>Usuario</span><span>Motivo</span><span>Monto</span><span>Tipo TX</span><span>Fecha</span>
    </div>
    ${list.map(a => `
    <div class="htable-row">
      <span class="mono small">#${(a.id||"").slice(0,8).toUpperCase()}</span>
      <span>${a.user?.name || a.phone || "—"}<br><span class="mono small">${a.cedula || ""}</span></span>
      <span>${LABELS[a.reason] || a.reason || "—"}</span>
      <span class="mono">${a.amount ? fmt(a.amount) : "—"}</span>
      <span class="small">${a.tx_type || "—"}</span>
      <span class="small">${fmtDate(a.created_at)}</span>
    </div>`).join("")}
  </div>`;
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

function showToast(msg, type = "success") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.className = `toast toast-${type} show`;
  setTimeout(() => toast.classList.remove("show"), 3500);
}

function setLoading(id, loading) {
  const el = document.getElementById(id);
  if (el) el.disabled = loading;
}

function fmt(amount) {
  return "$" + parseFloat(amount || 0).toFixed(2);
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-EC", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ─── Login ────────────────────────────────────────────────────────────────────

async function handleLogin(e) {
  e.preventDefault();
  const email    = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const pin      = document.getElementById("pin").value;
  const errEl    = document.getElementById("login-error");

  setLoading("btn-login", true);
  errEl.textContent = "";

  try {
    const data = await apiPost("/admin/auth/login", { email, password, pin });
    saveToken(data.token);
    localStorage.setItem("bp_operator", JSON.stringify({ name: data.name, role: data.role }));
    window.location.href = "dashboard.html";
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    setLoading("btn-login", false);
  }
}

// ─── Analytics ────────────────────────────────────────────────────────────────

let _charts = {};

function _destroyChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

function _cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function setPeriod(days, btn) {
  document.querySelectorAll(".period-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  loadAnalytics(days);
}

async function loadAnalytics(days = 30) {
  const data = await apiFetch(`/admin/dashboard/analytics?days=${days}`).catch(() => null);
  if (!data) return;

  const isDark  = document.body.classList.contains("dark");
  const gridClr = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";
  const textClr = isDark ? "#9ca3af" : "#6b7280";

  const baseOpts = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: gridClr }, ticks: { color: textClr, maxTicksLimit: 8, font: { size: 11 } } },
      y: { grid: { color: gridClr }, ticks: { color: textClr, font: { size: 11 } }, beginAtZero: true },
    },
  };

  // ── 1. Volumen diario ─────────────────────────────────────────────────────
  _destroyChart("volume");
  const volCtx   = document.getElementById("chart-volume");
  if (volCtx) {
    const labels   = data.volume_by_day.map(d => d.date.slice(5));   // MM-DD
    _charts.volume = new Chart(volCtx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Depósitos",      data: data.volume_by_day.map(d => d.deposits),    backgroundColor: "rgba(34,197,94,0.7)"  },
          { label: "Retiros",        data: data.volume_by_day.map(d => d.withdrawals), backgroundColor: "rgba(239,68,68,0.7)"  },
          { label: "Transferencias", data: data.volume_by_day.map(d => d.transfers),   backgroundColor: "rgba(99,102,241,0.7)" },
        ],
      },
      options: {
        ...baseOpts,
        plugins: {
          legend: { display: true, position: "top", labels: { color: textClr, font: { size: 11 } } },
        },
        scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, stacked: true }, y: { ...baseOpts.scales.y, stacked: true } },
      },
    });
  }

  // ── 2. Tasa aprobación/rechazo ────────────────────────────────────────────
  _destroyChart("rates");
  const ratesCtx = document.getElementById("chart-rates");
  if (ratesCtx) {
    const r = data.deposit_rates;
    const total = (r.approved || 0) + (r.rejected || 0) + (r.pending || 0);
    _charts.rates = new Chart(ratesCtx, {
      type: "doughnut",
      data: {
        labels:   ["Aprobados", "Rechazados", "Pendientes"],
        datasets: [{
          data:            [r.approved || 0, r.rejected || 0, r.pending || 0],
          backgroundColor: ["#22c55e", "#ef4444", "#f59e0b"],
          borderWidth:     0,
          hoverOffset:     6,
        }],
      },
      options: {
        responsive: true,
        cutout: "65%",
        plugins: { legend: { display: false } },
      },
    });
    const legend = document.getElementById("rates-legend");
    if (legend) {
      const pct = v => total ? Math.round(v / total * 100) : 0;
      legend.innerHTML = `
        <span class="rl-dot" style="background:#22c55e"></span> Aprobados ${pct(r.approved||0)}%
        <span class="rl-dot" style="background:#ef4444"></span> Rechazados ${pct(r.rejected||0)}%
        <span class="rl-dot" style="background:#f59e0b"></span> Pendientes ${pct(r.pending||0)}%
      `;
    }
  }

  // ── 3. Depósitos por banco ────────────────────────────────────────────────
  _destroyChart("banks");
  const banksCtx = document.getElementById("chart-banks");
  if (banksCtx && data.deposits_by_bank.length) {
    const COLORS = ["#6366f1","#22c55e","#f59e0b","#ef4444","#06b6d4","#a855f7","#f97316"];
    _charts.banks = new Chart(banksCtx, {
      type: "bar",
      data: {
        labels:   data.deposits_by_bank.map(b => b.bank),
        datasets: [{
          label:           "USD aprobados",
          data:            data.deposits_by_bank.map(b => b.total),
          backgroundColor: data.deposits_by_bank.map((_, i) => COLORS[i % COLORS.length]),
          borderRadius:    6,
        }],
      },
      options: {
        ...baseOpts,
        indexAxis: "y",
        scales: {
          x: baseOpts.scales.x,
          y: { grid: { display: false }, ticks: { color: textClr, font: { size: 11 } } },
        },
      },
    });
  } else if (banksCtx) {
    banksCtx.parentElement.innerHTML += '<p class="empty" style="font-size:12px">Sin depósitos aprobados en el período</p>';
  }

  // ── 4. Usuarios nuevos por día ────────────────────────────────────────────
  _destroyChart("users");
  const usersCtx = document.getElementById("chart-users");
  if (usersCtx) {
    const labels = data.new_users_by_day.map(d => d.date.slice(5));
    _charts.users = new Chart(usersCtx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label:           "Usuarios nuevos",
          data:            data.new_users_by_day.map(d => d.count),
          borderColor:     "#6366f1",
          backgroundColor: "rgba(99,102,241,0.12)",
          tension:         0.4,
          fill:            true,
          pointRadius:     3,
        }],
      },
      options: baseOpts,
    });
  }

  // ── 5. Tiempo promedio aprobación ─────────────────────────────────────────
  const wrap = document.getElementById("approval-time-wrap");
  const val  = document.getElementById("approval-time-val");
  if (wrap && val && data.avg_approval_minutes != null) {
    const mins = data.avg_approval_minutes;
    val.textContent = mins < 60
      ? `${mins} min`
      : `${(mins / 60).toFixed(1)} h`;
    wrap.classList.remove("hidden");
  }
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  guardAuth();

  const op = JSON.parse(localStorage.getItem("bp_operator") || "{}");
  const nameEl = document.getElementById("operator-name");
  if (nameEl) nameEl.textContent = op.name || "Admin";

  try {
    const [metrics, fees] = await Promise.all([
      apiFetch("/admin/dashboard"),
      apiFetch("/admin/dashboard/fees"),
    ]);

    document.getElementById("float-total").textContent    = fmt(metrics.float_total);
    document.getElementById("float-fiat").textContent     = fmt(metrics.float_fiat);
    document.getElementById("float-usdt").textContent     = parseFloat(metrics.float_usdt  || 0).toFixed(2) + " USDT";
    document.getElementById("float-usdc").textContent     = parseFloat(metrics.float_usdc  || 0).toFixed(2) + " USDC";
    document.getElementById("users-total").textContent    = metrics.users_total;
    document.getElementById("users-today").textContent    = "+" + metrics.users_new_today + " hoy";
    document.getElementById("dep-pending").textContent    = metrics.deposits_pending;
    document.getElementById("wd-pending").textContent     = metrics.withdrawals_pending;
    document.getElementById("fees-today").textContent     = fmt(metrics.fees_today);
    document.getElementById("fees-month").textContent     = fmt(metrics.fees_month);
    document.getElementById("volume-today").textContent   = fmt(metrics.volume_today);

    // Alertas de pendientes
    if (metrics.deposits_pending > 0 || metrics.withdrawals_pending > 0) {
      document.getElementById("pending-alert").classList.remove("hidden");
      document.getElementById("pending-alert").textContent =
        `⏳ ${metrics.deposits_pending} depósito(s) y ${metrics.withdrawals_pending} retiro(s) esperando aprobación`;
    }

    await loadPnL();
  } catch (err) {
    showToast("Error cargando métricas: " + err.message, "error");
  }
}

async function loadPnL() {
  const rows = await apiFetch("/admin/dashboard/pnl?period=daily");
  const tbody = document.getElementById("pnl-tbody");
  if (!tbody || !rows) return;

  tbody.innerHTML = rows.slice(-14).reverse().map(r => `
    <tr>
      <td>${r.date}</td>
      <td class="green">${fmt(r.gross_revenue)}</td>
      <td class="red">${fmt(r.expenses)}</td>
      <td class="${r.net >= 0 ? "green" : "red"}">${fmt(r.net)}</td>
    </tr>
  `).join("");
}

// ─── Depósitos ────────────────────────────────────────────────────────────────

async function loadDeposits() {
  guardAuth();
  const list = await apiFetch("/admin/deposits/pending").catch(() => []);
  const container = document.getElementById("deposits-list");
  if (!container) return;

  if (!list || list.length === 0) {
    container.innerHTML = '<p class="empty">No hay depósitos pendientes ✅</p>';
    return;
  }

  container.innerHTML = list.map(d => `
    <div class="card" id="dep-${d.id}">
      <div class="card-header">
        <div class="card-header-left">
          <span class="badge badge-pending">Pendiente</span>
          <span class="card-id">#${d.id.slice(0,8).toUpperCase()}</span>
        </div>
        <span class="card-date">${fmtDate(d.created_at)}</span>
      </div>

      <div class="card-body">
        <div class="card-amount">${fmt(d.amount)}</div>

        <div class="dep-info-grid">
          <div class="dep-info-row">
            <span class="dep-label">👤 Nombre</span>
            <span class="dep-value">${d.user?.name || "—"}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">🪪 Cédula</span>
            <span class="dep-value mono">${d.user?.cedula || "—"}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">📱 Celular</span>
            <span class="dep-value mono">${d.user?.phone || "—"}</span>
          </div>
          ${d.bank_name ? `
          <div class="dep-info-row">
            <span class="dep-label">🏦 Banco</span>
            <span class="dep-value">${d.bank_name}</span>
          </div>` : ""}
          ${d.reference_number ? `
          <div class="dep-info-row">
            <span class="dep-label">📋 Referencia</span>
            <span class="dep-value mono">${d.reference_number}</span>
          </div>` : ""}
        </div>

        ${d.voucher_media_id ? `
        <div class="voucher-wrap">
          <p class="voucher-label">Comprobante de pago</p>
          <img
            class="voucher-img"
            src="${API}/admin/deposits/${d.id}/voucher?token=${encodeURIComponent(getToken())}"
            alt="Comprobante"
            onclick="this.classList.toggle('voucher-img--expanded')"
            onerror="this.parentElement.innerHTML='<p class=\\'voucher-error\\'>No se pudo cargar la imagen</p>'"
          />
        </div>` : `<p class="voucher-missing">⚠️ Sin comprobante adjunto</p>`}

        ${d.vision_verdict ? (() => {
          const cfg = {
            approved:      { icon: "✅", label: "Aprobado por IA",   cls: "vision-approved"  },
            rejected:      { icon: "❌", label: "Rechazado por IA",  cls: "vision-rejected"  },
            review_needed: { icon: "⚠️", label: "Revisión manual",   cls: "vision-review"    },
          };
          const v = cfg[d.vision_verdict] || { icon: "🔍", label: d.vision_verdict, cls: "vision-review" };
          const pct = d.vision_confidence != null ? Math.round(d.vision_confidence * 100) : 0;
          return `
        <div class="vision-banner ${v.cls}">
          <span class="vision-icon">${v.icon}</span>
          <div class="vision-text">
            <strong>Claude Vision — ${v.label} (${pct}%)</strong>
            ${d.vision_reason ? `<span class="vision-reason">${d.vision_reason}</span>` : ""}
          </div>
        </div>`;
        })() : ""}
      </div>

      <div class="card-actions">
        <button class="btn btn-approve" onclick="approveDeposit('${d.id}')">✅ Aprobar</button>
        <button class="btn btn-reject"  onclick="promptReject('deposit', '${d.id}')">❌ Rechazar</button>
      </div>
    </div>
  `).join("");
}

async function approveDeposit(id) {
  if (!confirm("¿Aprobar este depósito?")) return;
  try {
    await apiPost(`/admin/deposits/${id}/approve`, {});
    document.getElementById(`dep-${id}`)?.remove();
    showToast("Depósito aprobado ✅");
    if (!document.querySelector(".card")) {
      document.getElementById("deposits-list").innerHTML = '<p class="empty">No hay depósitos pendientes ✅</p>';
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

// ─── Retiros ──────────────────────────────────────────────────────────────────

async function loadWithdrawals() {
  guardAuth();
  const list = await apiFetch("/admin/withdrawals/pending").catch(() => []);
  const container = document.getElementById("withdrawals-list");
  if (!container) return;

  if (!list || list.length === 0) {
    container.innerHTML = '<p class="empty">No hay retiros pendientes ✅</p>';
    return;
  }

  container.innerHTML = list.map(w => `
    <div class="card" id="wd-${w.id}">
      <div class="card-header">
        <div class="card-header-left">
          <span class="badge badge-pending">Pendiente</span>
          <span class="card-id">#${w.id.slice(0,8).toUpperCase()}</span>
        </div>
        <span class="card-date">${fmtDate(w.created_at)}</span>
      </div>

      <div class="card-body">
        <div class="wd-amount-row">
          <div class="card-amount">${fmt(w.amount)}</div>
          <div class="wd-receives">
            <span class="wd-receives-label">Recibe</span>
            <span class="wd-receives-value">${fmt(w.amount_received)}</span>
          </div>
        </div>

        <div class="wd-type-row">
          <span class="wd-badge ${w.withdrawal_type === 'instant' ? 'wd-badge--instant' : 'wd-badge--normal'}">
            ${w.withdrawal_type === 'instant' ? '⚡ Instant' : '🕐 Normal'}
          </span>
          <span class="fee-pill">Fee ${fmt(w.fee)}</span>
        </div>

        <div class="section-divider">Titular de la cuenta</div>
        <div class="dep-info-grid">
          <div class="dep-info-row">
            <span class="dep-label">👤 Nombre</span>
            <span class="dep-value">${w.user?.name || "—"}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">📱 Celular</span>
            <span class="dep-value mono">${w.user?.phone || "—"}</span>
          </div>
        </div>

        <div class="section-divider">Datos bancarios</div>
        <div class="dep-info-grid">
          <div class="dep-info-row">
            <span class="dep-label">🏦 Banco</span>
            <span class="dep-value">${w.bank_name}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">📋 Tipo</span>
            <span class="dep-value">${w.account_type}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">💳 Número</span>
            <span class="dep-value mono">${w.account_number}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">👤 Titular</span>
            <span class="dep-value">${w.account_holder}</span>
          </div>
          ${w.recipient_phone ? `
          <div class="dep-info-row">
            <span class="dep-label">📲 Destinatario</span>
            <span class="dep-value mono">${w.recipient_phone}</span>
          </div>` : ""}
          ${w.recipient_cedula ? `
          <div class="dep-info-row">
            <span class="dep-label">🪪 Cédula dest.</span>
            <span class="dep-value mono">${w.recipient_cedula}</span>
          </div>` : ""}
        </div>
      </div>

      <div class="card-actions">
        <button class="btn btn-approve" onclick="approveWithdrawal('${w.id}')">✅ Transferí</button>
        <button class="btn btn-reject"  onclick="promptReject('withdrawal', '${w.id}')">❌ Rechazar</button>
      </div>
    </div>
  `).join("");
}

async function approveWithdrawal(id) {
  if (!confirm("¿Confirmas que ya transferiste el dinero?")) return;
  try {
    await apiPost(`/admin/withdrawals/${id}/approve`, {});
    document.getElementById(`wd-${id}`)?.remove();
    showToast("Retiro aprobado ✅");
    if (!document.querySelector(".card")) {
      document.getElementById("withdrawals-list").innerHTML = '<p class="empty">No hay retiros pendientes ✅</p>';
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

// ─── Rechazar (deposit o withdrawal) ─────────────────────────────────────────

function promptReject(type, id) {
  const notes = prompt("Motivo del rechazo (opcional):");
  if (notes === null) return; // canceló
  rejectItem(type, id, notes);
}

async function rejectItem(type, id, notes) {
  const path = type === "deposit"
    ? `/admin/deposits/${id}/reject`
    : `/admin/withdrawals/${id}/reject`;
  try {
    await apiPost(path, { notes });
    document.getElementById(`${type === "deposit" ? "dep" : "wd"}-${id}`)?.remove();
    showToast("Rechazado y notificado");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

// ─── Gastos ───────────────────────────────────────────────────────────────────

async function handleExpense(e) {
  e.preventDefault();
  const body = {
    category:    document.getElementById("exp-category").value,
    description: document.getElementById("exp-description").value.trim(),
    amount_usd:  parseFloat(document.getElementById("exp-amount").value),
    expense_date: document.getElementById("exp-date").value || null,
  };
  try {
    await apiPost("/admin/dashboard/expenses", body);
    showToast("Gasto registrado ✅");
    e.target.reset();
    loadExpenses();
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

async function loadExpenses() {
  const list = await apiFetch("/admin/dashboard/expenses").catch(() => []);
  const tbody = document.getElementById("expenses-tbody");
  if (!tbody) return;
  tbody.innerHTML = (list || []).map(ex => `
    <tr>
      <td>${ex.expense_date}</td>
      <td><span class="badge">${ex.category}</span></td>
      <td>${ex.description}</td>
      <td class="red">${fmt(ex.amount_usd)}</td>
    </tr>
  `).join("") || '<tr><td colspan="4" class="empty">Sin gastos este mes</td></tr>';
}

// ─── Auto-refresh ─────────────────────────────────────────────────────────────

let _lastDepCount     = null;
let _lastWdCount      = null;
let _lastSupportCount = null;
let _lastFraudCount   = null;
const POLL_INTERVAL = 20_000; // 20 segundos

function _updateNavBadge(linkHref, count) {
  const link = document.querySelector(`.nav a[href="${linkHref}"]`);
  if (!link) return;
  const existing = link.querySelector(".nav-badge");
  if (count > 0) {
    if (existing) { existing.textContent = count; }
    else {
      const b = document.createElement("span");
      b.className = "nav-badge";
      b.textContent = count;
      link.appendChild(b);
    }
  } else {
    existing?.remove();
  }
}

async function _pollDeposits() {
  if (!isLoggedIn()) return;
  try {
    const list = await apiFetch("/admin/deposits/pending");
    const count = list?.length ?? 0;
    _updateNavBadge("deposits.html", count);
    if (_lastDepCount !== null && count > _lastDepCount) {
      showToast(`📥 Nuevo depósito pendiente (${count} total)`);
      // Recargar lista si estamos en esa página
      if (document.getElementById("deposits-list")) loadDeposits();
    }
    _lastDepCount = count;
  } catch (_) {}
}

async function _pollWithdrawals() {
  if (!isLoggedIn()) return;
  try {
    const list = await apiFetch("/admin/withdrawals/pending");
    const count = list?.length ?? 0;
    _updateNavBadge("withdrawals.html", count);
    if (_lastWdCount !== null && count > _lastWdCount) {
      showToast(`📤 Nuevo retiro pendiente (${count} total)`);
      // Recargar lista si estamos en esa página
      if (document.getElementById("withdrawals-list")) loadWithdrawals();
    }
    _lastWdCount = count;
  } catch (_) {}
}

async function _pollSupport() {
  if (!isLoggedIn()) return;
  try {
    const list = await apiFetch("/admin/support/pending");
    const count = list?.length ?? 0;
    _updateNavBadge("support.html", count);
    if (_lastSupportCount !== null && count > _lastSupportCount) {
      showToast(`🆘 Nueva solicitud de soporte (${count} total)`);
      if (document.getElementById("support-list")) loadSupport();
    }
    _lastSupportCount = count;
  } catch (_) {}
}

async function _pollFraud() {
  if (!isLoggedIn()) return;
  try {
    const data  = await apiFetch("/admin/fraud/alerts");
    const count = data?.total ?? 0;
    const highCount = (data?.alerts ?? []).filter(a => a.risk_level === "high").length;
    _updateNavBadge("fraud.html", count);
    if (_lastFraudCount !== null && count > _lastFraudCount) {
      const label = highCount > 0 ? `🔴 ${highCount} alerta(s) de alto riesgo` : `🟡 Nueva alerta de fraude`;
      showToast(`🚨 ${label}`);
      if (document.getElementById("fraud-list")) loadFraud();
    }
    _lastFraudCount = count;
  } catch (_) {}
}

async function _poll() {
  await Promise.all([_pollDeposits(), _pollWithdrawals(), _pollSupport(), _pollFraud()]);
}

function startPolling() {
  if (!isLoggedIn()) return;
  _poll(); // primera llamada inmediata para mostrar badges
  setInterval(_poll, POLL_INTERVAL);
}

// ─── Fraude ───────────────────────────────────────────────────────────────────

const FRAUD_LABELS = {
  duplicate_voucher:          { icon: "🔁", label: "Comprobante duplicado" },
  too_many_rejected_deposits: { icon: "🔄", label: "Muchos depósitos rechazados" },
  high_amount_deposit:        { icon: "💰", label: "Depósito monto alto" },
  new_user_large_deposit:     { icon: "👤", label: "Usuario nuevo, monto alto" },
  new_user_withdrawal:        { icon: "🆕", label: "Usuario nuevo retirando" },
  new_bank_account:           { icon: "🏦", label: "Nueva cuenta bancaria" },
  high_amount_withdrawal:     { icon: "💸", label: "Retiro monto alto" },
};
const RISK_COLORS = { high: "#ef4444", medium: "#f59e0b", low: "#22c55e" };

async function loadFraud() {
  guardAuth();
  const data      = await apiFetch("/admin/fraud/alerts").catch(() => ({ alerts: [] }));
  const alerts    = data?.alerts ?? [];
  const container = document.getElementById("fraud-list");
  if (!container) return;

  if (!alerts.length) {
    container.innerHTML = '<p class="empty">Sin alertas de fraude abiertas ✅</p>';
    return;
  }

  container.innerHTML = alerts.map(a => {
    const info  = FRAUD_LABELS[a.alert_type] || { icon: "⚠️", label: a.alert_type };
    const color = RISK_COLORS[a.risk_level]  || "#6b7280";
    const det   = a.details ? Object.entries(a.details).map(([k,v]) =>
      `<span class="dep-label">${k}:</span><span class="dep-value">${v}</span>`
    ).join("") : "";
    return `
    <div class="card" id="fraud-${a.id}">
      <div class="card-header">
        <div class="card-header-left">
          <span class="badge" style="background:${color}20;color:${color};border:1px solid ${color}40">
            ${info.icon} ${info.label}
          </span>
          <span style="font-size:12px;color:var(--text-muted);margin-left:8px">
            🔴 ${a.risk_level.toUpperCase()}
          </span>
        </div>
        <span class="card-date">${fmtDate(a.created_at)}</span>
      </div>
      <div class="dep-info-grid" style="margin:10px 0">
        <span class="dep-label">Usuario:</span>
        <span class="dep-value">${a.user?.name ?? "—"} · ${a.user?.phone ?? "—"}</span>
        ${det}
      </div>
      <div class="card-actions">
        <button class="btn btn-secondary" onclick="resolveFraudAlert('${a.id}')">
          ✅ Marcar resuelta
        </button>
      </div>
    </div>`;
  }).join("");
}

async function resolveFraudAlert(id) {
  await apiPost(`/admin/fraud/alerts/${id}/resolve`);
  document.getElementById(`fraud-${id}`)?.remove();
  showToast("✅ Alerta marcada como resuelta");
  _lastFraudCount = Math.max(0, (_lastFraudCount ?? 1) - 1);
  _updateNavBadge("fraud.html", _lastFraudCount);
}

// ─── Blacklist ────────────────────────────────────────────────────────────────

async function loadBlacklist() {
  const container = document.getElementById("blacklist-list");
  if (!container) return;
  const data = await apiFetch("/admin/fraud/blacklist").catch(() => null);
  const list = data?.blacklist || [];
  if (!list.length) {
    container.innerHTML = '<p class="empty">Sin entradas en blacklist.</p>';
    return;
  }
  container.innerHTML = list.map(e => `
    <div class="bl-row" id="bl-${e.id}">
      <div class="bl-info">
        ${e.phone  ? `<span class="bl-tag">📱 ${e.phone}</span>`  : ""}
        ${e.cedula ? `<span class="bl-tag">🪪 ${e.cedula}</span>` : ""}
        <span class="bl-reason">${e.reason}</span>
        <span class="bl-date">${fmtDate(e.created_at)}</span>
      </div>
      <button class="btn btn-secondary" style="font-size:12px;padding:6px 12px" onclick="removeBlacklist('${e.id}')">
        🔓 Desbloquear
      </button>
    </div>
  `).join("");
}

async function addBlacklist() {
  const phone  = document.getElementById("bl-phone")?.value.trim();
  const cedula = document.getElementById("bl-cedula")?.value.trim();
  const reason = document.getElementById("bl-reason")?.value.trim();
  if (!reason)          return showToast("⚠️ Escribe el motivo del bloqueo");
  if (!phone && !cedula) return showToast("⚠️ Ingresa teléfono o cédula");

  const res = await apiFetch("/admin/fraud/blacklist", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ phone: phone || null, cedula: cedula || null, reason }),
  }).catch(() => null);

  if (res?.ok) {
    showToast("🚫 Usuario bloqueado");
    document.getElementById("bl-phone").value  = "";
    document.getElementById("bl-cedula").value = "";
    document.getElementById("bl-reason").value = "";
    loadBlacklist();
  } else {
    showToast("❌ No se pudo bloquear");
  }
}

async function removeBlacklist(id) {
  const res = await apiFetch(`/admin/fraud/blacklist/${id}`, { method: "DELETE" }).catch(() => null);
  if (res?.ok) {
    document.getElementById(`bl-${id}`)?.remove();
    showToast("🔓 Usuario desbloqueado");
  } else {
    showToast("❌ Error al desbloquear");
  }
}

// ─── Configuración de límites de fraude ───────────────────────────────────────

const _CONFIG_META = {
  high_deposit_amount:    { label: "💰 Monto alto — Depósito ($)",       type: "decimal", min: 1 },
  high_withdrawal_amount: { label: "💸 Monto alto — Retiro ($)",          type: "decimal", min: 1 },
  max_rejected_per_hour:  { label: "🔄 Rechazos por hora antes de bloquear", type: "int",  min: 1 },
  new_user_hours:         { label: "🕐 Ventana cuenta nueva (horas)",     type: "int",     min: 1 },
  new_user_max_deposit:   { label: "👤 Depósito máx — cuenta nueva ($)",  type: "decimal", min: 1 },
};

async function loadFraudConfig() {
  const card = document.getElementById("fraud-config-card");
  if (!card) return;

  const data = await apiFetch("/admin/fraud/config").catch(() => null);
  if (!data) {
    card.innerHTML = '<p class="empty">No se pudo cargar la configuración.</p>';
    return;
  }

  // Convertir array [{key, value, label, description}] a objeto
  const cfg = {};
  for (const row of (data.config || [])) cfg[row.key] = row;

  card.innerHTML = `
    <div class="config-grid">
      ${Object.entries(_CONFIG_META).map(([key, meta]) => {
        const row   = cfg[key] || {};
        const val   = row.value ?? "";
        const desc  = row.description ?? "";
        const step  = meta.type === "decimal" ? "0.01" : "1";
        return `
        <div class="config-row">
          <div class="config-label">
            <span class="config-title">${meta.label}</span>
            <span class="config-desc">${desc}</span>
          </div>
          <input
            class="config-input"
            id="cfg-${key}"
            type="number"
            min="${meta.min}"
            step="${step}"
            value="${val}"
          />
        </div>`;
      }).join("")}
    </div>
    <div style="margin-top:16px;display:flex;justify-content:flex-end">
      <button class="btn btn-approve" onclick="saveFraudConfig()" style="min-width:160px">
        💾 Guardar cambios
      </button>
    </div>
  `;
}

async function saveFraudConfig() {
  const keys = Object.keys(_CONFIG_META);
  const payload = {};
  for (const key of keys) {
    const el = document.getElementById(`cfg-${key}`);
    if (!el) return showToast("Error leyendo formulario");
    const meta = _CONFIG_META[key];
    payload[key] = meta.type === "int" ? parseInt(el.value, 10) : parseFloat(el.value);
    if (isNaN(payload[key]) || payload[key] < meta.min) {
      return showToast(`⚠️ Valor inválido en: ${meta.label}`);
    }
  }

  const res = await apiFetch("/admin/fraud/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => null);

  if (res?.ok) {
    showToast("✅ Configuración guardada");
  } else {
    showToast("❌ No se pudo guardar");
  }
}

// ─── Soporte ──────────────────────────────────────────────────────────────────

async function loadSupport() {
  guardAuth();
  const list = await apiFetch("/admin/support/pending").catch(() => []);
  const container = document.getElementById("support-list");
  if (!container) return;

  if (!list || list.length === 0) {
    container.innerHTML = '<p class="empty">No hay solicitudes pendientes ✅</p>';
    return;
  }

  container.innerHTML = list.map(s => {
    const waLink = `https://wa.me/${s.phone.replace(/\D/g,"")}`;
    const elapsed = _timeAgo(s.created_at);
    return `
    <div class="card support-card" id="sup-${s.id}">
      <div class="card-header">
        <div class="card-header-left">
          <span class="badge badge-support">🆘 Soporte</span>
          <span class="support-elapsed">${elapsed}</span>
        </div>
        <span class="card-date">${fmtDate(s.created_at)}</span>
      </div>
      <div class="card-body">
        <div class="dep-info-grid">
          <div class="dep-info-row">
            <span class="dep-label">👤 Nombre</span>
            <span class="dep-value">${s.name || "No registrado"}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">🪪 Cédula</span>
            <span class="dep-value mono">${s.cedula || "—"}</span>
          </div>
          <div class="dep-info-row">
            <span class="dep-label">📱 Celular</span>
            <span class="dep-value mono">${s.phone}</span>
          </div>
        </div>
        <a href="${waLink}" target="_blank" class="btn btn-wa">
          💬 Abrir WhatsApp
        </a>
      </div>
      <div class="card-actions">
        <button class="btn btn-approve" onclick="attendSupport('${s.id}')">✅ Marcar atendido</button>
      </div>
    </div>`;
  }).join("");
}

async function attendSupport(id) {
  try {
    await apiPost(`/admin/support/${id}/attend`, {});
    document.getElementById(`sup-${id}`)?.remove();
    showToast("Marcado como atendido ✅");
    if (!document.querySelector(".support-card")) {
      document.getElementById("support-list").innerHTML = '<p class="empty">No hay solicitudes pendientes ✅</p>';
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

function _timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)  return `hace ${diff}s`;
  if (diff < 3600) return `hace ${Math.floor(diff/60)}min`;
  return `hace ${Math.floor(diff/3600)}h`;
}

// ─── Usuarios ─────────────────────────────────────────────────────────────────

let _searchTimer = null;

function onSearchInput(val) {
  clearTimeout(_searchTimer);
  const dropdown = document.getElementById("search-results");
  if (val.trim().length < 3) {
    dropdown.classList.add("hidden");
    return;
  }
  _searchTimer = setTimeout(() => searchUsers(val.trim()), 350);
}

async function searchUsers(q) {
  const dropdown = document.getElementById("search-results");
  dropdown.innerHTML = '<p class="search-loading">Buscando...</p>';
  dropdown.classList.remove("hidden");

  const list = await apiFetch(`/admin/users/search?q=${encodeURIComponent(q)}`).catch(() => []);

  if (!list || list.length === 0) {
    dropdown.innerHTML = '<p class="search-loading">Sin resultados</p>';
    return;
  }

  dropdown.innerHTML = list.map(u => `
    <div class="search-result-row" onclick="loadUser('${u.id}')">
      <div class="sr-name">${u.name || "—"}</div>
      <div class="sr-meta">${u.cedula || "—"} · ${u.phone || "—"}</div>
    </div>
  `).join("");
}

async function loadUser(userId) {
  document.getElementById("search-results").classList.add("hidden");
  const profile = document.getElementById("user-profile");
  profile.innerHTML = '<p class="empty">Cargando...</p>';
  profile.classList.remove("hidden");

  const u = await apiFetch(`/admin/users/${userId}`).catch(() => null);
  if (!u) {
    profile.innerHTML = '<p class="empty">Error al cargar usuario</p>';
    return;
  }

  const balUSD  = u.wallets?.find(w => w.currency === "USD")?.balance  ?? 0;
  const balUSDT = u.wallets?.find(w => w.currency === "USDT")?.balance ?? 0;
  const balUSDC = u.wallets?.find(w => w.currency === "USDC")?.balance ?? 0;

  profile.innerHTML = `
    <!-- Tarjeta principal -->
    <div class="user-card">
      <div class="user-card-header">
        <div>
          <div class="user-card-name">${u.name || "—"}</div>
          <div class="user-card-sub">Registrado ${fmtDate(u.created_at)}</div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px">
          <div class="user-balance-badge">$${Number(balUSD).toFixed(2)} USD</div>
          ${Number(balUSDT) > 0 ? `<div class="user-balance-badge" style="background:rgba(8,145,178,0.12);color:#0891b2;border-color:rgba(8,145,178,0.3)">${Number(balUSDT).toFixed(2)} USDT</div>` : ""}
          ${Number(balUSDC) > 0 ? `<div class="user-balance-badge" style="background:rgba(99,102,241,0.12);color:#6366f1;border-color:rgba(99,102,241,0.3)">${Number(balUSDC).toFixed(2)} USDC</div>` : ""}
        </div>
      </div>

      <div class="dep-info-grid" style="margin-top:14px">
        <div class="dep-info-row">
          <span class="dep-label">🪪 Cédula</span>
          <span class="dep-value mono">${u.cedula || "—"}</span>
        </div>
        <div class="dep-info-row">
          <span class="dep-label">📱 Teléfono</span>
          <span class="dep-value mono" id="disp-phone">${u.phone || "—"}</span>
        </div>
        <div class="dep-info-row">
          <span class="dep-label">📧 Email</span>
          <span class="dep-value" id="disp-email">${u.email || "—"}</span>
        </div>
        <div class="dep-info-row">
          <span class="dep-label">🔏 Dactilar</span>
          <span class="dep-value mono">${u.dactilar || "—"}</span>
        </div>
        <div class="dep-info-row">
          <span class="dep-label">🎂 Nacimiento</span>
          <span class="dep-value">${u.birth_date || "—"}</span>
        </div>
        <div class="dep-info-row">
          <span class="dep-label">🔐 Custody</span>
          <span class="dep-value">${u.custody_mode || "—"}</span>
        </div>
      </div>

      <!-- Edición inline -->
      <div class="edit-section">
        <p class="section-divider" style="margin-top:16px">Editar datos</p>
        <div class="edit-row">
          <input type="text" id="edit-name"     placeholder="Nombre completo"      value="${u.name || ""}" />
          <input type="text" id="edit-phone"    placeholder="Teléfono"             value="${u.phone || ""}" />
          <input type="text" id="edit-email"    placeholder="Email"                value="${u.email || ""}" />
          <input type="text" id="edit-dactilar" placeholder="Código dactilar (ej: E4443V2442)" value="${u.dactilar || ""}" style="font-family:var(--mono-font,monospace);text-transform:uppercase" />
          <button class="btn btn-primary btn-sm" style="margin-top:4px" onclick="saveUser('${u.id}')">💾 Guardar cambios</button>
        </div>
      </div>
    </div>

    <!-- Historial tabs -->
    <div class="hist-tabs">
      <button class="hist-tab active" onclick="showTab('deposits',   this)">📥 Depósitos (${u.deposits.length})</button>
      <button class="hist-tab"        onclick="showTab('withdrawals',this)">📤 Retiros (${u.withdrawals.length})</button>
      <button class="hist-tab"        onclick="showTab('sent',       this)">💸 Enviadas (${u.transfers_sent.length})</button>
      <button class="hist-tab"        onclick="showTab('received',   this)">💰 Recibidas (${u.transfers_received.length})</button>
    </div>

    <div id="tab-deposits"   class="hist-panel">${renderUserDeposits(u.deposits)}</div>
    <div id="tab-withdrawals"class="hist-panel hidden">${renderUserWithdrawals(u.withdrawals)}</div>
    <div id="tab-sent"       class="hist-panel hidden">${renderUserTransfers(u.transfers_sent,   'sent')}</div>
    <div id="tab-received"   class="hist-panel hidden">${renderUserTransfers(u.transfers_received,'received')}</div>
  `;
}

function showTab(name, btn) {
  document.querySelectorAll(".hist-panel").forEach(p => p.classList.add("hidden"));
  document.querySelectorAll(".hist-tab").forEach(b => b.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.remove("hidden");
  btn.classList.add("active");
}

function renderUserDeposits(list) {
  if (!list.length) return '<p class="empty">Sin depósitos</p>';
  return list.map(d => `
    <div class="hist-row">
      <div class="hist-row-left">
        <span class="hist-id">#${d.id.slice(0,8).toUpperCase()}</span>
        <span class="hist-date">${fmtDate(d.created_at)}</span>
      </div>
      <div class="hist-row-right">
        <span class="hist-amount green">+${fmt(d.amount)}</span>
        <span class="hist-status status-${d.status}">${d.status}</span>
      </div>
    </div>
    ${d.bank_name ? `<div class="hist-sub">🏦 ${d.bank_name}${d.reference_number ? ' · Ref: '+d.reference_number : ''}</div>` : ''}
  `).join("");
}

function renderUserWithdrawals(list) {
  if (!list.length) return '<p class="empty">Sin retiros</p>';
  return list.map(w => `
    <div class="hist-row">
      <div class="hist-row-left">
        <span class="hist-id">#${w.id.slice(0,8).toUpperCase()}</span>
        <span class="hist-date">${fmtDate(w.created_at)}</span>
      </div>
      <div class="hist-row-right">
        <span class="hist-amount red">-${fmt(w.amount)}</span>
        <span class="hist-status status-${w.status}">${w.status}</span>
      </div>
    </div>
    <div class="hist-sub">🏦 ${w.bank_name} · ${w.account_number} · Recibe ${fmt(w.amount_received)} · ${w.withdrawal_type}</div>
  `).join("");
}

function renderUserTransfers(list, dir) {
  if (!list.length) return `<p class="empty">Sin transferencias ${dir === 'sent' ? 'enviadas' : 'recibidas'}</p>`;
  return list.map(t => {
    const peer = dir === 'sent' ? t.to_user : t.from_user;
    const sign = dir === 'sent' ? '-' : '+';
    const cls  = dir === 'sent' ? 'red' : 'green';
    return `
      <div class="hist-row">
        <div class="hist-row-left">
          <span class="hist-id">#${t.id.slice(0,8).toUpperCase()}</span>
          <span class="hist-date">${fmtDate(t.created_at)}</span>
        </div>
        <div class="hist-row-right">
          <span class="hist-amount ${cls}">${sign}${fmt(t.amount)}</span>
          <span class="hist-status status-${t.status}">${t.status}</span>
        </div>
      </div>
      <div class="hist-sub">👤 ${peer?.name || '—'} · ${peer?.phone || '—'}${t.fee > 0 ? ' · fee '+fmt(t.fee) : ''}</div>
    `;
  }).join("");
}

async function saveUser(userId) {
  const patch = {
    name:     document.getElementById("edit-name")?.value.trim()                    || undefined,
    phone:    document.getElementById("edit-phone")?.value.trim()                   || undefined,
    email:    document.getElementById("edit-email")?.value.trim()                   || undefined,
    dactilar: document.getElementById("edit-dactilar")?.value.trim().toUpperCase() || undefined,
  };
  // Quitar campos vacíos
  Object.keys(patch).forEach(k => { if (!patch[k]) delete patch[k]; });

  try {
    await apiPatch(`/admin/users/${userId}`, patch);
    showToast("✅ Usuario actualizado");
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}
