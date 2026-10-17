# Notion integration

Notion pages, databases and blocks via the official Notion MCP server
(`@notionhq/notion-mcp-server`). No OAuth required — an internal integration
token is enough.

| | |
|---|---|
| Category | Productivity |
| Authentication | Integration Token (`ntn_`) |
| Server | `@notionhq/notion-mcp-server` (official) |
| Transport | stdio (`npx -y @notionhq/notion-mcp-server`) |
| Status | not installed |

## Install

Install from the marketplace (attaches a server named `notion`) via
`POST /api/plugins/install` with `source = <resolved ./marketplaces/integrations/notion path>`.

## Credentials

1. Create an internal integration at notion.so/my-integrations.
2. Share the pages/databases you want the agent to reach with that integration.
3. Store the token as secret **`NOTION_TOKEN`** (resolved via `${NOTION_TOKEN}`).

## Verify

- Phase 5 repo check: official Notion server — active.
- Probe: `POST /api/mcp/test` → tools list.
- Execution: `API-post-search` returns the shared pages.

## Notes

The official Notion MCP server exposes tools with the `API-` prefix matching the Notion API naming convention (e.g., `API-post-search`, `API-retrieve-a-page`, `API-create-a-data-source`).
