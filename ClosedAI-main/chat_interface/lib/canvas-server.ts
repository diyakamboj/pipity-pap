import fs from 'node:fs'
import path from 'node:path'

import type { CanvasBlock, CanvasStatePayload } from '@/lib/canvas-types'

type TraceStatus = 'success' | 'failure' | 'info'

interface TraceDetails {
  turnId?: string | null
  success?: boolean
  count?: number
  status?: string | null
  error?: string
  [key: string]: unknown
}

interface ConversationRecord {
  conversationId: string
  turnId: string | null
  events: any[]
  eventKeys: Set<string>
  terminalKeys: Set<string>
  processing: boolean
  processedTerminalKey: string | null
  pendingTerminalKey: string | null
  pendingTerminalTimer: ReturnType<typeof setTimeout> | null
  state: CanvasStatePayload
  pose: Record<string, unknown>
}

export interface EvaluatorResult {
  workflow_detected: boolean
  canvas_worthy: boolean
  workflow_type: string | null
  reason: string
}

const TERMINAL_STATUSES = new Set(['finished', 'error', 'stuck', 'paused', 'interrupted', 'stopped'])
const records = new Map<string, ConversationRecord>()

function nowIso(): string {
  return new Date().toISOString()
}

function cleanId(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed || null
}

function normalizeConversationId(value: string): string {
  return value.replace(/-/g, '').toLowerCase()
}

function trace(conversationId: string, stage: string, status: TraceStatus, details: TraceDetails = {}) {
  const safeDetails = { ...details }
  delete safeDetails.prompt
  delete safeDetails.content
  delete safeDetails.llm_message
  console.info('[canvas-trace]', JSON.stringify({
    conversationId,
    turnId: details.turnId ?? null,
    stage,
    timestamp: nowIso(),
    status,
    ...safeDetails,
  }))
}

function emptyState(conversationId: string): CanvasStatePayload {
  return {
    conversationId,
    turnId: null,
    status: 'empty',
    blocks: [],
    updatedAt: nowIso(),
  }
}

function getRecord(conversationId: string): ConversationRecord {
  conversationId = normalizeConversationId(conversationId)
  let record = records.get(conversationId)
  if (!record) {
    record = {
      conversationId,
      turnId: null,
      events: [],
      eventKeys: new Set(),
      terminalKeys: new Set(),
      processing: false,
      processedTerminalKey: null,
      pendingTerminalKey: null,
      pendingTerminalTimer: null,
      state: emptyState(conversationId),
      pose: {},
    }
    records.set(conversationId, record)
  }
  return record
}

function eventKey(evt: any, index: number): string {
  const kind = cleanId(evt?.kind) || 'event'
  return cleanId(evt?.id) || cleanId(evt?.event_id) || (cleanId(evt?.tool_call_id) ? `${kind}:${evt.tool_call_id}` : null) || `${kind}:${index}:${JSON.stringify(evt).slice(0, 300)}`
}

function eventText(evt: any): string {
  const pieces = [
    evt?.kind,
    evt?.tool_name,
    evt?.action?.name,
    evt?.action?.tool_name,
    evt?.observation?.content,
    evt?.observation?.result,
    evt?.observation?.text,
    evt?.status,
    evt?.execution_status,
  ]
  return pieces.filter((p) => typeof p === 'string').join(' ').toLowerCase()
}

function semanticEventText(evt: any): string {
  return [
    eventText(evt),
    evt?.tool_name,
    stringifyForSearch(evt?.action),
    stringifyForSearch(evt?.observation),
  ]
    .filter(Boolean)
    .join(' ')
    .replace(/_/g, ' ')
    .toLowerCase()
}

function readExecutionStatus(evt: any): string | null {
  const raw =
    evt?.execution_status ||
    evt?.status ||
    evt?.state?.execution_status ||
    evt?.conversation?.execution_status ||
    evt?.data?.execution_status
  if (typeof raw !== 'string') return null
  return raw.toLowerCase()
}

function isFinalAgentMessage(evt: any): boolean {
  return evt?.kind === 'MessageEvent' && evt?.source === 'agent'
}

