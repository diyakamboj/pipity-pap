"use client"

import { useMemo, useState } from "react"
import { Plus, Search, Pencil, Trash2, MoreHorizontal, Brain } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { OptionMenu } from "@/components/option-menu"
import { cn } from "@/lib/utils"
import { PageContainer, PageHeader, Tag } from "@/components/management/shared"

type MemoryType = "Preference" | "Fact" | "Instruction" | "Context"

interface MemoryEntry {
  id: string
  type: MemoryType
  content: string
  source: string
  created: string
  updated: string
}

const TYPES: MemoryType[] = ["Preference", "Fact", "Instruction", "Context"]
const FILTERS = ["All", ...TYPES] as const

const INITIAL_MEMORIES: MemoryEntry[] = [
  {
    id: "mem-1",
    type: "Preference",
    content: "Prefers concise answers with bullet points and no filler. Skip pleasantries.",
    source: "Conversation",
    created: "Jan 10, 2026",
    updated: "Jan 14, 2026",
  },
  {
    id: "mem-2",
    type: "Fact",
    content: "Works at Northwind Labs as Head of Platform Engineering. Team of 24.",
    source: "Profile",
    created: "Dec 30, 2025",
    updated: "Jan 08, 2026",
  },
  {
    id: "mem-3",
    type: "Instruction",
    content: "Always use the Postgres MCP for analytics questions rather than estimating figures.",
    source: "Manual",
    created: "Dec 21, 2025",
    updated: "Dec 21, 2025",
  },
  {
    id: "mem-4",
    type: "Context",
    content: "Current project: migrating the billing service from REST to gRPC by Q2.",
    source: "Conversation",
    created: "Dec 18, 2025",
    updated: "Jan 02, 2026",
  },
  {
    id: "mem-5",
    type: "Preference",
    content: "Timezone is America/New_York. Working hours 9am-6pm ET.",
    source: "Profile",
    created: "Nov 28, 2025",
    updated: "Nov 28, 2025",
  },
]

export function MemoryPage() {
  const [memories, setMemories] = useState<MemoryEntry[]>(INITIAL_MEMORIES)
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All")
  const [editing, setEditing] = useState<MemoryEntry | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  const filtered = useMemo(() => {
    return memories.filter((m) => {
      const matchesType = filter === "All" || m.type === filter
      const matchesQuery =
        m.content.toLowerCase().includes(query.toLowerCase()) ||
        m.source.toLowerCase().includes(query.toLowerCase())
      return matchesType && matchesQuery
    })
  }, [memories, filter, query])

  const deleteMemory = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id))
    toast.success("Memory deleted")
  }

  const saveMemory = (entry: MemoryEntry) => {
    setMemories((prev) => {
      const exists = prev.some((m) => m.id === entry.id)
      return exists ? prev.map((m) => (m.id === entry.id ? entry : m)) : [entry, ...prev]
    })
  }

  return (
    <PageContainer>
      <PageHeader
        title="Memory"
        icon={Brain}
        description="Everything the agent remembers about you and your work. Review, refine, and control what persists across conversations."
        action={
          <Button
            onClick={() => setCreateOpen(true)}
            className="gap-2 bg-primary text-primary-foreground transition-transform duration-200 hover:opacity-90 active:scale-95"
          >
            <Plus className="h-4 w-4" />
            Add Memory
          </Button>
        }
      />

      {/* Controls */}
      <div className="dream-in mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memories"
            className="bg-secondary/40 pl-9"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors duration-200",
                filter === f
                  ? "border-border bg-secondary text-foreground"
                  : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="overflow-hidden rounded-2xl border border-border/60">
        {filtered.length === 0 && (
          <div className="px-6 py-16 text-center text-sm text-muted-foreground">No memories match your filters.</div>
        )}
        {filtered.map((m, i) => (
          <div
            key={m.id}
            className={cn(
              "group flex items-start gap-4 px-5 py-4 transition-colors duration-200 hover:bg-card/60",
              i !== filtered.length - 1 && "border-b border-border/60",
            )}
          >
            <Tag className="mt-0.5 shrink-0">{m.type}</Tag>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] leading-relaxed text-foreground text-pretty">{m.content}</p>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
                <span>Source: {m.source}</span>
                <span>Created {m.created}</span>
                <span>Updated {m.updated}</span>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                  aria-label="Memory actions"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                <DropdownMenuItem onClick={() => setEditing(m)} className="gap-2 text-[13px]">
                  <Pencil />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onClick={() => deleteMemory(m.id)} className="gap-2 text-[13px]">
                  <Trash2 />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ))}
      </div>

      <MemoryDialog
        open={createOpen || editing !== null}
        entry={editing}
        onOpenChange={(o) => {
          if (!o) {
            setCreateOpen(false)
            setEditing(null)
          }
        }}
        onSave={saveMemory}
      />
    </PageContainer>
  )
}

function MemoryDialog({
  open,
  entry,
  onOpenChange,
  onSave,
}: {
  open: boolean
  entry: MemoryEntry | null
  onOpenChange: (open: boolean) => void
  onSave: (entry: MemoryEntry) => void
}) {
  const isEditing = entry !== null
  const [type, setType] = useState<MemoryType>("Preference")
  const [content, setContent] = useState("")
  const [source, setSource] = useState("Manual")

  const [syncedFor, setSyncedFor] = useState<string | null>(null)
  const currentKey = entry?.id ?? "new"
  if (open && syncedFor !== currentKey) {
    setType(entry?.type ?? "Preference")
    setContent(entry?.content ?? "")
    setSource(entry?.source ?? "Manual")
    setSyncedFor(currentKey)
  }
  if (!open && syncedFor !== null) setSyncedFor(null)

  const handleSave = () => {
    if (!content.trim()) {
      toast.error("Memory content is required")
      return
    }
    const today = new Date().toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })
    onSave({
      id: entry?.id ?? `mem-${Date.now()}`,
      type,
      content: content.trim(),
      source,
      created: entry?.created ?? today,
      updated: today,
    })
    toast.success(isEditing ? "Memory updated" : "Memory added")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 border-border/60 bg-card p-0 sm:max-w-lg">
        <DialogHeader className="border-b border-border/60 px-6 py-5">
          <DialogTitle className="font-heading text-lg">{isEditing ? "Edit Memory" : "Add Memory"}</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Store a fact, preference, or instruction the agent should remember.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 px-6 py-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label className="text-[13px] font-medium text-foreground">Type</Label>
              <OptionMenu
                label="Type"
                options={TYPES}
                value={type}
                onChange={(v) => setType(v as MemoryType)}
                trigger={
                  <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground">
                    {type}
                    <span className="text-muted-foreground">▾</span>
                  </button>
                }
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label className="text-[13px] font-medium text-foreground">Source</Label>
              <OptionMenu
                label="Source"
                options={["Manual", "Conversation", "Profile"]}
                value={source}
                onChange={setSource}
                trigger={
                  <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground">
                    {source}
                    <span className="text-muted-foreground">▾</span>
                  </button>
                }
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label className="text-[13px] font-medium text-foreground">Content</Label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="What should the agent remember?"
              className="min-h-[120px] resize-none bg-secondary/40 leading-relaxed"
            />
          </div>
        </div>

        <DialogFooter className="border-t border-border/60 px-6 py-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-primary text-primary-foreground hover:opacity-90">
            {isEditing ? "Save changes" : "Add memory"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
