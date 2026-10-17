"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { LayoutGrid, ListFilter, Radar, ShieldCheck, Zap } from "lucide-react";
import { ClusterCard, IntakeRow } from "@/components/intake-bits";
import {
  dispositionMeta,
  intakeClusters,
  intakeItems,
  intakeStats,
  type IntakeDisposition,
} from "@/lib/intake-data";
import { useNavigation } from "@/lib/navigation";
import IntakeClusterDetail from "./intake-cluster-detail";
import { PageContainer, PageHeader } from "@/components/management/shared";
import { cn } from "@/lib/utils";

type View = "decide" | "clusters" | "stream";

const views: { key: View; label: string; icon: typeof LayoutGrid }[] = [
  { key: "decide", label: "By decision", icon: Zap },
  { key: "clusters", label: "By cluster", icon: LayoutGrid },
  { key: "stream", label: "Full stream", icon: ListFilter },
];

const lanes: { key: IntakeDisposition; accent: string }[] = [
  { key: "human", accent: "border-t-amber-500/60" },
  { key: "assist", accent: "border-t-sky-500/60" },
  { key: "auto", accent: "border-t-emerald-500/60" },
];

function IntakePageContent() {
  const searchParams = useSearchParams();
  const nav = useNavigation();

  if (nav?.selectedClusterId) {
    return <IntakeClusterDetail clusterId={nav.selectedClusterId} />;
  }

  const raw = searchParams?.get("view");
  const valid = ["decide", "clusters", "stream"];
  const view = (typeof raw === "string" && valid.includes(raw) ? raw : "decide") as View;
  const open = intakeItems.filter((i) => i.state !== "handled");

  return (
    <PageContainer>
      <PageHeader
        title="Intake"
        icon={Radar}
        description="Everything arriving for HR, from every system and every channel. Sorted by the decision it needs from you — not by when it landed."
        action={
          <div className="flex items-center gap-1 rounded-xl border border-border/60 bg-card/40 p-1">
            {views.map((v) => (
              <Link
                key={v.key}
                href={`/intake?view=${v.key}`}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground",
                  view === v.key && "bg-secondary/60 text-foreground font-semibold",
                )}
              >
                <v.icon className="size-3.5" />
                {v.label}
              </Link>
            ))}
          </div>
        }
      />

      <div className="dream-in">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Arrived today" value={String(intakeStats.arrivedToday)} sub="all channels" />
          <Stat
            label="Absorbed by Copilot"
            value={String(intakeStats.autoAbsorbed)}
            sub="no human touch"
            tone="success"
          />
          <Stat
            label="Open for HR"
            value={String(intakeStats.open)}
            sub={`${intakeStats.needsJudgement} need your judgement`}
            tone="warning"
          />
          <Stat
            label="New patterns"
            value={String(intakeStats.newPatterns)}
            sub="clusters with no playbook"
            tone="warning"
          />
        </div>

        {view === "decide" && (
          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {lanes.map((lane) => {
              const meta = dispositionMeta[lane.key];
              const items = open.filter((i) => i.disposition === lane.key);
              return (
                <section
                  key={lane.key}
                  className={cn(
                    "overflow-hidden rounded-xl border border-t-2 border-border/60 bg-card/40",
                    lane.accent,
                  )}
                >
                  <div className="border-b border-border/60 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold">{meta.label}</p>
                      <span className="rounded-md border border-border/60 bg-secondary/60 px-2 py-0.5 text-xs font-mono font-medium text-muted-foreground">
                        {items.length}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{meta.blurb}</p>
                  </div>
                  {items.length ? (
                    items.map((item) => <IntakeRow key={item.id} item={item} />)
                  ) : (
                    <p className="px-4 py-8 text-center text-xs text-muted-foreground">
                      Nothing waiting here.
                    </p>
                  )}
                </section>
              );
            })}
          </div>
        )}

        {view === "clusters" && (
          <>
            <div className="mt-6 flex items-center gap-2">
              <Radar className="size-4 text-amber-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Emerging — no playbook yet</h2>
              <p className="text-xs text-muted-foreground">
                Grouped automatically from requests that didn&apos;t fit an existing category.
              </p>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {intakeClusters
                .filter((c) => c.discovered)
                .map((c) => (
                  <ClusterCard
                    key={c.id}
                    cluster={c}
                    count={open.filter((i) => i.clusterId === c.id).length}
                  />
                ))}
            </div>

            <div className="mt-6 flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Known streams</h2>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {intakeClusters
                .filter((c) => !c.discovered)
                .map((c) => (
                  <ClusterCard
                    key={c.id}
                    cluster={c}
                    count={open.filter((i) => i.clusterId === c.id).length}
                  />
                ))}
            </div>
          </>
        )}

        {view === "stream" && (
          <div className="mt-6 overflow-hidden rounded-xl border border-border/60 bg-card/40">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
              <p className="text-xs font-medium text-muted-foreground">
                Newest first · every channel · {intakeItems.length} items
              </p>
              <p className="text-[11px] text-muted-foreground">Age</p>
            </div>
            {[...intakeItems]
              .sort((a, b) => a.ageMinutes - b.ageMinutes)
              .map((item) => (
                <IntakeRow key={item.id} item={item} dense />
              ))}
          </div>
        )}
      </div>
    </PageContainer>
  );
}

function Stat({
  label,
  value,
  sub,
  tone = "muted",
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "muted" | "success" | "warning";
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:border-border hover:bg-card/70">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">{label}</p>
      <p
        className={cn(
          "mt-1.5 text-2xl font-semibold",
          tone === "success" && "text-emerald-400",
          tone === "warning" && "text-amber-400",
          tone === "muted" && "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}

export default function IntakePage() {
  return (
    <Suspense>
      <IntakePageContent />
    </Suspense>
  );
}
