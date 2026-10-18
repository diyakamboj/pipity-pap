"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  Lock,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react"
import {
  DrawerShell,
  EmptyState,
  PageContainer,
  PageHeader,
  PanelSection,
  SearchBar,
  StatusBadge,
  Tag,
  type StatusTone,
} from "@/components/management/shared"
import { Button } from "@/components/ui/button"
import {
  fetchLogisticsProposal,
  fetchLogisticsProposals,
  type LogisticsProposal,
  type ProposedChange,
} from "@/lib/logistics-client"
import { cn } from "@/lib/utils"

type FilterKey = "all" | "pending" | "approved" | "rejected" | "expired"

interface LogisticsProposalsViewProps {
  initialEventId?: string
}

export function LogisticsProposalsView({ initialEventId }: LogisticsProposalsViewProps) {
  const [proposals, setProposals] = useState<LogisticsProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterKey>("all")
  const [search, setSearch] = useState("")
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [selectedProposal, setSelectedProposal] = useState<LogisticsProposal | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadProposals = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)

    try {
      const res = await fetchLogisticsProposals({
        event_id: initialEventId,
      })
      setProposals(res.proposals || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load logistics proposals.")
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void loadProposals()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialEventId])

  // Fetch full details when a proposal is selected for the drawer
  useEffect(() => {
    if (!selectedProposalId) {
      setSelectedProposal(null)
      return
    }

    let cancelled = false
    setDetailLoading(true)

    fetchLogisticsProposal(selectedProposalId)
      .then((detail) => {
        if (!cancelled) setSelectedProposal(detail)
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to fetch proposal details:", err)
          // Fall back to item already in proposals list if fetch fails
          const fallback = proposals.find((p) => p.id === selectedProposalId) || null
          setSelectedProposal(fallback)
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedProposalId, proposals])

  const filterCounts = useMemo(() => {
    const counts: Record<FilterKey, number> = {
      all: proposals.length,
      pending: 0,
      approved: 0,
      rejected: 0,
      expired: 0,
    }

    for (const p of proposals) {
      const eff = p.effective_status.toLowerCase()
      if (eff === "pending") counts.pending++
      else if (eff === "approved") counts.approved++
      else if (eff === "rejected") counts.rejected++
      else if (eff === "expired" || p.is_expired) counts.expired++
    }
    return counts
  }, [proposals])

  const filteredProposals = useMemo(() => {
    return proposals.filter((p) => {
      // Status filter matching
      const eff = p.effective_status.toLowerCase()
      if (filter === "pending" && eff !== "pending") return false
      if (filter === "approved" && eff !== "approved") return false
      if (filter === "rejected" && eff !== "rejected") return false
      if (filter === "expired" && eff !== "expired" && !p.is_expired) return false

      // Search term matching
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchTitle = p.title.toLowerCase().includes(q)
        const matchId = p.id.toLowerCase().includes(q)
        const matchTarget = p.target_schedule_id.toLowerCase().includes(q)
        const matchDesc = p.description.toLowerCase().includes(q)
        if (!matchTitle && !matchId && !matchTarget && !matchDesc) return false
      }

      return true
    })
  }, [proposals, filter, search])

  return (
    <PageContainer>
      <PageHeader
        title="Schedule Change Proposals"
        icon={Calendar}
        description="Inspect and review deterministic schedule conflict resolutions proposed by the Gurt Logistics Engine."
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadProposals(true)}
            disabled={loading || refreshing}
            className="gap-2 border-border/60 bg-secondary/50 text-foreground hover:bg-secondary"
          >
            <RefreshCw className={cn("size-3.5", (loading || refreshing) && "animate-spin")} />
            Refresh
          </Button>
        }
      />

      {/* Security posture notice banner */}
      <div className="mb-6 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-4 text-xs text-amber-200">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-400" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-100">
              Read-Only Proposal Review Mode
            </p>
            <p className="leading-relaxed text-amber-200/80">
              Gurt is currently running without an external organizer authentication provider.
              Proposals are displayed directly from the authoritative server store for review.
              Mutation controls (Approve &amp; Reject) fail closed on the server (HTTP 401) and remain
              disabled in the UI until verified organizer identity is configured in Phase 5B.6.
            </p>
          </div>
        </div>
      </div>

      {/* Toolbar: search and status filter tabs */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          <Filter className="mr-1 size-3.5 text-muted-foreground" />
          {(
            [
              { key: "all", label: "All" },
              { key: "pending", label: "Pending Review" },
              { key: "approved", label: "Approved" },
              { key: "rejected", label: "Rejected" },
              { key: "expired", label: "Expired" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                filter === tab.key
                  ? "border-sky-500/40 bg-sky-500/10 font-semibold text-sky-400"
                  : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              <span>{tab.label}</span>
              <span className="rounded-full bg-white/10 px-1.5 py-0.2 text-[10px] tabular-nums text-neutral-300">
                {filterCounts[tab.key]}
              </span>
            </button>
          ))}
        </div>

        <div className="w-full sm:w-64">
          <SearchBar
            value={search}
            onChange={setSearch}
            placeholder="Search proposals..."
          />
        </div>
      </div>

      {/* Content list area */}
      {loading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-xl border border-border/60 bg-card/40 p-8 text-center">
          <RefreshCw className="size-6 animate-spin text-muted-foreground" />
          <p className="text-sm font-medium text-foreground">Loading logistics proposals...</p>
          <p className="text-xs text-muted-foreground">Connecting to EventStore approval service</p>
        </div>
      ) : error ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-xl border border-red-500/30 bg-red-500/[0.05] p-8 text-center text-red-300">
          <XCircle className="size-8 text-red-400" />
          <p className="text-sm font-semibold text-red-200">Unable to load proposals</p>
          <p className="max-w-md text-xs text-red-300/80">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadProposals(true)}
            className="mt-2 border-red-500/40 bg-red-500/10 text-red-200 hover:bg-red-500/20"
          >
            Retry Connection
          </Button>
        </div>
      ) : filteredProposals.length === 0 ? (
        <EmptyState
          icon={<Calendar className="size-5 text-muted-foreground" />}
          title="No proposals found"
          description={
            search
              ? `No proposals match the search query "${search}".`
              : filter !== "all"
                ? `No proposals in "${filter}" status.`
                : "No schedule change proposals have been registered in the EventStore yet."
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredProposals.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              onSelect={() => setSelectedProposalId(proposal.id)}
            />
          ))}
        </div>
      )}

      {/* Detailed Inspection Drawer */}
      <ProposalDetailDrawer
        proposal={selectedProposal}
        loading={detailLoading}
        open={Boolean(selectedProposalId)}
        onOpenChange={(open) => {
          if (!open) setSelectedProposalId(null)
        }}
      />
    </PageContainer>
  )
}

