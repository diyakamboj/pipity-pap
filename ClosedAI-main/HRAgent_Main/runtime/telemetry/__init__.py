"""Sanitized product-analytics telemetry for the agent server.

This is **product analytics**, and is distinct from two other things in this
repository that are easy to confuse it with:

* **LLM completion logging** (``LLM.log_completions``) writes full prompts and
  responses to disk for debugging. It is high-fidelity and privacy-sensitive by
  design, and nothing it produces is ever forwarded here.
* **Laminar / OpenTelemetry tracing**
  (``runtime.telemetry.observability``) produces distributed traces for latency and
  span analysis. Separate pipeline, separate destination.

What this package emits is a small, versioned, allowlisted set of lifecycle and
failure events whose properties are constrained scalars — never prompts,
messages, paths, secrets, request/response bodies, or tracebacks.

``posthog_exporter`` is deliberately **not** imported here: importing this
package must not pull in the optional vendor dependency.

All re-exported symbols are resolved lazily via ``__getattr__``. The heavy
submodules pull in first-party import graphs — ``factory`` imports
``utilities``, ``service`` imports ``runtime.server.config``, and ``subscriber``
imports ``core.*``/``models.llm.*``. Low-level modules (``utilities.command``,
``models.llm.auth.credentials``, …) import ``runtime.telemetry.logger`` for
``get_logger``; importing that submodule triggers this ``__init__``, which must
not drag the first-party graph back in while those modules are mid-import.
"""

import importlib
from typing import Final


#: Mapping of public re-exports to the submodule that defines them. Resolved on
#: first attribute access so that importing this package (or any
#: ``runtime.telemetry.*`` submodule, which runs this ``__init__``) stays
#: lightweight and outside the first-party import graph. Submodule imports such
#: as ``from runtime.telemetry import models`` fall back to the normal import
#: machinery when ``__getattr__`` raises.
_LAZY_SYMBOLS: Final[dict[str, str]] = {
    # runtime.telemetry.factory
    "DISTINCT_ID_HEADER": "runtime.telemetry.factory",
    "DiagnosticEventFactory": "runtime.telemetry.factory",
    "build_runtime_properties": "runtime.telemetry.factory",
    "distinct_id_from_header": "runtime.telemetry.factory",
    # runtime.telemetry.models
    "TELEMETRY_SCHEMA_VERSION": "runtime.telemetry.models",
    "DiagnosticEvent": "runtime.telemetry.models",
    "RuntimeProperties": "runtime.telemetry.models",
    # runtime.telemetry.policy
    "TelemetryConsent": "runtime.telemetry.policy",
    "TelemetryDecision": "runtime.telemetry.policy",
    "kill_switch_engaged": "runtime.telemetry.policy",
    "read_consent": "runtime.telemetry.policy",
    "resolve": "runtime.telemetry.policy",
    # runtime.telemetry.service
    "build_telemetry_sink": "runtime.telemetry.service",
    "emit_server_started": "runtime.telemetry.service",
    "emit_server_stopped": "runtime.telemetry.service",
    "get_event_factory": "runtime.telemetry.service",
    "get_telemetry_sink": "runtime.telemetry.service",
    "notify_misc_settings_changed": "runtime.telemetry.service",
    "reset_telemetry_sink": "runtime.telemetry.service",
    "shutdown_telemetry_sink": "runtime.telemetry.service",
    # runtime.telemetry.sink
    "BufferedTelemetrySink": "runtime.telemetry.sink",
    "NoOpTelemetrySink": "runtime.telemetry.sink",
    "TelemetryExporter": "runtime.telemetry.sink",
    "TelemetrySink": "runtime.telemetry.sink",
    # runtime.telemetry.subscriber
    "ConversationTelemetryContext": "runtime.telemetry.subscriber",
    "TelemetrySubscriber": "runtime.telemetry.subscriber",
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
    "TELEMETRY_SCHEMA_VERSION",
    "BufferedTelemetrySink",
    "ConversationTelemetryContext",
    "DiagnosticEvent",
    "DISTINCT_ID_HEADER",
    "DiagnosticEventFactory",
    "NoOpTelemetrySink",
    "RuntimeProperties",
    "TelemetryConsent",
    "TelemetryDecision",
    "TelemetryExporter",
    "read_consent",
    "TelemetrySink",
    "TelemetrySubscriber",
    "build_runtime_properties",
    "distinct_id_from_header",
    "build_telemetry_sink",
    "emit_server_started",
    "emit_server_stopped",
    "get_event_factory",
    "get_telemetry_sink",
    "kill_switch_engaged",
    "notify_misc_settings_changed",
    "reset_telemetry_sink",
    "resolve",
    "shutdown_telemetry_sink",
]