function terminalKey(evt: any, record: ConversationRecord): string | null {
  const status = readExecutionStatus(evt)
  if (!status || !TERMINAL_STATUSES.has(status)) return null
  const turnId = cleanId(evt?.turn_id) || cleanId(evt?.turnId) || cleanId(evt?.head_id) || cleanId(evt?.leaf_event_id) || `events:${record.events.length}`
  record.turnId = turnId
  return `${turnId}:${status}`
}

function summarizePose(record: ConversationRecord): Record<string, unknown> {
  return {
    ...record.pose,
    subject: inferSubject(record.events),
  }
}

function inferSubject(events: any[]): string | null {
  const joined = JSON.stringify(events).slice(0, 10000)
  const match = joined.match(/\b([A-Z][a-z]+ [A-Z][a-z]+)\b/)
  return match?.[1] || null
}

function toolNames(events: any[]): string[] {
  return Array.from(new Set(events.map((evt) => cleanId(evt?.tool_name)).filter(Boolean) as string[]))
}

export function shouldEvaluateCanvas(pose: Record<string, unknown>, events: any[]) {
  const names = toolNames(events)
  const actionEvents = events.filter((evt) => evt?.kind === 'ActionEvent')
  const observationEvents = events.filter((evt) => evt?.kind === 'ObservationEvent')
  const text = `${JSON.stringify(pose)} ${names.join(' ')} ${events.map(semanticEventText).join(' ')}`.replace(/_/g, ' ').toLowerCase()
  const structuredOutcome = observationEvents.some((evt) => hasSubstantialStructuredPayload(observationPayload(evt)))
  const longFormOutcome = observationEvents.some((evt) => observationTextLength(evt) >= 280)
  const explicitCanvasLanguage = /\b(show|display|visualize|compare|review|summarize|table|report|draft|form|dashboard|profile|record|workspace)\b/.test(text)
  const batchOrMultiStep = /\bbatch\b|\bmultiple\b|\bworkflow\b|\bdependent\b|\bseveral\b/.test(text) || actionEvents.length >= 3
  const multipleSystems = new Set(names.map((name) => name.split('_')[0])).size > 1 && actionEvents.length > 1
  return {
    candidate: structuredOutcome || longFormOutcome || explicitCanvasLanguage || batchOrMultiStep || multipleSystems,
    reason: { structuredOutcome, longFormOutcome, explicitCanvasLanguage, batchOrMultiStep, multipleSystems, actionCount: actionEvents.length, toolCount: names.length },
  }
}

export function parseEvaluatorResult(raw: unknown): EvaluatorResult {
  const data = typeof raw === 'string' ? parseJsonObject(raw) : raw
  if (!data || typeof data !== 'object') throw new Error('Evaluator returned no JSON object')
  const obj = data as Record<string, unknown>
  return {
    workflow_detected: obj.workflow_detected === true,
    canvas_worthy: obj.canvas_worthy === true,
    workflow_type: typeof obj.workflow_type === 'string' ? obj.workflow_type : null,
    reason: typeof obj.reason === 'string' ? obj.reason.slice(0, 500) : '',
  }
}

export function validateCanvasBlocks(raw: unknown, supportedTypes = loadSupportedBlockTypes()): CanvasBlock[] {
  const data = typeof raw === 'string' ? parseJsonObject(raw) : raw
  const list = Array.isArray(data) ? data : Array.isArray((data as any)?.blocks) ? (data as any).blocks : data ? [data] : []
  const blocks: CanvasBlock[] = []
  for (const item of list) {
    if (!item || typeof item !== 'object') continue
    const block = item as Record<string, unknown>
    if (typeof block.type !== 'string') continue
    if (!supportedTypes.has(block.type)) continue
    if (typeof block.props !== 'object' || block.props === null || Array.isArray(block.props)) continue
    blocks.push({
      type: block.type,
      version: typeof block.version === 'string' || typeof block.version === 'number' ? block.version : 1,
      props: block.props as Record<string, unknown>,
    })
  }
  const sanitized = sanitizeCanvasBlocks(blocks)
  if (sanitized.length === 0) throw new Error('Generator returned no supported Canvas blocks')
  return sanitized
}

function sanitizeCanvasBlocks(blocks: CanvasBlock[]): CanvasBlock[] {
  return blocks
    .filter((block) => !['approval-card', 'approval-compact', 'approval'].includes(block.type))
    .map((block) => {
      const props = { ...block.props }
      delete props.actions
      delete props.buttons
      delete props.primaryAction
      delete props.secondaryAction
      delete props.approveAction
      delete props.rejectAction
      return { ...block, props }
    })
}

