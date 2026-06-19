"""Widget API endpoints.

GET  /widget/token?widget_id=&origin=   — public; validates origin → signed JWT
GET  /widget/config                     — requires valid widget Bearer token
GET  /widget.js                         — public; serves the loader script
POST /widget/widgets                    — tenant admin: create widget
GET  /widget/widgets                    — tenant admin: list widgets
PATCH /widget/widgets/{id}              — tenant admin: update widget
"""
from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.security import TokenClaims, get_current_user
from api.domain.widget import WidgetConfig, WidgetCreate, WidgetRead, WidgetUpdate
from api.infra.db import get_db, get_session_factory
from api.repositories.tenant_repo import PlatformTenantRepository
from api.repositories.widget_repo import PlatformWidgetRepository, WidgetRepository
from api.services.widget_service import create_widget, update_widget
from api.api.widget.token_service import issue_token

logger = structlog.get_logger(__name__)

router = APIRouter()

_LOADER_JS = r"""
(function () {
  var scripts = document.querySelectorAll('script[data-widget-id]');
  var script = scripts[scripts.length - 1];
  if (!script) return;
  var widgetId = script.getAttribute('data-widget-id');
  var apiBase = script.getAttribute('data-api-base') || '{api_base}';
  var origin = window.location.origin;

  fetch(apiBase + '/widget/token?widget_id=' + encodeURIComponent(widgetId) + '&origin=' + encodeURIComponent(origin))
    .then(function (r) {
      if (!r.ok) { console.warn('[baladiya] widget denied:', r.status); return null; }
      return r.json();
    })
    .then(function (data) {
      if (!data || !data.token) return;

      // ── Bubble icons (tenant logo when closed, X when open) ─────
      var widgetAppBase = script.getAttribute('data-widget-app') || '{widget_app_base}';
      var closedIcon = '<img src="' + widgetAppBase + '/logo.png" alt="" '
        + 'style="width:100%;height:100%;border-radius:50%;object-fit:cover" '
        + 'onerror="this.remove()">';
      var openIcon = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

      // ── Bubble button (inset-inline-start: left in EN, right in AR) ─
      var btn = document.createElement('button');
      btn.title = 'Chat with us';
      btn.style.cssText = [
        'position:fixed', 'bottom:20px', 'inset-inline-start:20px',
        'width:56px', 'height:56px', 'border-radius:50%',
        'background:#1a3a2a', 'border:none', 'cursor:pointer',
        'padding:0', 'overflow:hidden',
        'box-shadow:0 4px 16px rgba(0,0,0,0.25)',
        'z-index:2147483647', 'display:flex',
        'align-items:center', 'justify-content:center',
        'transition:transform 0.15s'
      ].join(';');
      btn.innerHTML = closedIcon;

      // ── Chat iframe (hidden until bubble clicked) ───────────────
      var iframe = document.createElement('iframe');
      iframe.src = widgetAppBase + '/?token=' + encodeURIComponent(data.token);
      iframe.style.cssText = [
        'position:fixed', 'bottom:88px', 'inset-inline-start:20px',
        'width:380px', 'height:560px', 'border:none',
        'border-radius:16px',
        'box-shadow:0 8px 32px rgba(0,0,0,0.18)',
        'z-index:2147483646',
        'display:none',
        'transition:opacity 0.2s'
      ].join(';');
      iframe.title = 'Baladiya Chat';

      var open = false;
      btn.addEventListener('click', function () {
        open = !open;
        iframe.style.display = open ? 'block' : 'none';
        btn.style.transform = open ? 'scale(0.92)' : 'scale(1)';
        btn.innerHTML = open ? openIcon : closedIcon;
      });

      document.body.appendChild(iframe);
      document.body.appendChild(btn);
    })
    .catch(function (err) {
      console.warn('[baladiya] widget load error:', err);
    });
})();
"""


class WidgetTokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"


def _build_csp(origins: list[str]) -> str:
    """Build Content-Security-Policy frame-ancestors value from allowed_origins list."""
    parts = ["'self'"] + [o.rstrip("/") for o in origins if o.strip()]
    return f"frame-ancestors {' '.join(parts)}"


# ── Helpers ────────────────────────────────────────────────────────────────

