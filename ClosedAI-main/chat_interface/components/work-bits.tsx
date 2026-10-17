"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Sparkles,
  TicketCheck,
  UserPlus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  sourceMeta,
  statusMeta,
  type WorkItem,
  type WorkSource,
  type WorkStatus,
} from "@/lib/hr-data";
import { useNavigation } from "@/lib/navigation";

export const sourceIcons: Record<WorkSource, typeof TicketCheck> = {
  ticketing: TicketCheck,
  recruiting: UserPlus,
  attendance: Clock,
  leave: CalendarClock,
  documents: FileText,
  adhoc: Sparkles,
};

const toneClasses: Record<string, string> = {
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  primary: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  muted: "bg-slate-800/80 text-slate-300 border-slate-700",
  destructive: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

export function StatusPill({ status, className }: { status: WorkStatus; className?: string }) {
  const meta = statusMeta[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium shadow-sm",
        toneClasses[meta.tone],
        className,
      )}
    >
      {status === "running" ? (
        <Loader2 className="size-3 animate-spin text-sky-400" />
      ) : status === "needs_approval" ? (
        <AlertTriangle className="size-3 text-amber-400" />
      ) : status === "completed" ? (
        <CheckCircle2 className="size-3 text-emerald-400" />
      ) : status === "blocked" ? (
        <AlertTriangle className="size-3 text-rose-400" />
      ) : (
        <span className="size-1.5 rounded-full bg-slate-400" />
      )}
      {meta.label}
    </span>
  );
}

export function SourceTag({ source }: { source: WorkSource }) {
  const Icon = sourceIcons[source];
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
      <Icon className="size-3.5 text-sky-400/80" />
      {sourceMeta[source].label}
      <span className="text-border-strong">·</span>
      <span className="text-muted-foreground/80">{sourceMeta[source].system}</span>
    </span>
  );
}

export function WorkRow({ item }: { item: WorkItem }) {
  const nav = useNavigation();

  const handleClick = (e: React.MouseEvent) => {
    if (nav?.navigateToWorkDetail) {
      e.preventDefault();
      nav.navigateToWorkDetail(item.id);
    }
  };

  return (
    <Link
      href={`/work/${item.id}`}
      onClick={handleClick}
      className="group flex flex-col gap-2 border-b border-border px-4 py-3 transition-colors last:border-0 hover:bg-sidebar-accent/60 md:flex-row md:items-center md:gap-4"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-medium text-sky-400/90">{item.id}</span>
          {item.priority !== "normal" && (
            <span
              className={cn(
                "rounded px-1.5 py-0.2 text-[10px] font-semibold uppercase tracking-wide border",
                item.priority === "urgent"
                  ? "bg-rose-500/20 text-rose-400 border-rose-500/30"
                  : "bg-amber-500/20 text-amber-400 border-amber-500/30",
              )}
            >
              {item.priority}
            </span>
          )}
        </div>
        <p className="truncate text-sm font-medium text-foreground group-hover:text-primary transition-colors">
          {item.title}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <SourceTag source={item.source} />
          <span className="text-[11px] text-muted-foreground">{item.externalRef}</span>
        </div>
      </div>

      <div className="flex items-center gap-4 md:w-[420px] md:justify-end">
        <div className="hidden text-right lg:block">
          <p className="text-xs text-foreground">{item.subject.name}</p>
          <p className="text-[11px] text-muted-foreground">{item.subject.role}</p>
        </div>
        <div className="hidden w-28 sm:block">
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-300",
                item.status === "blocked"
                  ? "bg-rose-500"
                  : item.status === "completed"
                    ? "bg-emerald-400"
                    : item.status === "needs_approval"
                      ? "bg-amber-400"
                      : "bg-sky-400",
              )}
              style={{ width: `${item.progress}%` }}
            />
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">{item.sla}</p>
        </div>
        <StatusPill status={item.status} />
      </div>
    </Link>
  );
}
