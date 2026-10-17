"use client"

import { useEffect, type ReactNode } from 'react'
import { create } from 'zustand'
// Type-only import (erased at build time, so no runtime import cycle with
// agent-runtime, which imports the store's `useChat` value).
import type { EventCategory, EventStatus } from './agent-runtime'
import { actionTitle } from './gurt-actions'

export type Reaction = 'up' | 'down' | null

/**
 * A single step in the agent's live reasoning stream, derived from the
 * backend's Action/Observation events. The execution panel (agent-runtime)
 * maps these into its RunEvent shape for rendering. Timestamps are absolute
 * (ms) and converted to run-relative offsets at render time.
 */
export interface ActivityStep {
  id: string
  category: EventCategory
  title: string
  detail?: string
  status: EventStatus
  createdAtMs: number
  endedAtMs?: number
  /** Backend tool_call_id, used to match an Observation back to its Action. */
  toolCallId?: string
  level?: 'info' | 'warn' | 'error' | 'debug'
  /** Raw action data for rendering approval cards if the backend pauses execution. */
  toolName?: string
  rawParams?: Record<string, any>
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  createdAt?: number
  reaction?: Reaction
  status: 'sending' | 'sent' | 'receiving' | 'received' | 'error'
  metadata?: {
    files?: string[]
    artifacts?: unknown
    tool_calls?: unknown[]
    approval?: ChatApproval
  }
}

export interface ChatApproval {
  id: string
  conversationId: string
  toolName: string
  title: string
  params: Record<string, any>
  risk?: string
}

export interface ConversationMeta {
  id: string
  title: string
}

interface ChatState {
  // Active conversation (UI)
  activeConversation: Message[]
  conversations: ConversationMeta[]
  activeId: string | null

  // Per-chat history and backend binding (persisted to localStorage). The
  // active chat's messages live in `activeConversation`; the others are parked
  // here and swapped in on selection. `backendIdByChat` maps a UI chat to its
  // reused backend conversation id so context survives across messages/reloads.
  messagesByChat: Record<string, Message[]>
  backendIdByChat: Record<string, string>

  // Run state
  isRunning: boolean
  error: string | null

  // Live agent reasoning steps for the current turn (execution panel / feed).
  activity: ActivityStep[]
  activityStartedAt: number | null

  // Backend (HRAgents agent server) connection
  backendConversationId: string | null
  socket: WebSocket | null
  backendConnected: boolean
  connectionError: string | null

  // Settings
  model: string
  tone: string
  dataSource: string
  webSearch: boolean

  // UI state
  sidebarOpen: boolean
  sidebarWidth: number
  agent: string

  // Actions
  sendMessage: (content: string) => Promise<void>
  cancelRun: () => void
  clearConversation: () => void
  setModel: (model: string) => void
  setTone: (tone: string) => void
  setDataSource: (source: string) => void
  toggleWebSearch: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void
  setAgent: (agent: string) => void
  newChat: () => void
  selectConversation: (id: string) => void
  deleteConversation: (id: string) => void
  reactToMessage: (messageId: string, reaction: 'up' | 'down') => void
  hydrate: () => void
}

const MODELS = [
  { label: 'GPT-4o (Azure)', value: 'gpt-4o' },
  { label: 'GPT-5.5', value: 'gpt-5.5' },
  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet' },
  { label: 'Claude 3 Opus', value: 'claude-3-opus' },
]

const TONES = [
  'Default',
  'Professional',
  'Friendly',
  'Technical',
  'Creative',
  'Analytical',
]

const DATA_SOURCES = [
  'Internal Knowledge',
  'Web Search',
  'Both',
]

// Browser-reachable base for the backend event WebSocket. The REST calls that
// carry secrets (creating the conversation with the Azure LLM config) go
// through the Next.js server route instead, so no credentials touch the client.
const WS_BASE =
  process.env.NEXT_PUBLIC_HRAGENT_WS_URL?.replace(/\/$/, '') || 'ws://127.0.0.1:8001'

// Optional token for the browser's event WebSocket, used only when the backend
// is started with SESSION_API_KEY. Sent as a first-message auth frame. NOTE:
// because it is a NEXT_PUBLIC_ value it is visible to the browser; treat this
// as a network-scoped (VPN/internal) control, not a real secret. A short-lived
// minted token / WS proxy is tracked for the hardening phase. Empty = the
// backend is open (local testing default) and no auth frame is sent.
const WS_TOKEN = process.env.NEXT_PUBLIC_HRAGENT_WS_TOKEN || ''

const CONNECT_TIMEOUT_MS = 20000

// Whether the agent produced any visible text during the current turn. Used to
// decide if we need the final-response fallback when the run finishes. The UI
// only runs one turn at a time, so a module-scoped flag is sufficient.
let sawAgentTextThisTurn = false

// Id of the assistant message currently being built from streaming token
// deltas, if any. Null when we are not mid-stream. Reset each turn.
let streamingMessageId: string | null = null

