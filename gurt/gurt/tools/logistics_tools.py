"""Gurt Logistics Tools.

Exposes conflict detection, precision run-of-show synthesis, and role-specific
briefing drafting to the agent orchestrator and REST API.
"""

from __future__ import annotations

from typing import Any
from gurt.db import (
    save_briefing,
    get_briefings,
    get_briefing_by_id,
    mark_briefing_status,
    log_audit_event
)
from gurt.logistics.schedule_engine import (
    build_run_of_show,
    generate_operational_tasks
)
from gurt.logistics.conflict_engine import (
    detect_schedule_conflicts,
    analyze_schedule_impact,
    propose_conflict_resolutions,
    apply_conflict_resolution
)
from gurt.logistics.briefing_engine import (
    preview_briefing,
    generate_speaker_briefing,
    generate_vendor_briefing,
    generate_volunteer_briefing
)


def tool_detect_schedule_conflicts(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Check for room overlaps, turnover buffer insufficiencies, and vendor delivery window readiness."""
    return detect_schedule_conflicts(event_id)


def tool_preview_schedule_change(
    session_id: str,
    proposed_changes: dict[str, Any],
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Preview downstream impact and conflict risk before modifying a schedule session."""
    return analyze_schedule_impact(session_id, proposed_changes, event_id=event_id)


def tool_generate_role_briefing(
    role: str = "speaker",
    recipient_id: str = "",
    event_id: str = "evt-dubhacks-2026",
    save_draft: bool = True
) -> dict[str, Any]:
    """Generate a permission-scoped briefing draft for Speaker, Vendor, or Volunteer with positive projection."""
    briefing = preview_briefing(event_id=event_id, role=role, recipient_id=recipient_id)
    if save_draft:
        saved = save_briefing(
            event_id=event_id,
            recipient_role=briefing["recipient_role"],
            recipient_id=briefing["recipient_id"],
            recipient_name=briefing["recipient_name"],
            content_dict=briefing,
            source_fingerprint=briefing["fingerprint"],
            status="ready" if briefing["is_ready"] else "draft"
        )
        briefing["briefing_id"] = saved["id"]
        log_audit_event(
            event_id=event_id,
            actor_id="gurt_agent",
            action="briefing_generated",
            target_type="briefing",
            target_id=saved["id"],
            details={"role": role, "recipient": briefing["recipient_name"]}
        )
    return briefing


def tool_get_role_briefings(event_id: str = "evt-dubhacks-2026", role: str | None = None) -> list[dict[str, Any]]:
    """Retrieve saved role briefings for an event."""
    return get_briefings(event_id=event_id, recipient_role=role)


def tool_build_precision_run_of_show(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Generate precision chronological timeline with gap warnings and confirmation states."""
    return build_run_of_show(event_id=event_id)


def tool_propose_conflict_resolutions(
    conflict_id: str | None = None,
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Generate explainable, non-hallucinated schedule resolution proposals for active conflicts."""
    return propose_conflict_resolutions(conflict_id=conflict_id, event_id=event_id)


def tool_apply_conflict_resolution(
    event_id: str = "evt-dubhacks-2026",
    session_id: str = "",
    proposed_changes: dict[str, Any] | None = None,
    expected_fingerprint: str | None = None,
    conflict_id: str | None = None
) -> dict[str, Any]:
    """Apply an organizer-approved schedule resolution to SQLite with strict validation, stale checks, and recalculation."""
    return apply_conflict_resolution(
        event_id=event_id,
        session_id=session_id,
        proposed_changes=proposed_changes or {},
        expected_fingerprint=expected_fingerprint,
        conflict_id=conflict_id
    )
