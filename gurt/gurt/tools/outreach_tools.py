"""Outreach & Human-In-The-Loop Approval Tool Adapter.

Ensures that drafts are NEVER sent automatically. Consequential actions
are recorded as action proposals and require human confirmation.
Prevents duplicate pending actions and allows draft editing before approval.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any
import httpx
from gurt.config import settings
from gurt.db import (
    get_connection,
    get_event_brief,
    get_action_proposal,
    update_action_proposal,
    record_action_approval,
    list_action_proposals,
    log_audit_event
)


def tool_compose_outreach_draft(
    target_type: str,
    target_id_or_name: str,
    event_id: str = "evt-dubhacks-2026",
    custom_instructions: str = "",
    recipient_email: str | None = None,
    recipient_name: str | None = None,
    save_as_draft_only: bool = False,
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Generate a draft outreach email for a speaker, sponsor, or vendor using saved event facts.
    Saves the generated draft as a pending action proposal with event isolation.
    """
    ev = get_event_brief(event_id)
    event_title = ev.get("title", "Event")
    event_date = ev.get("date", "Upcoming")
    event_location = ev.get("location", "UW Campus Venue")
    event_attendees = ev.get("attendee_count", 80)
    event_dietary = ev.get("dietary_specs", "vegan, gluten-free, nut-free")

    clean_target = target_type.lower().strip()
    target_rec_name = recipient_name or ""
    target_rec_email = recipient_email or ""
    subject = ""
    message_body = ""
    action_type = "speaker_outreach"
    facts_used = {
        "event_title": event_title,
        "event_date": event_date,
        "event_location": event_location,
        "event_attendees": event_attendees
    }

    speaker = None
    sponsor = None
    vendor = None
    req_row = None

    conn = get_connection()
    c = conn.cursor()
    try:
        if clean_target in ("speaker", "keynote", "presenter"):
            action_type = "speaker_outreach"
            c.execute(
                "SELECT * FROM speakers WHERE event_id = ? AND (id = ? OR LOWER(TRIM(name)) = LOWER(?))",
                (event_id, target_id_or_name.strip(), target_id_or_name.strip())
            )
            rows = c.fetchall()
            if not rows:
                c.execute(
                    "SELECT * FROM speakers WHERE event_id = ? AND name LIKE ?",
                    (event_id, f"%{target_id_or_name.strip()}%")
                )
                rows = c.fetchall()
            if rows:
                speaker = dict(rows[0])

        elif clean_target in ("sponsor", "partner"):
            action_type = "sponsor_outreach"
            c.execute(
                "SELECT * FROM sponsors WHERE event_id = ? AND (id = ? OR LOWER(TRIM(name)) = LOWER(?))",
                (event_id, target_id_or_name.strip(), target_id_or_name.strip())
            )
            rows = c.fetchall()
            if not rows:
                c.execute(
                    "SELECT * FROM sponsors WHERE event_id = ? AND name LIKE ?",
                    (event_id, f"%{target_id_or_name.strip()}%")
                )
                rows = c.fetchall()
            if rows:
                sponsor = dict(rows[0])

        elif clean_target in ("vendor", "catering", "caterer", "supplier"):
            action_type = "vendor_quote_approval"
            c.execute(
                "SELECT * FROM vendors WHERE event_id = ? AND (id = ? OR LOWER(TRIM(company_name)) = LOWER(?))",
                (event_id, target_id_or_name.strip(), target_id_or_name.strip())
            )
            rows = c.fetchall()
            if not rows:
                c.execute(
                    "SELECT * FROM vendors WHERE event_id = ? AND company_name LIKE ?",
                    (event_id, f"%{target_id_or_name.strip()}%")
                )
                rows = c.fetchall()
            if rows:
                vendor = dict(rows[0])

            c.execute("SELECT * FROM vendor_requirements WHERE event_id = ? AND category LIKE '%cater%' LIMIT 1", (event_id,))
            req_rows = c.fetchall()
            if req_rows:
                req_row = dict(req_rows[0])
        else:
            raise ValueError(f"Unsupported target_type '{target_type}'. Must be 'speaker', 'sponsor', or 'vendor'.")
    finally:
        c.close()
        conn.close()

    if clean_target in ("speaker", "keynote", "presenter"):
        if not speaker and not target_rec_email:
            raise ValueError(f"Speaker '{target_id_or_name}' not found for event '{event_id}'")

        if speaker:
            target_rec_name = target_rec_name or speaker.get("name", "Speaker")
            target_rec_email = target_rec_email or speaker.get("contact_email") or f"{target_rec_name.lower().replace(' ', '.')}@example.org"
            topic = speaker.get("topic") or "Keynote Presentation"
            org = speaker.get("org") or "Guest Institution"
            proposed_time = speaker.get("proposed_time") or "10:00 AM - 10:45 AM"
        else:
            target_rec_name = target_rec_name or target_id_or_name
            topic = "Guest Presentation"
            org = "Industry"
            proposed_time = "10:00 AM - 10:45 AM"

        facts_used.update({
            "speaker_name": target_rec_name,
            "speaker_topic": topic,
            "speaker_org": org,
            "proposed_time": proposed_time
        })

        subject = f"Speaker Invitation: {event_title} — {topic}"
        message_body = (
            f"Dear {target_rec_name},\n\n"
            f"On behalf of the organizing team for {event_title}, we would be honored to invite you to present on "
            f"'{topic}' ({org}) at our upcoming workshop on {event_date} at {event_location}.\n\n"
            f"We are expecting approximately {event_attendees} attendees comprising students, researchers, and engineers. "
            f"We have reserved a proposed session slot for you at {proposed_time}.\n\n"
            f"Please let us know if this time slot works for your schedule, and if you have any dietary accommodations "
            f"({event_dietary}) or special presentation requirements.\n\n"
            f"Warm regards,\n{event_title} Organizing Committee"
        )

    elif clean_target in ("sponsor", "partner"):
        if not sponsor and not target_rec_email:
            raise ValueError(f"Sponsor '{target_id_or_name}' not found for event '{event_id}'")

        if sponsor:
            target_rec_name = target_rec_name or sponsor.get("name", "Sponsor")
            target_rec_email = target_rec_email or sponsor.get("contact_email") or f"partnerships@{target_rec_name.lower().replace(' ', '')}.com"
            tier = sponsor.get("tier", "Silver")
            amount = float(sponsor.get("amount", 1500.0))
        else:
            target_rec_name = target_rec_name or target_id_or_name
            tier = "Silver"
            amount = 1500.0

        facts_used.update({
            "sponsor_name": target_rec_name,
            "tier": tier,
            "amount": amount
        })

        subject = f"Partnership Opportunity: {event_title} — {tier} Tier Sponsorship"
        message_body = (
            f"Dear {target_rec_name} Partnerships Team,\n\n"
            f"We are writing to invite {target_rec_name} to partner with us for {event_title}, taking place on {event_date} "
            f"at {event_location}.\n\n"
            f"Our workshop brings together {event_attendees} top collegiate builders and researchers. We would love to offer you "
            f"our {tier} Tier sponsorship package (${amount:,.0f}), which includes branded booth presence, keynote stage acknowledgment, "
            f"and direct recruiting engagement with all participants.\n\n"
            f"Please let us know if you would like to discuss this opportunity or if we can send over our sponsorship prospectus.\n\n"
            f"Best regards,\n{event_title} Sponsorship Team"
        )

    elif clean_target in ("vendor", "catering", "caterer", "supplier"):
        if not vendor and not target_rec_email:
            raise ValueError(f"Vendor '{target_id_or_name}' not found for event '{event_id}'")

        cater_dietary = event_dietary
        service_window = "11:30 AM - 1:00 PM"
        cater_loc = event_location
        if req_row:
            cater_dietary = req_row.get("dietary_needs") or cater_dietary
            service_window = req_row.get("service_window") or service_window
            cater_loc = req_row.get("location") or cater_loc

        if vendor:
            target_rec_name = target_rec_name or vendor.get("company_name", "Vendor")
            target_rec_email = target_rec_email or vendor.get("contact_email") or f"orders@{target_rec_name.lower().replace(' ', '')}.com"
            category = vendor.get("category", "Catering")
            quote_amount = float(vendor.get("quote_amount", 0.0))
            price_head = float(vendor.get("price_per_head", 0.0))
        else:
            target_rec_name = target_rec_name or target_id_or_name
            category = "Catering"
            quote_amount = 0.0
            price_head = 0.0

        facts_used.update({
            "vendor_name": target_rec_name,
            "category": category,
            "quote_amount": quote_amount,
            "price_per_head": price_head,
            "dietary_needs": cater_dietary,
            "service_window": service_window
        })

        subject = f"Order Inquiry & Dietary Specifications: {event_title} — {category}"
        message_body = (
            f"Hello {target_rec_name} Orders Team,\n\n"
            f"We are coordinating operational logistics for {event_title} scheduled on {event_date} at {cater_loc}.\n\n"
            f"We are reviewing your quote of ${quote_amount:,.2f} (${price_head:.2f}/head) for {event_attendees} attendees. "
            f"Please confirm that you can accommodate our service drop-off window ({service_window}) and our required dietary "
            f"accommodations: {cater_dietary}.\n\n"
            f"Please reply with an updated itemized proposal and delivery access instructions.\n\n"
            f"Thank you,\n{event_title} Operations Team"
        )

    if custom_instructions:
        message_body += f"\n\nSpecial Note: {custom_instructions}"

    init_status = "draft" if save_as_draft_only else "pending_approval"
    init_delivery_status = "draft" if save_as_draft_only else "pending approval"

    draft_result = tool_draft_outreach(
        recipient_name=target_rec_name,
        recipient_email=target_rec_email,
        subject=subject,
        message_body=message_body,
        action_type=action_type,
        event_id=event_id,
        status=init_status,
        delivery_status=init_delivery_status,
        actor_id=actor_id
    )

    draft_result["target_type"] = clean_target
    draft_result["target_id_or_name"] = target_id_or_name
    draft_result["facts_used"] = facts_used
    return draft_result


