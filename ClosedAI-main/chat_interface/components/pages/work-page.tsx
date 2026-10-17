"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Filter, Inbox, Plus } from "lucide-react";
import { WorkRow } from "@/components/work-bits";
import { statusMeta, workItems, type WorkStatus } from "@/lib/hr-data";
import { useNavigation } from "@/lib/navigation";
import WorkDetail from "./work-detail";
import { PageContainer, PageHeader } from "@/components/management/shared";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type StatusFilter = WorkStatus | "all";

const filters: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All work" },
  { key: "needs_approval", label: statusMeta.needs_approval.label },
  { key: "running", label: statusMeta.running.label },
  { key: "queued", label: statusMeta.queued.label },
  { key: "blocked", label: statusMeta.blocked.label },
  { key: "completed", label: statusMeta.completed.label },
];

function WorkQueueContent() {
  const searchParams = useSearchParams();
  const nav = useNavigation();

  if (nav?.selectedWorkId) {
    return <WorkDetail workId={nav.selectedWorkId} />;
  }

  const raw = searchParams?.get("status");
  const valid = ["needs_approval", "running", "queued", "blocked", "completed"];
  const status = (typeof raw === "string" && valid.includes(raw) ? raw : "all") as StatusFilter;
  const items = status === "all" ? workItems : workItems.filter((w) => w.status === status);

  return (
    <PageContainer>
      <PageHeader
        title="Work queue"
        icon={Inbox}
        description="Work created by other HR systems, plus ad hoc requests, executed by the Copilot."
        action={
          <Button
            onClick={() => nav?.setView("chat")}
            className="inline-flex items-center gap-2"
          >
            <Plus className="size-4" />
            New task
          </Button>
        }
      />

      <div className="dream-in">
        <div className="mb-4 flex flex-wrap gap-1.5">
          <Filter className="size-3.5 self-center text-muted-foreground mr-1" />
          {filters.map((f) => (
            <Link
              key={f.key}
              href={f.key === "all" ? "/work" : `/work?status=${f.key}`}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                status === f.key
                  ? "border-sky-500/40 bg-sky-500/10 text-sky-400 font-semibold"
                  : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              {f.label}
            </Link>
          ))}
        </div>

        <div className="overflow-hidden rounded-xl border border-border/60 bg-card/40">
          {items.length ? (
            items.map((item) => <WorkRow key={item.id} item={item} />)
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              No work items match this filter.
            </p>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function WorkPage() {
  return (
    <Suspense>
      <WorkQueueContent />
    </Suspense>
  );
}
