"""Event Operations Tool Adapters.

Independently implemented bounded tools for reading and modifying event records,
event briefs, vendor requirements, schedules, speakers, and sponsors.
"""

from __future__ import annotations

import uuid
from typing import Any
from gurt.db import (
    get_connection,
    query_records,
    get_event_summary,
    get_event_brief,
    update_event_brief,
    create_event_brief,
    get_vendor_requirements,
    save_vendor_requirement,
    get_schedule_items,
    save_schedule_item,
    clear_schedule_items
)


def tool_get_event_overview(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Get the high-level summary of the event (date, venue, attendee count, stats)."""
    return get_event_summary(event_id)


def tool_get_event_brief(event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Retrieve full event brief specifications."""
    return get_event_brief(event_id)


def tool_update_event_brief(event_id: str = "evt-dubhacks-2026", **updates: Any) -> dict[str, Any]:
    """Update event brief parameters (title, date, location, attendee_count, budget, goals, theme, dietary_specs, av_requirements)."""
    return update_event_brief(event_id, updates)


def tool_lookup_speakers(query: str = "", event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up speakers by name, organization, or topic."""
    conn = get_connection()
    c = conn.cursor()
    if query:
        q = f"%{query.strip()}%"
        c.execute("SELECT * FROM speakers WHERE event_id = ? AND (name LIKE ? OR org LIKE ? OR topic LIKE ?)", (event_id, q, q, q))
    else:
        c.execute("SELECT * FROM speakers WHERE event_id = ?", (event_id,))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_propose_speaker(
    name: str,
    org: str,
    topic: str,
    bio: str = "",
    contact_email: str = "",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Add a newly discovered speaker candidate to the shortlist with topic and evidence."""
    spk_id = f"spk-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO speakers (id, event_id, name, org, topic, status, contact_email, proposed_time, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (spk_id, event_id, name, org, topic, "shortlist", contact_email, "TBD", bio)
    )
    conn.commit()
    conn.close()
    return {
        "status": "added_to_shortlist",
        "speaker_id": spk_id,
        "name": name,
        "topic": topic,
        "org": org
    }


def tool_lookup_sponsors(query: str = "", event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up sponsors by name or tier (e.g., Gold, Silver, Bronze)."""
    conn = get_connection()
    c = conn.cursor()
    if query:
        q = f"%{query.strip()}%"
        c.execute("SELECT * FROM sponsors WHERE event_id = ? AND (name LIKE ? OR tier LIKE ?)", (event_id, q, q))
    else:
        c.execute("SELECT * FROM sponsors WHERE event_id = ?", (event_id,))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_save_sponsor_candidate(
    name: str,
    tier: str = "Silver",
    amount: float = 1500.0,
    notes: str = "",
    contact_email: str = "",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Save a researched sponsor prospect into the sponsorship pipeline."""
    spn_id = f"spn-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sponsors (id, event_id, name, tier, amount, status, contact_email, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (spn_id, event_id, name, tier, float(amount), "pipeline", contact_email, notes)
    )
    conn.commit()
    conn.close()
    return {
        "status": "recorded_in_pipeline",
        "sponsor_id": spn_id,
        "name": name,
        "tier": tier,
        "amount": amount
    }


def tool_lookup_vendors(category: str = "", event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up vendor quotes by category (e.g., Catering, Badges & Swag, AV Rentals)."""
    conn = get_connection()
    c = conn.cursor()
    if category:
        q = f"%{category.strip()}%"
        c.execute("SELECT * FROM vendors WHERE event_id = ? AND (category LIKE ? OR company_name LIKE ?)", (event_id, q, q))
    else:
        c.execute("SELECT * FROM vendors WHERE event_id = ?", (event_id,))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_add_vendor_quote(
    company_name: str,
    category: str,
    quote_amount: float,
    price_per_head: float = 0.0,
    details: str = "",
    contact_email: str = "",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Add a new vendor quote or supplier comparison to the event database."""
    vnd_id = f"vnd-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO vendors (id, event_id, category, company_name, quote_amount, price_per_head, status, contact_email, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vnd_id, event_id, category, company_name, float(quote_amount), float(price_per_head), "quoted", contact_email, details)
    )
    conn.commit()
    conn.close()
    return {
        "status": "added",
        "vendor_id": vnd_id,
        "company_name": company_name,
        "quote_amount": quote_amount,
        "price_per_head": price_per_head
    }


def tool_lookup_vendor_requirements(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up discovered vendor requirements, specifications, and unknowns."""
    return get_vendor_requirements(event_id)


def tool_save_vendor_requirement(
    category: str,
    specification: str,
    headcount: int = 80,
    budget_allocated: float = 0.0,
    unknowns: str = "",
    status: str = "quoted",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Record discovered vendor needs (e.g. food restrictions, badge count, AV equipment) and missing facts."""
    return save_vendor_requirement(
        event_id=event_id,
        category=category,
        specification=specification,
        headcount=headcount,
        budget_allocated=budget_allocated,
        unknowns=unknowns,
        status=status
    )


def tool_lookup_tasks(status: str = "", event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up logistics tasks, optionally filtering by status (todo, in_progress, done)."""
    conn = get_connection()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM tasks WHERE event_id = ? AND status = ?", (event_id, status.strip()))
    else:
        c.execute("SELECT * FROM tasks WHERE event_id = ?", (event_id,))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_create_task(
    title: str,
    owner: str,
    category: str,
    deadline: str,
    dependencies: str = "None",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Create a new operational or logistics task."""
    task_id = f"tsk-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, event_id, title, owner, category, deadline, "todo", dependencies)
    )
    conn.commit()
    conn.close()
    return {
        "status": "created",
        "task_id": task_id,
        "title": title,
        "owner": owner,
        "deadline": deadline,
        "dependencies": dependencies
    }


def tool_update_task_status(task_id: str, new_status: str) -> dict[str, Any]:
    """Update task status (todo, in_progress, done)."""
    clean_status = new_status.lower().strip()
    if clean_status not in ("todo", "in_progress", "done"):
        clean_status = "done" if "done" in clean_status else "in_progress"

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, title FROM tasks WHERE id = ? OR title LIKE ? LIMIT 1", (task_id, f"%{task_id}%"))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": f"Task '{task_id}' not found."}

    actual_id = row["id"]
    task_title = row["title"]
    c.execute("UPDATE tasks SET status = ? WHERE id = ?", (clean_status, actual_id))
    conn.commit()
    conn.close()
    return {
        "status": "updated",
        "task_id": actual_id,
        "title": task_title,
        "new_status": clean_status
    }


def tool_generate_schedule(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Synthesize a complete run-of-show schedule linking confirmed speakers, lunch, setup, and teardown."""
    event = get_event_brief(event_id)
    speakers = query_records("speakers", event_id=event_id)
    vendors = query_records("vendors", event_id=event_id)

    confirmed_spk = [s for s in speakers if s.get("status") == "confirmed"] or speakers[:2]
    caterer = next((v for v in vendors if "catering" in v.get("category", "").lower()), None)
    caterer_name = caterer["company_name"] if caterer else "Catered Lunch"

    clear_schedule_items(event_id)

    schedule_plan = [
        ("08:00 - 09:00", "Venue Setup & AV Line Check", "UW HUB Room 214", "Jordan Tech", "setup", "None", "Inspect dual projectors and test podium/handheld mics."),
        ("09:00 - 09:30", "Attendee Check-in & Badge Pickup", "Ballroom Lobby Desk", "Sam Operations", "logistics", "sch-setup", "Distribute printed NFC badges and workshop agendas."),
        ("09:30 - 10:00", "Opening Keynote & Workshop Kickoff", "Room 214", "Alicia Lead", "presentation", "sch-checkin", "Welcome 80 attendees, overview agent safety principles and schedule."),
        ("10:00 - 10:45", f"Keynote: {confirmed_spk[0]['topic'] if confirmed_spk else 'Agent Autonomy'}", "Room 214", confirmed_spk[0]["name"] if confirmed_spk else "Keynote Speaker", "keynote", "sch-intro", "Featured technical presentation with live audience Q&A."),
        ("11:00 - 12:30", "Technical Track: FastMCP Tool Integration", "Room 214", "Priya Nair", "workshop", "sch-keynote", "Hands-on builder lab creating bounded agent tool adapters."),
        ("12:30 - 01:30", f"Catered Lunch ({caterer_name}) & Sponsor Mingle", "Ballroom Foyer", "Sam Operations", "lunch", "sch-lab1", f"Distribute boxed meals ({event.get('dietary_specs', 'Nut-free, Vegan, GF')})."),
        ("01:30 - 03:00", "Technical Track: Evaluator Harness & HITL Gates", "Room 214", "Marcus Rivera", "workshop", "sch-lunch", "Implementing deterministic unit tests and confirmation safety policies."),
        ("03:00 - 04:30", "Agent Buildathon & Rapid Demos", "Room 214", "Alicia Lead", "demos", "sch-lab2", "Participant prototype presentations judged by mentors."),
        ("04:30 - 05:00", "Awards, Sponsor Recognition & Teardown", "Room 214", "Whole Team", "teardown", "sch-demos", "Pack equipment, clear UW HUB Room 214, return badge surplus.")
    ]

    saved_items = []
    for item in schedule_plan:
        saved = save_schedule_item(
            event_id=event_id,
            time_slot=item[0],
            activity=item[1],
            location=item[2],
            owner=item[3],
            activity_type=item[4],
            dependencies=item[5],
            notes=item[6]
        )
        saved_items.append(saved)

    return saved_items


def tool_lookup_schedule(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up active run-of-show schedule items."""
    items = get_schedule_items(event_id)
    if not items:
        return tool_generate_schedule(event_id)
    return items
