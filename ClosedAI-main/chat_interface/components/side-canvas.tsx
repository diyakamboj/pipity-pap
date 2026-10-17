"use client"

import { useEffect, useState } from "react"
import { LayoutPanelLeft, PanelRightClose, X } from "lucide-react"
import { useCanvas } from "@/lib/canvas-store"
import { useChat } from "@/lib/chat-store"
import { UiBlockCanvas } from "@/components/ui-block-canvas"
import { cn } from "@/lib/utils"
import type { CanvasStatePayload } from "@/lib/canvas-types"

/**
 * Right-hand Side Canvas: a downstream consumer of completed conversation
 * events. It renders generated ui-block state from /api/canvas/state and does
 * not ingest tool observations directly from the chat execution path.
 */
export function SideCanvas() {
  const open = useCanvas((s) => s.open)
  const setOpen = useCanvas((s) => s.setOpen)
  const setServerBlockCount = useCanvas((s) => s.setServerBlockCount)
  const backendConversationId = useChat((s) => s.backendConversationId)
  const [serverCanvas, setServerCanvas] = useState<CanvasStatePayload | null>(null)

  const hasServerBlocks = !!serverCanvas?.blocks.length

  useEffect(() => {
    if (!backendConversationId) {
      setServerCanvas(null)
      setServerBlockCount(0)
      setOpen(false)
      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let intervalMs = 1000

    const poll = async () => {
      try {
        const res = await fetch(`/api/canvas/state?conversationId=${encodeURIComponent(backendConversationId)}`)
        if (!res.ok) return
        const data = await res.json() as CanvasStatePayload
        if (cancelled) return
        console.info('[canvas-trace]', JSON.stringify({
          conversationId: backendConversationId,
          turnId: data.turnId ?? null,
          stage: 'UiBlockCanvas receives state',
          timestamp: new Date().toISOString(),
          status: 'success',
          canvasStatus: data.status,
          count: data.blocks.length,
        }))
        setServerCanvas(data)
        setServerBlockCount(data.blocks.length)
        intervalMs = data.status === 'evaluating' ? 750 : 2500
      } catch (error) {
        if (!cancelled) {
          console.info('[canvas-trace]', JSON.stringify({
            conversationId: backendConversationId,
            turnId: null,
            stage: 'UiBlockCanvas receives state',
            timestamp: new Date().toISOString(),
            status: 'failure',
            error: error instanceof Error ? error.message : String(error),
          }))
        }
      } finally {
        if (!cancelled) timer = setTimeout(poll, intervalMs)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      setServerCanvas(null)
      setServerBlockCount(0)
    }
  }, [backendConversationId, setOpen, setServerBlockCount])

  useEffect(() => {
    if (hasServerBlocks) setOpen(true)
  }, [hasServerBlocks, setOpen])

  return (
    <aside
      aria-hidden={!open}
      className={cn(
        "relative z-10 shrink-0 overflow-hidden border-l border-white/[0.06] transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
        open ? "w-[440px]" : "w-0",
      )}
    >
      <div className="flex h-full w-[440px] flex-col bg-[#0a0a0a]/85 backdrop-blur-xl">
        {/* Header */}
        <div className="shrink-0 border-b border-white/[0.06] px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <LayoutPanelLeft className="h-4 w-4 shrink-0 text-neutral-400" />
              <span className="truncate text-[13px] font-semibold text-neutral-100">
                Side Canvas
              </span>
            </div>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close side canvas"
              className="rounded-md p-1 text-neutral-500 transition-colors hover:bg-white/[0.06] hover:text-neutral-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {hasServerBlocks ? (
            <UiBlockCanvas
              blocks={serverCanvas.blocks}
              conversationId={serverCanvas.conversationId}
              turnId={serverCanvas.turnId}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <LayoutPanelLeft className="h-8 w-8 text-neutral-700" />
              <p className="text-[13px] font-medium text-neutral-400">Nothing to review yet</p>
              <p className="text-[12px] text-neutral-600">
                Rich results from completed tasks appear here when Canvas adds value.
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}

/** Header toggle for the Side Canvas; badges the number of available modules. */
export function CanvasToggle() {
  const open = useCanvas((s) => s.open)
  const serverBlockCount = useCanvas((s) => s.serverBlockCount)
  const toggle = useCanvas((s) => s.toggle)

  if (serverBlockCount === 0) return null

  return (
    <button
      onClick={toggle}
      aria-label="Toggle side canvas"
      aria-pressed={open}
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors",
        open
          ? "border-white/15 bg-white/[0.08] text-neutral-100"
          : "border-white/10 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.07]",
      )}
    >
      <PanelRightClose className="h-4 w-4" />
      <span className="hidden sm:inline">Canvas</span>
      <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-white/10 px-1 text-[10px] tabular-nums text-neutral-300">
        {serverBlockCount}
      </span>
    </button>
  )
}
