import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { History } from "lucide-react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Empty, OriginPill, PageHeader, Pill, StatusPill } from "@/components/ui-bits";
import { forEvent, useAppState, useCurrentEvent } from "@/lib/store";

export const Route = createFileRoute("/_workspace/activity")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Activity — Event Operations Agent" },
      { name: "description", content: "Audit trail of agent proposals, approvals, changes and blocked actions." },
      { property: "og:title", content: "Activity — Event Operations Agent" },
      { property: "og:description", content: "Audit trail of agent proposals, approvals, changes and blocked actions." },
    ],
  }),
  component: Activity,
});

function Activity() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const [f, setF] = useState<string>("all");
  const items = forEvent(s.activity, ev.id).filter((a) => f === "all" || a.kind === f || a.actor === f);
  return (
    <>
      <PageHeader title="Activity" description="What the agent proposed, what changed, who approved it, and whether data was live or simulated." />
      <div className="mb-3 flex gap-1">
        {["all", "agent", "organizer", "proposed", "approved", "rejected", "executed", "blocked", "failed"].map((k) => (
          <Button key={k} size="sm" variant={f === k ? "secondary" : "ghost"} className="h-7 text-xs" onClick={() => setF(k)}>{k}</Button>
        ))}
      </div>
      {items.length === 0 ? <Empty icon={History} title="No activity" /> : (
        <ol className="overflow-hidden rounded-xl border bg-card">
          {items.map((a) => (
            <li key={a.id} className="flex items-start gap-3 border-b px-4 py-2.5 text-[13px] last:border-0">
              <span className="w-28 shrink-0 font-mono text-[11px] text-muted-foreground">{format(new Date(a.at), "MMM d HH:mm:ss")}</span>
              <span className="w-20 shrink-0"><StatusPill status={a.kind} /></span>
              <span className="flex-1">{a.summary}{a.sources?.length ? <span className="ml-1 text-xs text-muted-foreground">· sources: {a.sources.join(", ")}</span> : null}</span>
              <Pill>{a.actor}</Pill>
              <OriginPill origin={a.origin} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