def tool_draft_outreach(
    recipient_name: str,
    recipient_email: str,
    subject: str,
    message_body: str,
    action_type: str = "speaker_outreach",
    event_id: str = "evt-dubhacks-2026",
    status: str = "pending_approval",
    delivery_status: str = "pending approval",
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Draft an outreach message or proposal for human review. Does NOT send.
    Checks for existing pending drafts to prevent duplicate actions.
    """
    conn = get_connection()
    c = conn.cursor()

    # Duplicate check: Is there already a pending action for this recipient and action_type?
    c.execute(
        "SELECT * FROM action_proposals WHERE event_id = ? AND action_type = ? AND status IN ('pending_approval', 'draft')",
        (event_id, action_type)
    )
    existing_rows = [dict(r) for r in c.fetchall()]
    for row in existing_rows:
        try:
            p = json.loads(row["payload"])
            if p.get("recipient_email", "").lower() == recipient_email.lower():
                # Found existing pending draft - update it instead of creating unintended duplicates
                p["subject"] = subject
                p["message_body"] = message_body
                p["recipient_name"] = recipient_name
                now = datetime.now().isoformat()
                c.execute(
                    """
                    UPDATE action_proposals
                    SET title = ?, summary = ?, payload = ?, delivery_status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        f"Outreach to {recipient_name} ({subject})",
                        f"Proposed message to {recipient_email} regarding {subject}",
                        json.dumps(p),
                        delivery_status,
                        now,
                        row["id"]
                    )
                )
                conn.commit()
                conn.close()

                log_audit_event(
                    event_id=event_id,
                    actor_id=actor_id,
                    action="update_outreach_draft",
                    target_type="action_proposal",
                    target_id=row["id"],
                    details={"action_id": row["id"], "recipient": recipient_email, "is_duplicate_prevented": True}
                )

                return {
                    "action_id": row["id"],
                    "status": row["status"],
                    "delivery_status": delivery_status,
                    "approval_status": "pending",
                    "title": f"Outreach to {recipient_name} ({subject})",
                    "recipient": f"{recipient_name} <{recipient_email}>",
                    "subject": subject,
                    "preview": message_body[:200] + ("..." if len(message_body) > 200 else ""),
                    "full_body": message_body,
                    "is_duplicate_prevented": True,
                    "warning": "EXISTING PENDING DRAFT UPDATED. No message has been sent. Awaiting organizer approval in the Action Center."
                }
        except Exception:
            pass

    action_id = f"act-{uuid.uuid4().hex[:6]}"
    title = f"Outreach to {recipient_name} ({subject})"
    summary = f"Proposed message to {recipient_email} regarding {subject}"

    payload = {
        "recipient_name": recipient_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "message_body": message_body,
        "action_type": action_type
    }

    appr_status = "draft" if status == "draft" else "pending"

    c.execute(
        """
        INSERT INTO action_proposals (
            id, event_id, action_type, title, summary, payload, status,
            delivery_status, approval_status, delivery_mode
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id, event_id, action_type, title, summary,
            json.dumps(payload), status, delivery_status, appr_status, "simulated"
        )
    )
    conn.commit()
    conn.close()

    log_audit_event(
        event_id=event_id,
        actor_id=actor_id,
        action="create_outreach_draft",
        target_type="action_proposal",
        target_id=action_id,
        details={"action_id": action_id, "recipient": recipient_email, "action_type": action_type}
    )

    return {
        "action_id": action_id,
        "status": status,
        "delivery_status": delivery_status,
        "approval_status": appr_status,
        "title": title,
        "recipient": f"{recipient_name} <{recipient_email}>",
        "subject": subject,
        "preview": message_body[:200] + ("..." if len(message_body) > 200 else ""),
        "full_body": message_body,
        "is_duplicate_prevented": False,
        "warning": "DRAFT CREATED. No message has been sent. Awaiting organizer approval in the Action Center."
    }


def tool_update_draft(
    action_id: str,
    subject: str | None = None,
    message_body: str | None = None,
    recipient_email: str | None = None,
    recipient_name: str | None = None,
    event_id: str | None = None,
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Edit an existing outreach draft before organizer approval with event boundary checks."""
    conn = get_connection()
    c = conn.cursor()
    if event_id:
        c.execute("SELECT * FROM action_proposals WHERE id = ? AND event_id = ?", (action_id, event_id))
    else:
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] not in ("pending_approval", "draft"):
        conn.close()
        return {"error": f"Cannot edit action {action_id} in state '{action['status']}'. Only pending actions can be edited."}

    try:
        payload = json.loads(action["payload"])
    except Exception:
        payload = {}

    if subject:
        payload["subject"] = subject
    if message_body:
        payload["message_body"] = message_body
        payload["message"] = message_body
    if recipient_email:
        payload["recipient_email"] = recipient_email
    if recipient_name:
        payload["recipient_name"] = recipient_name

    rec_name = payload.get("recipient_name", "Contact")
    sub = payload.get("subject", "Communication")
    action_title = f"Outreach to {rec_name} ({sub})"
    summary = f"Proposed message to {payload.get('recipient_email', '')} regarding {sub}"

    now = datetime.now().isoformat()
    c.execute(
        """
        UPDATE action_proposals
        SET title = ?, summary = ?, payload = ?, updated_at = ?
        WHERE id = ?
        """,
        (action_title, summary, json.dumps(payload), now, action_id)
    )
    conn.commit()
    conn.close()

    log_audit_event(
        event_id=action.get("event_id", "evt-dubhacks-2026"),
        actor_id=actor_id,
        action="edit_outreach_draft",
        target_type="action_proposal",
        target_id=action_id,
        details={"action_id": action_id, "updated_fields": [k for k in ("subject", "message_body", "recipient_email", "recipient_name") if locals().get(k) is not None]}
    )

    return {
        "action_id": action_id,
        "status": action["status"],
        "delivery_status": action.get("delivery_status", "pending approval"),
        "title": action_title,
        "payload": payload,
        "updated": True
    }


