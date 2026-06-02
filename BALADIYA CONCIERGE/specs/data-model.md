# Data Model — Baladiya Concierge

All tenant-owned tables carry `tenant_id uuid NOT NULL` and have RLS enabled.
Platform-owned tables (`platform_managers`, `audit_log`) have no `tenant_id` and are accessible only by Platform Manager routes.

---

## Platform Tables (no RLS, no tenant_id)

### `platform_managers`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `email` | text UNIQUE NOT NULL | |
| `hashed_password` | text NOT NULL | |
| `created_at` | timestamptz | default now() |

### `tenants`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | the `tenant_id` referenced everywhere |
| `name` | text NOT NULL | municipality name |
| `plan` | text | e.g., `basic`, `pro` |
| `status` | text | `active` \| `suspended` \| `erased` |
| `settings` | jsonb | widget_config, guardrail_config, rate_limits, persona |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `audit_log`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `actor_id` | uuid NOT NULL | platform_manager or tenant_admin id |
| `actor_role` | text | `platform_manager` \| `tenant_admin` |
| `action` | text | e.g., `provision_tenant`, `erase_tenant`, `suspend_tenant` |
| `tenant_id` | uuid NULLABLE | null for cross-tenant platform actions |
| `metadata` | jsonb | action-specific details |
| `created_at` | timestamptz | |

---

## Tenant Tables (all have RLS enabled, `tenant_id NOT NULL`)

### `tenant_admins`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL FK → tenants.id | RLS |
| `email` | text NOT NULL | |
| `hashed_password` | text NOT NULL | |
| `created_at` | timestamptz | |

### `widgets`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | this is the `widget_id` in the embed snippet |
| `tenant_id` | uuid NOT NULL FK → tenants.id | RLS |
| `allowed_origins` | text[] | validated at token exchange |
| `is_active` | boolean | |
| `created_at` | timestamptz | |

### `cms_entries`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL FK → tenants.id | RLS |
| `title` | text NOT NULL | |
| `body` | text NOT NULL | full content |
| `category` | text | roads, water, electricity, etc. |
| `lang` | text | `en` \| `ar` |
| `embedding_status` | text | `pending` \| `done` \| `failed` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `cms_chunks` (pgvector)
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL | RLS — also the vector isolation boundary |
| `entry_id` | uuid NOT NULL FK → cms_entries.id | cascade delete |
| `chunk_text` | text NOT NULL | |
| `embedding` | vector(1536) | dimension matches the chosen hosted model |
| `chunk_index` | int | order within the entry |
| `metadata` | jsonb | lang, category, title for metadata filtering |
| `created_at` | timestamptz | |

> **Index**: `CREATE INDEX ON cms_chunks USING hnsw (embedding vector_cosine_ops)` — filtered by `tenant_id` at query time.

### `capture_requests`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL FK → tenants.id | RLS |
| `session_id` | text NOT NULL | resident's session key (from Redis) |
| `name` | text NULLABLE | resident-provided |
| `contact` | text NULLABLE | phone or email (PII — redacted in logs) |
| `location` | text NULLABLE | |
| `intent` | text NOT NULL | report \| question \| human |
| `description` | text NOT NULL | the resident's original message |
| `status` | text | `open` \| `escalated` \| `resolved` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `escalation_tickets`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL FK → tenants.id | RLS |
| `capture_request_id` | uuid NULLABLE FK → capture_requests.id | |
| `reason` | text NOT NULL | why escalated |
| `status` | text | `open` \| `closed` |
| `created_at` | timestamptz | |
| `closed_at` | timestamptz NULLABLE | |

---

## Redis Keys (not DB, but part of the data model)

| Key Pattern | TTL | Contents |
|---|---|---|
| `session:{session_id}:{tenant_id}` | 30 min (configurable) | `{turns: [{role, content}], created_at}` |
| `ratelimit:{tenant_id}:{endpoint}:{window}` | 1 min | sliding window counter |
| `ratelimit:capture:{session_id}:{tenant_id}` | 1 min | per-session capture_request counter |

---

## RLS Policy Template

Applied to every tenant table by Alembic migration:

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON {table_name}
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
```

The `true` flag makes `current_setting` return NULL instead of raising an exception when the variable is not set (e.g., during migrations). This prevents migration failures; migrations run as superuser with RLS bypassed.

---

## MinIO Object Layout

```
tenants/{tenant_id}/
├── cms/             ← uploaded images/attachments for CMS entries
└── evals/           ← eval reports, snapshots

modelserver/
├── classifier.joblib   ← (or classifier.onnx)
└── model_card.md
```

---

## Erasure Checklist (right-to-erasure verification)

When `DELETE /platform/tenants/{id}` is called, ALL of the following must be cleared:

1. `session:*:{tenant_id}` keys in Redis — use SCAN with pattern `session:*:{tenant_id}` then DEL (tenant_id is the suffix, not prefix)
2. `ratelimit:{tenant_id}:*` keys in Redis
3. `cms_chunks` WHERE `tenant_id = ?` (vectors)
4. `capture_requests` WHERE `tenant_id = ?`
5. `escalation_tickets` WHERE `tenant_id = ?`
6. `cms_entries` WHERE `tenant_id = ?`
7. `widgets` WHERE `tenant_id = ?`
8. `tenant_admins` WHERE `tenant_id = ?`
9. MinIO objects under `tenants/{tenant_id}/`
10. `tenants` WHERE `id = ?`
11. Write `audit_log` record (on platform connection, after all deletes)