function parseJsonObject(raw: string): unknown {
  const trimmed = raw.trim().replace(/^```(?:json|ui-block)?\s*/i, '').replace(/```$/i, '').trim()
  try {
    return JSON.parse(trimmed)
  } catch {
    const match = trimmed.match(/(\{[\s\S]*\}|\[[\s\S]*\])/)
    if (!match) throw new Error('No JSON found')
    return JSON.parse(match[1])
  }
}

function loadBlockCatalog(): string {
  const catalogPath = path.join(process.cwd(), '..', 'agent-ui-blocks-extracted', 'agent-ui-blocks', 'references', 'block-catalog.md')
  return fs.readFileSync(catalogPath, 'utf8')
}

function loadSupportedBlockTypes(): Set<string> {
  try {
    const catalog = loadBlockCatalog()
    return new Set(Array.from(catalog.matchAll(/"type":\s*"([^"]+)"/g)).map((m) => m[1]))
  } catch {
    return new Set(['summary-card', 'freeform-card', 'stepper', 'table', 'email-preview'])
  }
}

async function callConfiguredLlm(system: string, user: string): Promise<string | null> {
  const provider = (process.env.LLM_PROVIDER || process.env.CANVAS_LLM_PROVIDER || '').toLowerCase()
  const timeoutMs = Number(process.env.CANVAS_LLM_TIMEOUT_MS || 15000)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    if (provider === 'openai' && process.env.OPENAI_API_KEY) {
      const baseUrl = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '')
      const res = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
        body: JSON.stringify({
          model: process.env.CANVAS_OPENAI_MODEL || process.env.OPENAI_MODEL || 'gpt-4o-mini',
          temperature: 0,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`OpenAI ${res.status}`)
      const data = await res.json()
      return data?.choices?.[0]?.message?.content || null
    }
    if (provider === 'groq' && process.env.GROQ_API_KEY) {
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.GROQ_API_KEY}` },
        body: JSON.stringify({
          model: process.env.CANVAS_GROQ_MODEL || process.env.GROQ_MODEL || 'llama-3.1-8b-instant',
          temperature: 0,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`Groq ${res.status}`)
      const data = await res.json()
      return data?.choices?.[0]?.message?.content || null
    }
    if (provider === 'ollama') {
      const baseUrl = (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '')
      const res = await fetch(`${baseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: process.env.CANVAS_OLLAMA_MODEL || process.env.OLLAMA_MODEL || 'llama3.1',
          stream: false,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`Ollama ${res.status}`)
      const data = await res.json()
      return data?.message?.content || null
    }
  } finally {
    clearTimeout(timer)
  }
  return null
}

async function evaluateWithFallback(conversationId: string, turnId: string | null, pose: Record<string, unknown>, events: any[]): Promise<EvaluatorResult> {
  const system = [
    'Return only JSON with workflow_detected, canvas_worthy, workflow_type, and reason.',
    'Decide whether the user request plus result events produced a meaningful outcome/content surface.',
    'Task type is not the same thing as Canvas type. Do not limit Canvas to predefined workflows or examples.',
    'Base the decision on what the user wanted, what result/artifact was actually produced or retrieved, and whether that result benefits from persistent side-by-side inspection.',
    'Canvas is for substantial, structured, visual, or reviewable results the user may want to inspect, compare, edit, or reference while continuing the conversation.',
    'Examples include structured records, reports, tables, search results, summaries, comparisons, forms, drafts, workflow state, dashboards, and approval-related draft/status content. These are examples only, not special cases.',
    'Canvas is not for execution/audit reports, chat transcripts, tool calls, internal progress, or generic activity logs.',
    'Small/simple scalar answers should usually stay in chat.',
    'Multiple unrelated scalar lookups should not become a fake workflow Canvas.',
    'If Canvas would not add meaningful review/reference value beyond a short chat answer, set canvas_worthy=false.',
  ].join(' ')
  const user = JSON.stringify({ pose, execution_events: events.map(redactEventForModel) })
  try {
    trace(conversationId, 'evaluator invoked', 'info', { turnId, count: events.length })
    const raw = await callConfiguredLlm(system, user)
    if (raw) {
      const parsed = parseEvaluatorResult(raw)
      trace(conversationId, 'evaluator result', 'success', { turnId, ...parsed })
      return parsed
    }
  } catch (error) {
    trace(conversationId, 'evaluator result', 'failure', { turnId, error: error instanceof Error ? error.message : String(error) })
  }
  const structuredOutcome = events.some((evt) => hasSubstantialStructuredPayload(observationPayload(evt)))
  const longFormOutcome = events.some((evt) => observationTextLength(evt) >= 280)
  const actionCount = events.filter((evt) => evt?.kind === 'ActionEvent').length
  const simpleScalar = events.filter((evt) => evt?.kind === 'ObservationEvent').every((evt) => isScalarPayload(observationPayload(evt)))
  const multipleIndependentScalars = simpleScalar && events.filter((evt) => evt?.kind === 'ObservationEvent').length > 1
  const fallback = {
    workflow_detected: actionCount >= 2,
    canvas_worthy: (structuredOutcome || longFormOutcome || actionCount >= 3) && !multipleIndependentScalars,
    workflow_type: null,
    reason: structuredOutcome || longFormOutcome
      ? 'Deterministic fallback detected a substantial structured or long-form result, but did not choose a task-specific Canvas type.'
      : 'No substantial structured outcome detected by deterministic fallback.',
  }
  trace(conversationId, 'evaluator result', 'success', { turnId, fallback: true, ...fallback })
  return fallback
}