// Live text-generation step in the activity feed. When the agent answers with
// plain text (no tool call to render), the feed would otherwise stay empty for
// the whole turn; we keep one "responding…" step that is born on the first
// streamed token and closes when the run reaches a terminal state.
let respondingStepId: string | null = null
let respondTextBuffer = ''
let respondLastPaintedAt = 0

// A turn is terminal when the backend stops producing for it. Besides the
// explicit failures, a user-initiated interrupt lands here too: the backend
// reports `paused` (and may later resume on the next message). Without these,
// the activity feed's running steps and the streamed bubble would never be
// finalized after a Stop, leaving the sidebar stuck on "running".
const TERMINAL_STATUSES = new Set(['finished', 'error', 'stuck', 'paused', 'interrupted', 'stopped'])
// Statuses that represent a user-cancelled turn rather than a failure: closing
// steps as errors would mislead the activity feed.
const USER_CANCEL_STATUSES = new Set(['paused', 'interrupted', 'stopped'])

// hr-mcp tools that read structured data (Azure SQL later) vs. policy RAG.
const DATA_TOOLS = new Set(['employee_lookup', 'pto_balance', 'org_chart', 'benefits_lookup'])

const TOOL_LABELS: Record<string, string> = {
  employee_lookup: 'Looking up employee record',
  pto_balance: 'Checking PTO balance',
  org_chart: 'Fetching org chart',
  benefits_lookup: 'Looking up benefits',
  policy_search: 'Searching HR policies',
  invoke_skill: 'Executing HR skill',
}

const MCP_TOOL_LABELS: Record<string, string> = {
  query_cosmos: 'Querying Cosmos DB',
  list_collections: 'Listing Cosmos DB containers',
  describe_container: 'Describing Cosmos DB container',
  find_implied_links: 'Finding Cosmos DB relationships',
  get_sample_documents: 'Sampling Cosmos DB documents',
  count_documents: 'Counting Cosmos DB documents',
  get_partition_key_info: 'Reading Cosmos DB partition key',
  get_indexing_policy: 'Reading Cosmos DB indexing policy',
  list_distinct_values: 'Listing Cosmos DB field values',
  query: 'Searching Azure AI Search',
  list_indexes: 'Listing Azure AI Search indexes',
  get_index: 'Reading Azure AI Search index',
  list_formats: 'Listing supported document formats',
  get_document_info: 'Reading document metadata',
  office_read: 'Reading document contents',
  office_validate: 'Validating document integrity',
  office_diff_documents: 'Comparing documents',
  office_check_consistency: 'Checking document consistency',
  office_export_pdf: 'Exporting document to PDF',
  office_list_pdf_fields: 'Listing PDF form fields',
  office_fill_pdf_form: 'Filling PDF form fields',
  office_analyze_pdf_layout: 'Analyzing PDF layout',
  office_overlay_pdf_text: 'Overlaying text on PDF',
  office_template_detect: 'Detecting DOCX template fields',
  office_template_fill: 'Filling DOCX template',
  office_template_batch: 'Batch-filling DOCX templates',
}

// Map a backend tool name to the execution panel's visual category so the
// reasoning stepper shows a sensible icon (DB lookup vs. knowledge search).
function categoryForTool(name: string): EventCategory {
  if (name === 'policy_search') return 'memory'
  if (name === 'invoke_skill') return 'skill'
  if (DATA_TOOLS.has(name)) return 'database'
  if (name === 'think') return 'step'
  return 'tool'
}

