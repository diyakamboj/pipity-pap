"""Gurt Logistics Engine Package.

Provides precision schedule calculation, conflict detection, buffer math,
and role-specific participant briefings.
"""

from gurt.logistics.schedule_engine import (
    time_to_minutes,
    minutes_to_time,
    calculate_duration_minutes,
    build_run_of_show,
    calculate_critical_path,
    generate_operational_tasks
)
from gurt.logistics.conflict_engine import (
    intervals_overlap,
    is_shared_or_nonexclusive_space,
    detect_schedule_conflicts,
    analyze_schedule_impact,
    propose_conflict_resolutions
)
from gurt.logistics.briefing_engine import (
    compute_source_fingerprint,
    assert_no_sensitive_leakage,
    project_speaker_allowed_fields,
    project_vendor_allowed_fields,
    project_volunteer_allowed_fields,
    generate_speaker_briefing,
    generate_vendor_briefing,
    generate_volunteer_briefing,
    evaluate_briefing_readiness,
    preview_briefing
)

__all__ = [
    "time_to_minutes",
    "minutes_to_time",
    "calculate_duration_minutes",
    "build_run_of_show",
    "calculate_critical_path",
    "generate_operational_tasks",
    "intervals_overlap",
    "is_shared_or_nonexclusive_space",
    "detect_schedule_conflicts",
    "analyze_schedule_impact",
    "propose_conflict_resolutions",
    "compute_source_fingerprint",
    "assert_no_sensitive_leakage",
    "project_speaker_allowed_fields",
    "project_vendor_allowed_fields",
    "project_volunteer_allowed_fields",
    "generate_speaker_briefing",
    "generate_vendor_briefing",
    "generate_volunteer_briefing",
    "evaluate_briefing_readiness",
    "preview_briefing"
]
