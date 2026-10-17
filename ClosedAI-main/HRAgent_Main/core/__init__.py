from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from core.agent import (
    Agent,
    AgentBase,
)
from core.banner import _print_banner
from context import AgentContext, load_memory
from context.condenser import (
    LLMSummarizingCondenser,
)
from core.conversation import (
    BaseConversation,
    Conversation,
    ConversationCallbackType,
    ConversationExecutionStatus,
    LocalConversation,
    RemoteConversation,
)
from core.conversation.conversation_stats import ConversationStats
from core.execution.event import Event, HookExecutionEvent, LLMConvertibleEvent
from core.execution.event.llm_convertible import MessageEvent
from utilities.io import FileStore, LocalFileStore
from models.llm import (
    LLM,
    LLM_PROFILE_SCHEMA_VERSION,
    FallbackStrategy,
    ImageContent,
    LLMProfileStore,
    LLMRegistry,
    LLMStreamChunk,
    Message,
    RedactedThinkingBlock,
    RegistryEvent,
    TextContent,
    ThinkingBlock,
    TokenCallbackType,
    TokenUsage,
)
from runtime.telemetry.logger import get_logger
from mcp_integration import (
    MCPClient,
    MCPToolDefinition,
    MCPToolObservation,
    create_mcp_tools,
)
from plugins import Plugin

# Deferred exports from configuration.settings (and its .metadata submodule).
# configuration.settings.model eagerly imports core.conversation.*, which would
# re-enter core/__init__.py while configuration.settings is still initializing
# when the settings package is the import entry point (e.g. server boot via
# runtime.persistence). Resolved on first access via __getattr__ below, mirroring
# the lazy pattern used in configuration/settings/__init__.py itself.
_SETTINGS_LAZY_MODULE = {
    "ACP_PROVIDERS": "configuration.settings",
    "ACPAgentSettings": "configuration.settings",
    "ACPFileSecretSpec": "configuration.settings",
    "ACPModelOption": "configuration.settings",
    "ACPProviderInfo": "configuration.settings",
    "AgentSettingsBase": "configuration.settings",
    "AgentSettingsConfig": "configuration.settings",
    "CondenserSettings": "configuration.settings",
    "ConversationSettings": "configuration.settings",
    "HRAgentsAgentSettings": "configuration.settings",
    "SettingsChoice": "configuration.settings",
    "SettingsFieldSchema": "configuration.settings",
    "SettingsSchema": "configuration.settings",
    "SettingsSectionSchema": "configuration.settings",
    "VerificationSettings": "configuration.settings",
    "apply_agent_settings_diff": "configuration.settings",
    "build_session_model_meta": "configuration.settings",
    "default_agent_settings": "configuration.settings",
    "detect_acp_provider_by_agent_name": "configuration.settings",
    "export_agent_settings_schema": "configuration.settings",
    "export_settings_schema": "configuration.settings",
    "get_acp_provider": "configuration.settings",
    "validate_agent_settings": "configuration.settings",
    "SettingProminence": "configuration.settings.metadata",
    "SettingsFieldMetadata": "configuration.settings.metadata",
    "SettingsSectionMetadata": "configuration.settings.metadata",
    "field_meta": "configuration.settings.metadata",
}
from skills import (
    load_project_skills,
    load_skills_from_dir,
    load_user_skills,
)
from subagents import (
    agent_definition_to_factory,
    discover_agents,
    load_agents_from_dir,
    load_project_agents,
    load_user_agents,
    register_agent,
)
from tools import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from utilities import page_iterator
from core.workspace import (
    AsyncRemoteWorkspace,
    LocalWorkspace,
    RemoteWorkspace,
    Workspace,
)


try:
    __version__ = version("HRAgent-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments

# Print startup banner
_print_banner(__version__)


__all__ = [
    "LLM",
    "LLM_PROFILE_SCHEMA_VERSION",
    "LLMRegistry",
    "LLMProfileStore",
    "LLMStreamChunk",
    "FallbackStrategy",
    "TokenCallbackType",
    "TokenUsage",
    "ConversationStats",
    "RegistryEvent",
    "Message",
    "TextContent",
    "ImageContent",
    "ThinkingBlock",
    "RedactedThinkingBlock",
    "Tool",
    "ToolDefinition",
    "AgentBase",
    "Agent",
    "Action",
    "Observation",
    "MCPClient",
    "MCPToolDefinition",
    "MCPToolObservation",
    "MessageEvent",
    "HookExecutionEvent",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "BaseConversation",
    "LocalConversation",
    "RemoteConversation",
    "ConversationExecutionStatus",
    "ConversationCallbackType",
    "Event",
    "LLMConvertibleEvent",
    "AgentContext",
    "LLMSummarizingCondenser",
    "CondenserSettings",
    "ConversationSettings",
    "VerificationSettings",
    "ACP_PROVIDERS",
    "ACPAgentSettings",
    "ACPFileSecretSpec",
    "ACPModelOption",
    "ACPProviderInfo",
    "AgentSettingsBase",
    "AgentSettingsConfig",
    "HRAgentsAgentSettings",
    "apply_agent_settings_diff",
    "build_session_model_meta",
    "default_agent_settings",
    "detect_acp_provider_by_agent_name",
    "export_agent_settings_schema",
    "get_acp_provider",
    "validate_agent_settings",
    "SettingsChoice",
    "SettingProminence",
    "SettingsFieldMetadata",
    "SettingsFieldSchema",
    "SettingsSchema",
    "SettingsSectionMetadata",
    "SettingsSectionSchema",
    "export_settings_schema",
    "field_meta",
    "FileStore",
    "LocalFileStore",
    "Plugin",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
    "Workspace",
    "LocalWorkspace",
    "RemoteWorkspace",
    "AsyncRemoteWorkspace",
    "register_agent",
    "load_project_agents",
    "load_user_agents",
    "load_agents_from_dir",
    "discover_agents",
    "agent_definition_to_factory",
    "load_memory",
    "load_project_skills",
    "load_skills_from_dir",
    "load_user_skills",
    "page_iterator",
    "__version__",
]


def __getattr__(name: str) -> Any:
    module = _SETTINGS_LAZY_MODULE.get(name)
    if module is not None:
        from importlib import import_module

        return getattr(import_module(module), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
