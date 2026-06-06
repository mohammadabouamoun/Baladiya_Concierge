# Feature Specification: Embeddable Widget (Design F)

**Feature Branch**: `006-widget`

**Created**: 2026-06-02

**Status**: Implemented

**Covers**: Design F — React widget, signed token auth, RTL support, per-tenant origin allowlist

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Municipality Embeds the Widget (Priority: P1)

A Tenant Admin copies a one-line `<script>` embed snippet from the admin app and pastes it into their municipality website. The widget appears with the tenant's configured greeting and theme.

**Why this priority**: This is the public face of the product. Without a working embed, no resident can use the service.

**Independent Test**: The snippet `<script src="https://api/widget.js" data-widget-id="abc123"></script>` is pasted into a test HTML page served by the `host` container. The widget iframe loads, displays the tenant's greeting, and accepts a chat message.

**Acceptance Scenarios**:

1. **Given** a `<script>` with a valid `data-widget-id` is loaded on an allowed origin, **When** the loader runs, **Then** it calls `GET /widget/token?widget_id=abc123`, receives a signed short-lived JWT, and injects the iframe with that token.
2. **Given** the iframe loads, **When** it initializes, **Then** it fetches `GET /widget/config` (with the signed token) and renders the tenant's configured greeting, theme color, and language toggle (AR/EN).
3. **Given** a resident types a message and submits, **When** the chat request is made, **Then** it carries the signed token in `Authorization: Bearer ...`; the API validates the token, extracts `tenant_id`, and routes the message.

---

### User Story 2 — Widget Auth: Token, Not CORS (Priority: P1)

A developer tries to use a widget from a disallowed origin, then tries a raw `curl` with a stale/invalid token. Both are rejected.

**Why this priority**: CORS is defense-in-depth, not auth. The token is the boundary. This must be demonstrable at the defense.

**Independent Test**: Three denial cases in CI: (1) widget loaded on disallowed origin → 403 at token exchange; (2) raw `curl /chat` with no token → 401; (3) raw `curl /chat` with expired token → 401.

**Acceptance Scenarios**:

1. **Given** a `<script>` with `data-widget-id=abc123` is loaded on `evil.com` (not in the tenant's `allowed_origins`), **When** the loader calls `GET /widget/token`, **Then** the API validates the request origin, finds it is not in `allowed_origins`, and returns `403 Forbidden`.
2. **Given** a raw `curl POST /chat` with no `Authorization` header, **When** the API processes it, **Then** it returns `401 Unauthorized`.
3. **Given** a raw `curl POST /chat` with an expired JWT token (TTL elapsed), **When** the API validates it, **Then** it returns `401 Unauthorized` — no chat processing occurs.
4. **Given** a `POST /chat` with a valid token, **When** the API extracts the `tenant_id` from the token, **Then** it uses that `tenant_id` to set the RLS session — no `tenant_id` from the request body is accepted.

---

### User Story 3 — RTL/Arabic Toggle (Priority: P2)

A resident switches the widget to Arabic. The layout flips to RTL, the greeting appears in Arabic, and Arabic messages are processed correctly.

**Why this priority**: Arabic is an additive phase but the RTL toggle is part of the widget delivery.

**Independent Test**: Widget loaded → resident clicks language toggle → UI flips to RTL, greeting becomes the Arabic variant from tenant config, an Arabic message is sent and a response is received.

**Acceptance Scenarios**:

1. **Given** the widget is in English mode, **When** the resident clicks the language toggle, **Then** the widget re-renders in RTL layout with the Arabic greeting text from tenant config; the input field direction becomes RTL.
2. **Given** the widget is in Arabic mode and a resident types in Arabic, **When** the message is sent, **Then** the API classifies it as `ar` and processes it through the bilingual pipeline (language detection, multilingual retrieval).
3. **Given** the tenant has no Arabic greeting configured, **When** the resident switches to Arabic, **Then** the widget falls back to the English greeting — no error, no empty string.

---

### Edge Cases

- What if the `widget.js` loader is blocked by a browser ad blocker? The host site degrades gracefully — no error thrown; the widget simply doesn't appear.
- What if the signed token is issued and the tenant is suspended before it expires? Chat requests with the token return `403 Tenant Suspended` at the middleware level (tenant status check is per-request).
- What if the resident's session TTL expires mid-conversation? The next message starts a new session; the widget shows a "Your session has expired" notice and the conversation is refreshed.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The widget is a standalone React (Vite) application, bundled to a small gzipped bundle (target < 100 KB). Served from the `widget` static server or MinIO.
- **FR-002**: A `widget.js` loader at `GET /widget.js` — host pastes one `<script data-widget-id="...">` and the loader injects the iframe.
- **FR-003**: The loader exchanges `widget_id` + request origin for a signed short-lived JWT (`GET /widget/token`). The API validates: widget_id exists, origin is in `tenant.allowed_origins`. Reject with `403` if origin is not allowed.
- **FR-004**: Every chat request from the widget carries the signed JWT in `Authorization: Bearer`. The API validates it; `tenant_id` comes from the token claim only.
- **FR-005**: CORS headers and `CSP: frame-ancestors` are defense-in-depth around the token auth boundary — they are never the auth boundary themselves. The origin rejection that matters is the 403 at token exchange (FR-003).
- **FR-006**: The widget MUST support RTL layout — when the resident selects Arabic, the widget re-renders RTL using a CSS `dir="rtl"` toggle; no separate Arabic bundle.
- **FR-007**: Greeting and theme (color, logo URL) are fetched from `GET /widget/config` using the signed token. These come from `tenant.settings.widget_config`.
- **FR-008**: Widget token TTL MUST be short (target: 1 hour) and non-renewable by the resident — expiry returns `401`; the loader must re-exchange if the page is reloaded.
- **FR-009**: `CSP: frame-ancestors` header MUST be set on widget responses to the `allowed_origins` list — this is defense-in-depth alongside CORS.
- **FR-010**: The Tenant Admin can copy the embed snippet from the Streamlit admin — it is generated server-side using the tenant's `widget_id` and API URL.

### Key Entities

- **Widget**: `id (widget_id)`, `tenant_id`, `allowed_origins ([str])`, `is_active`, `created_at`
- **WidgetConfig** (from tenant settings): `greeting_en`, `greeting_ar`, `theme_color`, `logo_url`, `enabled_tools ([str])`, `persona`
- **WidgetToken** (JWT payload): `tenant_id`, `widget_id`, `exp`, `iat`, `jti (unique per issuance)`

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Widget bundle size < 100 KB gzipped (measured in CI build step).
- **SC-002**: Widget loads and first message round-trip completes in < 3s on a simulated 3G connection (manual or Lighthouse CI test).
- **SC-003**: All three denial cases pass in CI: disallowed-origin → 403, no-token → 401, expired-token → 401.
- **SC-004**: RTL toggle renders correctly — manual verification at defense demo.
- **SC-005**: Arabic fallback (no Arabic greeting configured) renders the English greeting without error.

---

## Assumptions

- The widget iframe is hosted at `/widget/` as a static bundle. The loader `widget.js` injects the iframe — same-origin embedding is not required (it is cross-origin by design).
- Widget token is a JWT signed with a per-widget HMAC secret stored in Vault. The loader receives it via the API, not by any client-visible means.
- The `host` nginx container serves the mock municipality demo site for the defense demo — it has the widget script tag embedded.
- The Streamlit admin's "Embed Snippet" page shows the one-line `<script>` tag — no customization required beyond copy-paste.
- RTL support is a CSS/HTML direction change, not a separate build. The widget reads the selected language from state and toggles `document.dir`.