def tool_draft_slack_message(channel: str, message: str, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Prepare a Slack message draft on the organizer's behalf for approval."""
    conn = get_connection()
    c = conn.cursor()

    # Check for existing pending slack message in the same channel
    c.execute(
        "SELECT * FROM action_proposals WHERE event_id = ? AND action_type = 'slack_message' AND status = 'pending_approval'",
        (event_id,)
    )
    for row in [dict(r) for r in c.fetchall()]:
        try:
            p = json.loads(row["payload"])
            if p.get("channel") == channel:
                p["message"] = message
                c.execute("UPDATE action_proposals SET payload = ? WHERE id = ?", (json.dumps(p), row["id"]))
                conn.commit()
                conn.close()
                return {
                    "action_id": row["id"],
                    "status": "pending_approval",
                    "title": row["title"],
                    "channel": channel,
                    "full_body": message,
                    "is_duplicate_prevented": True,
                    "warning": "EXISTING PENDING SLACK DRAFT UPDATED. Awaiting organizer approval in the Action Center."
                }
        except Exception:
            pass

    action_id = f"act-{uuid.uuid4().hex[:6]}"
    title = f"Slack Message to {channel}"
    summary = f"Drafted Slack communication to {channel}"
    payload = {
        "channel": channel,
        "message": message,
        "action_type": "slack_message"
    }

    c.execute(
        """
        INSERT INTO action_proposals (id, event_id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (action_id, event_id, "slack_message", title, summary, json.dumps(payload), "pending_approval")
    )
    conn.commit()
    conn.close()
    return {
        "action_id": action_id,
        "status": "pending_approval",
        "title": title,
        "channel": channel,
        "full_body": message,
        "is_duplicate_prevented": False,
        "warning": "DRAFT CREATED. No message has been sent. Awaiting organizer approval in the Action Center."
    }


def tool_draft_teams_message(recipient: str, message: str, event_id: str = "evt-dubhacks-2026") -> dict[str, Any]:
    """Prepare a Microsoft Teams message draft on the organizer's behalf for approval."""
    action_id = f"act-{uuid.uuid4().hex[:6]}"
    title = f"Teams Message to {recipient}"
    summary = f"Drafted Teams communication to {recipient}"
    payload = {
        "recipient": recipient,
        "message": message,
        "action_type": "teams_message"
    }

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO action_proposals (id, event_id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (action_id, event_id, "teams_message", title, summary, json.dumps(payload), "pending_approval")
    )
    conn.commit()
    conn.close()
    return {
        "action_id": action_id,
        "status": "pending_approval",
        "title": title,
        "recipient": recipient,
        "full_body": message,
        "warning": "DRAFT CREATED. No message has been sent. Awaiting organizer approval in the Action Center."
    }


def dismiss_action(
    action_id: str,
    event_id: str | None = None,
    actor_id: str = "organizer"
) -> dict[str, Any]:
    """Reject or dismiss an action proposal without sending."""
    conn = get_connection()
    c = conn.cursor()
    if event_id:
        c.execute("SELECT * FROM action_proposals WHERE id = ? AND event_id = ?", (action_id, event_id))
    else:
        c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] == "executed":
        conn.close()
        return {"error": f"Cannot dismiss action {action_id} in state 'executed'."}

    now = datetime.now().isoformat()
    c.execute(
        """
        UPDATE action_proposals
        SET status = 'dismissed', approval_status = 'dismissed', delivery_status = 'dismissed', updated_at = ?
        WHERE id = ?
        """,
        (now, action_id)
    )
    conn.commit()
    conn.close()

    log_audit_event(
        event_id=action.get("event_id", "evt-dubhacks-2026"),
        actor_id=actor_id,
        action="dismiss_action_proposal",
        target_type="action_proposal",
        target_id=action_id,
        details={"action_id": action_id, "previous_status": action["status"]}
    )

    return {
        "action_id": action_id,
        "status": "dismissed",
        "approval_status": "dismissed",
        "delivery_status": "dismissed"
    }


def tool_approve_outreach(
    action_id: str,
    event_id: str | None = None,
    actor_id: str = "organizer",
    dispatch_now: bool = True,
    force_simulation: bool = True,
    simulate_failure: bool = False,
    simulate_unconfirmed: bool = False
) -> dict[str, Any]:
    """Approve an outreach draft. If dispatch_now is True, proceeds to execute/dispatch the approved action."""
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
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] == "executed":
        log_audit_event(
            event_id=action.get("event_id", "evt-dubhacks-2026"),
            actor_id="gurt_agent",
            action="approved_action_execution",
            target_type="activity",
            target_id=action_id,
            details={
                "status": "failed",
                "summary": "Approved action execution was rejected because it was not pending approval.",
                "affected_record_ids": [action_id]
            }
        )
        return {
            "error": f"Action {action_id} is already in state '{action['status']}'. Only pending actions can be approved."
        }

    if action["status"] == "dismissed":
        return {
            "error": f"Cannot approve dismissed action {action_id}."
        }

    now = datetime.now().isoformat()
    record_action_approval(action_id, actor_id=actor_id, event_id=event_id)

    if not dispatch_now:
        return {
            "action_id": action_id,
            "status": "approved",
            "approval_status": "approved",
            "delivery_status": "approved",
            "approved_by": actor_id,
            "approved_at": now,
            "title": action.get("title", ""),
            "event_id": action.get("event_id", "")
        }

    return execute_approved_action(
        action_id=action_id,
        event_id=event_id,
        actor_id=actor_id,
        force_simulation=force_simulation,
        simulate_failure=simulate_failure,
        simulate_unconfirmed=simulate_unconfirmed
    )


