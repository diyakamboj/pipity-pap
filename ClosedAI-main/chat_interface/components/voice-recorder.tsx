"use client"

import { useEffect, useState } from "react"
import { X, Check } from "lucide-react"
import { Button } from "@/components/ui/button"

interface VoiceRecorderProps {
  onCancel: () => void
  onConfirm: (transcript: string) => void
  barCount?: number
}

// Simulated voice capture UI. Backend transcription can be wired in later via onConfirm.
export function VoiceRecorder({ onCancel, onConfirm, barCount = 60 }: VoiceRecorderProps) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0")
  const ss = String(seconds % 60).padStart(2, "0")

  return (
    <div className="dream-pop mb-3 rounded-full border border-white/10 bg-background px-6 py-3">
      <div className="flex items-center justify-between gap-6">
        <div className="flex shrink-0 items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-destructive" />
          <p className="text-sm font-medium text-foreground">Recording</p>
          <span className="font-mono text-xs text-muted-foreground tabular-nums">
            {mm}:{ss}
          </span>
        </div>

        <div className="flex h-10 flex-1 items-center justify-center gap-[2px] overflow-hidden">
          {Array.from({ length: barCount }).map((_, i) => (
            <div
              key={i}
              className="voice-wave-bar-horizontal shrink-0 rounded-full bg-foreground/70"
              style={{ width: "2px", animationDelay: `${-i * 0.03}s`, animationDirection: "reverse" }}
            />
          ))}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Cancel recording"
            className="btn-3d h-8 w-8 rounded-full bg-secondary/30 text-white hover:bg-destructive/20 hover:text-destructive"
            onClick={onCancel}
          >
            <X className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            aria-label="Confirm recording"
            className="btn-3d btn-glow h-8 w-8 rounded-full bg-gradient-to-br from-primary via-gray-900 to-black text-white shadow-xl hover:from-gray-900 hover:to-black"
            onClick={() => onConfirm("Combine those two files and summarize results")}
          >
            <Check className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
