"use client"

import { useState } from "react"
import { ImageIcon, Lightbulb, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ParticleOrb } from "@/components/particle-orb"
import { ChatComposer } from "@/components/chat-composer"

const QUICK_ACTIONS = [
  { icon: ImageIcon, label: "Create Image", prompt: "Create an image of " },
  { icon: Lightbulb, label: "Brainstorm", prompt: "Help me brainstorm ideas about " },
  { icon: FileText, label: "Make a plan", prompt: "Make a plan for " },
]

export function ChatLanding() {
  const [prefill, setPrefill] = useState<{ text: string; nonce: number }>()

  const applyQuickAction = (prompt: string) => {
    setPrefill({ text: prompt, nonce: Date.now() })
  }

  return (
    <div className="relative z-10 flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-6">
      <div className="dream-in mb-6" style={{ animationDelay: "0.05s" }}>
        <ParticleOrb />
      </div>

      <h1
        className="dream-in mb-8 text-center font-[var(--font-heading)] text-4xl font-semibold tracking-tight text-foreground text-balance"
        style={{ animationDelay: "0.15s" }}
      >
        Ready to Create Something New?
      </h1>

      <div className="mb-8 flex flex-wrap items-center justify-center gap-3">
        {QUICK_ACTIONS.map(({ icon: Icon, label, prompt }, i) => (
          <Button
            key={label}
            variant="secondary"
            onClick={() => applyQuickAction(prompt)}
            className="dream-in gap-2 bg-secondary font-medium text-secondary-foreground transition-colors duration-300 hover:bg-foreground hover:text-background"
            style={{ animationDelay: `${0.25 + i * 0.08}s` }}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Button>
        ))}
      </div>

      <div className="dream-in w-full" style={{ animationDelay: "0.5s" }}>
        <ChatComposer prefill={prefill} />
      </div>
    </div>
  )
}
