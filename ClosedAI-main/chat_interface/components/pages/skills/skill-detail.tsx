"use client"

import { useMemo, useState, type ReactNode } from "react"
import {
  MoreHorizontal,
  Pencil,
  Copy,
  Trash2,
  Zap,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  CircleDot,
  Shield,
  ShieldCheck,
  FileEdit,
  Globe,
  Database,
  Terminal,
  Clock,
  Activity as ActivityIcon,
  Search as SearchIcon,
  Play,
  Plus,
} from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  CATEGORY_TONES,
  DrawerShell,
  PanelSection,
  DetailRow,
  StatusBadge,
  StatusPill,
  Tag,
  ActivityLogEntry,
  Pagination,
} from "@/components/management/shared"
import { AVAILABLE_CONNECTIONS, categoryIcon } from "./skill-data"
import { SCOPE_META } from "./skill-types"
import type {
  ActivityStatus,
  Skill,
  SkillActivity,
  SkillPermissions,
  ToolOverride,
} from "./skill-types"

export interface SkillDetailPanelProps {
  skill: Skill | null
  onOpenChange: (open: boolean) => void
  onToggle: (id: string) => void
  onEdit: (skill: Skill) => void
  onDuplicate: (skill: Skill) => void
  onDelete: (skill: Skill) => void
  onSaveInstructions: (id: string, instructions: string) => void
  onSavePermissions: (id: string, perms: SkillPermissions) => void
  onRun: (skill: Skill) => void
}

export function SkillDetailPanel(props: SkillDetailPanelProps) {
  const { skill, ...rest } = props
  const Icon = skill ? categoryIcon(skill.category) : null
  const scope = skill ? SCOPE_META[skill.scope] : null

  return (
    <DrawerShell
      open={skill !== null}
      onOpenChange={props.onOpenChange}
      eyebrow="Skill"
      icon={Icon ? <Icon className="h-5 w-5" /> : undefined}
      iconClassName={skill ? (CATEGORY_TONES[skill.category] ?? "border-border/60 bg-secondary/60 text-foreground") : undefined}
      title={skill?.name ?? ""}
      description={skill?.description}
      meta={
        skill ? (
          <>
            <StatusPill active={skill.enabled} activeLabel="Enabled" inactiveLabel="Disabled" />
            <Tag>{skill.version}</Tag>
            <Tag>{skill.triggerType}</Tag>
            {scope && <Tag className={scope.className}>{scope.label}</Tag>}
            <Tag>{skill.category}</Tag>
          </>
        ) : undefined
      }
      actions={
        skill ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground" aria-label={`${skill.name} actions`}>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => rest.onEdit(skill)} className="gap-2 text-[13px]">
                <Pencil />
                Edit skill
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => rest.onDuplicate(skill)} className="gap-2 text-[13px]">
                <Copy />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => rest.onDelete(skill)} className="gap-2 text-[13px]">
                <Trash2 />
                Delete skill
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : undefined
      }
      alert={
        skill && skill.errors24h > 0 ? (
          <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3.5 py-3">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-red-300">
                {skill.errors24h} error{skill.errors24h === 1 ? "" : "s"} in the last 24 hours
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-red-300/80">
                Review the activity log for recent failures and check the skill's dependencies.
              </p>
            </div>
          </div>
        ) : undefined
      }
      footer={
        skill ? (
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Switch checked={skill.enabled} onCheckedChange={() => rest.onToggle(skill.id)} aria-label={`Toggle ${skill.name}`} />
              <span className="text-[13px] text-muted-foreground">{skill.enabled ? "Enabled" : "Disabled"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => rest.onEdit(skill)} className="gap-2">
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
              <Button onClick={() => rest.onRun(skill)} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
                <Play className="h-4 w-4" />
                Run skill
              </Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {skill && (
        <PanelTabs
          key={skill.id}
          skill={skill}
          onSaveInstructions={rest.onSaveInstructions}
          onSavePermissions={rest.onSavePermissions}
        />
      )}
    </DrawerShell>
  )
}

