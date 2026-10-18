"""EventStore: Persistent, JSON-backed event operations data store.

Provides durable persistence across MCP server subprocess restarts, normalized
serializable data structures, and atomic file writes.

Maintains 100% backward compatibility with existing mock backend lookups and seed data.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from typing import Any, Optional

# Ensure sibling import works when loaded in isolation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_data import (
    BRIEFINGS,
    EVENT,
    SCHEDULE_ITEMS,
    SPEAKERS,
    SPONSORS,
    TASKS,
    VENDORS,
    VENUE_CONSTRAINTS,
)


# ---------------------------------------------------------------------------
# Normalized Domain Records & Confirmation States
# ---------------------------------------------------------------------------
class ConfirmationState(str, Enum):
    """Status indicating how grounded a record or timing assumption is."""
    CONFIRMED = "confirmed"  # Verified fact, signed contract, or agreed commitment
    TENTATIVE = "tentative"  # Planned or targeted, but pending confirmation
    ASSUMED = "assumed"      # Operational assumption (e.g. standard buffer times)
    PROPOSED = "proposed"    # Under consideration or candidate


@dataclass
class VenueConstraints:
    venue_name: str
    access_start: str
    access_end: str
    max_capacity: int
    av_provisions: list[str] = field(default_factory=list)
    loading_dock_instructions: str = ""
    food_policy: str = ""
    curfew: str = ""
    confirmation_state: str = ConfirmationState.ASSUMED.value
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VenueConstraints:
        return cls(
            venue_name=data.get("venue_name", ""),
            access_start=data.get("access_start", ""),
            access_end=data.get("access_end", ""),
            max_capacity=int(data.get("max_capacity", 0)),
            av_provisions=list(data.get("av_provisions", [])),
            loading_dock_instructions=data.get("loading_dock_instructions", ""),
            food_policy=data.get("food_policy", ""),
            curfew=data.get("curfew", ""),
            confirmation_state=data.get("confirmation_state", ConfirmationState.ASSUMED.value),
            notes=data.get("notes", ""),
        )


@dataclass
class ScheduleItem:
    id: str
    title: str
    start_time: str
    end_time: str
    room: str
    item_type: str
    speaker_id: Optional[str] = None
    vendor_id: Optional[str] = None
    confirmation_state: str = ConfirmationState.TENTATIVE.value
    dependencies: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleItem:
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            room=data.get("room", ""),
            item_type=data.get("item_type", "session"),
            speaker_id=data.get("speaker_id"),
            vendor_id=data.get("vendor_id"),
            confirmation_state=data.get("confirmation_state", ConfirmationState.TENTATIVE.value),
            dependencies=list(data.get("dependencies", [])),
            notes=data.get("notes", ""),
        )


@dataclass
class OperationalTask:
    id: str
    title: str
    owner: str
    status: str
    due_date: str
    depends_on: list[str] = field(default_factory=list)
    notes: str = ""
    category: str = "general"
    confirmation_state: str = ConfirmationState.TENTATIVE.value
    session_id: Optional[str] = None
    confirmation_requirement: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["due"] = self.due_date
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationalTask:
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            owner=data.get("owner", ""),
            status=data.get("status", "open"),
            due_date=data.get("due_date", "") or data.get("due", ""),
            depends_on=list(data.get("depends_on", [])),
            notes=data.get("notes", ""),
            category=data.get("category", "general"),
            confirmation_state=data.get("confirmation_state", ConfirmationState.TENTATIVE.value),
            session_id=data.get("session_id"),
            confirmation_requirement=data.get("confirmation_requirement"),
        )


@dataclass
class Briefing:
    id: str
    role: str
    recipient_id: str
    recipient_name: str
    recipient_email: str
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    session_time: Optional[str] = None
    arrival_time: Optional[str] = None
    room: Optional[str] = None
    av_provisions: Optional[str] = None
    notes: str = ""
    emergency_contact: str = ""
    is_stale: bool = False
    version: int = 1
    confirmation_state: str = ConfirmationState.CONFIRMED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Briefing:
        return cls(
            id=data["id"],
            role=data.get("role", "speaker"),
            recipient_id=data.get("recipient_id", ""),
            recipient_name=data.get("recipient_name", ""),
            recipient_email=data.get("recipient_email", ""),
            session_id=data.get("session_id"),
            session_title=data.get("session_title"),
            session_time=data.get("session_time"),
            arrival_time=data.get("arrival_time"),
            room=data.get("room"),
            av_provisions=data.get("av_provisions"),
            notes=data.get("notes", ""),
            emergency_contact=data.get("emergency_contact", ""),
            is_stale=bool(data.get("is_stale", False)),
            version=int(data.get("version", 1)),
            confirmation_state=data.get("confirmation_state", ConfirmationState.CONFIRMED.value),
        )


# ---------------------------------------------------------------------------
# Persistent Event Store Implementation
# ---------------------------------------------------------------------------
class EventStore:
    """Thread-safe, JSON-backed event store with atomic persistence.

    - Initializes from seed data without modifying existing IDs or schemas.
    - Persists updates atomically via temp file + fsync + atomic rename.
    - Preserves data across MCP subprocess restarts.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        if storage_path is None:
            storage_path = os.environ.get("EVENT_STORE_PATH")
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "event_data.json"
            )
        self.storage_path = os.path.abspath(storage_path)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load()

    # -----------------------------------------------------------------------
    # Persistence & Synchronization
    # -----------------------------------------------------------------------
    def load(self) -> None:
        """Load data from JSON file or initialize with seed data if file doesn't exist."""
        with self._lock:
            if not os.path.exists(self.storage_path):
                self.reset_to_seed()
                return

            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if not isinstance(raw, dict):
                    raise ValueError("Event store file must contain a JSON object")
                self._data = self._ensure_schema(raw)
            except (json.JSONDecodeError, ValueError, OSError):
                # Preserve the corrupted file for investigation rather than silently destroying it
                self._preserve_corrupted_file()
                self.reset_to_seed()

    def _preserve_corrupted_file(self) -> str | None:
        """Preserve a corrupted store file to a timestamped backup before recovery."""
        try:
            if not os.path.exists(self.storage_path) or os.path.getsize(self.storage_path) == 0:
                return None
            dir_name = os.path.dirname(self.storage_path)
            base_name = os.path.basename(self.storage_path)
            timestamp = int(time.time())
            backup_path = os.path.join(dir_name, f"{base_name}.corrupted.{timestamp}")
            counter = 1
            while os.path.exists(backup_path):
                backup_path = os.path.join(dir_name, f"{base_name}.corrupted.{timestamp}_{counter}")
                counter += 1

            shutil.copy2(self.storage_path, backup_path)
            sys.stderr.write(
                f"[EventStore] WARNING: Corrupted event store detected at '{self.storage_path}'. "
                f"Preserved corrupted data to '{backup_path}' for forensic recovery.\n"
            )
            return backup_path
        except Exception as e:
            sys.stderr.write(
                f"[EventStore] ERROR: Failed to preserve corrupted store '{self.storage_path}': {e}\n"
            )
            return None

    def save(self) -> None:
        """Atomically persist store data to disk."""
        with self._lock:
            dir_name = os.path.dirname(self.storage_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=dir_name, prefix=".event_store_tmp_", suffix=".json"
            )
            try:
                with open(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.storage_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise

    def reset_to_seed(self) -> None:
        """Reset the store contents strictly to seed data and persist."""
        with self._lock:
            self._data = {
                "version": 1,
                "event": copy.deepcopy(EVENT),
                "venue_constraints": copy.deepcopy(VENUE_CONSTRAINTS),
                "speakers": copy.deepcopy(SPEAKERS),
                "vendors": copy.deepcopy(VENDORS),
                "sponsors": copy.deepcopy(SPONSORS),
                "tasks": copy.deepcopy(TASKS),
                "schedule": copy.deepcopy(SCHEDULE_ITEMS),
                "briefings": copy.deepcopy(BRIEFINGS),
            }
            self.save()

    def _ensure_schema(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Ensure all required collections exist, backfilling from seed if missing."""
        data = copy.deepcopy(raw)
        defaults = {
            "version": 1,
            "event": copy.deepcopy(EVENT),
            "venue_constraints": copy.deepcopy(VENUE_CONSTRAINTS),
            "speakers": copy.deepcopy(SPEAKERS),
            "vendors": copy.deepcopy(VENDORS),
            "sponsors": copy.deepcopy(SPONSORS),
            "tasks": copy.deepcopy(TASKS),
            "schedule": copy.deepcopy(SCHEDULE_ITEMS),
            "briefings": copy.deepcopy(BRIEFINGS),
        }
        for key, val in defaults.items():
            if key not in data or data[key] is None:
                data[key] = val
        return data

    # -----------------------------------------------------------------------
    # Event Profile & Venue Constraints
    # -----------------------------------------------------------------------
    def get_event(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data["event"])

    def update_event(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._data["event"].update(updates)
            self.save()
            return copy.deepcopy(self._data["event"])

    def get_venue_constraints(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data["venue_constraints"])

    def update_venue_constraints(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._data["venue_constraints"].update(updates)
            self.save()
            return copy.deepcopy(self._data["venue_constraints"])

    # -----------------------------------------------------------------------
    # Speakers
    # -----------------------------------------------------------------------
    def all_speakers(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["speakers"])

    def find_speaker(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            speakers = self._data["speakers"]
            for spk in speakers:
                if q == spk["id"].lower() or q == spk["name"].lower():
                    return copy.deepcopy(spk)
            for spk in speakers:
                if (
                    q in spk["name"].lower()
                    or q in spk["org"].lower()
                    or q in spk["topic"].lower()
                ):
                    return copy.deepcopy(spk)
        return None

    def update_speaker(self, speaker_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for spk in self._data["speakers"]:
                if spk["id"] == speaker_id:
                    spk.update(updates)
                    self.save()
                    return copy.deepcopy(spk)
        return None

    # -----------------------------------------------------------------------
    # Vendors
    # -----------------------------------------------------------------------
    def all_vendors(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["vendors"])

    def find_vendor(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            vendors = self._data["vendors"]
            for v in vendors:
                if q == v["id"].lower() or q == v["name"].lower():
                    return copy.deepcopy(v)
            for v in vendors:
                if q in v["name"].lower() or q in v["category"].lower():
                    return copy.deepcopy(v)
        return None

    def update_vendor(self, vendor_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for v in self._data["vendors"]:
                if v["id"] == vendor_id:
                    v.update(updates)
                    self.save()
                    return copy.deepcopy(v)
        return None

    # -----------------------------------------------------------------------
    # Sponsors
    # -----------------------------------------------------------------------
    def all_sponsors(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["sponsors"])

    def find_sponsor(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            sponsors = self._data["sponsors"]
            for s in sponsors:
                if q == s["id"].lower() or q == s["name"].lower():
                    return copy.deepcopy(s)
            for s in sponsors:
                if q in s["name"].lower() or q in s["tier"].lower():
                    return copy.deepcopy(s)
        return None

    def update_sponsor(self, sponsor_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for s in self._data["sponsors"]:
                if s["id"] == sponsor_id:
                    s.update(updates)
                    self.save()
                    return copy.deepcopy(s)
        return None

    # -----------------------------------------------------------------------
    # Operational Tasks
    # -----------------------------------------------------------------------
    def all_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["tasks"])

    def find_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    return copy.deepcopy(t)
        return None

    def add_task(self, task: dict[str, Any] | OperationalTask) -> dict[str, Any]:
        task_dict = task.to_dict() if isinstance(task, OperationalTask) else copy.deepcopy(task)
        with self._lock:
            # Prevent duplicate IDs
            for existing in self._data["tasks"]:
                if existing["id"] == task_dict["id"]:
                    raise ValueError(f"Task with id '{task_dict['id']}' already exists.")
            self._data["tasks"].append(task_dict)
            self.save()
            return copy.deepcopy(task_dict)

    def update_task(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    t.update(updates)
                    self.save()
                    return copy.deepcopy(t)
        return None

    def upsert_tasks(self, tasks: list[dict[str, Any] | OperationalTask]) -> list[dict[str, Any]]:
        """Idempotently insert new tasks and update matching non-conflicting tasks without clobbering edits."""
        with self._lock:
            existing_by_id = {t["id"]: t for t in self._data["tasks"]}
            persisted: list[dict[str, Any]] = []
            for t in tasks:
                t_dict = t.to_dict() if isinstance(t, OperationalTask) else copy.deepcopy(t)
                t_id = t_dict["id"]
                if t_id in existing_by_id:
                    target = existing_by_id[t_id]
                    # Preserve user status if already changed from open
                    user_status = target.get("status", "open")
                    target.update({k: v for k, v in t_dict.items() if k != "status"})
                    if user_status in ("done", "in_progress", "blocked"):
                        target["status"] = user_status
                    persisted.append(copy.deepcopy(target))
                else:
                    self._data["tasks"].append(t_dict)
                    existing_by_id[t_id] = t_dict
                    persisted.append(copy.deepcopy(t_dict))
            self.save()
            return persisted

    # -----------------------------------------------------------------------
    # Schedule Items (Day-of Run-of-Show)
    # -----------------------------------------------------------------------
    def all_schedule_items(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["schedule"])

    def find_schedule_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            for item in self._data["schedule"]:
                if item["id"] == item_id:
                    return copy.deepcopy(item)
        return None

    def add_schedule_item(self, item: dict[str, Any] | ScheduleItem) -> dict[str, Any]:
        item_dict = item.to_dict() if isinstance(item, ScheduleItem) else copy.deepcopy(item)
        with self._lock:
            for existing in self._data["schedule"]:
                if existing["id"] == item_dict["id"]:
                    raise ValueError(f"Schedule item with id '{item_dict['id']}' already exists.")
            self._data["schedule"].append(item_dict)
            self.save()
            return copy.deepcopy(item_dict)

    def update_schedule_item(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for item in self._data["schedule"]:
                if item["id"] == item_id:
                    item.update(updates)
                    self.save()
                    return copy.deepcopy(item)
        return None

    # -----------------------------------------------------------------------
    # Briefings
    # -----------------------------------------------------------------------
    def all_briefings(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._data["briefings"])

    def find_briefing(self, briefing_id: str) -> dict[str, Any] | None:
        with self._lock:
            for b in self._data["briefings"]:
                if b["id"] == briefing_id:
                    return copy.deepcopy(b)
        return None

    def add_briefing(self, briefing: dict[str, Any] | Briefing) -> dict[str, Any]:
        briefing_dict = briefing.to_dict() if isinstance(briefing, Briefing) else copy.deepcopy(briefing)
        with self._lock:
            for existing in self._data["briefings"]:
                if existing["id"] == briefing_dict["id"]:
                    raise ValueError(f"Briefing with id '{briefing_dict['id']}' already exists.")
            self._data["briefings"].append(briefing_dict)
            self.save()
            return copy.deepcopy(briefing_dict)

    def update_briefing(self, briefing_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for b in self._data["briefings"]:
                if b["id"] == briefing_id:
                    b.update(updates)
                    self.save()
                    return copy.deepcopy(b)
        return None


# ---------------------------------------------------------------------------
# Global Singleton Accessor
# ---------------------------------------------------------------------------
_GLOBAL_STORE: EventStore | None = None
_STORE_LOCK = threading.Lock()


def get_event_store(storage_path: str | None = None, reload: bool = False) -> EventStore:
    """Return the global singleton EventStore instance."""
    global _GLOBAL_STORE
    with _STORE_LOCK:
        if _GLOBAL_STORE is None or reload or storage_path is not None:
            _GLOBAL_STORE = EventStore(storage_path=storage_path)
        return _GLOBAL_STORE