function truncate(text: string, max = 140): string {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

// Extract a tool call's real arguments from the ActionEvent `action` payload.
// MCP tools nest args under `data`; client tools carry them top-level. Either
// way, drop the SDK meta fields (kind / summary / security_risk).
function extractActionParams(action: any): Record<string, any> {
  if (!action || typeof action !== 'object') return {}
  const base =
    action.data && typeof action.data === 'object' && !Array.isArray(action.data)
      ? action.data
      : action
  const out: Record<string, any> = {}
  for (const [k, v] of Object.entries(base)) {
    if (k === 'kind' || k === 'summary' || k === 'security_risk') continue
    out[k] = v
  }
  return out
}

// Compact "key: value, key: value" summary of a tool call's arguments for the
// step's detail line.
function argsSummary(action: any): string | undefined {
  const entries = Object.entries(extractActionParams(action))
  if (entries.length === 0) return undefined
  const parts = entries.map(
    ([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`,
  )
  return truncate(parts.join(', '), 120)
}

function observationText(observation: any): string {
  const content = observation?.content
  if (!Array.isArray(content)) return ''
  return content
    .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
    .map((c) => c.text)
    .join(' ')
    .trim()
}

function titleForAction(evt: any): string {
  const toolName: string = evt?.tool_name || 'tool'
  if (toolName === 'think') {
    const thought = evt?.action?.thought
    if (typeof thought === 'string' && thought.trim()) return truncate(thought)
    return 'Thinking'
  }
  const summary = typeof evt?.summary === 'string' ? evt.summary.trim() : ''
  if (summary) return truncate(summary)
  return TOOL_LABELS[toolName] || MCP_TOOL_LABELS[toolName] || `Calling ${toolName}`
}

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

// Chat title from the first user message: first line, trimmed to a sane length.
function titleFromText(text: string): string {
  const firstLine = text.split('\n')[0].trim()
  if (firstLine.length <= 48) return firstLine || 'New Chat'
  return `${firstLine.slice(0, 45).trimEnd()}…`
}

function textFromLlmMessage(llmMessage: any): string {
  if (!llmMessage) return ''
  const content = llmMessage.content
  if (typeof content === 'string') return content.trim()
  if (Array.isArray(content)) {
    return content
      .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
      .map((c) => c.text)
      .join('\n')
      .trim()
  }
  return ''
}

function readExecutionStatus(evt: any): string | undefined {
  const value = evt?.value
  if (evt?.key === 'execution_status') {
    return typeof value === 'string' ? value : value?.execution_status
  }
  if (value && typeof value === 'object') return value.execution_status
  return undefined
}

export const useChat = create<ChatState>((set, get) => ({
  // Initial state
  activeConversation: [],
  conversations: [],
  activeId: null,
  messagesByChat: {},
  backendIdByChat: {},
  isRunning: false,
  error: null,

  activity: [],
  activityStartedAt: null,

  backendConversationId: null,
  socket: null,
  backendConnected: false,
  connectionError: null,

  model: MODELS[0].value,
  tone: 'Default',
  dataSource: 'Internal Knowledge',
  webSearch: false,
  sidebarOpen: true,
  sidebarWidth: 320,
  agent: 'HR Agent',

  sendMessage: async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed) return
    // One turn at a time: never queue a new prompt while the previous agent run
    // is still in flight. The composer shows a Stop button while running, so
    // the user can interrupt instead. Guarding here (not just in the UI) makes
    // the rule hold for every caller and is the single source of truth.
    if (get().isRunning) return

    const now = new Date()
    const userMessage: Message = {
      id: newId('user'),
      role: 'user',
      content: trimmed,
      timestamp: now,
      createdAt: now.getTime(),
      reaction: null,
      status: 'sent',
    }

    set((state) => {
      // Ensure a chat exists (messages sent from the landing screen have no
      // active chat yet) and give it a title from the first user message.
      let activeId = state.activeId
      let conversations = state.conversations
      if (!activeId) {
        activeId = `chat-${Date.now()}`
        conversations = [{ id: activeId, title: titleFromText(trimmed) }, ...conversations]
      } else if (state.activeConversation.every((m) => m.role !== 'user')) {
        conversations = conversations.map((c) =>
          c.id === activeId && c.title === 'New Chat'
            ? { ...c, title: titleFromText(trimmed) }
            : c,
        )
      }
      return {
        activeId,
        conversations,
        activeConversation: [...state.activeConversation, userMessage],
        isRunning: true,
        error: null,
        // Start a fresh reasoning stream for this turn.
        activity: [],
        activityStartedAt: now.getTime(),
      }
    })

    sawAgentTextThisTurn = false
    streamingMessageId = null
    resetRespondingStep()
    // Reset per-turn markdown artifact tracking so a fresh artifact is created
    // for each turn (not merged into a prior turn's artifact).

    try {
      const socket = await ensureSocket(get, set)
      socket.send(
        JSON.stringify({
          role: 'user',
          content: [{ type: 'text', text: trimmed }],
        }),
      )
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to reach HR Agent'
      appendSystem(set, `Error: ${detail}`)
      set({ isRunning: false, error: detail, connectionError: detail })
    }
  },

  cancelRun: () => {
    const { backendConversationId } = get()
    set({ isRunning: false })
    if (backendConversationId) {
      // Best-effort interrupt of the running backend conversation.
      fetch('/api/chat', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversationId: backendConversationId }),
      }).catch(() => {})
    }
  },

  clearConversation: () => {
    streamingMessageId = null
    resetRespondingStep()
    set({ activeConversation: [], error: null, activity: [], activityStartedAt: null })
  },

  setModel: (model: string) => set({ model }),
  setTone: (tone: string) => set({ tone }),
  setDataSource: (dataSource: string) => set({ dataSource }),
  toggleWebSearch: () => set((state) => ({ webSearch: !state.webSearch })),
  setSidebarOpen: (sidebarOpen: boolean) => set({ sidebarOpen }),
  setSidebarWidth: (sidebarWidth: number) => set({ sidebarWidth }),
  setAgent: (agent: string) => set({ agent }),

  reactToMessage: (messageId: string, reaction: 'up' | 'down') => {
    set((state) => ({
      activeConversation: state.activeConversation.map((message) =>
        message.id === messageId
          ? { ...message, reaction: message.reaction === reaction ? null : reaction }
          : message,
      ),
    }))
  },

  newChat: () => {
    const { activeId, activeConversation, conversations } = get()
    // If the active conversation is already an untouched new chat, just reset state
    if (activeId && activeConversation.length === 0) {
      const activeMeta = conversations.find((c) => c.id === activeId)
      if (activeMeta?.title === 'New Chat') {
        resetConnection(get, set)
        streamingMessageId = null
        resetRespondingStep()
        set({
          error: null,
          isRunning: false,
          activity: [],
          activityStartedAt: null,
        })
        return
      }
    }

    resetConnection(get, set)
    streamingMessageId = null
    resetRespondingStep()
    const id = `chat-${Date.now()}`
    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      if (activeId) messagesByChat[activeId] = activeConversation
      return {
        messagesByChat,
        activeConversation: [],
        activeId: id,
        conversations: [
          { id, title: 'New Chat' },
          ...state.conversations.filter(
            (c) =>
              !(
                c.title === 'New Chat' &&
                (messagesByChat[c.id]?.length === 0 || (!messagesByChat[c.id] && c.id !== activeId))
              ),
          ),
        ],
        error: null,
        isRunning: false,
        activity: [],
        activityStartedAt: null,
      }
    })
  },

  selectConversation: (id: string) => {
    const { activeId, activeConversation } = get()
    if (id === activeId) return
    resetConnection(get, set)
    streamingMessageId = null
    resetRespondingStep()
    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      if (activeId) messagesByChat[activeId] = activeConversation
      return {
        messagesByChat,
        activeId: id,
        // Restore this chat's history; the backend conversation is rebound
        // lazily (reconnected) on the next message.
        activeConversation: messagesByChat[id] ?? [],
        backendConversationId: state.backendIdByChat[id] ?? null,
        error: null,
        isRunning: false,
        activity: [],
        activityStartedAt: null,
      }
    })
  },

  deleteConversation: (id: string) => {
    const conversations = get().conversations.filter((c) => c.id !== id)
    const isActive = get().activeId === id
    const nextActiveId = isActive ? (conversations[0]?.id ?? null) : get().activeId
    if (isActive) {
      resetConnection(get, set)
      streamingMessageId = null
      resetRespondingStep()
    }
    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      delete messagesByChat[id]
      const backendIdByChat = { ...state.backendIdByChat }
      delete backendIdByChat[id]
      return {
        conversations,
        messagesByChat,
        backendIdByChat,
        activeId: nextActiveId,
        ...(isActive
          ? {
              activeConversation: nextActiveId ? (messagesByChat[nextActiveId] ?? []) : [],
              backendConversationId: nextActiveId
                ? (backendIdByChat[nextActiveId] ?? null)
                : null,
              error: null,
              isRunning: false,
              activity: [],
              activityStartedAt: null,
            }
          : {}),
      }
    })
  },

  hydrate: () => hydrateFromStorage(set),
}))

type Getter = typeof useChat.getState
type Setter = (partial: Partial<ChatState> | ((state: ChatState) => Partial<ChatState>)) => void

function appendAssistant(set: Setter, text: string) {
  const now = new Date()
  const message: Message = {
    id: newId('assistant'),
    role: 'assistant',
    content: text,
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'received',
  }
  set((state) => ({ activeConversation: [...state.activeConversation, message] }))
}

function appendApprovalRequest(set: Setter, approval: Omit<ChatApproval, 'id'>) {
  const now = new Date()
  const id = newId('approval')
  const message: Message = {
    id,
    role: 'assistant',
    content: 'I prepared an action that needs your approval before it can continue. Review the draft/details in the Canvas, then approve or reject it here.',
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'received',
    metadata: {
      approval: { ...approval, id },
    },
  }
  set((state) => ({ activeConversation: [...state.activeConversation, message] }))
}

function pushActivity(set: Setter, step: ActivityStep) {
  set((state) => ({ activity: [...state.activity, step] }))
}

// Patch the most recent still-running step matching a tool_call_id (an
// Observation/error responding to an earlier Action).
function updateActivityByToolCall(
  set: Setter,
  toolCallId: string | undefined,
  patch: Partial<ActivityStep>,
) {
  if (!toolCallId) return
  set((state) => {
    let done = false
    const activity = state.activity.map((s) => {
      if (!done && s.toolCallId === toolCallId && s.status === 'running') {
        done = true
        return { ...s, ...patch }
      }
      return s
    })
    return done ? { activity } : {}
  })
}

function markRunningStepsError(set: Setter, detail: string) {
  const now = Date.now()
  set((state) => ({
    activity: state.activity.map((s) =>
      s.status === 'running' ? { ...s, status: 'error' as EventStatus, endedAtMs: now, detail } : s,
    ),
  }))
}

// --- Live text-generation step (activity feed) ------------------------------
// Surfaces the agent's plain-text answer as it streams, so the feed reflects
// what the agent is doing even when it never calls a tool. The step is created
// on the first streamed token and closed by finishTurn / the error handlers.

function ensureRespondingStep(set: Setter) {
  if (respondingStepId) return
  const id = newId('resp')
  respondingStepId = id
  pushActivity(set, {
    id,
    category: 'step',
    title: 'Responding…',
    status: 'running',
    createdAtMs: Date.now(),
  })
}

function paintRespondingStep(set: Setter) {
  if (!respondingStepId) return
  const title = truncate(respondTextBuffer, 60) || 'Responding…'
  set((state) => {
    let changed = false
    const activity = state.activity.map((s) => {
      if (!changed && s.id === respondingStepId && s.status === 'running' && s.title !== title) {
        changed = true
        return { ...s, title }
      }
      return s
    })
    return changed ? { activity } : {}
  })
}

// Throttle step-title repaints to a few per second (deltas arrive per token).
function maybePaintRespondingStep(set: Setter) {
  const now = Date.now()
  if (now - respondLastPaintedAt < 120) return
  respondLastPaintedAt = now
  paintRespondingStep(set)
}

function resetRespondingStep() {
  respondingStepId = null
  respondTextBuffer = ''
  respondLastPaintedAt = 0
}

// Append a streamed token chunk to the in-progress assistant bubble, creating
// it on the first delta of the turn.  Deltas arrive per-token from the
// WebSocket and can fire hundreds of times per second.  To avoid exceeding
// React's maximum update depth we batch them and flush at most once per
// animation frame (~16 ms).  The buffer is always flushed synchronously when
// the streaming message is finalized (see finalizeStreaming).
let _pendingDelta = ''
let _deltaRafId: ReturnType<typeof requestAnimationFrame> | null = null
let _deltaPendingSet: Setter | null = null

function _flushDelta() {
  _deltaRafId = null
  const batch = _pendingDelta
  const set = _deltaPendingSet
  if (!batch || !set) return
  _pendingDelta = ''

  if (!streamingMessageId) {
    const now = new Date()
    const id = newId('assistant')
    streamingMessageId = id
    const message: Message = {
      id,
      role: 'assistant',
      content: batch,
      timestamp: now,
      createdAt: now.getTime(),
      reaction: null,
      status: 'receiving',
    }
    set((state) => ({ activeConversation: [...state.activeConversation, message] }))
    return
  }
  const id = streamingMessageId
  set((state) => ({
    activeConversation: state.activeConversation.map((m) =>
      m.id === id ? { ...m, content: m.content + batch } : m,
    ),
  }))
}

function appendStreamingDelta(set: Setter, delta: string) {
  sawAgentTextThisTurn = true
  _pendingDelta += delta
  _deltaPendingSet = set
  if (_deltaRafId == null) {
    // In SSR/Node environments requestAnimationFrame is unavailable; fall back
    // to a 30 ms setTimeout which achieves the same batching effect.
    if (typeof requestAnimationFrame === 'function') {
      _deltaRafId = requestAnimationFrame(_flushDelta)
    } else {
      _deltaRafId = setTimeout(_flushDelta, 30) as unknown as number
    }
  }
}

// Commit the streamed bubble: mark it received and, when the authoritative
// final text is available, replace the accumulated deltas with it.
function finalizeStreaming(set: Setter, finalText?: string) {
  // Flush any buffered tokens before sealing the message.
  if (_deltaRafId != null) {
    if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(_deltaRafId)
    else clearTimeout(_deltaRafId as unknown as ReturnType<typeof setTimeout>)
    _deltaRafId = null
  }
  _deltaPendingSet = set
  _flushDelta()

  const id = streamingMessageId
  if (!id) return
  streamingMessageId = null
  const authoritative = finalText != null && finalText.trim().length > 0 ? finalText : undefined
  set((state) => ({
    activeConversation: state.activeConversation.map((m) =>
      m.id === id
        ? { ...m, content: authoritative ?? m.content, status: 'received' as Message['status'] }
        : m,
    ),
  }))
}

function appendSystem(set: Setter, text: string) {
  const now = new Date()
  const message: Message = {
    id: newId('system'),
    role: 'system',
    content: text,
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'error',
  }
  set((state) => ({ activeConversation: [...state.activeConversation, message] }))
}

function resetConnection(get: Getter, set: Setter) {
  const { socket } = get()
  if (socket) {
    try {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      socket.close()
    } catch {
      /* ignore */
    }
  }
  set({ socket: null, backendConversationId: null, backendConnected: false })
}

async function ensureSocket(get: Getter, set: Setter): Promise<WebSocket> {
  const existing = get().socket
  if (existing && existing.readyState === WebSocket.OPEN && get().backendConversationId) {
    return existing
  }
  if (existing) {
    try {
      existing.close()
    } catch {
      /* ignore */
    }
  }

  const activeId = get().activeId
  const storedBackendId = (activeId && get().backendIdByChat[activeId]) || null

  // 1) Reuse this chat's existing backend conversation if we have one — this
  //    reconnects the WebSocket and keeps the agent's server-side context. If
  //    the backend no longer has it (e.g. it was restarted with a fresh
  //    workspace), fall through and create a new one; the UI history is
  //    preserved locally regardless.
  if (storedBackendId) {
    try {
      return await openBackendSocket(storedBackendId, get, set)
    } catch (error) {
      if (!(error as { notFound?: boolean })?.notFound) throw error
    }
  }

  // 2) Create a backend conversation server-side (LLM config + secrets stay in
  //    the Next.js server process, never in the browser) and bind it to this chat.
  const newConversationId = await createBackendConversation()
  if (activeId) {
    set((state) => ({
      backendIdByChat: { ...state.backendIdByChat, [activeId]: newConversationId },
    }))
  }
  return openBackendSocket(newConversationId, get, set)
}

async function createBackendConversation(): Promise<string> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    let detail = 'Failed to create HR Agent conversation'
    try {
      const body = await res.json()
      detail = body.error || body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const { conversationId } = await res.json()
  if (!conversationId) throw new Error('Backend did not return a conversation id')
  return conversationId
}

// Open the event WebSocket for a backend conversation and subscribe. Resolves
// once connected; rejects with `{ notFound: true }` if the backend reports the
// conversation is gone (close code 4004) so the caller can recreate it.
function openBackendSocket(
  conversationId: string,
  get: Getter,
  set: Setter,
): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${WS_BASE}/sockets/events/${conversationId}`)
    let settled = false
    set({ socket: ws, backendConversationId: conversationId, connectionError: null })

    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      reject(new Error('Timed out connecting to the HR Agent event stream'))
    }, CONNECT_TIMEOUT_MS)

    ws.onmessage = (event) => {
      let parsed: any
      try {
        parsed = JSON.parse(event.data)
      } catch {
        return
      }
      handleServerEvent(parsed, get, set)
    }

    ws.onopen = () => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      // First-frame auth when the backend requires a session key; ignored when
      // no keys are configured.
      if (WS_TOKEN) {
        try {
          ws.send(JSON.stringify({ type: 'auth', session_api_key: WS_TOKEN }))
        } catch {
          /* ignore */
        }
      }
      set({ backendConnected: true })
      resolve(ws)
    }

    ws.onclose = (ev) => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        if (ev.code === 4004) {
          const err = new Error('Backend conversation not found') as Error & {
            notFound: boolean
          }
          err.notFound = true
          reject(err)
        } else {
          reject(new Error('Could not connect to the HR Agent event stream'))
        }
        return
      }
      if (get().socket === ws) set({ backendConnected: false })
    }
  })
}

