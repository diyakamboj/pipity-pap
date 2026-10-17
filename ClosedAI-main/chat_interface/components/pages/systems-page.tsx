"use client";

import { useState } from "react";
import { Link2, Plus, X } from "lucide-react";
import { connectedSystems, type ConnectedSystem } from "@/lib/hr-data";
import { PageContainer, PageHeader } from "@/components/management/shared";
import { cn } from "@/lib/utils";

const statusTone: Record<ConnectedSystem["status"], string> = {
  live: "text-emerald-400",
  degraded: "text-amber-400",
};

const statusDot: Record<ConnectedSystem["status"], string> = {
  live: "bg-emerald-400",
  degraded: "bg-amber-400 animate-pulse",
};

export default function SystemsPage() {
  const [adding, setAdding] = useState(false);

  return (
    <PageContainer>
      <PageHeader
        title="Connected systems"
        icon={Link2}
        description="HR platforms and data sources the Copilot reads from and writes to. Each connection is scoped to the minimum permissions needed."
        action={
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/60 px-3 py-2 text-sm font-medium text-foreground transition-colors hover:border-border hover:bg-secondary"
          >
            <Plus className="size-4" />
            Add connection
          </button>
        }
      />

      <div className="dream-in grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {connectedSystems.map((s) => (
          <article
            key={s.name}
            className="flex flex-col rounded-xl border border-border/60 bg-card/40 p-5 transition-colors duration-150 hover:border-border hover:bg-card/70"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-secondary/60">
                <Link2 className="size-4 text-muted-foreground" />
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-[15px] font-semibold text-foreground">{s.name}</h2>
                <p className="text-[11px] text-muted-foreground">{s.kind}</p>
              </div>
              <span className={cn("flex items-center gap-1.5 text-[11px] font-medium", statusTone[s.status])}>
                <span className={cn("size-1.5 rounded-full", statusDot[s.status])} />
                {s.status}
              </span>
            </div>

            <dl className="mt-4 grid grid-cols-1 gap-y-1.5 border-t border-border/60 pt-3 text-[12px] text-muted-foreground">
              <div className="flex justify-between">
                <dt>Inbound</dt>
                <dd className="font-medium text-foreground">{s.inbound}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Last sync</dt>
                <dd className="font-medium text-foreground">{s.lastSync}</dd>
              </div>
            </dl>

            <div className="mt-4 flex items-center gap-2">
              <button className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground">
                Configure
              </button>
              <button className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground">
                Test connection
              </button>
            </div>
          </article>
        ))}
      </div>

      {adding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-border/60 bg-card p-5 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Add connection</h2>
                <p className="text-xs text-muted-foreground">
                  Connect an HR platform or data source.
                </p>
              </div>
              <button
                onClick={() => setAdding(false)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Demo only — connection wizard not wired up yet.
            </p>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setAdding(false)}
                className="rounded-lg border border-border/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
