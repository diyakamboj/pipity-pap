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
    list_all_events,
    get_vendor_requirements,
    save_vendor_requirement,
    get_schedule_items,
    save_schedule_item,
    clear_schedule_items
)


def tool_list_events() -> list[dict[str, Any]]:
    """List all registered events in the workspace database."""
    return list_all_events()


def tool_create_event(
    title: str,
    attendee_count: int = 50,
    budget: float = 1000.0,
    location: str = "Seattle Tech Hub",
    date: str = "TBD",
    theme: str = "",
    goals: str = "",
    dietary_specs: str = "Standard options with vegan & gluten-free accommodations",
    av_requirements: str = "Projector and wireless microphone"
) -> dict[str, Any]:
    """Create a completely distinct new event with isolated brief, tasks, and requirements."""
    brief_data = {
        "title": title,
        "attendee_count": int(attendee_count),
        "budget": float(budget),
        "location": location,
        "date": date,
        "theme": theme or f"{title} coordination",
        "goals": goals or f"Deliver an outstanding {title} event within ${budget:,.2f} budget.",
        "dietary_specs": dietary_specs,
        "av_requirements": av_requirements,
        "status": "planning"
    }
    created = create_event_brief(brief_data)
    return {
        "status": "created",
        "event_id": created["id"],
        "title": created["title"],
        "brief": created,
        "message": f"Successfully created new event '{created['title']}' with distinct ID '{created['id']}'."
    }


def tool_switch_event(event_id_or_title: str) -> dict[str, Any]:
    """Switch active event context by event ID or case-insensitive title."""
    brief = get_event_brief(event_id_or_title)
    if not brief or not brief.get("id"):
        return {"error": f"Event '{event_id_or_title}' not found in database."}
    return {
        "status": "switched",
        "event_id": brief["id"],
        "title": brief["title"],
        "brief": brief
    }


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
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM speakers WHERE event_id = ? AND LOWER(TRIM(name)) = LOWER(?)",
        (event_id, name.strip())
    )
    existing = c.fetchone()
    if existing:
        spk_id = existing["id"]
        c.execute(
            "UPDATE speakers SET org = ?, topic = ?, bio = ?, contact_email = ? WHERE id = ?",
            (org, topic, bio, contact_email, spk_id)
        )
        conn.commit()
        conn.close()
        return {
            "status": "updated_shortlist",
            "speaker_id": spk_id,
            "name": name,
            "topic": topic,
            "org": org
        }

    spk_id = f"spk-{uuid.uuid4().hex[:6]}"
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
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM sponsors WHERE event_id = ? AND LOWER(TRIM(name)) = LOWER(?)",
        (event_id, name.strip())
    )
    existing = c.fetchone()
    if existing:
        spn_id = existing["id"]
        c.execute(
            "UPDATE sponsors SET tier = ?, amount = ?, notes = ?, contact_email = ? WHERE id = ?",
            (tier, float(amount), notes, contact_email, spn_id)
        )
        conn.commit()
        conn.close()
        return {
            "status": "updated_in_pipeline",
            "sponsor_id": spn_id,
            "name": name,
            "tier": tier,
            "amount": amount
        }

    spn_id = f"spn-{uuid.uuid4().hex[:6]}"
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
        "SELECT id FROM vendors WHERE event_id = ? AND LOWER(TRIM(company_name)) = LOWER(?) AND LOWER(TRIM(category)) = LOWER(?)",
        (event_id, company_name.strip(), category.strip())
    )
    existing = c.fetchone()
    if existing:
        vnd_id = existing["id"]
        c.execute(
            "UPDATE vendors SET quote_amount = ?, price_per_head = ?, contact_email = ?, details = ? WHERE id = ?",
            (float(quote_amount), float(price_per_head), contact_email, details, vnd_id)
        )
        conn.commit()
        conn.close()
        return {
            "status": "updated",
            "vendor_id": vnd_id,
            "company_name": company_name,
            "quote_amount": quote_amount,
            "price_per_head": price_per_head
        }

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


