"""Gurt Schedule Engine.

Deterministic day-of run-of-show synthesis, precision minute math,
critical path analysis, and preview-first operational task planning.
"""

from __future__ import annotations

import copy
from typing import Any
from gurt.db import (
    get_connection,
    get_event_brief,
    get_schedule_items,
    get_tasks,
    query_records
)


def time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' string to total minutes from midnight."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return 0


def minutes_to_time(minutes: int) -> str:
    """Convert total minutes from midnight to 'HH:MM'."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_duration_minutes(start_time: str, end_time: str) -> int:
    """Calculate duration between two HH:MM strings."""
    start = time_to_minutes(start_time)
    end = time_to_minutes(end_time)
    if end >= start:
        return end - start
    return (24 * 60 - start) + end


def calculate_critical_path(tasks: list[dict[str, Any]]) -> list[str]:
    """Dynamically compute the critical path (longest dependency chain) from a task DAG."""
    task_ids = {t["id"] for t in tasks}
    successors: dict[str, list[str]] = {t_id: [] for t_id in task_ids}
    predecessors: dict[str, list[str]] = {t_id: [] for t_id in task_ids}

    for t in tasks:
        t_id = t["id"]
        deps_raw = t.get("dependencies") or []
        if isinstance(deps_raw, str):
            deps = [d.strip() for d in deps_raw.split(",") if d.strip() and d.strip().lower() != "none"]
        else:
            deps = list(deps_raw)

        for dep in deps:
            if dep in task_ids:
                successors[dep].append(t_id)
                predecessors[t_id].append(dep)

    in_degree = {t_id: len(predecessors[t_id]) for t_id in task_ids}
    queue = [t_id for t_id in task_ids if in_degree[t_id] == 0]
    queue.sort()

    dist: dict[str, int] = {t_id: 1 for t_id in task_ids}
    parent: dict[str, str | None] = {t_id: None for t_id in task_ids}

    visited_count = 0
    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for succ in successors[curr]:
            if dist[curr] + 1 > dist[succ]:
                dist[succ] = dist[curr] + 1
                parent[succ] = curr
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)
                queue.sort()

    if not dist:
        return []

    max_dist = max(dist.values())
    end_nodes = [t_id for t_id, d in dist.items() if d == max_dist]
    end_nodes.sort()
    curr_node = end_nodes[0]

    path = []
    while curr_node is not None:
        path.append(curr_node)
        curr_node = parent[curr_node]

    path.reverse()
    return path


def build_run_of_show(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Build a precision, chronological day-of run-of-show timeline with verification states and warnings."""
    ev = get_event_brief(event_id) or {}
    title = ev.get("title", "Event")
    date = ev.get("date", "2026-12-21")
    venue = ev.get("location", "Main Venue")

    # Fetch related records
    raw_items = get_schedule_items(event_id)
    speakers = query_records("speakers", event_id=event_id)
    vendors = query_records("vendors", event_id=event_id)
    sponsors = query_records("sponsors", event_id=event_id)

    speakers_by_id = {s["id"]: s for s in speakers}
    speakers_by_name = {s["name"].lower(): s for s in speakers}
    vendors_by_id = {v["id"]: v for v in vendors}

    # Normalize timeline
    sorted_items = []
    for item in raw_items:
        # Determine start/end times
        start_t = item.get("start_time") or ""
        end_t = item.get("end_time") or ""
        time_slot = item.get("time_slot") or ""
        if (not start_t or not end_t) and "-" in time_slot:
            parts = time_slot.split("-")
            start_t = parts[0].strip()
            end_t = parts[1].strip()

        item_copy = dict(item)
        item_copy["start_time"] = start_t
        item_copy["end_time"] = end_t
        item_copy["duration_minutes"] = calculate_duration_minutes(start_t, end_t)
        sorted_items.append(item_copy)

    sorted_items.sort(key=lambda x: time_to_minutes(x.get("start_time", "00:00")))

    timeline = []
    confirmed_count = 0
    tentative_count = 0
    missing_info = []

    for item in sorted_items:
        state = item.get("confirmation_state") or "tentative"
        if state == "confirmed":
            confirmed_count += 1
        else:
            tentative_count += 1

        # Link speaker
        spk_info = None
        spk_id = item.get("speaker_id")
        if spk_id and spk_id in speakers_by_id:
            spk = speakers_by_id[spk_id]
            spk_info = {
                "id": spk["id"],
                "name": spk["name"],
                "org": spk.get("org", ""),
                "topic": spk.get("topic", ""),
                "status": spk.get("status", "shortlist")
            }
        else:
            # Check owner or activity text for match
            owner_lower = item.get("owner", "").lower()
            for name_l, s in speakers_by_name.items():
                if name_l in owner_lower or name_l in item.get("activity", "").lower():
                    spk_info = {
                        "id": s["id"],
                        "name": s["name"],
                        "org": s.get("org", ""),
                        "topic": s.get("topic", ""),
                        "status": s.get("status", "shortlist")
                    }
                    break

        # Link vendor
        vnd_info = None
        vnd_id = item.get("vendor_id")
        if vnd_id and vnd_id in vendors_by_id:
            vnd = vendors_by_id[vnd_id]
            vnd_info = {
                "id": vnd["id"],
                "company_name": vnd["company_name"],
                "category": vnd.get("category", ""),
                "quote_amount": vnd.get("quote_amount", 0.0),
                "status": vnd.get("status", "quoted")
            }
        elif "lunch" in item.get("activity", "").lower() or "cater" in item.get("activity", "").lower():
            for v in vendors:
                if v.get("category", "").lower() == "catering" and v.get("status") in ("selected", "confirmed"):
                    vnd_info = {
                        "id": v["id"],
                        "company_name": v["company_name"],
                        "category": v.get("category", ""),
                        "quote_amount": v.get("quote_amount", 0.0),
                        "status": v.get("status", "quoted")
                    }
                    break

        entry = {
            "id": item.get("id"),
            "activity": item.get("activity", ""),
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "duration_minutes": item["duration_minutes"],
            "location": item.get("room") or item.get("location", venue),
            "owner": item.get("owner", "Event Operations"),
            "activity_type": item.get("activity_type", "session"),
            "confirmation_state": state,
            "speaker": spk_info,
            "vendor": vnd_info,
            "dependencies": item.get("dependencies", "None"),
            "notes": item.get("notes", "")
        }
        timeline.append(entry)

        # Gap & Missing Info analysis
        if spk_info:
            if spk_info["status"] != "confirmed":
                missing_info.append({
                    "type": "unconfirmed_speaker_slot",
                    "session_id": item.get("id"),
                    "activity": item.get("activity"),
                    "speaker": spk_info["name"],
                    "issue": f"{spk_info['name']} is on shortlist; exact time slot {item['start_time']}-{item['end_time']} is provisional.",
                    "required_action": f"Finalize speaker agreement for {spk_info['name']}."
                })
        if vnd_info:
            if vnd_info["status"] != "confirmed":
                missing_info.append({
                    "type": "unconfirmed_vendor_booking",
                    "session_id": item.get("id"),
                    "activity": item.get("activity"),
                    "vendor": vnd_info["company_name"],
                    "issue": f"Vendor {vnd_info['company_name']} ({vnd_info['category']}) has quote logged but final contract is pending.",
                    "required_action": "Review compliance & execute booking contract."
                })

    return {
        "event_id": event_id,
        "event_title": title,
        "date": date,
        "venue": venue,
        "timeline": timeline,
        "summary": {
            "total_slots": len(timeline),
            "confirmed_slots": confirmed_count,
            "tentative_slots": tentative_count
        },
        "missing_information": missing_info
    }


def generate_operational_tasks(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Synthesize actionable day-of operational tasks with owners, deadlines, and dependencies."""
    ros = build_run_of_show(event_id)
    timeline = ros.get("timeline", [])
    tasks = []

    for item in timeline:
        act = item.get("activity", "")
        start_t = item.get("start_time", "")
        owner = item.get("owner", "Logistics Lead")

        # AV line check for keynotes / presentations
        if any(w in act.lower() for w in ["keynote", "kickoff", "demo", "presentation"]):
            tasks.append({
                "title": f"Conduct AV mic & projector check for {act}",
                "owner": "Jordan AV Lead",
                "category": "AV",
                "deadline": start_t,
                "status": "todo",
                "dependencies": "None",
                "notes": f"Linked to session {item.get('id')} ({start_t})"
            })

        # Catering staging & inspection
        if any(w in act.lower() for w in ["lunch", "cater", "dinner", "breakfast"]):
            tasks.append({
                "title": f"Coordinate caterer loading dock arrival and dietary staging",
                "owner": "Sam Ops Lead",
                "category": "Catering",
                "deadline": start_t,
                "status": "todo",
                "dependencies": "None",
                "notes": f"Verify dietary labeling before {start_t} service."
            })

    return tasks
