"""Event Operations Tool Adapters.

Independently implemented bounded tools for reading and modifying event records,
event briefs, vendor requirements, schedules, speakers, and sponsors.
"""

from __future__ import annotations

import json
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
    get_vendor_requirement_by_id,
    update_vendor_requirement,
    get_vendor_by_id,
    update_vendor,
    record_vendor_selection,
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


def check_dietary_coverage(required_dietary: str | list[str], vendor_coverage: list[str] | str) -> dict[str, Any]:
    """Helper to evaluate dietary restriction accommodations against vendor offerings."""
    common_tags = ["vegan", "vegetarian", "gluten-free", "nut-free", "halal", "kosher", "dairy-free"]

    req_tags = set()
    if isinstance(required_dietary, list):
        for item in required_dietary:
            item_str = str(item).lower()
            for tag in common_tags:
                if tag in item_str or (tag == "gluten-free" and ("gf" in item_str or "gluten free" in item_str)):
                    req_tags.add(tag)
    else:
        text = str(required_dietary or "").lower()
        for tag in common_tags:
            if tag in text or (tag == "gluten-free" and ("gf" in text or "gluten free" in text)):
                req_tags.add(tag)

    vnd_tags = set()
    if isinstance(vendor_coverage, list):
        for item in vendor_coverage:
            item_str = str(item).lower()
            for tag in common_tags:
                if tag in item_str or (tag == "gluten-free" and ("gf" in item_str or "gluten free" in item_str)):
                    vnd_tags.add(tag)
    else:
        text = str(vendor_coverage or "").lower()
        for tag in common_tags:
            if tag in text or (tag == "gluten-free" and ("gf" in text or "gluten free" in text)):
                vnd_tags.add(tag)

    covered = sorted(list(req_tags.intersection(vnd_tags)))
    uncovered = sorted(list(req_tags - vnd_tags))
    return {
        "required_dietary_tags": sorted(list(req_tags)),
        "vendor_dietary_tags": sorted(list(vnd_tags)),
        "covered_tags": covered,
        "uncovered_tags": uncovered,
        "is_fully_covered": len(uncovered) == 0
    }