async def _unscoped_db():
    """Session without RLS — for public endpoints that don't have a tenant yet."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def _require_visitor(
    claims: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    if claims.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_id required")
    return claims


def _require_tenant_admin(
    claims: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    if claims.role != "tenant_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_admin role required")
    if claims.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_id required")
    return claims


async def _admin_db(
    claims: Annotated[TokenClaims, Depends(_require_tenant_admin)],
) -> AsyncSession:
    async for session in get_db(claims):
        yield session


# ── Public: loader script ──────────────────────────────────────────────────

@router.get(".js", response_class=PlainTextResponse, tags=["widget"])
async def widget_loader(request: Request) -> PlainTextResponse:
    from api.core.config import get_settings
    api_base = str(request.base_url).rstrip("/")
    settings = get_settings()
    widget_app_base = getattr(settings, "widget_app_url", "http://localhost:3000")
    js = _LOADER_JS.replace("{api_base}", api_base).replace("{widget_app_base}", widget_app_base)
    return PlainTextResponse(
        content=js,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


# ── Public: token exchange ─────────────────────────────────────────────────

@router.get("/token", response_model=WidgetTokenResponse, tags=["widget"])
async def get_widget_token(
    widget_id: uuid.UUID = Query(...),
    origin: str = Query(...),
    session: AsyncSession = Depends(_unscoped_db),
) -> WidgetTokenResponse:
    """Issue a signed short-lived JWT (TTL 1h) after validating origin.

    Returns 403 if origin is not in allowed_origins — this is the auth boundary,
    not CORS.
    """
    token = await issue_token(widget_id, origin, session)
    return WidgetTokenResponse(token=token)


# ── Authenticated: widget config ───────────────────────────────────────────

@router.get("/config", response_model=WidgetConfig, tags=["widget"])
async def get_widget_config(
    claims: Annotated[TokenClaims, Depends(_require_visitor)],
    response: Response,
) -> WidgetConfig:
    """Return tenant widget config (greeting, theme, logo). Requires valid widget JWT.

    Sets Content-Security-Policy: frame-ancestors dynamically from the widget's
    allowed_origins list (FR-009).
    """
    factory = get_session_factory()
    async with factory() as db:
        tenant_repo = PlatformTenantRepository(db)
        tenant = await tenant_repo.get(claims.tenant_id)

        # Look up allowed_origins from the widget for dynamic CSP (FR-009)
        allowed_origins: list[str] = []
        if claims.widget_id is not None:
            widget_repo = PlatformWidgetRepository(db)
            widget = await widget_repo.get_by_widget_id(claims.widget_id)
            if widget:
                allowed_origins = widget.allowed_origins or []

    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.status == "suspended":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant suspended")

    # FR-009: set CSP frame-ancestors to the widget's allowed_origins
    response.headers["Content-Security-Policy"] = _build_csp(allowed_origins)
    response.headers["X-Content-Type-Options"] = "nosniff"

    wc = (tenant.settings or {}).get("widget_config", {})
    return WidgetConfig(
        greeting_en=wc.get("greeting_en", "Hello! How can I help you today?"),
        greeting_ar=wc.get("greeting_ar", ""),
        theme_color=wc.get("theme_color", "#1a3a2a"),
        logo_url=wc.get("logo_url", ""),
        enabled_tools=wc.get("enabled_tools", ["rag_search", "capture_request", "escalate"]),
        persona=wc.get("persona", ""),
        phone_country_code=wc.get("phone_country_code", "961"),
    )


# ── Tenant Admin: widget CRUD ──────────────────────────────────────────────

@router.post("/widgets", response_model=WidgetRead, status_code=status.HTTP_201_CREATED, tags=["widget"])
async def create_widget_route(
    body: WidgetCreate,
    claims: Annotated[TokenClaims, Depends(_require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(_admin_db)],
) -> WidgetRead:
    widget = await create_widget(body, claims.tenant_id, db)
    return WidgetRead.model_validate(widget)


@router.get("/widgets", response_model=list[WidgetRead], tags=["widget"])
async def list_widgets(
    claims: Annotated[TokenClaims, Depends(_require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(_admin_db)],
) -> list[WidgetRead]:
    repo = WidgetRepository(db, claims.tenant_id)
    widgets = await repo.list()
    return [WidgetRead.model_validate(w) for w in widgets]


@router.patch("/widgets/{widget_id}", response_model=WidgetRead, tags=["widget"])
async def update_widget_route(
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    claims: Annotated[TokenClaims, Depends(_require_tenant_admin)],
    db: Annotated[AsyncSession, Depends(_admin_db)],
) -> WidgetRead:
    widget = await update_widget(widget_id, body, claims.tenant_id, db)
    return WidgetRead.model_validate(widget)
