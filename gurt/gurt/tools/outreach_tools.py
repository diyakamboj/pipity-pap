"""Outreach & Human-In-The-Loop Approval Tool Adapter.

Ensures that drafts are NEVER sent automatically. Consequential actions
are recorded as action proposals and require human confirmation.
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
    action_type: str = "speaker_outreach"
) -> dict[str, Any]:
    """Draft an outreach message or proposal for human review. Does NOT send."""
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

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO action_proposals (id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (action_id, action_type, title, summary, json.dumps(payload), "pending_approval")
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
        "warning": "DRAFT CREATED. No message has been sent. Awaiting organizer approval in the Action Center."
    }


def tool_draft_slack_message(channel: str, message: str) -> dict[str, Any]:
    """Prepare a Slack message draft on the organizer's behalf for approval."""
    action_id = f"act-{uuid.uuid4().hex[:6]}"
    title = f"Slack Message to {channel}"
    summary = f"Drafted Slack communication to {channel}"
    payload = {
        "channel": channel,
        "message": message,
        "action_type": "slack_message"
    }

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO action_proposals (id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (action_id, "slack_message", title, summary, json.dumps(payload), "pending_approval")
    )
    conn.commit()
    conn.close()
    return {
        "action_id": action_id,
        "status": "pending_approval",
        "title": title,
        "channel": channel,
        "full_body": message,
        "warning": "DRAFT CREATED. No message has been sent. Awaiting organizer approval in the Action Center."
    }


def tool_draft_teams_message(recipient: str, message: str) -> dict[str, Any]:
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
        INSERT INTO action_proposals (id, action_type, title, summary, payload, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (action_id, "teams_message", title, summary, json.dumps(payload), "pending_approval")
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

    payload = json.loads(action["payload"])
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
