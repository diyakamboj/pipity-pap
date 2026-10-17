#!/usr/bin/env bash
# Launches office-oxide-mcp (see README.md for what/why). Unlike the npx/uvx
# integrations elsewhere in this marketplace, office-oxide-mcp is not
# published to any package registry (npm/PyPI/crates.io) -- it must be built
# once via `cargo install --git https://github.com/Aimino-Tech/opendocswork-mcp`,
# which installs the binary to ~/.cargo/bin/office-oxide-mcp. This script
# looks there by default; OFFICE_OXIDE_MCP_BIN overrides it (same
# hardcoded-with-env-override pattern as HR_MCP_PYTHON / COSMOS_MCP_VENV_PYTHON
# elsewhere in this repo, for the same reason: this plugin gets *copied* to
# ~/.HRAgent/plugins/installed/document-editor/ on install, so it can't find
# a machine-specific binary via a path relative to its own location).
set -euo pipefail
BIN="${OFFICE_OXIDE_MCP_BIN:-$HOME/.cargo/bin/office-oxide-mcp}"

if [ ! -x "$BIN" ]; then
  echo "[document-editor mcp] office-oxide-mcp binary not found at $BIN -- run: cargo install --git https://github.com/Aimino-Tech/opendocswork-mcp" >&2
  exit 1
fi

exec "$BIN"
