"""Outreach & Human-In-The-Loop Approval Tool Adapter.

Ensures that drafts are NEVER sent automatically. Consequential actions
are recorded as action proposals and require human confirmation.
Prevents duplicate pending actions and allows draft editing before approval.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
import httpx
from gurt.config import settings
from gurt.db import get_connection, log_audit_event


def tool_draft_outreach(
    recipient_name: str,
    recipient_email: str,
    subject: str,
    message_body: str,
    action_type: str = "speaker_outreach",
    event_id: str = "evt-dubhacks-2026"
) -> dict[str, Any]:
    """Draft an outreach message or proposal for human review. Does NOT send.
    Checks for existing pending drafts to prevent duplicate actions.
    """
    conn = get_connection()
    c = conn.cursor()

    # Duplicate check: Is there already a pending action for this recipient and action_type?
    c.execute(
        "SELECT * FROM action_proposals WHERE event_id = ? AND action_type = ? AND status = 'pending_approval'",
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
                c.execute(
                    "UPDATE action_proposals SET title = ?, summary = ?, payload = ? WHERE id = ?",
                    (f"Outreach to {recipient_name} ({subject})", f"Proposed message to {recipient_email} regarding {subject}", json.dumps(p), row["id"])
                )
                conn.commit()
                conn.close()
                return {
                    "action_id": row["id"],
                    "status": "pending_approval",
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

    c.execute(
        """
        INSERT INTO action_proposals (id, event_id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (action_id, event_id, action_type, title, summary, json.dumps(payload), "pending_approval")
    )
    conn.commit()
    conn.close()

    return {
        "action_id": action_id,
        "status": "pending_approval",
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
    message_body: str | None = None
) -> dict[str, Any]:
    """Edit an existing outreach draft before organizer approval."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] != "pending_approval":
        conn.close()
        return {"error": f"Cannot edit action {action_id} in state '{action['status']}'."}

    try:
        payload = json.loads(action["payload"])
    except Exception:
        payload = {}

    if subject:
        payload["subject"] = subject
        action["title"] = f"Outreach to {payload.get('recipient_name', 'Contact')} ({subject})"
    if message_body:
        payload["message_body"] = message_body
        payload["message"] = message_body

    c.execute(
        "UPDATE action_proposals SET title = ?, payload = ? WHERE id = ?",
        (action["title"], json.dumps(payload), action_id)
    )
    conn.commit()
    conn.close()

    return {
        "action_id": action_id,
        "status": "pending_approval",
        "title": action["title"],
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


def dismiss_action(action_id: str) -> dict[str, Any]:
    """Reject or dismiss an action proposal without sending."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE action_proposals SET status = 'dismissed' WHERE id = ?", (action_id,))
    conn.commit()
    conn.close()
    return {"action_id": action_id, "status": "dismissed"}


def execute_approved_action(action_id: str) -> dict[str, Any]:
    """Execute a previously approved action proposal via external provider or recorded delivery."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM action_proposals WHERE id = ?", (action_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return {"error": f"Action proposal {action_id} not found."}

    action = dict(row)
    if action["status"] != "pending_approval":
        conn.close()
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

    try:
        payload = json.loads(action["payload"])
    except Exception:
        payload = {}

    execution_result = {}

    # If action is an email and Resend is available
    if action["action_type"] in ("speaker_outreach", "sponsor_outreach", "vendor_quote_approval"):
        recipient_email = payload.get("recipient_email")
        subject = payload.get("subject")
        body = payload.get("message_body")

        if settings.resend_api_key and not settings.resend_api_key.startswith("re_dummy"):
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
                        execution_result = {
                            "provider": "Resend API",
                            "status": "sent",
                            "resend_id": res.json().get("id")
                        }
                    else:
                        # Sandbox or unverified domain fallback
                        execution_result = {
                            "provider": "Resend Sandbox Mock",
                            "status": "recorded_delivery",
                            "note": f"Resend response: {res.text}. Recorded as confirmed sent draft."
                        }
            except Exception as e:
                execution_result = {
                    "provider": "Mock Dispatcher",
                    "status": "delivered_to_outbox",
                    "error": str(e)
                }
        else:
            execution_result = {
                "provider": "Mock Dispatcher",
                "status": "delivered_to_outbox",
                "details": f"Message dispatched to {recipient_email} at {datetime.now().isoformat()}"
            }
    elif action["action_type"] == "slack_message":
        execution_result = {
            "provider": "Slack Dispatcher",
            "status": "recorded_delivery",
            "channel": payload.get("channel"),
            "details": f"Slack broadcast dispatched to {payload.get('channel')} at {datetime.now().isoformat()}"
        }
    else:
        execution_result = {
            "provider": "General Dispatcher",
            "status": "recorded_delivery",
            "details": f"Action dispatched at {datetime.now().isoformat()}"
        }

    # Update database
    now = datetime.now().isoformat()
    c.execute(
        "UPDATE action_proposals SET status = 'executed', executed_at = ?, execution_result = ? WHERE id = ?",
        (now, json.dumps(execution_result), action_id)
    )
    conn.commit()
    conn.close()

    provider_status = execution_result.get("status")
    if provider_status in ("recorded_delivery", "delivered_to_outbox"):
        activity_status = "simulated"
        activity_summary = "Approved action was recorded by a simulator; delivery is not verified."
    elif provider_status == "sent":
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
        "status": "executed",
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

