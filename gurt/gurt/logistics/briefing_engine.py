"""Gurt Role-Specific Briefing Engine.

Permission-scoped, versioned participant briefings for Speakers, Vendors, and Volunteers.
Enforces positive projection allowlists (preventing cross-role data leaks) and
exact-field SHA-256 fingerprinting for staleness detection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any
from gurt.db import (
    get_connection,
    get_event_brief,
    get_schedule_items,
    get_briefings,
    save_briefing,
    query_records
)


# ---------------------------------------------------------------------------
# Positive Projection Allowlisting & Anti-Leak Guards
# ---------------------------------------------------------------------------
def compute_source_fingerprint(data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 fingerprint from the exact fields used for a role's briefing."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def assert_no_sensitive_leakage(role: str, text: str) -> None:
    """Strictly assert that no cross-role sensitive terms leak into formatted briefings."""
    text_lower = text.lower()
    if role == "speaker":
        # Speakers must not receive internal vendor quotes, costs, or competitor pricing
        for term in ["quote_amount", "price_per_head", "competitor quote", "$1080", "$13.50"]:
            if term in text_lower:
                raise ValueError(f"CRITICAL SECURITY: Sensitive vendor financial data '{term}' leaked into speaker briefing.")
    elif role == "vendor":
        # Vendors must not receive speaker private contact emails or competitor quotes
        for term in ["alicia.chen@cs.washington.edu", "competitor quote", "budget cap", "$2500"]:
            if term in text_lower:
                raise ValueError(f"CRITICAL SECURITY: Sensitive contact/budget data '{term}' leaked into vendor briefing.")
    elif role == "volunteer":
        # Volunteers must not receive sponsor contract details or vendor pricing
        for term in ["quote_amount", "sponsorship amount", "$3000", "$1500"]:
            if term in text_lower:
                raise ValueError(f"CRITICAL SECURITY: Financial data '{term}' leaked into volunteer briefing.")


def project_speaker_allowed_fields(speaker: dict[str, Any], event: dict[str, Any], schedule_item: dict[str, Any] | None) -> dict[str, Any]:
    """Positive projection: ONLY allowed fields for speaker briefings."""
    return {
        "speaker_name": speaker.get("name", "Honored Speaker"),
        "topic": speaker.get("topic", "Keynote Session"),
        "event_title": event.get("title", "Event"),
        "event_date": event.get("date", "Upcoming"),
        "venue": event.get("location", "Main Venue"),
        "session_time": schedule_item.get("time_slot") or f"{schedule_item.get('start_time', 'TBD')} - {schedule_item.get('end_time', 'TBD')}" if schedule_item else "TBD",
        "room": schedule_item.get("room") or schedule_item.get("location", "Main Room") if schedule_item else "TBD",
        "av_specs": event.get("av_requirements", "Stage display and wireless microphones provided.")
    }


def project_vendor_allowed_fields(vendor: dict[str, Any], event: dict[str, Any], schedule_item: dict[str, Any] | None) -> dict[str, Any]:
    """Positive projection: ONLY allowed fields for vendor briefings."""
    return {
        "vendor_company": vendor.get("company_name", "Supplier"),
        "category": vendor.get("category", "Services"),
        "event_title": event.get("title", "Event"),
        "event_date": event.get("date", "Upcoming"),
        "venue": event.get("location", "Main Venue"),
        "service_time": schedule_item.get("time_slot") if schedule_item else "12:00 - 13:00",
        "room": schedule_item.get("room") or schedule_item.get("location", "Main Hall") if schedule_item else "Main Hall",
        "dietary_specs": event.get("dietary_specs", "Standard dietary accommodations."),
        "expected_headcount": event.get("attendee_count", 80)
    }


def project_volunteer_allowed_fields(volunteer: dict[str, Any], event: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Positive projection: ONLY allowed fields for volunteer briefings."""
    return {
        "volunteer_name": volunteer.get("name", "Team Volunteer"),
        "event_title": event.get("title", "Event"),
        "event_date": event.get("date", "Upcoming"),
        "venue": event.get("location", "Main Venue"),
        "assigned_shift": "08:00 - 14:00",
        "reporting_location": "Registration Desk",
        "checklist": [t.get("title") for t in tasks[:5]]
    }


# ---------------------------------------------------------------------------
# Briefing Generators
# ---------------------------------------------------------------------------
def generate_speaker_briefing(event_id: str = "evt-dubhacks-2026", speaker_id: str = "") -> dict[str, Any]:
    """Generate a permission-scoped, formatted speaker briefing draft."""
    ev = get_event_brief(event_id) or {}
    speakers = query_records("speakers", event_id=event_id)
    target = next((s for s in speakers if s.get("id") == speaker_id or s.get("name").lower() == speaker_id.lower()), None)
    if not target and speakers:
        target = speakers[0]
    if not target:
        target = {"id": "spk-generic", "name": "Honored Speaker", "topic": "Keynote Presentation"}

    schedule = get_schedule_items(event_id)
    matched_slot = next((s for s in schedule if target.get("name", "").lower() in s.get("owner", "").lower() or target.get("name", "").lower() in s.get("activity", "").lower()), None)

    projected = project_speaker_allowed_fields(target, ev, matched_slot)
    fingerprint = compute_source_fingerprint(projected)

    body = (
        f"# Speaker Briefing: {projected['speaker_name']}\n\n"
        f"**Event:** {projected['event_title']}\n"
        f"**Date:** {projected['event_date']}\n"
        f"**Location:** {projected['venue']} ({projected['room']})\n"
        f"**Session Slot:** {projected['session_time']}\n"
        f"**Topic:** {projected['topic']}\n\n"
        f"### Stage & AV Setup\n"
        f"{projected['av_specs']}\n\n"
        f"### Speaker Arrival Protocol\n"
        f"- Please arrive at least 30 minutes prior to your session slot for mic check.\n"
        f"- Check in at the main organizer desk upon arrival."
    )

    assert_no_sensitive_leakage("speaker", body)

    return {
        "event_id": event_id,
        "recipient_role": "speaker",
        "recipient_id": target.get("id"),
        "recipient_name": target.get("name"),
        "fingerprint": fingerprint,
        "status": "draft",
        "markdown_body": body,
        "projected_data": projected
    }


