# Tasks: Embeddable Widget

**Branch**: `006-widget` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [X] **T-001** Alembic migration: `widgets` table with `tenant_id` RLS policy; `allowed_origins text[]` column
- [X] **T-002** Scaffold React + Vite widget project (`widget/`); install tailwindcss with RTL plugin; configure Vite for small bundle output
- [X] **T-003** `api/domain/widget.py` — `Widget` SQLAlchemy model + `WidgetCreate`, `WidgetToken` Pydantic schemas

---

## Phase 2: Foundational — Token Service & Repository

- [X] **T-010** `api/repositories/widget_repo.py` — `WidgetRepository` (BaseRepository); `get_by_widget_id(widget_id)` → returns Widget with `allowed_origins`
- [X] **T-011** `api/api/widget/token_service.py` — `issue_token(widget_id, request_origin)`: lookup widget → validate origin in `allowed_origins` → 403 if not → sign JWT with HMAC secret from Vault; TTL 3600s
- [X] **T-012** HMAC secret stored in Vault under `secret/widget-signing-key`; resolved at API startup via Vault client

---

## Phase 3: API Endpoints (US1 + US2)

- [X] **T-020** `GET /widget/token?widget_id=&origin=` — validates origin, returns signed JWT; rejects with 403 on disallowed origin
- [X] **T-021** `GET /widget/config` — requires valid widget Bearer token; returns `{greeting_en, greeting_ar, theme_color, logo_url}` from `tenant.settings.widget_config`
- [X] **T-022** `GET /widget.js` — serves the loader script (plain JS); no auth required (public)
- [X] **T-023** CORS middleware: per-tenant `allowed_origins` from widget config; `CSP: frame-ancestors` header on all widget responses

---

## Phase 4: Loader Script (US1)

- [X] **T-030** `widget/src/widget.js` — reads `data-widget-id` from script tag; reads `window.location.origin`; calls `GET /widget/token`; injects `<iframe src="/widget/?token=...">` into page; handles 403 gracefully (no iframe injected)

---

## Phase 5: React Widget (US1 + US3)

- [X] **T-040** `ChatWidget.tsx` — renders conversation; fetches config on load; handles token expiry (401 → show "session expired" notice)
- [X] **T-041** `MessageList.tsx` — displays turns; RTL-aware text alignment
- [X] **T-042** `LangToggle.tsx` — toggles `document.documentElement.dir`; updates `lang` state; falls back to English greeting if Arabic greeting is empty
- [X] **T-043** `useChat.ts` — `POST /chat` with `Authorization: Bearer token`; manages conversation turns in state
- [X] **T-044** Streamlit admin: widget management page (create widget, set `allowed_origins`, copy embed snippet)

---

## Phase 6: Demo Site & CI (US2)

- [X] **T-050** `host/nginx.conf` — serve mock municipality demo site HTML with `<script data-widget-id="...">` embed tag using Tenant A's widget_id
- [X] **T-051** [P] CI test: GET /widget/token with disallowed origin → 403
- [X] **T-052** [P] CI test: POST /chat with no Authorization header → 401
- [X] **T-053** [P] CI test: POST /chat with expired JWT → 401
- [X] **T-054** [P] CI bundle size check: `widget/dist/*.js` gzipped < 100 KB

---

## Dependencies & Execution Order

```
T-001 → T-003 → T-010 → T-011 → T-012
T-012 → T-020 → T-021 → T-022 → T-023
T-022 → T-030
T-023 → T-040 → T-041 → T-042 → T-043 → T-044
T-002 (parallel with T-001)
T-043 → T-050 → T-051, T-052, T-053, T-054 [P]
```

**Gate**: Widget bundle < 100 KB gzipped; all 3 denial probes pass in CI; embed snippet works on `host` container; RTL toggle works manually.
