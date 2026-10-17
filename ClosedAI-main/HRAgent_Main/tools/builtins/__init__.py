"""Implementing essential tools that doesn't interact with the environment.

These are built in and are *required* for the agent to work.

For tools that require interacting with the environment, add them to `HRAgent-tools`.
"""

from tools.builtins.activate_integration import (
    ActivateIntegrationAction,
    ActivateIntegrationExecutor,
    ActivateIntegrationObservation,
    ActivateIntegrationTool,
)
from tools.builtins.finish import (
    FinishAction,
    FinishExecutor,
    FinishObservation,
    FinishTool,
)
from tools.builtins.invoke_skill import (
    InvokeSkillAction,
    InvokeSkillExecutor,
    InvokeSkillObservation,
    InvokeSkillTool,
)
from tools.builtins.switch_llm import (
    SwitchLLMAction,
    SwitchLLMExecutor,
    SwitchLLMObservation,
    SwitchLLMTool,
)
from tools.builtins.think import (
    ThinkAction,
    ThinkExecutor,
    ThinkObservation,
    ThinkTool,
)
from tools.builtins.vision_inspect import (
    VisionInspectAction,
    VisionInspectExecutor,
    VisionInspectObservation,
    VisionInspectTool,
)


# Tools attached to every agent by default. `InvokeSkillTool` is deliberately
# *not* here: it's auto-attached by `Agent._initialize` only when an
# AgentSkills-format skill is loaded (see BUILT_IN_TOOL_CLASSES below).
BUILT_IN_TOOLS = [FinishTool, ThinkTool]

# Map of built-in tool class names to their classes. Includes optional built-ins
# so they can be resolved by name from `include_default_tools` and the
# conditional wiring in `Agent._initialize`.
BUILT_IN_TOOL_CLASSES = {
    **{tool.__name__: tool for tool in BUILT_IN_TOOLS},
    InvokeSkillTool.__name__: InvokeSkillTool,
    SwitchLLMTool.__name__: SwitchLLMTool,
    VisionInspectTool.__name__: VisionInspectTool,
    ActivateIntegrationTool.__name__: ActivateIntegrationTool,
}

__all__ = [
    "BUILT_IN_TOOLS",
    "BUILT_IN_TOOL_CLASSES",
    "ActivateIntegrationTool",
    "ActivateIntegrationAction",
    "ActivateIntegrationObservation",
    "ActivateIntegrationExecutor",
    "FinishTool",
    "FinishAction",
    "FinishObservation",
    "FinishExecutor",
    "InvokeSkillTool",
    "InvokeSkillAction",
    "InvokeSkillObservation",
    "InvokeSkillExecutor",
    "SwitchLLMTool",
    "SwitchLLMAction",
    "SwitchLLMObservation",
    "SwitchLLMExecutor",
    "ThinkTool",
    "ThinkAction",
    "ThinkObservation",
    "ThinkExecutor",
    "VisionInspectTool",
    "VisionInspectAction",
    "VisionInspectObservation",
    "VisionInspectExecutor",
]
