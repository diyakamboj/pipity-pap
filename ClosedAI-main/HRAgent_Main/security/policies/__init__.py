import importlib
from typing import Final

from security.policies.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)
from security.policies.risk import SecurityRisk
from security.policies.toolshield_helpers import (
    auto_detect_safety_experiences,
    default_safety_experiences,
    detect_active_mcp_tools,
    load_safety_experiences,
    mcp_tools_from_config,
    safety_experiences_for_mcp_config,
)


#: Symbols re-exported from the analyzer subpackages. The analyzers consume
#: ``core.execution.event`` types at module level (e.g. ``analyzer.py`` imports
#: ``ActionEvent``), and ``tools.tool`` imports ``security.policies.risk`` in
#: turn, so importing them eagerly at package load creates an import cycle
#: through ``core.execution.event``. The light modules above stay eager; the
#: analyzers are resolved on first attribute access, by which point the event
#: graph is fully initialized.
_LAZY_SYMBOLS: Final[dict[str, str]] = {
    "SecurityAnalyzerBase": "security.policies.analyzer",
    "LLMSecurityAnalyzer": "security.policies.llm_analyzer",
    "ToolShieldLLMSecurityAnalyzer": "security.policies.toolshield_llm_analyzer",
    "GraySwanAnalyzer": "security.policies.grayswan",
    "PatternSecurityAnalyzer": "security.policies.defense_in_depth",
    "PolicyRailSecurityAnalyzer": "security.policies.defense_in_depth",
    "EnsembleSecurityAnalyzer": "security.policies.ensemble",
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
    "SecurityRisk",
    "SecurityAnalyzerBase",
    "LLMSecurityAnalyzer",
    "ToolShieldLLMSecurityAnalyzer",
    "auto_detect_safety_experiences",
    "default_safety_experiences",
    "detect_active_mcp_tools",
    "load_safety_experiences",
    "mcp_tools_from_config",
    "safety_experiences_for_mcp_config",
    "GraySwanAnalyzer",
    "PatternSecurityAnalyzer",
    "PolicyRailSecurityAnalyzer",
    "EnsembleSecurityAnalyzer",
    "ConfirmationPolicyBase",
    "AlwaysConfirm",
    "NeverConfirm",
    "ConfirmRisky",
]