function PanelTabs({
  skill,
  onSaveInstructions,
  onSavePermissions,
}: {
  skill: Skill
  onSaveInstructions: (id: string, instructions: string) => void
  onSavePermissions: (id: string, perms: SkillPermissions) => void
}) {
  return (
    <Tabs defaultValue="overview" className="flex flex-col">
      <div className="sticky top-0 z-10 border-b border-border/60 bg-card/95 px-6 pt-4 pb-2 backdrop-blur">
        <TabsList className="h-9 w-auto justify-start gap-0.5 self-start rounded-lg border border-border/60 bg-secondary/30 p-1">
          <TabTrigger value="overview">Overview</TabTrigger>
          <TabTrigger value="instructions">Instructions</TabTrigger>
          <TabTrigger value="dependencies">Dependencies</TabTrigger>
          <TabTrigger value="permissions">Permissions</TabTrigger>
          <TabTrigger value="activity">Activity</TabTrigger>
        </TabsList>
      </div>

      <TabsContent value="overview" className="px-6 pt-3 pb-6">
        <OverviewTab skill={skill} />
      </TabsContent>
      <TabsContent value="instructions" className="px-6 pt-3 pb-6">
        <InstructionsTab skill={skill} onSave={onSaveInstructions} />
      </TabsContent>
      <TabsContent value="dependencies" className="px-6 pt-3 pb-6">
        <DependenciesTab skill={skill} />
      </TabsContent>
      <TabsContent value="permissions" className="px-6 pt-3 pb-6">
        <PermissionsTab skill={skill} onSave={onSavePermissions} />
      </TabsContent>
      <TabsContent value="activity" className="px-6 pt-3 pb-6">
        <ActivityTab activity={skill.activity} />
      </TabsContent>
    </Tabs>
  )
}

function TabTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsTrigger value={value} className="h-7 rounded-md px-3 text-[13px] data-[state=active]:bg-secondary data-[state=active]:text-foreground">
      {children}
    </TabsTrigger>
  )
}

/* ------------------------------------------------------------------ */
/*  Overview                                                           */
/* ------------------------------------------------------------------ */