async function generateWithFallback(conversationId: string, turnId: string | null, pose: Record<string, unknown>, events: any[], evaluation: EvaluatorResult): Promise<CanvasBlock[]> {
  const catalog = loadBlockCatalog()
  const system = [
    'Return only JSON. Generate supported Canvas block objects shaped {type,version,props}.',
    'Canvas is a generic outcome/content surface, not a fixed workflow UI and not an execution report.',
    'Dynamically decide the useful presentation for this specific task result using the available block catalog.',
    'Think like a product-minded work-product curator before choosing blocks.',
    'First identify: (1) what the user was trying to accomplish, (2) what the agent actually produced or retrieved, (3) which observed artifacts/results the user needs to inspect or use, and (4) which parts belong only in chat.',
    'The Canvas must represent the meaningful result/work product of the user task: the thing the user needs to inspect, compare, review, edit, reference, or use.',
    'Do not design around hard-coded task types. Examples like onboarding or employee lookup are only quality references, not special cases.',
    'Do not reproduce the chat transcript or execution timeline.',
    'Do not show tool names, MCP operations, database queries, container inspection, integration activation, internal reasoning, execution timings, or implementation details unless they are themselves meaningful user-facing artifacts.',
    'Use execution events only as evidence for determining which real artifacts, results, statuses, and outcomes exist.',
    'Infer the appropriate Canvas structure from the user request, final conversation context, observed result data, and available block catalog.',
    'Possible useful outputs include profiles, tables, comparisons, reports, summaries, workflow state, forms, dashboards, read-only drafts, checklists, search results, and other structured content. This list is illustrative, not exhaustive.',
    'Prefer reusable, generic block types that match the shape of the result. A person/record can be a compact card plus fields; rows or comparisons can be a table; key facts can be a key-value list; drafts can be read-only email/content blocks; process state can be a stepper/checklist-style block; narrative takeaways can be a summary card.',
    'Use multiple blocks when the result has meaningfully different sections. Put the most important overview first, then the primary artifact, then supporting details.',
    'Do not make every event into a block. Collapse low-level details into the user-facing outcome.',
    'Reference examples for selection quality, not implementation: if a task prepares onboarding content, Canvas might show the person/context, assigned benefits or setup facts, read-only email drafts, and next-step status. If a task retrieves a person record, Canvas might show identity/role plus structured fields. If a task compares requests, Canvas might show a short summary plus a sortable-looking table. If a task creates a report, Canvas might show key findings, sections, charts/tables when data exists, and source/status notes.',
    'These examples are not task rules. For any new task, derive the Canvas from the actual observed result and choose the closest supported generic blocks.',
    'Small/simple answers can remain chat-only; if generating blocks, include only content that adds value as a side workspace.',
    'Do not invent missing information or artifacts. If a useful section lacks observed data, omit it or mark it unavailable/pending rather than fabricating details.',
    'Approval buttons belong in chat, never in Canvas. Canvas may show read-only drafts and approval status.',
    'The Canvas should answer: "What does the user need to see to understand and work with the result?"',
  ].join(' ')
  const user = JSON.stringify({
    pose,
    execution_events: events.map(redactEventForModel),
    conversation_messages: events.filter((evt) => evt?.kind === 'MessageEvent').map(redactEventForModel),
    evaluator_result: evaluation,
    block_catalog: catalog.slice(0, 50000),
  })
  try {
    trace(conversationId, 'generator invoked', 'info', { turnId, workflowType: evaluation.workflow_type })
    const raw = await callConfiguredLlm(system, user)
    if (raw) {
      const blocks = validateCanvasBlocks(raw)
      trace(conversationId, 'generator result', 'success', { turnId, count: blocks.length })
      return blocks
    }
  } catch (error) {
    trace(conversationId, 'generator result', 'failure', { turnId, error: error instanceof Error ? error.message : String(error) })
  }
  trace(conversationId, 'generator result', 'failure', { turnId, fallback: true, error: 'No model-generated Canvas blocks available; refusing task-specific fallback.' })
  return []
}