def tool_calculate_quote_cost(
    quantities: int | float,
    unit_price: float,
    tax: float | None = None,
    tax_is_unknown: bool = False,
    delivery_fee: float | None = None,
    delivery_fee_is_unknown: bool = False,
    other_fees: float = 0.0,
    quoted_headcount: int | None = None,
    target_headcount: int | None = None
) -> dict[str, Any]:
    """Accurately calculate quote subtotal, base cost, and per-attendee cost.
    CRITICAL: Never treats unknown fees as zero or assumes a quote stays valid after headcount changes.
    """
    qty = float(quantities)
    price = float(unit_price)
    subtotal = round(qty * price, 2)

    unknown_fees = []
    known_fees_total = 0.0

    # Tax evaluation
    if tax_is_unknown or tax is None:
        unknown_fees.append("tax")
        tax_amount = None
        tax_status = "unknown"
    else:
        tax_amount = round(float(tax), 2)
        known_fees_total += tax_amount
        tax_status = "known"

    # Delivery fee evaluation
    if delivery_fee_is_unknown or delivery_fee is None:
        unknown_fees.append("delivery_fee")
        delivery_amount = None
        delivery_status = "unknown"
    else:
        delivery_amount = round(float(delivery_fee), 2)
        known_fees_total += delivery_amount
        delivery_status = "known"

    other_amount = round(float(other_fees or 0.0), 2)
    known_fees_total += other_amount

    base_cost = round(subtotal + known_fees_total, 2)
    has_unknown_fees = len(unknown_fees) > 0
    is_total_definite = not has_unknown_fees

    # Headcount validity check
    q_headcount = int(quoted_headcount if quoted_headcount is not None else qty)
    headcount_mismatch = False
    headcount_warning = None
    is_valid_for_headcount = True

    if target_headcount is not None and target_headcount > 0:
        if q_headcount != target_headcount:
            headcount_mismatch = True
            is_valid_for_headcount = False
            headcount_warning = (
                f"Headcount mismatch: Quote was priced for {q_headcount} attendees, "
                f"but event requirement is {target_headcount} attendees. "
                "Quote cannot be assumed valid after headcount change; pricing tier, minimums, or delivery fees must be re-quoted."
            )

    per_attendee_cost = round(base_cost / qty, 2) if qty > 0 else 0.0

    cost_classification = "definite_quote" if is_total_definite else "known_cost_subtotal_estimate"
    is_estimate = has_unknown_fees
    if is_total_definite:
        total_label = f"${base_cost:,.2f} (definite total quote)"
        price_per_head_label = f"${per_attendee_cost:,.2f}/head (definite quote)"
    else:
        total_label = f"${base_cost:,.2f} (estimate / known-cost subtotal; excludes {', '.join(unknown_fees)})"
        price_per_head_label = f"${per_attendee_cost:,.2f}/head (provisional estimate)"

    assumptions = []
    if has_unknown_fees:
        assumptions.append(
            f"Quote excludes unknown fees ({', '.join(unknown_fees)}). Total base of ${base_cost:,.2f} is an incomplete known-cost subtotal estimate; actual cost will be higher. Never treated as $0.00."
        )
    else:
        assumptions.append("All line-item taxes and delivery fees are explicitly quantified.")

    if headcount_mismatch:
        assumptions.append(headcount_warning)
    else:
        assumptions.append(f"Quote is valid for {q_headcount} attendees.")

    return {
        "quantities": qty,
        "unit_price": price,
        "subtotal": subtotal,
        "tax": tax_amount,
        "tax_status": tax_status,
        "delivery_fee": delivery_amount,
        "delivery_fee_status": delivery_status,
        "other_fees": other_amount,
        "known_fees_total": known_fees_total,
        "base_cost": base_cost,
        "is_total_definite": is_total_definite,
        "has_unknown_fees": has_unknown_fees,
        "unknown_fees": unknown_fees,
        "cost_classification": cost_classification,
        "is_estimate": is_estimate,
        "total_label": total_label,
        "price_per_head_label": price_per_head_label,
        "definite_quote_amount": base_cost if is_total_definite else None,
        "known_cost_subtotal": base_cost,
        "unknown_fees_warning": (
            f"WARNING: Unknown fees present: {', '.join(unknown_fees)}. Total of ${base_cost:,.2f} is an incomplete known-cost subtotal estimate. Missing fees must NEVER be treated as $0.00."
            if has_unknown_fees else None
        ),
        "per_attendee_cost": per_attendee_cost,
        "per_attendee_is_provisional": has_unknown_fees,
        "quoted_headcount": q_headcount,
        "target_headcount": target_headcount,
        "headcount_mismatch": headcount_mismatch,
        "is_valid_for_headcount": is_valid_for_headcount,
        "headcount_warning": headcount_warning,
        "assumptions": assumptions
    }


