"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useChat, type ActivityStep } from "./chat-store"

export type RunStatus = "idle" | "thinking" | "planning" | "executing" | "finished" | "error"
export type EventStatus = "pending" | "running" | "success" | "warn" | "error"
export type EventCategory =
  | "step"
  | "skill"
  | "tool"
  | "mcp"
  | "memory"
  | "database"
  | "subagent"
  | "task"
  | "file"
  | "api"
  | "log"
  | "error"
  | "retry"

export interface EventMeta {
  label: string
  value: string
}

export interface RunEvent {
  id: string
  category: EventCategory
  title: string
  detail?: string
  status: EventStatus
  /** ms relative to run start */
  startedAt: number
  endedAt?: number
  progress?: number
  parentId?: string
  level?: "info" | "warn" | "error" | "debug"
  meta?: EventMeta[]
}

interface RunState {
  runId: string | null
  prompt: string
  status: RunStatus
  events: RunEvent[]
  startedAt: number | null
  elapsedMs: number
  phases: Partial<Record<RunStatus, { start: number; end?: number }>>
}

interface AgentRuntimeValue extends RunState {
  isRunning: boolean
  hasRun: boolean
  panelOpen: boolean
  setPanelOpen: (v: boolean) => void
  togglePanel: () => void
  startRun: (prompt: string) => void
  stopRun: () => void
}

const AgentRuntimeContext = createContext<AgentRuntimeValue | null>(null)

function uid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID()
  return Math.random().toString(36).slice(2)
}

const INITIAL: RunState = {
  runId: null,
  prompt: "",
  status: "idle",
  events: [],
  startedAt: null,
  elapsedMs: 0,
  phases: {},
}

// Convert the store's absolute-timestamped reasoning steps into RunEvents with
// run-relative offsets (what the panel/feed render against `elapsedMs`).
function mapActivity(steps: ActivityStep[], origin: number | null): RunEvent[] {
  const base = origin ?? (steps.length > 0 ? steps[0].createdAtMs : 0)
  return steps.map((s) => ({
    id: s.id,
    category: s.category,
    title: s.title,
    detail: s.detail,
    status: s.status,
    startedAt: Math.max(0, s.createdAtMs - base),
    endedAt: s.endedAtMs != null ? Math.max(0, s.endedAtMs - base) : undefined,
    level: s.level,
  }))
}

function closePhases(s: RunState): RunState["phases"] {
  const rel = s.startedAt == null ? s.elapsedMs : Date.now() - s.startedAt
  const phases = { ...s.phases }
  if (s.status !== "idle" && phases[s.status]) {
    phases[s.status] = { ...phases[s.status]!, end: rel }
  }
  return phases
}

export function AgentRuntimeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<RunState>(INITIAL)
  const [panelOpen, setPanelOpen] = useState(false)
  const clockRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // The real run lifecycle is owned by the chat store: it opens the WebSocket,
  // streams events, and flips `isRunning` off when the backend reports a
  // terminal execution status. This panel mirrors that state and renders the
  // live reasoning steps the store derives from the backend event stream.
  const chatRunning = useChat((s) => s.isRunning)
  const cancelRun = useChat((s) => s.cancelRun)
  const activity = useChat((s) => s.activity)
  const activityStartedAt = useChat((s) => s.activityStartedAt)
  const prevRunningRef = useRef(false)

  // Live steps mapped into RunEvents, timed relative to the run start.
  const events = useMemo(
    () => mapActivity(activity, state.startedAt ?? activityStartedAt),
    [activity, state.startedAt, activityStartedAt],
  )

  const stopClock = useCallback(() => {
    if (clockRef.current) {
      clearInterval(clockRef.current)
      clockRef.current = null
    }
  }, [])

  const startClock = useCallback(() => {
    stopClock()
    clockRef.current = setInterval(() => {
      setState((s) => {
        if (s.startedAt == null) return s
        if (s.status === "finished" || s.status === "error" || s.status === "idle") return s
        return { ...s, elapsedMs: Date.now() - s.startedAt }
      })
    }, 100)
  }, [stopClock])

  useEffect(() => () => stopClock(), [stopClock])

  const startRun = useCallback(
    (prompt: string) => {
      const t0 = Date.now()
      setState({
        runId: uid(),
        prompt,
        status: "executing",
        events: [],
        startedAt: t0,
        elapsedMs: 0,
        phases: { executing: { start: 0 } },
      })
      setPanelOpen(true)
      startClock()
    },
    [startClock],
  )

  const stopRun = useCallback(() => {
    stopClock()
    cancelRun?.()
    setState((s) => (s.status === "idle" ? s : { ...s, status: "finished" }))
  }, [cancelRun, stopClock])

  // Mirror the chat store's run lifecycle onto the panel status.
  useEffect(() => {
    if (chatRunning && !prevRunningRef.current) {
      // A run started (defensive: also handles runs not begun via startRun).
      setState((s) => (s.status === "executing" ? s : { ...s, status: "executing" }))
    }
    if (!chatRunning && prevRunningRef.current) {
      // Run just finished.
      stopClock()
      setState((s) => (s.status === "idle" ? s : { ...s, status: "finished", phases: closePhases(s) }))
    }
    prevRunningRef.current = chatRunning
  }, [chatRunning, stopClock])

  const isRunning = chatRunning

  const value = useMemo<AgentRuntimeValue>(
    () => ({
      ...state,
      // Real steps from the chat store's event stream override the placeholder
      // (always empty) events kept in local state.
      events,
      isRunning,
      hasRun: state.runId !== null || events.length > 0,
      panelOpen,
      setPanelOpen,
      togglePanel: () => setPanelOpen((v) => !v),
      startRun,
      stopRun,
    }),
    [state, events, isRunning, panelOpen, startRun, stopRun],
  )

  return <AgentRuntimeContext.Provider value={value}>{children}</AgentRuntimeContext.Provider>
}

export function useAgentRuntime() {
  const ctx = useContext(AgentRuntimeContext)
  if (!ctx) throw new Error("useAgentRuntime must be used within an AgentRuntimeProvider")
  return ctx
}

// ---- formatting + presentation helpers shared by the panel ----

export function fmtDuration(ms: number): string {
  if (ms < 0) ms = 0
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function fmtClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export const STATUS_LABEL: Record<RunStatus, string> = {
  idle: "Idle",
  thinking: "Thinking",
  planning: "Planning",
  executing: "Executing",
  finished: "Finished",
  error: "Error",
}
