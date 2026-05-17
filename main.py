"""BananaPay — FastAPI entry point.

Desarrollo local (accesible desde el celular en la misma red WiFi):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Producción:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import health, webhook, dev as dev_router
from app.api.app import auth as app_auth
from app.api.app import me as app_me
from app.api.app import transfer as app_transfer
from app.api.app import deposit as app_deposit
from app.api.app import withdraw as app_withdraw
from app.api.admin import auth as admin_auth
from app.api.admin import dashboard as admin_dashboard
from app.api.admin import deposits as admin_deposits
from app.api.admin import fraud as admin_fraud
from app.api.admin import history as admin_history
from app.api.admin import support as admin_support
from app.api.admin import users as admin_users
from app.api.admin import withdrawals as admin_withdrawals
from app.config import settings
from app.core.limiter import limiter
from app.core.session import session_manager
from app.utils.logger import get_logger


# ── Middleware: IP whitelist para rutas /admin/* ──────────────────────────────

class AdminIPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    En producción bloquea el panel admin a IPs no autorizadas.
    Configura ADMIN_IP_WHITELIST en .env como IPs separadas por coma:
        ADMIN_IP_WHITELIST=203.0.113.10,198.51.100.5
    Si la variable está vacía o no es producción → permite todo.
    """

    def __init__(self, app, whitelist: list[str]) -> None:
        super().__init__(app)
        self.whitelist = set(ip.strip() for ip in whitelist if ip.strip())

    async def dispatch(self, request: Request, call_next: any) -> Response:
        if self.whitelist and request.url.path.startswith("/admin"):
            # Respetar X-Forwarded-For si hay reverse proxy (nginx, Caddy, etc.)
            forwarded = request.headers.get("X-Forwarded-For", "")
            client_ip = forwarded.split(",")[0].strip() if forwarded \
                else (request.client.host if request.client else "")

            if client_ip not in self.whitelist:
                logger.warning("Admin acceso bloqueado desde IP %s → %s", client_ip, request.url.path)
                return Response(
                    content='{"detail":"Acceso no autorizado"}',
                    status_code=403,
                    media_type="application/json",
                )
        return await call_next(request)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("BananaPay arrancando en modo '%s'", settings.app_env)

    # En producción el listener corre como proceso separado (worker: python worker.py).
    # En desarrollo lo arrancamos inline para no necesitar dos terminales.
    listener_task = None
    if not settings.deposit_listener_worker:
        from app.modules.crypto.deposit_listener import run_deposit_listener
        listener_task = asyncio.create_task(run_deposit_listener())
        logger.info("BananaPay: deposit_listener iniciado inline (modo desarrollo)")
    else:
        logger.info("BananaPay: deposit_listener delegado al proceso worker (producción)")

    yield

    # Apagar limpiamente
    if listener_task is not None:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
    await session_manager.close()
    from app.integrations.redis_client import close_redis
    await close_redis()
    logger.info("BananaPay apagado correctamente")


def _check_production_secrets() -> None:
    """
    Bloquea el arranque si variables críticas tienen valores inseguros.
    Corre solo en producción — en desarrollo se permite todo.
    """
    errors = []

    if settings.secret_key == "change-me-in-production":
        errors.append("SECRET_KEY tiene el valor por defecto — es forjable por cualquiera")

    if not settings.wallet_encryption_key:
        errors.append("WALLET_ENCRYPTION_KEY vacía — private keys sin cifrar")

    if not settings.whatsapp_app_secret:
        errors.append("WHATSAPP_APP_SECRET vacío — webhook sin autenticación")

    if not settings.supabase_service_key:
        errors.append("SUPABASE_SERVICE_KEY vacía — sin acceso a la base de datos")

    if errors:
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        raise RuntimeError(
            f"\n\n🚨 BananaPay no puede arrancar en producción:\n{msg}\n\n"
            "Configura las variables de entorno antes de desplegar.\n"
        )


def create_app() -> FastAPI:
    if settings.is_production:
        _check_production_secrets()

    if settings.is_production and settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)

    app = FastAPI(
        title="BananaPay API",
        description="Fintech ecuatoriana 100% vía WhatsApp",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # Rate limiter — contadores en Redis, responde 429 al exceder el límite
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Request body size limit — protege contra payloads gigantes (ataques DoS)
    # El webhook de Meta nunca supera ~50 KB; comprobantes de depósito son imágenes
    # que se descargan desde Meta, no se suben directamente → 2 MB es más que suficiente.
    _MAX_BODY_MB   = 2
    _MAX_BODY_SIZE = _MAX_BODY_MB * 1024 * 1024

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_SIZE:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content={"detail": f"Cuerpo demasiado grande (máximo {_MAX_BODY_MB} MB)"},
            )
        return await call_next(request)

    # Security headers — protegen contra clickjacking, MIME sniffing, XSS, etc.
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["X-Frame-Options"]          = "DENY"
        response.headers["X-XSS-Protection"]         = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
        if settings.is_production:
            # HSTS — fuerza HTTPS por 1 año, incluye subdominios
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # IP whitelist admin — solo activo si hay IPs configuradas en .env
    whitelist = [ip for ip in settings.admin_ip_whitelist.split(",") if ip.strip()] \
        if getattr(settings, "admin_ip_whitelist", "") else []
    app.add_middleware(AdminIPWhitelistMiddleware, whitelist=whitelist)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [settings.api_base_url],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(webhook.router)

    # App mobile
    app.include_router(app_auth.router)
    app.include_router(app_me.router)
    app.include_router(app_transfer.router)
    app.include_router(app_deposit.router)
    app.include_router(app_withdraw.router)

    # Endpoints de prueba — solo en development
    if not settings.is_production:
        app.include_router(dev_router.router)

    # Panel admin
    app.include_router(admin_auth.router)
    app.include_router(admin_dashboard.router)
    app.include_router(admin_deposits.router)
    app.include_router(admin_withdrawals.router)
    app.include_router(admin_users.router)
    app.include_router(admin_history.router)
    app.include_router(admin_support.router)
    app.include_router(admin_fraud.router)

    # Panel admin — sirve los archivos estáticos en /panel
    # Accesible en: https://api.bananapay.ec/panel/index.html
    import os
    panel_path = os.path.join(os.path.dirname(__file__), "panel")
    if os.path.isdir(panel_path):
        app.mount("/panel", StaticFiles(directory=panel_path, html=True), name="panel")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",   # accesible desde el celular en la misma red
        port=8000,
        reload=True,
    )
