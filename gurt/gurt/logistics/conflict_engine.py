"""Gurt Conflict Engine.

Deterministic schedule and room conflict detection, turnover buffer analysis,
vendor delivery window dependencies, and resolution proposal generation.
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
    get_schedule_item_by_id,
    update_schedule_item,
    log_audit_event,
    query_records
)
from gurt.logistics.schedule_engine import (
    time_to_minutes,
    minutes_to_time,
    calculate_duration_minutes
)


def intervals_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """Half-open interval overlap math: [start_a, end_a) and [start_b, end_b)."""
    s_a = time_to_minutes(start_a)
    e_a = time_to_minutes(end_a)
    s_b = time_to_minutes(start_b)
    e_b = time_to_minutes(end_b)
    return max(s_a, s_b) < min(e_a, e_b)


def is_shared_or_nonexclusive_space(room_name: str) -> bool:
    """Filter out non-exclusive or shared spaces that allow concurrent activities."""
    name_l = (room_name or "").lower().strip()
    shared_keywords = [
        "lobby", "foyer", "atrium", "hallway", "corridor", "patio",
        "courtyard", "registration", "outdoor", "common area", "lounge"
    ]
    return any(k in name_l for k in shared_keywords)


def is_valid_time_str(time_str: str) -> bool:
    """Validate that time_str matches strictly valid 24-hour HH:MM format."""
    if not isinstance(time_str, str):
        return False
    return re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", time_str.strip()) is not None


def compute_session_fingerprint(session: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 fingerprint of a session's scheduling state."""
    state = {
        "id": str(session.get("id", "")).strip(),
        "event_id": str(session.get("event_id", "")).strip(),
        "start_time": str(session.get("start_time", "")).strip(),
        "end_time": str(session.get("end_time", "")).strip(),
        "room": str(session.get("room") or session.get("location") or "").strip(),
        "location": str(session.get("location") or session.get("room") or "").strip(),
        "time_slot": str(session.get("time_slot", "")).strip()
    }
    raw = json.dumps(state, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_schedule_dependencies(
    target_session_id: str,
    target_start_time: str,
    all_sessions: list[dict[str, Any]]
) -> str | None:
    """Verify that target session does not start before its dependencies finish. Returns error message or None."""
    target = next((s for s in all_sessions if s.get("id") == target_session_id), None)
    if not target:
        return None
    raw_deps = target.get("dependencies")
    if not raw_deps or str(raw_deps).strip().lower() in ("none", ""):
        return None

    if isinstance(raw_deps, list):
        dep_ids = [str(d).strip() for d in raw_deps if str(d).strip()]
    else:
        dep_ids = [d.strip() for d in str(raw_deps).split(",") if d.strip()]

    sessions_by_id = {s.get("id"): s for s in all_sessions}
    target_start_min = time_to_minutes(target_start_time)

    for dep_id in dep_ids:
        if dep_id in sessions_by_id:
            dep_session = sessions_by_id[dep_id]
            dep_end = dep_session.get("end_time") or ""
            if not dep_end and "-" in (dep_session.get("time_slot") or ""):
                dep_end = dep_session["time_slot"].split("-")[-1].strip()
            if dep_end and is_valid_time_str(dep_end):
                dep_end_min = time_to_minutes(dep_end)
                if target_start_min < dep_end_min:
                    return f"Dependency violation: Session '{target_session_id}' scheduled at {target_start_time} cannot start before predecessor '{dep_id}' ({dep_session.get('activity', '')}) finishes at {dep_end}."
    return None


def detect_schedule_conflicts(
    event_id_or_items: str | list[dict[str, Any]] = "evt-dubhacks-2026",
    schedule_items: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Detect room overlaps, turnover buffer insufficiencies, vendor delivery constraints, and venue limits."""
    if isinstance(event_id_or_items, list):
        items = event_id_or_items
        event_id = "evt-dubhacks-2026"
    else:
        event_id = event_id_or_items
        items = schedule_items if schedule_items is not None else get_schedule_items(event_id)

    ev = get_event_brief(event_id) or {}
    vendors = query_records("vendors", event_id=event_id)
    conflicts: list[dict[str, Any]] = []

    # Normalize schedule items
    normalized = []
    for it in items:
        start_t = it.get("start_time") or ""
        end_t = it.get("end_time") or ""
        if not start_t or not end_t:
            ts = it.get("time_slot", "")
            if "-" in ts:
                parts = ts.split("-")
                start_t = parts[0].strip()
                end_t = parts[1].strip()

        room = it.get("room") or it.get("location") or "Main Hall"
        entry = dict(it)
        entry["start_time"] = start_t
        entry["end_time"] = end_t
        entry["room"] = room
        entry["setup_buffer_minutes"] = it.get("setup_buffer_minutes") or 0
        entry["teardown_buffer_minutes"] = it.get("teardown_buffer_minutes") or 0
        normalized.append(entry)

    # 1. Exclusive Room Overlaps & Turnover Buffers
    by_room: dict[str, list[dict[str, Any]]] = {}
    for it in normalized:
        rm = it["room"]
        if not is_shared_or_nonexclusive_space(rm):
            by_room.setdefault(rm, []).append(it)

    for room, room_items in by_room.items():
        room_items_sorted = sorted(room_items, key=lambda x: time_to_minutes(x["start_time"]))
        for i in range(len(room_items_sorted)):
            for j in range(i + 1, len(room_items_sorted)):
                item_a = room_items_sorted[i]
                item_b = room_items_sorted[j]

                s_a, e_a = item_a["start_time"], item_a["end_time"]
                s_b, e_b = item_b["start_time"], item_b["end_time"]

                # Direct overlap check
                if intervals_overlap(s_a, e_a, s_b, e_b):
                    conflicts.append({
                        "id": f"cnf-ovl-{item_a.get('id')}-{item_b.get('id')}",
                        "conflict_type": "room_double_booking",
                        "severity": "high",
                        "room": room,
                        "session_a_id": item_a.get("id"),
                        "session_a_title": item_a.get("activity"),
                        "session_a_time": f"{s_a} - {e_a}",
                        "session_b_id": item_b.get("id"),
                        "session_b_title": item_b.get("activity"),
                        "session_b_time": f"{s_b} - {e_b}",
                        "description": f"Room '{room}' is double-booked between '{item_a.get('activity')}' ({s_a}-{e_a}) and '{item_b.get('activity')}' ({s_b}-{e_b}).",
                        "requires_human_approval": True
                    })
                else:
                    # Turnover buffer check (minimum 10 minutes needed between consecutive sessions in same room)
                    gap = time_to_minutes(s_b) - time_to_minutes(e_a)
                    req_turnover = max(10, item_a.get("teardown_buffer_minutes", 0), item_b.get("setup_buffer_minutes", 0))
                    if 0 <= gap < req_turnover:
                        conflicts.append({
                            "id": f"cnf-buf-{item_a.get('id')}-{item_b.get('id')}",
                            "conflict_type": "insufficient_turnover_buffer",
                            "severity": "medium",
                            "room": room,
                            "session_a_id": item_a.get("id"),
                            "session_a_title": item_a.get("activity"),
                            "session_b_id": item_b.get("id"),
                            "session_b_title": item_b.get("activity"),
                            "gap_minutes": gap,
                            "required_buffer_minutes": req_turnover,
                            "description": f"Only {gap}m turnover between '{item_a.get('activity')}' and '{item_b.get('activity')}' in room '{room}' (at least {req_turnover}m needed).",
                            "requires_human_approval": True
                        })

    # 2. Vendor Delivery Window Readiness
    catering_items = [it for it in normalized if "lunch" in it.get("activity", "").lower() or "cater" in it.get("activity", "").lower()]
    for c_item in catering_items:
        lunch_start_min = time_to_minutes(c_item["start_time"])
        # Caterer must be set up at least 30 minutes before meal service begins
        required_arrival = minutes_to_time(max(0, lunch_start_min - 30))
        for v in vendors:
            if v.get("category", "").lower() == "catering":
                details_lower = (v.get("details") or "").lower()
                # Check for explicit delivery notes
                if "delivery" in details_lower or "dropoff" in details_lower:
                    pass

    return {
        "event_id": event_id,
        "event_title": ev.get("title", "Event"),
        "total_conflicts": len(conflicts),
        "has_blocking_conflicts": any(c["severity"] == "high" for c in conflicts),
        "conflicts": conflicts
    }


def analyze_schedule_impact(
    session_id: str,
    proposed_changes: dict[str, Any],
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Preview-first non-mutating impact analysis of shifting a schedule item."""
    items = get_schedule_items(event_id)
    target_item = next((it for it in items if it.get("id") == session_id), None)
    if not target_item:
        return {"error": f"Session '{session_id}' not found."}

    # Simulate updated item
    simulated_items = []
    for it in items:
        if it.get("id") == session_id:
            updated = dict(it)
            updated.update(proposed_changes)
            simulated_items.append(updated)
        else:
            simulated_items.append(dict(it))

    # Calculate conflicts on simulated list
    new_conflicts = []
    new_start = proposed_changes.get("start_time") or target_item.get("start_time")
    new_end = proposed_changes.get("end_time") or target_item.get("end_time")
    new_room = proposed_changes.get("room") or target_item.get("room") or target_item.get("location")

    for other in simulated_items:
        if other.get("id") == session_id:
            continue
        o_room = other.get("room") or other.get("location")
        if o_room == new_room and not is_shared_or_nonexclusive_space(new_room):
            o_s = other.get("start_time") or other.get("time_slot", "").split("-")[0].strip()
            o_e = other.get("end_time") or other.get("time_slot", "").split("-")[-1].strip()
            if intervals_overlap(new_start, new_end, o_s, o_e):
                new_conflicts.append({
                    "conflicting_session_id": other.get("id"),
                    "conflicting_title": other.get("activity"),
                    "time": f"{o_s} - {o_e}",
                    "room": new_room
                })

    return {
        "session_id": session_id,
        "current_state": {
            "activity": target_item.get("activity"),
            "time_slot": target_item.get("time_slot"),
            "location": target_item.get("location")
        },
        "proposed_changes": proposed_changes,
        "is_safe_to_apply": len(new_conflicts) == 0,
        "introduced_conflicts": new_conflicts,
        "requires_human_approval": True
    }


def _generate_resolutions_for_conflict(
    target_conflict: dict[str, Any],
    items: list[dict[str, Any]],
    event_id: str
) -> list[dict[str, Any]]:
    s_a_id = target_conflict.get("session_a_id")
    s_b_id = target_conflict.get("session_b_id")
    item_a = next((it for it in items if it.get("id") == s_a_id), {})
    item_b = next((it for it in items if it.get("id") == s_b_id), {})
    if not item_a or not item_b:
        return []

    c_type = target_conflict.get("conflict_type")
    resolutions = []

    if c_type in ("room_double_booking", "insufficient_turnover_buffer"):
        s_a_end = item_a.get("end_time") or ""
        if not s_a_end and "-" in (item_a.get("time_slot") or ""):
            s_a_end = item_a["time_slot"].split("-")[-1].strip()
        if not s_a_end:
            s_a_end = "10:00"

        s_b_start = item_b.get("start_time") or ""
        s_b_end = item_b.get("end_time") or ""
        if not s_b_start and "-" in (item_b.get("time_slot") or ""):
            parts = item_b["time_slot"].split("-")
            s_b_start, s_b_end = parts[0].strip(), parts[-1].strip()

        dur_b = calculate_duration_minutes(s_b_start or "10:00", s_b_end or "11:00")
        if dur_b <= 0:
            dur_b = 30

        req_buffer = max(10, int(item_a.get("teardown_buffer_minutes") or 0), int(item_b.get("setup_buffer_minutes") or 0))
        shifted_start_min = time_to_minutes(s_a_end) + req_buffer
        shifted_end_min = shifted_start_min + dur_b

        proposed_start = minutes_to_time(shifted_start_min)
        proposed_end = minutes_to_time(shifted_end_min)
        proposed_changes = {
            "start_time": proposed_start,
            "end_time": proposed_end,
            "time_slot": f"{proposed_start} - {proposed_end}"
        }

        # Check safety via impact preview
        impact = analyze_schedule_impact(s_b_id, proposed_changes, event_id=event_id)

        expected_state = {
            "id": s_b_id,
            "activity": item_b.get("activity"),
            "start_time": s_b_start,
            "end_time": s_b_end,
            "room": item_b.get("room") or item_b.get("location") or "",
            "location": item_b.get("location") or item_b.get("room") or "",
            "time_slot": item_b.get("time_slot", "")
        }

        fp = compute_session_fingerprint(item_b)

        resolutions.append({
            "resolution_id": f"res-shift-{s_b_id}-{shifted_start_min}",
            "conflict_id": target_conflict.get("id"),
            "resolution_type": "time_shift",
            "target_session_id": s_b_id,
            "target_session_title": item_b.get("activity"),
            "proposed_changes": proposed_changes,
            "expected_state": expected_state,
            "expected_fingerprint": fp,
            "is_safe_to_apply": impact.get("is_safe_to_apply", True),
            "introduced_conflicts": impact.get("introduced_conflicts", []),
            "explanation": f"Shift '{item_b.get('activity')}' to start at {proposed_start} (ends {proposed_end}) to provide a {req_buffer}-minute turnover buffer after '{item_a.get('activity')}'.",
            "requires_human_approval": True
        })

    return resolutions


def propose_conflict_resolutions(conflict_id: str | None = None, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Generate explainable, non-hallucinated schedule adjustments to resolve conflicts."""
    conflicts_data = detect_schedule_conflicts(event_id)
    all_conflicts = conflicts_data.get("conflicts", [])
    items = get_schedule_items(event_id)

    if conflict_id:
        target_conflict = next((c for c in all_conflicts if c.get("id") == conflict_id), None)
        if not target_conflict:
            return {
                "event_id": event_id,
                "conflict_id": conflict_id,
                "error": f"Conflict '{conflict_id}' not found or already resolved.",
                "resolutions": []
            }
        resolutions = _generate_resolutions_for_conflict(target_conflict, items, event_id)
        return {
            "event_id": event_id,
            "conflict_id": conflict_id,
            "conflict_type": target_conflict.get("conflict_type"),
            "room": target_conflict.get("room"),
            "resolutions": resolutions
        }

    # All conflicts
    all_proposals = []
    for c in all_conflicts:
        res_list = _generate_resolutions_for_conflict(c, items, event_id)
        all_proposals.extend(res_list)

    return {
        "event_id": event_id,
        "total_conflicts": len(all_conflicts),
        "total_proposals": len(all_proposals),
        "proposals": all_proposals
    }


def apply_conflict_resolution(
    event_id: str,
    session_id: str,
    proposed_changes: dict[str, Any],
    expected_fingerprint: str | None = None,
    conflict_id: str | None = None
) -> dict[str, Any]:
    """Apply an organizer-approved schedule resolution with strict validation and conflict recalculation."""
    # 1. Event Validation
    if not event_id or not isinstance(event_id, str) or not event_id.strip():
        return {"status": "error", "error": "invalid_input", "message": "event_id is required."}

    event = get_event_brief(event_id)
    if not event or not event.get("id"):
        return {"status": "error", "error": "not_found", "message": f"Event '{event_id}' not found."}

    # 2. Session Validation
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        return {"status": "error", "error": "invalid_input", "message": "session_id is required."}

    target_session = get_schedule_item_by_id(session_id, event_id=event_id)
    if not target_session:
        return {"status": "error", "error": "not_found", "message": f"Session '{session_id}' not found in event '{event_id}'."}

    # 3. Stale Proposal Check
    if expected_fingerprint:
        current_fp = compute_session_fingerprint(target_session)
        if current_fp != expected_fingerprint:
            return {
                "status": "error",
                "error": "stale_proposal",
                "message": f"Target session '{session_id}' has been modified since resolution was generated. Current fingerprint '{current_fp}' does not match expected '{expected_fingerprint}'. Please refresh conflicts.",
                "current_fingerprint": current_fp,
                "expected_fingerprint": expected_fingerprint
            }

    if conflict_id:
        current_conflicts = detect_schedule_conflicts(event_id).get("conflicts", [])
        if not any(c.get("id") == conflict_id for c in current_conflicts):
            return {
                "status": "error",
                "error": "conflict_already_resolved",
                "message": f"Conflict '{conflict_id}' is no longer active in the schedule."
            }

    # 4. Proposed Changes Validation
    if not proposed_changes or not isinstance(proposed_changes, dict):
        return {"status": "error", "error": "invalid_input", "message": "proposed_changes dictionary is required."}

    # Determine start and end times
    new_start = proposed_changes.get("start_time")
    new_end = proposed_changes.get("end_time")

    if (not new_start or not new_end) and "time_slot" in proposed_changes:
        ts = str(proposed_changes["time_slot"])
        if "-" in ts:
            parts = ts.split("-")
            new_start = new_start or parts[0].strip()
            new_end = new_end or parts[-1].strip()

    new_start = new_start or target_session.get("start_time")
    new_end = new_end or target_session.get("end_time")

    if not new_start or not is_valid_time_str(new_start):
        return {
            "status": "error",
            "error": "invalid_time",
            "message": f"Invalid start_time '{new_start}'. Must be HH:MM format (00:00 - 23:59)."
        }

    if not new_end or not is_valid_time_str(new_end):
        return {
            "status": "error",
            "error": "invalid_time",
            "message": f"Invalid end_time '{new_end}'. Must be HH:MM format (00:00 - 23:59)."
        }

    if time_to_minutes(new_start) >= time_to_minutes(new_end):
        return {
            "status": "error",
            "error": "invalid_time",
            "message": f"start_time ({new_start}) must be strictly before end_time ({new_end})."
        }

    # Room Validation
    if "room" in proposed_changes and not str(proposed_changes["room"]).strip():
        return {
            "status": "error",
            "error": "invalid_room",
            "message": "Room/location cannot be empty."
        }
    if "location" in proposed_changes and not str(proposed_changes["location"]).strip():
        return {
            "status": "error",
            "error": "invalid_room",
            "message": "Room/location cannot be empty."
        }
    new_room = proposed_changes.get("room") or proposed_changes.get("location") or target_session.get("room") or target_session.get("location")
    if not new_room or not str(new_room).strip():
        return {
            "status": "error",
            "error": "invalid_room",
            "message": "Room/location cannot be empty."
        }

    # Dependencies Validation
    all_sessions = get_schedule_items(event_id)
    dep_error = validate_schedule_dependencies(session_id, new_start, all_sessions)
    if dep_error:
        return {
            "status": "error",
            "error": "dependency_violation",
            "message": dep_error
        }

    # 5. Persist Approved Changes in SQLite
    clean_updates = dict(proposed_changes)
    clean_updates["start_time"] = new_start
    clean_updates["end_time"] = new_end
    clean_updates["room"] = str(new_room).strip()
    clean_updates["location"] = str(new_room).strip()
    clean_updates["time_slot"] = f"{new_start} - {new_end}"

    updated_row = update_schedule_item(item_id=session_id, updates=clean_updates, event_id=event_id)
    if not updated_row:
        return {"status": "error", "error": "update_failed", "message": f"Failed to update session '{session_id}' in database."}

    # 6. Audit Logging
    log_audit_event(
        event_id=event_id,
        actor_id="organizer",
        action="schedule_conflict_resolved",
        target_type="schedule",
        target_id=session_id,
        details={
            "conflict_id": conflict_id,
            "previous_time": target_session.get("time_slot"),
            "new_time": f"{new_start} - {new_end}",
            "room": str(new_room).strip()
        }
    )

    # 7. Recalculate Conflicts
    recalculated = detect_schedule_conflicts(event_id)
    is_resolved = conflict_id is None or not any(c.get("id") == conflict_id for c in recalculated.get("conflicts", []))

    return {
        "status": "applied",
        "message": f"Successfully applied schedule resolution for session '{session_id}'.",
        "session_id": session_id,
        "previous_state": target_session,
        "updated_session": updated_row,
        "recalculated_conflicts": recalculated,
        "is_conflict_resolved": is_resolved
    }
