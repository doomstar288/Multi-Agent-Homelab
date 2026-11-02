"""Harness web app: FastAPI behind Traefik + Authelia."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import audit, db, providers
from .auth import User, authenticate
from .config import Settings

HERE = Path(__file__).parent
LOCALHOST = {"127.0.0.1", "::1"}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; img-src 'self'; script-src 'self'; "
        "connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("harness")
    if not settings.allowed_users or not settings.trusted_proxies:
        log.warning("HARNESS_ALLOWED_USERS or HARNESS_TRUSTED_PROXIES is empty: all requests will be refused")

    conn = db.connect(settings.db_path)
    audit.record(conn, "system", "startup", {"providers": providers.status(settings.secrets_dir)})

    # No interactive API docs: nothing should be reachable that we didn't mean to expose.
    app = FastAPI(title="Multi-Agent Homelab", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.db = conn
    templates = Jinja2Templates(directory=HERE / "templates")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    def current_user(request: Request) -> User:
        return authenticate(request, settings)

    @app.get("/healthz", include_in_schema=False)
    def healthz(request: Request):
        # Only the container's own healthcheck may call this.
        if not request.client or request.client.host not in LOCALHOST:
            raise HTTPException(404)
        conn.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, user: User = Depends(current_user)):
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "providers": providers.status(settings.secrets_dir),
                "entries": audit.recent(conn, 25),
                "chain": audit.verify(conn),
            },
        )

    @app.get("/api/me")
    def me(user: User = Depends(current_user)):
        return {"name": user.name, "groups": list(user.groups), "email": user.email}

    @app.get("/api/providers")
    def provider_status(user: User = Depends(current_user)):
        return providers.status(settings.secrets_dir)

    @app.get("/api/audit")
    def audit_entries(limit: int = 50, user: User = Depends(current_user)):
        return audit.recent(conn, max(1, min(limit, 500)))

    @app.get("/api/audit/verify")
    def audit_verify(user: User = Depends(current_user)):
        return audit.verify(conn)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        # Plain, uninformative errors.
        return JSONResponse({"error": exc.detail if exc.status_code != 404 else "Not Found"}, status_code=exc.status_code)

    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    return app
