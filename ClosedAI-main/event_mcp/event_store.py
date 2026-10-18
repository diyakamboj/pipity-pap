"""EventStore: Persistent, JSON-backed event operations data store.

Provides durable persistence across MCP server subprocess restarts, normalized
serializable data structures, and atomic file writes.

Maintains 100% backward compatibility with existing mock backend lookups and seed data.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
import fcntl
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from typing import Any, Optional


class CorruptedStoreError(ValueError):
    """Raised when persistent store data on disk is corrupted or cannot be safely loaded."""
    pass


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
    confirmation_state: str = ConfirmationState.TENTATIVE.value
    status: str = "draft"
    source_fingerprint: str = ""
    source_records: list[str] = field(default_factory=list)
    missing_details: list[str] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

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
            confirmation_state=data.get("confirmation_state", ConfirmationState.TENTATIVE.value),
            status=data.get("status", "draft"),
            source_fingerprint=data.get("source_fingerprint", ""),
            source_records=list(data.get("source_records", [])),
            missing_details=list(data.get("missing_details", [])),
            content=dict(data.get("content", {})),
            history=list(data.get("history", [])),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class AuditEvent:
    event_id: str
    proposal_id: str
    action_type: str
    actor_id: str
    actor_role: str
    auth_source: str
    timestamp: str
    target_id: str
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    affected_records: dict[str, Any] = field(default_factory=dict)
    outcome: str = "success"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        return cls(
            event_id=data["event_id"],
            proposal_id=data.get("proposal_id", ""),
            action_type=data.get("action_type", ""),
            actor_id=data.get("actor_id", ""),
            actor_role=data.get("actor_role", ""),
            auth_source=data.get("auth_source", ""),
            timestamp=data.get("timestamp", ""),
            target_id=data.get("target_id", ""),
            before_state=dict(data.get("before_state", {})),
            after_state=dict(data.get("after_state", {})),
            affected_records=dict(data.get("affected_records", {})),
            outcome=data.get("outcome", "success"),
            notes=data.get("notes", ""),
        )


# ---------------------------------------------------------------------------
# Persistent Event Store Implementation
# ---------------------------------------------------------------------------
class EventStore:
    """Thread-safe, multi-process safe, JSON-backed event store with atomic persistence.

    Cross-process concurrency & consistency guarantees (Phase 5B.1):
    - Multi-process transaction synchronization via POSIX fcntl.flock on an adjacent
      stable lock file (<storage_path>.lock). Never locks the JSON inode which is replaced.
    - Deterministic lock order: in-process threading.RLock acquired FIRST, adjacent
      _file_lock acquired SECOND to prevent deadlocks.
    - Cross-process freshness: all public read methods detect external updates via
      file stat signatures (st_dev, st_ino, st_mtime_ns, st_size) and version counter,
      reloading latest state immediately while never reloading during an active transaction.
    - Strict lost-update prevention: all mutation helpers acquire exclusive file locks
      and reload fresh disk state before modifying and persisting.
    - Corruption protection: runtime corrupted JSON preserves a timestamped forensic backup
      and raises CorruptedStoreError rather than silently destroying user data with a seed reset.
    - Atomic rollback: failed transactions leave persistent data unchanged with no audit
      record consumed.
    """

    def __init__(self, storage_path: str | None = None) -> None:
        if storage_path is None:
            storage_path = os.environ.get("EVENT_STORE_PATH")
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "event_data.json"
            )
        self.storage_path = os.path.abspath(storage_path)
        self.lock_path = f"{self.storage_path}.lock"
        self._lock = threading.RLock()
        self._file_lock_depth: int = 0
        self._file_lock_fd: int | None = None
        self._in_transaction: bool = False
        self._cached_stat: tuple[int, int, int, int] | None = None
        self._cached_version: int = 0
        self._data: dict[str, Any] = {}
        self.load(initial=True)

    # -----------------------------------------------------------------------
    # Cross-Process Locking & Synchronization
    # -----------------------------------------------------------------------
    @contextmanager
    def _file_lock(self, exclusive: bool = True):
        """Cross-process file lock context manager using POSIX fcntl.flock on an adjacent lockfile.

        Acquisition order invariant:
            self._lock (threading.RLock) MUST be acquired prior to invoking _file_lock.
            This serializes threads in the current process before contending for or reusing
            the process-level file descriptor lock.
        """
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        if self._file_lock_depth > 0:
            self._file_lock_depth += 1
            try:
                yield
            finally:
                self._file_lock_depth -= 1
            return

        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o666)
        op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(fd, op)
            self._file_lock_fd = fd
            self._file_lock_depth = 1
            try:
                yield
            finally:
                self._file_lock_depth = 0
                self._file_lock_fd = None
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(fd)

    def _ensure_fresh(self, force: bool = False) -> None:
        """Check if file on disk has changed and reload if so.

        Requirements:
        - Detect atomic file replacement (st_ino change).
        - Do not rely exclusively on mtime > previous_mtime.
        - Do not reload in the middle of an active transaction (unless force=True).
        - Do not silently reset corrupted data on runtime reload.
        """
        if getattr(self, "_in_transaction", False) and not force:
            return

        storage = getattr(self, "storage_path", None)
        if not storage or storage == "/dev/null" or not os.path.exists(storage):
            return

        try:
            st = os.stat(storage)
            current_sig = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
        except OSError:
            return

        if not force and getattr(self, "_cached_stat", None) == current_sig:
            return

        self._reload_from_disk(current_sig)

    def _reload_from_disk(self, current_sig: tuple[int, int, int, int] | None = None) -> None:
        """Read and parse the JSON file from disk into self._data.

        On corruption, preserves the corrupted file to a backup and raises CorruptedStoreError.
        """
        storage = getattr(self, "storage_path", None)
        if not storage or storage == "/dev/null" or not os.path.exists(storage):
            return

        try:
            with open(storage, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Event store file must contain a JSON object")
            self._data = self._ensure_schema(raw)
            if current_sig is None:
                st = os.stat(storage)
                current_sig = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
            self._cached_stat = current_sig
            self._cached_version = int(self._data.get("version", 1))
        except (json.JSONDecodeError, ValueError, OSError) as e:
            backup_path = self._preserve_corrupted_file()
            raise CorruptedStoreError(
                f"Failed to read or parse event store from '{storage}': {e}. "
                f"Corrupted file backed up to '{backup_path}'."
            ) from e

    def load(self, initial: bool = False) -> None:
        """Load data from JSON file or initialize with seed data if file doesn't exist."""
        with self._lock:
            with self._file_lock(exclusive=False):
                if not os.path.exists(self.storage_path):
                    self.reset_to_seed()
                    return

                try:
                    with open(self.storage_path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if not isinstance(raw, dict):
                        raise ValueError("Event store file must contain a JSON object")
                    self._data = self._ensure_schema(raw)
                    st = os.stat(self.storage_path)
                    self._cached_stat = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
                    self._cached_version = int(self._data.get("version", 1))
                except (json.JSONDecodeError, ValueError, OSError) as e:
                    backup = self._preserve_corrupted_file()
                    if initial:
                        # Initial startup recovery for backward compatibility with mock/test crash recovery
                        self.reset_to_seed()
                    else:
                        raise CorruptedStoreError(
                            f"Corrupted event store at '{self.storage_path}': {e}. Preserved at '{backup}'."
                        ) from e

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

    def _save_under_lock(self) -> None:
        """Atomically persist self._data to disk while holding file and thread locks."""
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
            st = os.stat(self.storage_path)
            self._cached_stat = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
            self._cached_version = int(self._data.get("version", 1))
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def save(self) -> None:
        """Atomically persist store data to disk."""
        with self._lock:
            if self._in_transaction:
                raise RuntimeError(
                    "Premature save called while an atomic transaction is active. "
                    "Transactions must commit via transaction context manager only."
                )
            with self._file_lock(exclusive=True):
                self._save_under_lock()

    def reset_to_seed(self) -> None:
        """Reset the store contents strictly to seed data and persist."""
        with self._lock:
            with self._file_lock(exclusive=True):
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
                    "audit_trail": [],
                }
                self._save_under_lock()

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
            "audit_trail": [],
        }
        for key, val in defaults.items():
            if key not in data or data[key] is None:
                data[key] = val
        return data

    @contextmanager
    def transaction(self):
        """Context manager for atomic multi-entity mutations with cross-process locking.

        Locking Order:
            1. In-process threading.RLock (self._lock)
            2. Cross-process POSIX fcntl.flock exclusive on self.lock_path

        Cross-Process Freshness:
            Reloads the latest persisted state from disk AFTER acquiring the exclusive file lock
            and BEFORE yielding to the caller for validation and staged mutation.

        Atomicity & Rollback:
            Modifications made to the yielded `staged` dictionary are only committed
            if the context block exits without error AND the disk write (save) succeeds.
            If any exception occurs inside the block or during persistence, in-memory state
            is rolled back to the pre-transaction snapshot, and no disk write occurs.
        """
        with self._lock:
            if self._in_transaction:
                raise RuntimeError("Nested transactions are not supported.")
            with self._file_lock(exclusive=True):
                # Reload latest persisted state AFTER acquiring exclusive lock
                self._ensure_fresh(force=True)
                snapshot = copy.deepcopy(self._data)
                staged = copy.deepcopy(self._data)
                self._in_transaction = True
                try:
                    yield staged
                    staged = self._ensure_schema(staged)
                    staged["version"] = int(staged.get("version", 0)) + 1
                    self._data = staged
                    self._in_transaction = False
                    self.save()
                except Exception:
                    self._data = snapshot
                    self._in_transaction = False
                    raise

    # -----------------------------------------------------------------------
    # Event Profile & Venue Constraints
    # -----------------------------------------------------------------------
    def get_event(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["event"])

    def update_event(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                self._data["event"].update(updates)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(self._data["event"])

    def get_venue_constraints(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["venue_constraints"])

    def update_venue_constraints(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                self._data["venue_constraints"].update(updates)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(self._data["venue_constraints"])

    # -----------------------------------------------------------------------
    # Speakers
    # -----------------------------------------------------------------------
    def all_speakers(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["speakers"])

    def find_speaker(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            self._ensure_fresh()
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
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for spk in self._data["speakers"]:
                    if spk["id"] == speaker_id:
                        spk.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(spk)
        return None

    # -----------------------------------------------------------------------
    # Vendors
    # -----------------------------------------------------------------------
    def all_vendors(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["vendors"])

    def find_vendor(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            self._ensure_fresh()
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
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for v in self._data["vendors"]:
                    if v["id"] == vendor_id:
                        v.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(v)
        return None

    # -----------------------------------------------------------------------
    # Sponsors
    # -----------------------------------------------------------------------
    def all_sponsors(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["sponsors"])

    def find_sponsor(self, query: str) -> dict[str, Any] | None:
        q = (query or "").strip().lower()
        if not q:
            return None
        with self._lock:
            self._ensure_fresh()
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
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for s in self._data["sponsors"]:
                    if s["id"] == sponsor_id:
                        s.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(s)
        return None

    # -----------------------------------------------------------------------
    # Operational Tasks
    # -----------------------------------------------------------------------
    def all_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["tasks"])

    def find_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_fresh()
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    return copy.deepcopy(t)
        return None

    def add_task(self, task: dict[str, Any] | OperationalTask) -> dict[str, Any]:
        task_dict = task.to_dict() if isinstance(task, OperationalTask) else copy.deepcopy(task)
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for existing in self._data["tasks"]:
                    if existing["id"] == task_dict["id"]:
                        raise ValueError(f"Task with id '{task_dict['id']}' already exists.")
                self._data["tasks"].append(task_dict)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(task_dict)

    def update_task(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for t in self._data["tasks"]:
                    if t["id"] == task_id:
                        t.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(t)
        return None

    def upsert_tasks(self, tasks: list[dict[str, Any] | OperationalTask]) -> list[dict[str, Any]]:
        """Idempotently insert new tasks and update matching non-conflicting tasks without clobbering edits."""
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                existing_by_id = {t["id"]: t for t in self._data["tasks"]}
                persisted: list[dict[str, Any]] = []
                for t in tasks:
                    t_dict = t.to_dict() if isinstance(t, OperationalTask) else copy.deepcopy(t)
                    t_id = t_dict["id"]
                    if t_id in existing_by_id:
                        target = existing_by_id[t_id]
                        user_status = target.get("status", "open")
                        target.update({k: v for k, v in t_dict.items() if k != "status"})
                        if user_status in ("done", "in_progress", "blocked"):
                            target["status"] = user_status
                        persisted.append(copy.deepcopy(target))
                    else:
                        self._data["tasks"].append(t_dict)
                        existing_by_id[t_id] = t_dict
                        persisted.append(copy.deepcopy(t_dict))
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return persisted

    # -----------------------------------------------------------------------
    # Schedule Items (Day-of Run-of-Show)
    # -----------------------------------------------------------------------
    def all_schedule_items(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["schedule"])

    def find_schedule_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_fresh()
            for item in self._data["schedule"]:
                if item["id"] == item_id:
                    return copy.deepcopy(item)
        return None

    def add_schedule_item(self, item: dict[str, Any] | ScheduleItem) -> dict[str, Any]:
        item_dict = item.to_dict() if isinstance(item, ScheduleItem) else copy.deepcopy(item)
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for existing in self._data["schedule"]:
                    if existing["id"] == item_dict["id"]:
                        raise ValueError(f"Schedule item with id '{item_dict['id']}' already exists.")
                self._data["schedule"].append(item_dict)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(item_dict)

    def update_schedule_item(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for item in self._data["schedule"]:
                    if item["id"] == item_id:
                        item.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(item)
        return None

    # -----------------------------------------------------------------------
    # Briefings
    # -----------------------------------------------------------------------
    def all_briefings(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data["briefings"])

    def find_briefing(self, briefing_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_fresh()
            for b in self._data["briefings"]:
                if b["id"] == briefing_id:
                    return copy.deepcopy(b)
        return None

    def add_briefing(self, briefing: dict[str, Any] | Briefing) -> dict[str, Any]:
        briefing_dict = briefing.to_dict() if isinstance(briefing, Briefing) else copy.deepcopy(briefing)
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for existing in self._data["briefings"]:
                    if existing["id"] == briefing_dict["id"]:
                        raise ValueError(f"Briefing with id '{briefing_dict['id']}' already exists.")
                self._data["briefings"].append(briefing_dict)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(briefing_dict)

    def update_briefing(self, briefing_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for b in self._data["briefings"]:
                    if b["id"] == briefing_id:
                        # Guard sent briefings against accidental in-place mutation of content
                        if b.get("status") == "sent":
                            immutable_fields = (
                                "content",
                                "rendered_body",
                                "session_time",
                                "arrival_time",
                                "av_provisions",
                                "notes",
                            )
                            if any(k in updates for k in immutable_fields):
                                raise ValueError(
                                    f"Briefing '{briefing_id}' has already been marked as 'sent' and is immutable. "
                                    "Use upsert_briefing_version to archive the sent version and create a revised draft."
                                )
                        b.update(updates)
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(b)
        return None

    def find_briefing_by_recipient(self, role: str, recipient_id: str) -> dict[str, Any] | None:
        """Find the active briefing for a specific role and recipient ID."""
        with self._lock:
            self._ensure_fresh()
            for b in self._data["briefings"]:
                if b.get("role", "").lower() == role.lower() and b.get("recipient_id", "").lower() == recipient_id.lower():
                    return copy.deepcopy(b)
        return None

    def upsert_briefing_version(self, briefing: dict[str, Any] | Briefing) -> dict[str, Any]:
        """Insert or version-update a briefing, preserving sent versions and history."""
        b_dict = briefing.to_dict() if isinstance(briefing, Briefing) else copy.deepcopy(briefing)
        b_id = b_dict["id"]
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                for idx, existing in enumerate(self._data["briefings"]):
                    if existing["id"] == b_id:
                        # Found existing briefing
                        history = list(existing.get("history", []))
                        current_status = existing.get("status", "draft")

                        # Archive current revision into history
                        snapshot = {
                            "version": existing.get("version", 1),
                            "status": current_status,
                            "archived_at": b_dict.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "source_fingerprint": existing.get("source_fingerprint", ""),
                            "notes": existing.get("notes", ""),
                        }
                        history.append(snapshot)

                        # If previously sent, do NOT silently overwrite: increment version and return to draft
                        if current_status == "sent":
                            b_dict["version"] = existing.get("version", 1) + 1
                            b_dict["status"] = "draft"
                        else:
                            # For existing draft, increment version if source fingerprint changed
                            if existing.get("source_fingerprint") and b_dict.get("source_fingerprint") != existing.get("source_fingerprint"):
                                b_dict["version"] = existing.get("version", 1) + 1

                        b_dict["history"] = history
                        self._data["briefings"][idx] = b_dict
                        self._data["version"] = int(self._data.get("version", 0)) + 1
                        self._save_under_lock()
                        return copy.deepcopy(b_dict)

                # Not found: new briefing
                self._data["briefings"].append(b_dict)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(b_dict)

    # -----------------------------------------------------------------------
    # Audit Trail (Append-Only)
    # -----------------------------------------------------------------------
    def all_audit_events(self) -> list[dict[str, Any]]:
        """Return all recorded audit events (read-only copy)."""
        with self._lock:
            self._ensure_fresh()
            return copy.deepcopy(self._data.get("audit_trail", []))

    def get_audit_event(self, event_id: str) -> dict[str, Any] | None:
        """Find a specific audit event by its event ID."""
        with self._lock:
            self._ensure_fresh()
            for entry in self._data.get("audit_trail", []):
                if entry.get("event_id") == event_id:
                    return copy.deepcopy(entry)
            return None

    def find_audit_by_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Find the audit record for a given proposal ID (used for idempotency and duplicate rejection)."""
        with self._lock:
            self._ensure_fresh()
            for entry in self._data.get("audit_trail", []):
                if entry.get("proposal_id") == proposal_id:
                    return copy.deepcopy(entry)
            return None

    def record_audit_event(self, event: dict[str, Any] | AuditEvent) -> dict[str, Any]:
        """Append an audit event to the audit trail and persist atomically.

        The public API is strictly append-only: there are no update or delete methods
        for audit trail entries.
        """
        evt_dict = event.to_dict() if isinstance(event, AuditEvent) else copy.deepcopy(event)
        with self._lock:
            with self._file_lock(exclusive=True):
                self._ensure_fresh(force=True)
                if "audit_trail" not in self._data:
                    self._data["audit_trail"] = []
                self._data["audit_trail"].append(evt_dict)
                self._data["version"] = int(self._data.get("version", 0)) + 1
                self._save_under_lock()
                return copy.deepcopy(evt_dict)


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
