# Microsoft 365 integration

Outlook, Calendar, Contacts, OneDrive (personal mode) and Teams/SharePoint
(org mode) via `@softeria/ms-365-mcp-server`.

| | |
|---|---|
| Category | Communication |
| Authentication | Microsoft Entra ID (OAuth) |
| Server | `@softeria/ms-365-mcp-server` (confirmed) |
| Transport | stdio (`npx -y @softeria/ms-365-mcp-server`) |
| Status | not installed |

## Install

Install from the marketplace (attaches a server named `microsoft-365`) via
`POST /api/plugins/install` with `source = <resolved ./marketplaces/integrations/microsoft-365 path>`.

## Credentials

Requires an Azure app registration. Secrets resolved at conversation build:

- `MS365_MCP_CLIENT_ID`
- `MS365_MCP_CLIENT_SECRET`
- `MS365_MCP_TENANT_ID`

Optional hardening: `READ_ONLY=1`, `MS365_MCP_ALLOWED_SCOPES` (least-privilege),
and org-mode extras (`MS365_MCP_ORGANIZATION` etc.) for Teams/SharePoint.

## Verify

- Phase 5 repo check: `@softeria/ms-365-mcp-server` — active, well-maintained.
- Probe: `POST /api/mcp/test` → tools list (requires Azure app configured).
- Auth: Entra OAuth (device code / auth-code / BYO token) — reuse the existing
  OAuth job flow, no new OAuth code.