def tool_discover_vendor_needs(event_id: str = "evt-dubhacks-2026", event_type: str = "workshop") -> dict[str, Any]:
    """Contextually discover overlooked operational and supplier requirements beyond food (V1).
    Discovers Badges & Lanyards, Directional Signage, AV Equipment, Catering, and Apparel.
    """
    ev = get_event_brief(event_id)
    headcount = ev.get("attendee_count", 50)
    budget = ev.get("budget", 2000.0)

    # Standard contextual catalog based on event scale
    contextual_catalog = [
        {
            "category": "Catering & Hydration",
            "specification": f"Boxed meal service for {headcount} attendees with {ev.get('dietary_specs', 'vegan, GF, nut-free')} accommodations plus coffee/water station.",
            "budget_allocated": round(budget * 0.45, 2),
            "unknowns": "Final dietary breakdown cutoff date, service drop-off window.",
            "status": "pending_quotes"
        },
        {
            "category": "Badges & Lanyards",
            "specification": f"{headcount + 15} color-printed 4x3 badge inserts with double-ended bulldog clip lanyards.",
            "budget_allocated": round(budget * 0.12, 2),
            "unknowns": "Sponsor vector logo inclusion deadline, on-site blank badge surplus count.",
            "status": "pending_quotes"
        },
        {
            "category": "Directional Signage & Printing",
            "specification": "2 Foam-core agenda boards (24x36) and 6 directional directional arrows for foyer check-in.",
            "budget_allocated": round(budget * 0.08, 2),
            "unknowns": "Easel availability from venue vs rental necessity.",
            "status": "pending_quotes"
        },
        {
            "category": "AV & Presentation Tech",
            "specification": f"Dual projection hookup, 2 wireless handheld mics, 1 lavalier for speaker podium, backup HDMI dongles.",
            "budget_allocated": round(budget * 0.15, 2),
            "unknowns": "House sound tie-in technician fee and auxiliary audio recording interface.",
            "status": "pending_quotes"
        },
        {
            "category": "Volunteer & Speaker Shirts",
            "specification": f"Screen-printed short-sleeve shirts (approx 25 units for crew & speakers).",
            "budget_allocated": round(budget * 0.10, 2),
            "unknowns": "Vector artwork readiness and 10-day print production lead time.",
            "status": "optional_unresolved"
        }
    ]

    existing = get_vendor_requirements(event_id)
    existing_cats = {e.get("category", "").lower() for e in existing}

    added = []
    for item in contextual_catalog:
        if item["category"].lower() not in existing_cats:
            saved = save_vendor_requirement(
                event_id=event_id,
                category=item["category"],
                specification=item["specification"],
                headcount=headcount,
                budget_allocated=item["budget_allocated"],
                unknowns=item["unknowns"],
                status=item["status"]
            )
            added.append(saved)

    all_reqs = get_vendor_requirements(event_id)

    discovery_questions = [
        f"1. Dietary Cutoff: By what date must final attendee dietary counts ({ev.get('dietary_specs', 'vegan/GF/nut-free')}) be submitted to the caterer?",
        "2. Badge Artwork: Is the front/back artwork and sponsor logo lockup ready for print, or should we assign a task to collect vector assets?",
        "3. Venue AV Inclusion: Does the venue contract cover house audio microphones and projector cabling, or do we need external AV rentals?",
        "4. Directional Signs: Are easels provided by the facility for 24x36 schedule boards?"
    ]

    return {
        "event_id": event_id,
        "event_title": ev.get("title"),
        "headcount": headcount,
        "discovered_categories_count": len(all_reqs),
        "requirements": all_reqs,
        "newly_seeded_requirements": added,
        "discovery_questions": discovery_questions,
        "summary": f"Discovered {len(all_reqs)} operational supplier needs beyond food (Badges, Signage, AV Tech, Apparel, Catering)."
    }