function handleServerEvent(evt: any, get: Getter, set: Setter) {
  const kind = evt?.kind

  if (kind === 'MessageEvent') {
    // Only render the agent's messages; the user's own turn is added
    // optimistically when sending, and echoes back as source "user".
    if (evt.source === 'agent') {
      const text = textFromLlmMessage(evt.llm_message)
      if (text) {
        sawAgentTextThisTurn = true
        // If we streamed this answer token-by-token, replace the in-progress
        // bubble with the authoritative text instead of appending a duplicate.
        if (streamingMessageId) finalizeStreaming(set, text)
        else appendAssistant(set, text)
      }
    }
    return
  }

  // A live token delta for the current answer (only emitted when the backend
  // LLM is configured with stream=true). Builds the assistant bubble
  // incrementally; the trailing MessageEvent finalizes it. Also mirrors the
  // stream onto a live "responding…" activity step so the sidebar reflects the
  // agent's plain-text work in real time, not just its tool calls.
  if (kind === 'StreamingDeltaEvent') {
    if (typeof evt.content === 'string' && evt.content.length > 0) {
      respondTextBuffer = (respondTextBuffer + evt.content).slice(-4000)
      appendStreamingDelta(set, evt.content)
      ensureRespondingStep(set)
      maybePaintRespondingStep(set)
    }
    return
  }

  // The agent decided to call a tool: add a running step to the reasoning feed.
  if (kind === 'ActionEvent') {
    const toolName: string = evt.tool_name || 'tool'
    // The final answer is delivered via MessageEvent; don't clutter the feed
    // with the internal "finish" call.
    if (toolName === 'finish') return

    const params = extractActionParams(evt.action)

    // We no longer eagerly open Approval cards here for HR_ACTION_TOOL_NAMES, 
    // because we want the backend's SecurityAnalyzer and ConfirmationPolicy to 
    // dictate when an approval is required (i.e. via 'waiting_for_confirmation' status).
    // So we just push it as a running step and wait for the backend's decision.
    pushActivity(set, {
      id: newId('act'),
      category: categoryForTool(toolName),
      title: titleForAction(evt),
      detail: argsSummary(evt.action),
      status: 'running',
      createdAtMs: Date.now(),
      toolCallId: evt.tool_call_id,
      toolName,
      rawParams: params,
    })
    return
  }

  // A tool returned: close out the matching step (success or error) and, on
  // success, surface any structured result on the Side Canvas for review.
  if (kind === 'ObservationEvent') {
    const isErr = !!evt.observation?.is_error
    updateActivityByToolCall(set, evt.tool_call_id, {
      status: isErr ? 'error' : 'success',
      endedAtMs: Date.now(),
      ...(isErr ? { detail: truncate(observationText(evt.observation)) || 'Tool error' } : {}),
    })
    return
  }

  if (kind === 'UserRejectObservation') {
    updateActivityByToolCall(set, evt.tool_call_id, {
      status: 'warn',
      endedAtMs: Date.now(),
      detail: truncate(evt.rejection_reason || 'Rejected'),
    })
    return
  }

  // Conversation-level failure (not fed back to the LLM). Surface it and stop.
  if (kind === 'ConversationErrorEvent') {
    const detail = evt.detail || evt.code || 'The conversation failed.'
    appendSystem(set, `Conversation error: ${detail}`)
    markRunningStepsError(set, truncate(String(detail)))
    finalizeStreaming(set)
    set({ isRunning: false })
    // Stale backend conversations keep the LLM config from when they were
    // created. After switching providers (e.g. Groq → Ollama), reconnecting to
    // an old id produces auth/provider errors. Drop the binding so the next
    // message creates a fresh conversation with the current provider.
    if (isStaleProviderError(detail)) {
      invalidateBackendBinding(get, set)
      appendSystem(
        set,
        'This chat was still bound to an old LLM provider. Send your message again — it will use the current provider (Ollama).',
      )
    }
    return
  }

  if (kind === 'ConversationStateUpdateEvent') {
    const status = readExecutionStatus(evt)
    if (status === 'running') {
      set({ isRunning: true })
    } else if (status === 'waiting_for_confirmation') {
      set({ isRunning: false })
      const { activity } = get()
      // The pending action should be the last step in a 'running' state
      const pendingStep = activity.slice().reverse().find(s => s.status === 'running')
      const conversationId = get().backendConversationId;
      if (pendingStep && pendingStep.toolName && conversationId) {
        updateActivityByToolCall(set, pendingStep.toolCallId, {
          status: 'warn',
          detail: 'Awaiting approval in chat',
        })
        appendApprovalRequest(set, {
          conversationId,
          toolName: pendingStep.toolName,
          title: actionTitle(pendingStep.toolName, pendingStep.rawParams || {}),
          params: pendingStep.rawParams || {},
          risk: String(pendingStep.rawParams?.security_risk || 'HIGH'),
        })
      }
    } else if (status && TERMINAL_STATUSES.has(status)) {
      finishTurn(status, get, set)
    }
    return
  }

  if (kind === 'AgentErrorEvent') {
    const detail = evt.error || evt.detail || evt.message || 'The agent reported an error.'
    // Reflect the failure on the originating tool step when we can match it.
    if (evt.tool_call_id) {
      updateActivityByToolCall(set, evt.tool_call_id, {
        status: 'error',
        endedAtMs: Date.now(),
        detail: truncate(String(detail)),
      })
    }
    appendSystem(set, `Agent error: ${detail}`)
    return
  }

  if (kind === 'ServerErrorEvent') {
    const detail = evt.detail || evt.code || 'Unknown server error'
    appendSystem(set, `Server error: ${detail}`)
    set({ isRunning: false })
    return
  }
}

