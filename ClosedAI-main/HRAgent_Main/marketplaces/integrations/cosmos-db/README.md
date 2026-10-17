# Cosmos DB

Azure Cosmos DB integration — query, schema discovery, and document
exploration via the official Azure Cosmos DB team's MCP server sample.

## Source

Vendored from [`AzureCosmosDB/azure-cosmos-mcp-server-samples`](https://github.com/AzureCosmosDB/azure-cosmos-mcp-server-samples)
(`python/cosmos_server.py`, MIT License, Copyright (c) Microsoft Corporation
— see `server/LICENSE-upstream`). This is the official Azure Cosmos DB
product team's sample MCP server, not a third-party implementation.

Microsoft also publishes a more broadly-scoped official server,
[`@azure/mcp`](https://github.com/microsoft/mcp) (covers many Azure
services, Cosmos DB included). It was evaluated first but only supports
Azure Entra ID / service-principal authentication, not the account-key
credentials already provisioned for this project's Cosmos account — so
this repo uses the Cosmos-DB-team sample instead, which supports key-based
auth directly.

## What was changed vs. upstream

Two small, disclosed adaptations — no tool behavior was changed:

1. **`server/cosmos_server.py`** — the vendored copy, with one line removed:
   `FastMCP(..., capabilities={...})` no longer accepts a `capabilities=`
   kwarg in the `fastmcp>=2.14` version this repo pins (this repo's
   `pyproject.toml` requires `fastmcp>=2.14.0,<3.0`); tools/logging are
   enabled by default in current fastmcp regardless, so the kwarg is simply
   dropped.
2. **`server/stdio_main.py`** — a new, small entrypoint. Upstream's
   `cosmos_server.main()` hardcodes `mcp.run(transport="streamable-http",
   host="127.0.0.1", port=8080)`, i.e. a long-running HTTP sidecar you'd
   have to manage separately. Every other integration in this marketplace
   (`azure-ai-search`, `postgres`, ...) is instead spawned fresh per
   conversation over stdio, which needs no separately-managed process and
   scopes credentials to a single subprocess's environment. `stdio_main.py`
   imports the *same* `cosmos_server.mcp` FastMCP instance and the *same*
   tool functions unchanged, and just calls `.run(transport="stdio")`
   instead.

## Tools

- `query_cosmos` — execute a Cosmos DB SQL query
- `list_collections` — enumerate containers in the database
- `describe_container` — container schema (approximate, sampled)
- `find_implied_links` — detect cross-container relationships
- `get_sample_documents` — retrieve sample records
- `count_documents` — document count for a container
- `get_partition_key_info` — partition key configuration
- `get_indexing_policy` — indexing policy
- `list_distinct_values` — unique values for a field

## Setup

Requires an Azure Cosmos DB account URI + access key (or set
`COSMOS_USE_MANAGED_IDENTITY=true` and rely on `DefaultAzureCredential`
instead of a key — supported by the underlying `CosmosDBConnection` class,
not currently exposed as a marketplace field).

| Field | Example |
|---|---|
| `COSMOS_URI` | `https://<account>.documents.azure.com:443/` |
| `COSMOS_KEY` | account access key |
| `COSMOS_DATABASE` | `closedai-db` |
| `COSMOS_CONTAINER` | `employees` (default container; `query_cosmos` and friends can target other containers by name too) |

For this project, these map to the repo-root `.env`'s existing
`COSMOS_ENDPOINT` / `COSMOS_KEY` / `COSMOS_DATABASE_NAME` /
`COSMOS_CONTAINER_NAME` (aliased as `COSMOS_URI` / `COSMOS_KEY` /
`COSMOS_DATABASE` / `COSMOS_CONTAINER` since the vendored script reads
those exact names — see the comment above them in `.env`).

## Running the server standalone (outside the agent)

```bash
cd HRAgent_Main
COSMOS_URI=... COSMOS_KEY=... COSMOS_DATABASE=... COSMOS_CONTAINER=... \
  .venv/bin/python marketplaces/integrations/cosmos-db/server/stdio_main.py
```

Speaks MCP over stdio (JSON-RPC on stdin/stdout) — pipe an `initialize`
request to smoke-test it, or install through the marketplace to get it
wired into a live conversation with the `activate_integration` tool.

## Known limitation

`server/run.sh` locates the backend's `HRAgent_Main/.venv` via a hardcoded
absolute path with an env-var override (`COSMOS_MCP_VENV_PYTHON`), the same
pattern `HR_MCP_PYTHON` uses in `chat_interface/app/api/chat/route.ts`. This
is necessary because once installed, the plugin is *copied* to
`~/.HRAgent/plugins/installed/cosmos-db/` (see `HRAgent_Main/plugins/installed.py`)
and can no longer find the venv via a path relative to its own vendored
location. If this repo is checked out somewhere other than
`/Users/anushkaboran/Desktop/ClosedAI`, set `COSMOS_MCP_VENV_PYTHON` to the
correct `.venv/bin/python` path.