function redactEventForModel(evt: any) {
  return {
    kind: evt?.kind,
    tool_name: evt?.tool_name,
    tool_call_id: evt?.tool_call_id,
    status: readExecutionStatus(evt),
    is_error: !!evt?.observation?.is_error,
    action: evt?.action ? { name: evt.action.name, args: evt.action.args || evt.action.arguments } : undefined,
    observation_summary: summarizeObservation(evt?.observation),
  }
}

function summarizeObservation(observation: any): string | undefined {
  if (!observation) return undefined
  const text = typeof observation === 'string' ? observation : JSON.stringify(observation)
  return text.replace(/api[_-]?key|token|secret|password/gi, '[redacted]').slice(0, 1000)
}

function parseMaybeJson(value: unknown): unknown {
  if (typeof value !== 'string') return value
  const trimmed = value.trim()
  if (!trimmed || !/^[\[{]/.test(trimmed)) return value
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

function observationPayload(evt: any): any {
  const observation = evt?.observation
  if (!observation) return null
  const raw = observation.result ?? observation.content ?? observation.data ?? observation.text ?? observation
  return parseMaybeJson(raw)
}

function observationTextLength(evt: any): number {
  const payload = observationPayload(evt)
  if (typeof payload === 'string') return payload.trim().length
  return stringifyForSearch(payload).length
}

function isScalarPayload(value: unknown): boolean {
  if (value == null) return true
  if (['string', 'number', 'boolean'].includes(typeof value)) return true
  if (Array.isArray(value)) return value.length <= 1 && value.every(isScalarPayload)
  if (typeof value !== 'object') return true
  const entries = Object.entries(value as Record<string, unknown>)
  return entries.length <= 2 && entries.every(([, nested]) => isScalarPayload(nested))
}

function hasSubstantialStructuredPayload(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  if (Array.isArray(value)) {
    return value.length > 1 || value.some((item) => hasSubstantialStructuredPayload(item))
  }
  const entries = Object.entries(value as Record<string, unknown>)
  if (entries.length >= 3) return true
  return entries.some(([, nested]) => hasSubstantialStructuredPayload(nested))
}

function stringifyForSearch(value: unknown): string {
  try {
    return JSON.stringify(value)
  } catch {
    return String(value ?? '')
  }
}

async function runPipeline(record: ConversationRecord, terminal: string) {
  record.pendingTerminalKey = null
  record.pendingTerminalTimer = null
  if (record.processing || record.processedTerminalKey === terminal) {
    trace(record.conversationId, 'terminal deduped', 'info', { turnId: record.turnId, terminal })
    return
  }
  record.processing = true
  record.state = { ...record.state, status: 'evaluating', updatedAt: nowIso() }
  try {
    const pose = summarizePose(record)
    trace(record.conversationId, 'pre-filter invoked', 'info', { turnId: record.turnId, count: record.events.length })
    const prefilter = shouldEvaluateCanvas(pose, record.events)
    trace(record.conversationId, 'pre-filter result', 'success', { turnId: record.turnId, candidate: prefilter.candidate, ...prefilter.reason })
    if (!prefilter.candidate) {
      record.processedTerminalKey = terminal
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      return
    }
    const evaluation = await evaluateWithFallback(record.conversationId, record.turnId, pose, record.events)
    if (!evaluation.canvas_worthy) {
      record.processedTerminalKey = terminal
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      return
    }
    const blocks = await generateWithFallback(record.conversationId, record.turnId, pose, record.events, evaluation)
    record.processedTerminalKey = terminal
    if (blocks.length === 0) {
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      trace(record.conversationId, 'canvas state written', 'success', { turnId: record.turnId, count: 0, stateStatus: 'skipped' })
      return
    }
    record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'ready', blocks, updatedAt: nowIso() }
    trace(record.conversationId, 'canvas state written', 'success', { turnId: record.turnId, count: blocks.length })
  } catch (error) {
    record.state = {
      conversationId: record.conversationId,
      turnId: record.turnId,
      status: 'error',
      blocks: [],
      error: error instanceof Error ? error.message : String(error),
      updatedAt: nowIso(),
    }
    trace(record.conversationId, 'canvas pipeline failed', 'failure', { turnId: record.turnId, error: record.state.error })
  } finally {
    record.processing = false
  }
}

function schedulePipeline(record: ConversationRecord, terminal: string) {
  if (record.processedTerminalKey === terminal || record.pendingTerminalKey === terminal) return
  if (record.pendingTerminalTimer) clearTimeout(record.pendingTerminalTimer)
  record.pendingTerminalKey = terminal
  record.pendingTerminalTimer = setTimeout(() => {
    void runPipeline(record, terminal)
  }, 300)
}

export async function recordCanvasEvents(conversationId: string, events: any[]) {
  conversationId = normalizeConversationId(conversationId)
  const record = getRecord(conversationId)
  trace(conversationId, 'execution event received', 'info', { count: events.length })
  events.forEach((evt, index) => {
    const key = eventKey(evt, index)
    if (evt?.kind === 'StreamingDeltaEvent') return
    if (
      evt?.kind === 'ActionEvent' &&
      record.processedTerminalKey &&
      !record.processing &&
      record.state.status !== 'empty'
    ) {
      const previousCount = record.events.length
      record.state = emptyState(conversationId)
      record.events = []
      record.eventKeys.clear()
      record.terminalKeys.clear()
      record.processedTerminalKey = null
      trace(conversationId, 'canvas state cleared for new turn', 'success', { previousCount })
    }
    if (!record.eventKeys.has(key)) {
      record.eventKeys.add(key)
      record.events.push(evt)
    }
    const terminal = terminalKey(evt, record)
    if (terminal && !record.terminalKeys.has(terminal)) {
      record.terminalKeys.add(terminal)
      trace(conversationId, 'terminal conversation event received', 'success', { turnId: record.turnId, status: readExecutionStatus(evt) })
      schedulePipeline(record, terminal)
    }
    if (isFinalAgentMessage(evt)) {
      const messageTerminal = `message:${key}`
      if (!record.terminalKeys.has(messageTerminal)) {
        record.terminalKeys.add(messageTerminal)
        record.turnId = cleanId(evt?.id) || cleanId(evt?.event_id) || messageTerminal
        trace(conversationId, 'final agent message received', 'success', { turnId: record.turnId })
        schedulePipeline(record, messageTerminal)
      }
    }
  })
  trace(conversationId, 'execution events accumulated', 'success', { turnId: record.turnId, count: record.events.length })
}

export async function recordCanvasConversation(conversation: any) {
  const rawConversationId = cleanId(conversation?.id) || cleanId(conversation?.conversation_id)
  const conversationId = rawConversationId ? normalizeConversationId(rawConversationId) : null
  if (!conversationId) return
  const record = getRecord(conversationId)
  record.pose = { ...record.pose, title: conversation?.title, execution_status: conversation?.execution_status }
  trace(conversationId, 'conversation webhook received', 'success', { status: readExecutionStatus(conversation) })
}

export function readCanvasState(conversationId: string): CanvasStatePayload {
  conversationId = normalizeConversationId(conversationId)
  const record = records.get(conversationId)
  trace(conversationId, 'canvas state requested', 'info')
  const state = record?.state || emptyState(conversationId)
  trace(conversationId, 'canvas state returned', 'success', { turnId: state.turnId, status: state.status, count: state.blocks.length })
  return state
}