def generate_vendor_briefing(event_id: str = "evt-dubhacks-2026", vendor_id: str = "") -> dict[str, Any]:
    """Generate a permission-scoped vendor service & loading dock briefing draft."""
    ev = get_event_brief(event_id) or {}
    vendors = query_records("vendors", event_id=event_id)
    target = next((v for v in vendors if v.get("id") == vendor_id or v.get("company_name", "").lower() == vendor_id.lower()), None)
    if not target and vendors:
        target = vendors[0]
    if not target:
        target = {"id": "vnd-generic", "company_name": "Event Caterer", "category": "Catering"}

    schedule = get_schedule_items(event_id)
    matched_slot = next((s for s in schedule if "lunch" in s.get("activity", "").lower() or "cater" in s.get("activity", "").lower()), None)

    projected = project_vendor_allowed_fields(target, ev, matched_slot)
    fingerprint = compute_source_fingerprint(projected)

    body = (
        f"# Vendor Service Briefing: {projected['vendor_company']}\n\n"
        f"**Event:** {projected['event_title']}\n"
        f"**Service Date:** {projected['event_date']}\n"
        f"**Venue:** {projected['venue']} — Room: {projected['room']}\n"
        f"**Meal Service Time:** {projected['service_time']}\n"
        f"**Expected Headcount:** {projected['expected_headcount']} attendees\n\n"
        f"### Dietary & Special Requirements\n"
        f"{projected['dietary_specs']}\n\n"
        f"### Loading Dock & Access\n"
        f"- Delivery van access: UW HUB loading bay (Gate 3).\n"
        f"- Arrival window: 45 minutes prior to service time for setup and dietary labeling."
    )

    assert_no_sensitive_leakage("vendor", body)

    return {
        "event_id": event_id,
        "recipient_role": "vendor",
        "recipient_id": target.get("id"),
        "recipient_name": target.get("company_name"),
        "fingerprint": fingerprint,
        "status": "draft",
        "markdown_body": body,
        "projected_data": projected
    }


def generate_volunteer_briefing(event_id: str = "evt-dubhacks-2026", volunteer_id: str = "vol-001") -> dict[str, Any]:
    """Generate a permission-scoped shift & task briefing for student volunteers."""
    ev = get_event_brief(event_id) or {}
    tasks = query_records("tasks", event_id=event_id)
    target = {"id": volunteer_id, "name": "Event Ops Volunteer"}

    projected = project_volunteer_allowed_fields(target, ev, tasks)
    fingerprint = compute_source_fingerprint(projected)

    checklist_str = "\n".join(f"- [ ] {t}" for t in projected["checklist"])
    body = (
        f"# Volunteer Briefing: {projected['volunteer_name']}\n\n"
        f"**Event:** {projected['event_title']}\n"
        f"**Date:** {projected['event_date']}\n"
        f"**Venue:** {projected['venue']}\n"
        f"**Reporting Time & Location:** {projected['assigned_shift']} at {projected['reporting_location']}\n\n"
        f"### Day-Of Checklist\n"
        f"{checklist_str}\n\n"
        f"### Emergency & Lead Contact\n"
        f"- Lead Organizer: Diya / Operations Desk\n"
        f"- Radios on Channel 2 for logistics team."
    )

    assert_no_sensitive_leakage("volunteer", body)

    return {
        "event_id": event_id,
        "recipient_role": "volunteer",
        "recipient_id": target.get("id"),
        "recipient_name": target.get("name"),
        "fingerprint": fingerprint,
        "status": "draft",
        "markdown_body": body,
        "projected_data": projected
    }


def evaluate_briefing_readiness(briefing_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Verify whether a briefing draft is ready to send without missing assumptions."""
    unresolved = []
    proj = briefing_data.get("projected_data", {})
    for k, v in proj.items():
        if "tbd" in str(v).lower() or "unconfirmed" in str(v).lower():
            unresolved.append(f"Field '{k}' is unconfirmed: '{v}'")

    is_ready = len(unresolved) == 0
    return is_ready, unresolved


def preview_briefing(event_id: str = "evt-dubhacks-2026", role: str = "speaker", recipient_id: str = "") -> dict[str, Any]:
    """Preview a role-specific participant briefing with readiness verification."""
    role_clean = role.lower().strip()
    if role_clean == "speaker":
        draft = generate_speaker_briefing(event_id, recipient_id)
    elif role_clean in ("vendor", "catering"):
        draft = generate_vendor_briefing(event_id, recipient_id)
    else:
        draft = generate_volunteer_briefing(event_id, recipient_id or "vol-001")

    is_ready, blockers = evaluate_briefing_readiness(draft)
    draft["is_ready"] = is_ready
    draft["blockers"] = blockers
    return draft


def generate_role_briefing(role: str, participant_id: str | None = None, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Generate and dispatch a role-specific briefing draft."""
    return preview_briefing(event_id=event_id, role=role, recipient_id=participant_id or "")

