#!/usr/bin/env python3
"""Stdio entrypoint for the vendored Azure Cosmos DB MCP server.

The upstream sample (AzureCosmosDB/azure-cosmos-mcp-server-samples, see
cosmos_server.py + LICENSE-upstream) only ships a streamable-http entrypoint
(cosmos_server.main() hardcodes mcp.run(transport="streamable-http", ...)).
Every other marketplace integration in this repo is spawned per-conversation
over stdio (see ../azure-ai-search/.mcp.json, ../postgres/.mcp.json), which
is simpler to operate -- no separately-managed long-running sidecar process,
and credentials are scoped to a single subprocess's environment instead of a
shared server.

This file changes nothing about the upstream tool implementations
(query_cosmos, list_collections, describe_container, etc.) or how they talk
to Cosmos DB -- it only swaps the transport the same FastMCP instance is
served over, so the plugin fits the stdio/npx-style pattern the rest of the
marketplace uses.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cosmos_server  # noqa: E402


def main() -> None:
    uri = os.environ.get("COSMOS_URI")
    key = os.environ.get("COSMOS_KEY")
    database = os.environ.get("COSMOS_DATABASE")
    container = os.environ.get("COSMOS_CONTAINER")
    use_managed_identity = os.environ.get("COSMOS_USE_MANAGED_IDENTITY", "").lower() in (
        "1",
        "true",
        "yes",
    )

    missing = [
        name
        for name, value in (
            ("COSMOS_URI", uri),
            ("COSMOS_DATABASE", database),
            ("COSMOS_CONTAINER", container),
        )
        if not value
    ]
    if not use_managed_identity and not key:
        missing.append("COSMOS_KEY (or set COSMOS_USE_MANAGED_IDENTITY=true)")
    if missing:
        print(f"[cosmos-db mcp] missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    cosmos_server.cosmos_connection = cosmos_server.CosmosDBConnection(
        uri=uri,
        key=key,
        database=database,
        container=container,
        use_managed_identity=use_managed_identity,
    )
    # Fail fast (and visibly, in the subprocess's stderr) if the credentials
    # or container name are wrong, rather than surfacing a confusing error
    # on the agent's first tool call.
    cosmos_server.cosmos_connection.get_container_client()

    cosmos_server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
