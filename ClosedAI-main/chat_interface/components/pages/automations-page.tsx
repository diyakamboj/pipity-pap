"use client";

import { useState } from "react";
import { Pause, Play, Plus, Sparkles, Workflow, X } from "lucide-react";
import { sourceIcons } from "@/components/work-bits";
import { automations, sourceMeta } from "@/lib/hr-data";
import { useNavigation } from "@/lib/navigation";
import { PageContainer, PageHeader } from "@/components/management/shared";
import { cn } from "@/lib/utils";

const statusTone = {
  live: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  draft: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  paused: "bg-secondary/60 text-muted-foreground border-border/60",
};

export default function AutomationsPage() {
  const [creating, setCreating] = useState(false);
  const nav = useNavigation();

  return (
    <PageContainer>
      <PageHeader
        title="Automations"
        icon={Workflow}
        description="Standardised HR processes the Copilot can execute end to end. Anything not here still gets done through chat."
        action={
          <button
            onClick={() => setCreating(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary/60 px-3 py-2 text-sm font-medium text-foreground transition-colors hover:border-border hover:bg-secondary"
          >
            <Plus className="size-4" />
            Create automation
          </button>
        }
      />

      <div className="dream-in grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {automations.map((a) => {
          const Icon = sourceIcons[a.source];
          return (
            <article
              key={a.id}
              className="flex flex-col rounded-xl border border-border/60 bg-card/40 p-5 transition-colors duration-150 hover:border-border hover:bg-card/70"
            >
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-secondary/60">
                  <Icon className="size-4 text-muted-foreground" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-[15px] font-semibold text-foreground">{a.name}</h2>
                  <p className="text-[11px] text-muted-foreground">
                    {a.trigger} · {sourceMeta[a.source].system}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    statusTone[a.status],
                  )}
                >
                  {a.status}
                </span>
              </div>

              <p className="mt-3 flex-1 text-[13px] leading-relaxed text-muted-foreground">
                {a.description}
              </p>

              <dl className="mt-4 grid grid-cols-4 gap-2 border-t border-border/60 pt-3 text-center">
                {[
                  { k: "Steps", v: a.steps },
                  { k: "Approvals", v: a.approvals },
                  { k: "Runs 30d", v: a.runs30d },
                  { k: "Clean", v: a.successRate ? `${a.successRate}%` : "—" },
                ].map((s) => (
                  <div key={s.k}>
                    <dd className="text-sm font-semibold text-foreground">{s.v}</dd>
                    <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {s.k}
                    </dt>
                  </div>
                ))}
              </dl>

              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={() => nav?.setView("chat")}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground"
                >
                  <Play className="size-3" />
                  Run
                </button>
                <button
                  className="rounded-lg border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground"
                  aria-label={a.status === "paused" ? "Resume automation" : "Pause automation"}
                >
                  {a.status === "paused" ? (
                    <Play className="size-3.5" />
                  ) : (
                    <Pause className="size-3.5" />
                  )}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {creating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-border/60 bg-card p-5 shadow-2xl">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 size-4 text-primary" />
              <div className="flex-1">
                <h2 className="text-sm font-semibold text-foreground">Create automation</h2>
                <p className="text-xs text-muted-foreground">
                  Describe the process. The Copilot drafts the steps, picks the source system and
                  marks where a human must approve.
                </p>
              </div>
              <button
                onClick={() => setCreating(false)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <textarea
              rows={4}
              placeholder="e.g. When a badge reissue ticket arrives, verify identity, open a facilities request and notify the employee."
              className="mt-4 w-full resize-none rounded-xl border border-border/60 bg-secondary/40 p-3 text-sm outline-none placeholder:text-muted-foreground focus:border-border"
            />
            <p className="mt-2 text-[11px] text-muted-foreground">
              Demo only — drafting isn't wired up yet.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setCreating(false)}
                className="rounded-lg border border-border/60 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground"
              >
                Cancel
              </button>
              <button className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90">
                Draft steps
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