def tool_dispatch_approved_action(
    action_id: str,
    event_id: str | None = None,
    actor_id: str = "organizer",
    force_simulation: bool = True,
    simulate_failure: bool = False,
    simulate_unconfirmed: bool = False
) -> dict[str, Any]:
    """Dispatch an explicitly approved action proposal. Rejects drafts or unapproved actions directly."""
    return execute_approved_action(
        action_id=action_id,
        event_id=event_id,
        actor_id=actor_id,
        force_simulation=force_simulation,
        simulate_failure=simulate_failure,
        simulate_unconfirmed=simulate_unconfirmed,
        require_approved=True
    )


def execute_approved_action(
    action_id: str,
    event_id: str | None = None,
    actor_id: str = "organizer",
    force_simulation: bool = True,
    simulate_failure: bool = False,
    simulate_unconfirmed: bool = False,
    require_approved: bool = False
) -> dict[str, Any]:
    """Execute a previously approved action proposal via external provider or recorded delivery."""
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
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] == "draft" or action.get("approval_status") == "draft":
        return {
            "error": f"Cannot dispatch unapproved draft action {action_id}. Action must be submitted and approved before dispatch."
        }

    if action["status"] == "executed":
        return {
            "error": f"Action {action_id} is already in state 'executed'. Only pending actions can be approved."
        }

    if action["status"] == "dismissed":
        return {
            "error": f"Cannot dispatch dismissed action {action_id}."
        }

    # Explicit approval requirement: only persisted 'approved' proposals can be dispatched
    if action["status"] != "approved" or action.get("approval_status") != "approved":
        return {
            "error": f"Cannot execute unapproved action {action_id} in state '{action['status']}'. Explicit organizer approval is required before execution."
        }

    if not action.get("approved_at") or not action.get("approved_by"):
        return {
            "error": f"Cannot execute action {action_id}: missing persisted approval audit record (approved_at / approved_by)."
        }

    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE action_proposals
            SET status = 'executing', updated_at = ?
            WHERE id = ? AND status = 'approved'
            """,
            (now, action_id)
        )
        if c.rowcount == 0:
            return {
                "error": f"Action {action_id} could not be executed: status is not 'approved' or action is already executing/executed."
            }
        conn.commit()
    finally:
        conn.close()

    try:
        payload = json.loads(action["payload"])
    except Exception:
        payload = {}

    approved_by = action.get("approved_by") or actor_id
    approved_at = action.get("approved_at") or now
    execution_result = {}
    delivery_status = "simulated delivery"
    delivery_mode = "simulated"
    is_real_sent = False

    is_email = action["action_type"] in (
        "speaker_outreach", "sponsor_outreach", "vendor_quote_approval", "vendor_outreach"
    )

    if is_email:
        recipient_email = payload.get("recipient_email", "")
        recipient_name = payload.get("recipient_name", "")
        subject = payload.get("subject", "")
        body = payload.get("message_body", "")

        is_test = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules) or ("unittest" in sys.modules)
        is_production = (os.getenv("GURT_ENV") == "production")
        allow_real = (os.getenv("GURT_ALLOW_REAL_EMAIL", "").lower() in ("true", "1"))
        has_real_resend_key = bool(settings.resend_api_key and not settings.resend_api_key.startswith("re_dummy"))

        can_send_real = (
            is_production and
            allow_real and
            not force_simulation and
            not is_test and
            has_real_resend_key
        )

        if simulate_failure:
            delivery_status = "failed"
            delivery_mode = "failed"
            is_real_sent = False
            execution_result = {
                "provider": "Mock Dispatcher",
                "status": "failed",
                "delivery_status": "failed",
                "delivery_mode": "failed",
                "error": "Simulated external provider connection failure or HTTP 500.",
                "is_real_sent": False,
                "is_simulated": True
            }
        elif simulate_unconfirmed:
            delivery_status = "delivery unconfirmed"
            delivery_mode = "simulated"
            is_real_sent = False
            execution_result = {
                "provider": "Mock Dispatcher",
                "status": "delivery unconfirmed",
                "delivery_status": "delivery unconfirmed",
                "delivery_mode": "simulated",
                "note": "Dispatch initiated but delivery confirmation from provider is unconfirmed.",
                "is_real_sent": False,
                "is_simulated": True
            }
        elif can_send_real:
            try:
                with httpx.Client(timeout=10.0) as client:
                    res = client.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {settings.resend_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "from": settings.resend_from_email,
                            "to": [recipient_email],
                            "subject": subject,
                            "text": body
                        }
                    )
                    if res.status_code in (200, 201):
                        delivery_status = "real provider accepted"
                        delivery_mode = "real"
                        is_real_sent = True
                        execution_result = {
                            "provider": "Resend API",
                            "status": "real provider accepted",
                            "delivery_status": "real provider accepted",
                            "delivery_mode": "real",
                            "is_real_sent": True,
                            "is_simulated": False,
                            "resend_id": res.json().get("id")
                        }
                    elif res.status_code == 202:
                        delivery_status = "delivery unconfirmed"
                        delivery_mode = "real"
                        is_real_sent = False
                        execution_result = {
                            "provider": "Resend API",
                            "status": "delivery unconfirmed",
                            "delivery_status": "delivery unconfirmed",
                            "delivery_mode": "real",
                            "note": f"Resend 202 accepted without final dispatch confirmation: {res.text}",
                            "is_real_sent": False,
                            "is_simulated": False
                        }
                    else:
                        delivery_status = "failed"
                        delivery_mode = "failed"
                        is_real_sent = False
                        execution_result = {
                            "provider": "Resend API",
                            "status": "failed",
                            "delivery_status": "failed",
                            "delivery_mode": "failed",
                            "error": f"Resend HTTP {res.status_code}: {res.text}",
                            "is_real_sent": False,
                            "is_simulated": False
                        }
            except Exception as e:
                delivery_status = "failed"
                delivery_mode = "failed"
                is_real_sent = False
                execution_result = {
                    "provider": "Resend API",
                    "status": "failed",
                    "delivery_status": "failed",
                    "delivery_mode": "failed",
                    "error": str(e),
                    "is_real_sent": False,
                    "is_simulated": False
                }
        else:
            delivery_status = "simulated delivery"
            delivery_mode = "simulated"
            is_real_sent = False
            execution_result = {
                "provider": "Local Simulation Dispatcher",
                "status": "simulated delivery",
                "delivery_status": "simulated delivery",
                "delivery_mode": "simulated",
                "is_real_sent": False,
                "is_simulated": True,
                "recipient": recipient_email,
                "subject": subject,
                "details": f"Local simulation: message to {recipient_email} recorded safely without external network dispatch at {now}.",
                "simulated_at": now
            }
    elif action["action_type"] == "slack_message":
        delivery_status = "simulated delivery"
        delivery_mode = "simulated"
        is_real_sent = False
        execution_result = {
            "provider": "Slack Dispatcher",
            "status": "simulated delivery",
            "delivery_status": "simulated delivery",
            "delivery_mode": "simulated",
            "channel": payload.get("channel"),
            "details": f"Slack broadcast simulated to {payload.get('channel')} at {now}",
            "is_real_sent": False,
            "is_simulated": True
        }
    else:
        delivery_status = "simulated delivery"
        delivery_mode = "simulated"
        is_real_sent = False
        execution_result = {
            "provider": "General Dispatcher",
            "status": "simulated delivery",
            "delivery_status": "simulated delivery",
            "delivery_mode": "simulated",
            "details": f"Action simulated at {now}",
            "is_real_sent": False,
            "is_simulated": True
        }

    final_status = "failed" if delivery_status == "failed" else "executed"

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE action_proposals
            SET status = ?, delivery_status = ?, delivery_mode = ?, approval_status = 'approved',
                approved_at = ?, approved_by = ?, executed_at = ?, execution_result = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                delivery_status,
                delivery_mode,
                approved_at,
                approved_by,
                now,
                json.dumps(execution_result),
                now,
                action_id
            )
        )
        conn.commit()
    finally:
        conn.close()

    log_audit_event(
        event_id=action.get("event_id", "evt-dubhacks-2026"),
        actor_id=actor_id,
        action="execute_approved_action",
        target_type="action_proposal",
        target_id=action_id,
        details={
            "action_id": action_id,
            "status": final_status,
            "delivery_status": delivery_status,
            "delivery_mode": delivery_mode,
            "is_real_sent": is_real_sent,
            "provider": execution_result.get("provider")
        }
    )

    provider_status = execution_result.get("status")
    if provider_status in ("recorded_delivery", "delivered_to_outbox", "simulated delivery"):
        activity_status = "simulated"
        activity_summary = "Approved action was recorded by a simulator; delivery is not verified."
    elif provider_status in ("sent", "real provider accepted"):
        activity_status = "succeeded"
        activity_summary = "Approved action was accepted by the configured provider; delivery is not verified."
    else:
        activity_status = "unknown"
        activity_summary = "Approved action execution returned an unverified outcome."
    log_audit_event(
        event_id=action.get("event_id", "evt-dubhacks-2026"),
        actor_id="gurt_agent",
        action="approved_action_execution",
        target_type="activity",
        target_id=action_id,
        details={
            "status": activity_status,
            "summary": activity_summary,
            "affected_record_ids": [action_id]
        }
    )

    return {
        "action_id": action_id,
        "status": final_status,
        "delivery_status": delivery_status,
        "approval_status": "approved",
        "approved_by": approved_by,
        "approved_at": approved_at,
        "delivery_mode": delivery_mode,
        "is_real_sent": is_real_sent,
        "title": action["title"],
        "executed_at": now,
        "result": execution_result
    }


def tool_process_outreach_reply(
    contact_name: str,
    reply_text: str,
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Parse a pasted speaker or sponsor reply and extract structured data (O2).
    Detects availability, topic confirmation, dietary needs, sponsor commitment tier,
    and proposed time slots. Updates the speaker/sponsor persistent record status.
    """
    conn = get_connection()
    c = conn.cursor()

    reply_lower = reply_text.lower()

    # ---- Extract signals from the reply ----
    extracted = {
        "interest_level": "interested" if any(w in reply_lower for w in ["love to", "happy to", "excited", "thrilled", "delighted", "honored", "pleased", "available", "yes", "confirmed", "let's do it", "i'm in", "count me in", "would love"]) else
                          "declined" if any(w in reply_lower for w in ["can't", "cannot", "decline", "unavailable", "won't be able", "not able"]) else
                          "needs_clarification",
        "dietary_needs": [],
        "proposed_times": [],
        "topic_confirmed": False,
        "conditions": [],
        "follow_up_needed": []
    }

    # Dietary signals
    for diet in ["vegan", "vegetarian", "gluten-free", "halal", "kosher", "nut-free", "dairy-free"]:
        if diet in reply_lower:
            extracted["dietary_needs"].append(diet)

    # Time slot signals
    import re
    time_patterns = re.findall(r'\b(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\b', reply_text)
    date_patterns = re.findall(r'\b(\w+\s+\d{1,2}(?:st|nd|rd|th)?)\b', reply_text)
    extracted["proposed_times"] = time_patterns[:3]
    if date_patterns:
        extracted["proposed_times"] = [f"{d} {t}" for d, t in zip(date_patterns[:2], time_patterns[:2])] or extracted["proposed_times"]

    # Topic confirmation
    if any(w in reply_lower for w in ["topic", "presentation", "talk about", "speaking on", "my session"]):
        extracted["topic_confirmed"] = True

    # Conditions
    if any(w in reply_lower for w in ["honorarium", "compensation", "stipend", "travel", "hotel", "flight"]):
        extracted["conditions"].append("Financial terms mentioned — requires organizer review.")
    if any(w in reply_lower for w in ["nda", "agreement", "contract", "terms"]):
        extracted["conditions"].append("Legal/contractual terms mentioned — requires organizer review.")

    # ---- Update speaker or sponsor record ----
    updated_record = None
    record_type = "unknown"

    # Try speakers first
    c.execute("SELECT * FROM speakers WHERE event_id = ? AND name LIKE ?", (event_id, f"%{contact_name}%"))
    row = c.fetchone()
    if row:
        record_type = "speaker"
        new_status = "confirmed" if extracted["interest_level"] == "interested" else "declined" if extracted["interest_level"] == "declined" else row["status"]
        c.execute("UPDATE speakers SET status = ? WHERE id = ?", (new_status, row["id"]))
        updated_record = {"type": "speaker", "id": row["id"], "name": row["name"], "new_status": new_status}
    else:
        # Try sponsors
        c.execute("SELECT * FROM sponsors WHERE event_id = ? AND name LIKE ?", (event_id, f"%{contact_name}%"))
        row = c.fetchone()
        if row:
            record_type = "sponsor"
            new_status = "confirmed" if extracted["interest_level"] == "interested" else "declined" if extracted["interest_level"] == "declined" else row["status"]
            c.execute("UPDATE sponsors SET status = ? WHERE id = ?", (new_status, row["id"]))
            updated_record = {"type": "sponsor", "id": row["id"], "name": row["name"], "new_status": new_status}
        else:
            # Auto-create speaker candidate with confirmed/interested status
            record_type = "speaker"
            spk_id = f"spk-{uuid.uuid4().hex[:6]}"
            new_status = "confirmed" if extracted["interest_level"] == "interested" else "prospect"
            topic = "Keynote / Technical Session"
            if extracted.get("topic_confirmed"):
                m_topic = re.search(r'(?:topic|session|talk about|on)\s+([A-Za-z0-9\s\-]+?)(?:\.|\!|\,|$)', reply_text, flags=re.IGNORECASE)
                if m_topic:
                    topic = m_topic.group(1).strip()
            c.execute(
                "INSERT INTO speakers (id, event_id, name, org, topic, status, contact_email, proposed_time, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (spk_id, event_id, contact_name, "Guest Keynote", topic, new_status, "", ", ".join(extracted["proposed_times"]) or "TBD", f"Dietary: {', '.join(extracted['dietary_needs']) or 'None specified'}")
            )
            updated_record = {"type": "speaker", "id": spk_id, "name": contact_name, "new_status": new_status}

    # ---- Create follow-up tasks if needed ----
    created_tasks = []
    if extracted["interest_level"] == "interested" and record_type == "speaker":
        task_id = f"tsk-{uuid.uuid4().hex[:6]}"
        c.execute(
            "INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, event_id, f"Finalize details with {contact_name} (confirmed speaker)", "Operations Lead", "Outreach", "2026-11-08", "todo", "None")
        )
        created_tasks.append({"task_id": task_id, "title": f"Finalize details with {contact_name}"})

    if extracted["conditions"]:
        task_id = f"tsk-{uuid.uuid4().hex[:6]}"
        c.execute(
            "INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, event_id, f"Review conditions from {contact_name}: {'; '.join(extracted['conditions'][:2])}", "Operations Lead", "Outreach", "2026-11-05", "todo", "None")
        )
        created_tasks.append({"task_id": task_id, "title": f"Review conditions from {contact_name}"})

    conn.commit()
    conn.close()

    return {
        "contact_name": contact_name,
        "record_type": record_type,
        "extracted": extracted,
        "updated_record": updated_record,
        "created_tasks": created_tasks,
        "summary": (
            f"Processed reply from {contact_name}: interest={extracted['interest_level']}, "
            f"topic_confirmed={extracted['topic_confirmed']}, "
            f"dietary={extracted['dietary_needs'] or 'none specified'}, "
            f"conditions={len(extracted['conditions'])} flagged."
        )
    }


