"use client"

import type { ComponentType } from "react"
import {
  Check,
  ChevronDown,
  Database,
  Table2,
  FileText,
  Globe,
  Server,
  Sparkles,
  Briefcase,
  Coffee,
  Smile,
  Minimize2,
  Palette,
  Settings,
  KeyRound,
  SlidersHorizontal,
  Wrench,
  FileType,
  Hash,
  Braces,
  Link2,
  Bot,
  LineChart,
  BookOpen,
  Headphones,
  ArrowUpRight,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MODELS, TONES, DATA_SOURCES } from "@/lib/chat-store"
import { cn } from "@/lib/utils"

/** Shared dark surface + dreamy easing for every menu. Content differs per menu. */
const surface =
  "border-white/10 bg-[#0f0f0f]/95 text-neutral-200 shadow-2xl backdrop-blur-xl duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"

const pillTrigger =
  "flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[12px] font-medium text-neutral-200 transition-colors hover:bg-white/[0.07]"

/* ------------------------------------------------------------------ */
/* Model selector — grouped by provider, accent dot + tagline          */
/* ------------------------------------------------------------------ */

const MODEL_META: Record<string, { provider: string; dot: string; tag: string }> = {
  "Claude-3-sonnet": { provider: "Anthropic", dot: "bg-orange-400", tag: "Balanced speed & depth" },
  "Claude-3-opus": { provider: "Anthropic", dot: "bg-orange-400", tag: "Most capable reasoning" },
  "GPT-4o": { provider: "OpenAI", dot: "bg-emerald-400", tag: "Multimodal flagship" },
  "GPT-4 Turbo": { provider: "OpenAI", dot: "bg-emerald-400", tag: "Fast & capable" },
  "Gemini Pro": { provider: "Google", dot: "bg-sky-400", tag: "Long context window" },
}

const PROVIDER_ORDER = ["Anthropic", "OpenAI", "Google"]

