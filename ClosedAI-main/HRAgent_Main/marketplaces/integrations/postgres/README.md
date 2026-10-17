# PostgreSQL integration

Schema inspection and SQL queries against a PostgreSQL database via Postgres
MCP Pro (`crystaldba/postgres-mcp`).

> **Security constraint:** restricted mode (`--restricted`) is the default —
> read-only access, execution-time limits, and rejection of `COMMIT`/`ROLLBACK`
> and other mutating statements. Do not ship a template that disables it.

| | |
|---|---|
| Category | Databases |
| Authentication | `DATABASE_URI` (connection string) |
| Server | `crystaldba/postgres-mcp` (confirmed) |
| Transport | stdio (`uvx postgres-mcp --restricted`) |
| Status | not installed |

> **Flag verification pending (Phase 5):** confirm the exact restricted-mode flag
> for the installed `postgres-mcp` version (`--restricted` / env var) before the
> plugin ships.

## Install

Install from the marketplace (attaches a server named `postgres`) via
`POST /api/plugins/install` with `source = <resolved ./marketplaces/integrations/postgres path>`.

## Credentials

Store the connection string as secret **`DATABASE_URI`** (e.g.
`postgresql://user:pass@host:5432/db`). A read-only DB role is strongly
recommended so the server itself cannot exceed restricted mode's guarantees.

## Verify

- Phase 5 repo check: `crystaldba/postgres-mcp` — active, security-focused.
- Probe: `POST /api/mcp/test` → tools list.
- Execution: `get_schema` / `list_tables` run read-only; a mutating statement is
  rejected by restricted mode.