function finishTurn(status: string, get: Getter, set: Setter) {
  set({ isRunning: false })
  resetRespondingStep()

  // Close out any steps still marked running so the feed doesn't spin forever,
  // and commit any partially streamed answer. A user-initiated stop is not a
  // failure: close those steps as "warn" so the feed reads as cancelled, not
  // broken, and don't fetch the final response for it.
  let stepStatus: EventStatus = status === 'finished' ? 'success' : 'error'
  let cancelled = false
  if (USER_CANCEL_STATUSES.has(status)) {
    stepStatus = 'warn'
    cancelled = true
  }
  const now = Date.now()
  set((state) => ({
    activity: state.activity.map((s) =>
      s.status === 'running' ? { ...s, status: stepStatus, endedAtMs: now } : s,
    ),
  }))
  finalizeStreaming(set)

  if (status === 'error' || status === 'stuck') {
    appendSystem(set, `The agent stopped (${status}).`)
    return
  }
  if (cancelled) {
    appendSystem(set, 'The run was stopped.')
    return
  }

  // status === 'finished'. Some agents deliver their final answer via a
  // finish action rather than a plain message event. If nothing rendered this
  // turn, pull the final response as a fallback (give a trailing message event
  // a brief moment to arrive first).
  if (sawAgentTextThisTurn) return
  const conversationId = get().backendConversationId
  if (!conversationId) return
  setTimeout(async () => {
    if (sawAgentTextThisTurn) return
    try {
      const res = await fetch(
        `/api/chat?conversationId=${encodeURIComponent(conversationId)}&final=1`,
      )
      if (!res.ok) return
      const data = await res.json()
      const text = (data.response || '').trim()
      if (text && !sawAgentTextThisTurn) {
        sawAgentTextThisTurn = true
        appendAssistant(set, text)
      }
    } catch {
      /* ignore */
    }
  }, 500)
}

