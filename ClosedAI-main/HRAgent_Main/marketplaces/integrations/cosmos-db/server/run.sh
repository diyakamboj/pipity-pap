#!/usr/bin/env bash
# Launches the vendored Cosmos DB MCP server (stdio_main.py) using this
# repo's backend venv, so it has azure-cosmos/azure-identity/fastmcp without
# needing its own separate environment.
#
# NOTE: once installed via the plugin marketplace, this script is *copied*
# to ~/.HRAgent/plugins/installed/cosmos-db/server/run.sh (see
# HRAgent_Main/plugins/installed.py) -- it no longer lives next to
# HRAgent_Main/.venv, so its location cannot be used to find the venv the
# way hr_mcp/server.py's sibling-import trick does. COSMOS_MCP_VENV_PYTHON
# lets an installation override the path (e.g. a different checkout);
# the default below matches this specific machine's checkout, same
# hardcoded-with-env-override pattern as HR_MCP_PYTHON in
# chat_interface/app/api/chat/route.ts.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${COSMOS_MCP_VENV_PYTHON:-/Users/anushkaboran/Desktop/ClosedAI/HRAgent_Main/.venv/bin/python}"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "[cosmos-db mcp] backend venv python not found at $VENV_PYTHON -- set COSMOS_MCP_VENV_PYTHON or run 'uv sync' in HRAgent_Main" >&2
  exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT_DIR/stdio_main.py"