def tool_record_sponsor_commitment(
    sponsor_name: str,
    tier: str = "Silver",
    amount: float = 1500.0,
    benefits_agreed: str = "",
    notes: str = "",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Record a confirmed sponsor pledge with tier, amount, and agreed benefits (O2/O3)."""
    conn = get_connection()
    c = conn.cursor()

    # Try to find existing sponsor record
    c.execute("SELECT * FROM sponsors WHERE event_id = ? AND name LIKE ?", (event_id, f"%{sponsor_name}%"))
    row = c.fetchone()

    if row:
        # Update existing sponsor
        full_notes = f"{row['notes'] or ''}; Commitment confirmed: {benefits_agreed}. {notes}".strip("; ")
        c.execute(
            "UPDATE sponsors SET tier = ?, amount = ?, status = 'confirmed', notes = ? WHERE id = ?",
            (tier, float(amount), full_notes, row["id"])
        )
        sponsor_id = row["id"]
    else:
        # Create new sponsor record
        sponsor_id = f"spn-{uuid.uuid4().hex[:6]}"
        full_notes = f"Commitment confirmed: {benefits_agreed}. {notes}".strip()
        c.execute(
            "INSERT INTO sponsors (id, event_id, name, tier, amount, status, contact_email, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sponsor_id, event_id, sponsor_name, tier, float(amount), "confirmed", "", full_notes)
        )

    # Create fulfillment task
    task_id = f"tsk-{uuid.uuid4().hex[:6]}"
    c.execute(
        "INSERT INTO tasks (id, event_id, title, owner, category, deadline, status, dependencies) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, event_id, f"Fulfill {tier} sponsor benefits for {sponsor_name} (${amount:,.0f})", "Operations Lead", "Outreach", "2026-11-10", "todo", "None")
    )

    conn.commit()
    conn.close()

    return {
        "status": "commitment_recorded",
        "sponsor_id": sponsor_id,
        "sponsor_name": sponsor_name,
        "tier": tier,
        "amount": amount,
        "benefits_agreed": benefits_agreed,
        "fulfillment_task_id": task_id,
        "notes": full_notes
    }


def tool_check_outreach_followups(
    event_id: str = "evt-dubhacks-2026",
    days_threshold: int = 3
) -> dict[str, Any]:
    """Identify stalled outreach candidates and pending actions that need follow-up (O3).
    Returns speakers in 'shortlist' or 'contacted' status and sponsors in 'pipeline' or 'discussion'
    that haven't been confirmed, plus any stale pending action proposals.
    """
    conn = get_connection()
    c = conn.cursor()

    # Stalled speakers (not yet confirmed or declined)
    c.execute(
        "SELECT * FROM speakers WHERE event_id = ? AND status IN ('shortlist', 'contacted')",
        (event_id,)
    )
    stalled_speakers = [dict(r) for r in c.fetchall()]

    # Stalled sponsors
    c.execute(
        "SELECT * FROM sponsors WHERE event_id = ? AND status IN ('pipeline', 'discussion')",
        (event_id,)
    )
    stalled_sponsors = [dict(r) for r in c.fetchall()]

    # Pending action proposals (drafts awaiting approval)
    c.execute(
        "SELECT * FROM action_proposals WHERE event_id = ? AND status = 'pending_approval'",
        (event_id,)
    )
    pending_actions = [dict(r) for r in c.fetchall()]

    conn.close()

    # Build follow-up suggestions
    followup_suggestions = []
    for s in stalled_speakers:
        followup_suggestions.append({
            "type": "speaker_followup",
            "name": s["name"],
            "org": s["org"],
            "current_status": s["status"],
            "contact_email": s.get("contact_email", ""),
            "suggested_action": f"Send a friendly follow-up to {s['name']} ({s['org']}) regarding their {s['topic']} presentation. Current status: {s['status']}."
        })

    for sp in stalled_sponsors:
        followup_suggestions.append({
            "type": "sponsor_followup",
            "name": sp["name"],
            "tier": sp["tier"],
            "current_status": sp["status"],
            "contact_email": sp.get("contact_email", ""),
            "suggested_action": f"Follow up with {sp['name']} on {sp['tier']} tier sponsorship (${sp['amount']:,.0f}). Current status: {sp['status']}."
        })

    return {
        "event_id": event_id,
        "days_threshold": days_threshold,
        "stalled_speakers": len(stalled_speakers),
        "stalled_sponsors": len(stalled_sponsors),
        "pending_actions": len(pending_actions),
        "followup_suggestions": followup_suggestions,
        "pending_action_details": [{"id": a["id"], "title": a["title"], "action_type": a["action_type"]} for a in pending_actions],
        "summary": (
            f"Found {len(stalled_speakers)} speakers and {len(stalled_sponsors)} sponsors needing follow-up, "
            f"plus {len(pending_actions)} pending action proposals awaiting organizer approval."
        )
    }

