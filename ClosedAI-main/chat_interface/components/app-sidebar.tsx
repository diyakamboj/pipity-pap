"use client"

import { useState } from "react"
import {
  MessageSquarePlus,
  Search,
  MessageSquare,
  Plug,
  Blocks,
  Store,
  Brain,
  SlidersHorizontal,
  ChevronRight,
  ChevronDown,
  ChevronsUpDown,
  MoreHorizontal,
  CircleDashed,
  Trash2,
  PanelLeftClose,
  Sparkles,
  FolderPlus,
  LayoutTemplate,
  Radar,
  Inbox,
  Workflow,
  Server,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { User, Settings, CreditCard, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { useChat } from "@/lib/chat-store"
import { useNavigation, type View } from "@/lib/navigation"

const PRIMARY_NAV: { icon: typeof MessageSquare; label: string; view: View }[] = [
  { icon: MessageSquare, label: "Chat", view: "chat" },
  { icon: Radar, label: "Intake", view: "intake" },
  { icon: Inbox, label: "Work Queue", view: "work" },
  { icon: Workflow, label: "Automations", view: "automations" },
  { icon: Server, label: "Connected Systems", view: "systems" },
  { icon: Plug, label: "MCP Connections", view: "mcp" },
  { icon: Blocks, label: "Skills", view: "skills" },
  { icon: Store, label: "Marketplace", view: "marketplace" },
  { icon: Brain, label: "Memory", view: "memory" },
  { icon: SlidersHorizontal, label: "Settings", view: "settings" },
]

interface AppSidebarProps {
  open: boolean
  width: number
  onCollapse: () => void
}

export function AppSidebar({ open, width, onCollapse }: AppSidebarProps) {
  const { conversations, activeId, newChat, selectConversation, deleteConversation } = useChat()
  const { view, setView } = useNavigation()
  const [query, setQuery] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [favoritesOpen, setFavoritesOpen] = useState(false)
  const [recentOpen, setRecentOpen] = useState(true)
  const [showAllRecent, setShowAllRecent] = useState(false)

  const goNewChat = () => {
    setView("chat")
    newChat()
  }
  const goSelect = (id: string) => {
    setView("chat")
    selectConversation(id)
  }

  const filtered = conversations.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()))
  const visibleRecent = showAllRecent ? filtered : filtered.slice(0, 5)
  const hasMore = filtered.length > 5

  return (
    <aside
      style={{ width }}
      className={cn(
        "flex h-full flex-col bg-sidebar transition-[opacity,transform,filter] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
        open ? "translate-x-0 opacity-100 blur-0" : "-translate-x-6 opacity-0 blur-sm",
      )}
    >
      {/* Brand / logo */}
      <div className="flex items-center justify-between px-3 pt-4 pb-2">
        <div className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/[0.06] shadow-lg shadow-black/40">
            <Sparkles className="h-[18px] w-[18px] text-neutral-200" />
          </span>
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-semibold leading-tight text-sidebar-foreground">Gurt</span>
            <span className="truncate text-[11px] leading-tight text-muted-foreground">Event Operations</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 text-muted-foreground transition-all duration-300 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-90"
          onClick={onCollapse}
          aria-label="Collapse sidebar"
        >
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {/* New Chat */}
      <div className="px-3 pb-2">
        <div className="flex items-stretch gap-1">
          <Button
            variant="secondary"
            onClick={goNewChat}
            className="btn-3d btn-glow flex-1 justify-center gap-2 rounded-md border border-white/20 bg-gradient-to-br from-primary via-gray-900 to-black font-medium text-white shadow-xl transition-all hover:from-gray-900 hover:to-black"
          >
            <MessageSquarePlus className="h-4 w-4" />
            New Chat
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                id="sidebar-new-chat-trigger"
                variant="secondary"
                size="icon"
                aria-label="New chat options"
                className="btn-3d btn-glow group rounded-md border border-white/20 bg-gradient-to-br from-primary via-gray-900 to-black text-white shadow-xl transition-all hover:from-gray-900 hover:to-black"
              >
                <ChevronDown className="h-4 w-4 transition-transform duration-300 group-data-[state=open]:rotate-180" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={6}
              className="w-56 border-white/10 bg-[#111111] text-neutral-200 shadow-2xl duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
            >
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                Create new
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                onClick={goNewChat}
                className="gap-2.5 text-[13px] transition-colors focus:bg-white/[0.06] focus:text-white"
              >
                <MessageSquarePlus className="h-4 w-4 text-neutral-400" />
                New Chat
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={goNewChat}
                className="gap-2.5 text-[13px] transition-colors focus:bg-white/[0.06] focus:text-white"
              >
                <FolderPlus className="h-4 w-4 text-neutral-400" />
                New Project
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={goNewChat}
                className="gap-2.5 text-[13px] transition-colors focus:bg-white/[0.06] focus:text-white"
              >
                <LayoutTemplate className="h-4 w-4 text-neutral-400" />
                New from Template
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-1">
        {/* Primary nav */}
        <nav className="space-y-0.5">
          <button
            onClick={() => setSearchOpen((v) => !v)}
            className={cn(
              "group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors duration-200 hover:bg-sidebar-accent",
              searchOpen && "bg-sidebar-accent",
            )}
          >
            <Search className="h-[18px] w-[18px] text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground" />
            Search
          </button>

          <div
            className={cn(
              "grid transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              searchOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              <div className="px-1 py-1">
                <input
                  autoFocus={searchOpen}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search chats"
                  className="w-full rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-3 py-2 text-sm text-sidebar-foreground outline-none transition-all duration-300 placeholder:text-muted-foreground focus:border-sidebar-border focus:bg-sidebar-accent/60 focus:ring-1 focus:ring-white/10"
                />
              </div>
            </div>
          </div>

          {PRIMARY_NAV.map(({ icon: Icon, label, view: navView }) => (
            <button
              key={label}
              onClick={() => setView(navView)}
              className={cn(
                "group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors duration-200 hover:bg-sidebar-accent",
                view === navView && "bg-sidebar-accent",
              )}
            >
              <Icon
                className={cn(
                  "h-[18px] w-[18px] text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
                  view === navView && "text-sidebar-foreground",
                )}
              />
              {label}
            </button>
          ))}
        </nav>

        {/* Favorites */}
        <div className="mt-5">
          <button
            onClick={() => setFavoritesOpen((v) => !v)}
            className="group flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-all duration-300 hover:text-sidebar-foreground"
          >
            <span>Favorites</span>
            <ChevronRight
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-300",
                favoritesOpen && "rotate-90",
              )}
            />
          </button>
          <div
            className={cn(
              "grid transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              favoritesOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              <p className="px-3 py-2 text-xs text-muted-foreground">No favorites yet.</p>
            </div>
          </div>
        </div>

        {/* Recent Chats */}
        <div className="mt-4">
          <button
            onClick={() => setRecentOpen((v) => !v)}
            className="group flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-all duration-300 hover:text-sidebar-foreground"
          >
            <span>Recent Chats</span>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-300",
                recentOpen ? "rotate-0" : "-rotate-90",
              )}
            />
          </button>
          <div
            className={cn(
              "grid transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              recentOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              <div className="space-y-0.5 pt-1">
                {visibleRecent.length === 0 && (
                  <p className="px-3 py-2 text-xs text-muted-foreground">No chats found.</p>
                )}
                {visibleRecent.map((c) => (
                  <div
                    key={c.id}
                    className={cn(
                      "group flex items-center gap-2 rounded-lg px-3 py-2 transition-colors duration-200 hover:bg-sidebar-accent",
                      activeId === c.id && "bg-sidebar-accent",
                    )}
                  >
                    <button
                      onClick={() => goSelect(c.id)}
                      className="flex min-w-0 flex-1 items-center gap-3 text-left"
                    >
                      <CircleDashed
                        className={cn(
                          "h-4 w-4 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
                          activeId === c.id && "text-sidebar-foreground",
                        )}
                      />
                      <span
                        className={cn(
                          "truncate text-sm text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
                          activeId === c.id && "text-sidebar-foreground",
                        )}
                      >
                        {c.title}
                      </span>
                    </button>
                    <button
                      onClick={() => deleteConversation(c.id)}
                      aria-label={`Delete ${c.title}`}
                      className="shrink-0 text-muted-foreground opacity-0 transition-all duration-300 hover:scale-110 hover:text-destructive group-hover:opacity-100 active:scale-90"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                {hasMore && (
                  <button
                    onClick={() => setShowAllRecent((v) => !v)}
                    className="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-all duration-300 hover:translate-x-0.5 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-[0.98]"
                  >
                    <MoreHorizontal className="h-4 w-4 transition-colors duration-300 group-hover:text-sidebar-foreground" />
                    {showAllRecent ? "Less" : "More"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom profile */}
      <div className="border-t border-sidebar-border p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button id="sidebar-user-menu-trigger" className="group flex w-full min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-all duration-300 hover:-translate-y-px hover:bg-sidebar-accent active:scale-[0.99]">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/15 bg-neutral-300 transition-transform duration-300 group-hover:scale-105" />
              <span className="truncate text-sm font-medium text-sidebar-foreground">Organizer</span>
              <ChevronsUpDown className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            side="top"
            className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[240px]"
          >
            <DropdownMenuLabel className="flex flex-col">
              <span className="text-[13px] font-medium text-foreground">Organizer</span>
              <span className="text-xs font-normal text-muted-foreground">Event workspace</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 text-[13px]">
              <User />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setView("settings")} className="gap-2 text-[13px]">
              <Settings />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2 text-[13px]">
              <CreditCard />
              Billing
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" className="gap-2 text-[13px]">
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}
