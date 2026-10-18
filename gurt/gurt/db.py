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
    conn = sqlite3.connect(str(settings.db_path), timeout=30.0)
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

    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tool_calls TEXT,
        model_used TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        category TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS briefings (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        recipient_role TEXT NOT NULL,
        recipient_id TEXT,
        recipient_name TEXT,
        version INTEGER DEFAULT 1,
        status TEXT NOT NULL,
        content_json TEXT NOT NULL,
        source_fingerprint TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        event_id TEXT DEFAULT 'evt-dubhacks-2026',
        actor_id TEXT NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        details_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Apply incremental migrations to existing databases
    _ensure_column(cursor, "events", "goals TEXT")
    _ensure_column(cursor, "events", "theme TEXT")
    _ensure_column(cursor, "events", "venue_contact TEXT")
    _ensure_column(cursor, "events", "dietary_specs TEXT")
    _ensure_column(cursor, "events", "av_requirements TEXT")
    _ensure_column(cursor, "events", "organizer_name TEXT DEFAULT ''")
    _ensure_column(cursor, "events", "organizer_email TEXT DEFAULT ''")
    _ensure_column(cursor, "events", "organizer_phone TEXT DEFAULT ''")
    _ensure_column(cursor, "events", "organization TEXT DEFAULT ''")
    _ensure_column(cursor, "events", "venue_confirmation_status TEXT DEFAULT 'unconfirmed'")
    _ensure_column(cursor, "events", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    _ensure_column(cursor, "events", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    _ensure_column(cursor, "speakers", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "vendors", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "vendors", "compliance_verified INTEGER DEFAULT 0")
    _ensure_column(cursor, "vendors", "compliance_notes TEXT DEFAULT ''")
    _ensure_column(cursor, "vendors", "quote_data TEXT DEFAULT '{}'")
    _ensure_column(cursor, "vendors", "selected_at TEXT DEFAULT ''")
    _ensure_column(cursor, "vendors", "selection_notes TEXT DEFAULT ''")
    _ensure_column(cursor, "vendor_requirements", "dietary_needs TEXT DEFAULT ''")
    _ensure_column(cursor, "vendor_requirements", "service_window TEXT DEFAULT ''")
    _ensure_column(cursor, "vendor_requirements", "location TEXT DEFAULT ''")
    _ensure_column(cursor, "vendor_requirements", "details_json TEXT DEFAULT '{}'")
    _ensure_column(cursor, "vendor_requirements", "updated_at TEXT DEFAULT ''")
    _ensure_column(cursor, "sponsors", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "tasks", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "action_proposals", "event_id TEXT DEFAULT 'evt-dubhacks-2026'")
    _ensure_column(cursor, "action_proposals", "delivery_status TEXT DEFAULT 'pending approval'")
    _ensure_column(cursor, "action_proposals", "approval_status TEXT DEFAULT 'pending'")
    _ensure_column(cursor, "action_proposals", "approved_at TEXT DEFAULT ''")
    _ensure_column(cursor, "action_proposals", "approved_by TEXT DEFAULT ''")
    _ensure_column(cursor, "action_proposals", "delivery_mode TEXT DEFAULT 'simulated'")
    _ensure_column(cursor, "action_proposals", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    # Schedule extensions for precision logistics & conflict detection
    for tbl in ("schedules", "schedule"):
        try:
            _ensure_column(cursor, tbl, "start_time TEXT")
            _ensure_column(cursor, tbl, "end_time TEXT")
            _ensure_column(cursor, tbl, "room TEXT")
            _ensure_column(cursor, tbl, "speaker_id TEXT")
            _ensure_column(cursor, tbl, "vendor_id TEXT")
            _ensure_column(cursor, tbl, "confirmation_state TEXT DEFAULT 'tentative'")
            _ensure_column(cursor, tbl, "setup_buffer_minutes INTEGER DEFAULT 0")
            _ensure_column(cursor, tbl, "teardown_buffer_minutes INTEGER DEFAULT 0")
        except Exception:
            pass

    # Backfill start_time, end_time, room from time_slot and location
    cursor.execute("""
        UPDATE schedules
        SET room = location
        WHERE (room IS NULL OR room = '') AND location IS NOT NULL
    """)
    cursor.execute("""
        UPDATE schedules
        SET start_time = TRIM(SUBSTR(time_slot, 1, INSTR(time_slot, '-') - 1)),
            end_time = TRIM(SUBSTR(time_slot, INSTR(time_slot, '-') + 1))
        WHERE (start_time IS NULL OR start_time = '') AND INSTR(time_slot, '-') > 0
    """)

    # Backfill event_id for existing rows
    cursor.execute("UPDATE speakers SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE vendors SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE sponsors SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE tasks SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")
    cursor.execute("UPDATE action_proposals SET event_id = 'evt-dubhacks-2026' WHERE event_id IS NULL OR event_id = ''")

    # Restore DubHacks 2026 benchmark event details if overwritten
    cursor.execute("""
        UPDATE events
        SET title = 'DubHacks 2026 Agentic AI Workshop',
            location = 'UW HUB Ballroom & Room 214',
            attendee_count = 80,
            budget = 2500.0,
            goals = 'Deliver an intensive, hands-on 1-day agentic AI builder workshop with keynotes, technical tracks, and live project demos for 80 attendees.',
            dietary_specs = 'Nut-free facility required; 15 vegan, 10 gluten-free, 5 halal meal boxes needed.',
            av_requirements = '2 handheld wireless mics, 1 podium lapel mic, dual 4K HDMI projectors in Room 214, stable high-bandwidth Wi-Fi for 80 concurrent dev laptops.'
        WHERE id = 'evt-dubhacks-2026' AND title != 'DubHacks 2026 Agentic AI Workshop'
    """)

    # Seed distinct Loveable Event record if not present
    cursor.execute("SELECT COUNT(*) FROM events WHERE id = 'evt-loveable-2026'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO events (
                id, title, date, location, attendee_count, budget, status,
                goals, theme, venue_contact, dietary_specs, av_requirements
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "evt-loveable-2026",
            "Loveable Community Builder Meetup",
            "2026-11-20 18:00",
            "Seattle Tech Hub Lounge",
            20,
            400.0,
            "planning",
            "Host an intimate community meetup for 20 AI creators and builders to demo projects, network, and exchange feedback.",
            "Full-Stack AI Prototyping & Loveable Workflows",
            "Seattle Tech Hub Community Team (events@seattletechhub.example)",
            "5 vegan wraps, 5 vegetarian sandwiches, 10 assorted snack boxes.",
            "1 presentation monitor, 1 wireless mic, fast guest Wi-Fi."
        ))

        # Seed distinct tasks for Loveable event
        loveable_tasks = [
            ("tsk-lov-001", "evt-loveable-2026", "Confirm Seattle Tech Hub lounge reservation", "Diya Lead", "Venue", "2026-11-10", "in_progress", "None"),
            ("tsk-lov-002", "evt-loveable-2026", "Source snack boxes & beverages for 20 pax ($400 cap)", "Diya Lead", "Catering", "2026-11-14", "todo", "tsk-lov-001"),
            ("tsk-lov-003", "evt-loveable-2026", "Send participant RSVP reminder and lightning demo form", "Diya Lead", "Outreach", "2026-11-16", "todo", "None")
        ]
        cursor.executemany("INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", loveable_tasks)

        # Seed distinct vendor requirements for Loveable event
        loveable_reqs = [
            ("vrq-lov-001", "evt-loveable-2026", "Catering", "Light evening snacks and drinks for 20 people ($20/head limit)", 20, 400.0, "quoted", "Check for dairy and gluten restrictions among RSVPs."),
            ("vrq-lov-002", "evt-loveable-2026", "Badges & Signage", "20 name badges and 1 welcome directional sign", 20, 60.0, "todo", "Use Seattle Tech Hub color printer.")
        ]
        cursor.executemany("INSERT INTO vendor_requirements (id, event_id, category, specification, headcount, budget_allocated, status, unknowns) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", loveable_reqs)

    # Seed distinct Claude Workshop record if not present
    cursor.execute("SELECT COUNT(*) FROM events WHERE id = 'evt-claude-workshop'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO events (
                id, title, date, location, attendee_count, budget, status,
                goals, theme, venue_contact, dietary_specs, av_requirements,
                organizer_name, organizer_email, organizer_phone, organization, venue_confirmation_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "evt-claude-workshop",
            "Claude Workshop",
            "2026-11-22 13:00",
            "Blueprint office in Bellevue",
            40,
            500.0,
            "planning",
            "Hands-on Claude and agentic coding workshop for 40 builders with practical tool use exercises.",
            "Claude Tool Calling & FastMCP Development",
            "Blueprint Building Facilities (facilities@blueprint.example)",
            "Nut-free snacks; vegetarian and gluten-free cookies & coffee.",
            "Display monitor, high-speed Wi-Fi, 1 handheld mic.",
            "",
            "",
            "",
            "",
            "unconfirmed"
        ))

        # Seed distinct vendor requirement for Claude Workshop
        claude_reqs = [
            ("vrq-claude-001", "evt-claude-workshop", "Catering", "Afternoon refreshments & coffee for 40 attendees ($500 event cap)", 40, 500.0, "quoted", "Verify nut-free facility and delivery timing.")
        ]
        cursor.executemany("INSERT INTO vendor_requirements (id, event_id, category, specification, headcount, budget_allocated, status, unknowns) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", claude_reqs)

    # Seed distinct pre-researched speakers for Claude Workshop if empty
    cursor.execute("SELECT COUNT(*) FROM speakers WHERE event_id = 'evt-claude-workshop'")
    if cursor.fetchone()[0] == 0:
        claude_speakers = [
            ("spk-cld-001", "evt-claude-workshop", "Marcus Rivera", "Anthropic / Independent", "Claude Tool Calling & FastMCP Development", "shortlist", "mrivera@example.com", "01:30 - 02:15 PM", "Core contributor to agent testing benchmarks and Claude agent evaluation."),
            ("spk-cld-002", "evt-claude-workshop", "Dr. Alicia Chen", "UW AI Institute", "Multi-Agent Coordination & Safety", "shortlist", "alicia.chen@cs.washington.edu", "02:30 - 03:15 PM", "Associate professor researching multi-agent autonomy and safety bounds.")
        ]
        cursor.executemany("INSERT INTO speakers (id, event_id, name, org, topic, status, contact_email, proposed_time, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", claude_speakers)

    # Check if benchmark event already seeded
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

    # Seed default conversation if empty
    cursor.execute("SELECT COUNT(*) FROM conversations")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO conversations (id, event_id, title)
            VALUES (?, ?, ?)
        """, ("conv-default", "evt-dubhacks-2026", "General Operations & Launch"))
        cursor.execute("""
            INSERT INTO messages (id, conversation_id, role, content, model_used)
            VALUES (?, ?, ?, ?, ?)
        """, ("msg-init", "conv-default", "assistant", "Yo! I'm Gurt, your autonomous event operations agent for DubHacks 2026. What should we work on today?", "gemini-3.8-flash"))

    # Seed initial memories if empty
    cursor.execute("SELECT COUNT(*) FROM memories")
    if cursor.fetchone()[0] == 0:
        initial_memories = [
            ("mem-001", "evt-dubhacks-2026", "catering_budget_ceiling", "Target maximum $15.00/head for attendee lunch catering.", "budget_preference"),
            ("mem-002", "evt-dubhacks-2026", "dietary_compliance", "100% nut-free facility requirement is strict; always verify supplier kitchen allergen protocols.", "dietary_rule"),
            ("mem-003", "evt-dubhacks-2026", "av_lead", "Jordan Tech is primary on-site AV contact with UW HUB technicians.", "team_assignment")
        ]
        cursor.executemany("INSERT INTO memories (id, event_id, key, value, category) VALUES (?, ?, ?, ?, ?)", initial_memories)

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


def get_event_brief(event_id: str | None = None) -> dict[str, Any]:
    """Retrieve full event brief for the given event_id, or the first active event."""
    conn = get_connection()
    c = conn.cursor()
    row = None
    if event_id:
        c.execute("SELECT * FROM events WHERE id = ? LIMIT 1", (event_id,))
        row = c.fetchone()
        if not row:
            # Also try matching by title case-insensitively
            c.execute("SELECT * FROM events WHERE title LIKE ? LIMIT 1", (f"%{event_id}%",))
            row = c.fetchone()
        if not row and event_id.startswith("evt-"):
            clean_title = event_id.replace("evt-", "").replace("-", " ")
            c.execute("SELECT * FROM events WHERE title LIKE ? LIMIT 1", (f"%{clean_title}%",))
            row = c.fetchone()
    if not row:
        c.execute("SELECT * FROM events ORDER BY created_at ASC LIMIT 1")
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
        "goals", "theme", "venue_contact", "dietary_specs", "av_requirements",
        "organizer_name", "organizer_email", "organizer_phone", "organization",
        "venue_confirmation_status"
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


def list_all_events() -> list[dict[str, Any]]:
    """List all registered events with live counts of tasks, speakers, and vendors."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY created_at ASC")
    events = [dict(r) for r in c.fetchall()]

    for ev in events:
        eid = ev["id"]
        c.execute("SELECT COUNT(*) FROM tasks WHERE event_id = ?", (eid,))
        ev["tasks_count"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM speakers WHERE event_id = ?", (eid,))
        ev["speakers_count"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM vendors WHERE event_id = ?", (eid,))
        ev["vendors_count"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sponsors WHERE event_id = ?", (eid,))
        ev["sponsors_count"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM action_proposals WHERE event_id = ? AND status = 'pending_approval'", (eid,))
        ev["pending_actions_count"] = c.fetchone()[0]

    conn.close()
    return events


def create_event_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Create a new event brief with clean slugged event_id and auto-seeded starter operations."""
    import re
    title = brief.get("title", "New Event").strip()
    clean_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:18] or "event"

    conn = get_connection()
    c = conn.cursor()

    # Determine unique event ID
    candidate_id = brief.get("id") or f"evt-{clean_slug}"
    c.execute("SELECT COUNT(*) FROM events WHERE id = ?", (candidate_id,))
    if c.fetchone()[0] > 0:
        event_id = f"evt-{clean_slug}-{uuid.uuid4().hex[:4]}"
    else:
        event_id = candidate_id

    now = datetime.now().isoformat()
    attendees = int(brief.get("attendee_count", 80))
    budget = float(brief.get("budget", 2500.0))
    location = brief.get("location", "UW Campus Venue")
    date_str = brief.get("date", "2026-11-20 09:00")

    organizer_name = brief.get("organizer_name", "")
    organizer_email = brief.get("organizer_email", "")
    organizer_phone = brief.get("organizer_phone", "")
    organization = brief.get("organization", "")
    venue_confirmation_status = brief.get("venue_confirmation_status", "unconfirmed")

    c.execute("""
        INSERT INTO events (
            id, title, date, location, attendee_count, budget, status,
            goals, theme, venue_contact, dietary_specs, av_requirements,
            organizer_name, organizer_email, organizer_phone, organization,
            venue_confirmation_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        title,
        date_str,
        location,
        attendees,
        budget,
        brief.get("status", "planning"),
        brief.get("goals", f"Plan and execute {title} for {attendees} attendees."),
        brief.get("theme", brief.get("theme", "")),
        brief.get("venue_contact", ""),
        brief.get("dietary_specs", "Vegetarian, Vegan, GF options required."),
        brief.get("av_requirements", "Microphone, presentation display/projector, Wi-Fi."),
        organizer_name,
        organizer_email,
        organizer_phone,
        organization,
        venue_confirmation_status,
        now,
        now
    ))

    # Auto-seed initial starter tasks tailored to the event
    starter_tasks = [
        (f"tsk-{uuid.uuid4().hex[:5]}", event_id, f"Confirm {location} reservation & access terms", "Event Lead", "Venue", date_str[:10], "in_progress", "None"),
        (f"tsk-{uuid.uuid4().hex[:5]}", event_id, f"Source catering & refreshments for {attendees} pax (${round(budget * 0.45):,} target)", "Ops Lead", "Catering", date_str[:10], "todo", "None"),
        (f"tsk-{uuid.uuid4().hex[:5]}", event_id, f"Prepare attendee registration, badges & agendas ({attendees} pax)", "Ops Lead", "Logistics", date_str[:10], "todo", "None")
    ]
    c.executemany("INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", starter_tasks)

    # Auto-seed initial vendor requirement
    per_head_target = round(budget * 0.45 / max(attendees, 1), 2)
    c.execute("""
        INSERT INTO vendor_requirements (id, event_id, category, specification, headcount, budget_allocated, status, unknowns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"vrq-{uuid.uuid4().hex[:5]}",
        event_id,
        "Catering",
        f"Lunch/refreshments for {attendees} attendees. Target ~${per_head_target:.2f}/head with dietary accommodations.",
        attendees,
        round(budget * 0.45, 2),
        "pending_sourcing",
        "Final RSVP dietary restrictions to be verified."
    ))

    conn.commit()
    conn.close()
    return get_event_brief(event_id)


def update_vendor_compliance(vendor_id: str, verified: bool, notes: str = "") -> dict[str, Any]:
    """Update compliance verification status (license, permits, insurance COI) for a supplier."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE vendors SET compliance_verified = ?, compliance_notes = ? WHERE id = ?",
        (1 if verified else 0, notes, vendor_id)
    )
    conn.commit()
    c.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
    row = c.fetchone()
    conn.close()
    return dict(row or {})


def update_speaker_or_sponsor_status(
    table: str,
    record_id: str,
    status: str,
    proposed_time: str | None = None,
    notes: str | None = None
) -> dict[str, Any]:
    """Update speaker or sponsor status following outreach reply processing."""
    conn = get_connection()
    c = conn.cursor()
    if table == "speakers":
        if proposed_time:
            c.execute("UPDATE speakers SET status = ?, proposed_time = ? WHERE id = ?", (status, proposed_time, record_id))
        else:
            c.execute("UPDATE speakers SET status = ? WHERE id = ?", (status, record_id))
        c.execute("SELECT * FROM speakers WHERE id = ?", (record_id,))
    else:
        if notes:
            c.execute("UPDATE sponsors SET status = ?, notes = ? WHERE id = ?", (status, notes, record_id))
        else:
            c.execute("UPDATE sponsors SET status = ? WHERE id = ?", (status, record_id))
        c.execute("SELECT * FROM sponsors WHERE id = ?", (record_id,))
    row = c.fetchone()
    conn.commit()
    conn.close()
    return dict(row or {})


def get_vendor_by_id(vendor_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    """Retrieve a single vendor by ID, optionally isolated to an event_id."""
    conn = get_connection()
    c = conn.cursor()
    if event_id:
        c.execute("SELECT * FROM vendors WHERE id = ? AND event_id = ?", (vendor_id, event_id))
    else:
        c.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    raw_quote = res.get("quote_data")
    if raw_quote and isinstance(raw_quote, str):
        try:
            res["quote_data"] = json.loads(raw_quote)
        except Exception:
            res["quote_data"] = {}
    elif not raw_quote or not isinstance(raw_quote, dict):
        res["quote_data"] = {}
    return res


def update_vendor(vendor_id: str, updates: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    """Update fields on an existing vendor with event isolation."""
    existing = get_vendor_by_id(vendor_id, event_id=event_id)
    if not existing:
        raise ValueError(f"Vendor '{vendor_id}' not found" + (f" for event '{event_id}'" if event_id else ""))

    allowed_fields = [
        "category", "company_name", "quote_amount", "price_per_head",
        "status", "contact_email", "details", "compliance_verified",
        "compliance_notes", "quote_data", "selected_at", "selection_notes"
    ]
    set_clauses = []
    values = []
    for k, v in updates.items():
        if k in allowed_fields:
            if k == "quote_data" and isinstance(v, (dict, list)):
                v = json.dumps(v)
            elif k == "compliance_verified" and isinstance(v, bool):
                v = 1 if v else 0
            elif k in ("quote_amount", "price_per_head") and v is not None:
                v = float(v)
            set_clauses.append(f"{k} = ?")
            values.append(v)

    if set_clauses:
        conn = get_connection()
        c = conn.cursor()
        values.append(vendor_id)
        if event_id:
            values.append(event_id)
            c.execute(f"UPDATE vendors SET {', '.join(set_clauses)} WHERE id = ? AND event_id = ?", values)
        else:
            c.execute(f"UPDATE vendors SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    updated = get_vendor_by_id(vendor_id, event_id=event_id)
    return updated or {}


def record_vendor_selection(
    vendor_id: str,
    event_id: str = "evt-dubhacks-2026",
    selection_notes: str = "",
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Select preferred vendor proposal without booking, purchasing, or contract commitment."""
    vendor = get_vendor_by_id(vendor_id, event_id=event_id)
    if not vendor:
        raise ValueError(f"Vendor '{vendor_id}' not found for event '{event_id}'")

    now = datetime.now().isoformat()
    update_vendor(vendor_id, {
        "status": "selected",
        "selected_at": now,
        "selection_notes": selection_notes
    }, event_id=event_id)

    # Immutable audit trail
    audit_details = {
        "vendor_id": vendor_id,
        "company_name": vendor.get("company_name"),
        "category": vendor.get("category"),
        "quote_amount": vendor.get("quote_amount"),
        "selection_notes": selection_notes,
        "is_booked": False,
        "is_confirmed": False,
        "is_actual_purchase": False,
        "is_purchase": False,
        "requires_manual_booking": True,
        "notice": "Selected as preferred proposal only. NOT booked, purchased, or confirmed."
    }
    log_audit_event(
        event_id=event_id,
        actor_id=actor_id,
        action="select_preferred_vendor",
        target_type="vendor",
        target_id=vendor_id,
        details=audit_details
    )

    return {
        "status": "selected",
        "vendor_id": vendor_id,
        "company_name": vendor.get("company_name"),
        "event_id": event_id,
        "quote_status": "selected",
        "selected_at": now,
        "selection_notes": selection_notes,
        "is_preferred": True,
        "is_booked": False,
        "is_confirmed": False,
        "is_actual_purchase": False,
        "is_purchase": False,
        "requires_manual_booking": True,
        "booking_disclaimer": (
            "Vendor proposal selected as preferred proposal. This action DOES NOT book, confirm, purchase, "
            "or sign any binding agreement with the vendor. The organizer must manually contact the vendor to "
            "negotiate, execute a contract, and arrange payment."
        ),
        "next_steps": [
            "Contact vendor representative to request formal catering agreement.",
            "Confirm loading dock clearance and access times with venue.",
            "Verify final guest dietary restrictions 5 days prior to the event.",
            "Process formal purchase order or payment through institutional finance."
        ]
    }


def get_action_proposal(action_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    """Retrieve an action proposal by ID with optional event isolation and parsed payload/result."""
    conn = get_connection()
    try:
        c = conn.cursor()
        if event_id:
            c.execute("SELECT * FROM action_proposals WHERE id = ? AND event_id = ?", (action_id, event_id))
        else:
            c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
        row = c.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    res = dict(row)
    for json_col in ("payload", "execution_result"):
        raw_val = res.get(json_col)
        if raw_val and isinstance(raw_val, str):
            try:
                res[json_col] = json.loads(raw_val)
            except Exception:
                pass
    return res


def update_action_proposal(action_id: str, updates: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    """Update fields on an existing action proposal with event isolation."""
    existing = get_action_proposal(action_id, event_id=event_id)
    if not existing:
        raise ValueError(f"Action proposal '{action_id}' not found" + (f" for event '{event_id}'" if event_id else ""))

    allowed_fields = [
        "title", "summary", "payload", "status", "delivery_status",
        "approval_status", "approved_at", "approved_by", "delivery_mode",
        "executed_at", "execution_result", "updated_at"
    ]
    set_clauses = []
    values = []
    for k, v in updates.items():
        if k in allowed_fields:
            if k in ("payload", "execution_result") and isinstance(v, (dict, list)):
                v = json.dumps(v)
            set_clauses.append(f"{k} = ?")
            values.append(v)

    if set_clauses:
        conn = get_connection()
        try:
            c = conn.cursor()
            values.append(action_id)
            if event_id:
                values.append(event_id)
                c.execute(f"UPDATE action_proposals SET {', '.join(set_clauses)} WHERE id = ? AND event_id = ?", values)
            else:
                c.execute(f"UPDATE action_proposals SET {', '.join(set_clauses)} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

    updated = get_action_proposal(action_id, event_id=event_id)
    return updated or {}


def record_action_approval(
    action_id: str,
    actor_id: str = "organizer",
    event_id: str | None = None
) -> dict[str, Any]:
    """Record organizer approval of an action proposal before execution."""
    action = get_action_proposal(action_id, event_id=event_id)
    if not action:
        raise ValueError(f"Action proposal '{action_id}' not found" + (f" for event '{event_id}'" if event_id else ""))

    now = datetime.now().isoformat()
    updated = update_action_proposal(action_id, {
        "status": "approved",
        "approval_status": "approved",
        "approved_at": now,
        "approved_by": actor_id,
        "delivery_status": "approved",
        "updated_at": now
    }, event_id=event_id)

    log_audit_event(
        event_id=action.get("event_id", "evt-dubhacks-2026"),
        actor_id=actor_id,
        action="approve_action_proposal",
        target_type="action_proposal",
        target_id=action_id,
        details={
            "action_id": action_id,
            "action_type": action.get("action_type"),
            "title": action.get("title"),
            "approved_by": actor_id,
            "approved_at": now
        }
    )
    return updated


def list_action_proposals(
    event_id: str = "evt-dubhacks-2026",
    status: str | None = None
) -> list[dict[str, Any]]:
    """List all action proposals for an event, optionally filtered by status, with parsed payloads."""
    conn = get_connection()
    try:
        c = conn.cursor()
        if status:
            c.execute(
                "SELECT * FROM action_proposals WHERE event_id = ? AND status = ? ORDER BY created_at DESC",
                (event_id, status)
            )
        else:
            c.execute(
                "SELECT * FROM action_proposals WHERE event_id = ? ORDER BY created_at DESC",
                (event_id,)
            )
        rows_raw = c.fetchall()
    finally:
        conn.close()

    rows = []
    for r in rows_raw:
        d = dict(r)
        for json_col in ("payload", "execution_result"):
            raw_val = d.get(json_col)
            if raw_val and isinstance(raw_val, str):
                try:
                    d[json_col] = json.loads(raw_val)
                except Exception:
                    pass
        rows.append(d)
    return rows


get_action_proposals = list_action_proposals


def get_vendor_requirements(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Retrieve all vendor requirements for an event, with parsed details_json."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM vendor_requirements WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
    rows = []
    for r in c.fetchall():
        d = dict(r)
        raw_details = d.get("details_json")
        if raw_details and isinstance(raw_details, str):
            try:
                d["details_json"] = json.loads(raw_details)
            except Exception:
                d["details_json"] = {}
        elif not raw_details or not isinstance(raw_details, dict):
            d["details_json"] = {}
        rows.append(d)
    conn.close()
    return rows


def get_vendor_requirement_by_id(req_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    """Retrieve a single vendor requirement by ID, optionally isolated to an event_id."""
    conn = get_connection()
    c = conn.cursor()
    if event_id:
        c.execute("SELECT * FROM vendor_requirements WHERE id = ? AND event_id = ?", (req_id, event_id))
    else:
        c.execute("SELECT * FROM vendor_requirements WHERE id = ?", (req_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    raw_details = d.get("details_json")
    if raw_details and isinstance(raw_details, str):
        try:
            d["details_json"] = json.loads(raw_details)
        except Exception:
            d["details_json"] = {}
    elif not raw_details or not isinstance(raw_details, dict):
        d["details_json"] = {}
    return d


def update_vendor_requirement(req_id: str, updates: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
    """Update fields on an existing vendor requirement with event isolation."""
    existing = get_vendor_requirement_by_id(req_id, event_id=event_id)
    if not existing:
        raise ValueError(f"Vendor requirement '{req_id}' not found" + (f" for event '{event_id}'" if event_id else ""))

    allowed_fields = [
        "category", "specification", "headcount", "budget_allocated",
        "status", "unknowns", "dietary_needs", "service_window",
        "location", "details_json", "updated_at"
    ]
    set_clauses = []
    values = []
    for k, v in updates.items():
        if k in allowed_fields:
            if k == "details_json" and isinstance(v, (dict, list)):
                v = json.dumps(v)
            elif k == "unknowns" and isinstance(v, (list, tuple)):
                v = "; ".join(str(item) for item in v)
            elif k in ("headcount",) and v is not None:
                v = int(v)
            elif k in ("budget_allocated",) and v is not None:
                v = float(v)
            set_clauses.append(f"{k} = ?")
            values.append(v)

    if "updated_at" not in updates:
        set_clauses.append("updated_at = ?")
        values.append(datetime.now().isoformat())

    if set_clauses:
        conn = get_connection()
        c = conn.cursor()
        values.append(req_id)
        if event_id:
            values.append(event_id)
            c.execute(f"UPDATE vendor_requirements SET {', '.join(set_clauses)} WHERE id = ? AND event_id = ?", values)
        else:
            c.execute(f"UPDATE vendor_requirements SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    updated = get_vendor_requirement_by_id(req_id, event_id=event_id)
    return updated or {}


def save_vendor_requirement(
    event_id: str,
    category: str,
    specification: str,
    headcount: int = 80,
    budget_allocated: float = 0.0,
    unknowns: str | list[str] = "",
    status: str = "quoted",
    dietary_needs: str = "",
    service_window: str = "",
    location: str = "",
    details_json: str | dict[str, Any] = "",
    req_id: str | None = None
) -> dict[str, Any]:
    """Insert or update a vendor requirement."""
    if req_id:
        existing = get_vendor_requirement_by_id(req_id, event_id=event_id)
        if existing:
            updates = {
                "category": category,
                "specification": specification,
                "headcount": headcount,
                "budget_allocated": budget_allocated,
                "unknowns": unknowns,
                "status": status,
                "dietary_needs": dietary_needs,
                "service_window": service_window,
                "location": location,
                "details_json": details_json
            }
            return update_vendor_requirement(req_id, updates, event_id=event_id)

    new_id = f"vrq-{uuid.uuid4().hex[:6]}"
    if isinstance(unknowns, (list, tuple)):
        unknowns_str = "; ".join(str(x) for x in unknowns)
    else:
        unknowns_str = str(unknowns or "")

    if isinstance(details_json, (dict, list)):
        details_str = json.dumps(details_json)
    else:
        details_str = str(details_json or "{}")

    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO vendor_requirements (
            id, event_id, category, specification, headcount, budget_allocated, status, unknowns,
            dietary_needs, service_window, location, details_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        new_id, event_id, category, specification, headcount, float(budget_allocated), status, unknowns_str,
        dietary_needs, service_window, location, details_str, now, now
    ))
    conn.commit()
    conn.close()
    created = get_vendor_requirement_by_id(new_id, event_id=event_id)
    return created or {
        "id": new_id,
        "event_id": event_id,
        "category": category,
        "specification": specification,
        "headcount": headcount,
        "budget_allocated": budget_allocated,
        "unknowns": unknowns_str,
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


def get_schedule_item_by_id(item_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    conn = get_connection()
    c = conn.cursor()
    if event_id:
        c.execute("SELECT * FROM schedules WHERE id = ? AND event_id = ?", (item_id, event_id))
    else:
        c.execute("SELECT * FROM schedules WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_schedule_item(
    item_id: str,
    updates: dict[str, Any],
    event_id: str | None = None
) -> dict[str, Any] | None:
    conn = get_connection()
    c = conn.cursor()

    # Verify item exists
    if event_id:
        c.execute("SELECT * FROM schedules WHERE id = ? AND event_id = ?", (item_id, event_id))
    else:
        c.execute("SELECT * FROM schedules WHERE id = ?", (item_id,))
    existing = c.fetchone()
    if not existing:
        conn.close()
        return None

    allowed_cols = {
        "time_slot", "activity", "location", "owner", "activity_type",
        "dependencies", "notes", "start_time", "end_time", "room",
        "speaker_id", "vendor_id", "confirmation_state",
        "setup_buffer_minutes", "teardown_buffer_minutes"
    }

    clean_updates = {k: v for k, v in updates.items() if k in allowed_cols}

    # Synchronize room and location if one is updated
    if "room" in clean_updates and "location" not in clean_updates:
        clean_updates["location"] = clean_updates["room"]
    elif "location" in clean_updates and "room" not in clean_updates:
        clean_updates["room"] = clean_updates["location"]

    # Synchronize time_slot if start_time and end_time are updated
    if "start_time" in clean_updates and "end_time" in clean_updates and "time_slot" not in clean_updates:
        clean_updates["time_slot"] = f"{clean_updates['start_time']} - {clean_updates['end_time']}"

    if clean_updates:
        set_clauses = [f"{col} = ?" for col in clean_updates.keys()]
        values = list(clean_updates.values())
        if event_id:
            query = f"UPDATE schedules SET {', '.join(set_clauses)} WHERE id = ? AND event_id = ?"
            values.extend([item_id, event_id])
        else:
            query = f"UPDATE schedules SET {', '.join(set_clauses)} WHERE id = ?"
            values.append(item_id)
        c.execute(query, values)
        conn.commit()

    if event_id:
        c.execute("SELECT * FROM schedules WHERE id = ? AND event_id = ?", (item_id, event_id))
    else:
        c.execute("SELECT * FROM schedules WHERE id = ?", (item_id,))
    updated_row = c.fetchone()
    conn.close()
    return dict(updated_row) if updated_row else None


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
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO pdf_documents (id, event_id, template_name, file_path, mapped_fields, unresolved_fields, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, event_id, template_name, file_path,
            json.dumps(mapped_fields), json.dumps(unresolved_fields), status
        ))
        conn.commit()
    finally:
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
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pdf_documents WHERE event_id = ? ORDER BY created_at DESC", (event_id,))
        raw_rows = c.fetchall()
    finally:
        conn.close()

    rows = [dict(r) for r in raw_rows]
    for r in rows:
        try: r["mapped_fields"] = json.loads(r["mapped_fields"])
        except Exception: pass
        try: r["unresolved_fields"] = json.loads(r["unresolved_fields"])
        except Exception: pass
    return rows


def get_pdf_document_by_id(doc_id: str, event_id: str | None = None) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        if event_id:
            c.execute("SELECT * FROM pdf_documents WHERE id = ? AND event_id = ? LIMIT 1", (doc_id, event_id))
        else:
            c.execute("SELECT * FROM pdf_documents WHERE id = ? LIMIT 1", (doc_id,))
        row = c.fetchone()
        if not row:
            return None
        doc = dict(row)
        try: doc["mapped_fields"] = json.loads(doc["mapped_fields"])
        except Exception: pass
        try: doc["unresolved_fields"] = json.loads(doc["unresolved_fields"])
        except Exception: pass
        return doc
    finally:
        conn.close()


def get_event_by_id(event_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM events WHERE id = ? LIMIT 1", (event_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


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


def get_conversations(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Retrieve all conversations for the event, ordered by recency."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM conversations WHERE event_id = ? ORDER BY updated_at DESC", (event_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def create_conversation(event_id: str = "evt-dubhacks-2026", title: str = "New Conversation") -> dict[str, Any]:
    """Create a new conversation session."""
    conv_id = f"conv-{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO conversations (id, event_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, event_id, title, now, now)
    )
    # Add initial greeting message
    c.execute(
        "INSERT INTO messages (id, conversation_id, role, content, model_used) VALUES (?, ?, ?, ?, ?)",
        (f"msg-{uuid.uuid4().hex[:6]}", conv_id, "assistant", "Yo! I'm Gurt, your autonomous event operations agent. What should we work on in this thread?", "gemini-3.8-flash")
    )
    conn.commit()
    conn.close()
    return {
        "id": conv_id,
        "event_id": event_id,
        "title": title,
        "created_at": now,
        "updated_at": now
    }


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and its messages."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return True


def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    """Get all messages for a specific conversation."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
    rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        if r.get("tool_calls"):
            try:
                r["tool_calls"] = json.loads(r["tool_calls"])
            except Exception:
                pass
    conn.close()
    return rows


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    model_used: str | None = None
) -> dict[str, Any]:
    """Save a user or assistant message to SQLite history and touch conversation updated_at."""
    msg_id = f"msg-{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()
    tool_calls_json = json.dumps(tool_calls) if tool_calls else None

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (id, conversation_id, role, content, tool_calls, model_used, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg_id, conversation_id, role, content, tool_calls_json, model_used, now)
    )
    # Touch conversation timestamp
    c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    conn.commit()
    conn.close()

    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "model_used": model_used,
        "created_at": now
    }


def get_memories(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Retrieve persistent memories / organizer preferences."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM memories WHERE event_id = ? ORDER BY updated_at DESC", (event_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def save_memory(
    event_id: str = "evt-dubhacks-2026",
    key: str = "",
    value: str = "",
    category: str = "preference"
) -> dict[str, Any]:
    """Save or update a persistent memory fact."""
    mem_id = f"mem-{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    # Check if key already exists for this event
    c.execute("SELECT id FROM memories WHERE event_id = ? AND key = ?", (event_id, key))
    existing = c.fetchone()
    if existing:
        c.execute("UPDATE memories SET value = ?, category = ?, updated_at = ? WHERE id = ?", (value, category, now, existing[0]))
        actual_id = existing[0]
    else:
        c.execute(
            "INSERT INTO memories (id, event_id, key, value, category, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mem_id, event_id, key, value, category, now)
        )
        actual_id = mem_id
    conn.commit()
    conn.close()
    return {
        "id": actual_id,
        "event_id": event_id,
        "key": key,
        "value": value,
        "category": category,
        "updated_at": now
    }


def delete_memory(memory_id: str) -> bool:
    """Delete a memory item."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Briefings CRUD & Versioning
# ---------------------------------------------------------------------------
def save_briefing(
    event_id: str = "evt-dubhacks-2026",
    recipient_role: str = "speaker",
    recipient_id: str = "",
    recipient_name: str = "",
    content_dict: dict[str, Any] | None = None,
    source_fingerprint: str = "",
    status: str = "draft",
    version: int = 1
) -> dict[str, Any]:
    """Save or update a role-specific participant briefing draft."""
    content_json = json.dumps(content_dict or {})
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()

    # Check if a briefing already exists for this role + recipient
    c.execute(
        "SELECT id, version FROM briefings WHERE event_id = ? AND recipient_role = ? AND recipient_id = ?",
        (event_id, recipient_role, recipient_id)
    )
    existing = c.fetchone()
    if existing:
        briefing_id = existing[0]
        new_version = existing[1] + 1 if status == "revised" else existing[1]
        c.execute("""
            UPDATE briefings
            SET recipient_name = ?, version = ?, status = ?, content_json = ?, source_fingerprint = ?, updated_at = ?
            WHERE id = ?
        """, (recipient_name, new_version, status, content_json, source_fingerprint, now, briefing_id))
    else:
        briefing_id = f"brf-{uuid.uuid4().hex[:6]}"
        c.execute("""
            INSERT INTO briefings (
                id, event_id, recipient_role, recipient_id, recipient_name, version, status,
                content_json, source_fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            briefing_id, event_id, recipient_role, recipient_id, recipient_name, version, status,
            content_json, source_fingerprint, now, now
        ))

    conn.commit()
    conn.close()
    return {
        "id": briefing_id,
        "event_id": event_id,
        "recipient_role": recipient_role,
        "recipient_id": recipient_id,
        "recipient_name": recipient_name,
        "version": version,
        "status": status,
        "source_fingerprint": source_fingerprint,
        "content": content_dict or {},
        "updated_at": now
    }


def get_briefings(event_id: str = "evt-dubhacks-2026", recipient_role: str | None = None) -> list[dict[str, Any]]:
    """Retrieve participant briefings for an event, optionally filtered by role."""
    conn = get_connection()
    c = conn.cursor()
    if recipient_role:
        c.execute(
            "SELECT * FROM briefings WHERE event_id = ? AND recipient_role = ? ORDER BY updated_at DESC",
            (event_id, recipient_role)
        )
    else:
        c.execute("SELECT * FROM briefings WHERE event_id = ? ORDER BY updated_at DESC", (event_id,))

    rows = c.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["content"] = json.loads(d.get("content_json") or "{}")
        except Exception:
            d["content"] = {}
        results.append(d)
    conn.close()
    return results


def get_briefing_by_id(briefing_id: str) -> dict[str, Any] | None:
    """Retrieve single briefing by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM briefings WHERE id = ?", (briefing_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["content"] = json.loads(d.get("content_json") or "{}")
    except Exception:
        d["content"] = {}
    return d


def mark_briefing_status(briefing_id: str, status: str) -> bool:
    """Update briefing status (e.g. 'ready', 'sent')."""
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE briefings SET status = ?, updated_at = ? WHERE id = ?", (status, now, briefing_id))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
def log_audit_event(
    event_id: str = "evt-dubhacks-2026",
    actor_id: str = "organizer",
    action: str = "schedule_updated",
    target_type: str = "schedule",
    target_id: str = "",
    details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Record an immutable, durable audit log event."""
    log_id = f"aud-{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()
    details_str = json.dumps(details or {})
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO audit_logs (id, event_id, actor_id, action, target_type, target_id, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, event_id, actor_id, action, target_type, target_id, details_str, now))
    conn.commit()
    conn.close()
    return {
        "id": log_id,
        "event_id": event_id,
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "created_at": now
    }


def get_audit_logs(event_id: str = "evt-dubhacks-2026", limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve audit log history for an event."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM audit_logs WHERE event_id = ? ORDER BY created_at DESC LIMIT ?",
        (event_id, limit)
    )
    rows = c.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d.get("details_json") or "{}")
        except Exception:
            d["details"] = {}
        results.append(d)
    conn.close()
    return results


# Backward-compatible alias
record_audit_log = log_audit_event


def get_tasks(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Retrieve all tasks for an event."""
    return query_records("tasks", event_id=event_id)


def get_schedule(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Retrieve schedule items for an event."""
    return get_schedule_items(event_id=event_id)


def get_event(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Retrieve event brief for an event."""
    return get_event_brief(event_id=event_id)