// ---------------------------------------------------------------------------
// Persistence: chat list, per-chat history, and per-chat backend binding are
// saved to localStorage so closing the tab (or the whole app) and reopening it
// restores the session. Ephemeral runtime state (socket, isRunning, activity)
// is intentionally not persisted.
// ---------------------------------------------------------------------------

const PERSIST_KEY = 'hr-copilot:chats:v3'
const PERSIST_KEY_LEGACY = ['hr-copilot:chats:v2', 'hr-copilot:chats:v1']

interface StoredMessage extends Omit<Message, 'timestamp'> {
  timestamp: number
}

interface PersistShape {
  conversations: ConversationMeta[]
  activeId: string | null
  messagesByChat: Record<string, StoredMessage[]>
  backendIdByChat: Record<string, string>
}

/** True when the error means this backend conversation's baked-in LLM is unusable. */
function isStaleProviderError(detail: unknown): boolean {
  const s = String(detail || '').toLowerCase()
  return (
    s.includes('invalid_api_key') ||
    s.includes('invalid api key') ||
    s.includes('authentication') ||
    s.includes('llmauthenticationerror') ||
    s.includes('resource_exhausted') ||
    s.includes('ollamaexception') ||
    s.includes('apiconnectionerror') ||
    (s.includes('groqexception') && s.includes('api')) ||
    (s.includes('badrequesterror') &&
      (s.includes('api key') || s.includes('api_key') || s.includes('gemini')))
  )
}

