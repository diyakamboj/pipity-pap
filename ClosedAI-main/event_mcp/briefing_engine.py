"""L2 Briefing Engine: Role-Specific, Versioned Participant Briefings.

Generates permission-scoped, versioned briefing drafts for:
1. Speakers (session timing, arrival instructions, stage AV, emergency contact).
2. Vendors (delivery window, loading dock access, food policies, service setup).
3. Volunteers (assigned shift, check-in lobby, operational checklist, escalation contact).

Core Principles:
- Strictly Permission-Scoped (Positive Projection): Explicit allowlists prevent
  cross-role data leaks before formatting:
  * Speakers receive NO vendor pricing, competitor quotes, or sponsor funding amounts.
  * Vendors receive NO pricing, quotes, competitor comparisons, budgets, or private speaker contacts.
  * Volunteers receive NO financial data, sponsor contracts, or private speaker contacts.
- Grounded Truthfulness & Inline Labeling: Never invent confirmed times, agreements, or
  personal contact details. All unverified planning assumptions, tentative offsets, assumed
  venue rules, and unassigned roles are explicitly tagged inline throughout the briefing draft.
- Strict Readiness & Sending Guards: Prevents a briefing from becoming 'ready' or 'sent'
  whenever underlying external commitments remain unverified. No boolean bypass is permitted;
  any authorized exception workflow is strictly deferred to the future authenticated approval layer.
- Fingerprinted Versioning & Exact-Field Staleness: Computes a deterministic SHA-256 fingerprint
  from the exact source fields used by each role. Unrelated changes (e.g. vendor updates)
  do not falsely mark speaker briefings as stale.
- Sent-Version Immutability: Previously sent briefings are immutable and preserved in a
  timestamped revision history; revisions automatically create new drafts with incremented versions.
- Preview-First Safety: Agent-facing MCP tools are strictly read-only and preview-only.
  Persistence is reserved for internal backend operations tied to human approval actions.

=============================================================================
SECURITY NOTICE: Role-Specific Redaction vs. Requester Authorization
=============================================================================
Role-specific field allowlisting and positive projection enforces least privilege
by restricting which data fields are packaged into briefing drafts for each participant
role (e.g. speakers do not receive vendor pricing or sponsor amounts; vendors do not
receive pricing, budgets, competitor quotes, or private speaker emails; volunteers do not
receive financial contracts).

CRITICAL ARCHITECTURAL DISTINCTION:
This content filtering controls what is packaged inside a given role's briefing artifact.
It is NOT a substitute for requester authentication or access control. The application
runtime, API layer, or security gateway MUST authenticate the requesting caller and verify
their authorization before permitting retrieval, preview, or transmission of any briefing.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Optional

from event_store import Briefing, ConfirmationState, EventStore


# ---------------------------------------------------------------------------
# Predefined Volunteer Roles and Templates
# ---------------------------------------------------------------------------
VOLUNTEER_ROLES: dict[str, dict[str, Any]] = {
    "vol-001": {
        "id": "vol-001",
        "role_title": "Check-in Desk & Attendee Registration",
        "assigned_volunteer": "Unassigned (Pending student volunteer recruitment)",
        "shift_time": "08:30 - 11:30",
        "timing_state": "assumed",
        "location": "Gates Hall 106 Lobby",
        "checklist": [
            "[PROPOSED] Staff lobby check-in desk starting 08:30 AM (planning arrival estimate)",
            "[PROPOSED] Test attendee QR code/badge scanner with organizing team",
            "[PROPOSED] Distribute printed name badges and lanyards to arriving attendees",
            "[PROPOSED] Direct attendees into Gates Hall 106 auditorium for 09:15 opening",
            "[PROPOSED] Flag walk-in attendees to lead organizer for capacity check",
        ],
        "missing_details": [
            "Requires organizer confirmation of assigned student volunteer names (currently unassigned)",
            "Shift timing (08:30 - 11:30) is a planning estimate; requires confirmation with assigned volunteer",
            "Requires registration platform cutoff for badge count verification",
            "Requires lead organizer (Diya) confirmed emergency phone number",
        ],
    },
    "vol-002": {
        "id": "vol-002",
        "role_title": "Speaker Support & Stage AV Hand",
        "assigned_volunteer": "Unassigned (Pending student volunteer recruitment)",
        "shift_time": "09:00 - 13:00",
        "timing_state": "assumed",
        "location": "Gates Hall 106 Auditorium Stage",
        "checklist": [
            "[PROPOSED] Meet Prof. Sara Kim at Gates Hall lobby at 09:00 AM (tentative arrival)",
            "[PROPOSED] Escort speaker to podium for 09:10 AV & microphone sound check",
            "[PROPOSED] Verify dual HDMI projection display mirrors speaker laptop",
            "[PROPOSED] Provide 10-minute and 5-minute cue cards during keynote",
            "[PROPOSED] Assist morning workshop hands-on transition at 11:00 AM",
        ],
        "missing_details": [
            "Requires organizer confirmation of assigned student volunteer names (currently unassigned)",
            "Requires confirmation of morning keynote slide format and aspect ratio",
            "Requires facility coordinator verification of AV cabinet keys",
            "Requires lead organizer (Diya) confirmed emergency phone number",
        ],
    },
    "vol-003": {
        "id": "vol-003",
        "role_title": "Venue Teardown & Room Reset",
        "assigned_volunteer": "Unassigned (Pending student volunteer recruitment)",
        "shift_time": "16:30 - 18:00",
        "timing_state": "assumed",
        "location": "Gates Hall 106 Main Hall & Patio",
        "checklist": [
            "[PROPOSED] Collect leftover printed materials and unused lanyards for recycling",
            "[PROPOSED] Disconnect and return podium HDMI cables and microphones to AV cabinet",
            "[PROPOSED] Assist catering vendor with prompt service bay departure before 30-min limit",
            "[PROPOSED] Conduct room reset and walkthrough before strict 18:00 venue curfew lock-out",
        ],
        "missing_details": [
            "Requires organizer confirmation of assigned student volunteer names (currently unassigned)",
            "Requires facility coordinator walkthrough and room lock-out checklist completion",
            "Venue 18:00 curfew lock-out is an assumed constraint pending facility verification",
            "Requires lead organizer (Diya) confirmed emergency phone number",
        ],
    },
}


# ---------------------------------------------------------------------------
# 1. Source Fingerprinting and Stale Detection
# ---------------------------------------------------------------------------
def compute_source_fingerprint(
    store: EventStore, role: str, recipient_id: str
) -> tuple[str, list[str]]:
    """Compute a deterministic hash of only the exact approved source fields used by the briefing role.

    Excludes unrelated fields so that changes to vendor pricing do not stale speaker
    briefings, changes to speaker topics do not stale vendor briefings, and changes
    to sponsor funding do not stale any briefings.

    Returns:
        (fingerprint_hex, list_of_source_record_ids)
    """
    role_norm = role.lower().strip()
    source_records: list[str] = ["evt-001", "venue"]
    event = store.get_event()
    venue = store.get_venue_constraints()

    data_to_hash: dict[str, Any] = {}

    if role_norm == "speaker":
        source_records.append(recipient_id)
        spk = store.find_speaker(recipient_id) or {}
        sessions = [s for s in store.all_schedule_items() if s.get("speaker_id") == recipient_id]
        if sessions:
            source_records.extend([s["id"] for s in sessions])
        data_to_hash = {
            "event": {
                "name": event.get("name"),
                "date": event.get("date"),
                "venue": event.get("venue"),
            },
            "venue": {
                "venue_name": venue.get("venue_name"),
                "av_provisions": venue.get("av_provisions"),
            },
            "speaker": {
                "name": spk.get("name"),
                "status": spk.get("status"),
                "availability": spk.get("availability"),
                "topic": spk.get("topic"),
            },
            "sessions": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time"),
                    "room": s.get("room"),
                    "confirmation_state": s.get("confirmation_state"),
                }
                for s in sessions
            ],
        }

    elif role_norm == "vendor":
        source_records.append(recipient_id)
        vnd = store.find_vendor(recipient_id) or {}
        sessions = [s for s in store.all_schedule_items() if s.get("vendor_id") == recipient_id]
        if sessions:
            source_records.extend([s["id"] for s in sessions])
        data_to_hash = {
            "event": {
                "name": event.get("name"),
                "date": event.get("date"),
                "attendees": event.get("attendees"),
            },
            "venue": {
                "venue_name": venue.get("venue_name"),
                "loading_dock_instructions": venue.get("loading_dock_instructions"),
                "food_policy": venue.get("food_policy"),
            },
            "vendor": {
                "name": vnd.get("name"),
                "category": vnd.get("category"),
                "confirmed": vnd.get("confirmed"),
                "dietary": vnd.get("dietary"),
            },
            "sessions": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time"),
                    "room": s.get("room"),
                    "confirmation_state": s.get("confirmation_state"),
                }
                for s in sessions
            ],
        }

    elif role_norm == "volunteer":
        vol_info = VOLUNTEER_ROLES.get(recipient_id, VOLUNTEER_ROLES["vol-001"])
        source_records.append(vol_info["id"])
        data_to_hash = {
            "event": {
                "name": event.get("name"),
                "date": event.get("date"),
            },
            "venue": {
                "venue_name": venue.get("venue_name"),
                "curfew": venue.get("curfew"),
                "operating_window": f"{venue.get('access_start', '08:00')} - {venue.get('access_end', '18:00')}",
            },
            "volunteer": {
                "id": vol_info.get("id"),
                "role_title": vol_info.get("role_title"),
                "shift_time": vol_info.get("shift_time"),
                "location": vol_info.get("location"),
                "assigned_volunteer": vol_info.get("assigned_volunteer"),
                "checklist": vol_info.get("checklist"),
                "missing_details": vol_info.get("missing_details"),
            },
        }
        if recipient_id == "vol-002":
            data_to_hash["venue"]["av_provisions"] = venue.get("av_provisions")
            keynote_sessions = [
                s for s in store.all_schedule_items() if s.get("item_type") == "keynote"
            ]
            if keynote_sessions:
                source_records.extend([s["id"] for s in keynote_sessions])
                data_to_hash["keynote_session"] = [
                    {
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                    }
                    for s in keynote_sessions
                ]

    raw_json = json.dumps(data_to_hash, sort_keys=True)
    digest = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()[:16]
    return digest, sorted(list(set(source_records)))


def check_stale_briefings(store: EventStore) -> dict[str, Any]:
    """Inspect all stored briefings and detect staleness against current live data.

    Strictly read-only; never mutates stored briefings or triggers disk writes.
    """
    briefings = store.all_briefings()
    stale_list: list[dict[str, Any]] = []

    for b in briefings:
        b_id = b["id"]
        role = b.get("role", "speaker")
        recip_id = b.get("recipient_id", "")
        current_fp, _ = compute_source_fingerprint(store, role, recip_id)
        stored_fp = b.get("source_fingerprint", "")

        is_stale = False
        reasons: list[str] = []

        if stored_fp and stored_fp != current_fp:
            is_stale = True
            reasons.append(
                f"Source data modified (stored fingerprint '{stored_fp}' != live '{current_fp}')."
            )
        elif b.get("is_stale"):
            is_stale = True
            reasons.append("Manually flagged as stale.")

        if is_stale:
            stale_list.append(
                {
                    "briefing_id": b_id,
                    "recipient_name": b.get("recipient_name", ""),
                    "role": role,
                    "version": b.get("version", 1),
                    "status": b.get("status", "draft"),
                    "reasons": reasons,
                }
            )

    return {
        "total_briefings": len(briefings),
        "stale_count": len(stale_list),
        "stale_briefings": stale_list,
        "is_healthy": len(stale_list) == 0,
        "_canvas": {
            "module": "briefing_audit",
            "title": "Briefings Staleness & Version Audit",
        },
    }


# ---------------------------------------------------------------------------
# 2. Permission-Scoped Information Filtering & Allowlist Enforcement
# ---------------------------------------------------------------------------
SENSITIVE_PATTERNS = [
    # Vendor pricing & quotes
    "$1200",
    "$960",
    "$240",
    "1200",
    "960",
    "$15",
    "$12",
    "$3",
    "per head",
    "per_head",
    "quote",
    # Sponsor contracts & funding
    "$2000",
    "$1000",
    "2000",
    "1000",
    "Acme AI Labs",
    "Northwest Tech Fund",
    "gold tier",
    "silver tier",
]


def assert_no_sensitive_leakage(role: str, text: str) -> None:
    """Validate that text does not contain forbidden cross-role or financial info (defense-in-depth)."""
    role_norm = role.lower()
    text_lower = text.lower()

    if role_norm in ("speaker", "volunteer"):
        for sensitive in ("$1200", "$960", "campus catering co.", "acme ai labs", "northwest tech fund"):
            if sensitive in text_lower:
                raise ValueError(
                    f"Privacy Leakage Violation: Sensitive text '{sensitive}' found in {role} briefing."
                )

    if role_norm == "vendor":
        for sensitive in (
            "$",
            "quote",
            "per head",
            "per_head",
            "budget",
            "1200",
            "960",
            "240",
            "2000",
            "1000",
            "5000",
            "campus catering",
            "printfast",
            "acme ai labs",
            "northwest tech fund",
            "skim@cs.uw.edu",
            "achen@example.com",
            "mrivera@example.com",
        ):
            if sensitive in text_lower:
                raise ValueError(
                    f"Privacy Leakage Violation: Forbidden pricing, internal quote, or private detail '{sensitive}' found in vendor briefing."
                )

    if role_norm in ("volunteer",):
        for sensitive in ("skim@cs.uw.edu", "achen@example.com", "mrivera@example.com"):
            if sensitive in text_lower:
                raise ValueError(
                    f"Privacy Leakage Violation: Private speaker contact '{sensitive}' found in {role} briefing."
                )


# ---------------------------------------------------------------------------
# 3. Positive Field Projection Helpers (Enforced BEFORE Formatting)
# ---------------------------------------------------------------------------
def project_speaker_allowed_fields(
    event: dict[str, Any],
    venue: dict[str, Any],
    speaker: dict[str, Any],
    session: dict[str, Any],
    arrival_time: str,
    av_check_time: str,
    missing_details: list[str],
) -> dict[str, Any]:
    """Positively project only approved fields for speaker briefings."""
    return {
        "event_overview": {
            "event_name": event.get("name", "DubHacks Workshop 2026"),
            "date": event.get("date", "2026-11-15"),
            "theme": event.get("theme", "AI for Social Good"),
            "venue": venue.get("venue_name", "Gates Hall 106, UW Seattle"),
            "room": session.get("room", "Gates Hall 106"),
            "confirmation_label": "[CONFIRMED EVENT DETAILS]",
        },
        "session_details": {
            "session_title": session.get("title", speaker.get("topic", "Keynote")),
            "scheduled_time": f"{session.get('start_time')} - {session.get('end_time')}",
            "timing_state": session.get("confirmation_state", "tentative"),
            "speaker_participation_state": speaker.get("status", "prospecting"),
            "confirmation_label": "[TENTATIVE PLANNING SLOT - PENDING SPEAKER CONFIRMATION]",
        },
        "arrival_and_checkin": {
            "recommended_arrival": arrival_time,
            "checkin_location": "Gates Hall 106 main entrance lobby",
            "av_check_window": f"{av_check_time} at stage podium",
            "confirmation_label": "[PROPOSED TIMING - TENTATIVE]",
            "instructions": (
                f"Proposed arrival: {arrival_time} at Gates Hall 106 lobby. A student volunteer will "
                f"meet you at the check-in desk and escort you to the auditorium. Stage AV sound check "
                f"is proposed for {av_check_time} at the podium. "
                f"Note: All arrival and sound check times are tentative planning proposals subject to your confirmation."
            ),
        },
        "av_and_technical_provisions": {
            "microphones": "Podium microphone and wireless handheld microphones (Assumed venue equipment; pending facility test)",
            "displays": "Dual HDMI projection displays (16:9 format) (Assumed venue equipment)",
            "connectivity": (
                "Standard HDMI input provided at podium. "
                "[NEEDS ORGANIZER CONFIRMATION]: Display adapters (USB-C/DisplayPort to HDMI) are NOT guaranteed; "
                "please bring your own laptop adapters or verify availability."
            ),
            "confirmation_label": "[ASSUMED VENUE PROVISIONS - PENDING FACILITY VERIFICATION]",
        },
        "organizer_contact": {
            "name": "Diya",
            "role": "Lead Organizer",
            "contact_status": "[NEEDS ORGANIZER CONFIRMATION]",
            "phone_note": "Phone number pending organizer confirmation (never publish unverified contact details)",
            "instructions": (
                "For travel delays or schedule adjustments, please coordinate via organizer email in the interim. "
                "Verified direct phone contact will be provided once confirmed by the organizer."
            ),
        },
        "unconfirmed_items": list(missing_details),
    }


def project_vendor_allowed_fields(
    event: dict[str, Any],
    venue: dict[str, Any],
    vendor: dict[str, Any],
    session: dict[str, Any],
    arrival_time: str,
    missing_details: list[str],
) -> dict[str, Any]:
    """Positively project only approved fields for vendor briefings (excludes pricing/quotes/budgets)."""
    return {
        "event_overview": {
            "event_name": event.get("name", "DubHacks Workshop 2026"),
            "date": event.get("date", "2026-11-15"),
            "venue": venue.get("venue_name", "Gates Hall 106, UW Seattle"),
            "delivery_location": session.get("room", "Gates Hall 106 Patio/Lounge"),
            "confirmation_label": "[CONFIRMED EVENT DETAILS]",
        },
        "service_specifications": {
            "service_name": session.get("title", "Catering Service"),
            "service_window": f"{session.get('start_time')} - {session.get('end_time')}",
            "expected_headcount": event.get("attendees", 80),
            "dietary_specifications": vendor.get("dietary", "Standard, Vegan, GF options"),
            "booking_status": (
                "[CONFIRMED BOOKING]" if vendor.get("confirmed") else "[UNCONFIRMED BOOKING - PENDING CONTRACT]"
            ),
            "headcount_label": "[TARGET PLANNING ESTIMATE: ~80 attendees (Final headcount pending registration close on Nov 10)]",
            "dietary_label": (
                f"[VENDOR CAPABILITY - ATTENDEE COUNTS PENDING]: Caterer offers {vendor.get('dietary', 'Standard options')}; "
                "exact attendee dietary breakdown to be finalized after registration closes."
            ),
        },
        "delivery_and_loading_dock": {
            "delivery_window": f"{arrival_time} - 12:15",
            "loading_access": venue.get(
                "loading_dock_instructions",
                "Access via Stevens Way service bay. 30-minute active loading limit.",
            ),
            "dock_rule": "30-minute strict loading limit; vehicles must vacate bay promptly after drop-off.",
            "delivery_label": "[PROPOSED DELIVERY WINDOW - TENTATIVE: 11:45 - 12:15]",
            "dock_label": "[ASSUMED VENUE ACCESS: Stevens Way service bay (30-min active limit; bay reservation pending facility confirmation)]",
        },
        "venue_facility_policies": {
            "food_policy": venue.get(
                "food_policy",
                "Buffet permitted; cold/warm chafing dishes allowed; open flames prohibited.",
            ),
            "tables": "Buffet serving tables provided by organizing team in patio/lounge area [PROPOSED SETUP].",
            "clean_up": "Catering team to clear service dishes by 14:00 [PROPOSED SCHEDULE].",
            "policy_label": "[ASSUMED VENUE POLICY - PENDING FACILITY VERIFICATION]",
        },
        "organizer_contact": {
            "name": "Diya",
            "role": "Lead Organizer",
            "contact_status": "[NEEDS ORGANIZER CONFIRMATION]",
            "phone_note": "Phone number pending organizer confirmation (never publish unverified contact details)",
            "instructions": (
                "Please coordinate delivery arrival with Diya via organizer email in the interim. "
                "Direct contact for service bay gate access will be confirmed prior to event day."
            ),
        },
        "unconfirmed_items": list(missing_details),
    }


def project_volunteer_allowed_fields(
    event: dict[str, Any],
    venue: dict[str, Any],
    vol_info: dict[str, Any],
    missing_details: list[str],
) -> dict[str, Any]:
    """Positively project only approved fields for volunteer briefings."""
    return {
        "event_overview": {
            "event_name": event.get("name", "DubHacks Workshop 2026"),
            "date": event.get("date", "2026-11-15"),
            "venue": venue.get("venue_name", "Gates Hall 106, UW Seattle"),
            "operating_window": f"{venue.get('access_start', '08:00')} - {venue.get('access_end', '18:00')}",
            "confirmation_label": "[CONFIRMED EVENT DETAILS]",
        },
        "assignment": {
            "role_title": vol_info["role_title"],
            "shift_time": vol_info["shift_time"],
            "checkin_location": vol_info["location"],
            "assigned_volunteer": vol_info.get("assigned_volunteer", "Unassigned"),
            "assignment_label": "[UNASSIGNED ROLE - NEEDS ORGANIZER CONFIRMATION]",
            "shift_label": f"[PROPOSED SHIFT - PLANNING ESTIMATE: {vol_info['shift_time']}]",
        },
        "operational_checklist": list(vol_info["checklist"]),
        "venue_rules_and_curfew": {
            "curfew": venue.get("curfew", "18:00 strict lock-out."),
            "reminder": "All spaces must be returned to standard university condition by 18:00.",
            "curfew_label": "[ASSUMED VENUE CONSTRAINT - PENDING FACILITY VERIFICATION: 18:00 strict lock-out]",
        },
        "escalation_contact": {
            "name": "Diya",
            "role": "Lead Organizer",
            "contact_status": "[NEEDS ORGANIZER CONFIRMATION]",
            "phone_note": "Phone number pending organizer confirmation",
            "instructions": "Escalate attendee inquiries, speaker delays, or facility needs to Diya via organizer email in the interim.",
        },
        "unconfirmed_items": list(missing_details),
    }


# ---------------------------------------------------------------------------
# 4. Role-Specific Briefing Generators
# ---------------------------------------------------------------------------
def generate_speaker_briefing(store: EventStore, speaker_id: str) -> dict[str, Any]:
    """Generate a permission-scoped, grounded briefing draft for a speaker."""
    speaker = store.find_speaker(speaker_id)
    if not speaker:
        speaker = store.find_speaker("spk-003") or {
            "id": speaker_id,
            "name": "Speaker",
            "email": "",
            "topic": "Session Presentation",
            "status": "prospecting",
        }

    event = store.get_event()
    venue = store.get_venue_constraints()

    sessions = [s for s in store.all_schedule_items() if s.get("speaker_id") == speaker["id"]]
    session = sessions[0] if sessions else {
        "id": "sch-003",
        "title": speaker.get("topic", "Keynote Session"),
        "start_time": "09:30",
        "end_time": "10:30",
        "room": "Gates Hall 106",
        "confirmation_state": ConfirmationState.TENTATIVE.value,
    }

    # Timing calculations
    session_start = session.get("start_time", "09:30")
    start_hour, start_min = map(int, session_start.split(":"))
    total_min = start_hour * 60 + start_min
    arr_hour, arr_min = divmod(max(0, total_min - 30), 60)
    av_hour, av_min = divmod(max(0, total_min - 20), 60)
    arrival_time = f"{arr_hour:02d}:{arr_min:02d}"
    av_check_time = f"{av_hour:02d}:{av_min:02d}"

    # Missing / unconfirmed details
    missing_details: list[str] = []
    if speaker.get("status") != "confirmed":
        missing_details.append(
            f"Speaker participation status is '{speaker.get('status')}'; requires written confirmation of acceptance."
        )
    else:
        missing_details.append(
            "Speaker attendance is confirmed for Nov 15, but exact session slot (09:30 - 10:30) is a tentative planning assumption requiring speaker confirmation."
        )

    if session.get("confirmation_state") != ConfirmationState.CONFIRMED.value:
        missing_details.append(
            f"Proposed arrival ({arrival_time}) and sound check ({av_check_time}) are tentative operational proposals requiring speaker confirmation."
        )

    missing_details.append(
        "AV equipment (microphones, dual displays) is an assumed venue constraint requiring facility verification."
    )
    missing_details.append(
        "Display adapters (USB-C to HDMI) are not guaranteed by venue; speaker must bring personal adapters."
    )
    missing_details.append(
        "Requires lead organizer (Diya) confirmed emergency phone number."
    )

    # Positive field selection
    sections = project_speaker_allowed_fields(
        event=event,
        venue=venue,
        speaker=speaker,
        session=session,
        arrival_time=arrival_time,
        av_check_time=av_check_time,
        missing_details=missing_details,
    )

    # Rendered Markdown with explicit inline confirmation tags
    body_markdown = (
        f"# Speaker Briefing: {speaker.get('name')}\n\n"
        f"**Event:** {sections['event_overview']['event_name']} {sections['event_overview']['confirmation_label']}\n"
        f"**Date:** {sections['event_overview']['date']}\n"
        f"**Venue:** {sections['event_overview']['venue']} (Room: {sections['event_overview']['room']})\n\n"
        f"## Session Information {sections['session_details']['confirmation_label']}\n"
        f"- **Title:** {sections['session_details']['session_title']}\n"
        f"- **Scheduled Slot:** {sections['session_details']['scheduled_time']} "
        f"({sections['session_details']['timing_state']} planning slot; attendance confirmed for Nov 15, exact slot requires speaker confirmation)\n\n"
        f"## Arrival & Stage Check-in {sections['arrival_and_checkin']['confirmation_label']}\n"
        f"- **Proposed Arrival:** {sections['arrival_and_checkin']['recommended_arrival']} (Tentative planning proposal; requires speaker confirmation)\n"
        f"- **Check-in Location:** {sections['arrival_and_checkin']['checkin_location']}\n"
        f"- **AV Sound Check Window:** {sections['arrival_and_checkin']['av_check_window']} (Tentative planning proposal)\n"
        f"- **Instructions:** {sections['arrival_and_checkin']['instructions']}\n\n"
        f"## Technical & AV Provisions {sections['av_and_technical_provisions']['confirmation_label']}\n"
        f"- **Microphones:** {sections['av_and_technical_provisions']['microphones']}\n"
        f"- **Displays:** {sections['av_and_technical_provisions']['displays']}\n"
        f"- **Connectivity & Adapters:** {sections['av_and_technical_provisions']['connectivity']}\n\n"
        f"## Emergency Contact {sections['organizer_contact']['contact_status']}\n"
        f"- **Lead Organizer:** {sections['organizer_contact']['name']} ({sections['organizer_contact']['role']})\n"
        f"- **Phone Status:** {sections['organizer_contact']['phone_note']}\n"
        f"- **Coordination:** {sections['organizer_contact']['instructions']}\n\n"
        f"## Needs Organizer & Participant Confirmation\n"
        + "\n".join(f"- {item}" for item in missing_details)
    )

    assert_no_sensitive_leakage("speaker", body_markdown)
    fingerprint, source_records = compute_source_fingerprint(store, "speaker", speaker["id"])

    return {
        "id": f"brf-spk-{speaker['id'].split('-')[-1]}",
        "role": "speaker",
        "recipient_id": speaker["id"],
        "recipient_name": speaker["name"],
        "recipient_email": speaker.get("email", ""),
        "session_id": session.get("id"),
        "session_title": session.get("title"),
        "session_time": f"{session.get('start_time')} - {session.get('end_time')}",
        "arrival_time": arrival_time,
        "room": session.get("room"),
        "av_provisions": "Podium microphone, Dual HDMI projection displays [Assumed venue provision]",
        "notes": (
            f"AV sound check proposed for {av_check_time}. Attendance confirmed: {speaker.get('status') == 'confirmed'}; "
            "timing and adapters pending confirmation."
        ),
        "emergency_contact": "Diya (Lead Organizer) [Phone number pending organizer confirmation]",
        "confirmation_state": session.get("confirmation_state", "tentative"),
        "status": "draft",
        "is_stale": False,
        "version": 1,
        "source_fingerprint": fingerprint,
        "source_records": source_records,
        "missing_details": missing_details,
        "content": sections,
        "rendered_body": body_markdown,
    }


def generate_vendor_briefing(store: EventStore, vendor_id: str) -> dict[str, Any]:
    """Generate a permission-scoped, grounded briefing draft for a vendor (strictly excludes pricing)."""
    vendor = store.find_vendor(vendor_id)
    if not vendor:
        vendor = store.find_vendor("vnd-003") or {
            "id": vendor_id,
            "name": "Vendor",
            "category": "catering",
            "confirmed": False,
        }

    event = store.get_event()
    venue = store.get_venue_constraints()

    sessions = [s for s in store.all_schedule_items() if s.get("vendor_id") == vendor["id"]]
    session = sessions[0] if sessions else {
        "id": "sch-006",
        "title": "Lunch & Networking",
        "start_time": "12:30",
        "end_time": "13:30",
        "room": "Gates Hall 106 Patio/Lounge",
        "confirmation_state": ConfirmationState.TENTATIVE.value,
    }

    arrival_time = "11:45"
    missing_details: list[str] = []
    if not vendor.get("confirmed"):
        missing_details.append(
            "Catering booking is unconfirmed: requires organizer vendor selection and countersigned agreement."
        )
    missing_details.append(
        "Delivery window (11:45 - 12:15) is a tentative planning target; requires caterer confirmation."
    )
    missing_details.append(
        "Loading bay access (30-min active limit) is an assumed venue constraint; bay reservation not yet booked with facility."
    )
    missing_details.append(
        "Final attendee headcount and dietary breakdown require registration platform close (due Nov 10)."
    )
    missing_details.append(
        "Requires lead organizer (Diya) confirmed emergency phone number."
    )

    sections = project_vendor_allowed_fields(
        event=event,
        venue=venue,
        vendor=vendor,
        session=session,
        arrival_time=arrival_time,
        missing_details=missing_details,
    )

    body_markdown = (
        f"# Vendor Briefing: {vendor.get('name')}\n\n"
        f"**Event:** {sections['event_overview']['event_name']} {sections['event_overview']['confirmation_label']}\n"
        f"**Date:** {sections['event_overview']['date']}\n"
        f"**Delivery Location:** {sections['event_overview']['delivery_location']}\n\n"
        f"## Booking Status\n"
        f"- {sections['service_specifications']['booking_status']}: Catering agreement is under review; booking is NOT finalized until contract signed.\n\n"
        f"## Service & Headcount\n"
        f"- **Service:** {sections['service_specifications']['service_name']}\n"
        f"- **Serving Window:** {sections['service_specifications']['service_window']} [PROPOSED TIMING - TENTATIVE]\n"
        f"- **Headcount:** {sections['service_specifications']['headcount_label']}\n"
        f"- **Dietary Requirements:** {sections['service_specifications']['dietary_label']}\n\n"
        f"## Delivery & Service Bay Access\n"
        f"- **Target Delivery:** {sections['delivery_and_loading_dock']['delivery_label']}\n"
        f"- **Service Bay Access:** {sections['delivery_and_loading_dock']['dock_label']}\n"
        f"- **Dock Rule:** {sections['delivery_and_loading_dock']['dock_rule']}\n\n"
        f"## Venue Policies {sections['venue_facility_policies']['policy_label']}\n"
        f"- {sections['venue_facility_policies']['food_policy']}\n"
        f"- {sections['venue_facility_policies']['tables']}\n"
        f"- {sections['venue_facility_policies']['clean_up']}\n\n"
        f"## Logistics Lead Contact {sections['organizer_contact']['contact_status']}\n"
        f"- **Lead Organizer:** {sections['organizer_contact']['name']} ({sections['organizer_contact']['role']})\n"
        f"- **Phone Status:** {sections['organizer_contact']['phone_note']}\n"
        f"- **Coordination:** {sections['organizer_contact']['instructions']}\n\n"
        f"## Needs Organizer & Vendor Confirmation\n"
        + "\n".join(f"- {item}" for item in missing_details)
    )

    assert_no_sensitive_leakage("vendor", body_markdown)
    fingerprint, source_records = compute_source_fingerprint(store, "vendor", vendor["id"])

    return {
        "id": f"brf-vnd-{vendor['id'].split('-')[-1]}",
        "role": "vendor",
        "recipient_id": vendor["id"],
        "recipient_name": vendor["name"],
        "recipient_email": vendor.get("contact", ""),
        "session_id": session.get("id"),
        "session_title": session.get("title"),
        "session_time": f"{session.get('start_time')} - {session.get('end_time')}",
        "arrival_time": arrival_time,
        "room": session.get("room"),
        "av_provisions": "None (Catering Load-in)",
        "notes": f"Load-in via Stevens Way service bay. Booking confirmed: {bool(vendor.get('confirmed'))}.",
        "emergency_contact": "Diya (Lead Organizer) [Phone number pending organizer confirmation]",
        "confirmation_state": session.get("confirmation_state", "tentative"),
        "status": "draft",
        "is_stale": False,
        "version": 1,
        "source_fingerprint": fingerprint,
        "source_records": source_records,
        "missing_details": missing_details,
        "content": sections,
        "rendered_body": body_markdown,
    }


def generate_volunteer_briefing(store: EventStore, volunteer_id: str = "vol-001") -> dict[str, Any]:
    """Generate a permission-scoped, grounded briefing draft for a volunteer role."""
    vol_info = VOLUNTEER_ROLES.get(volunteer_id, VOLUNTEER_ROLES["vol-001"])
    event = store.get_event()
    venue = store.get_venue_constraints()

    missing_details = list(vol_info.get("missing_details", []))

    sections = project_volunteer_allowed_fields(
        event=event,
        venue=venue,
        vol_info=vol_info,
        missing_details=missing_details,
    )

    body_markdown = (
        f"# Volunteer Briefing: {vol_info['role_title']}\n\n"
        f"**Event:** {sections['event_overview']['event_name']} {sections['event_overview']['confirmation_label']}\n"
        f"**Date:** {sections['event_overview']['date']}\n"
        f"**Venue:** {sections['event_overview']['venue']}\n\n"
        f"## Volunteer Assignment {sections['assignment']['assignment_label']}\n"
        f"- **Assigned Volunteer:** {sections['assignment']['assigned_volunteer']}\n"
        f"- **Role:** {sections['assignment']['role_title']}\n"
        f"- **Shift Hours:** {sections['assignment']['shift_label']}\n"
        f"- **Reporting Station:** {sections['assignment']['checkin_location']} [ASSUMED VENUE LOCATION]\n\n"
        f"## Operational Duties & Checklist [PROPOSED TASKS]\n"
        + "\n".join(f"- [ ] {item}" for item in sections['operational_checklist'])
        + "\n\n"
        f"## Venue Policies & Curfew {sections['venue_rules_and_curfew']['curfew_label']}\n"
        f"- **Curfew:** {sections['venue_rules_and_curfew']['curfew']}\n"
        f"- {sections['venue_rules_and_curfew']['reminder']}\n\n"
        f"## Escalation Contact {sections['escalation_contact']['contact_status']}\n"
        f"- **Lead Organizer:** {sections['escalation_contact']['name']} ({sections['escalation_contact']['role']})\n"
        f"- **Phone Status:** {sections['escalation_contact']['phone_note']}\n"
        f"- **Instructions:** {sections['escalation_contact']['instructions']}\n\n"
        f"## Needs Organizer Confirmation\n"
        + "\n".join(f"- {item}" for item in missing_details)
    )

    assert_no_sensitive_leakage("volunteer", body_markdown)
    fingerprint, source_records = compute_source_fingerprint(store, "volunteer", vol_info["id"])

    return {
        "id": f"brf-{vol_info['id']}",
        "role": "volunteer",
        "recipient_id": vol_info["id"],
        "recipient_name": vol_info["role_title"],
        "recipient_email": "volunteers@dubhacks.org",
        "session_id": "sch-002",
        "session_title": vol_info["role_title"],
        "session_time": vol_info["shift_time"],
        "arrival_time": vol_info["shift_time"].split("-")[0].strip(),
        "room": vol_info["location"],
        "av_provisions": "Badge scanner & Lobby station [Assumed operational provision]",
        "notes": f"Volunteer shift: {vol_info['shift_time']} at {vol_info['location']}. Identity unassigned.",
        "emergency_contact": "Diya (Lead Organizer) [Phone number pending organizer confirmation]",
        "confirmation_state": ConfirmationState.ASSUMED.value,
        "status": "draft",
        "is_stale": False,
        "version": 1,
        "source_fingerprint": fingerprint,
        "source_records": source_records,
        "missing_details": missing_details,
        "content": sections,
        "rendered_body": body_markdown,
    }


# ---------------------------------------------------------------------------
# 5. Readiness and Sending Guard Verification
# ---------------------------------------------------------------------------
def evaluate_briefing_readiness(briefing: dict[str, Any] | Briefing) -> tuple[bool, list[str]]:
    """Determine whether a briefing meets safety criteria to be marked 'ready' or 'sent'.

    A briefing CANNOT be marked 'ready' or 'sent' if required external commitments,
    timing agreements, or operational facts remain unverified (tentative, assumed,
    unassigned, or missing details).

    Returns:
        (is_ready: bool, blocking_reasons: list[str])
    """
    b_dict = briefing.to_dict() if isinstance(briefing, Briefing) else briefing
    reasons: list[str] = []

    # 1. Missing / unconfirmed details list
    missing = b_dict.get("missing_details", [])
    if missing:
        reasons.extend([f"Unverified detail: {item}" for item in missing])

    # 2. Confirmation state
    conf_state = b_dict.get("confirmation_state", "tentative")
    if conf_state != ConfirmationState.CONFIRMED.value:
        reasons.append(f"Briefing confirmation state is '{conf_state}' (must be 'confirmed').")

    # 3. Role-specific unverified commitment checks
    role = b_dict.get("role", "").lower()
    content = b_dict.get("content", {})

    if role == "speaker":
        sess_details = content.get("session_details", {})
        sess_state = sess_details.get("timing_state", "")
        if sess_state and sess_state != ConfirmationState.CONFIRMED.value:
            reasons.append(f"Speaker session timing is '{sess_state}', not confirmed by speaker.")
        emergency = b_dict.get("emergency_contact", "")
        if "pending" in emergency.lower() or "needs" in emergency.lower():
            reasons.append("Organizer emergency contact phone is not verified.")

    elif role == "vendor":
        booking_state = content.get("service_specifications", {}).get("booking_status", "")
        if "unconfirmed" in booking_state.lower():
            reasons.append("Vendor booking contract is unconfirmed.")
        emergency = b_dict.get("emergency_contact", "")
        if "pending" in emergency.lower() or "needs" in emergency.lower():
            reasons.append("Organizer emergency contact phone is not verified.")

    elif role == "volunteer":
        assignment = content.get("assignment", {}).get("assigned_volunteer", "")
        if not assignment or "unassigned" in assignment.lower() or "pending" in assignment.lower():
            reasons.append("Volunteer identity is unassigned.")
        emergency = b_dict.get("emergency_contact", "")
        if "pending" in emergency.lower() or "needs" in emergency.lower():
            reasons.append("Organizer emergency contact phone is not verified.")

    return len(reasons) == 0, reasons


# ---------------------------------------------------------------------------
# 6. Preview-First Generator and List Handlers (Strictly Read-Only)
# ---------------------------------------------------------------------------
def preview_briefing(store: EventStore, role: str, recipient_id: str = "") -> dict[str, Any]:
    """Generate a strictly read-only preview of a participant briefing draft.

    Never modifies or persists records in the store.
    """
    role_norm = role.lower().strip()

    if role_norm == "speaker":
        recip = recipient_id or "spk-003"
        draft = generate_speaker_briefing(store, recip)
    elif role_norm == "vendor":
        recip = recipient_id or "vnd-003"
        draft = generate_vendor_briefing(store, recip)
    elif role_norm == "volunteer":
        recip = recipient_id or "vol-001"
        draft = generate_volunteer_briefing(store, recip)
    else:
        raise ValueError(
            f"Unsupported briefing role '{role}'. Supported roles are: 'speaker', 'vendor', 'volunteer'."
        )

    # Check if a previously stored version exists
    existing = store.find_briefing(draft["id"]) or store.find_briefing_by_recipient(role_norm, recip)
    if existing:
        draft["version"] = existing.get("version", 1)
        draft["status"] = existing.get("status", "draft")
        if existing.get("source_fingerprint") and existing["source_fingerprint"] != draft["source_fingerprint"]:
            draft["is_stale"] = True
            draft["stale_reason"] = "Live event, speaker, or schedule records have changed since last draft."
            if existing.get("status") == "sent":
                draft["version"] = existing.get("version", 1) + 1
                draft["status"] = "draft"

    return {
        "is_preview": True,
        "briefing": draft,
        "message": (
            f"Preview generated for {role} briefing ({draft['recipient_name']}). "
            f"Store was NOT modified. Sending requires organizer approval."
        ),
        "_canvas": {
            "module": "briefing_view",
            "title": f"Participant Briefing: {draft['recipient_name']} ({role.capitalize()})",
        },
    }


def list_briefings(store: EventStore, role: str = "") -> dict[str, Any]:
    """List participant briefings from the store with active staleness detection.

    Read-only. Use to review briefing statuses and render summary cards on Canvas.
    Never mutates store or triggers disk writes.
    """
    raw_briefings = store.all_briefings()
    role_norm = role.lower().strip()

    filtered = []
    for b in raw_briefings:
        item = copy.deepcopy(b)
        b_role = item.get("role", "").lower()
        if role_norm and b_role != role_norm:
            continue

        # Check staleness dynamically against current source records
        recip_id = item.get("recipient_id", "")
        current_fp, _ = compute_source_fingerprint(store, b_role, recip_id)
        if item.get("source_fingerprint") and item["source_fingerprint"] != current_fp:
            item["is_stale"] = True
            item["status"] = "stale" if item.get("status") != "sent" else "sent"
        filtered.append(item)

    return {
        "found": True,
        "total": len(filtered),
        "role_filter": role or "all",
        "briefings": filtered,
        "_canvas": {
            "module": "briefing_list",
            "title": f"Participant Briefings ({role.capitalize() if role else 'All Roles'})",
        },
    }


# ---------------------------------------------------------------------------
# 7. Internal Backend Operations (Reserved for Client-Side Approval Actions)
# ---------------------------------------------------------------------------
def save_briefing_draft(
    store: EventStore,
    role: str = "",
    recipient_id: str = "",
    briefing_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Internal backend operation to persist an organizer-approved briefing draft.

    Preserves sent versions and records history snapshots. Strictly blocks setting status
    to 'ready' or 'sent' whenever required external commitments remain unverified.
    Authorized human exception workflows are deferred to the future authenticated approval layer.
    NOT exposed directly as an MCP tool.
    """
    if briefing_data is None:
        preview = preview_briefing(store, role=role, recipient_id=recipient_id)
        briefing_data = preview["briefing"]

    target_status = briefing_data.get("status", "draft")
    if target_status in ("ready", "sent"):
        is_ready, reasons = evaluate_briefing_readiness(briefing_data)
        if not is_ready:
            formatted_reasons = "\n".join(f"- {r}" for r in reasons)
            raise ValueError(
                f"Cannot save briefing '{briefing_data.get('id')}' with status '{target_status}': "
                f"required external commitments remain unverified:\n{formatted_reasons}\n"
                "A briefing must remain in 'draft' status until all required details are confirmed. "
                "Any authorized exception workflow is deferred to the future authenticated approval layer."
            )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    briefing_data["updated_at"] = now_iso
    if not briefing_data.get("created_at"):
        briefing_data["created_at"] = now_iso

    saved = store.upsert_briefing_version(briefing_data)
    return {
        "success": True,
        "is_preview": False,
        "briefing_id": saved["id"],
        "version": saved["version"],
        "status": saved["status"],
        "message": f"Successfully persisted briefing '{saved['id']}' (v{saved['version']}).",
    }