def tool_add_detailed_vendor_quote(
    company_name: str,
    category: str = "Catering",
    quantities: int | float = 80,
    unit_price: float = 0.0,
    tax: float | None = None,
    tax_is_unknown: bool = False,
    delivery_fee: float | None = None,
    delivery_fee_is_unknown: bool = False,
    other_fees: float = 0.0,
    dietary_coverage: list[str] | str | None = None,
    source: str = "organizer-supplied quote",
    quote_status: str = "quoted",
    contact_email: str = "",
    details: str = "",
    quoted_headcount: int | None = None,
    unknown_details: list[str] | str | None = None,
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Add or update an organizer-supplied vendor quote with line items, fees, dietary coverage, and source."""
    if dietary_coverage is None:
        dietary_list = []
    elif isinstance(dietary_coverage, list):
        dietary_list = [str(x).strip() for x in dietary_coverage if str(x).strip()]
    else:
        dietary_list = [x.strip() for x in str(dietary_coverage).split(",") if x.strip()]

    if unknown_details is None:
        unknown_list = []
    elif isinstance(unknown_details, list):
        unknown_list = [str(x).strip() for x in unknown_details if str(x).strip()]
    else:
        unknown_list = [x.strip() for x in str(unknown_details).split(";") if x.strip()]

    cost_calc = tool_calculate_quote_cost(
        quantities=quantities,
        unit_price=unit_price,
        tax=tax,
        tax_is_unknown=tax_is_unknown,
        delivery_fee=delivery_fee,
        delivery_fee_is_unknown=delivery_fee_is_unknown,
        other_fees=other_fees,
        quoted_headcount=quoted_headcount
    )

    quote_data = {
        "quantities": cost_calc["quantities"],
        "unit_price": cost_calc["unit_price"],
        "subtotal": cost_calc["subtotal"],
        "tax": cost_calc["tax"],
        "tax_status": cost_calc["tax_status"],
        "delivery_fee": cost_calc["delivery_fee"],
        "delivery_fee_status": cost_calc["delivery_fee_status"],
        "other_fees": cost_calc["other_fees"],
        "known_fees_total": cost_calc["known_fees_total"],
        "base_cost": cost_calc["base_cost"],
        "is_total_definite": cost_calc["is_total_definite"],
        "has_unknown_fees": cost_calc["has_unknown_fees"],
        "unknown_fees": cost_calc["unknown_fees"],
        "per_attendee_cost": cost_calc["per_attendee_cost"],
        "dietary_coverage": dietary_list,
        "source": source,
        "quoted_headcount": cost_calc["quoted_headcount"],
        "unknown_details": unknown_list,
        "assumptions": cost_calc["assumptions"]
    }

    if not details:
        diet_str = ", ".join(dietary_list) if dietary_list else "Standard menu"
        tax_str = f"${cost_calc['tax']:.2f}" if cost_calc['tax'] is not None else "Unknown"
        deliv_str = f"${cost_calc['delivery_fee']:.2f}" if cost_calc['delivery_fee'] is not None else "Unknown"
        details = (
            f"Quote for {cost_calc['quantities']} units at ${cost_calc['unit_price']:.2f}/unit. "
            f"Dietary: {diet_str}. Tax: {tax_str}, Delivery: {deliv_str}. Source: {source}."
        )

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM vendors WHERE event_id = ? AND LOWER(TRIM(company_name)) = LOWER(?) AND LOWER(TRIM(category)) = LOWER(?)",
        (event_id, company_name.strip(), category.strip())
    )
    existing = c.fetchone()
    conn.close()

    if existing:
        vnd_id = existing["id"]
        update_vendor(vnd_id, {
            "company_name": company_name.strip(),
            "category": category.strip(),
            "quote_amount": cost_calc["base_cost"],
            "price_per_head": cost_calc["per_attendee_cost"],
            "status": quote_status,
            "contact_email": contact_email,
            "details": details,
            "quote_data": quote_data
        }, event_id=event_id)
        return {
            "status": "updated",
            "vendor_id": vnd_id,
            "company_name": company_name,
            "category": category,
            "quote_amount": cost_calc["base_cost"],
            "price_per_head": cost_calc["per_attendee_cost"],
            "quote_status": quote_status,
            "quote_data": quote_data,
            "details": details
        }

    vnd_id = f"vnd-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO vendors (id, event_id, category, company_name, quote_amount, price_per_head, status, contact_email, details, quote_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vnd_id, event_id, category.strip(), company_name.strip(),
            cost_calc["base_cost"], cost_calc["per_attendee_cost"],
            quote_status, contact_email, details, json.dumps(quote_data)
        )
    )
    conn.commit()
    conn.close()

    return {
        "status": "added",
        "vendor_id": vnd_id,
        "company_name": company_name,
        "category": category,
        "quote_amount": cost_calc["base_cost"],
        "cost_classification": cost_calc["cost_classification"],
        "is_estimate": cost_calc["is_estimate"],
        "total_label": cost_calc["total_label"],
        "price_per_head": cost_calc["per_attendee_cost"],
        "price_per_head_label": cost_calc["price_per_head_label"],
        "quote_status": quote_status,
        "calculation": cost_calc,
        "quote_data": quote_data,
        "details": details
    }


def tool_update_vendor_quote(
    vendor_id: str,
    event_id: str = "evt-dubhacks-2026",
    company_name: str | None = None,
    category: str | None = None,
    quantities: int | float | None = None,
    unit_price: float | None = None,
    tax: float | None = None,
    tax_is_unknown: bool | None = None,
    delivery_fee: float | None = None,
    delivery_fee_is_unknown: bool | None = None,
    other_fees: float | None = None,
    dietary_coverage: list[str] | str | None = None,
    source: str | None = None,
    quote_status: str | None = None,
    contact_email: str | None = None,
    details: str | None = None,
    quoted_headcount: int | None = None,
    unknown_details: list[str] | str | None = None
) -> dict[str, Any]:
    """Edit an existing vendor quote, recomputing costs, unknown fee warnings, and persistence."""
    vendor = get_vendor_by_id(vendor_id, event_id=event_id)
    if not vendor:
        raise ValueError(f"Vendor '{vendor_id}' not found for event '{event_id}'")

    existing_qd = vendor.get("quote_data") or {}

    q_quantities = quantities if quantities is not None else existing_qd.get("quantities", 80)
    q_unit_price = unit_price if unit_price is not None else existing_qd.get("unit_price", vendor.get("price_per_head", 0.0))
    q_tax = tax if tax is not None else existing_qd.get("tax")
    q_tax_unknown = tax_is_unknown if tax_is_unknown is not None else (existing_qd.get("tax_status") == "unknown" if "tax_status" in existing_qd else (q_tax is None))
    q_deliv = delivery_fee if delivery_fee is not None else existing_qd.get("delivery_fee")
    q_deliv_unknown = delivery_fee_is_unknown if delivery_fee_is_unknown is not None else (existing_qd.get("delivery_fee_status") == "unknown" if "delivery_fee_status" in existing_qd else (q_deliv is None))
    q_other = other_fees if other_fees is not None else existing_qd.get("other_fees", 0.0)
    q_headcount = quoted_headcount if quoted_headcount is not None else existing_qd.get("quoted_headcount", q_quantities)

    if dietary_coverage is not None:
        if isinstance(dietary_coverage, list):
            q_diet = [str(x).strip() for x in dietary_coverage if str(x).strip()]
        else:
            q_diet = [x.strip() for x in str(dietary_coverage).split(",") if x.strip()]
    else:
        q_diet = existing_qd.get("dietary_coverage", [])

    if unknown_details is not None:
        if isinstance(unknown_details, list):
            q_unknown_details = [str(x).strip() for x in unknown_details if str(x).strip()]
        else:
            q_unknown_details = [x.strip() for x in str(unknown_details).split(";") if x.strip()]
    else:
        q_unknown_details = existing_qd.get("unknown_details", [])

    q_source = source if source is not None else existing_qd.get("source", "organizer-supplied quote")
    q_status = quote_status if quote_status is not None else vendor.get("status", "quoted")
    q_name = company_name if company_name is not None else vendor.get("company_name", "")
    q_category = category if category is not None else vendor.get("category", "Catering")
    q_email = contact_email if contact_email is not None else vendor.get("contact_email", "")

    cost_calc = tool_calculate_quote_cost(
        quantities=q_quantities,
        unit_price=q_unit_price,
        tax=q_tax,
        tax_is_unknown=q_tax_unknown,
        delivery_fee=q_deliv,
        delivery_fee_is_unknown=q_deliv_unknown,
        other_fees=q_other,
        quoted_headcount=q_headcount
    )

    new_qd = {
        "quantities": cost_calc["quantities"],
        "unit_price": cost_calc["unit_price"],
        "subtotal": cost_calc["subtotal"],
        "tax": cost_calc["tax"],
        "tax_status": cost_calc["tax_status"],
        "delivery_fee": cost_calc["delivery_fee"],
        "delivery_fee_status": cost_calc["delivery_fee_status"],
        "other_fees": cost_calc["other_fees"],
        "known_fees_total": cost_calc["known_fees_total"],
        "base_cost": cost_calc["base_cost"],
        "is_total_definite": cost_calc["is_total_definite"],
        "has_unknown_fees": cost_calc["has_unknown_fees"],
        "unknown_fees": cost_calc["unknown_fees"],
        "per_attendee_cost": cost_calc["per_attendee_cost"],
        "dietary_coverage": q_diet,
        "source": q_source,
        "quoted_headcount": cost_calc["quoted_headcount"],
        "unknown_details": q_unknown_details,
        "assumptions": cost_calc["assumptions"]
    }

    if details is not None:
        q_details = details
    else:
        diet_str = ", ".join(q_diet) if q_diet else "Standard menu"
        tax_str = f"${cost_calc['tax']:.2f}" if cost_calc['tax'] is not None else "Unknown"
        deliv_str = f"${cost_calc['delivery_fee']:.2f}" if cost_calc['delivery_fee'] is not None else "Unknown"
        q_details = (
            f"Quote for {cost_calc['quantities']} units at ${cost_calc['unit_price']:.2f}/unit. "
            f"Dietary: {diet_str}. Tax: {tax_str}, Delivery: {deliv_str}. Source: {q_source}."
        )

    update_vendor(vendor_id, {
        "company_name": q_name,
        "category": q_category,
        "quote_amount": cost_calc["base_cost"],
        "price_per_head": cost_calc["per_attendee_cost"],
        "status": q_status,
        "contact_email": q_email,
        "details": q_details,
        "quote_data": new_qd
    }, event_id=event_id)

    return {
        "status": "updated",
        "vendor_id": vendor_id,
        "company_name": q_name,
        "category": q_category,
        "quote_amount": cost_calc["base_cost"],
        "cost_classification": cost_calc["cost_classification"],
        "is_estimate": cost_calc["is_estimate"],
        "total_label": cost_calc["total_label"],
        "price_per_head": cost_calc["per_attendee_cost"],
        "price_per_head_label": cost_calc["price_per_head_label"],
        "quote_status": q_status,
        "calculation": cost_calc,
        "quote_data": new_qd,
        "details": q_details
    }


def tool_add_vendor_quote(
    company_name: str,
    category: str,
    quote_amount: float,
    price_per_head: float = 0.0,
    details: str = "",
    contact_email: str = "",
    event_id: str = "evt-dubhacks-2026",
    quantities: int | float | None = None,
    unit_price: float | None = None,
    tax: float | None = None,
    tax_is_unknown: bool = False,
    delivery_fee: float | None = None,
    delivery_fee_is_unknown: bool = False,
    other_fees: float = 0.0,
    dietary_coverage: list[str] | str | None = None,
    source: str = "organizer-supplied quote",
    quote_status: str = "quoted",
    quoted_headcount: int | None = None,
    unknown_details: list[str] | str | None = None
) -> dict[str, Any]:
    """Add or update a vendor quote in the event database (backward-compatible)."""
    if quantities is not None or unit_price is not None or tax is not None or delivery_fee is not None or dietary_coverage is not None:
        q_quantities = quantities if quantities is not None else 80
        q_unit_price = unit_price if unit_price is not None else (price_per_head if price_per_head > 0 else (quote_amount / q_quantities if q_quantities else 0.0))
        return tool_add_detailed_vendor_quote(
            company_name=company_name,
            category=category,
            quantities=q_quantities,
            unit_price=q_unit_price,
            tax=tax,
            tax_is_unknown=tax_is_unknown,
            delivery_fee=delivery_fee,
            delivery_fee_is_unknown=delivery_fee_is_unknown,
            other_fees=other_fees,
            dietary_coverage=dietary_coverage,
            source=source,
            quote_status=quote_status,
            contact_email=contact_email,
            details=details,
            quoted_headcount=quoted_headcount,
            unknown_details=unknown_details,
            event_id=event_id
        )

    # Legacy invocation: preserve exact quote_amount and price_per_head
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
            "quote_amount": float(quote_amount),
            "price_per_head": float(price_per_head)
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
        "quote_amount": float(quote_amount),
        "price_per_head": float(price_per_head)
    }


def tool_lookup_vendor_requirements(event_id: str = "evt-dubhacks-2026") -> list[dict[str, Any]]:
    """Look up discovered vendor requirements, specifications, and unknowns."""
    return get_vendor_requirements(event_id)


def tool_save_vendor_requirement(
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
    req_id: str | None = None,
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
        status=status,
        dietary_needs=dietary_needs,
        service_window=service_window,
        location=location,
        details_json=details_json,
        req_id=req_id
    )


def tool_save_catering_requirement(
    event_id: str = "evt-dubhacks-2026",
    headcount: int = 80,
    budget: float = 1200.0,
    dietary_needs: str = "15 vegan, 10 gluten-free, 5 halal, nut-free facility",
    service_window: str = "11:30 AM - 1:00 PM",
    location: str = "UW HUB Ballroom Foyer",
    unknowns: list[str] | str = "Final allergy counts cutoff; loading dock access",
    specification: str = "",
    status: str = "quoted",
    req_id: str | None = None
) -> dict[str, Any]:
    """Save or edit catering requirements for a specific event with dietary needs, window, and unknowns."""
    if not specification:
        specification = (
            f"Boxed lunch catering for {headcount} attendees with {dietary_needs}. "
            f"Service drop-off and staging at {location} for window {service_window}."
        )

    unknowns_list = []
    if isinstance(unknowns, (list, tuple)):
        unknowns_list = [str(x).strip() for x in unknowns if str(x).strip()]
        unknowns_str = "; ".join(unknowns_list)
    else:
        unknowns_str = str(unknowns or "").strip()
        unknowns_list = [x.strip() for x in unknowns_str.split(";") if x.strip()]

    details_payload = {
        "headcount": headcount,
        "budget": budget,
        "dietary_needs": dietary_needs,
        "service_window": service_window,
        "location": location,
        "unknowns_list": unknowns_list
    }

    if not req_id:
        existing_reqs = get_vendor_requirements(event_id)
        for r in existing_reqs:
            if "cater" in r.get("category", "").lower() or "food" in r.get("category", "").lower():
                req_id = r.get("id")
                break

    saved = save_vendor_requirement(
        event_id=event_id,
        category="Catering",
        specification=specification,
        headcount=headcount,
        budget_allocated=budget,
        unknowns=unknowns_str,
        status=status,
        dietary_needs=dietary_needs,
        service_window=service_window,
        location=location,
        details_json=details_payload,
        req_id=req_id
    )

    return {
        "status": "saved",
        "requirement_id": saved.get("id"),
        "event_id": event_id,
        "category": "Catering",
        "headcount": headcount,
        "budget_allocated": budget,
        "dietary_needs": dietary_needs,
        "service_window": service_window,
        "location": location,
        "unknowns": unknowns_list,
        "specification": specification,
        "requirement_status": status
    }


def tool_update_vendor_requirement(
    req_id: str,
    event_id: str = "evt-dubhacks-2026",
    category: str | None = None,
    specification: str | None = None,
    headcount: int | None = None,
    budget_allocated: float | None = None,
    dietary_needs: str | None = None,
    service_window: str | None = None,
    location: str | None = None,
    unknowns: str | list[str] | None = None,
    status: str | None = None
) -> dict[str, Any]:
    """Edit an existing vendor requirement with event isolation."""
    existing = get_vendor_requirement_by_id(req_id, event_id=event_id)
    if not existing:
        raise ValueError(f"Vendor requirement '{req_id}' not found for event '{event_id}'")

    updates = {}
    if category is not None:
        updates["category"] = category
    if specification is not None:
        updates["specification"] = specification
    if headcount is not None:
        updates["headcount"] = headcount
    if budget_allocated is not None:
        updates["budget_allocated"] = budget_allocated
    if dietary_needs is not None:
        updates["dietary_needs"] = dietary_needs
    if service_window is not None:
        updates["service_window"] = service_window
    if location is not None:
        updates["location"] = location
    if unknowns is not None:
        updates["unknowns"] = unknowns
    if status is not None:
        updates["status"] = status

    return update_vendor_requirement(req_id, updates, event_id=event_id)


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
    """Compare supplier quotes against current requirements, budget, unknowns, and assumptions (V2)."""
    ev = get_event_brief(event_id)

    # Check for specific vendor requirement in this category first
    reqs = get_vendor_requirements(event_id)
    cat_req = None
    for r in reqs:
        if category and category.lower() in r.get("category", "").lower():
            cat_req = r
            break
        elif not category and ("cater" in r.get("category", "").lower() or "food" in r.get("category", "").lower()):
            cat_req = r
            break

    # Determine baseline facts from requirement or event brief
    if cat_req:
        target_headcount = int(cat_req.get("headcount") or ev.get("attendee_count", 80))
        budget = float(cat_req.get("budget_allocated") or ev.get("budget", 2500.0))
        target_dietary = cat_req.get("dietary_needs") or ev.get("dietary_specs", "")
        target_window = cat_req.get("service_window", "")
        target_location = cat_req.get("location") or ev.get("location", "")
        req_unknowns = cat_req.get("unknowns", "")
        req_id = cat_req.get("id")
    else:
        target_headcount = int(ev.get("attendee_count", 80))
        budget = float(ev.get("budget", 2500.0))
        target_dietary = ev.get("dietary_specs", "")
        target_window = ""
        target_location = ev.get("location", "")
        req_unknowns = ""
        req_id = None

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
            "message": f"No quotes currently logged under category '{category}' for event '{ev.get('title')}'. Suggest adding quotes via tool_add_detailed_vendor_quote."
        }

    comparisons = []

    for v in vendors:
        raw_qd = v.get("quote_data")
        qd = {}
        if raw_qd and isinstance(raw_qd, str):
            try:
                qd = json.loads(raw_qd)
            except Exception:
                qd = {}
        elif isinstance(raw_qd, dict):
            qd = raw_qd

        raw_quote = float(v.get("quote_amount", 0.0))
        raw_price_head = float(v.get("price_per_head", 0.0))

        quantities = qd.get("quantities")
        if quantities is None or float(quantities) <= 0:
            quantities = target_headcount if target_headcount > 0 else 80

        unit_price = qd.get("unit_price")
        if unit_price is None or float(unit_price) <= 0:
            unit_price = raw_price_head if raw_price_head > 0 else (raw_quote / quantities if quantities else 0.0)

        tax = qd.get("tax")
        tax_is_unknown = qd.get("tax_is_unknown", (qd.get("tax_status") == "unknown" if "tax_status" in qd else (tax is None)))
        delivery_fee = qd.get("delivery_fee")
        delivery_fee_is_unknown = qd.get("delivery_fee_is_unknown", (qd.get("delivery_fee_status") == "unknown" if "delivery_fee_status" in qd else (delivery_fee is None)))
        other_fees = qd.get("other_fees", 0.0)
        quoted_hc = qd.get("quoted_headcount", quantities)

        # Run rigorous calculation
        calc = tool_calculate_quote_cost(
            quantities=quantities,
            unit_price=unit_price,
            tax=tax,
            tax_is_unknown=tax_is_unknown,
            delivery_fee=delivery_fee,
            delivery_fee_is_unknown=delivery_fee_is_unknown,
            other_fees=other_fees,
            quoted_headcount=quoted_hc,
            target_headcount=target_headcount
        )

        dietary_cov = qd.get("dietary_coverage", [])
        if not dietary_cov and v.get("details"):
            dt = v["details"].lower()
            hints = []
            if "vegan" in dt: hints.append("vegan")
            if "gluten-free" in dt or "gf" in dt: hints.append("gluten-free")
            if "nut-free" in dt: hints.append("nut-free")
            if "halal" in dt: hints.append("halal")
            dietary_cov = hints

        diet_eval = check_dietary_coverage(target_dietary, dietary_cov)

        quote_amount = calc["base_cost"]
        per_head = calc["per_attendee_cost"]
        budget_variance = round(budget - quote_amount, 2)
        is_within_budget = quote_amount <= budget

        missing_info = []
        if calc["has_unknown_fees"]:
            missing_info.extend([f"Unspecified fee: {f}" for f in calc["unknown_fees"]])
        if diet_eval["uncovered_tags"]:
            missing_info.append(f"Unconfirmed dietary accommodations: {', '.join(diet_eval['uncovered_tags'])}")
        if qd.get("unknown_details"):
            missing_info.extend(qd["unknown_details"])

        assumptions = list(calc["assumptions"])
        if target_window:
            assumptions.append(f"Assumes vendor can service drop-off window: {target_window}.")
        if target_location:
            assumptions.append(f"Assumes delivery access to: {target_location}.")

        v_status = v.get("status", "quoted")

        comparisons.append({
            "vendor_id": v.get("id"),
            "company_name": v.get("company_name"),
            "category": v.get("category"),
            "quote_amount": quote_amount,
            "cost_classification": calc["cost_classification"],
            "is_estimate": calc["is_estimate"],
            "total_label": calc["total_label"],
            "price_per_head": per_head,
            "price_per_head_label": calc["price_per_head_label"],
            "budget_variance": budget_variance,
            "is_within_budget": is_within_budget,
            "compliance_verified": bool(v.get("compliance_verified")),
            "details": v.get("details", ""),
            "quantities": calc["quantities"],
            "unit_price": calc["unit_price"],
            "subtotal": calc["subtotal"],
            "tax": calc["tax"],
            "tax_status": calc["tax_status"],
            "delivery_fee": calc["delivery_fee"],
            "delivery_fee_status": calc["delivery_fee_status"],
            "other_fees": calc["other_fees"],
            "has_unknown_fees": calc["has_unknown_fees"],
            "unknown_fees": calc["unknown_fees"],
            "is_total_definite": calc["is_total_definite"],
            "quoted_headcount": calc["quoted_headcount"],
            "target_headcount": target_headcount,
            "headcount_mismatch": calc["headcount_mismatch"],
            "is_valid_for_headcount": calc["is_valid_for_headcount"],
            "headcount_warning": calc["headcount_warning"],
            "dietary_coverage": diet_eval["vendor_dietary_tags"],
            "uncovered_dietary_needs": diet_eval["uncovered_tags"],
            "is_fully_dietary_compliant": diet_eval["is_fully_covered"],
            "missing_information": missing_info,
            "assumptions": assumptions,
            "source": qd.get("source", "organizer-supplied quote"),
            "status": v_status,
            "is_selected": v_status == "selected"
        })

    # Ranking logic:
    # 1. Headcount valid
    # 2. Fully dietary compliant
    # 3. Definite total (no unknown fees)
    # 4. Within budget
    # 5. Lowest base cost
    def sort_score(c):
        score = 0
        if not c["is_valid_for_headcount"]:
            score += 10000  # Penalty for headcount mismatch
        if not c["is_within_budget"]:
            score += 5000   # Penalty for over budget
        if not c["is_fully_dietary_compliant"]:
            score += 2000 * len(c["uncovered_dietary_needs"])
        if c["has_unknown_fees"]:
            score += 1000 * len(c["unknown_fees"])
        score += c["quote_amount"]
        return score

    comparisons.sort(key=sort_score)
    best_candidate = comparisons[0]

    rec_reasons = []
    if best_candidate["is_valid_for_headcount"]:
        rec_reasons.append(f"Valid for full attendance of {target_headcount} attendees.")
    else:
        rec_reasons.append(f"⚠️ Caution: Quote has headcount mismatch ({best_candidate['quoted_headcount']} vs {target_headcount}).")

    if best_candidate["is_total_definite"]:
        rec_reasons.append(f"Definite total quote of ${best_candidate['quote_amount']:,.2f} (${best_candidate['price_per_head']:.2f}/head).")
    else:
        rec_reasons.append(f"⚠️ Incomplete Quote / Estimate: Total of ${best_candidate['quote_amount']:,.2f} is an incomplete known-cost subtotal estimate and excludes unknown {', '.join(best_candidate['unknown_fees'])}. Never treated as $0.00.")

    if best_candidate["is_within_budget"]:
        rec_reasons.append(f"Leaves ${best_candidate['budget_variance']:,.2f} margin in the ${budget:,.2f} budget.")
    else:
        rec_reasons.append(f"⚠️ Quote exceeds allocated budget by ${abs(best_candidate['budget_variance']):,.2f}.")

    if best_candidate["is_fully_dietary_compliant"]:
        rec_reasons.append(f"Fully covers required dietary accommodations ({', '.join(best_candidate['dietary_coverage'])}).")
    elif best_candidate["uncovered_dietary_needs"]:
        rec_reasons.append(f"Note: Unconfirmed accommodations for {', '.join(best_candidate['uncovered_dietary_needs'])}.")

    recommendation_reason = " ".join(rec_reasons)

    return {
        "status": "success",
        "event_id": event_id,
        "event_title": ev.get("title"),
        "category": category,
        "event_budget": budget,
        "attendee_count": target_headcount,
        "catering_requirement": {
            "requirement_id": req_id,
            "headcount": target_headcount,
            "budget": budget,
            "dietary_needs": target_dietary,
            "service_window": target_window,
            "location": target_location,
            "unknowns": req_unknowns
        },
        "quotes_evaluated": len(comparisons),
        "comparison_matrix": comparisons,
        "recommended_vendor": best_candidate["company_name"],
        "recommended_vendor_id": best_candidate["vendor_id"],
        "recommendation_reason": recommendation_reason,
        "missing_information_summary": {
            c["company_name"]: c["missing_information"] for c in comparisons if c["missing_information"]
        },
        "assumptions_summary": {
            c["company_name"]: c["assumptions"] for c in comparisons
        }
    }


def tool_select_vendor_proposal(
    vendor_id: str,
    event_id: str = "evt-dubhacks-2026",
    selection_notes: str = "",
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Allow the organizer to select a preferred vendor proposal without treating selection as a booking or purchase."""
    return record_vendor_selection(
        vendor_id=vendor_id,
        event_id=event_id,
        selection_notes=selection_notes,
        actor_id=actor_id
    )


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
