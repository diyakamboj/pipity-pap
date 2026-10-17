"use client"

import { Activity, ChevronRight, Loader2, Square, X } from "lucide-react"
import {
  useAgentRuntime,
  fmtClock,
  STATUS_LABEL,
  type RunStatus,
} from "@/lib/agent-runtime"
import { PHASE_ICON, ProgressBar } from "@/components/agent-primitives"
import {
  ApiSection,
  DatabaseSection,
  ErrorsSection,
  FilesSection,
  LogsSection,
  McpSection,
  MemorySection,
  SkillsSection,
  StepsSection,
  SubAgentsSection,
  TasksSection,
  TimelineSection,
  ToolsSection,
} from "@/components/agent-sections"
import { cn } from "@/lib/utils"

const PHASES: RunStatus[] = ["thinking", "planning", "executing", "finished"]

const STATUS_STYLES: Record<RunStatus, { dot: string; text: string; ring: string }> = {
  idle: { dot: "bg-neutral-600", text: "text-neutral-500", ring: "ring-white/10" },
  thinking: { dot: "bg-neutral-300", text: "text-neutral-300", ring: "ring-white/15" },
  planning: { dot: "bg-neutral-300", text: "text-neutral-300", ring: "ring-white/15" },
  executing: { dot: "bg-neutral-100", text: "text-neutral-100", ring: "ring-white/20" },
  finished: { dot: "bg-neutral-400", text: "text-neutral-400", ring: "ring-white/10" },
  error: { dot: "bg-neutral-200", text: "text-neutral-200", ring: "ring-white/20" },
}

function overallProgress(status: RunStatus, tasks: { progress?: number }[]): number {
  if (status === "finished") return 100
  if (tasks.length > 0) {
    const avg = tasks.reduce((sum, t) => sum + (t.progress ?? 0), 0) / tasks.length
    // blend so it never sits at exactly 0 while clearly working
    return Math.max(status === "idle" ? 0 : 8, Math.round(avg))
  }
  return { idle: 0, thinking: 6, planning: 20, executing: 45, finished: 100, error: 100 }[status]
}

/** Header button that opens the live activity panel; pulses while running. */
export function AgentActivityToggle() {
  const { isRunning, hasRun, panelOpen, togglePanel, status } = useAgentRuntime()
  const styles = STATUS_STYLES[status]
  return (
    <button
      onClick={togglePanel}
      aria-label="Toggle agent activity panel"
      aria-pressed={panelOpen}
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors",
        panelOpen
          ? "border-white/15 bg-white/[0.08] text-neutral-100"
          : "border-white/10 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.07]",
      )}
    >
      {isRunning ? (
        <Loader2 className="h-4 w-4 animate-spin text-neutral-300" />
      ) : (
        <Activity className={cn("h-4 w-4", hasRun ? styles.text : "text-neutral-400")} />
      )}
      <span className="hidden sm:inline">Activity</span>
      {(isRunning || (hasRun && !panelOpen)) && <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot)} />}
    </button>
  )
}

function PhaseStepper() {
  const { status, phases } = useAgentRuntime()
  const currentIdx = PHASES.indexOf(status === "error" ? "executing" : status)
  return (
    <div className="flex items-center gap-1">
      {PHASES.map((p, i) => {
        const Icon = PHASE_ICON[p as keyof typeof PHASE_ICON]
        const done = currentIdx > i || status === "finished"
        const active = currentIdx === i && status !== "finished"
        const phase = phases[p]
        const dur = phase?.end != null && phase.start != null ? phase.end - phase.start : null
        return (
          <div key={p} className="flex items-center gap-1">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition-colors",
                active
                  ? "bg-white/[0.08] text-neutral-100"
                  : done
                    ? "text-neutral-400"
                    : "text-neutral-600",
              )}
            >
              {active ? <Loader2 className="h-3 w-3 animate-spin" /> : <Icon className="h-3 w-3" />}
              <span className="capitalize">{p}</span>
              {dur != null && <span className="tabular-nums text-neutral-600">{(dur / 1000).toFixed(1)}s</span>}
            </div>
            {i < PHASES.length - 1 && (
              <ChevronRight className={cn("h-3 w-3", currentIdx > i ? "text-neutral-500" : "text-neutral-700")} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function AgentExecutionPanel() {
  const { panelOpen, setPanelOpen, status, elapsedMs, events, isRunning, stopRun, prompt } = useAgentRuntime()
  const styles = STATUS_STYLES[status]
  const tasks = events.filter((e) => e.category === "task")
  const progress = overallProgress(status, tasks)

  return (
    <aside
      aria-hidden={!panelOpen}
      className={cn(
        "relative z-10 shrink-0 overflow-hidden border-l border-white/[0.06] transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
        panelOpen ? "w-[400px]" : "w-0",
      )}
    >
      <div className="flex h-full w-[400px] flex-col bg-[#0a0a0a]/80 backdrop-blur-xl">
        {/* Header */}
        <div className="shrink-0 border-b border-white/[0.06] px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ring-1",
                  styles.text,
                  styles.ring,
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot, isRunning && "animate-pulse")} />
                {STATUS_LABEL[status]}
              </div>
              <span className="text-[12px] tabular-nums text-neutral-500">{fmtClock(elapsedMs)}</span>
            </div>
            <div className="flex items-center gap-1">
              {isRunning && (
                <button
                  onClick={stopRun}
                  aria-label="Stop run"
                  className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-neutral-300 transition-colors hover:bg-white/[0.08]"
                >
                  <Square className="h-3 w-3" />
                  Stop
                </button>
              )}
              <button
                onClick={() => setPanelOpen(false)}
                aria-label="Close activity panel"
                className="rounded-md p-1 text-neutral-500 transition-colors hover:bg-white/[0.06] hover:text-neutral-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <ProgressBar value={progress} className="flex-1" />
            <span className="text-[11px] tabular-nums text-neutral-400">{progress}%</span>
          </div>

          <div className="mt-3 overflow-x-auto pb-0.5">
            <PhaseStepper />
          </div>

          {prompt && (
            <p className="mt-2.5 truncate text-[11px] text-neutral-500">
              <span className="text-neutral-600">objective:</span> {prompt}
            </p>
          )}
        </div>

        {/* Sections */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {status === "idle" ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <Activity className="h-8 w-8 text-neutral-700" />
              <p className="text-[13px] font-medium text-neutral-400">No active run</p>
              <p className="text-[12px] text-neutral-600">Send a message to watch the agent work in real time.</p>
            </div>
          ) : (
            <>
              <TimelineSection />
              <TasksSection />
              <StepsSection />
              <ToolsSection />
              <SubAgentsSection />
              <McpSection />
              <SkillsSection />
              <MemorySection />
              <DatabaseSection />
              <FilesSection />
              <ApiSection />
              <ErrorsSection />
              <LogsSection />
            </>
          )}
        </div>
      </div>
    </aside>
  )
}
