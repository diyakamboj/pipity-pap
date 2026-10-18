"""Logistics Engine: Deterministic Run-of-Show and Operational Task Planner.

Generates:
1. Chronological day-of run-of-show with confirmation states, dependencies, and missing information.
2. Actionable operational tasks with owners, deadlines, dependencies, linked session IDs, and status.
3. Preview-first workflow to ensure tasks are not persisted without explicit organizer confirmation.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from event_store import ConfirmationState, EventStore, OperationalTask


def _time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' string to total minutes from midnight."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def _minutes_to_time(minutes: int) -> str:
    """Convert total minutes from midnight to 'HH:MM'."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _calculate_duration_minutes(start_time: str, end_time: str) -> int:
    """Calculate duration between two HH:MM strings."""
    start = _time_to_minutes(start_time)
    end = _time_to_minutes(end_time)
    if end >= start:
        return end - start
    return (24 * 60 - start) + end


# ---------------------------------------------------------------------------
# 1. Day-of Run-of-Show Generation
# ---------------------------------------------------------------------------
def build_run_of_show(store: EventStore) -> dict[str, Any]:
    """Build a sorted, chronological day-of run-of-show timeline from store records.

    Enriches schedule slots with speaker and vendor commitments, flags missing
    information, and identifies confirmation states.
    """
    event = store.get_event()
    venue = store.get_venue_constraints()
    speakers_by_id = {s["id"]: s for s in store.all_speakers()}
    vendors_by_id = {v["id"]: v for v in store.all_vendors()}
    sponsors_by_id = {s["id"]: s for s in store.all_sponsors()}

    raw_items = store.all_schedule_items()
    # Sort chronologically by start_time
    sorted_items = sorted(raw_items, key=lambda x: _time_to_minutes(x.get("start_time", "00:00")))

    timeline: list[dict[str, Any]] = []
    confirmed_count = 0
    tentative_count = 0
    assumed_count = 0
    proposed_count = 0

    for item in sorted_items:
        state = item.get("confirmation_state", ConfirmationState.TENTATIVE.value)
        if state == ConfirmationState.CONFIRMED.value:
            confirmed_count += 1
        elif state == ConfirmationState.TENTATIVE.value:
            tentative_count += 1
        elif state == ConfirmationState.ASSUMED.value:
            assumed_count += 1
        elif state == ConfirmationState.PROPOSED.value:
            proposed_count += 1

        speaker_info = None
        spk_id = item.get("speaker_id")
        if spk_id and spk_id in speakers_by_id:
            spk = speakers_by_id[spk_id]
            speaker_info = {
                "id": spk["id"],
                "name": spk["name"],
                "org": spk.get("org", ""),
                "topic": spk.get("topic", ""),
                "status": spk.get("status", "prospecting"),
                "availability": spk.get("availability", "Unknown"),
            }

        vendor_info = None
        vnd_id = item.get("vendor_id")
        if vnd_id and vnd_id in vendors_by_id:
            vnd = vendors_by_id[vnd_id]
            vendor_info = {
                "id": vnd["id"],
                "name": vnd["name"],
                "category": vnd.get("category", ""),
                "quote": vnd.get("quote"),
                "confirmed": vnd.get("confirmed", False),
            }

        duration = _calculate_duration_minutes(
            item.get("start_time", "00:00"), item.get("end_time", "00:00")
        )

        timeline.append(
            {
                "id": item["id"],
                "title": item.get("title", ""),
                "start_time": item.get("start_time", ""),
                "end_time": item.get("end_time", ""),
                "duration_minutes": duration,
                "room": item.get("room", venue.get("venue_name", "")),
                "item_type": item.get("item_type", "session"),
                "confirmation_state": state,
                "speaker": speaker_info,
                "vendor": vendor_info,
                "dependencies": list(item.get("dependencies", [])),
                "notes": item.get("notes", ""),
            }
        )

    # Detect missing information and items requiring organizer confirmation
    missing_info: list[dict[str, Any]] = []

    # 1. Speaker slot confirmation
    for item in timeline:
        if item.get("speaker"):
            spk = item["speaker"]
            if spk["status"] == "confirmed" and item["confirmation_state"] != ConfirmationState.CONFIRMED.value:
                missing_info.append(
                    {
                        "type": "unconfirmed_speaker_slot",
                        "session_id": item["id"],
                        "session_title": item["title"],
                        "speaker_id": spk["id"],
                        "speaker_name": spk["name"],
                        "issue": f"{spk['name']} attendance is confirmed for the event date, but the exact session slot ({item['start_time']}-{item['end_time']}) is tentative.",
                        "required_action": "Contact speaker to confirm availability for the scheduled time slot.",
                    }
                )
            elif spk["status"] != "confirmed":
                missing_info.append(
                    {
                        "type": "uncommitted_speaker",
                        "session_id": item["id"],
                        "session_title": item["title"],
                        "speaker_id": spk["id"],
                        "speaker_name": spk["name"],
                        "issue": f"{spk['name']} has outreach status '{spk['status']}'; session is placed tentatively.",
                        "required_action": "Complete speaker outreach and secure firm commitment.",
                    }
                )

    # 2. Vendor booking confirmation
    for item in timeline:
        if item.get("vendor"):
            vnd = item["vendor"]
            if not vnd.get("confirmed"):
                missing_info.append(
                    {
                        "type": "unconfirmed_vendor_booking",
                        "session_id": item["id"],
                        "session_title": item["title"],
                        "vendor_id": vnd["id"],
                        "vendor_name": vnd["name"],
                        "issue": f"Vendor {vnd['name']} ({vnd['category']}) has not been confirmed or booked.",
                        "required_action": f"Compare quotes and execute booking for {vnd['name']}.",
                    }
                )

    # 3. Badge production lead-time warning
    badge_vendor = store.find_vendor("badges")
    if badge_vendor and not badge_vendor.get("confirmed"):
        missing_info.append(
            {
                "type": "lead_time_deadline",
                "vendor_id": badge_vendor["id"],
                "vendor_name": badge_vendor["name"],
                "issue": f"{badge_vendor['name']} requires 4 days lead time; order must be placed by Nov 11 for Nov 15 event.",
                "required_action": "Finalize attendee list and submit badge printing order before Nov 11 cutoff.",
            }
        )

    # 4. Venue operating constraint check
    access_start = venue.get("access_start", "08:00")
    access_end = venue.get("access_end", "18:00")
    if timeline:
        first_start = timeline[0]["start_time"]
        last_end = timeline[-1]["end_time"]
        if _time_to_minutes(first_start) < _time_to_minutes(access_start):
            missing_info.append(
                {
                    "type": "venue_access_violation",
                    "issue": f"First schedule item starts at {first_start}, before venue access begins at {access_start}.",
                    "required_action": "Shift early setup to after access_start or request early building unlock.",
                }
            )
        if _time_to_minutes(last_end) > _time_to_minutes(access_end):
            missing_info.append(
                {
                    "type": "venue_curfew_violation",
                    "issue": f"Last schedule item ends at {last_end}, exceeding venue curfew at {access_end}.",
                    "required_action": "Compress afternoon sessions to ensure room reset by curfew.",
                }
            )

    return {
        "event_name": event.get("name", "DubHacks Workshop 2026"),
        "date": event.get("date", "2026-11-15"),
        "venue": venue.get("venue_name", "Gates Hall 106, UW Seattle"),
        "operating_window": f"{access_start} - {access_end}",
        "timeline": timeline,
        "summary": {
            "total_slots": len(timeline),
            "confirmed_slots": confirmed_count,
            "tentative_slots": tentative_count,
            "assumed_slots": assumed_count,
            "proposed_slots": proposed_count,
        },
        "missing_information": missing_info,
        "_canvas": {
            "module": "run_of_show",
            "title": f"{event.get('name', 'Event')} — Day-of Run of Show",
        },
    }


