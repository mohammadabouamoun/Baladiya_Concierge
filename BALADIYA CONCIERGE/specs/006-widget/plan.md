# Implementation Plan: Embeddable Widget

**Branch**: `006-widget` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Build a React (Vite) chat widget served as a static bundle, a `widget.js` loader that injects the iframe and exchanges a `widget_id` for a signed JWT, per-tenant CORS + CSP enforcement, and an RTL Arabic toggle. All authentication is token-based — CORS is depth, not the boundary.

## Technical Context

**Language/Version**: React 18 + TypeScript (widget); Python 3.11 FastAPI (API token endpoint); nginx (widget static server + host demo site)

**Primary Dependencies**: React, Vite, tailwindcss (RTL via `dir` attribute); PyJWT (JWT signing in API); httpx (widget config fetch)

**Storage**: `widgets` table in Postgres (tenant_id RLS); widget JWT signed with HMAC secret from Vault

**Testing**: pytest for API token endpoints; Playwright or manual for widget UI; bundle size check in CI

**Target Platform**: `widget` Docker service (nginx static), `api` Docker service (token + config endpoints), `host` Docker service (demo site)

**Performance Goals**: Widget bundle < 100 KB gzipped; first message round-trip < 3s

**Constraints**: `tenant_id` comes from verified JWT token claim ONLY — never from widget URL params or postMessage body; widget token TTL = 1 hour (non-renewable without page reload); disallowed origin → 403 at token exchange (NOT at CORS layer)

## Constitution Check

- [x] Widget auth = signed JWT, not CORS
- [x] `tenant_id` from token claim only — widget cannot inject its own
- [x] Server-side origin validation at token exchange (403 on mismatch)
- [x] CORS + CSP are defense-in-depth, not the auth boundary
- [x] Token TTL short (1 hour); stale token → 401

## Project Structure

```text
widget/
├── Dockerfile                  ← nginx serving /dist static bundle
├── nginx.conf
└── src/
    ├── main.tsx                ← React entry; fetches config; renders ChatWidget
    ├── App.tsx                 ← loading/error/ready state machine; injects --accent CSS var
    ├── components/
    │   ├── ChatWidget.tsx      ← container: message list + input + lang toggle
    │   ├── MessageList.tsx
    │   └── LangToggle.tsx      ← sets document.dir = "rtl"|"ltr"
    └── hooks/
        └── useChat.ts          ← fetch POST /chat with Bearer token; manage turns

api/
├── domain/
│   └── widget.py              ← Widget model + Pydantic schemas (WidgetConfig includes enabled_tools, persona)
├── repositories/
│   └── widget_repo.py         ← WidgetRepository (BaseRepository) + PlatformWidgetRepository
├── services/
│   └── widget_service.py      ← create_widget(), update_widget() — keeps ORM out of router
└── api/
    └── widget/
        ├── router.py          ← GET /widget/token, GET /widget/config, GET /widget.js, widget CRUD
        └── token_service.py   ← validate widget_id + origin; sign JWT with jwt_secret (see DECISIONS.md)

host/
├── index.html                 ← mock municipality demo site with <script> embed tag
└── nginx.conf                 ← static server config
```

## Token Flow

```
1. Browser loads municipality site with:
   <script src="https://api/widget.js" data-widget-id="abc123"></script>

2. widget.js loader runs:
   - Reads data-widget-id from script tag
   - Reads window.location.origin
   - GET /widget/token?widget_id=...&origin=... (query params, no body)

3. API /widget/token:
   - Lookup widget by id → get tenant_id + allowed_origins
   - If origin NOT in allowed_origins → 403
   - Sign JWT { tenant_id, widget_id, exp: now+3600, jti: uuid }
   - Return { token, config_url }

4. loader injects: <iframe src="/widget/?token=...">

5. Widget iframe loads, fetches GET /widget/config (Authorization: Bearer token)
   → Returns { greeting_en, greeting_ar, theme_color, logo_url }

6. Every POST /chat carries Authorization: Bearer token
   → API validates JWT, extracts tenant_id, sets RLS session variable
```

## RTL Implementation

The widget has a single `lang` state (`en` | `ar`). The `LangToggle` component sets `document.documentElement.dir = lang === "ar" ? "rtl" : "ltr"` and Tailwind's RTL utilities handle layout flip. No separate bundle — same JS, CSS direction driven by `dir` attribute.