/** Drop the active chat's backend conversation binding and close the socket. */
function invalidateBackendBinding(get: Getter, set: Setter) {
  const activeId = get().activeId
  resetConnection(get, set)
  if (!activeId) return
  set((state) => {
    const backendIdByChat = { ...state.backendIdByChat }
    delete backendIdByChat[activeId]
    return { backendIdByChat, backendConversationId: null }
  })
}

function serializeMessages(messages: Message[]): StoredMessage[] {
  return messages.map((m) => ({
    ...m,
    timestamp: m.timestamp instanceof Date ? m.timestamp.getTime() : (m.createdAt ?? Date.now()),
  }))
}

function reviveMessages(messages: StoredMessage[] | undefined): Message[] {
  if (!Array.isArray(messages)) return []
  return messages.map((m) => ({
    ...m,
    timestamp: new Date(typeof m.timestamp === 'number' ? m.timestamp : (m.createdAt ?? Date.now())),
  }))
}

function persistState(state: ChatState) {
  if (typeof window === 'undefined') return
  // Fold the active chat's live messages back into the map before writing.
  const messagesByChat: Record<string, StoredMessage[]> = {}
  for (const [id, msgs] of Object.entries(state.messagesByChat)) {
    messagesByChat[id] = serializeMessages(msgs)
  }
  if (state.activeId) {
    messagesByChat[state.activeId] = serializeMessages(state.activeConversation)
  }
  const shape: PersistShape = {
    conversations: state.conversations,
    activeId: state.activeId,
    messagesByChat,
    backendIdByChat: state.backendIdByChat,
  }
  try {
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(shape))
  } catch {
    /* quota / private mode — non-fatal */
  }
}

