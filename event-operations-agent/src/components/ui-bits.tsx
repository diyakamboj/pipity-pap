import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Origin } from "@/lib/types";
import { FlaskConical, User, Globe, Cog } from "lucide-react";

const TONES: Record<string, string> = {
  neutral: "bg-muted text-muted-foreground border-border",
  violet: "bg-info-soft text-accent-foreground border-transparent",
  green: "bg-success-soft text-success border-transparent",
  amber: "bg-warning-soft text-warning border-transparent",
  red: "bg-danger-soft text-destructive border-transparent",
};

const STATUS_TONE: Record<string, keyof typeof TONES> = {
  required: "violet", optional: "neutral", declined: "neutral", unresolved: "amber",
  candidate: "neutral", drafted: "violet", awaiting_approval: "amber", sent_simulated: "violet", replied: "green", committed: "green",
  draft: "neutral", pending_approval: "amber", approved: "green", rejected: "red", pending: "amber", executed: "green",
  estimate: "neutral", quote_received: "violet", selected: "amber", confirmed: "green",
  todo: "neutral", in_progress: "violet", blocked: "red", done: "green",
  match: "green", missing: "amber", mismatch: "red",
  proposed: "violet", changed: "neutral", created: "neutral", failed: "red",
};

export function Pill({ tone = "neutral", children, className }: { tone?: keyof typeof TONES; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium", TONES[tone], className)}>
      {children}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const label = status === "sent_simulated" ? "sent (simulated)" : status.replace(/_/g, " ");
  return <Pill tone={STATUS_TONE[status] ?? "neutral"}>{label}</Pill>;
}

export function OriginPill({ origin }: { origin: Origin }) {
  const map = {
    simulated: { icon: FlaskConical, label: "Simulated", tone: "amber" as const },
    organizer: { icon: User, label: "Organizer", tone: "neutral" as const },
    live: { icon: Globe, label: "Live source", tone: "green" as const },
    system: { icon: Cog, label: "System", tone: "neutral" as const },
  }[origin];
  const I = map.icon;
  return (
    <Pill tone={map.tone}>
      <I className="h-3 w-3" />
      {map.label}
    </Pill>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border bg-card shadow-[var(--shadow-card)]", className)}>
      {title && (
        <header className="flex items-center justify-between border-b px-4 py-2.5">
          <h2 className="text-[13px] font-semibold">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Empty({ icon: I, title, body, action }: { icon: React.ComponentType<{ className?: string }>; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-10 text-center">
      <I className="h-5 w-5 text-muted-foreground" />
      <p className="mt-2 text-sm font-medium">{title}</p>
      {body && <p className="mt-1 max-w-sm text-xs text-muted-foreground">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Unknowns({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((u) => (
        <Pill key={u} tone="amber">? {u}</Pill>
      ))}
    </div>
  );
}
