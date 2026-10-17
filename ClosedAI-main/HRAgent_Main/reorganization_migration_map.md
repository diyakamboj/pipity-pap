# Repository Reorganization Migration Map

This file records the structural moves performed as part of the repository reorganization. No implementation files were rewritten; only folders were relocated into responsibility-based package areas.

## Package-root moves

- Current path: `HRAgent-sdk/` -> New path: `packages/agent-core/HRAgent-sdk/`
- Current path: `HRAgent-agent-server/` -> New path: `packages/agent-runtime/HRAgent-agent-server/`
- Current path: `HRAgent-tools/` -> New path: `packages/agent-tools/HRAgent-tools/`

## Responsibility-based moves

- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/agent/` -> New path: `packages/agent-core/agent/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/context/` -> New path: `packages/agent-core/context/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/conversation/` -> New path: `packages/agent-core/conversation/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/conversation/goal/` -> New path: `packages/agent-core/orchestration/goal/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/llm/` -> New path: `packages/agent-core/models/llm/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/mcp/` -> New path: `packages/agent-core/models/mcp/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/security/` -> New path: `packages/agent-core/security/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/skills/` -> New path: `packages/agent-capabilities/skills/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/plugin/` -> New path: `packages/agent-capabilities/plugins/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/subagent/` -> New path: `packages/agent-capabilities/subagents/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/tool/` -> New path: `packages/agent-capabilities/tools/tool/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/utils/` -> New path: `packages/agent-core/utils/`
- Current path: `packages/agent-core/HRAgent-sdk/HRAgent/sdk/settings/` -> New path: `packages/infrastructure/configuration/settings/`
- Current path: `packages/agent-runtime/HRAgent-agent-server/HRAgent/agent_server/` -> New path: `packages/agent-runtime/server/agent_server/`
- Current path: `packages/agent-runtime/HRAgent-agent-server/HRAgent/agent_server/persistence/` -> New path: `packages/agent-runtime/persistence/`
- Current path: `packages/agent-runtime/HRAgent-agent-server/HRAgent/agent_server/telemetry/` -> New path: `packages/agent-runtime/telemetry/`
- Current path: `packages/agent-runtime/HRAgent-agent-server/HRAgent/agent_server/openai/` -> New path: `packages/agent-runtime/integrations/openai/`
- Current path: `packages/agent-runtime/HRAgent-agent-server/HRAgent/agent_server/vscode_extensions/` -> New path: `packages/agent-runtime/integrations/vscode_extensions/`
- Current path: `packages/agent-tools/HRAgent-tools/HRAgent/tools/` -> New path: `packages/agent-capabilities/tools/`

## Compatibility note

Old package paths remain available through compatibility links so the repository continues to resolve the historical package layout while the implementation remains in the new responsibility-based locations.