# ---------------------------------------------------------------------------
# 2. Operational Task Plan Generation & Dynamic Critical Path
# ---------------------------------------------------------------------------
def calculate_critical_path(tasks: list[dict[str, Any]]) -> list[str]:
    """Dynamically compute the critical path (longest dependency chain) from a task DAG."""
    task_ids = {t["id"] for t in tasks}
    successors: dict[str, list[str]] = {t_id: [] for t_id in task_ids}
    predecessors: dict[str, list[str]] = {t_id: [] for t_id in task_ids}

    for t in tasks:
        t_id = t["id"]
        for dep in t.get("depends_on", []):
            if dep in task_ids:
                successors[dep].append(t_id)
                predecessors[t_id].append(dep)

    # In-degrees for Kahn's topological sort
    in_degree = {t_id: len(predecessors[t_id]) for t_id in task_ids}
    queue = [t_id for t_id in task_ids if in_degree[t_id] == 0]
    queue.sort()

    topo_order: list[str] = []
    while queue:
        curr = queue.pop(0)
        topo_order.append(curr)
        for nxt in sorted(successors[curr]):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    # If cycle detected or empty, return empty list
    if len(topo_order) < len(task_ids):
        return []

    # Dynamic programming for longest dependency chain (critical path)
    dist: dict[str, int] = {t_id: 1 for t_id in task_ids}
    prev: dict[str, Optional[str]] = {t_id: None for t_id in task_ids}

    for u in topo_order:
        for v in successors[u]:
            if dist[u] + 1 > dist[v]:
                dist[v] = dist[u] + 1
                prev[v] = u

    if not dist:
        return []
    max_node = max(dist.keys(), key=lambda k: dist[k])

    path: list[str] = []
    curr_node: Optional[str] = max_node
    while curr_node is not None:
        path.append(curr_node)
        curr_node = prev[curr_node]
    path.reverse()
    return path


