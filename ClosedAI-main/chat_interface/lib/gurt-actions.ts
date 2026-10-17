// Shared definitions for the Gurt "action" client tools (email / Slack / Teams).
//
// These are registered with the backend as `client_tools` (see app/api/chat/
// route.ts): when the agent calls one, the backend emits an ActionEvent over
// the WebSocket and immediately acks — it does NOT perform the action. The
// frontend surfaces an "Approve & Send" card in chat, and the organizer is the
// enforcement point: nothing is sent until they approve.
//
// This module is framework-neutral (no React / no zustand) so it can be
// imported by both the server route and client components as a single source
// of truth for the tool names, schemas, and presentation metadata.

// Minimal shape of the backend's ClientToolSpec (a JSON-Schema object for
// `parameters`). Kept local so we don't couple to backend types.
export interface ClientToolSpec {
  name: string
  description: string
  parameters: {
    type: 'object'
    properties: Record<string, unknown>
    required?: string[]
  }
}

export type GurtActionKind = 'email' | 'slack' | 'teams'

const HITL_NOTE =
  'This does NOT send immediately: the draft is shown to the organizer for ' +
  'approval in chat and is only delivered after they click "Approve & Send". ' +
  'Provide a complete, ready-to-send draft. After calling this tool, tell the ' +
  'organizer you have prepared it for review in Canvas and approval in chat — do not claim it ' +
  'has already been sent.'

export const GURT_ACTION_TOOLS: ClientToolSpec[] = [
  {
    name: 'send_email',
    description: `Prepare an email to send on the organizer's behalf. ${HITL_NOTE}`,
    parameters: {
      type: 'object',
      properties: {
        to: { type: 'string', description: 'Primary recipient email address.' },
        cc: { type: 'string', description: 'Optional CC recipients (comma-separated).' },
        subject: { type: 'string', description: 'Email subject line.' },
        body: { type: 'string', description: 'Full email body, ready to send.' },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'send_slack_message',
    description: `Prepare a Slack message to send on the organizer's behalf. ${HITL_NOTE}`,
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Target Slack channel (e.g. "#event-ops") or user (e.g. "@speaker").',
        },
        message: { type: 'string', description: 'Full message text, ready to send.' },
      },
      required: ['channel', 'message'],
    },
  },
  {
    name: 'send_teams_message',
    description: `Prepare a Microsoft Teams message to send on the organizer's behalf. ${HITL_NOTE}`,
    parameters: {
      type: 'object',
      properties: {
        recipient: {
          type: 'string',
          description: 'Target Teams recipient (person name/email or channel).',
        },
        message: { type: 'string', description: 'Full message text, ready to send.' },
      },
      required: ['recipient', 'message'],
    },
  },
]

export const GURT_ACTION_KIND: Record<string, GurtActionKind> = {
  send_email: 'email',
  send_slack_message: 'slack',
  send_teams_message: 'teams',
}

export const GURT_ACTION_TOOL_NAMES: ReadonlySet<string> = new Set(
  GURT_ACTION_TOOLS.map((t) => t.name),
)

export function isGurtActionTool(name: string): boolean {
  return GURT_ACTION_TOOL_NAMES.has(name)
}

const KIND_LABEL: Record<GurtActionKind, string> = {
  email: 'Email',
  slack: 'Slack message',
  teams: 'Teams message',
}

function recipientOf(toolName: string, params: Record<string, any>): string {
  switch (GURT_ACTION_KIND[toolName]) {
    case 'email':
      return params.to || 'recipient'
    case 'slack':
      return params.channel || 'channel'
    case 'teams':
      return params.recipient || 'recipient'
    default:
      return 'recipient'
  }
}

/** Canvas artifact title, e.g. "Email to speaker@example.com". */
export function actionTitle(toolName: string, params: Record<string, any>): string {
  const kind = GURT_ACTION_KIND[toolName]
  const label = kind ? KIND_LABEL[kind] : 'Action'
  return `${label} to ${recipientOf(toolName, params)}`
}

/** Reasoning-stepper title, e.g. "Prepared email for approval". */
export function actionStepTitle(toolName: string, params: Record<string, any>): string {
  const kind = GURT_ACTION_KIND[toolName]
  const label = kind ? KIND_LABEL[kind].toLowerCase() : 'action'
  void params
  return `Prepared ${label} for approval`
}
