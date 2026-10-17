"""Import smoke test for the flattened HRAgent project."""
import importlib
import sys
import traceback

# (module, note)
MODULES = [
    # Top-level packages
    ("core", "core package"),
    ("context", "context package"),
    ("models", "models package"),
    ("tools", "tools package"),
    ("plugins", "plugins package"),
    ("skills", "skills package"),
    ("subagents", "subagents package"),
    ("mcp_integration", "first-party MCP integration package"),
    ("mcp", "third-party MCP SDK (unshadowed)"),
    ("mcp.client", "third-party MCP SDK client"),
    ("mcp.types", "third-party MCP SDK types"),
    ("security", "security package"),
    ("utilities", "utilities package"),
    ("configuration", "configuration package"),
    ("runtime", "runtime package"),
    ("memory.memory", "memory.memory"),
    # Shims
    ("core.workspace", "workspace shim"),
    ("core.critic", "critic shim"),
    ("utilities.git", "git shim"),
    ("plugins.installation", "installation shim"),
    ("plugins.marketplace", "marketplace shim"),
    ("runtime.server.bash_service", "bash_service shim"),
    # Key entry points / routers
    ("tools.registry", "tool registry"),
    ("tools.defaults", "tool defaults"),
    ("runtime.server.api", "api app"),
    ("runtime.server.server_details_router", "server details router"),
    ("runtime.server.skills_router", "skills router"),
    ("runtime.server.plugins_router", "plugins router"),
    ("runtime.server.skills_service", "skills service"),
    ("runtime.server.plugins_service", "plugins service"),
    ("runtime.server.mcp_router", "mcp router"),
    ("runtime.server.tool_router", "tool router"),
    ("runtime.server.event_router", "event router"),
    ("runtime.server.event_service", "event service"),
    ("runtime.server.conversation_router", "conversation router"),
    ("runtime.server.conversation_service", "conversation service"),
    ("runtime.server.init_router", "init router"),
    ("runtime.server.dependencies", "dependencies"),
    ("runtime.server.sockets", "sockets"),
    ("runtime.server.models", "server models"),
    ("runtime.server.tool_preload_service", "tool preload service"),
    ("models.llm", "llm package"),
    ("models.llm.llm", "llm impl"),
    ("core.agent", "agent package"),
    ("core.agent.agent", "agent impl"),
    ("core.agent.base", "agent base"),
    ("core.agent.acp_agent", "acp agent"),
    ("core.conversation", "conversation"),
    ("core.orchestration.goal", "goal"),
    ("core.execution.event", "event"),
    ("core.execution.hooks", "hooks"),
    ("context.agent_context", "agent context"),
    ("context.condenser", "condenser"),
    ("context.prompts", "prompts"),
    ("context.prompts.presets", "prompt presets"),
    ("configuration.settings", "settings"),
    ("configuration.settings.model", "settings model"),
    ("configuration.profiles", "profiles"),
    ("configuration.profiles.agent_profile", "agent profile"),
    ("tools.preset", "preset package"),
    ("tools.preset.default", "preset default"),
    ("tools.preset.gemini", "preset gemini"),
    ("tools.preset.gpt5", "preset gpt5"),
    ("tools.preset.planning", "preset planning"),
    ("tools.schema", "tool schema"),
    ("tools.tool", "tool base"),
    ("subagents.registry", "subagent registry"),
    ("plugins.fetch", "plugins fetch"),
    ("skills.fetch", "skills fetch"),
    ("mcp_integration.config", "mcp integration config"),
    ("mcp_integration.client", "mcp integration client"),
    ("mcp_integration.tool", "mcp integration tool"),
    ("mcp_integration.utils", "mcp integration utils"),
    ("runtime.integrations.openai.service", "openai service"),
    ("runtime.integrations.vscode_extensions", "vscode extensions"),
]

ok, fail = [], []
for mod, note in MODULES:
    try:
        importlib.import_module(mod)
        ok.append(mod)
    except Exception:
        fail.append((mod, note))
        print(f"FAIL: {mod} ({note})")
        traceback.print_exc()

print("\n==== SMOKE RESULT ====")
print(f"OK:   {len(ok)}")
print(f"FAIL: {len(fail)}")
for mod, note in fail:
    print(f"  - {mod} ({note})")
sys.exit(1 if fail else 0)