def validate_task_dependencies(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify that dependencies reference valid tasks and form an acyclic graph (DAG)."""
    task_ids = {t["id"] for t in tasks}
    errors: list[str] = []

    # Check for invalid references and self-dependencies
    for t in tasks:
        t_id = t["id"]
        for dep in t.get("depends_on", []):
            if dep == t_id:
                errors.append(f"Task '{t_id}' cannot depend on itself.")
            elif dep not in task_ids:
                errors.append(f"Task '{t_id}' references unknown dependency '{dep}'.")

    # Check for dependency cycles via topological sort
    if not errors:
        topo = calculate_critical_path(tasks)
        if not topo and tasks:
            errors.append("Cyclic dependency loop detected among operational tasks.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }


def _generate_default_operational_plan(store: EventStore) -> list[OperationalTask]:
    """Deterministically generate operational tasks derived from event context.

    Note on confirmation accuracy:
    Operational tasks are labeled according to the grounded state of their underlying
    commitments (tentative or assumed). Tasks include explicit confirmation_requirements
    rather than treating deadlines or task existence as proof of verified facts.
    """
    event = store.get_event()
    event_date = event.get("date", "2026-11-15")

    tasks: list[OperationalTask] = [
        OperationalTask(
            id="tsk-001",
            title="Confirm speaker availability",
            owner="Diya",
            status="open",
            due_date="2026-10-25",
            depends_on=[],
            notes="Follow up with spk-001 and spk-002; spk-003 already confirmed.",
            category="speakers",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-003",
            confirmation_requirement="Requires written speaker confirmation of talk title and specific time slot.",
        ),
        OperationalTask(
            id="tsk-002",
            title="Send vendor quote requests",
            owner="Team",
            status="open",
            due_date="2026-10-22",
            depends_on=[],
            notes="Contact Campus Catering Co. and Taste of Seoul; PrintFast already quoted.",
            category="catering",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-006",
            confirmation_requirement="Requires vendor quote responses and menu selections before booking.",
        ),
        OperationalTask(
            id="tsk-003",
            title="Draft sponsor outreach emails",
            owner="Gurt",
            status="open",
            due_date="2026-10-20",
            depends_on=[],
            notes="Draft for Acme AI Labs and Northwest Tech Fund pending organizer approval.",
            category="sponsors",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-004",
            confirmation_requirement="Requires organizer review and approval of sponsor email drafts.",
        ),
        OperationalTask(
            id="tsk-004",
            title="Book catering vendor",
            owner="Team",
            status="open",
            due_date="2026-11-01",
            depends_on=["tsk-002"],
            notes="Compare quotes from vnd-001 and vnd-003 after receiving final numbers.",
            category="catering",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-006",
            confirmation_requirement="Requires organizer quote selection and signed catering order.",
        ),
        OperationalTask(
            id="tsk-005",
            title="Order badges and lanyards",
            owner="Team",
            status="open",
            due_date="2026-11-11",
            depends_on=["tsk-006"],
            notes="4-day lead time -- must place by Nov 11 for Nov 15 delivery.",
            category="logistics",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-002",
            confirmation_requirement="Requires locked headcount and approved badge artwork by Nov 11 cutoff.",
        ),
        OperationalTask(
            id="tsk-006",
            title="Confirm final headcount with registration",
            owner="Diya",
            status="open",
            due_date="2026-11-10",
            depends_on=[],
            notes="Required for catering order and badge count.",
            category="logistics",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-002",
            confirmation_requirement="Requires registration platform cutoff and final attendee count.",
        ),
        OperationalTask(
            id="tsk-007",
            title="Create run-of-show document",
            owner="Gurt",
            status="open",
            due_date="2026-11-12",
            depends_on=["tsk-001", "tsk-004"],
            notes="Needs confirmed speaker schedule and catering arrival time.",
            category="logistics",
            confirmation_state=ConfirmationState.ASSUMED.value,
            session_id=None,
            confirmation_requirement="Requires confirmed speaker slots and catering delivery window.",
        ),
        OperationalTask(
            id="tsk-008",
            title="Verify Gates Hall 106 AV & dual projection displays",
            owner="Team",
            status="open",
            due_date="2026-11-14",
            depends_on=["tsk-007"],
            notes="Test podium mic, 2 handheld wireless mics, and HDMI projection inputs.",
            category="venue",
            confirmation_state=ConfirmationState.ASSUMED.value,
            session_id="sch-001",
            confirmation_requirement="Requires facility coordinator verification of Gates Hall 106 AV cabinet access and mic batteries.",
        ),
        OperationalTask(
            id="tsk-009",
            title="Coordinate catering delivery and load-in at service bay",
            owner="Team",
            status="open",
            due_date=event_date,
            depends_on=["tsk-004"],
            notes="Meet Taste of Seoul at Stevens Way service bay (11:45 AM). 30-min active loading limit.",
            category="catering",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-006",
            confirmation_requirement="Requires confirmed vendor booking and loading dock reservation.",
        ),
        OperationalTask(
            id="tsk-010",
            title="Send logistics briefing to Prof. Sara Kim",
            owner="Gurt",
            status="open",
            due_date="2026-11-10",
            depends_on=["tsk-001"],
            notes="Send room, AV check time (09:10), arrival window, and organizer emergency contact.",
            category="speakers",
            confirmation_state=ConfirmationState.TENTATIVE.value,
            session_id="sch-003",
            confirmation_requirement="Requires confirmed morning keynote schedule before sending final briefing.",
        ),
        OperationalTask(
            id="tsk-011",
            title="Setup check-in desk and test badge scanner",
            owner="Team",
            status="open",
            due_date=event_date,
            depends_on=["tsk-005"],
            notes="Staff Gates Hall 106 lobby check-in desk starting 08:30 AM.",
            category="logistics",
            confirmation_state=ConfirmationState.ASSUMED.value,
            session_id="sch-002",
            confirmation_requirement="Requires volunteer assignment and equipment availability confirmation.",
        ),
        OperationalTask(
            id="tsk-012",
            title="Execute venue teardown and room reset before curfew",
            owner="Team",
            status="open",
            due_date=event_date,
            depends_on=["tsk-008"],
            notes="Complete clean-up, return AV cables, and clear room before strict 18:00 lock-out.",
            category="venue",
            confirmation_state=ConfirmationState.ASSUMED.value,
            session_id="sch-010",
            confirmation_requirement="Requires facility coordinator walkthrough and room lock-out checklist completion.",
        ),
    ]
    return tasks


def generate_operational_tasks(store: EventStore) -> dict[str, Any]:
    """Generate a proposed operational task plan for event logistics.

    Strictly Read-Only & Preview-Only:
    This function NEVER modifies or persists data in the event store.
    It returns a preview of the proposed plan with owners, due dates,
    dependencies, session links, and underlying confirmation requirements.

    Committing tasks is an internal backend operation reserved for future
    approval-gated actions.
    """
    proposed_tasks = _generate_default_operational_plan(store)
    existing_tasks = {t["id"]: t for t in store.all_tasks()}

    merged_tasks: list[dict[str, Any]] = []
    new_count = 0
    existing_count = 0

    for task in proposed_tasks:
        task_dict = task.to_dict()
        t_id = task_dict["id"]
        if t_id in existing_tasks:
            existing_count += 1
            current = copy.deepcopy(existing_tasks[t_id])
            merged = copy.deepcopy(current)

            # Preserve manual edits: keep title, owner, status, notes
            for field_name in ("title", "owner", "status", "notes"):
                if current.get(field_name):
                    merged[field_name] = current[field_name]

            # Due date preservation
            if current.get("due_date"):
                merged["due_date"] = current["due_date"]
                merged["due"] = current["due_date"]
            elif current.get("due"):
                merged["due_date"] = current["due"]
                merged["due"] = current["due"]

            # Dependencies: preserve user-specified dependencies if set, else enrich
            if not current.get("depends_on") and task_dict.get("depends_on"):
                merged["depends_on"] = list(task_dict["depends_on"])

            # Enrich missing domain attributes if not set in existing
            for k in ("category", "confirmation_state", "session_id", "confirmation_requirement"):
                if not merged.get(k) and task_dict.get(k):
                    merged[k] = task_dict[k]

            merged_tasks.append(merged)
        else:
            new_count += 1
            merged_tasks.append(task_dict)

    # Include any custom user-added tasks not in default plan
    proposed_ids = {t.id for t in proposed_tasks}
    for custom_id, custom_task in existing_tasks.items():
        if custom_id not in proposed_ids:
            merged_tasks.append(copy.deepcopy(custom_task))
            existing_count += 1

    # Validate dependency network
    validation = validate_task_dependencies(merged_tasks)

    # Dynamically compute critical path from dependency graph
    critical_path = calculate_critical_path(merged_tasks)

    message = (
        f"Preview of proposed operational plan generated with {len(merged_tasks)} tasks "
        f"({new_count} proposed new, {existing_count} existing/updated). "
        f"Store was NOT modified. Changes require organizer approval before persistence."
    )

    return {
        "is_preview": True,
        "message": message,
        "total_tasks": len(merged_tasks),
        "new_tasks_count": new_count,
        "existing_tasks_count": existing_count,
        "dependency_validation": validation,
        "critical_path": critical_path,
        "tasks": merged_tasks,
        "_canvas": {
            "module": "task_board",
            "title": "Proposed Operational Plan",
        },
    }


def commit_task_plan(store: EventStore, tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Internal backend operation to commit an approved task plan to the store.

    This function is intended for invocation exclusively by the client-side
    approval handler after genuine human review. It is NOT exposed directly as an
    agent-accessible MCP tool.
    """
    if tasks is None:
        plan = generate_operational_tasks(store)
        tasks = plan["tasks"]

    saved = store.upsert_tasks(tasks)
    return {
        "success": True,
        "persisted_count": len(saved),
        "message": f"Successfully committed {len(saved)} tasks to the active logistics store.",
    }


def _infer_task_category(task: dict[str, Any]) -> str:
    """Infer category for tasks that do not have an explicit category set."""
    if task.get("category"):
        return task["category"]
    title = task.get("title", "").lower()
    notes = task.get("notes", "").lower()
    t_id = task.get("id", "")

    if t_id == "tsk-001" or "speaker" in title or "speaker" in notes:
        return "speakers"
    if t_id in ("tsk-002", "tsk-004") or "catering" in title or "catering" in notes or "quote" in title:
        return "catering"
    if t_id == "tsk-003" or "sponsor" in title or "sponsor" in notes:
        return "sponsors"
    if "venue" in title or "hall" in title or "projection" in title or "teardown" in title:
        return "venue"
    return "logistics"


def get_task_board(
    store: EventStore,
    filter_category: str = "",
    filter_owner: str = "",
    filter_status: str = "",
) -> dict[str, Any]:
    """Retrieve active tasks grouped by category and owner with progress summary."""
    raw_tasks = store.all_tasks()
    tasks = []
    for t in raw_tasks:
        item = copy.deepcopy(t)
        if not item.get("category"):
            item["category"] = _infer_task_category(item)
        tasks.append(item)

    if filter_category:
        tasks = [t for t in tasks if filter_category.lower() in t.get("category", "").lower()]
    if filter_owner:
        tasks = [t for t in tasks if filter_owner.lower() in t.get("owner", "").lower()]
    if filter_status:
        tasks = [t for t in tasks if filter_status.lower() == t.get("status", "").lower()]

    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    status_summary = {"open": 0, "in_progress": 0, "done": 0, "blocked": 0}

    for t in tasks:
        cat = t.get("category", "general")
        by_category.setdefault(cat, []).append(t)
        st = t.get("status", "open").lower()
        if st in status_summary:
            status_summary[st] += 1
        else:
            status_summary[st] = 1

    return {
        "found": True,
        "total": len(tasks),
        "status_summary": status_summary,
        "categories": by_category,
        "tasks": tasks,
        "_canvas": {
            "module": "task_board",
            "title": "Logistics Task Board",
        },
    }
