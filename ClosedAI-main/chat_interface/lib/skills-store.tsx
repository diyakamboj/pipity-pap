"use client"

import { createContext, useContext, useState, useMemo, type ReactNode } from "react"
import { toast } from "sonner"
import { INITIAL_SKILLS, defaultPermissions, todayLabel, uid } from "@/components/pages/skills/skill-data"
import type { Skill, SkillPermissionFlags, SkillPermissions, SkillTemplate } from "@/components/pages/skills/skill-types"

interface SkillsContextValue {
  skills: Skill[]
  toggleSkill: (id: string) => void
  deleteSkill: (id: string) => void
  duplicateSkill: (skill: Skill) => void
  saveSkill: (skill: Skill) => void
  saveInstructions: (id: string, instructions: string) => void
  savePermissions: (id: string, perms: SkillPermissions) => void
  runCompleted: (skill: Skill, ok: boolean) => void
  installTemplate: (tpl: SkillTemplate, config?: { flags?: SkillPermissionFlags }) => void
}

const SkillsContext = createContext<SkillsContextValue | null>(null)

export function SkillsProvider({ children }: { children: ReactNode }) {
  const [skills, setSkills] = useState<Skill[]>(INITIAL_SKILLS)

  const patchSkill = (id: string, fn: (s: Skill) => Skill) =>
    setSkills((prev) => prev.map((s) => (s.id === id ? fn(s) : s)))

  const toggleSkill = (id: string) => {
    const skill = skills.find((s) => s.id === id)
    if (!skill) return
    const next = !skill.enabled
    patchSkill(id, (s) => ({
      ...s,
      enabled: next,
      activity: [
        { id: `a-${uid()}`, action: next ? "Skill enabled" : "Skill disabled", detail: `${s.name} ${next ? "enabled" : "disabled"}`, time: "just now", ts: Date.now(), status: "info" as const },
        ...s.activity,
      ],
    }))
    toast(next ? `${skill.name} enabled` : `${skill.name} disabled`)
  }

  const deleteSkill = (id: string) => {
    setSkills((prev) => prev.filter((s) => s.id !== id))
    toast.success("Skill removed")
  }

  const duplicateSkill = (skill: Skill) => {
    const clone: Skill = {
      ...skill,
      id: `skill-${uid()}`,
      name: `${skill.name} (Copy)`,
      enabled: false,
      version: "1.0.0",
      added: todayLabel(),
      lastUsed: "never",
      lastUsedTs: 0,
      runCount: 0,
      successRate: 100,
      avgDurationMs: 0,
      errors24h: 0,
      activity: [{ id: `a-${uid()}`, action: "Skill created", detail: "Duplicated from an existing skill", time: "just now", ts: Date.now(), status: "info" }],
    }
    setSkills((prev) => [clone, ...prev])
    toast.success(`Duplicated "${skill.name}"`)
  }

  const saveSkill = (skill: Skill) => {
    setSkills((prev) => {
      const exists = prev.some((s) => s.id === skill.id)
      return exists ? prev.map((s) => (s.id === skill.id ? skill : s)) : [skill, ...prev]
    })
  }

  const saveInstructions = (id: string, instructions: string) => {
    patchSkill(id, (s) => ({
      ...s,
      instructions,
      activity: [
        { id: `a-${uid()}`, action: "Instructions updated", detail: "System prompt revised by the operator", time: "just now", ts: Date.now(), status: "info" },
        ...s.activity,
      ],
    }))
  }

  const savePermissions = (id: string, perms: SkillPermissions) => {
    patchSkill(id, (s) => ({
      ...s,
      permissions: perms,
      activity: [
        { id: `a-${uid()}`, action: "Permissions updated", detail: "Policy revised by the operator", time: "just now", ts: Date.now(), status: "info" },
        ...s.activity,
      ],
    }))
  }

  const runCompleted = (skill: Skill, ok: boolean) => {
    patchSkill(skill.id, (s) => ({
      ...s,
      runCount: s.runCount + 1,
      lastUsed: "just now",
      lastUsedTs: Date.now(),
      errors24h: ok ? s.errors24h : s.errors24h + 1,
      successRate: Math.max(0, Math.min(100, Math.round((s.successRate * s.runCount + (ok ? 100 : 0)) / (s.runCount + 1)))),
      activity: [
        { id: `a-${uid()}`, action: ok ? "Ran skill" : "Run failed", detail: ok ? "Executed via test preview" : "Test run failed", time: "just now", ts: Date.now(), status: ok ? ("success" as const) : ("error" as const) },
        ...s.activity,
      ],
    }))
    if (ok) toast.success(`${skill.name} run completed`)
    else toast.error(`${skill.name} run failed`)
  }

  const installTemplate = (tpl: SkillTemplate, config?: { flags?: SkillPermissionFlags }) => {
    const flags = config?.flags ?? defaultPermissions().flags
    const permissions: SkillPermissions = {
      flags,
      toolOverrides: Object.fromEntries(
        tpl.requiredTools.map((tool) => [
          tool,
          { tool, allowed: true, requiresConfirmation: flags.requireConfirmation },
        ]),
      ),
    }
    const skill: Skill = {
      id: `skill-${uid()}`,
      name: tpl.name,
      description: tpl.description,
      category: tpl.category,
      scope: "global",
      triggerType: tpl.triggerType,
      keywords: [],
      enabled: true,
      version: "1.0.0",
      author: "me",
      requiredTools: tpl.requiredTools,
      instructions: tpl.instructions,
      variables: tpl.variables,
      added: todayLabel(),
      lastUsed: "never",
      lastUsedTs: 0,
      runCount: 0,
      successRate: 100,
      avgDurationMs: 0,
      errors24h: 0,
      permissions,
      activity: [{ id: `a-${uid()}`, action: "Skill created", detail: "Installed from the marketplace", time: "just now", ts: Date.now(), status: "info" }],
    }
    setSkills((prev) => [skill, ...prev])
    toast.success(`${tpl.name} installed`)
  }

  const value = useMemo<SkillsContextValue>(
    () => ({
      skills,
      toggleSkill,
      deleteSkill,
      duplicateSkill,
      saveSkill,
      saveInstructions,
      savePermissions,
      runCompleted,
      installTemplate,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [skills],
  )

  return <SkillsContext.Provider value={value}>{children}</SkillsContext.Provider>
}

export function useSkills() {
  const ctx = useContext(SkillsContext)
  if (!ctx) throw new Error("useSkills must be used within a SkillsProvider")
  return ctx
}