let hydrated = false

function hydrateFromStorage(set: Setter) {
  if (typeof window === 'undefined' || hydrated) return
  hydrated = true
  let shape: PersistShape | null = null
  let fromLegacy = false
  try {
    const raw = window.localStorage.getItem(PERSIST_KEY)
    if (raw) {
      shape = JSON.parse(raw)
    } else {
      // Migrate older persist keys: keep chat list + messages, but DROP backend
      // conversation ids. Those bake in the LLM provider from creation time;
      // reusing them after a provider switch (Ollama ↔ Gemini ↔ Groq) fails.
      for (const key of PERSIST_KEY_LEGACY) {
        const legacy = window.localStorage.getItem(key)
        if (!legacy) continue
        shape = JSON.parse(legacy)
        fromLegacy = true
        window.localStorage.removeItem(key)
        break
      }
    }
  } catch {
    shape = null
  }
  if (!shape) return

  const messagesByChat: Record<string, Message[]> = {}
  for (const [id, msgs] of Object.entries(shape.messagesByChat || {})) {
    messagesByChat[id] = reviveMessages(msgs)
  }
  const activeId = shape.activeId ?? null
  // Fresh provider bindings after migration; keep them for same-session v2 loads.
  const backendIdByChat = fromLegacy ? {} : shape.backendIdByChat || {}
  set({
    conversations: shape.conversations || [],
    activeId,
    messagesByChat,
    backendIdByChat,
    activeConversation: activeId ? (messagesByChat[activeId] ?? []) : [],
    backendConversationId: activeId ? (backendIdByChat[activeId] ?? null) : null,
  })
}

// Debounced write on any relevant state change. Runs once per module load.
if (typeof window !== 'undefined') {
  let writeTimer: ReturnType<typeof setTimeout> | undefined
  useChat.subscribe((state) => {
    clearTimeout(writeTimer)
    writeTimer = setTimeout(() => persistState(state), 250)
  })
}

export function ChatProvider({ children }: { children: ReactNode }) {
  // Restore the persisted session once, on the client, after mount to avoid an
  // SSR/CSR hydration mismatch.
  useEffect(() => {
    useChat.getState().hydrate()
  }, [])
  return children
}

export function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  return `${days} d ago`
}

export { MODELS, TONES, DATA_SOURCES }
