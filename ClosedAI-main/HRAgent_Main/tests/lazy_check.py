"""Verify the lazy __getattr__ re-exports resolve to the right objects at runtime.

The smoke test imports modules via importlib.import_module, which never touches a
package's __getattr__. These `from pkg import X` / `pkg.X` forms do, so they
exercise the deferred-load paths exactly as real callers will.
"""
import sys
import traceback

# (how, what, expected_module) — resolve and sanity-check
CHECKS = [
    ("from runtime.telemetry import TELEMETRY_SCHEMA_VERSION", None),
    ("from runtime.telemetry import DiagnosticEventFactory", None),
    ("from runtime.telemetry import build_runtime_properties", None),
    ("from runtime.telemetry import get_telemetry_sink", None),
    ("from runtime.telemetry import build_telemetry_sink", None),
    ("from runtime.telemetry import emit_server_started", None),
    ("from runtime.telemetry import notify_misc_settings_changed", None),
    ("from runtime.telemetry import TelemetrySubscriber", None),
    ("from runtime.telemetry import ConversationTelemetryContext", None),
    ("from runtime.telemetry import BufferedTelemetrySink", None),
    ("from runtime.telemetry import NoOpTelemetrySink", None),
    ("from runtime.telemetry import TelemetryDecision", None),
    ("from runtime.telemetry import models as m", "m.DiagnosticEvent"),
    ("from models.llm import RouterLLM", "RouterLLM.__name__"),
    ("from tools import BUILT_IN_TOOLS", "len(BUILT_IN_TOOLS)"),
    ("from tools import BUILT_IN_TOOL_CLASSES", None),
    ("from tools import FinishTool", "FinishTool.__name__"),
    ("from tools import ThinkTool", "ThinkTool.__name__"),
    ("from security.policies import SecurityAnalyzerBase", None),
    ("from security.policies import LLMSecurityAnalyzer", None),
    ("from security.policies import ToolShieldLLMSecurityAnalyzer", None),
    ("from security.policies import GraySwanAnalyzer", None),
    ("from security.policies import PatternSecurityAnalyzer", None),
    ("from security.policies import PolicyRailSecurityAnalyzer", None),
    ("from security.policies import EnsembleSecurityAnalyzer", None),
    ("from plugins import Plugin", "Plugin.__name__"),
    ("from plugins import load_plugins", None),
    ("from plugins import install_plugin", None),
    ("from plugins import load_available_plugins", None),
    ("from plugins import load_user_plugins", None),
    ("from plugins import list_installed_plugins", None),
    ("from plugins.marketplace import MarketplaceRegistry", None),
    ("from plugins.marketplace import MarketplaceNotFoundError", None),
    ("from plugins.marketplace import PluginResolutionError", None),
]

ok, fail = 0, 0
for stmt, probe in CHECKS:
    try:
        ns: dict = {}
        exec(stmt, ns)  # noqa: S102 — deliberate: exercising import forms
        if probe:
            assert eval(probe, ns), f"{stmt}: {probe} falsy"
        ok += 1
    except Exception:
        fail += 1
        print(f"FAIL: {stmt}")
        traceback.print_exc()

# Attribute-style access on the lazy packages too.
for pkg, attr in [
    ("runtime.telemetry", "get_telemetry_sink"),
    ("runtime.telemetry", "TelemetrySubscriber"),
    ("models.llm", "RouterLLM"),
    ("tools", "BUILT_IN_TOOLS"),
    ("tools", "FinishTool"),
    ("security.policies", "SecurityAnalyzerBase"),
    ("plugins", "Plugin"),
    ("plugins", "load_plugins"),
]:
    try:
        mod = __import__(pkg, fromlist=[attr])
        getattr(mod, attr)
        ok += 1
    except Exception:
        fail += 1
        print(f"FAIL: {pkg}.{attr} (attribute access)")
        traceback.print_exc()

print(f"\n==== LAZY CHECK ====\nOK: {ok}  FAIL: {fail}")
sys.exit(1 if fail else 0)