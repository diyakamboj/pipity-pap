"use client"

import { useState, type ReactNode } from "react"
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  Boxes,
  Brain,
  Check,
  ChevronRight,
  CircleDashed,
  Cpu,
  Database,
  FileText,
  GitBranch,
  ListTodo,
  Loader2,
  Network,
  Plug,
  RefreshCw,
  Terminal,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import type { EventCategory, EventStatus, RunEvent } from "@/lib/agent-runtime"
import { fmtDuration } from "@/lib/agent-runtime"
import { cn } from "@/lib/utils"

export const CATEGORY_META: Record<EventCategory, { label: string; icon: LucideIcon; color: string }> = {
  step: { label: "Execution step", icon: GitBranch, color: "text-neutral-300" },
  skill: { label: "Skill", icon: Boxes, color: "text-neutral-300" },
  tool: { label: "Tool call", icon: Wrench, color: "text-neutral-300" },
  mcp: { label: "MCP server", icon: Plug, color: "text-neutral-300" },
  memory: { label: "Memory", icon: Brain, color: "text-neutral-300" },
  database: { label: "Database", icon: Database, color: "text-neutral-300" },
  subagent: { label: "Sub-agent", icon: Network, color: "text-neutral-300" },
  task: { label: "Task", icon: ListTodo, color: "text-neutral-300" },
  file: { label: "File", icon: FileText, color: "text-neutral-300" },
  api: { label: "API request", icon: ArrowLeftRight, color: "text-neutral-300" },
  log: { label: "Log", icon: Terminal, color: "text-neutral-400" },
  error: { label: "Error", icon: AlertTriangle, color: "text-neutral-300" },
  retry: { label: "Retry", icon: RefreshCw, color: "text-neutral-300" },
}

export const PHASE_ICON = {
  thinking: Brain,
  planning: Activity,
  executing: Cpu,
  finished: ListTodo,
} as const

/** Small status glyph reflecting an event's lifecycle. */
export function StatusGlyph({ status, className }: { status: EventStatus; className?: string }) {
  if (status === "running")
    return <Loader2 className={cn("h-3.5 w-3.5 animate-spin text-neutral-300", className)} aria-label="running" />
  if (status === "success")
    return (
      <Check
        className={cn("h-3.5 w-3.5 text-neutral-400", className)}
        aria-label="succeeded"
        strokeWidth={2.5}
      />
    )
  if (status === "warn")
    return <AlertTriangle className={cn("h-3.5 w-3.5 text-neutral-400", className)} aria-label="warning" />
  if (status === "error")
    return (
      <AlertTriangle
        className={cn("h-3.5 w-3.5 text-neutral-200", className)}
        aria-label="error"
        strokeWidth={2.5}
      />
    )
  return <CircleDashed className={cn("h-3.5 w-3.5 text-neutral-600", className)} aria-label="pending" />
}

export function LiveDot({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <span className="relative flex h-2 w-2" aria-label="live">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neutral-400 opacity-60" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-neutral-300" />
    </span>
  )
}

/** Collapsible section shell used for every activity group in the panel. */
export function Section({
  icon: Icon,
  title,
  count,
  live,
  defaultOpen = false,
  accent = "text-neutral-400",
  children,
}: {
  icon: LucideIcon
  title: string
  count?: number
  live?: boolean
  defaultOpen?: boolean
  accent?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const empty = count === 0
  return (
    <div className="border-b border-white/[0.06]">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={empty}
        aria-expanded={open}
        className={cn(
          "group flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors",
          empty ? "cursor-default opacity-40" : "hover:bg-white/[0.03]",
        )}
      >
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-neutral-500 transition-transform duration-300",
            open && !empty && "rotate-90",
          )}
        />
        <Icon className={cn("h-4 w-4 shrink-0", accent)} />
        <span className="flex-1 text-[13px] font-medium text-neutral-200">{title}</span>
        {live && <LiveDot active />}
        {typeof count === "number" && (
          <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium tabular-nums text-neutral-400">
            {count}
          </span>
        )}
      </button>
      {open && !empty && <div className="px-3 pb-3">{children}</div>}
    </div>
  )
}

/** One activity line: glyph, title, optional detail + meta chips + duration. */
export function EventRow({
  event,
  elapsedMs,
  compact = false,
}: {
  event: RunEvent
  elapsedMs: number
  compact?: boolean
}) {
  const meta = CATEGORY_META[event.category]
  const Icon = meta.icon
  const running = event.status === "running"
  const dur = event.endedAt != null ? event.endedAt - event.startedAt : Math.max(0, elapsedMs - event.startedAt)

  return (
    <div className="dream-fade flex items-start gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.03]">
      <StatusGlyph status={event.status} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {!compact && <Icon className={cn("h-3.5 w-3.5 shrink-0", meta.color)} />}
          <span
            className={cn(
              "min-w-0 flex-1 truncate text-[12.5px] leading-tight",
              event.status === "error"
                ? "text-neutral-100"
                : event.status === "warn"
                  ? "text-neutral-300"
                  : "text-neutral-200",
            )}
          >
            {event.title}
          </span>
          <span
            className={cn(
              "shrink-0 text-[10.5px] tabular-nums",
              running ? "text-neutral-300" : "text-neutral-500",
            )}
          >
            {fmtDuration(dur)}
          </span>
        </div>
        {event.detail && (
          <p className="mt-0.5 truncate text-[11px] leading-tight text-neutral-500">{event.detail}</p>
        )}
        {event.meta && event.meta.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {event.meta.map((m) => (
              <span
                key={m.label}
                className="rounded border border-white/[0.06] bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-neutral-400"
              >
                <span className="text-neutral-500">{m.label}:</span> {m.value}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Slim animated progress bar used by tasks + overall progress. */
export function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/[0.08]", className)}>
      <div
        className="h-full rounded-full bg-neutral-300 transition-[width] duration-500 ease-out"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}
