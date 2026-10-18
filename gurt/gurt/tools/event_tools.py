"""Event Operations Tool Adapters.

Independently implemented bounded tools for reading and modifying event records.
"""

from __future__ import annotations

import uuid
from typing import Any
from gurt.db import get_connection, query_records, get_event_summary


def tool_get_event_overview() -> dict[str, Any]:
    """Get the high-level summary of the event (date, venue, attendee count, stats)."""
    return get_event_summary()


def tool_lookup_speakers(query: str = "") -> list[dict[str, Any]]:
    """Look up speakers by name, organization, or topic."""
    conn = get_connection()
    c = conn.cursor()
    if query:
        q = f"%{query.strip()}%"
        c.execute("SELECT * FROM speakers WHERE name LIKE ? OR org LIKE ? OR topic LIKE ?", (q, q, q))
    else:
        c.execute("SELECT * FROM speakers")
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_lookup_vendors(category: str = "") -> list[dict[str, Any]]:
    """Look up vendor quotes by category (e.g., Catering, Badges & Swag, AV Rentals)."""
    conn = get_connection()
    c = conn.cursor()
    if category:
        q = f"%{category.strip()}%"
        c.execute("SELECT * FROM vendors WHERE category LIKE ? OR company_name LIKE ?", (q, q))
    else:
        c.execute("SELECT * FROM vendors")
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_lookup_tasks(status: str = "") -> list[dict[str, Any]]:
    """Look up logistics tasks, optionally filtering by status (todo, in_progress, done)."""
    conn = get_connection()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM tasks WHERE status = ?", (status.strip(),))
    else:
        c.execute("SELECT * FROM tasks")
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_create_task(title: str, owner: str, category: str, deadline: str, dependencies: str = "None") -> dict[str, Any]:
    """Create a new operational or logistics task."""
    task_id = f"tsk-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, title, owner, category, deadline, "todo", dependencies)
    )
    conn.commit()
    conn.close()
    return {
        "status": "created",
        "task_id": task_id,
        "title": title,
        "owner": owner,
        "deadline": deadline
    }


def tool_propose_speaker(name: str, org: str, topic: str, bio: str = "", contact_email: str = "") -> dict[str, Any]:
    """Add a newly discovered speaker to the shortlist."""
    spk_id = f"spk-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO speakers (id, name, org, topic, status, contact_email, proposed_time, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (spk_id, name, org, topic, "shortlist", contact_email, "TBD", bio)
    )
    conn.commit()
    conn.close()
    return {
        "status": "added_to_shortlist",
        "speaker_id": spk_id,
        "name": name,
        "topic": topic
    }


def tool_lookup_sponsors(query: str = "") -> list[dict[str, Any]]:
    """Look up sponsors by name or tier (e.g., Gold, Silver, Bronze)."""
    conn = get_connection()
    c = conn.cursor()
    if query:
        q = f"%{query.strip()}%"
        c.execute("SELECT * FROM sponsors WHERE name LIKE ? OR tier LIKE ?", (q, q))
    else:
        c.execute("SELECT * FROM sponsors")
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def tool_update_task_status(task_id: str, new_status: str) -> dict[str, Any]:
    """Update task status (todo, in_progress, done)."""
    clean_status = new_status.lower().strip()
    if clean_status not in ("todo", "in_progress", "done"):
        clean_status = "done" if "done" in clean_status else "in_progress"
    
    conn = get_connection()
    c = conn.cursor()
    # Check if task_id matches id or partial title
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


def tool_add_vendor_quote(
    company_name: str,
    category: str,
    quote_amount: float,
    price_per_head: float = 0.0,
    details: str = "",
    contact_email: str = ""
) -> dict[str, Any]:
    """Add a new vendor quote or supplier comparison to the event database."""
    vnd_id = f"vnd-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO vendors (id, category, company_name, quote_amount, price_per_head, status, contact_email, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vnd_id, category, company_name, float(quote_amount), float(price_per_head), "quoted", contact_email, details)
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

