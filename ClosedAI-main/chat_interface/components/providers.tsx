"use client"

import type React from "react"
import { ChatProvider } from "@/lib/chat-store"
import { SkillsProvider } from "@/lib/skills-store"
import { McpProvider } from "@/lib/mcp-store"
import { AgentRuntimeProvider } from "@/lib/agent-runtime"
import { NavigationProvider } from "@/lib/navigation"
import { Toaster } from "@/components/ui/sonner"

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AgentRuntimeProvider>
      <ChatProvider>
        <SkillsProvider>
          <McpProvider>
            <NavigationProvider>
              {children}
              <Toaster theme="dark" position="bottom-center" />
            </NavigationProvider>
          </McpProvider>
        </SkillsProvider>
      </ChatProvider>
    </AgentRuntimeProvider>
  )
}
