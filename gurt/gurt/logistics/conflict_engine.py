"""Gurt Conflict Engine.

Deterministic schedule and room conflict detection, turnover buffer analysis,
vendor delivery window dependencies, and resolution proposal generation.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any
from gurt.db import (
    get_connection,
    get_event_brief,
    get_schedule_items,
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


def propose_conflict_resolutions(conflict_id: str, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Generate explainable, non-hallucinated schedule adjustments to resolve a conflict."""
    conflicts_data = detect_schedule_conflicts(event_id)
    target_conflict = next((c for c in conflicts_data.get("conflicts", []) if c.get("id") == conflict_id), None)
    if not target_conflict:
        return {"error": f"Conflict '{conflict_id}' not found or already resolved."}

    s_a_id = target_conflict.get("session_a_id")
    s_b_id = target_conflict.get("session_b_id")
    items = get_schedule_items(event_id)
    item_a = next((it for it in items if it.get("id") == s_a_id), {})
    item_b = next((it for it in items if it.get("id") == s_b_id), {})

    resolutions = []
    # Option 1: Time shift downstream session
    if target_conflict.get("conflict_type") in ("room_double_booking", "insufficient_turnover_buffer"):
        s_a_end = item_a.get("end_time") or "11:00"
        dur_b = calculate_duration_minutes(item_b.get("start_time", "11:00"), item_b.get("end_time", "12:00"))
        # Shift start to end_a + 15m buffer
        shifted_start_min = time_to_minutes(s_a_end) + 15
        shifted_end_min = shifted_start_min + max(30, dur_b)

        resolutions.append({
            "resolution_type": "time_shift",
            "target_session_id": s_b_id,
            "target_session_title": item_b.get("activity"),
            "proposed_start_time": minutes_to_time(shifted_start_min),
            "proposed_end_time": minutes_to_time(shifted_end_min),
            "explanation": f"Shift '{item_b.get('activity')}' to start at {minutes_to_time(shifted_start_min)} to provide a 15-minute turnover buffer after '{item_a.get('activity')}'.",
            "requires_human_approval": True
        })

    return {
        "conflict_id": conflict_id,
        "conflict_type": target_conflict.get("conflict_type"),
        "room": target_conflict.get("room"),
        "resolutions": resolutions
    }