function StatCell({ label, value, className, sub }: { label: string; value: string; className?: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-secondary/30 px-3.5 py-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">{label}</p>
      <p className={`mt-1 font-heading text-xl font-semibold ${className ?? "text-foreground"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  )
}

function usageBars(runCount: number, seed: string): number[] {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 997
  const base = Math.max(4, Math.round(runCount / 6))
  return Array.from({ length: 7 }, (_, i) => Math.max(2, ((h + i * 37) % base) + 2))
}

function OverviewTab({ skill }: { skill: Skill }) {
  const bars = useMemo(() => usageBars(skill.runCount, skill.id), [skill.runCount, skill.id])
  const max = Math.max(...bars)
  const activeOverrides = Object.values(skill.permissions.toolOverrides).filter((o) => !o.allowed).length

  return (
    <div className="flex flex-col gap-5">
      {skill.keywords.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground/70">Keywords</span>
          {skill.keywords.map((k) => (
            <Tag key={k}>{k}</Tag>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <StatCell label="Runs" value={skill.runCount.toLocaleString()} sub="Total executions" />
        <StatCell
          label="Success rate"
          value={`${skill.successRate}%`}
          className={skill.successRate >= 95 ? "text-emerald-400" : skill.successRate >= 85 ? "text-amber-400" : "text-red-400"}
          sub="Last 30 days"
        />
        <StatCell label="Avg duration" value={`${(skill.avgDurationMs / 1000).toFixed(1)}s`} sub="Per run" />
        <StatCell
          label="Errors (24h)"
          value={String(skill.errors24h)}
          className={skill.errors24h === 0 ? "text-emerald-400" : "text-red-400"}
          sub={skill.errors24h === 0 ? "No failures" : "Needs attention"}
        />
      </div>

      <PanelSection
        title="Usage over the last 7 days"
        description="Relative number of executions per day"
      >
        <div className="flex h-24 items-end gap-1.5">
          {bars.map((v, i) => (
            <div key={i} className="flex flex-1 flex-col items-center gap-1.5">
              <div
                className="w-full rounded-t-md bg-gradient-to-t from-secondary to-secondary/40"
                style={{ height: `${Math.max(8, (v / max) * 88)}px` }}
              />
              <span className="text-[10px] tabular-nums text-muted-foreground/70">
                {["M", "T", "W", "T", "F", "S", "S"][i]}
              </span>
            </div>
          ))}
        </div>
      </PanelSection>

      <PanelSection title="Details">
        <div className="divide-y divide-border/50">
          <DetailRow label="Version" value={<span className="font-mono">{skill.version}</span>} />
          <DetailRow label="Author" value={skill.author} />
          <DetailRow label="Scope" value={<span className={SCOPE_META[skill.scope].className}>{SCOPE_META[skill.scope].label}</span>} />
          <DetailRow label="Trigger" value={skill.triggerType} />
          <DetailRow label="Category" value={skill.category} />
          <DetailRow label="Added" value={skill.added} />
          <DetailRow label="Last used" value={skill.lastUsed} />
        </div>
      </PanelSection>

      <PanelSection title="Permissions summary">
        <PermissionBadgeRow
          icon={<Shield className="h-3.5 w-3.5" />}
          label="Confirmation"
          active={skill.permissions.flags.requireConfirmation}
          activeLabel="Required"
          inactiveLabel="Not required"
        />
        <PermissionBadgeRow
          icon={<FileEdit className="h-3.5 w-3.5" />}
          label="File writes"
          active={skill.permissions.flags.allowFileWrite}
          activeLabel="Allowed"
          inactiveLabel="Blocked"
        />
        <PermissionBadgeRow
          icon={<Globe className="h-3.5 w-3.5" />}
          label="Network"
          active={skill.permissions.flags.allowNetwork}
          activeLabel="Allowed"
          inactiveLabel="Blocked"
        />
        <PermissionBadgeRow
          icon={<Database className="h-3.5 w-3.5" />}
          label="DB mutations"
          active={skill.permissions.flags.allowDbMutations}
          activeLabel="Allowed"
          inactiveLabel="Blocked"
        />
        <PermissionBadgeRow
          icon={<Terminal className="h-3.5 w-3.5" />}
          label="Shell"
          active={skill.permissions.flags.allowShellCommands}
          activeLabel="Allowed"
          inactiveLabel="Blocked"
        />
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2">
          <ShieldCheck className="h-3.5 w-3.5 text-amber-400" />
          <p className="text-xs text-muted-foreground">
            {activeOverrides > 0
              ? `${activeOverrides} tool override${activeOverrides === 1 ? "" : "s"} restrict access.`
              : "No per-tool restrictions in effect."}
          </p>
        </div>
      </PanelSection>
    </div>
  )
}

function PermissionBadgeRow({ icon, label, active, activeLabel, inactiveLabel }: { icon: ReactNode; label: string; active: boolean; activeLabel: string; inactiveLabel: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <span className={active ? "text-emerald-400" : "text-muted-foreground/50"}>{icon}</span>
        {label}
      </span>
      <StatusBadge status={active ? "success" : "neutral"}>{active ? activeLabel : inactiveLabel}</StatusBadge>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Instructions (full editor with variables + dirty state)            */
/* ------------------------------------------------------------------ */

function InstructionsTab({ skill, onSave }: { skill: Skill; onSave: (id: string, instructions: string) => void }) {
  const [value, setValue] = useState(skill.instructions)
  const [saving, setSaving] = useState(false)
  const dirty = value !== skill.instructions

  const insertVariable = (key: string) => {
    const token = `{{${key}}}`
    setValue((v) => (v === "" ? token : `${v}\n${token}`))
  }

  const handleSave = () => {
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      onSave(skill.id, value)
      toast.success("Instructions saved")
    }, 600)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-[13px] font-medium text-foreground">System instructions</span>
          <Tag>v{skill.version}</Tag>
        </div>
        {dirty && <StatusBadge status="warning">Unsaved changes</StatusBadge>}
      </div>

      <div className="rounded-lg border border-border/60 bg-secondary/30 p-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          spellCheck={false}
          className="h-64 w-full resize-none bg-transparent p-2 font-mono text-[13px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/50"
          placeholder="Describe exactly how the agent should behave when this skill runs…"
        />
        <div className="flex items-center justify-between border-t border-border/60 px-2 pt-2">
          <span className="text-[11px] tabular-nums text-muted-foreground/70">{value.length} characters</span>
          <span className="text-[11px] text-muted-foreground/70">Variables are injected at run time</span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground">Variables</p>
          <p className="text-xs text-muted-foreground">Click a variable to append it to the instructions.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => setValue(skill.instructions)} disabled={!dirty || saving}>
            Discard
          </Button>
          <Button onClick={handleSave} disabled={!dirty || saving} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            Save instructions
          </Button>
        </div>
      </div>

      {skill.variables.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {skill.variables.map((v) => (
            <button
              key={v.key}
              onClick={() => insertVariable(v.key)}
              className="group flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-secondary/30 px-3.5 py-2.5 text-left transition-colors hover:border-border"
            >
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[13px] font-medium text-foreground">
                  <code className="font-mono text-[12px] text-sky-400">{"{{"}{v.key}{"}}"}</code>
                  {v.required && <Tag className="border-red-500/20 bg-red-500/10 text-red-400">required</Tag>}
                </p>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{v.label}: {v.description}</p>
              </div>
              <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-colors group-hover:text-foreground" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Dependencies                                                       */
/* ------------------------------------------------------------------ */

function DependenciesTab({ skill }: { skill: Skill }) {
  const rows = skill.requiredTools.map((tool) => {
    const found = AVAILABLE_CONNECTIONS.find((c) => c.name.toLowerCase() === tool.toLowerCase())
    return {
      name: tool,
      type: found?.type ?? "Unknown",
      installed: found?.installed ?? false,
    }
  })
  const missing = rows.filter((r) => !r.installed)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ActivityIcon className="h-4 w-4 text-muted-foreground" />
          <span className="text-[13px] font-medium text-foreground">Required connections & tools</span>
        </div>
        <StatusBadge status={missing.length === 0 ? "success" : "warning"}>
          {missing.length === 0 ? "All satisfied" : `${missing.length} missing`}
        </StatusBadge>
      </div>

      {skill.requiredTools.length === 0 ? (
        <p className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-6 text-center text-[13px] text-muted-foreground">
          This skill does not require any external connections or tools.
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-border/50 overflow-hidden rounded-lg border border-border/60">
          {rows.map((r) => (
            <div key={r.name} className="flex items-center justify-between gap-3 bg-secondary/20 px-4 py-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className={r.installed ? "text-emerald-400" : "text-red-400"}>
                  {r.installed ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-foreground">{r.name}</p>
                  <p className="text-[11px] text-muted-foreground">{r.type}</p>
                </div>
              </div>
              {r.installed ? (
                <StatusBadge status="success">Installed</StatusBadge>
              ) : (
                <StatusBadge status="error">Not installed</StatusBadge>
              )}
            </div>
          ))}
        </div>
      )}

      {missing.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/25 bg-amber-500/[0.06] px-3.5 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-amber-300">Missing dependencies</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              This skill will fail when it tries to use{" "}
              {missing.map((m) => m.name).join(", ")}. Install the corresponding MCP server or remove the dependency
              to keep the skill healthy.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Permissions                                                        */
/* ------------------------------------------------------------------ */

function PermissionsTab({ skill, onSave }: { skill: Skill; onSave: (id: string, perms: SkillPermissions) => void }) {
  const [perms, setPerms] = useState<SkillPermissions>({
    flags: { ...skill.permissions.flags },
    toolOverrides: Object.fromEntries(Object.entries(skill.permissions.toolOverrides).map(([k, v]) => [k, { ...v }])),
  })
  const [saving, setSaving] = useState(false)
  const dirty = JSON.stringify(perms) !== JSON.stringify(skill.permissions)

  const toggleFlag = (key: keyof SkillPermissions["flags"]) =>
    setPerms((p) => ({ ...p, flags: { ...p.flags, [key]: !p.flags[key] } }))

  const patchOverride = (tool: string, patch: Partial<ToolOverride>) =>
    setPerms((p) => {
      const existing = p.toolOverrides[tool] ?? { tool, allowed: true, requiresConfirmation: false }
      return { ...p, toolOverrides: { ...p.toolOverrides, [tool]: { ...existing, ...patch } } }
    })

  const handleSave = () => {
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      onSave(skill.id, perms)
      toast.success("Permissions updated")
    }, 600)
  }

  const flagRows: { key: keyof SkillPermissions["flags"]; icon: ReactNode; label: string; description: string }[] = [
    { key: "requireConfirmation", icon: <Shield className="h-4 w-4 text-muted-foreground" />, label: "Require confirmation", description: "Ask before the agent uses any tool in this skill." },
    { key: "allowFileWrite", icon: <FileEdit className="h-4 w-4 text-muted-foreground" />, label: "Allow file writes", description: "Let this skill create or modify files on the filesystem." },
    { key: "allowNetwork", icon: <Globe className="h-4 w-4 text-muted-foreground" />, label: "Allow network requests", description: "Let this skill make outbound HTTP/API calls." },
    { key: "allowDbMutations", icon: <Database className="h-4 w-4 text-muted-foreground" />, label: "Allow DB mutations", description: "Let this skill run write/update/delete queries." },
    { key: "allowShellCommands", icon: <Terminal className="h-4 w-4 text-muted-foreground" />, label: "Allow shell commands", description: "Let this skill execute commands in a sandboxed shell." },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          <span className="text-[13px] font-medium text-foreground">Permission policy</span>
        </div>
        {dirty && <StatusBadge status="warning">Unsaved changes</StatusBadge>}
      </div>

      <div className="flex flex-col divide-y divide-border/50 overflow-hidden rounded-lg border border-border/60">
        {flagRows.map((row) => (
          <div key={row.key} className="flex items-center justify-between gap-4 bg-secondary/20 px-4 py-3">
            <div className="flex min-w-0 items-center gap-2.5">
              {row.icon}
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">{row.label}</p>
                <p className="text-xs text-muted-foreground">{row.description}</p>
              </div>
            </div>
            <Switch checked={perms.flags[row.key]} onCheckedChange={() => toggleFlag(row.key)} aria-label={row.label} />
          </div>
        ))}
      </div>

      {skill.requiredTools.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-[13px] font-medium text-foreground">Per-tool access</p>
          <div className="flex flex-col divide-y divide-border/50 overflow-hidden rounded-lg border border-border/60">
            {skill.requiredTools.map((tool) => {
              const o = perms.toolOverrides[tool] ?? { tool, allowed: true, requiresConfirmation: false }
              return (
                <div key={tool} className="flex items-center justify-between gap-3 bg-secondary/20 px-4 py-3">
                  <div className="min-w-0">
                    <p className={`truncate text-[13px] font-medium ${o.allowed ? "text-foreground" : "text-muted-foreground line-through"}`}>{tool}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {o.allowed ? (o.requiresConfirmation ? "Allowed, with confirmation" : "Allowed") : "Blocked"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      Confirm
                      <Switch checked={o.requiresConfirmation} onCheckedChange={(v) => patchOverride(tool, { requiresConfirmation: v })} disabled={!o.allowed} aria-label={`Confirm ${tool}`} className="scale-75" />
                    </label>
                    <Switch checked={o.allowed} onCheckedChange={(v) => patchOverride(tool, { allowed: v, requiresConfirmation: v ? o.requiresConfirmation : false })} aria-label={`Allow ${tool}`} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={() => setPerms({ flags: { ...skill.permissions.flags }, toolOverrides: { ...skill.permissions.toolOverrides } })} disabled={!dirty || saving}>
          Discard
        </Button>
        <Button onClick={handleSave} disabled={!dirty || saving} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Save permissions
        </Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Activity                                                           */
/* ------------------------------------------------------------------ */

function activityIcon(status: ActivityStatus, className: string): ReactNode {
  switch (status) {
    case "success":
      return <CheckCircle2 className={className} />
    case "error":
      return <XCircle className={className} />
    case "warning":
      return <AlertTriangle className={className} />
    default:
      return <CircleDot className={className} />
  }
}

const FILTERS = ["All", "Success", "Warnings", "Errors", "Info"] as const
type ActivityFilter = (typeof FILTERS)[number]

function ActivityTab({ activity }: { activity: SkillActivity[] }) {
  const [filter, setFilter] = useState<ActivityFilter>("All")
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const pageSize = 7

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return activity.filter((a) => {
      const matchesFilter =
        filter === "All" ||
        (filter === "Success" && a.status === "success") ||
        (filter === "Warnings" && a.status === "warning") ||
        (filter === "Errors" && a.status === "error") ||
        (filter === "Info" && a.status === "info")
      const matchesQuery = !q || a.action.toLowerCase().includes(q) || a.detail.toLowerCase().includes(q)
      return matchesFilter && matchesQuery
    })
  }, [activity, filter, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount)
  const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1) }}
            placeholder="Search activity…"
            className="h-8 w-full rounded-lg border border-border/60 bg-card/40 pl-8 pr-2 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-border"
          />
        </div>
        <div className="flex items-center gap-0.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1) }}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                filter === f ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border/60 px-4 py-10 text-center text-[13px] text-muted-foreground">
          No activity matches your filter.
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-border/50">
          {visible.map((a) => (
            <ActivityLogEntry
              key={a.id}
              icon={activityIcon(a.status, "h-4 w-4")}
              title={a.action}
              detail={a.detail}
              time={a.time}
              status={a.status === "success" ? "success" : a.status === "error" ? "error" : a.status === "warning" ? "warning" : "default"}
            />
          ))}
        </div>
      )}

      <Pagination page={safePage} pageSize={pageSize} total={filtered.length} onPageChange={setPage} />
    </div>
  )
}
