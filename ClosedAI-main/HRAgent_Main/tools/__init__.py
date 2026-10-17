import importlib
from typing import Final

from tools.client_tool import (
    ClientTool,
    ClientToolRegistrationError,
    ClientToolSchemaConflictError,
    ClientToolSpec,
    register_client_tools,
)
from tools.defaults import (
    BROWSER_TOOL_NAME,
    DEFAULT_EXEC_TOOL_NAMES,
    SUB_AGENT_TOOL_NAME,
    default_tool_specs,
)
from tools.registry import (
    is_tool_usable,
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from tools.schema import (
    Action,
    Observation,
)
from tools.spec import Tool
from tools.tool import (
    DeclaredResources,
    ExecutableTool,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


#: Symbols re-exported from the heavy ``tools.builtins`` subpackage. It imports
#: ``skills`` → plugins → core.execution.hooks → core.conversation, which would
#: re-enter ``core.execution.event`` while low-level modules (e.g.
#: ``core.execution.event.llm_convertible`` importing ``tools.schema``) are
#: still mid-initialization. Resolved on first attribute access instead; the
#: builtins only ever load once their surrounding graph is ready.
_LAZY_SYMBOLS: Final[dict[str, str]] = {
    "BUILT_IN_TOOL_CLASSES": "tools.builtins",
    "BUILT_IN_TOOLS": "tools.builtins",
    "FinishTool": "tools.builtins",
    "ThinkTool": "tools.builtins",
}


def __getattr__(name: str):
    module_name = _LAZY_SYMBOLS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "ClientTool",
    "ClientToolRegistrationError",
    "ClientToolSchemaConflictError",
    "ClientToolSpec",
    "register_client_tools",
    "DeclaredResources",
    "Tool",
    "BROWSER_TOOL_NAME",
    "DEFAULT_EXEC_TOOL_NAMES",
    "SUB_AGENT_TOOL_NAME",
    "default_tool_specs",
    "is_tool_usable",
    "ToolDefinition",
    "ToolAnnotations",
    "ToolExecutor",
    "ExecutableTool",
    "Action",
    "Observation",
    "FinishTool",
    "ThinkTool",
    "BUILT_IN_TOOLS",
    "BUILT_IN_TOOL_CLASSES",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
]
