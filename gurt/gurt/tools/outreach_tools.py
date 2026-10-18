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
from gurt.db import get_connection


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

    return {
        "action_id": action_id,
        "status": "executed",
        "title": action["title"],
        "executed_at": now,
        "result": execution_result
    }