function getProposalStatusMeta(proposal: LogisticsProposal): {
  label: string
  tone: StatusTone
  subtext?: string
} {
  const isExpired = proposal.is_expired || proposal.effective_status.toLowerCase() === "expired"
  const isStale = proposal.is_stale
  const status = proposal.status.toLowerCase()

  if (isExpired) {
    return {
      label: "Expired",
      tone: "error",
      subtext: proposal.persisted_status === "pending" ? "Expired before review" : undefined,
    }
  }

  if (isStale) {
    return {
      label: "Stale Baseline",
      tone: "warning",
      subtext: "Schedule item modified",
    }
  }

  if (status === "approved") {
    return {
      label: "Approved (Applied)",
      tone: "success",
    }
  }

  if (status === "rejected") {
    return {
      label: "Rejected",
      tone: "neutral",
    }
  }

  return {
    label: "Pending Review",
    tone: "info",
  }
}

function ProposalCard({
  proposal,
  onSelect,
}: {
  proposal: LogisticsProposal
  onSelect: () => void
}) {
  const statusMeta = getProposalStatusMeta(proposal)
  const changesCount = proposal.proposed_changes?.length ?? 0
  const impact = proposal.impact || {}
  const conflictsResolvedCount = Array.isArray(impact.conflicts_resolved)
    ? impact.conflicts_resolved.length
    : 0
  const conflictsCreatedCount = Array.isArray(impact.conflicts_created)
    ? impact.conflicts_created.length
    : 0

  return (
    <div
      onClick={onSelect}
      className="group relative cursor-pointer rounded-xl border border-border/60 bg-card/60 p-4.5 transition-all hover:border-sky-500/40 hover:bg-card/90"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-semibold text-sky-400">
              {proposal.id}
            </span>
            <StatusBadge status={statusMeta.tone}>
              {statusMeta.label}
            </StatusBadge>
            {proposal.is_stale && (
              <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                Stale
              </span>
            )}
            {proposal.required_confirmations?.map((role) => (
              <Tag key={role} className="border-violet-500/30 bg-violet-500/10 text-violet-300">
                Req: {role}
              </Tag>
            ))}
          </div>

          <h3 className="text-base font-semibold leading-tight text-foreground group-hover:text-sky-300">
            {proposal.title}
          </h3>

          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {proposal.description || "Schedule modification proposal."}
          </p>

          {/* Quick summary line of changes & impacts */}
          <div className="flex flex-wrap items-center gap-4 pt-1 text-[11.5px] text-muted-foreground">
            <span className="flex items-center gap-1 font-mono text-neutral-300">
              Target: {proposal.target_schedule_id}
            </span>
            <span>{changesCount} {changesCount === 1 ? "field change" : "field changes"}</span>
            {conflictsResolvedCount > 0 && (
              <span className="font-medium text-emerald-400">
                ✓ Resolves {conflictsResolvedCount} {conflictsResolvedCount === 1 ? "conflict" : "conflicts"}
              </span>
            )}
            {conflictsCreatedCount > 0 && (
              <span className="font-semibold text-red-400">
                ⚠ Introduces {conflictsCreatedCount} {conflictsCreatedCount === 1 ? "conflict" : "conflicts"}
              </span>
            )}
            {proposal.expires_at && (
              <span className="flex items-center gap-1 text-neutral-400">
                <Clock className="size-3" />
                Expires: {formatIsoDate(proposal.expires_at)}
              </span>
            )}
          </div>
        </div>

        <div className="shrink-0 pt-1">
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs text-sky-400 hover:text-sky-300 group-hover:bg-sky-500/10"
          >
            Review Details
            <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

function ProposalDetailDrawer({
  proposal,
  loading,
  open,
  onOpenChange,
}: {
  proposal: LogisticsProposal | null
  loading: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!proposal) return null

  const statusMeta = getProposalStatusMeta(proposal)
  const changes = proposal.proposed_changes || []
  const impact = proposal.impact || {}

  const conflictsResolved = Array.isArray(impact.conflicts_resolved)
    ? impact.conflicts_resolved
    : []
  const conflictsCreated = Array.isArray(impact.conflicts_created)
    ? impact.conflicts_created
    : []
  const affectedSessions = Array.isArray(impact.affected_sessions)
    ? impact.affected_sessions
    : []
  const briefingsInvalidated = Array.isArray(impact.briefings_invalidated)
    ? impact.briefings_invalidated
    : []

  return (
    <DrawerShell
      open={open}
      onOpenChange={onOpenChange}
      eyebrow={`Logistics Proposal · ${proposal.event_id}`}
      title={proposal.title}
      description={proposal.description}
      icon={<Calendar className="size-5 text-sky-400" />}
      meta={
        <>
          <span className="font-mono text-xs text-sky-400">{proposal.id}</span>
          <StatusBadge status={statusMeta.tone}>{statusMeta.label}</StatusBadge>
          {proposal.is_stale && (
            <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
              Stale Baseline
            </span>
          )}
          {proposal.is_expired && (
            <span className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[11px] font-medium text-red-300">
              Expired
            </span>
          )}
        </>
      }
      alert={
        <div className="space-y-2 pt-3">
          {proposal.is_stale && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
              <div className="flex items-start gap-2">
                <AlertTriangle className="size-4 shrink-0 text-amber-400" />
                <p>
                  <strong>Stale Proposal Warning:</strong> The target schedule item has been modified
                  in the EventStore since this proposal was generated (baseline fingerprint mismatch).
                  Applying this proposal would cause an optimistic locking conflict.
                </p>
              </div>
            </div>
          )}

          {proposal.is_expired && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">
              <div className="flex items-start gap-2">
                <Clock className="size-4 shrink-0 text-red-400" />
                <p>
                  <strong>Expired Proposal:</strong> This proposal expired on{" "}
                  {formatIsoDate(proposal.expires_at)} and can no longer be executed.
                </p>
              </div>
            </div>
          )}

          {proposal.rejection_reason && (
            <div className="rounded-lg border border-neutral-700 bg-neutral-800/80 p-3 text-xs text-neutral-300">
              <p>
                <strong>Rejection Reason:</strong> {proposal.rejection_reason}
              </p>
            </div>
          )}

          <div className="rounded-lg border border-white/[0.08] bg-black/30 p-3 text-xs text-neutral-400">
            <div className="flex items-start gap-2">
              <Lock className="size-4 shrink-0 text-neutral-400" />
              <p>
                <strong>Mutation Controls Locked:</strong> Organizer authentication is unconfigured.
                Approve and Reject operations fail closed on the server (HTTP 401).
              </p>
            </div>
          </div>
        </div>
      }
      footer={
        <div className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between border-t border-border/60 bg-card/80">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="size-3.5 text-neutral-400" />
            <span>Approval provider pending Phase 5B.6</span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled
              title="Rejection disabled: Organizer authentication provider is not configured"
              className="gap-1.5 border-border/60 opacity-60 cursor-not-allowed"
            >
              <XCircle className="size-3.5" />
              Reject Proposal
            </Button>
            <Button
              variant="default"
              size="sm"
              disabled
              title="Approval disabled: Organizer authentication provider is not configured"
              className="gap-1.5 bg-sky-600/60 opacity-60 cursor-not-allowed"
            >
              <CheckCircle2 className="size-3.5" />
              Approve Proposal
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-6 p-6">
        {/* Section 1: Proposed Changes Diffs */}
        <PanelSection
          title="Proposed Schedule Changes"
          description={`Strict field mutations targeting item '${proposal.target_schedule_id}'.`}
        >
          {changes.length === 0 ? (
            <p className="text-xs text-muted-foreground">No field mutations declared.</p>
          ) : (
            <div className="divide-y divide-border/40 overflow-hidden rounded-lg border border-border/60 bg-black/20">
              {changes.map((c, idx) => (
                <ProposedChangeRow key={`${c.field}-${idx}`} change={c} />
              ))}
            </div>
          )}
        </PanelSection>

        {/* Section 2: Conflict & Impact Analysis */}
        <PanelSection
          title="Conflict & Downstream Impact"
          description="Evaluation of schedule consistency and affected downstream operations."
        >
          <div className="space-y-3 text-xs">
            {/* Resolved Conflicts */}
            <div>
              <p className="font-semibold text-neutral-300">Conflicts Resolved</p>
              {conflictsResolved.length === 0 ? (
                <p className="text-muted-foreground">No specific conflicts marked as resolved.</p>
              ) : (
                <ul className="mt-1 space-y-1">
                  {conflictsResolved.map((conf, i) => (
                    <li key={i} className="flex items-center gap-1.5 text-emerald-400">
                      <CheckCircle2 className="size-3.5 shrink-0" />
                      <span>{typeof conf === "string" ? conf : conf.title || conf.id || JSON.stringify(conf)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Created Conflicts */}
            {conflictsCreated.length > 0 && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2.5">
                <p className="font-semibold text-red-200">⚠ New Conflicts Introduced</p>
                <ul className="mt-1 space-y-1 text-red-300">
                  {conflictsCreated.map((conf, i) => (
                    <li key={i} className="flex items-center gap-1.5">
                      <AlertTriangle className="size-3.5 shrink-0" />
                      <span>{typeof conf === "string" ? conf : conf.title || conf.id || JSON.stringify(conf)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Affected Sessions */}
            {affectedSessions.length > 0 && (
              <div>
                <p className="font-semibold text-neutral-300">Affected Sessions</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {affectedSessions.map((sess, i) => (
                    <span
                      key={i}
                      className="rounded bg-secondary/80 px-2 py-0.5 font-mono text-[11px] text-neutral-300"
                    >
                      {typeof sess === "string" ? sess : sess.title || sess.id || JSON.stringify(sess)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Role Briefings Invalidated */}
            {briefingsInvalidated.length > 0 && (
              <div>
                <p className="font-semibold text-neutral-300">Role Briefings Invalidated</p>
                <p className="text-[11px] text-muted-foreground mb-1">
                  The following role briefings will be flagged as stale upon commitment:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {briefingsInvalidated.map((b, i) => (
                    <span
                      key={i}
                      className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300"
                    >
                      {typeof b === "string" ? b : b.role || JSON.stringify(b)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Risk notes */}
            {impact.notes && (
              <div className="pt-1">
                <p className="font-semibold text-neutral-300">Logistics Notes</p>
                <p className="text-muted-foreground">{String(impact.notes)}</p>
              </div>
            )}
          </div>
        </PanelSection>

        {/* Section 3: Verification & Audit Metadata */}
        <PanelSection
          title="Audit & Integrity Metadata"
          description="Authoritative EventStore transaction and baseline fingerprint data."
        >
          <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
            <MetaBlock label="Target Schedule ID" value={proposal.target_schedule_id} mono />
            <MetaBlock label="Event ID" value={proposal.event_id} mono />
            <MetaBlock label="Persisted Status" value={proposal.persisted_status} />
            <MetaBlock label="Effective Status" value={proposal.effective_status} />
            <MetaBlock label="Baseline Version" value={String(proposal.baseline_version)} mono />
            <MetaBlock label="Baseline Fingerprint" value={proposal.baseline_fingerprint} mono truncate />
            <MetaBlock label="Created At" value={formatIsoDate(proposal.created_at)} />
            <MetaBlock label="Expires At" value={formatIsoDate(proposal.expires_at)} />
            {proposal.audit_event_id && (
              <MetaBlock label="Audit Event ID" value={proposal.audit_event_id} mono />
            )}
            {proposal.created_by && (
              <MetaBlock label="Created By" value={proposal.created_by} />
            )}
          </div>
        </PanelSection>
      </div>
    </DrawerShell>
  )
}

function ProposedChangeRow({ change }: { change: ProposedChange }) {
  const beforeVal = change.before !== undefined ? String(change.before) : "—"
  const afterVal = change.after !== undefined ? String(change.after) : "—"

  return (
    <div className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between text-xs">
      <div className="space-y-0.5">
        <span className="font-mono font-semibold text-neutral-200">
          {change.field}
        </span>
        {change.reason && (
          <p className="text-[11px] text-muted-foreground">{change.reason}</p>
        )}
      </div>

      <div className="flex items-center gap-2 font-mono">
        <span className="rounded bg-red-500/10 px-2 py-0.5 text-red-300 line-through">
          {beforeVal}
        </span>
        <ArrowRight className="size-3 text-muted-foreground" />
        <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-semibold text-emerald-300">
          {afterVal}
        </span>
      </div>
    </div>
  )
}

function MetaBlock({
  label,
  value,
  mono,
  truncate,
}: {
  label: string
  value: string
  mono?: boolean
  truncate?: boolean
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-secondary/30 p-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 text-xs font-medium text-foreground",
          mono && "font-mono",
          truncate && "truncate",
        )}
        title={truncate ? value : undefined}
      >
        {value || "—"}
      </p>
    </div>
  )
}

function formatIsoDate(isoString?: string): string {
  if (!isoString) return "—"
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return isoString
  }
}
