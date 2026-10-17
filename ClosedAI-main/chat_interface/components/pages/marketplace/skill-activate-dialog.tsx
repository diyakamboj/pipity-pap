"use client"

import { useState } from "react"
import { Check, Shield } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CATEGORY_TONES, Tag } from "@/components/management/shared"
import { defaultPermissions } from "@/components/pages/skills/skill-data"
import type { SkillPermissionFlags, SkillTemplate } from "@/components/pages/skills/skill-types"
import { cn } from "@/lib/utils"

const PERMISSION_ROWS: { key: keyof SkillPermissionFlags; label: string; description: string }[] = [
  { key: "requireConfirmation", label: "Require confirmation", description: "Ask before the agent uses tools from this skill." },
  { key: "allowFileWrite", label: "Allow file writes", description: "Let the skill create and modify files." },
  { key: "allowNetwork", label: "Allow network access", description: "Let the skill make outbound requests." },
  { key: "allowDbMutations", label: "Allow database mutations", description: "Let the skill write to connected databases." },
  { key: "allowShellCommands", label: "Allow shell commands", description: "Let the skill run commands in the terminal." },
]

/* Pre-install review + configuration for a Skill from the marketplace. */
export function SkillActivateDialog({
  template,
  onOpenChange,
  onActivate,
}: {
  template: SkillTemplate | null
  onOpenChange: (open: boolean) => void
  onActivate: (tpl: SkillTemplate, flags: SkillPermissionFlags) => void
}) {
  const isOpen = template !== null
  const [flags, setFlags] = useState<SkillPermissionFlags>(defaultPermissions().flags)
  const [syncedFor, setSyncedFor] = useState<string | null>(null)

  // Sync form state whenever a different template is opened (matches app convention)
  const currentKey = template?.id ?? "none"
  if (isOpen && syncedFor !== currentKey) {
    setFlags(defaultPermissions().flags)
    setSyncedFor(currentKey)
  }
  if (!isOpen && syncedFor !== null) setSyncedFor(null)

  if (!template) return null

  const Icon = template.icon
  const tone = CATEGORY_TONES[template.category] ?? "border-border/60 bg-secondary/60 text-foreground"

  const setFlag = (key: keyof SkillPermissionFlags, value: boolean) =>
    setFlags((prev) => ({ ...prev, [key]: value }))

  const handleActivate = () => {
    onActivate(template, flags)
    onOpenChange(false)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] gap-0 overflow-y-auto border-border/60 bg-card p-0 sm:max-w-xl">
        <DialogHeader className="border-b border-border/60 px-6 py-5">
          <div className="flex items-start gap-4">
            <span className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border", tone)}>
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <DialogTitle className="font-heading text-lg">{template.name}</DialogTitle>
              <DialogDescription className="text-muted-foreground">{template.description}</DialogDescription>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">{template.category}</span>
                <span className="rounded-full border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {template.triggerType}
                </span>
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="flex flex-col gap-6 px-6 py-6">
          {/* Review: what gets installed */}
          <section className="flex flex-col gap-2">
            <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Review</h4>
            <div className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
              <p className="text-[13px] font-medium text-foreground">Required connections / tools</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {template.requiredTools.length === 0 ? (
                  <span className="text-xs text-muted-foreground">No external tools required</span>
                ) : (
                  template.requiredTools.map((tool) => <Tag key={tool}>{tool}</Tag>)
                )}
              </div>
            </div>
          </section>

          {/* Permissions: the actionable configuration */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Permissions</h4>
            </div>
            <div className="flex flex-col rounded-lg border border-border/60 bg-secondary/30 px-1">
              {PERMISSION_ROWS.map((row, i) => (
                <div
                  key={row.key}
                  className={cn(
                    "flex items-center justify-between gap-4 px-3.5 py-3",
                    i !== PERMISSION_ROWS.length - 1 && "border-b border-border/60",
                  )}
                >
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-foreground">{row.label}</p>
                    <p className="text-xs text-muted-foreground">{row.description}</p>
                  </div>
                  <Switch
                    checked={flags[row.key]}
                    onCheckedChange={(v) => setFlag(row.key, v)}
                    aria-label={row.label}
                  />
                </div>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground/70">
              Permissions apply immediately after installation and can be changed later from the Skills page.
            </p>
          </section>

          {/* Expected inputs */}
          <section className="flex flex-col gap-2">
            <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Expected inputs</h4>
            <div className="flex flex-col gap-2">
              {template.variables.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border/60 bg-secondary/20 px-4 py-3 text-xs text-muted-foreground">
                  No inputs required at runtime.
                </p>
              ) : (
                template.variables.map((v) => (
                  <div
                    key={v.key}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-secondary/20 px-4 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-foreground">{v.label || v.key}</p>
                      {v.description && <p className="text-xs text-muted-foreground">{v.description}</p>}
                    </div>
                    {v.required && (
                      <span className="shrink-0 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                        Required
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        <DialogFooter className="border-t border-border/60 px-6 py-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleActivate} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
            <Check className="h-4 w-4" />
            Add to workspace
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
