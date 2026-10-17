"use client"

import { useEffect, useMemo, useState } from "react"
import {
  MoreHorizontal,
  Pencil,
  Eye,
  Trash2,
  Copy,
  Zap,
  Plus,
  Store,
  Blocks,
  SearchX,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  PageContainer,
  PageHeader,
  ItemCard,
  SearchBar,
  SegmentedTabs,
  ConfirmDialog,
} from "@/components/management/shared"
import { SkillDetailPanel } from "./skill-detail"
import { SkillDialog, SkillTestDialog } from "./skill-dialogs"
import { categoryIcon } from "./skill-data"
import type { Skill, SkillTemplate } from "./skill-types"
import { useSkills } from "@/lib/skills-store"
import { useNavigation } from "@/lib/navigation"

type StatusFilter = "all" | "enabled" | "disabled"

export function SkillsPage() {
  const { skills, toggleSkill, deleteSkill, duplicateSkill, saveSkill, saveInstructions, savePermissions, runCompleted } =
    useSkills()
  const { setView } = useNavigation()

  const [loaded, setLoaded] = useState(false)
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<StatusFilter>("all")

  const [detailId, setDetailId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Skill | null>(null)
  const [templatePrefill, setTemplatePrefill] = useState<SkillTemplate | null>(null)
  const [testTarget, setTestTarget] = useState<Skill | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Skill | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 400)
    return () => clearTimeout(t)
  }, [])

  const detail = useMemo(() => skills.find((s) => s.id === detailId) ?? null, [skills, detailId])

  const counts = useMemo(
    () => ({
      all: skills.length,
      enabled: skills.filter((s) => s.enabled).length,
      disabled: skills.filter((s) => !s.enabled).length,
    }),
    [skills],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return skills.filter((s) => {
      const matchesQuery = !q || s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
      const matchesStatus = status === "all" || (status === "enabled" && s.enabled) || (status === "disabled" && !s.enabled)
      return matchesQuery && matchesStatus
    })
  }, [skills, query, status])

  const openCreate = () => {
    setEditing(null)
    setTemplatePrefill(null)
    setDialogOpen(true)
  }

  const openEdit = (skill: Skill) => {
    setEditing(skill)
    setTemplatePrefill(null)
    setDialogOpen(true)
  }

  return (
    <PageContainer>
      <PageHeader
        title="Skills"
        icon={Blocks}
        description="Skills add reusable capabilities your agent can invoke on demand. Manage what is installed, configure permissions, and watch activity."
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setView("marketplace")} className="gap-2">
              <Store className="h-4 w-4" />
              Browse marketplace
            </Button>
            <Button onClick={openCreate} className="gap-2">
              <Plus className="h-4 w-4" />
              Add skill
            </Button>
          </div>
        }
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="max-w-md flex-1 sm:flex-none sm:min-w-64">
          <SearchBar value={query} onChange={setQuery} placeholder="Search skills..." />
        </div>
        <SegmentedTabs
          tabs={[
            { id: "all", label: "All", count: counts.all },
            { id: "enabled", label: "Enabled", count: counts.enabled },
            { id: "disabled", label: "Disabled", count: counts.disabled },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>

      {!loaded ? (
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[96px] animate-pulse rounded-xl border border-border/60 bg-card/30" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="dream-in flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-card/30 px-6 py-16 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/60 bg-secondary/60">
            {skills.length === 0 ? (
              <Blocks className="h-5 w-5 text-muted-foreground" />
            ) : (
              <SearchX className="h-5 w-5 text-muted-foreground" />
            )}
          </span>
          <p className="mt-4 text-sm font-medium text-foreground">
            {skills.length === 0 ? "No skills yet" : "No matching skills"}
          </p>
          <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
            {skills.length === 0
              ? "Install a skill from the marketplace or create your own to get started."
              : "Try a different search or status filter."}
          </p>
          {skills.length === 0 && (
            <Button variant="secondary" onClick={() => setView("marketplace")} className="mt-5 gap-2">
              <Store className="h-4 w-4" />
              Browse marketplace
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          {filtered.map((s) => {
            const Icon = categoryIcon(s.category)
            return (
              <ItemCard
                key={s.id}
                icon={<Icon className="h-5 w-5 text-muted-foreground" />}
                name={s.name}
                description={s.description}
                enabled={s.enabled}
                onToggle={() => toggleSkill(s.id)}
                onOpen={() => setDetailId(s.id)}
                menu={
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        aria-label={`${s.name} options`}
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem onClick={() => setDetailId(s.id)}>
                        <Eye />
                        View details
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setTestTarget(s)}>
                        <Zap />
                        Run and test
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => duplicateSkill(s)}>
                        <Copy />
                        Duplicate
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openEdit(s)}>
                        <Pencil />
                        Edit skill
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem variant="destructive" onClick={() => setDeleteTarget(s)}>
                        <Trash2 />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                }
              />
            )
          })}
        </div>
      )}

      <SkillDetailPanel
        skill={detail}
        onOpenChange={(open) => {
          if (!open) setDetailId(null)
        }}
        onToggle={toggleSkill}
        onEdit={openEdit}
        onDuplicate={duplicateSkill}
        onDelete={(s) => setDeleteTarget(s)}
        onSaveInstructions={saveInstructions}
        onSavePermissions={savePermissions}
        onRun={(s) => setTestTarget(s)}
      />

      <SkillDialog
        open={dialogOpen}
        skill={editing}
        templatePrefill={templatePrefill}
        onOpenChange={setDialogOpen}
        onSave={saveSkill}
      />

      <SkillTestDialog
        skill={testTarget}
        onOpenChange={(open) => {
          if (!open) setTestTarget(null)
        }}
        onCompleted={(s, ok) => runCompleted(s, ok)}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Delete skill"
        description={`"${deleteTarget?.name ?? ""}" will be removed from your workspace. Installed tools and history are not affected.`}
        confirmLabel="Delete"
        onConfirm={() => {
          if (!deleteTarget) return
          if (detailId === deleteTarget.id) setDetailId(null)
          deleteSkill(deleteTarget.id)
        }}
      />
    </PageContainer>
  )
}