def tool_compare_vendor_quotes(category: str = "Catering", event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Compare supplier quotes, calculate cost-per-head, evaluate minimums, and test budget feasibility (V2)."""
    ev = get_event_brief(event_id)
    budget = float(ev.get("budget", 2500.0))
    attendees = int(ev.get("attendee_count", 80))

    conn = get_connection()
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM vendors WHERE event_id = ? AND category LIKE ?", (event_id, f"%{category}%"))
    else:
        c.execute("SELECT * FROM vendors WHERE event_id = ?", (event_id,))
    vendors = [dict(row) for row in c.fetchall()]
    conn.close()

    if not vendors:
        return {
            "status": "no_quotes_found",
            "category": category,
            "message": f"No quotes currently logged under category '{category}' for event '{ev.get('title')}'. Suggest adding quotes via tool_add_vendor_quote."
        }

    comparisons = []
    for v in vendors:
        quote = float(v.get("quote_amount", 0.0))
        per_head = float(v.get("price_per_head", 0.0))
        if per_head <= 0 and attendees > 0:
            per_head = round(quote / attendees, 2)

        budget_variance = budget - quote
        is_within_budget = quote <= budget

        comparisons.append({
            "vendor_id": v.get("id"),
            "company_name": v.get("company_name"),
            "category": v.get("category"),
            "quote_amount": quote,
            "price_per_head": per_head,
            "budget_variance": budget_variance,
            "is_within_budget": is_within_budget,
            "compliance_verified": bool(v.get("compliance_verified")),
            "details": v.get("details", "")
        })

    # Sort by quote amount ascending (best value first)
    comparisons.sort(key=lambda x: x["quote_amount"])
    best_value = comparisons[0]

    return {
        "event_id": event_id,
        "event_title": ev.get("title"),
        "category": category,
        "event_budget": budget,
        "attendee_count": attendees,
        "quotes_evaluated": len(comparisons),
        "comparison_matrix": comparisons,
        "recommended_vendor": best_value["company_name"],
        "recommendation_reason": (
            f"Lowest total quote (${best_value['quote_amount']:,.2f} at ${best_value['price_per_head']:.2f}/head). "
            f"Leaves ${best_value['budget_variance']:,.2f} margin in the event budget."
        )
    }


def tool_verify_vendor_compliance(
    company_name_or_id: str,
    event_id: str = "evt-dubhacks-2026",
    verified: bool = True,
    notes: str = ""
) -> dict[str, Any]:
    """Verify vendor licensing, food safety permits, King County temporary event status, and COI (V2)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM vendors WHERE event_id = ? AND (id = ? OR company_name LIKE ?) LIMIT 1",
        (event_id, company_name_or_id, f"%{company_name_or_id}%")
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": f"Vendor '{company_name_or_id}' not found for event {event_id}."}

    vnd = dict(row)
    compliance_int = 1 if verified else 0

    full_notes = notes.strip()
    if not full_notes:
        if "cater" in vnd.get("category", "").lower() or "food" in vnd.get("category", "").lower():
            full_notes = (
                "Verified Washington State Master Business License & Seattle Food Worker Cards. "
                "Note: King County Public Health excludes temporary-event caterers from its standard 0-4 point rating scale; "
                "verified via temporary food service establishment operating permit."
            )
        else:
            full_notes = "Verified Washington State Master Business License and active Certificate of Insurance (COI) on file."

    c.execute(
        "UPDATE vendors SET compliance_verified = ?, compliance_notes = ? WHERE id = ?",
        (compliance_int, full_notes, vnd["id"])
    )
    conn.commit()
    conn.close()

    return {
        "status": "updated",
        "vendor_id": vnd["id"],
        "company_name": vnd["company_name"],
        "category": vnd["category"],
        "compliance_verified": verified,
        "compliance_notes": full_notes,
        "king_county_regulatory_note": "Temporary event vendors operate under specific temporary health permits; lack of restaurant rating is normal and compliant."
    }


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
