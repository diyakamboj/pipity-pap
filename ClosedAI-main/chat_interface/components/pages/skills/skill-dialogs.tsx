"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { Play, RotateCcw, X, Loader2, CheckCircle2, XCircle, Plus, Terminal, Shield } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { OptionMenu } from "@/components/option-menu"
import { CATEGORY_TONES, DrawerShell } from "@/components/management/shared"
import { categoryIcon, defaultPermissions, todayLabel, uid } from "./skill-data"
import { CATEGORIES, SCOPE_FILTERS, TRIGGER_FILTERS } from "./skill-types"
import type { Skill, SkillPermissions, SkillScope, SkillTemplate, SkillVariable, TriggerType } from "./skill-types"

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <Label className="text-[13px] font-medium text-foreground">{label}</Label>
        {hint && <span className="text-[11px] text-muted-foreground/70">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Select({ label, options, value, onChange }: { label: string; options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <OptionMenu
      label={label}
      options={options}
      value={value}
      onChange={onChange}
      trigger={
        <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground">
          {value}
          <span className="text-muted-foreground">▾</span>
        </button>
      }
    />
  )
}

/* Chip input: type + Enter adds, click X removes, Backspace on empty removes last. */
function ChipsInput({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [draft, setDraft] = useState("")

  const add = () => {
    const t = draft.trim().replace(/,$/, "")
    if (!t) return
    if (!value.some((v) => v.toLowerCase() === t.toLowerCase())) onChange([...value, t])
    setDraft("")
  }

  return (
    <div className="flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-md border border-border/60 bg-secondary/40 px-2 py-1.5 focus-within:border-border">
      {value.map((chip) => (
        <span key={chip} className="flex items-center gap-1 rounded-md border border-border/60 bg-card/60 px-2 py-0.5 text-[12px] font-medium text-foreground">
          {chip}
          <button onClick={() => onChange(value.filter((v) => v !== chip))} aria-label={`Remove ${chip}`} className="text-muted-foreground/70 transition-colors hover:text-foreground">
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); add() }
          else if (e.key === "Backspace" && draft === "" && value.length > 0) onChange(value.slice(0, -1))
          else if (e.key === ",") { e.preventDefault(); add() }
        }}
        onBlur={add}
        placeholder={value.length === 0 ? placeholder : ""}
        className="min-w-[120px] flex-1 bg-transparent px-1 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/50"
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Create / Edit skill                                                */
/* ------------------------------------------------------------------ */

export function SkillDialog({
  open,
  skill,
  templatePrefill,
  onOpenChange,
  onSave,
}: {
  open: boolean
  skill: Skill | null
  templatePrefill: SkillTemplate | null
  onOpenChange: (open: boolean) => void
  onSave: (skill: Skill) => void
}) {
  const isEditing = skill !== null
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [category, setCategory] = useState(CATEGORIES[0])
  const [scope, setScope] = useState<SkillScope>("global")
  const [triggerType, setTriggerType] = useState<TriggerType>("Trigger-based")
  const [keywords, setKeywords] = useState<string[]>([])
  const [instructions, setInstructions] = useState("")
  const [tools, setTools] = useState<string[]>([])
  const [variables, setVariables] = useState<SkillVariable[]>([])
  const [enabled, setEnabled] = useState(true)
  const [restricted, setRestricted] = useState(false)

  const [syncedFor, setSyncedFor] = useState<string | null>(null)
  const currentKey = skill?.id ?? templatePrefill?.id ?? "new"
  if (open && syncedFor !== currentKey) {
    if (skill) {
      setName(skill.name)
      setDescription(skill.description)
      setCategory(skill.category)
      setScope(skill.scope)
      setTriggerType(skill.triggerType)
      setKeywords(skill.keywords)
      setInstructions(skill.instructions)
      setTools(skill.requiredTools)
      setVariables(skill.variables)
      setEnabled(skill.enabled)
      setRestricted(skill.permissions.flags.requireConfirmation)
    } else if (templatePrefill) {
      setName(templatePrefill.name)
      setDescription(templatePrefill.description)
      setCategory(templatePrefill.category)
      setScope("global")
      setTriggerType(templatePrefill.triggerType)
      setKeywords([])
      setInstructions(templatePrefill.instructions)
      setTools(templatePrefill.requiredTools)
      setVariables(templatePrefill.variables)
      setEnabled(true)
      setRestricted(false)
    } else {
      setName("")
      setDescription("")
      setCategory(CATEGORIES[0])
      setScope("global")
      setTriggerType("Trigger-based")
      setKeywords([])
      setInstructions("")
      setTools([])
      setVariables([])
      setEnabled(true)
      setRestricted(false)
    }
    setSyncedFor(currentKey)
  }
  if (!open && syncedFor !== null) setSyncedFor(null)

  const addVariable = () => setVariables((v) => [...v, { key: `var_${v.length + 1}`, label: "", description: "", required: false }])

  const handleSave = () => {
    if (!name.trim() || !instructions.trim()) {
      toast.error("Name and instructions are required")
      return
    }
    const cleanVars = variables.filter((v) => v.key.trim() !== "" && v.label.trim() !== "")
    const perms: SkillPermissions = skill
      ? skill.permissions
      : {
          flags: { ...defaultPermissions().flags, requireConfirmation: restricted },
          toolOverrides: Object.fromEntries(tools.map((t) => [t, { tool: t, allowed: true, requiresConfirmation: false }])),
        }
    const now = Date.now()
    onSave({
      id: skill?.id ?? `skill-${uid()}`,
      name: name.trim(),
      description: description.trim() || "Custom skill.",
      category,
      scope,
      triggerType,
      keywords,
      enabled,
      version: skill?.version ?? "1.0.0",
      author: skill?.author ?? "me",
      requiredTools: tools,
      instructions: instructions.trim(),
      variables: cleanVars,
      added: skill?.added ?? todayLabel(),
      lastUsed: skill?.lastUsed ?? "never",
      lastUsedTs: skill?.lastUsedTs ?? 0,
      runCount: skill?.runCount ?? 0,
      successRate: skill?.successRate ?? 100,
      avgDurationMs: skill?.avgDurationMs ?? 0,
      errors24h: skill?.errors24h ?? 0,
      permissions: perms,
      activity: [
        {
          id: `a-${uid()}`,
          action: isEditing ? "Configuration updated" : "Skill created",
          detail: isEditing ? "Details changed by the operator" : "Created a new skill",
          time: "just now",
          ts: now,
          status: "info",
        },
        ...(skill?.activity ?? []),
      ],
    })
    toast.success(isEditing ? `${name.trim()} updated` : `${name.trim()} created`)
    onOpenChange(false)
  }

  const Icon = categoryIcon(category)

  return (
    <DrawerShell
      open={open}
      onOpenChange={onOpenChange}
      eyebrow="Skill"
      icon={<Icon className="h-5 w-5" />}
      iconClassName={CATEGORY_TONES[category] ?? "border-border/60 bg-secondary/60 text-foreground"}
      title={isEditing ? "Edit Skill" : templatePrefill ? "Create from Template" : "Create Custom Skill"}
      description="Instructions and tools that define how the agent behaves for this skill."
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-primary text-primary-foreground hover:opacity-90">
            {isEditing ? "Save changes" : "Save & activate"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-6 py-6">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Category">
              <Select label="Category" options={CATEGORIES} value={category} onChange={setCategory} />
            </Field>
            <Field label="Trigger type">
              <Select label="Trigger type" options={[...TRIGGER_FILTERS.slice(1)]} value={triggerType} onChange={(v) => setTriggerType(v as TriggerType)} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Scope">
              <Select label="Scope" options={SCOPE_FILTERS.slice(1)} value={scope} onChange={(v) => setScope(v as SkillScope)} />
            </Field>
            <Field label="Author">
              <Input value={skill?.author ?? "me"} readOnly className="bg-secondary/40 text-muted-foreground" />
            </Field>
          </div>

          <Field label="Skill name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Meeting Summarizer" className="bg-secondary/40" />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="A short summary of what this skill does." className="min-h-[64px] resize-none bg-secondary/40" />
          </Field>

          <Field label="System instructions">
            <Textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Describe exactly how the agent should behave when this skill runs…"
              className="min-h-[140px] resize-none bg-secondary/40 font-mono text-[13px] leading-relaxed"
            />
          </Field>

          <Field label="Required MCP connections / tools" hint="Press Enter to add">
            <ChipsInput value={tools} onChange={setTools} placeholder="GitHub, Web Search, …" />
          </Field>

          <Field label="Trigger keywords" hint="Press Enter to add">
            <ChipsInput value={keywords} onChange={setKeywords} placeholder="summary, notes, …" />
          </Field>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label className="text-[13px] font-medium text-foreground">Variables</Label>
              <Button type="button" variant="ghost" size="sm" onClick={addVariable} className="gap-1.5 text-[12px] text-muted-foreground hover:text-foreground">
                <Plus className="h-3.5 w-3.5" />
                Add variable
              </Button>
            </div>
            {variables.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border/60 bg-secondary/20 px-4 py-3 text-center text-xs text-muted-foreground">
                No variables yet. Variables are injected into instructions as {"{{key}}"}.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {variables.map((v, i) => (
                  <div key={i} className="grid grid-cols-[1fr_1fr_auto_auto] items-center gap-2 rounded-lg border border-border/60 bg-secondary/30 px-3 py-2.5">
                    <Input
                      value={v.key}
                      onChange={(e) => setVariables((vars) => vars.map((x, xi) => (xi === i ? { ...x, key: e.target.value } : x)))}
                      placeholder="key"
                      className="h-8 bg-card/40 font-mono text-[12px]"
                    />
                    <Input
                      value={v.label}
                      onChange={(e) => setVariables((vars) => vars.map((x, xi) => (xi === i ? { ...x, label: e.target.value } : x)))}
                      placeholder="Label"
                      className="h-8 bg-card/40 text-[12px]"
                    />
                    <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <Switch checked={v.required} onCheckedChange={(r) => setVariables((vars) => vars.map((x, xi) => (xi === i ? { ...x, required: r } : x)))} aria-label="Required" className="scale-75" />
                      Req
                    </label>
                    <button onClick={() => setVariables((vars) => vars.filter((_, xi) => xi !== i))} aria-label="Remove variable" className="text-muted-foreground/70 transition-colors hover:text-red-400">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 rounded-lg border border-border/60 bg-secondary/30 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">Enable skill</p>
                <p className="text-xs text-muted-foreground">Make this skill available to the agent immediately.</p>
              </div>
              <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Enable skill" />
            </div>
            <div className="h-px bg-border/60" />
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
                  <Shield className="h-3.5 w-3.5 text-muted-foreground" />
                  Require confirmation
                </p>
                <p className="text-xs text-muted-foreground">Ask before the agent uses any tool in this skill.</p>
              </div>
              <Switch checked={restricted} onCheckedChange={setRestricted} aria-label="Require confirmation" />
            </div>
          </div>
      </div>
    </DrawerShell>
  )
}

/* ------------------------------------------------------------------ */
/*  Skill test / preview                                               */
/* ------------------------------------------------------------------ */

type LogTone = "muted" | "info" | "success" | "error"
interface RunLine { text: string; tone: LogTone }

export function SkillTestDialog({
  skill,
  onOpenChange,
  onCompleted,
}: {
  skill: Skill | null
  onOpenChange: (open: boolean) => void
  onCompleted: (skill: Skill, ok: boolean) => void
}) {
  const [phase, setPhase] = useState<"idle" | "running" | "done" | "error">("idle")
  const [lines, setLines] = useState<RunLine[]>([])
  const [input, setInput] = useState("")
  const [durationMs, setDurationMs] = useState(0)
  const timers = useRef<number[]>([])

  useEffect(() => {
    const t = timers.current
    return () => t.forEach((id) => window.clearTimeout(id))
  }, [])

  if (!skill) return null

  const clearTimers = () => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
  }

  const pushAfter = (delay: number, lineOrFn: RunLine | (() => void)) => {
    timers.current.push(
      window.setTimeout(() => {
        if (typeof lineOrFn === "function") lineOrFn()
        else setLines((prev) => [...prev, lineOrFn])
      }, delay),
    )
  }

  const handleRun = () => {
    clearTimers()
    setLines([])
    setPhase("running")
    const started = performance.now()
    const toolLines: RunLine[] = skill.requiredTools.map((t) => ({ text: `Calling tool: ${t}`, tone: "info" as const }))

    const disabled = !skill.enabled
    const willFail = disabled || skill.instructions.trim().toLowerCase().includes("fail")
    const step = 320

    pushAfter(step, { text: `Loading skill "${skill.name}" v${skill.version}`, tone: "muted" })
    pushAfter(step * 2, { text: "Resolving permission policy…", tone: "muted" })
    pushAfter(step * 3, {
      text: disabled
        ? "Skill is disabled. Cannot execute."
        : skill.permissions.flags.requireConfirmation
          ? "Policy: confirmation required for tool calls"
          : "Policy: no confirmation required",
      tone: disabled ? "error" : "info",
    })
    pushAfter(step * 4, {
      text: skill.requiredTools.length === 0
        ? "No external dependencies"
        : `Resolving ${skill.requiredTools.length} dependency${skill.requiredTools.length === 1 ? "" : "ies"}`,
      tone: "muted",
    })

    toolLines.forEach((line, i) => pushAfter(step * (5 + i), line))

    if (willFail) {
      pushAfter(step * (5 + toolLines.length), {
        text: disabled ? "Aborted: skill is disabled" : "Execution failed: instructions rejected the input",
        tone: "error",
      })
      pushAfter(step * (6 + toolLines.length), () => {
        setPhase("error")
        setDurationMs(Math.round(performance.now() - started))
        onCompleted(skill, false)
      })
    } else {
      pushAfter(step * (5 + toolLines.length), { text: "Instructions executed successfully", tone: "success" })
      pushAfter(step * (6 + toolLines.length), {
        text: `Completed in ${((step * (6 + toolLines.length)) / 1000).toFixed(1)}s`,
        tone: "success",
      })
      pushAfter(step * (7 + toolLines.length), () => {
        setPhase("done")
        setDurationMs(Math.round(performance.now() - started))
        onCompleted(skill, true)
      })
    }
  }

  const toneClass: Record<LogTone, string> = {
    muted: "text-muted-foreground",
    info: "text-sky-400",
    success: "text-emerald-400",
    error: "text-red-400",
  }

  return (
    <DrawerShell
      open={skill !== null}
      onOpenChange={onOpenChange}
      eyebrow="Preview"
      icon={<Terminal className="h-5 w-5" />}
      title={skill.name}
      description="Run a preview of this skill to verify its instructions and dependencies."
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {phase !== "running" && (
            <Button onClick={handleRun} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
              {phase === "idle" ? <Play className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
              {phase === "idle" ? "Run" : "Run again"}
            </Button>
          )}
        </div>
      }
    >
      <div className="flex flex-col gap-4 px-6 py-6">
          <Field label="Test input" hint="Optional">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Sample input the skill would receive…"
              className="min-h-[72px] resize-none bg-secondary/40 text-[13px]"
              disabled={phase === "running"}
            />
          </Field>

          <div className="rounded-lg border border-border/60 bg-[#0c0c0c] p-3.5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">Run output</span>
              {phase === "running" && (
                <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Running…
                </span>
              )}
              {phase === "done" && <span className="text-[11px] text-emerald-400">✓ Done in {(durationMs / 1000).toFixed(1)}s</span>}
              {phase === "error" && <span className="text-[11px] text-red-400">✗ Failed</span>}
            </div>
            <div className="flex min-h-[280px] flex-col gap-1 font-mono text-[12px]">
              {lines.length === 0 ? (
                <p className="text-muted-foreground/50">Press "Run" to execute the skill in preview mode.</p>
              ) : (
                lines.map((line, i) => (
                  <p key={i} className={toneClass[line.tone]}>
                    <span className="mr-2 select-none text-muted-foreground/40">{String(i + 1).padStart(2, "0")}</span>
                    {line.text}
                  </p>
                ))
              )}
            </div>
          </div>

          {phase === "done" && (
            <div className="flex flex-col gap-2 rounded-lg border border-emerald-500/25 bg-emerald-500/[0.06] px-4 py-3">
              <p className="flex items-center gap-2 text-[13px] font-medium text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                Execution completed
              </p>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {skill.name} ran successfully{input ? ` on "${input.slice(0, 60)}${input.length > 60 ? "…" : ""}"` : ""}.
                {skill.runCount + 1} total runs will be recorded after this test.
              </p>
            </div>
          )}

          {phase === "error" && (
            <div className="flex items-start gap-2.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3.5 py-3">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-red-300">Run failed</p>
                <p className="mt-0.5 text-xs leading-relaxed text-red-300/80">
                  {!skill.enabled
                    ? "The skill is disabled. Enable it before running."
                    : "The skill's instructions rejected this input. Review the instructions or the error in the output above."}
                </p>
              </div>
            </div>
          )}
      </div>
    </DrawerShell>
  )
}
