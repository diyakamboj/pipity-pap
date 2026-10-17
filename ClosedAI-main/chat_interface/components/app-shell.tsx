"use client"

import { useEffect, useState } from "react"
import { PanelLeftOpen } from "lucide-react"
import { AppSidebar } from "@/components/app-sidebar"
import { ChatArea } from "@/components/chat-area"
import { McpConnectionsPage } from "@/components/pages/mcp/page"
import { SkillsPage } from "@/components/pages/skills/page"
import { MarketplaceDashboard } from "@/components/pages/marketplace/page"
import { MemoryPage } from "@/components/pages/memory-page"
import { SettingsPage } from "@/components/pages/settings-page"
import IntakePage from "@/components/pages/intake-page"
import WorkPage from "@/components/pages/work-page"
import AutomationsPage from "@/components/pages/automations-page"
import SystemsPage from "@/components/pages/systems-page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useNavigation } from "@/lib/navigation"

const SIDEBAR_MIN_WIDTH = 240
const SIDEBAR_MAX_WIDTH = 420
const SIDEBAR_DEFAULT_WIDTH = 320

export function AppShell() {
  const { view } = useNavigation()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const next = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, e.clientX))
      setSidebarWidth(next)
    }
    const stopDragging = () => setIsDragging(false)

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", stopDragging)

    return () => {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", stopDragging)
    }
  }, [isDragging])

  const isChat = view === "chat"

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {view === "marketplace" ? (
        <MarketplaceDashboard />
      ) : (
        <>
          <div
            style={{ width: sidebarOpen ? sidebarWidth : 0 }}
            className={cn(
              "shrink-0 overflow-hidden",
              !isDragging && "transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
            )}
          >
            <AppSidebar open={sidebarOpen} width={sidebarWidth} onCollapse={() => setSidebarOpen(false)} />
          </div>

          {/* Draggable divider */}
          {sidebarOpen && (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize sidebar"
              onMouseDown={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT_WIDTH)}
              className="group relative z-20 flex w-2 shrink-0 cursor-col-resize items-stretch justify-center"
            >
              <span
                className={cn(
                  "pointer-events-none h-full rounded-full transition-all duration-200",
                  isDragging ? "w-1 bg-white" : "w-px bg-sidebar-border group-hover:w-1 group-hover:bg-white",
                )}
              />
            </div>
          )}

          {isChat ? (
            <ChatArea sidebarOpen={sidebarOpen} onOpenSidebar={() => setSidebarOpen(true)} />
          ) : (
            <main className="relative flex flex-1 flex-col overflow-y-auto bg-background">
              {!sidebarOpen && (
                <div className="absolute left-4 top-4 z-20">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-foreground"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open sidebar"
                  >
                    <PanelLeftOpen className="h-4 w-4" />
                  </Button>
                </div>
              )}
              {view === "intake" && <IntakePage />}
              {view === "work" && <WorkPage />}
              {view === "automations" && <AutomationsPage />}
              {view === "systems" && <SystemsPage />}
              {view === "mcp" && <McpConnectionsPage />}
              {view === "skills" && <SkillsPage />}
              {view === "memory" && <MemoryPage />}
              {view === "settings" && <SettingsPage />}
            </main>
          )}
        </>
      )}
    </div>
  )
}
