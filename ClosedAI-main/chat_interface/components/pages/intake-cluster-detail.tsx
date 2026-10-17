"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageContainer } from "@/components/management/shared";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  ArrowRight,
  BookPlus,
  CheckCircle2,
  Clock3,
  Forward,
  ShieldAlert,
  Sparkles,
  Users,
} from "lucide-react";
import {
  DispositionPill,
  Sparkline,
  UrgencyDot,
  channelIcons,
} from "@/components/intake-bits";
import {
  channelMeta,
  dispositionMeta,
  intakeClusters,
  itemsForCluster,
  type IntakeCluster,
  type IntakeItem,
} from "@/lib/intake-data";
import { useNavigation } from "@/lib/navigation";
import { cn } from "@/lib/utils";

function ClusterPageContent({ clusterId: propClusterId }: { clusterId?: string }) {
  const params = useParams<{ clusterId?: string }>();
  const searchParams = useSearchParams();
  const nav = useNavigation();

  const targetClusterId = propClusterId || nav?.selectedClusterId || params?.clusterId || intakeClusters[0]!.id;
  const cluster = intakeClusters.find((c) => c.id === targetClusterId) || intakeClusters[0]!;

  const handleBack = (e: React.MouseEvent) => {
    if (nav?.setSelectedClusterId) {
      e.preventDefault();
      nav.setSelectedClusterId(null);
      nav.setView("intake");
    }
  };

  const selectedId = searchParams?.get("item") ?? "";
  const items = itemsForCluster(cluster.id);
  const selected = items.find((i) => i.id === selectedId) ?? items[0];
  const restricted = cluster.domain === "Restricted";

  return (
    <PageContainer>
      <div className="dream-in space-y-6">
        <Link
          href="/intake?view=clusters"
          onClick={handleBack}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5 text-primary" />
          Back to intake
        </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{cluster.label}</h1>
            {cluster.discovered && (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400">
                New pattern
              </span>
            )}
            {restricted && (
              <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-400">
                <ShieldAlert className="size-3" />
                Restricted handling
              </span>
            )}
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{cluster.blurb}</p>
        </div>

        <div className="panel flex items-center gap-5 px-4 py-3 rounded-lg border border-border bg-card/40">
          <div>
            <p className="label-caps">Open</p>
            <p className="text-xl font-semibold">
              {items.filter((i) => i.state !== "handled").length}
            </p>
          </div>
          <div>
            <p className="label-caps">7-day volume</p>
            <Sparkline values={cluster.trend} tone={cluster.discovered ? "warning" : "primary"} />
          </div>
        </div>
      </div>

      {cluster.discovered && (
        <div className="panel mt-4 flex flex-wrap items-center gap-3 border-amber-500/40 bg-amber-500/5 px-4 py-3 rounded-lg border">
          <BookPlus className="size-4 text-amber-400" />
          <p className="min-w-0 flex-1 text-sm">
            These requests keep repeating with no automation behind them. Decide once, and the
            Copilot can turn your resolution into a reusable playbook.
          </p>
          <button
            onClick={() => nav?.setView("automations")}
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 px-3 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/10"
          >
            Draft a playbook
            <ArrowRight className="size-3.5" />
          </button>
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
        <section className="panel overflow-hidden rounded-lg border border-border bg-card/40">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <p className="text-xs text-muted-foreground">{items.length} requests in this cluster</p>
            <p className="text-[11px] text-muted-foreground">Oldest at the bottom</p>
          </div>
          {[...items]
            .sort((a, b) => a.ageMinutes - b.ageMinutes)
            .map((i) => {
              const Channel = channelIcons[i.channel];
              return (
                <Link
                  key={i.id}
                  href={`/intake/${cluster.id}?item=${i.id}`}
                  className={cn(
                    "flex items-start gap-3 border-b border-border px-4 py-3 text-left transition-colors last:border-0 hover:bg-sidebar-accent/60",
                    selected?.id === i.id && "bg-sidebar-accent",
                  )}
                >
                  <div className="mt-1.5 flex items-center gap-2">
                    <UrgencyDot urgency={i.urgency} />
                    <Channel className="size-3.5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{i.subject}</p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {i.requester.name} · {i.requester.role} · {i.age} ago
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <DispositionPill disposition={i.disposition} />
                    <span className="text-[11px] text-muted-foreground">{i.due}</span>
                  </div>
                </Link>
              );
            })}
        </section>

        {selected ? <TriagePanel item={selected} cluster={cluster} /> : null}
      </div>
      </div>
    </PageContainer>
  );
}

function TriagePanel({ item, cluster }: { item: IntakeItem; cluster: IntakeCluster }) {
  const meta = dispositionMeta[item.disposition];
  const Channel = channelIcons[item.channel];
  const nav = useNavigation();
  const [action, setAction] = useState<TriageActionKind | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);

  return (
    <aside className="panel h-fit lg:sticky lg:top-20 rounded-lg border border-border bg-card/40">
      <div className="border-b border-border px-4 py-3">
        <p className="font-mono text-[11px] text-muted-foreground">{item.id}</p>
        <p className="mt-1 text-sm font-medium">{item.subject}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <DispositionPill disposition={item.disposition} />
          <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Channel className="size-3.5" />
            {channelMeta[item.channel]}
          </span>
        </div>
      </div>

      <div className="space-y-4 px-4 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-full bg-sidebar-accent text-xs font-semibold">
            {item.requester.initials}
          </div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-xs font-medium">{item.requester.name}</p>
            <p className="truncate text-[11px] text-muted-foreground">{item.requester.role}</p>
          </div>
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Clock3 className="size-3" />
            {item.due}
          </span>
        </div>

        <blockquote className="rounded-md border border-border bg-background px-3 py-2.5 text-xs text-muted-foreground">
          {item.snippet}
        </blockquote>

        <div>
          <p className="label-caps">Copilot read</p>
          <p className="mt-1.5 text-xs">{item.suggestion}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full",
                  item.confidence >= 0.8
                    ? "bg-emerald-400"
                    : item.confidence >= 0.5
                      ? "bg-primary"
                      : "bg-amber-400",
                )}
                style={{ width: `${Math.round(item.confidence * 100)}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">
              {Math.round(item.confidence * 100)}% confidence
            </span>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{meta.blurb}</p>
        </div>

        <div className="space-y-2">
          <p className="label-caps">Triage</p>
          {item.linkedWorkId ? (
            <button
              onClick={() => nav?.navigateToWorkDetail(item.linkedWorkId!)}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <ArrowRight className="size-4" />
              Open in work queue · {item.linkedWorkId}
            </button>
          ) : (
            <button
              onClick={() => nav?.setView("chat")}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <Sparkles className="size-4" />
              {item.disposition === "human" ? "Answer with the Copilot" : "Release to the Copilot"}
            </button>
          )}
          <div className="grid grid-cols-3 gap-2">
            <TriageAction icon={Forward} label="Route" onClick={() => setAction("route")} />
            <TriageAction icon={Users} label="Group" onClick={() => setAction("group")} />
            <TriageAction icon={CheckCircle2} label="Close" onClick={() => setAction("close")} />
          </div>
          {outcome && (
            <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-400">
              {outcome}
            </p>
          )}
        </div>
      </div>

      <TriageActionDialog
        kind={action}
        item={item}
        cluster={cluster}
        onClose={() => setAction(null)}
        onDone={(summary) => {
          setOutcome(summary);
          setAction(null);
          toast.success(summary);
        }}
      />
    </aside>
  );
}

function TriageAction({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Forward;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-1 rounded-md border border-border px-2 py-2 text-[11px] text-muted-foreground hover:border-border/80 hover:text-foreground"
    >
      <Icon className="size-3.5" />
      {label}
    </button>
  );
}

type TriageActionKind = "route" | "group" | "close";

const routeTargets = [
  { id: "hr-ops", label: "HR Operations", hint: "Letters, records, day-to-day requests" },
  { id: "payroll", label: "Payroll", hint: "Pay runs, deductions, corrections" },
  { id: "people-partner", label: "People Partner", hint: "Manager and employee coaching" },
  { id: "legal", label: "Legal & Compliance", hint: "Restricted or sensitive matters" },
  { id: "mobility", label: "Global Mobility", hint: "Relocation, visas, cross-border" },
];

const closeReasons = [
  { id: "resolved", label: "Resolved — answered directly" },
  { id: "duplicate", label: "Duplicate of another request" },
  { id: "no-action", label: "No action needed" },
  { id: "withdrawn", label: "Requester withdrew it" },
];

function TriageActionDialog({
  kind,
  item,
  cluster,
  onClose,
  onDone,
}: {
  kind: TriageActionKind | null;
  item: IntakeItem;
  cluster: IntakeCluster;
  onClose: () => void;
  onDone: (summary: string) => void;
}) {
  const [target, setTarget] = useState(routeTargets[0]!.id);
  const [groupTarget, setGroupTarget] = useState(cluster.id);
  const [newCluster, setNewCluster] = useState("");
  const [reason, setReason] = useState(closeReasons[0]!.id);
  const [note, setNote] = useState("");

  const submit = () => {
    if (kind === "route") {
      const t = routeTargets.find((r) => r.id === target)!;
      onDone(`${item.id} routed to ${t.label}.`);
    } else if (kind === "group") {
      const name =
        groupTarget === "__new"
          ? newCluster.trim() || "New cluster"
          : (intakeClusters.find((c) => c.id === groupTarget)?.label ?? "cluster");
      onDone(`${item.id} grouped into "${name}".`);
    } else if (kind === "close") {
      const r = closeReasons.find((c) => c.id === reason)!;
      onDone(`${item.id} closed — ${r.label.toLowerCase()}.`);
    }
    setNote("");
  };

  return (
    <Dialog open={kind !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {kind === "route"
              ? "Route this request"
              : kind === "group"
                ? "Group this request"
                : "Close this request"}
          </DialogTitle>
          <DialogDescription>
            {kind === "route"
              ? "Hand it to the team that owns this kind of work. The requester keeps the same thread."
              : kind === "group"
                ? "Move it into the cluster it really belongs to, or start a new pattern the Copilot should watch."
                : "Record why this is done so the Copilot learns when no work is needed."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <p className="font-mono text-[11px] text-muted-foreground">{item.id}</p>
          <p className="text-sm font-medium">{item.subject}</p>
        </div>

        {kind === "route" && (
          <div className="space-y-1.5">
            {routeTargets.map((t) => (
              <label
                key={t.id}
                className={cn(
                  "flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2 text-left",
                  target === t.id ? "border-primary bg-primary/5" : "border-border",
                )}
              >
                <input
                  type="radio"
                  name="route-target"
                  className="mt-1"
                  checked={target === t.id}
                  onChange={() => setTarget(t.id)}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium">{t.label}</span>
                  <span className="block text-[11px] text-muted-foreground">{t.hint}</span>
                </span>
              </label>
            ))}
          </div>
        )}

        {kind === "group" && (
          <div className="space-y-2">
            <select
              value={groupTarget}
              onChange={(e) => setGroupTarget(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none"
            >
              {intakeClusters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                  {c.id === cluster.id ? " (current)" : ""}
                </option>
              ))}
              <option value="__new">+ Start a new cluster…</option>
            </select>
            {groupTarget === "__new" && (
              <input
                value={newCluster}
                onChange={(e) => setNewCluster(e.target.value)}
                placeholder="Name the new pattern, e.g. Lisbon relocations"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
              />
            )}
          </div>
        )}

        {kind === "close" && (
          <div className="space-y-1.5">
            {closeReasons.map((r) => (
              <label
                key={r.id}
                className={cn(
                  "flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-sm",
                  reason === r.id ? "border-primary bg-primary/5" : "border-border",
                )}
              >
                <input
                  type="radio"
                  name="close-reason"
                  checked={reason === r.id}
                  onChange={() => setReason(r.id)}
                />
                {r.label}
              </label>
            ))}
          </div>
        )}

        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          placeholder="Add a note for the audit trail (optional)"
          className="w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
        />

        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-3 py-2 text-sm hover:bg-sidebar-accent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            {kind === "route" ? "Route request" : kind === "group" ? "Move request" : "Close request"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function IntakeClusterDetail({ clusterId }: { clusterId?: string }) {
  return (
    <Suspense>
      <ClusterPageContent clusterId={clusterId} />
    </Suspense>
  );
}
