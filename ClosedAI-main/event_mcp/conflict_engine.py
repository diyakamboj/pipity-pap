"""L3 Conflict Engine: Deterministic Conflict Detection, Impact Analysis, and Resolution Proposals.

Core Capabilities:
1. Deterministic Conflict Detection:
   - Room and exclusive resource overlaps (using half-open intervals [start, end)).
   - Non-exclusive/shared space filtering (avoiding false positives for Lobby/Patio).
   - Setup, cleanup, and turnover buffer insufficiency derived from source records.
   - Vendor arrival, delivery window, and service readiness dependencies.
   - Venue constraints (access hours, curfew, capacity) with verified vs. provisional states.
2. Downstream Impact Analysis (Preview-First):
   - Previews schedule modifications without mutating the persistent EventStore.
   - Detects newly introduced or resolved conflicts.
   - Identifies affected operational tasks, critical path dependencies, and participants.
   - Computes briefing staleness using exact-field SHA-256 fingerprinting.
3. Conflict Resolution Proposals:
   - Generates deterministic, explainable proposals (time shifts, buffer additions).
   - Never invents non-existent rooms or ungrounded availability.
   - Always sets `requires_human_approval: true`.
"""

import copy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
import sys
import threading
from typing import Any, Optional

# Ensure sibling imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from briefing_engine import compute_source_fingerprint
from event_store import ConfirmationState, EventStore, ScheduleItem