def mark_briefing_sent(store: EventStore, briefing_id: str) -> dict[str, Any]:
    """Internal backend operation to record that an organizer approved and sent a briefing.

    Locks the version and preserves it against silent overwriting.
    Strictly blocks sending if required external commitments remain unverified.
    Authorized exception workflows are deferred to the future authenticated approval layer.
    NOT exposed as an MCP tool.
    """
    existing = store.find_briefing(briefing_id)
    if not existing:
        raise ValueError(f"Briefing '{briefing_id}' not found in store.")

    is_ready, reasons = evaluate_briefing_readiness(existing)
    if not is_ready:
        formatted_reasons = "\n".join(f"- {r}" for r in reasons)
        raise ValueError(
            f"Cannot send briefing '{briefing_id}': required external commitments remain unverified:\n"
            f"{formatted_reasons}\n"
            "Sending is blocked while required commitments remain unverified. "
            "Any authorized exception workflow is deferred to the future authenticated approval layer."
        )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    updated = store.update_briefing(
        briefing_id,
        {
            "status": "sent",
            "sent_at": now_iso,
            "updated_at": now_iso,
            "is_stale": False,
        },
    )
    return {
        "success": True,
        "briefing_id": briefing_id,
        "version": updated["version"],
        "status": "sent",
        "message": f"Briefing '{briefing_id}' marked as sent at {now_iso}.",
    }