export function ModelMenu({
  value,
  onChange,
  size = "sm",
  side = "bottom",
  align = "start",
}: {
  value: string
  onChange: (v: string) => void
  size?: "sm" | "md"
  side?: "top" | "bottom"
  align?: "start" | "center" | "end"
}) {
  const grouped = PROVIDER_ORDER.map((provider) => ({
    provider,
    models: MODELS.map((m) => m.label).filter((label) => MODEL_META[label]?.provider === provider),
  })).filter((g) => g.models.length > 0)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {size === "sm" ? (
          <button className={pillTrigger}>
            <Sparkles className="h-3.5 w-3.5 text-orange-400" />
            {value}
            <ChevronDown className="h-3.5 w-3.5 text-neutral-500" />
          </button>
        ) : (
          <button className="flex items-center gap-2 rounded-lg border border-border/50 bg-secondary px-3.5 py-2 text-sm font-medium text-foreground backdrop-blur-sm transition-colors hover:bg-secondary/70">
            <span className={cn("h-2 w-2 rounded-full", MODEL_META[value]?.dot ?? "bg-neutral-400")} />
            {value}
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side={side} align={align} className={cn(surface, "w-72 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Choose a model
        </div>
        {grouped.map((group, gi) => (
          <div key={group.provider}>
            {gi > 0 && <DropdownMenuSeparator className="bg-white/10" />}
            <DropdownMenuLabel className="px-2 py-1 text-[11px] font-medium text-neutral-500">
              {group.provider}
            </DropdownMenuLabel>
            {group.models.map((label) => {
              const meta = MODEL_META[label]
              const selected = value === label
              return (
                <DropdownMenuItem
                  key={label}
                  onSelect={() => onChange(label)}
                  className={cn(
                    "flex items-start gap-2.5 rounded-lg px-2 py-2 focus:bg-white/[0.06]",
                    selected && "bg-white/[0.04]",
                  )}
                >
                  <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", meta.dot)} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-[13px] font-medium text-neutral-100">{label}</span>
                    <span className="truncate text-[11px] text-neutral-500">{meta.tag}</span>
                  </span>
                  {selected && <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />}
                </DropdownMenuItem>
              )
            })}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------ */
/* Tone selector — icon + description, compact                          */
/* ------------------------------------------------------------------ */

const TONE_META: Record<string, { icon: ComponentType<{ className?: string }>; desc: string; color: string }> = {
  Default: { icon: Sparkles, desc: "Balanced, adaptive replies", color: "text-neutral-300" },
  Professional: { icon: Briefcase, desc: "Formal and precise", color: "text-sky-300" },
  Casual: { icon: Coffee, desc: "Relaxed and easygoing", color: "text-amber-300" },
  Friendly: { icon: Smile, desc: "Warm and approachable", color: "text-emerald-300" },
  Concise: { icon: Minimize2, desc: "Short and to the point", color: "text-violet-300" },
  Creative: { icon: Palette, desc: "Imaginative and bold", color: "text-pink-300" },
}

export function ToneMenu({
  value,
  onChange,
  side = "top",
  align = "start",
}: {
  value: string
  onChange: (v: string) => void
  side?: "top" | "bottom"
  align?: "start" | "center" | "end"
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[12px] font-medium text-neutral-300 transition-colors hover:text-neutral-100">
          <span className="flex h-3.5 w-3.5 items-center justify-center rounded-sm border border-neutral-500 text-[9px]">
            T
          </span>
          {value === "Default" ? "Tone" : value}
          <ChevronDown className="h-3.5 w-3.5 text-neutral-500" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side={side} align={align} className={cn(surface, "w-64 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Response tone
        </div>
        {TONES.map((tone) => {
          const meta = TONE_META[tone]
          const Icon = meta.icon
          const selected = value === tone
          return (
            <DropdownMenuItem
              key={tone}
              onSelect={() => onChange(tone)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2 py-1.5 focus:bg-white/[0.06]",
                selected && "bg-white/[0.04]",
              )}
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/[0.05]">
                <Icon className={cn("h-3.5 w-3.5", meta.color)} />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-[13px] font-medium text-neutral-100">{tone}</span>
                <span className="truncate text-[11px] text-neutral-500">{meta.desc}</span>
              </span>
              {selected && <Check className="h-4 w-4 shrink-0 text-emerald-400" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------ */
/* Data source selector — icon tiles + connection hint                  */
/* ------------------------------------------------------------------ */

const SOURCE_META: Record<string, { icon: ComponentType<{ className?: string }>; desc: string }> = {
  Data: { icon: Database, desc: "Structured datasets" },
  Spreadsheets: { icon: Table2, desc: "CSV & XLSX files" },
  Documents: { icon: FileText, desc: "PDFs and text docs" },
  Web: { icon: Globe, desc: "Live web results" },
  Database: { icon: Server, desc: "SQL connections" },
}

export function DataSourceMenu({
  value,
  onChange,
  side = "bottom",
  align = "end",
}: {
  value: string
  onChange: (v: string) => void
  side?: "top" | "bottom"
  align?: "start" | "center" | "end"
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className={pillTrigger}>
          <Database className="h-3.5 w-3.5" />
          {value}
          <ChevronDown className="h-3.5 w-3.5 text-neutral-500" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side={side} align={align} className={cn(surface, "w-64 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Connect a source
        </div>
        {DATA_SOURCES.map((source) => {
          const meta = SOURCE_META[source]
          const Icon = meta.icon
          const selected = value === source
          return (
            <DropdownMenuItem
              key={source}
              onSelect={() => onChange(source)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2 py-1.5 focus:bg-white/[0.06]",
                selected && "bg-white/[0.04]",
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-colors",
                  selected
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border-white/10 bg-white/[0.03] text-neutral-400",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-[13px] font-medium text-neutral-100">{source}</span>
                <span className="truncate text-[11px] text-neutral-500">{meta.desc}</span>
              </span>
              {selected && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------ */
/* Agent switcher — avatar + role, with manage footer                   */
/* ------------------------------------------------------------------ */

const AGENT_META: Record<string, { icon: ComponentType<{ className?: string }>; gradient: string; role: string }> = {
  "HR Agent": { icon: LineChart, gradient: "from-sky-400 to-blue-600", role: "Manages HR workflows" },
  "Research Agent": { icon: BookOpen, gradient: "from-violet-400 to-purple-600", role: "Gathers & synthesizes info" },
  "Writing Agent": { icon: FileText, gradient: "from-amber-400 to-orange-600", role: "Drafts & edits content" },
  "Support Agent": { icon: Headphones, gradient: "from-emerald-400 to-teal-600", role: "Answers user questions" },
}

export function AgentMenu({
  agents,
  value,
  onChange,
  onManage,
}: {
  agents: string[]
  value: string
  onChange: (v: string) => void
  onManage?: () => void
}) {
  const active = AGENT_META[value]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2">
          <span className={cn("h-4 w-4 rounded-full bg-gradient-to-br", active?.gradient ?? "from-sky-400 to-blue-600")} />
          <span className="text-[15px] font-medium text-neutral-100">{value}</span>
          <ChevronDown className="h-4 w-4 text-neutral-500" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="start" className={cn(surface, "w-72 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Switch agent
        </div>
        {agents.map((agent) => {
          const meta = AGENT_META[agent]
          const Icon = meta.icon
          const selected = value === agent
          return (
            <DropdownMenuItem
              key={agent}
              onSelect={() => onChange(agent)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-2 py-2 focus:bg-white/[0.06]",
                selected && "bg-white/[0.04]",
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-white",
                  meta.gradient,
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-[13px] font-medium text-neutral-100">{agent}</span>
                <span className="truncate text-[11px] text-neutral-500">{meta.role}</span>
              </span>
              {selected && <Check className="h-4 w-4 shrink-0 text-emerald-400" />}
            </DropdownMenuItem>
          )
        })}
        <DropdownMenuSeparator className="bg-white/10" />
        <DropdownMenuItem
          onSelect={() => onManage?.()}
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-neutral-400 focus:bg-white/[0.06] focus:text-neutral-100"
        >
          <Bot className="h-4 w-4" />
          Manage agents
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------ */
/* Configuration — settings rows with icons + shortcuts                 */
/* ------------------------------------------------------------------ */

const CONFIG_ITEMS: { label: string; icon: ComponentType<{ className?: string }>; desc: string; shortcut?: string }[] = [
  { label: "General Settings", icon: Settings, desc: "Workspace basics", shortcut: "G" },
  { label: "API Keys", icon: KeyRound, desc: "Manage credentials", shortcut: "K" },
  { label: "Preferences", icon: SlidersHorizontal, desc: "Personalize behavior", shortcut: "P" },
  { label: "Advanced", icon: Wrench, desc: "Power-user options", shortcut: "A" },
]

export function ConfigMenu({
  trigger,
  onSelect,
}: {
  trigger: React.ReactNode
  onSelect: (label: string) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" className={cn(surface, "w-64 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Configuration
        </div>
        {CONFIG_ITEMS.map(({ label, icon: Icon, desc, shortcut }) => (
          <DropdownMenuItem
            key={label}
            onSelect={() => onSelect(label)}
            className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 focus:bg-white/[0.06]"
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-neutral-300">
              <Icon className="h-3.5 w-3.5" />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-[13px] font-medium text-neutral-100">{label}</span>
              <span className="truncate text-[11px] text-neutral-500">{desc}</span>
            </span>
            {shortcut && (
              <kbd className="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-medium text-neutral-500">
                {shortcut}
              </kbd>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------ */
/* Export — format tiles, share split out below a divider              */
/* ------------------------------------------------------------------ */

const EXPORT_FORMATS: { label: string; icon: ComponentType<{ className?: string }>; ext: string }[] = [
  { label: "Export as PDF", icon: FileType, ext: ".pdf" },
  { label: "Export as Markdown", icon: Hash, ext: ".md" },
  { label: "Export as JSON", icon: Braces, ext: ".json" },
]

export function ExportMenu({
  trigger,
  onSelect,
}: {
  trigger: React.ReactNode
  onSelect: (label: string) => void
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" className={cn(surface, "w-60 p-1.5")}>
        <div className="px-2 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Download conversation
        </div>
        {EXPORT_FORMATS.map(({ label, icon: Icon, ext }) => (
          <DropdownMenuItem
            key={label}
            onSelect={() => onSelect(label)}
            className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 focus:bg-white/[0.06]"
          >
            <Icon className="h-4 w-4 text-neutral-400" />
            <span className="flex-1 text-[13px] font-medium text-neutral-100">{label.replace("Export as ", "")}</span>
            <span className="text-[11px] text-neutral-600">{ext}</span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator className="bg-white/10" />
        <DropdownMenuItem
          onSelect={() => onSelect("Share Link")}
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 focus:bg-white/[0.06]"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-300">
            <Link2 className="h-3.5 w-3.5" />
          </span>
          <span className="flex-1 text-[13px] font-medium text-neutral-100">Copy share link</span>
          <ArrowUpRight className="h-3.5 w-3.5 text-neutral-500" />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
