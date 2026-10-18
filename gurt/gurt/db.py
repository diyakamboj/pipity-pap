"""Gurt Event Database.

Independently implemented persistent storage using SQLite.
Stores events, speakers, vendors, sponsors, tasks, and approval proposals.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any
from gurt.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables and initial seed data if empty."""
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
        status TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS speakers (
        id TEXT PRIMARY KEY,
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
        category TEXT NOT NULL,
        company_name TEXT NOT NULL,
        quote_amount REAL NOT NULL,
        price_per_head REAL,
        status TEXT NOT NULL,
        contact_email TEXT,
        details TEXT
    );

    CREATE TABLE IF NOT EXISTS sponsors (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tier TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        contact_email TEXT,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        owner TEXT NOT NULL,
        category TEXT NOT NULL,
        deadline TEXT NOT NULL,
        status TEXT NOT NULL,
        dependencies TEXT
    );

    CREATE TABLE IF NOT EXISTS action_proposals (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        executed_at TIMESTAMP,
        execution_result TEXT
    );
    """)

    # Check if event already seeded
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO events (id, title, date, location, attendee_count, budget, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "evt-dubhacks-2026",
            "DubHacks 2026 Agentic AI Workshop",
            "2026-11-15 09:00",
            "UW HUB Ballroom & Room 214",
            80,
            2500.0,
            "planning"
        ))

        # Seed initial speakers
        speakers = [
            ("spk-001", "Dr. Alicia Chen", "UW AI Institute", "Multi-Agent Coordination & Safety", "shortlist", "alicia.chen@cs.washington.edu", "10:00 - 10:45 AM", "Associate professor researching multi-agent autonomy."),
            ("spk-002", "Marcus Rivera", "Anthropic / Independent", "Evaluations for Agentic Workflows", "contacted", "mrivera@example.com", "11:00 - 11:45 AM", "Core contributor to agent testing benchmarks."),
            ("spk-003", "Priya Nair", "Local AI Founder", "Shipping Production Tools with FastMCP", "confirmed", "priya@pnwtech.io", "02:00 - 02:45 PM", "Built top enterprise agent workflows in Seattle.")
        ]
        cursor.executemany("INSERT INTO speakers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", speakers)

        # Seed initial vendors
        vendors = [
            ("vnd-001", "Catering", "Ballard Bites & Bowls", 1080.0, 13.50, "quoted", "orders@ballardbites.example", "Grain bowls & wraps. Certified nut-free, vegan & gluten-free options."),
            ("vnd-002", "Catering", "Pacific Northwest Artisan Deli", 1360.0, 17.00, "quoted", "catering@pnwdeli.example", "Artisan sandwiches & salads. High minimum, delivery fee included."),
            ("vnd-003", "Badges & Swag", "Emerald City Printworks", 240.0, 3.00, "approved", "print@emeraldcity.example", "Lanyards, NFC hackathon badges, and agendas. 3-day turnaround.")
        ]
        cursor.executemany("INSERT INTO vendors VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vendors)

        # Seed sponsors
        sponsors = [
            ("spn-001", "CloudCompute Corp", "Gold", 3000.0, "confirmed", "sponsorships@cloudcompute.example", "Provides cloud credits and workshop mentorship."),
            ("spn-002", "VectorDB Labs", "Silver", 1500.0, "discussion", "community@vectordb.example", "Interested in sponsoring coffee & workshop tracks.")
        ]
        cursor.executemany("INSERT INTO sponsors VALUES (?, ?, ?, ?, ?, ?, ?)", sponsors)

        # Seed tasks
        tasks = [
            ("tsk-001", "Confirm keynote speaker & slides deadline", "Alicia Lead", "Outreach", "2026-11-01", "in_progress", "None"),
            ("tsk-002", "Approve catering contract for 80 attendees", "Sam Operations", "Vendors", "2026-11-05", "todo", "tsk-001"),
            ("tsk-003", "Submit HUB room 214 AV requirement sheet", "Jordan Tech", "Logistics", "2026-11-03", "todo", "None"),
            ("tsk-004", "Print participant badges and sponsor signage", "Sam Operations", "Logistics", "2026-11-10", "todo", "tsk-002"),
            ("tsk-005", "Send mentor briefing & Discord access", "Alicia Lead", "Logistics", "2026-11-12", "todo", "tsk-001")
        ]
        cursor.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)", tasks)

    conn.commit()
    conn.close()


def query_records(table: str, search: str = "") -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    safe_table = table if table in ("events", "speakers", "vendors", "sponsors", "tasks", "action_proposals") else "tasks"
    
    if search:
        cursor.execute(f"SELECT * FROM {safe_table} WHERE title LIKE ? OR name LIKE ? OR category LIKE ? LIMIT 50",
                       (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute(f"SELECT * FROM {safe_table} LIMIT 50")
    
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_event_summary() -> dict[str, Any]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM events LIMIT 1")
    event = dict(c.fetchone() or {})
    c.execute("SELECT COUNT(*) FROM speakers WHERE status = 'confirmed'")
    confirmed_speakers = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM speakers")
    total_speakers = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done'")
    completed_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM vendors")
    total_vendors = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM action_proposals WHERE status = 'pending_approval'")
    pending_actions = c.fetchone()[0]
    conn.close()

    return {
        "event": event,
        "speakers": f"{confirmed_speakers}/{total_speakers} confirmed",
        "vendors": f"{total_vendors} evaluated",
        "tasks": f"{completed_tasks}/{total_tasks} completed",
        "pending_actions": pending_actions
    }
