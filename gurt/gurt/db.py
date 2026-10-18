"""Gurt Event Database.

Independently implemented persistent storage using SQLite.
Stores events, event briefs, speakers, vendors, vendor requirements,
sponsors, tasks, schedules, and approval proposals.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any
from gurt.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor: sqlite3.Cursor, table: str, column_def: str) -> None:
    """Safely add a column to an existing SQLite table if it does not already exist."""
    col_name = column_def.strip().split()[0]
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if col_name not in cols:
        # SQLite does not allow CURRENT_TIMESTAMP in ALTER TABLE ADD COLUMN
        clean_def = column_def
        if "CURRENT_TIMESTAMP" in clean_def:
            clean_def = f"{col_name} TEXT"
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {clean_def}")


def init_db() -> None:
    """Initialize database tables, apply schema updates, and seed initial data if empty."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        location TEXT NOT NULL,
        attendee_count INTEGER NOT NULL,
        budget REAL NOT NULL,
        status TEXT NOT NULL,
        goals TEXT,
        theme TEXT,
        venue_contact TEXT,
        dietary_specs TEXT,
        av_requirements TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS speakers (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        name TEXT NOT NULL,
        org TEXT NOT NULL,
        topic TEXT NOT NULL,
        status TEXT NOT NULL,
        contact_email TEXT,
        proposed_time TEXT,
        bio TEXT
    );

    CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        category TEXT NOT NULL,
        company_name TEXT NOT NULL,
        quote_amount REAL NOT NULL,
        price_per_head REAL,
        status TEXT NOT NULL,
        contact_email TEXT,
        details TEXT
    );

    CREATE TABLE IF NOT EXISTS vendor_requirements (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        category TEXT NOT NULL,
        specification TEXT NOT NULL,
        headcount INTEGER,
        budget_allocated REAL,
        status TEXT NOT NULL,
        unknowns TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sponsors (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        name TEXT NOT NULL,
        tier TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        contact_email TEXT,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        title TEXT NOT NULL,
        owner TEXT NOT NULL,
        category TEXT NOT NULL,
        deadline TEXT NOT NULL,
        status TEXT NOT NULL,
        dependencies TEXT
    );

    CREATE TABLE IF NOT EXISTS schedules (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        time_slot TEXT NOT NULL,
        activity TEXT NOT NULL,
        location TEXT NOT NULL,
        owner TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        dependencies TEXT DEFAULT 'None',
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS action_proposals (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        action_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        executed_at TIMESTAMP,
        execution_result TEXT
    );

    CREATE TABLE IF NOT EXISTS pdf_documents (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        template_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        mapped_fields TEXT NOT NULL,
        unresolved_fields TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Apply incremental migrations to existing databases
    _ensure_column(cursor, "events", "goals TEXT")
    _ensure_column(cursor, "events", "theme TEXT")
    _ensure_column(cursor, "events", "venue_contact TEXT")
    _ensure_column(cursor, "events", "dietary_specs TEXT")
    _ensure_column(cursor, "events", "av_requirements TEXT")
    _ensure_column(cursor, "events", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    _ensure_column(cursor, "events", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    _ensure_column(cursor, "speakers", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "vendors", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "sponsors", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "tasks", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "action_proposals", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")

    # Backfill event_id for existing rows
    cursor.execute("UPDATE speakers SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE vendors SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE sponsors SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE tasks SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE action_proposals SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")

    # Check if event already seeded
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO events (
                id, title, date, location, attendee_count, budget, status,
                goals, theme, venue_contact, dietary_specs, av_requirements
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "evt-dubhacks-2026",
            "DubHacks 2026 Agentic AI Workshop",
            "2026-11-15 09:00",
            "UW HUB Ballroom & Room 214",
            80,
            2500.0,
            "planning",
            "Deliver an intensive, hands-on 1-day agentic AI builder workshop with keynotes, technical tracks, and live project demos for 80 attendees.",
            "Autonomous Agents, Safety Protocols & Production Orchestration",
            "UW Student Activities & HUB Events Office (hubevents@uw.edu)",
            "Nut-free facility required; 15 vegan, 10 gluten-free, 5 halal meal boxes needed.",
            "2 handheld wireless mics, 1 podium lapel mic, dual 4K HDMI projectors in Room 214, stable high-bandwidth Wi-Fi for 80 concurrent dev laptops."
        ))

        # Seed initial speakers
        speakers = [
            ("spk-001", "evt-dubhacks-2026", "Dr. Alicia Chen", "UW AI Institute", "Multi-Agent Coordination & Safety", "shortlist", "alicia.chen@cs.washington.edu", "10:00 - 10:45 AM", "Associate professor researching multi-agent autonomy and safety bounds."),
            ("spk-002", "evt-dubhacks-2026", "Marcus Rivera", "Anthropic / Independent", "Evaluations for Agentic Workflows", "contacted", "mrivera@example.com", "11:00 - 11:45 AM", "Core contributor to agent testing benchmarks and harness design."),
            ("spk-003", "evt-dubhacks-2026", "Priya Nair", "Local AI Founder", "Shipping Production Tools with FastMCP", "confirmed", "priya@pnwtech.io", "02:00 - 02:45 PM", "Built top enterprise agent workflows in Seattle.")
        ]
        cursor.executemany("INSERT INTO speakers (id, event_id, name, org, topic, status, contact_email, proposed_time, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", speakers)

        # Seed initial vendors
        vendors = [
            ("vnd-001", "evt-dubhacks-2026", "Catering", "Ballard Bites & Bowls", 1080.0, 13.50, "quoted", "orders@ballardbites.example", "Grain bowls & wraps. Certified nut-free, vegan & gluten-free options."),
            ("vnd-002", "evt-dubhacks-2026", "Catering", "Pacific Northwest Artisan Deli", 1360.0, 17.00, "quoted", "catering@pnwdeli.example", "Artisan sandwiches & salads. High minimum, delivery fee included."),
            ("vnd-003", "evt-dubhacks-2026", "Badges & Swag", "Emerald City Printworks", 240.0, 3.00, "approved", "print@emeraldcity.example", "Lanyards, NFC hackathon badges, and agendas. 3-day turnaround.")
        ]
        cursor.executemany("INSERT INTO vendors (id, event_id, category, company_name, quote_amount, price_per_head, status, contact_email, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", vendors)

        # Seed sponsors
        sponsors = [
            ("spn-001", "evt-dubhacks-2026", "CloudCompute Corp", "Gold", 3000.0, "confirmed", "sponsorships@cloudcompute.example", "Provides cloud credits and workshop mentorship."),
            ("spn-002", "evt-dubhacks-2026", "VectorDB Labs", "Silver", 1500.0, "discussion", "community@vectordb.example", "Interested in sponsoring coffee & workshop tracks.")
        ]
        cursor.executemany("INSERT INTO sponsors (id, event_id, name, tier, amount, status, contact_email, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sponsors)

        # Seed tasks
        tasks = [
            ("tsk-001", "evt-dubhacks-2026", "Confirm keynote speaker & slides deadline", "Alicia Lead", "Outreach", "2026-11-01", "in_progress", "None"),
            ("tsk-002", "evt-dubhacks-2026", "Approve catering contract for 80 attendees", "Sam Operations", "Vendors", "2026-11-05", "todo", "tsk-001"),
            ("tsk-003", "evt-dubhacks-2026", "Submit HUB room 214 AV requirement sheet", "Jordan Tech", "Logistics", "2026-11-03", "todo", "None"),
            ("tsk-004", "evt-dubhacks-2026", "Print participant badges and sponsor signage", "Sam Operations", "Logistics", "2026-11-10", "todo", "tsk-002"),
            ("tsk-005", "evt-dubhacks-2026", "Send mentor briefing & Discord access", "Alicia Lead", "Logistics", "2026-11-12", "todo", "tsk-001")
        ]
        cursor.executemany("INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tasks)

    # Seed vendor requirements if empty
    cursor.execute("SELECT COUNT(*) FROM vendor_requirements")
    if cursor.fetchone()[0] == 0:
        requirements = [
            ("vrq-001", "evt-dubhacks-2026", "Catering", "Boxed lunches for 80 attendees (15 vegan, 10 GF, 5 halal). Nut-free kitchen required.", 80, 1200.0, "quoted", "Exact breakdown of attendee allergies to finalize 5 days before."),
            ("vrq-002", "evt-dubhacks-2026", "Badges & Signage", "80 color attendee badges with QR codes, 15 mentor/speaker lanyards, 4 directional signs.", 95, 300.0, "approved", "Speaker badge names pending final shortlist confirmation."),
            ("vrq-003", "evt-dubhacks-2026", "AV Equipment", "Dual projectors, 2 wireless handheld microphones, 1 podium lapel, presentation clicker.", 80, 350.0, "pending_sourcing", "Confirm whether UW HUB provides built-in podium mic without surcharge.")
        ]
        cursor.executemany("INSERT INTO vendor_requirements (id, event_id, category, specification, headcount, budget_allocated, status, unknowns) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", requirements)

    # Seed schedule if empty
    cursor.execute("SELECT COUNT(*) FROM schedules")
    if cursor.fetchone()[0] == 0:
        schedule_seed = [
            ("sch-001", "evt-dubhacks-2026", "08:00 - 09:00", "Venue Setup & AV Line Check", "UW HUB Room 214", "Jordan Tech", "setup", "None", "Inspect dual projectors and microphone levels before doors open."),
            ("sch-002", "evt-dubhacks-2026", "09:00 - 09:30", "Attendee Check-in & Badge Pickup", "Ballroom Lobby Desk", "Sam Operations", "logistics", "sch-001", "Distribute NFC badges and schedule printouts."),
            ("sch-003", "evt-dubhacks-2026", "09:30 - 10:00", "Opening Remarks & Workshop Kickoff", "Room 214", "Alicia Lead", "presentation", "sch-002", "Welcome attendees, outline workshop objectives and sponsor thanks."),
            ("sch-004", "evt-dubhacks-2026", "10:00 - 10:45", "Keynote: Multi-Agent Coordination & Safety", "Room 214", "Dr. Alicia Chen", "keynote", "sch-003", "45-min talk + Q&A."),
            ("sch-005", "evt-dubhacks-2026", "11:00 - 12:30", "Hands-on Lab 1: FastMCP & Production Tools", "Room 214", "Priya Nair", "workshop", "sch-004", "Building and testing bounded tool adapters."),
            ("sch-006", "evt-dubhacks-2026", "12:30 - 01:30", "Catered Lunch & Sponsor Networking", "Ballroom Foyer", "Sam Operations", "lunch", "sch-005", "Ballard Bites boxed lunches distributed."),
            ("sch-007", "evt-dubhacks-2026", "01:30 - 03:00", "Hands-on Lab 2: Evaluation & HITL Guards", "Room 214", "Marcus Rivera", "workshop", "sch-006", "Evaluating agent safety, loops, and human-in-the-loop gates."),
            ("sch-008", "evt-dubhacks-2026", "03:00 - 04:30", "Hack Session & Lightning Demos", "Room 214", "Alicia Lead", "demos", "sch-007", "Participant teams present live running agent prototypes."),
            ("sch-009", "evt-dubhacks-2026", "04:30 - 05:00", "Wrap-up, Awards & Teardown", "Room 214", "Whole Team", "teardown", "sch-008", "Clean room, return rented AV equipment, clear HUB Ballroom.")
        ]
        cursor.executemany("INSERT INTO schedules (id, event_id, time_slot, activity, location, owner, activity_type, dependencies, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", schedule_seed)

    conn.commit()
    conn.close()


def query_records(table: str, search: str = "", event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    safe_table = table if table in (
        "events", "speakers", "vendors", "vendor_requirements",
        "sponsors", "tasks", "schedules", "action_proposals", "pdf_documents"
    ) else "tasks"

    if safe_table == "events":
        cursor.execute("SELECT * FROM events WHERE id = ? OR title LIKE ? LIMIT 50", (event_id, f"%{search}%"))
    elif search:
        cursor.execute(
            f"SELECT * FROM {safe_table} WHERE event_id = ? AND (title LIKE ? OR name LIKE ? OR category LIKE ? OR activity LIKE ?) LIMIT 50",
            (event_id, f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%")
        )
    else:
        cursor.execute(f"SELECT * FROM {safe_table} WHERE event_id = ? LIMIT 50", (event_id,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_event_brief(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Retrieve full event brief."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE id = ? LIMIT 1", (event_id,))
    row = c.fetchone()
    if not row:
        c.execute("SELECT * FROM events LIMIT 1")
        row = c.fetchone()
    event_data = dict(row or {})
    conn.close()
    return event_data


def update_event_brief(event_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update event brief fields and update timestamp."""
    conn = get_connection()
    c = conn.cursor()
    allowed_fields = [
        "title", "date", "location", "attendee_count", "budget", "status",
        "goals", "theme", "venue_contact", "dietary_specs", "av_requirements"
    ]
    set_clauses = []
    values = []
    for field in allowed_fields:
        if field in updates:
            set_clauses.append(f"{field} = ?")
            values.append(updates[field])

    if not set_clauses:
        conn.close()
        return get_event_brief(event_id)

    set_clauses.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(event_id)

    query = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"
    c.execute(query, tuple(values))
    conn.commit()
    conn.close()
    return get_event_brief(event_id)


def create_event_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Create a new event brief with dedicated event_id."""
    event_id = brief.get("id") or f"evt-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO events (
            id, title, date, location, attendee_count, budget, status,
            goals, theme, venue_contact, dietary_specs, av_requirements, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        brief.get("title", "New Event"),
        brief.get("date", "2026-11-15 09:00"),
        brief.get("location", "UW HUB"),
        int(brief.get("attendee_count", 80)),
        float(brief.get("budget", 2500.0)),
        brief.get("status", "planning"),
        brief.get("goals", ""),
        brief.get("theme", ""),
        brief.get("venue_contact", ""),
        brief.get("dietary_specs", ""),
        brief.get("av_requirements", ""),
        now,
        now
    ))
    conn.commit()
    conn.close()
    return get_event_brief(event_id)


def get_vendor_requirements(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM vendor_requirements WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def save_vendor_requirement(
    event_id: str,
    category: str,
    specification: str,
    headcount: int = 80,
    budget_allocated: float = 0.0,
    unknowns: str = "",
    status: str = "quoted"
) -> dict[str, Any]:
    req_id = f"vrq-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO vendor_requirements (id, event_id, category, specification, headcount, budget_allocated, status, unknowns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (req_id, event_id, category, specification, headcount, float(budget_allocated), status, unknowns))
    conn.commit()
    conn.close()
    return {
        "id": req_id,
        "event_id": event_id,
        "category": category,
        "specification": specification,
        "headcount": headcount,
        "budget_allocated": budget_allocated,
        "unknowns": unknowns,
        "status": status
    }


def get_schedule_items(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM schedules WHERE event_id = ? ORDER BY time_slot ASC", (event_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def clear_schedule_items(event_id: str = "evt-dubhacks-2026") -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM schedules WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()


def save_schedule_item(
    event_id: str,
    time_slot: str,
    activity: str,
    location: str,
    owner: str,
    activity_type: str,
    dependencies: str = "None",
    notes: str = ""
) -> dict[str, Any]:
    item_id = f"sch-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO schedules (id, event_id, time_slot, activity, location, owner, activity_type, dependencies, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (item_id, event_id, time_slot, activity, location, owner, activity_type, dependencies, notes))
    conn.commit()
    conn.close()
    return {
        "id": item_id,
        "event_id": event_id,
        "time_slot": time_slot,
        "activity": activity,
        "location": location,
        "owner": owner,
        "activity_type": activity_type,
        "dependencies": dependencies,
        "notes": notes
    }


def save_pdf_document(
    event_id: str,
    template_name: str,
    file_path: str,
    mapped_fields: dict[str, Any],
    unresolved_fields: list[str],
    status: str = "draft_ready"
) -> dict[str, Any]:
    doc_id = f"pdf-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO pdf_documents (id, event_id, template_name, file_path, mapped_fields, unresolved_fields, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id, event_id, template_name, file_path,
        json.dumps(mapped_fields), json.dumps(unresolved_fields), status
    ))
    conn.commit()
    conn.close()
    return {
        "id": doc_id,
        "event_id": event_id,
        "template_name": template_name,
        "file_path": file_path,
        "mapped_fields": mapped_fields,
        "unresolved_fields": unresolved_fields,
        "status": status
    }


def get_pdf_documents(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM pdf_documents WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
    rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        try: r["mapped_fields"] = json.loads(r["mapped_fields"])
        except Exception: pass
        try: r["unresolved_fields"] = json.loads(r["unresolved_fields"])
        except Exception: pass
    conn.close()
    return rows


def get_event_summary(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE id = ? LIMIT 1", (event_id,))
    row = c.fetchone()
    if not row:
        c.execute("SELECT * FROM events LIMIT 1")
        row = c.fetchone()
    event = dict(row or {})
    actual_event_id = event.get("id", event_id)

    c.execute("SELECT COUNT(*) FROM speakers WHERE event_id = ? AND status = 'confirmed'", (actual_event_id,))
    confirmed_speakers = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM speakers WHERE event_id = ?", (actual_event_id,))
    total_speakers = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM tasks WHERE event_id = ? AND status = 'done'", (actual_event_id,))
    completed_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE event_id = ?", (actual_event_id,))
    total_tasks = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM vendors WHERE event_id = ?", (actual_event_id,))
    total_vendors = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM action_proposals WHERE event_id = ? AND status = 'pending_approval'", (actual_event_id,))
    pending_actions = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM schedules WHERE event_id = ?", (actual_event_id,))
    total_schedule_items = c.fetchone()[0]

    conn.close()

    return {
        "event": event,
        "speakers": f"{confirmed_speakers}/{total_speakers} confirmed",
        "vendors": f"{total_vendors} evaluated",
        "tasks": f"{completed_tasks}/{total_tasks} completed",
        "pending_actions": pending_actions,
        "schedule_items": total_schedule_items
    }