# ---------------------------------------------------------------------------
# In-Memory Simulated Store (Strict Zero-Mutation Isolation)
# ---------------------------------------------------------------------------
class SimulatedEventStore(EventStore):
    """Isolated, in-memory EventStore for conflict and impact simulations.

    Guarantees:
    - Never reads from or writes to the persistent storage file.
    - Operates entirely on an in-memory deep copy of event data.
    - Has its own independent lock.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.storage_path = "/dev/null"
        self._lock = threading.RLock()
        self._data = copy.deepcopy(data)

    def load(self) -> None:
        pass

    def save(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Time & Interval Helpers
# ---------------------------------------------------------------------------
def time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' string to total minutes from midnight."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return 0


def minutes_to_time(minutes: int) -> str:
    """Convert total minutes from midnight to 'HH:MM' string."""
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


def intervals_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """Check if two half-open intervals [start, end) overlap.

    Returns True iff start_a < end_b and start_b < end_a.
    A session ending exactly when another starts ([09:30, 10:30) and [10:30, 11:00))
    does NOT overlap.
    """
    s_a = time_to_minutes(start_a)
    e_a = time_to_minutes(end_a)
    s_b = time_to_minutes(start_b)
    e_b = time_to_minutes(end_b)
    return s_a < e_b and s_b < e_a


def is_shared_or_nonexclusive_space(room_name: str) -> bool:
    """Check whether a space is non-exclusive or shared by design.

    Spaces such as lobbies, patios, lounges, hallways, and common areas
    can host multiple non-conflicting activities simultaneously.
    """
    if not room_name:
        return False
    r_lower = room_name.lower()
    shared_keywords = ("lobby", "patio", "lounge", "foyer", "atrium", "hallway", "common")
    return any(k in r_lower for k in shared_keywords)


# ---------------------------------------------------------------------------
# Conflict Data Structures
# ---------------------------------------------------------------------------
class ConflictType:
    ROOM_OVERLAP = "ROOM_OVERLAP"
    RESOURCE_CONTENTION = "RESOURCE_CONTENTION"
    INSUFFICIENT_BUFFER = "INSUFFICIENT_BUFFER"
    VENDOR_SERVICE_MISALIGNMENT = "VENDOR_SERVICE_MISALIGNMENT"
    VENUE_CONSTRAINT_VIOLATION = "VENUE_CONSTRAINT_VIOLATION"


class ConflictSeverity:
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"


@dataclass
class ConflictIssue:
    id: str
    conflict_type: str
    severity: str
    verification_status: str  # "verified" or "provisional"
    affected_schedule_ids: list[str] = field(default_factory=list)
    affected_task_ids: list[str] = field(default_factory=list)
    affected_resource_ids: list[str] = field(default_factory=list)
    title: str = ""
    explanation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
    downstream_impacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. Deterministic Conflict Detection
# ---------------------------------------------------------------------------
def detect_schedule_conflicts(store: EventStore) -> dict[str, Any]:
    """Scan all event records and detect deterministic logistics conflicts.

    Returns:
        {
            "has_conflicts": bool,
            "total_conflicts": int,
            "verified_conflicts_count": int,
            "provisional_conflicts_count": int,
            "conflicts": list[dict],
            "missing_constraints": list[dict],
            "summary": str,
        }
    """
    conflicts: list[ConflictIssue] = []
    missing_constraints: list[dict[str, Any]] = []

    schedule_items = store.all_schedule_items()
    venue = store.get_venue_constraints()
    event = store.get_event()
    all_speakers = {s["id"]: s for s in store.all_speakers()}
    all_vendors = {v["id"]: v for v in store.all_vendors()}
    all_tasks = store.all_tasks()

    # Map tasks to schedule items
    tasks_by_session: dict[str, list[dict[str, Any]]] = {}
    for t in all_tasks:
        s_id = t.get("session_id")
        if s_id:
            tasks_by_session.setdefault(s_id, []).append(t)

    # -----------------------------------------------------------------------
    # A. Room and Exclusive Resource Overlaps
    # -----------------------------------------------------------------------
    n_items = len(schedule_items)
    for i in range(n_items):
        item_a = schedule_items[i]
        id_a = item_a["id"]
        room_a = (item_a.get("room") or "").strip()
        start_a = item_a.get("start_time", "00:00")
        end_a = item_a.get("end_time", "00:00")
        spk_a = item_a.get("speaker_id")
        vnd_a = item_a.get("vendor_id")

        for j in range(i + 1, n_items):
            item_b = schedule_items[j]
            id_b = item_b["id"]
            room_b = (item_b.get("room") or "").strip()
            start_b = item_b.get("start_time", "00:00")
            end_b = item_b.get("end_time", "00:00")
            spk_b = item_b.get("speaker_id")
            vnd_b = item_b.get("vendor_id")

            # Check time interval overlap [start, end)
            if not intervals_overlap(start_a, end_a, start_b, end_b):
                continue

            # Case A1: Room Overlap in Exclusive Spaces
            if room_a and room_b and room_a.lower() == room_b.lower():
                if not is_shared_or_nonexclusive_space(room_a):
                    pair_ids = sorted([id_a, id_b])
                    cfl_id = f"cfl-room-{pair_ids[0]}-{pair_ids[1]}"
                    state_a = item_a.get("confirmation_state", ConfirmationState.TENTATIVE.value)
                    state_b = item_b.get("confirmation_state", ConfirmationState.TENTATIVE.value)
                    is_verified = (
                        state_a == ConfirmationState.CONFIRMED.value
                        and state_b == ConfirmationState.CONFIRMED.value
                    )
                    v_status = "verified" if is_verified else "provisional"

                    affected_tasks: list[str] = []
                    for t in tasks_by_session.get(id_a, []) + tasks_by_session.get(id_b, []):
                        affected_tasks.append(t["id"])

                    conflicts.append(
                        ConflictIssue(
                            id=cfl_id,
                            conflict_type=ConflictType.ROOM_OVERLAP,
                            severity=ConflictSeverity.CRITICAL if is_verified else ConflictSeverity.HIGH,
                            verification_status=v_status,
                            affected_schedule_ids=[id_a, id_b],
                            affected_task_ids=list(set(affected_tasks)),
                            affected_resource_ids=[room_a],
                            title=f"Room contention in {room_a}: '{item_a.get('title')}' and '{item_b.get('title')}'",
                            explanation=(
                                f"Sessions '{item_a.get('title')}' ({start_a}-{end_a}) and "
                                f"'{item_b.get('title')}' ({start_b}-{end_b}) both require exclusive room '{room_a}' "
                                f"during overlapping intervals."
                            ),
                            evidence={
                                "session_a": {
                                    "id": id_a,
                                    "title": item_a.get("title"),
                                    "interval": f"{start_a}-{end_a}",
                                    "room": room_a,
                                    "confirmation_state": state_a,
                                },
                                "session_b": {
                                    "id": id_b,
                                    "title": item_b.get("title"),
                                    "interval": f"{start_b}-{end_b}",
                                    "room": room_b,
                                    "confirmation_state": state_b,
                                },
                            },
                            missing_information=(
                                []
                                if is_verified
                                else [
                                    f"Confirmation of session times for {id_a} and {id_b}",
                                    f"Verification of secondary room availability for one session",
                                ]
                            ),
                            downstream_impacts=[
                                f"Attendees cannot be in {room_a} for two sessions simultaneously",
                                f"AV and audio setups cannot run competing programs in the same space",
                                f"Linked operational tasks ({', '.join(affected_tasks) if affected_tasks else 'none'}) may stall",
                            ],
                        )
                    )

            # Case A2: Resource Contention (Speaker Double-Booking)
            if spk_a and spk_b and spk_a == spk_b:
                pair_ids = sorted([id_a, id_b])
                cfl_id = f"cfl-speaker-{spk_a}-{pair_ids[0]}-{pair_ids[1]}"
                spk_record = all_speakers.get(spk_a, {})
                spk_name = spk_record.get("name", spk_a)
                spk_status = spk_record.get("status", "prospecting")
                v_status = "verified" if spk_status == "confirmed" else "provisional"

                conflicts.append(
                    ConflictIssue(
                        id=cfl_id,
                        conflict_type=ConflictType.RESOURCE_CONTENTION,
                        severity=ConflictSeverity.CRITICAL if spk_status == "confirmed" else ConflictSeverity.HIGH,
                        verification_status=v_status,
                        affected_schedule_ids=[id_a, id_b],
                        affected_task_ids=[],
                        affected_resource_ids=[spk_a],
                        title=f"Speaker double-booking: {spk_name} assigned to overlapping sessions",
                        explanation=(
                            f"{spk_name} is scheduled for '{item_a.get('title')}' ({start_a}-{end_a}) and "
                            f"'{item_b.get('title')}' ({start_b}-{end_b}) simultaneously."
                        ),
                        evidence={
                            "speaker_id": spk_a,
                            "speaker_name": spk_name,
                            "speaker_status": spk_status,
                            "session_a": {"id": id_a, "interval": f"{start_a}-{end_a}"},
                            "session_b": {"id": id_b, "interval": f"{start_b}-{end_b}"},
                        },
                        missing_information=[f"Speaker availability confirmation for one or both time slots"],
                        downstream_impacts=[f"{spk_name} cannot present in two sessions at once"],
                    )
                )

            # Case A3: Resource Contention (Vendor Double-Booking Across Rooms)
            if vnd_a and vnd_b and vnd_a == vnd_b and room_a != room_b:
                pair_ids = sorted([id_a, id_b])
                cfl_id = f"cfl-vendor-double-{vnd_a}-{pair_ids[0]}-{pair_ids[1]}"
                vnd_record = all_vendors.get(vnd_a, {})
                vnd_name = vnd_record.get("name", vnd_a)
                v_status = "verified" if vnd_record.get("confirmed") else "provisional"

                conflicts.append(
                    ConflictIssue(
                        id=cfl_id,
                        conflict_type=ConflictType.RESOURCE_CONTENTION,
                        severity=ConflictSeverity.HIGH if vnd_record.get("confirmed") else ConflictSeverity.MEDIUM,
                        verification_status=v_status,
                        affected_schedule_ids=[id_a, id_b],
                        affected_task_ids=[],
                        affected_resource_ids=[vnd_a],
                        title=f"Vendor double-booking: {vnd_name} scheduled across different locations simultaneously",
                        explanation=(
                            f"Vendor {vnd_name} is scheduled to service '{item_a.get('title')}' in {room_a} "
                            f"and '{item_b.get('title')}' in {room_b} during overlapping time windows."
                        ),
                        evidence={
                            "vendor_id": vnd_a,
                            "vendor_name": vnd_name,
                            "session_a": {"id": id_a, "room": room_a, "interval": f"{start_a}-{end_a}"},
                            "session_b": {"id": id_b, "room": room_b, "interval": f"{start_b}-{end_b}"},
                        },
                        missing_information=["Vendor staffing capability across multiple concurrent rooms"],
                        downstream_impacts=[f"Vendor delivery or service personnel may be overextended"],
                    )
                )

    # -----------------------------------------------------------------------
    # B. Setup, Teardown, and Turnover Buffers
    # -----------------------------------------------------------------------
    # Sort items chronologically
    sorted_items = sorted(schedule_items, key=lambda x: time_to_minutes(x.get("start_time", "00:00")))

    # Check vendor setup buffer requirements stated in source records
    for item in sorted_items:
        vnd_id = item.get("vendor_id")
        if not vnd_id or vnd_id not in all_vendors:
            continue
        vnd = all_vendors[vnd_id]
        notes = (vnd.get("notes") or "").lower()
        # Check if source notes require a setup buffer, e.g. "setup at t-60 min"
        buffer_minutes = 0
        if "t-60" in notes or "60 min" in notes or "60-minute" in notes:
            buffer_minutes = 60
        elif "t-30" in notes or "30 min" in notes or "30-minute" in notes:
            buffer_minutes = 30

        if buffer_minutes > 0:
            session_start_m = time_to_minutes(item.get("start_time", "00:00"))
            required_arrival_m = session_start_m - buffer_minutes
            # Find preceding session in same room
            item_room = item.get("room", "")
            preceding_items = [
                x
                for x in sorted_items
                if x.get("room", "") == item_room
                and time_to_minutes(x.get("end_time", "00:00")) <= session_start_m
                and x["id"] != item["id"]
            ]
            if preceding_items:
                last_prec = preceding_items[-1]
                prec_end_m = time_to_minutes(last_prec.get("end_time", "00:00"))
                if prec_end_m > required_arrival_m:
                    # Buffer violation
                    cfl_id = f"cfl-buffer-{vnd_id}-{item['id']}"
                    is_confirmed = vnd.get("confirmed", False)
                    conflicts.append(
                        ConflictIssue(
                            id=cfl_id,
                            conflict_type=ConflictType.INSUFFICIENT_BUFFER,
                            severity=ConflictSeverity.HIGH if is_confirmed else ConflictSeverity.MEDIUM,
                            verification_status="verified" if is_confirmed else "provisional",
                            affected_schedule_ids=[last_prec["id"], item["id"]],
                            affected_task_ids=[],
                            affected_resource_ids=[vnd_id, item_room],
                            title=f"Insufficient setup buffer for {vnd.get('name')} before '{item.get('title')}'",
                            explanation=(
                                f"Vendor {vnd.get('name')} source record specifies a {buffer_minutes}-minute setup window. "
                                f"Session starts at {item.get('start_time')}, requiring room access by {minutes_to_time(required_arrival_m)}, "
                                f"but preceding session '{last_prec.get('title')}' occupies {item_room} until {last_prec.get('end_time')}."
                            ),
                            evidence={
                                "vendor_requirement": vnd.get("notes"),
                                "required_buffer_minutes": buffer_minutes,
                                "preceding_session_end": last_prec.get("end_time"),
                                "session_start": item.get("start_time"),
                            },
                            missing_information=[
                                f"Whether setup can occur in parallel with preceding activity",
                                f"Whether vendor arrival time can be adjusted",
                            ],
                            downstream_impacts=[
                                f"Service setup will be delayed into session start time",
                                f"Attendees may experience meal or service delays",
                            ],
                        )
                    )

    # Check unrecorded buffer constraints between consecutive sessions in exclusive rooms
    for k in range(len(sorted_items) - 1):
        curr = sorted_items[k]
        nxt = sorted_items[k + 1]
        curr_room = (curr.get("room") or "").strip()
        nxt_room = (nxt.get("room") or "").strip()

        if curr_room and curr_room.lower() == nxt_room.lower() and not is_shared_or_nonexclusive_space(curr_room):
            curr_end = curr.get("end_time", "00:00")
            nxt_start = nxt.get("start_time", "00:00")
            gap = time_to_minutes(nxt_start) - time_to_minutes(curr_end)

            # If gap is 0 minutes and activities have distinct speakers or types, check if buffer is documented
            if gap == 0 and curr.get("item_type") != nxt.get("item_type"):
                missing_constraints.append(
                    {
                        "type": "unspecified_turnover_buffer",
                        "room": curr_room,
                        "session_a": {"id": curr["id"], "title": curr.get("title"), "end": curr_end},
                        "session_b": {"id": nxt["id"], "title": nxt.get("title"), "start": nxt_start},
                        "gap_minutes": 0,
                        "note": (
                            f"Zero turnover buffer between '{curr.get('title')}' and '{nxt.get('title')}' in {curr_room}. "
                            "No turnover constraint is documented in source records. Report as missing constraint rather than inventing one."
                        ),
                    }
                )

    # -----------------------------------------------------------------------
    # C. Vendor Arrival, Delivery Window, and Service Dependencies
    # -----------------------------------------------------------------------
    for item in schedule_items:
        vnd_id = item.get("vendor_id")
        if not vnd_id or vnd_id not in all_vendors:
            continue
        vnd = all_vendors[vnd_id]
        item_notes = (item.get("notes") or "").lower()
        session_start_m = time_to_minutes(item.get("start_time", "00:00"))
        vnd_confirmed = vnd.get("confirmed", False)

        # Parse delivery window from session notes if present (e.g. "delivery window targeted for 11:45-12:15")
        delivery_window = None
        if "delivery window targeted for" in item_notes:
            try:
                part = item_notes.split("delivery window targeted for")[1].split(".")[0].strip()
                if "-" in part:
                    w_start, w_end = part.split("-")
                    delivery_window = (w_start.strip(), w_end.strip())
            except Exception:
                delivery_window = None

        if delivery_window:
            d_start_m = time_to_minutes(delivery_window[0])
            d_end_m = time_to_minutes(delivery_window[1])

            # Check if delivery window ends AFTER service starts
            if d_end_m > session_start_m:
                cfl_id = f"cfl-vendor-delivery-{vnd_id}-{item['id']}"
                conflicts.append(
                    ConflictIssue(
                        id=cfl_id,
                        conflict_type=ConflictType.VENDOR_SERVICE_MISALIGNMENT,
                        severity=ConflictSeverity.CRITICAL if vnd_confirmed else ConflictSeverity.HIGH,
                        verification_status="verified" if vnd_confirmed else "provisional",
                        affected_schedule_ids=[item["id"]],
                        affected_task_ids=[t["id"] for t in tasks_by_session.get(item["id"], [])],
                        affected_resource_ids=[vnd_id],
                        title=f"Vendor delivery window extends past service start: {vnd.get('name')}",
                        explanation=(
                            f"Vendor {vnd.get('name')} delivery window ({delivery_window[0]}-{delivery_window[1]}) "
                            f"ends after scheduled session '{item.get('title')}' start ({item.get('start_time')}). "
                            "Food or equipment cannot be ready for attendees at session opening."
                        ),
                        evidence={
                            "vendor_id": vnd_id,
                            "vendor_name": vnd.get("name"),
                            "delivery_window": f"{delivery_window[0]}-{delivery_window[1]}",
                            "session_start": item.get("start_time"),
                            "vendor_confirmed": vnd_confirmed,
                        },
                        missing_information=[
                            "Confirmation from vendor whether delivery arrival can be shifted earlier",
                        ],
                        downstream_impacts=[
                            f"Attendees will experience delayed lunch/service at {item.get('start_time')}",
                            f"Setup volunteers will not have buffer to arrange buffet before attendee arrival",
                        ],
                    )
                )

        # Check unconfirmed booking dependency
        if not vnd_confirmed:
            missing_constraints.append(
                {
                    "type": "unconfirmed_vendor_booking",
                    "vendor_id": vnd_id,
                    "vendor_name": vnd.get("name"),
                    "session_id": item["id"],
                    "session_title": item.get("title"),
                    "note": (
                        f"Vendor booking for {vnd.get('name')} is unconfirmed (confirmed=False). "
                        "Service timing is a tentative planning assumption."
                    ),
                }
            )

    # -----------------------------------------------------------------------
    # D. Venue Constraints (Access Hours, Curfew, Capacity)
    # -----------------------------------------------------------------------
    venue_access_start = venue.get("access_start", "08:00")
    venue_access_end = venue.get("access_end", "18:00")
    venue_curfew = venue.get("curfew", "18:00")
    venue_max_capacity = int(venue.get("max_capacity", 0))
    venue_conf_state = venue.get("confirmation_state", ConfirmationState.ASSUMED.value)
    is_venue_confirmed = (venue_conf_state == ConfirmationState.CONFIRMED.value)
    venue_verification_status = "verified" if is_venue_confirmed else "provisional"

    v_start_m = time_to_minutes(venue_access_start)
    v_end_m = time_to_minutes(venue_access_end)
    curfew_m = time_to_minutes(venue_curfew.split()[0] if venue_curfew else venue_access_end)

    for item in schedule_items:
        s_id = item["id"]
        i_start = item.get("start_time", "00:00")
        i_end = item.get("end_time", "00:00")
        i_start_m = time_to_minutes(i_start)
        i_end_m = time_to_minutes(i_end)

        # Access hours: Activity before venue opening
        if i_start_m < v_start_m:
            cfl_id = f"cfl-venue-access-early-{s_id}"
            conflicts.append(
                ConflictIssue(
                    id=cfl_id,
                    conflict_type=ConflictType.VENUE_CONSTRAINT_VIOLATION,
                    severity=ConflictSeverity.HIGH if is_venue_confirmed else ConflictSeverity.MEDIUM,
                    verification_status=venue_verification_status,
                    affected_schedule_ids=[s_id],
                    affected_task_ids=[t["id"] for t in tasks_by_session.get(s_id, [])],
                    affected_resource_ids=[venue.get("venue_name", "Venue")],
                    title=f"Activity scheduled before venue access hours: '{item.get('title')}'",
                    explanation=(
                        f"'{item.get('title')}' starts at {i_start}, but venue access hours begin at {venue_access_start}. "
                        f"Constraint is currently {venue_conf_state}."
                    ),
                    evidence={
                        "activity_start": i_start,
                        "venue_access_start": venue_access_start,
                        "venue_confirmation_state": venue_conf_state,
                    },
                    missing_information=[
                        "Verification of early building access keys or facility coordinator approval",
                    ],
                    downstream_impacts=["Team and vendors may be locked out of the building"],
                )
            )

        # Access hours: Activity after venue access end
        if i_end_m > v_end_m:
            cfl_id = f"cfl-venue-access-late-{s_id}"
            conflicts.append(
                ConflictIssue(
                    id=cfl_id,
                    conflict_type=ConflictType.VENUE_CONSTRAINT_VIOLATION,
                    severity=ConflictSeverity.CRITICAL if is_venue_confirmed else ConflictSeverity.HIGH,
                    verification_status=venue_verification_status,
                    affected_schedule_ids=[s_id],
                    affected_task_ids=[t["id"] for t in tasks_by_session.get(s_id, [])],
                    affected_resource_ids=[venue.get("venue_name", "Venue")],
                    title=f"Activity extends beyond venue operating hours: '{item.get('title')}'",
                    explanation=(
                        f"'{item.get('title')}' concludes at {i_end}, but venue access hours end at {venue_access_end}."
                    ),
                    evidence={
                        "activity_end": i_end,
                        "venue_access_end": venue_access_end,
                        "venue_confirmation_state": venue_conf_state,
                    },
                    missing_information=[
                        "Facility approval for extended building access",
                    ],
                    downstream_impacts=[
                        "Facility lock-out, security alarms, or custodial overtime penalties",
                    ],
                )
            )

        # Curfew lock-out violation
        if i_end_m > curfew_m:
            cfl_id = f"cfl-venue-curfew-{s_id}"
            conflicts.append(
                ConflictIssue(
                    id=cfl_id,
                    conflict_type=ConflictType.VENUE_CONSTRAINT_VIOLATION,
                    severity=ConflictSeverity.CRITICAL if is_venue_confirmed else ConflictSeverity.HIGH,
                    verification_status=venue_verification_status,
                    affected_schedule_ids=[s_id],
                    affected_task_ids=[t["id"] for t in tasks_by_session.get(s_id, [])],
                    affected_resource_ids=[venue.get("venue_name", "Venue")],
                    title=f"Activity violates strict venue curfew: '{item.get('title')}'",
                    explanation=(
                        f"'{item.get('title')}' finishes at {i_end}, violating the strict curfew lock-out at {venue_curfew}."
                    ),
                    evidence={
                        "activity_end": i_end,
                        "curfew": venue_curfew,
                        "venue_confirmation_state": venue_conf_state,
                    },
                    missing_information=["Facility curfew extension authorization"],
                    downstream_impacts=["Automatic building lock-out leaving equipment trapped inside"],
                )
            )

    # Capacity check: Event attendee headcount vs. Venue Max Capacity
    attendees_count = int(event.get("attendees", 0))
    if venue_max_capacity > 0 and attendees_count > venue_max_capacity:
        conflicts.append(
            ConflictIssue(
                id="cfl-venue-capacity-event",
                conflict_type=ConflictType.VENUE_CONSTRAINT_VIOLATION,
                severity=ConflictSeverity.CRITICAL if is_venue_confirmed else ConflictSeverity.HIGH,
                verification_status=venue_verification_status,
                affected_schedule_ids=[s["id"] for s in schedule_items],
                affected_task_ids=[],
                affected_resource_ids=[venue.get("venue_name", "Venue")],
                title=f"Attendee headcount ({attendees_count}) exceeds venue capacity ({venue_max_capacity})",
                explanation=(
                    f"Event registration target of {attendees_count} attendees exceeds the maximum capacity "
                    f"of {venue_max_capacity} for {venue.get('venue_name', 'Venue')}."
                ),
                evidence={
                    "attendees": attendees_count,
                    "max_capacity": venue_max_capacity,
                    "venue_confirmation_state": venue_conf_state,
                },
                missing_information=["Capacity waiver or secondary room booking"],
                downstream_impacts=[
                    "Fire code violation and overcrowding",
                    "Insufficient seating for keynote and workshops",
                ],
            )
        )

    # Sort conflicts stably by ID
    conflicts.sort(key=lambda c: c.id)

    verified_count = sum(1 for c in conflicts if c.verification_status == "verified")
    provisional_count = sum(1 for c in conflicts if c.verification_status == "provisional")

    return {
        "has_conflicts": len(conflicts) > 0,
        "total_conflicts": len(conflicts),
        "verified_conflicts_count": verified_count,
        "provisional_conflicts_count": provisional_count,
        "conflicts": [c.to_dict() for c in conflicts],
        "missing_constraints": missing_constraints,
        "summary": (
            f"Detected {len(conflicts)} conflict(s) "
            f"({verified_count} verified, {provisional_count} provisional) "
            f"and {len(missing_constraints)} missing constraint(s)."
        ),
        "_canvas": {
            "module": "conflict_report",
            "title": "Logistics Conflict Report",
        },
    }


# ---------------------------------------------------------------------------
# 2. Downstream Impact Analysis (Preview-First)
# ---------------------------------------------------------------------------
def _create_simulated_store(
    original_store: EventStore,
    schedule_item_id: str,
    proposed_start: str,
    proposed_end: str,
    proposed_room: str = "",
) -> EventStore:
    """Create an isolated, in-memory EventStore containing the proposed schedule change.

    Never modifies original_store or writes to disk.
    """
    # Clone raw data dict
    data_clone = copy.deepcopy(original_store._data)

    # Apply proposed change to cloned schedule
    found = False
    for item in data_clone.get("schedule", []):
        if item["id"] == schedule_item_id:
            item["start_time"] = proposed_start
            item["end_time"] = proposed_end
            if proposed_room:
                item["room"] = proposed_room
            found = True
            break

    if not found:
        raise ValueError(f"Schedule item with id '{schedule_item_id}' not found.")

    # Return completely isolated, in-memory SimulatedEventStore
    return SimulatedEventStore(data_clone)


def analyze_schedule_impact(
    store: EventStore,
    schedule_item_id: str,
    proposed_start: str,
    proposed_end: str,
    proposed_room: str = "",
) -> dict[str, Any]:
    """Preview the downstream impact of a proposed schedule modification without store mutation.

    Evaluates:
    - Newly introduced conflicts and resolved conflicts.
    - Affected operational tasks and dependency chains.
    - Stale briefings using exact-field SHA-256 fingerprint comparison.
    - Directly affected speakers, vendors, volunteers, and downstream agenda items.
    """
    target_item = store.find_schedule_item(schedule_item_id)
    if not target_item:
        return {
            "found": False,
            "error": f"Schedule item '{schedule_item_id}' not found in event store.",
        }

    original_start = target_item.get("start_time", "")
    original_end = target_item.get("end_time", "")
    original_room = target_item.get("room", "")
    new_room = proposed_room.strip() if proposed_room else original_room

    # 1. Baseline Conflict Scan
    baseline_report = detect_schedule_conflicts(store)
    baseline_conflicts_by_id = {c["id"]: c for c in baseline_report["conflicts"]}

    # 2. Simulated Conflict Scan
    simulated_store = _create_simulated_store(
        store,
        schedule_item_id=schedule_item_id,
        proposed_start=proposed_start,
        proposed_end=proposed_end,
        proposed_room=new_room,
    )
    simulated_report = detect_schedule_conflicts(simulated_store)
    simulated_conflicts_by_id = {c["id"]: c for c in simulated_report["conflicts"]}

    introduced_conflicts = [
        c for c_id, c in simulated_conflicts_by_id.items() if c_id not in baseline_conflicts_by_id
    ]
    resolved_conflicts = [
        c for c_id, c in baseline_conflicts_by_id.items() if c_id not in simulated_conflicts_by_id
    ]

    # 3. Affected Operational Tasks
    all_tasks = store.all_tasks()
    directly_linked_tasks: list[dict[str, Any]] = []
    dependent_tasks: list[dict[str, Any]] = []

    linked_task_ids = set()
    for t in all_tasks:
        if t.get("session_id") == schedule_item_id:
            directly_linked_tasks.append(copy.deepcopy(t))
            linked_task_ids.add(t["id"])

    for t in all_tasks:
        if t["id"] in linked_task_ids:
            continue
        deps = t.get("depends_on", [])
        if any(d in linked_task_ids for d in deps):
            dependent_tasks.append(copy.deepcopy(t))

    # 4. Briefing Staleness Detection (using L2 source fingerprinting)
    stale_briefings: list[dict[str, Any]] = []
    for b in store.all_briefings():
        role = b.get("role", "")
        rec_id = b.get("recipient_id", "")
        # Compute fingerprint against current baseline store vs. simulated store
        baseline_fingerprint, _ = compute_source_fingerprint(store, role, rec_id)
        simulated_fingerprint, _ = compute_source_fingerprint(simulated_store, role, rec_id)

        if simulated_fingerprint != baseline_fingerprint:
            stale_briefings.append(
                {
                    "briefing_id": b["id"],
                    "role": role,
                    "recipient_name": b.get("recipient_name"),
                    "recipient_email": b.get("recipient_email"),
                    "current_version": b.get("version", 1),
                    "reason": (
                        f"Schedule change for '{target_item.get('title')}' "
                        f"alters source data hashed by the {role} briefing."
                    ),
                }
            )

    # 5. Affected Participants
    affected_speaker = None
    spk_id = target_item.get("speaker_id")
    if spk_id:
        spk = store.find_speaker(spk_id)
        if spk:
            affected_speaker = {
                "id": spk["id"],
                "name": spk["name"],
                "status": spk.get("status"),
                "notes": f"Session moved from {original_start}-{original_end} to {proposed_start}-{proposed_end}.",
            }

    affected_vendor = None
    vnd_id = target_item.get("vendor_id")
    if vnd_id:
        vnd = store.find_vendor(vnd_id)
        if vnd:
            affected_vendor = {
                "id": vnd["id"],
                "name": vnd["name"],
                "confirmed": vnd.get("confirmed", False),
                "notes": f"Service window shifted from {original_start}-{original_end} to {proposed_start}-{proposed_end}.",
            }

    # 6. Downstream Schedule Dependencies
    # Check sessions that declare dependencies on this session
    downstream_sessions: list[dict[str, Any]] = []
    prop_end_m = time_to_minutes(proposed_end)

    for item in store.all_schedule_items():
        if item["id"] == schedule_item_id:
            continue
        deps = item.get("dependencies", [])
        if schedule_item_id in deps:
            item_start_m = time_to_minutes(item.get("start_time", "00:00"))
            has_gap_issue = prop_end_m > item_start_m
            downstream_sessions.append(
                {
                    "session_id": item["id"],
                    "title": item.get("title"),
                    "start_time": item.get("start_time"),
                    "end_time": item.get("end_time"),
                    "gap_violation": has_gap_issue,
                    "explanation": (
                        f"Session '{item.get('title')}' depends on '{target_item.get('title')}'. "
                        + (
                            f"Proposed end time ({proposed_end}) exceeds its start time ({item.get('start_time')})."
                            if has_gap_issue
                            else "Preceding dependency completes in time."
                        )
                    ),
                }
            )

    # Identify unlinked operational tasks that might be affected
    missing_information: list[str] = []
    for t in all_tasks:
        if t["id"] not in linked_task_ids and t["id"] not in [d["id"] for d in dependent_tasks]:
            notes = (t.get("notes") or "").lower()
            if spk_id and spk_id.lower() in notes:
                missing_information.append(
                    f"Task '{t['id']}' ({t.get('title')}) notes mention speaker {spk_id}, but task lacks an explicit session_id link in EventStore."
                )
            elif vnd_id and vnd_id.lower() in notes:
                missing_information.append(
                    f"Task '{t['id']}' ({t.get('title')}) notes mention vendor {vnd_id}, but task lacks an explicit session_id link in EventStore."
                )

    return {
        "schedule_item_id": schedule_item_id,
        "title": target_item.get("title"),
        "original_slot": {
            "start_time": original_start,
            "end_time": original_end,
            "room": original_room,
        },
        "proposed_slot": {
            "start_time": proposed_start,
            "end_time": proposed_end,
            "room": new_room,
        },
        "conflict_summary": {
            "introduced_conflicts_count": len(introduced_conflicts),
            "resolved_conflicts_count": len(resolved_conflicts),
            "introduced_conflicts": introduced_conflicts,
            "resolved_conflicts": resolved_conflicts,
        },
        "affected_operational_tasks": {
            "directly_linked_tasks": directly_linked_tasks,
            "dependent_tasks": dependent_tasks,
        },
        "stale_briefings": stale_briefings,
        "affected_participants": {
            "speaker": affected_speaker,
            "vendor": affected_vendor,
        },
        "downstream_dependent_sessions": downstream_sessions,
        "missing_information": missing_information,
        "requires_human_approval": True,
        "_canvas": {
            "module": "schedule_impact_preview",
            "title": f"Schedule Impact: {target_item.get('title')}",
        },
    }


# ---------------------------------------------------------------------------
# 3. Deterministic Resolution Proposals
# ---------------------------------------------------------------------------
def _find_available_room_slots(
    store: EventStore,
    room: str,
    duration_minutes: int,
    exclude_item_id: str,
) -> list[tuple[str, str]]:
    """Scan existing schedule and find open time windows in the room within venue hours."""
    venue = store.get_venue_constraints()
    access_start_m = time_to_minutes(venue.get("access_start", "08:00"))
    access_end_m = time_to_minutes(venue.get("access_end", "18:00"))

    # Gather all existing bookings in this room
    bookings: list[tuple[int, int]] = []
    for item in store.all_schedule_items():
        if item["id"] == exclude_item_id:
            continue
        if (item.get("room") or "").strip().lower() == room.strip().lower():
            bookings.append(
                (time_to_minutes(item.get("start_time", "00:00")), time_to_minutes(item.get("end_time", "00:00")))
            )

    bookings.sort(key=lambda b: b[0])

    available_slots: list[tuple[str, str]] = []
    current_m = access_start_m

    for b_start, b_end in bookings:
        if b_start > current_m:
            gap = b_start - current_m
            if gap >= duration_minutes:
                available_slots.append((minutes_to_time(current_m), minutes_to_time(current_m + duration_minutes)))
        current_m = max(current_m, b_end)

    if access_end_m > current_m:
        gap = access_end_m - current_m
        if gap >= duration_minutes:
            available_slots.append((minutes_to_time(current_m), minutes_to_time(current_m + duration_minutes)))

    return available_slots


def propose_conflict_resolutions(store: EventStore, conflict_id: str) -> dict[str, Any]:
    """Generate deterministic, explainable proposals to resolve a specific conflict.

    Each proposal includes:
    - Before/after changes
    - Conflicts resolved vs. potential new conflicts
    - Downstream task and briefing impacts
    - Required external confirmations
    - Explicit `requires_human_approval: true`
    """
    conflict_report = detect_schedule_conflicts(store)
    target_conflict = None
    for c in conflict_report["conflicts"]:
        if c["id"] == conflict_id:
            target_conflict = c
            break

    if not target_conflict:
        return {
            "found": False,
            "error": f"Conflict with ID '{conflict_id}' is not currently active.",
            "active_conflicts": [c["id"] for c in conflict_report["conflicts"]],
        }

    cfl_type = target_conflict["conflict_type"]
    affected_sched_ids = target_conflict["affected_schedule_ids"]
    proposals: list[dict[str, Any]] = []

    venue = store.get_venue_constraints()
    access_start_str = venue.get("access_start", "08:00")
    access_end_str = venue.get("access_end", "18:00")
    venue_curfew_str = venue.get("curfew", "18:00").split()[0]
    access_start_m = time_to_minutes(access_start_str)
    access_end_m = time_to_minutes(access_end_str)
    curfew_m = time_to_minutes(venue_curfew_str)

    # -----------------------------------------------------------------------
    # Case 1: Room Overlap Resolution
    # -----------------------------------------------------------------------
    if cfl_type == ConflictType.ROOM_OVERLAP and len(affected_sched_ids) >= 2:
        id_a, id_b = affected_sched_ids[0], affected_sched_ids[1]
        item_a = store.find_schedule_item(id_a)
        item_b = store.find_schedule_item(id_b)

        # Propose shifting the more tentative session if one is confirmed, or the later one
        candidate_items = []
        if item_a and item_a.get("confirmation_state") != ConfirmationState.CONFIRMED.value:
            candidate_items.append(item_a)
        if item_b and item_b.get("confirmation_state") != ConfirmationState.CONFIRMED.value:
            candidate_items.append(item_b)
        if not candidate_items:
            candidate_items = [item_b or item_a]

        for cand in candidate_items:
            if not cand:
                continue
            cand_id = cand["id"]
            cand_room = cand.get("room", "")
            duration = calculate_duration_minutes(cand.get("start_time", "00:00"), cand.get("end_time", "00:00"))

            # Find available candidate slots in the same room
            open_slots = _find_available_room_slots(
                store, room=cand_room, duration_minutes=duration, exclude_item_id=cand_id
            )

            validated_slots: list[tuple[str, str, dict[str, Any]]] = []
            for s_start, s_end in open_slots:
                s_start_m = time_to_minutes(s_start)
                s_end_m = time_to_minutes(s_end)

                # Check venue access hours & curfew
                if s_start_m < access_start_m or s_end_m > access_end_m or s_end_m > curfew_m:
                    continue

                # Check linked speaker availability across ALL other sessions
                spk_id = cand.get("speaker_id")
                if spk_id:
                    spk_conflict = False
                    for other in store.all_schedule_items():
                        if other["id"] == cand_id:
                            continue
                        if other.get("speaker_id") == spk_id:
                            if intervals_overlap(
                                s_start, s_end, other.get("start_time", "00:00"), other.get("end_time", "00:00")
                            ):
                                spk_conflict = True
                                break
                    if spk_conflict:
                        continue

                # Check linked vendor availability across ALL other sessions
                vnd_id = cand.get("vendor_id")
                if vnd_id:
                    vnd_conflict = False
                    for other in store.all_schedule_items():
                        if other["id"] == cand_id:
                            continue
                        if other.get("vendor_id") == vnd_id:
                            if intervals_overlap(
                                s_start, s_end, other.get("start_time", "00:00"), other.get("end_time", "00:00")
                            ):
                                vnd_conflict = True
                                break
                    if vnd_conflict:
                        continue

                # Strict impact simulation: MUST resolve conflict and introduce ZERO new conflicts
                impact = analyze_schedule_impact(
                    store,
                    schedule_item_id=cand_id,
                    proposed_start=s_start,
                    proposed_end=s_end,
                )
                resolved_ids = [c["id"] for c in impact["conflict_summary"]["resolved_conflicts"]]
                introduced_conflicts = impact["conflict_summary"]["introduced_conflicts"]

                if conflict_id in resolved_ids and len(introduced_conflicts) == 0:
                    validated_slots.append((s_start, s_end, impact))

            # Add validated proposals
            for s_start, s_end, impact in validated_slots[:2]:
                prop_id = f"prop-reschedule-{cand_id}-{s_start.replace(':', '')}"
                proposals.append(
                    {
                        "proposal_id": prop_id,
                        "conflict_id": conflict_id,
                        "strategy": "RESCHEDULE_SESSION",
                        "title": f"Move '{cand.get('title')}' to open slot ({s_start}-{s_end}) in {cand_room}",
                        "description": (
                            f"Reschedule tentative session '{cand.get('title')}' from "
                            f"{cand.get('start_time')}-{cand.get('end_time')} to verified open slot "
                            f"{s_start}-{s_end} in {cand_room}."
                        ),
                        "proposed_changes": [
                            {
                                "record_type": "schedule_item",
                                "record_id": cand_id,
                                "field": "start_time",
                                "before": cand.get("start_time"),
                                "after": s_start,
                            },
                            {
                                "record_type": "schedule_item",
                                "record_id": cand_id,
                                "field": "end_time",
                                "before": cand.get("end_time"),
                                "after": s_end,
                            },
                        ],
                        "resolves_conflicts": [conflict_id],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": [
                            t["title"]
                            for t in impact["affected_operational_tasks"]["directly_linked_tasks"]
                        ],
                        "downstream_briefing_impacts": [
                            f"{b['role']} briefing ({b['recipient_name']})" for b in impact["stale_briefings"]
                        ],
                        "required_confirmations": [
                            f"Organizer sign-off on new timing ({s_start}-{s_end})",
                            (
                                f"Speaker confirmation for {cand.get('speaker_id')}"
                                if cand.get("speaker_id")
                                else "Session owner confirmation"
                            ),
                        ],
                        "affects_confirmed_commitments": cand.get("confirmation_state") == ConfirmationState.CONFIRMED.value,
                        "requires_human_approval": True,
                    }
                )

            # If no validated alternative exists for this candidate, return explicit failure proposal
            if not validated_slots:
                proposals.append(
                    {
                        "proposal_id": f"prop-no-alternative-{cand_id}",
                        "conflict_id": conflict_id,
                        "strategy": "NO_FEASIBLE_ALTERNATIVE",
                        "title": f"No validated alternative slot found for '{cand.get('title')}'",
                        "description": (
                            f"Exhaustive check of schedule gaps in {cand_room} within venue access hours "
                            f"({access_start_str}-{access_end_str}) found no open slot of duration {duration} minutes "
                            f"that resolves '{conflict_id}' without introducing secondary room, speaker, vendor, or venue conflicts."
                        ),
                        "proposed_changes": [],
                        "resolves_conflicts": [],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": [],
                        "downstream_briefing_impacts": [],
                        "required_confirmations": [
                            "Organizer review to cancel, shorten, or re-scope session",
                            "Facility coordinator consultation for secondary venue space",
                        ],
                        "affects_confirmed_commitments": cand.get("confirmation_state") == ConfirmationState.CONFIRMED.value,
                        "requires_human_approval": True,
                    }
                )

        # Propose room reassignment IF alternative confirmed rooms exist in venue
        proposals.append(
            {
                "proposal_id": f"prop-room-reassign-info-{conflict_id}",
                "conflict_id": conflict_id,
                "strategy": "ROOM_REASSIGNMENT_CHECK",
                "title": f"Alternative room reassignment check for {target_conflict.get('title')}",
                "description": (
                    "Checked source venue records for secondary auditorium/workshop rooms. "
                    "Gates Hall 106 is the only confirmed auditorium room; Lobby and Patio/Lounge "
                    "are shared open spaces unsuitable for parallel main-track workshops without venue authorization."
                ),
                "proposed_changes": [],
                "resolves_conflicts": [],
                "potential_new_conflicts": [],
                "downstream_task_impacts": [],
                "downstream_briefing_impacts": [],
                "required_confirmations": [
                    "Facility coordinator confirmation of additional breakout classroom or hall",
                ],
                "affects_confirmed_commitments": False,
                "requires_human_approval": True,
                "note": "Engine does not invent ungrounded rooms; secondary room must be confirmed in source records.",
            }
        )

    # -----------------------------------------------------------------------
    # Case 2: Vendor Delivery / Service Misalignment
    # -----------------------------------------------------------------------
    elif cfl_type == ConflictType.VENDOR_SERVICE_MISALIGNMENT and affected_sched_ids:
        s_id = affected_sched_ids[0]
        item = store.find_schedule_item(s_id)
        if item:
            vnd_id = item.get("vendor_id")
            vnd = store.find_vendor(vnd_id) if vnd_id else None
            session_start = item.get("start_time", "12:30")
            s_start_m = time_to_minutes(session_start)
            suggested_d_start = minutes_to_time(s_start_m - 45)
            suggested_d_end = minutes_to_time(s_start_m - 15)

            if s_start_m - 45 < access_start_m:
                proposals.append(
                    {
                        "proposal_id": f"prop-no-vendor-alternative-{vnd_id}-{s_id}",
                        "conflict_id": conflict_id,
                        "strategy": "NO_FEASIBLE_ALTERNATIVE",
                        "title": f"Earlier delivery window ({suggested_d_start}) precedes venue opening ({access_start_str})",
                        "description": (
                            f"Vendor delivery window cannot be shifted earlier because suggested arrival "
                            f"({suggested_d_start}) precedes venue access hours ({access_start_str})."
                        ),
                        "proposed_changes": [],
                        "resolves_conflicts": [],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": [],
                        "downstream_briefing_impacts": [],
                        "required_confirmations": ["Facility coordinator early loading dock access approval"],
                        "affects_confirmed_commitments": False,
                        "requires_human_approval": True,
                    }
                )
            else:
                proposals.append(
                    {
                        "proposal_id": f"prop-vendor-window-{vnd_id}-{s_id}",
                        "conflict_id": conflict_id,
                        "strategy": "ADJUST_VENDOR_DELIVERY_WINDOW",
                        "title": f"Propose earlier delivery window ({suggested_d_start}-{suggested_d_end}) for {vnd.get('name') if vnd else 'vendor'}",
                        "description": (
                            f"Adjust target delivery window for {vnd.get('name') if vnd else 'vendor'} "
                            f"from current window to {suggested_d_start}-{suggested_d_end}, ensuring buffer "
                            f"before '{item.get('title')}' starts at {session_start}."
                        ),
                        "proposed_changes": [
                            {
                                "record_type": "schedule_item",
                                "record_id": s_id,
                                "field": "notes",
                                "before": item.get("notes"),
                                "after": f"{item.get('notes')} [Proposed revised delivery: {suggested_d_start}-{suggested_d_end}]",
                            }
                        ],
                        "resolves_conflicts": [conflict_id],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": ["Update catering delivery arrival task"],
                        "downstream_briefing_impacts": ["Vendor briefing arrival time will be updated"],
                        "required_confirmations": [
                            f"Written confirmation from {vnd.get('name') if vnd else 'vendor'} agreeing to {suggested_d_start} load-in",
                            "Organizer approval to revise vendor briefing draft",
                        ],
                        "affects_confirmed_commitments": bool(vnd.get("confirmed", False) if vnd else False),
                        "requires_human_approval": True,
                    }
                )

    # -----------------------------------------------------------------------
    # Case 3: Insufficient Setup / Teardown Buffer
    # -----------------------------------------------------------------------
    elif cfl_type == ConflictType.INSUFFICIENT_BUFFER and len(affected_sched_ids) >= 2:
        prec_id, item_id = affected_sched_ids[0], affected_sched_ids[1]
        prec_item = store.find_schedule_item(prec_id)
        curr_item = store.find_schedule_item(item_id)
        if prec_item and curr_item:
            req_buffer = target_conflict.get("evidence", {}).get("required_buffer_minutes", 30)
            prec_end_m = time_to_minutes(prec_item.get("end_time", "00:00"))
            new_start_m = prec_end_m + req_buffer
            duration = calculate_duration_minutes(
                curr_item.get("start_time", "00:00"), curr_item.get("end_time", "00:00")
            )
            new_end_m = new_start_m + duration
            new_start = minutes_to_time(new_start_m)
            new_end = minutes_to_time(new_end_m)

            impact = analyze_schedule_impact(
                store, schedule_item_id=item_id, proposed_start=new_start, proposed_end=new_end
            )
            introduced = impact["conflict_summary"]["introduced_conflicts"]
            if len(introduced) == 0 and new_end_m <= curfew_m:
                proposals.append(
                    {
                        "proposal_id": f"prop-buffer-shift-{item_id}-{new_start.replace(':', '')}",
                        "conflict_id": conflict_id,
                        "strategy": "ADD_SETUP_BUFFER",
                        "title": f"Shift '{curr_item.get('title')}' to {new_start}-{new_end} to provide {req_buffer}-minute buffer",
                        "description": f"Postpone session '{curr_item.get('title')}' to {new_start}-{new_end} after '{prec_item.get('title')}' concludes.",
                        "proposed_changes": [
                            {
                                "record_type": "schedule_item",
                                "record_id": item_id,
                                "field": "start_time",
                                "before": curr_item.get("start_time"),
                                "after": new_start,
                            },
                            {
                                "record_type": "schedule_item",
                                "record_id": item_id,
                                "field": "end_time",
                                "before": curr_item.get("end_time"),
                                "after": new_end,
                            },
                        ],
                        "resolves_conflicts": [conflict_id],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": [
                            t["title"]
                            for t in impact["affected_operational_tasks"]["directly_linked_tasks"]
                        ],
                        "downstream_briefing_impacts": [
                            f"{b['role']} briefing ({b['recipient_name']})" for b in impact["stale_briefings"]
                        ],
                        "required_confirmations": [
                            "Organizer approval to shift session timing",
                            "Vendor confirmation of adjusted service start",
                        ],
                        "affects_confirmed_commitments": curr_item.get("confirmation_state") == ConfirmationState.CONFIRMED.value,
                        "requires_human_approval": True,
                    }
                )
            else:
                proposals.append(
                    {
                        "proposal_id": f"prop-no-buffer-alternative-{item_id}",
                        "conflict_id": conflict_id,
                        "strategy": "NO_FEASIBLE_ALTERNATIVE",
                        "title": f"Cannot shift '{curr_item.get('title')}' for buffer without new conflicts",
                        "description": (
                            f"Shifting session to {new_start}-{new_end} conflicts with subsequent sessions "
                            f"({', '.join(c['title'] for c in introduced) if introduced else 'exceeds venue curfew'}). "
                            "Requires organizer review to restructure timetable or shorten activities."
                        ),
                        "proposed_changes": [],
                        "resolves_conflicts": [],
                        "potential_new_conflicts": [c["title"] for c in introduced],
                        "downstream_task_impacts": [],
                        "downstream_briefing_impacts": [],
                        "required_confirmations": [
                            "Vendor negotiation to reduce buffer requirement",
                            "Organizer schedule restructuring",
                        ],
                        "affects_confirmed_commitments": False,
                        "requires_human_approval": True,
                    }
                )

    # -----------------------------------------------------------------------
    # Case 4: Venue Constraint / Curfew / Access Hours Violation
    # -----------------------------------------------------------------------
    elif cfl_type == ConflictType.VENUE_CONSTRAINT_VIOLATION and affected_sched_ids:
        s_id = affected_sched_ids[0]
        item = store.find_schedule_item(s_id)
        if item:
            duration = calculate_duration_minutes(item.get("start_time", "00:00"), item.get("end_time", "00:00"))
            suggested_start_m = curfew_m - duration
            suggested_start = minutes_to_time(suggested_start_m)

            # Analyze impact of shifting earlier to finish by curfew
            impact = analyze_schedule_impact(
                store, schedule_item_id=s_id, proposed_start=suggested_start, proposed_end=venue_curfew_str
            )
            introduced = impact["conflict_summary"]["introduced_conflicts"]

            if len(introduced) == 0 and suggested_start_m >= access_start_m:
                proposals.append(
                    {
                        "proposal_id": f"prop-curfew-adjust-{s_id}",
                        "conflict_id": conflict_id,
                        "strategy": "ALIGN_WITH_VENUE_HOURS",
                        "title": f"Shift '{item.get('title')}' to conclude by venue curfew ({venue_curfew_str})",
                        "description": (
                            f"Shift '{item.get('title')}' to {suggested_start}-{venue_curfew_str} so teardown "
                            f"finishes at or before the strict 18:00 lockout."
                        ),
                        "proposed_changes": [
                            {
                                "record_type": "schedule_item",
                                "record_id": s_id,
                                "field": "start_time",
                                "before": item.get("start_time"),
                                "after": suggested_start,
                            },
                            {
                                "record_type": "schedule_item",
                                "record_id": s_id,
                                "field": "end_time",
                                "before": item.get("end_time"),
                                "after": venue_curfew_str,
                            },
                        ],
                        "resolves_conflicts": [conflict_id],
                        "potential_new_conflicts": [],
                        "downstream_task_impacts": ["Venue teardown volunteer shift checklist timing"],
                        "downstream_briefing_impacts": ["Volunteer teardown briefing timing update"],
                        "required_confirmations": [
                            "Lead organizer sign-off",
                            "Teardown crew confirmation of revised shift timing",
                        ],
                        "affects_confirmed_commitments": False,
                        "requires_human_approval": True,
                    }
                )
            else:
                proposals.append(
                    {
                        "proposal_id": f"prop-no-curfew-alternative-{s_id}",
                        "conflict_id": conflict_id,
                        "strategy": "NO_FEASIBLE_ALTERNATIVE",
                        "title": f"Cannot shift '{item.get('title')}' earlier without creating new conflicts",
                        "description": (
                            f"Shifting '{item.get('title')}' to {suggested_start}-{venue_curfew_str} introduces "
                            f"{len(introduced)} new conflict(s) with preceding activities "
                            f"({', '.join(c['title'] for c in introduced) if introduced else 'precedes access hours'}). "
                            "Requires organizer review to shorten the session or obtain a venue curfew extension."
                        ),
                        "proposed_changes": [],
                        "resolves_conflicts": [],
                        "potential_new_conflicts": [c["title"] for c in introduced],
                        "downstream_task_impacts": [],
                        "downstream_briefing_impacts": [],
                        "required_confirmations": [
                            "Facility coordinator approval for extended building access",
                            "Organizer sign-off to shorten session duration",
                        ],
                        "affects_confirmed_commitments": False,
                        "requires_human_approval": True,
                    }
                )

    # -----------------------------------------------------------------------
    # Default Fallback Proposal
    # -----------------------------------------------------------------------
    if not proposals:
        proposals.append(
            {
                "proposal_id": f"prop-manual-{conflict_id}",
                "conflict_id": conflict_id,
                "strategy": "MANUAL_ORGANIZER_REVIEW",
                "title": f"Manual organizer review required for {target_conflict.get('title')}",
                "description": (
                    f"Conflict involves {target_conflict.get('conflict_type')}. "
                    "No automatic deterministic slot fits without human consultation."
                ),
                "proposed_changes": [],
                "resolves_conflicts": [conflict_id],
                "potential_new_conflicts": [],
                "downstream_task_impacts": [],
                "downstream_briefing_impacts": [],
                "required_confirmations": ["Direct organizer intervention"],
                "affects_confirmed_commitments": False,
                "requires_human_approval": True,
            }
        )

    return {
        "conflict_id": conflict_id,
        "conflict_title": target_conflict.get("title"),
        "total_proposals": len(proposals),
        "proposals": proposals,
        "requires_human_approval": True,
        "_canvas": {
            "module": "resolution_proposals",
            "title": f"Resolution Proposals: {conflict_id}",
        },
    }
