# Contract: POST /admin/widgets/{widget_id}/rotate-key

**Phase**: 008 | **Auth**: Tenant Admin JWT required | **Date**: 2026-06-06

## Endpoint

```
POST /admin/widgets/{widget_id}/rotate-key
Authorization: Bearer <tenant_admin_jwt>
```

## Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `widget_id` | UUID | The widget whose signing key is being rotated |

## Authorization

- Caller must have `role: tenant_admin` in their JWT.
- `tenant_id` in JWT must match `widgets.tenant_id` for the given `widget_id`.
- Platform Manager may NOT call this endpoint (cross-tenant write would violate Constitution I).

## Response — 200 OK

```json
{
  "rotated": true,
  "widget_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Error Responses

| Status | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | JWT tenant_id does not match widget's tenant_id |
| 404 | Widget not found or inactive |
| 503 | Vault unreachable — key rotation aborted, old key still valid |

## Side Effects

1. Generates a new 32-byte cryptographically random key.
2. Writes the new key to Vault at `baladiya/widget/{widget_id}/signing_key` (overwrites previous value).
3. Invalidates the in-process LRU cache entry for this `widget_id` (so the new key is picked up immediately — no 300s wait).
4. All existing visitor tokens signed with the old key become invalid on their next API call (401 response).
5. New tokens issued by `GET /widget/token` for this widget use the new key.

## No Body Required

The new key is server-generated. Callers do not supply key material.

## Audit Logging

```json
{
  "event": "widget.key.rotated",
  "widget_id": "...",
  "tenant_id": "...",
  "actor_id": "...",
  "trace_id": "..."
}
```
