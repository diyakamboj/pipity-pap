import { createFileRoute, Link } from "@tanstack/react-router";
import { forEvent, money, useAppState, useCurrentEvent } from "@/lib/store";
import { Panel, PageHeader, StatusPill, Pill } from "@/components/ui-bits";
import { Progress } from "@/components/ui/progress";
import { ShieldCheck, Mail, HelpCircle, Clock, ArrowUpRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDistanceToNow } from "date-fns";
import { EventProfile } from "@/components/EventProfile";

export const Route = createFileRoute("/_workspace/")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Overview — Event Operations Agent" },
      { name: "description", content: "Command center for your event: approvals, tasks, outreach and vendors in one place." },
      { property: "og:title", content: "Event Operations Agent" },
      { property: "og:description", content: "One AI workspace for event outreach, vendors and logistics." },
    ],
  }),
  component: Overview,
});

function Overview() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const reqs = forEvent(s.requirements, ev.id);
  const tasks = forEvent(s.tasks, ev.id);
  const contacts = forEvent(s.contacts, ev.id);
  const vendors = forEvent(s.vendors, ev.id);
  const approvals = forEvent(s.approvals, ev.id).filter((a) => a.status === "pending");
  const activity = forEvent(s.activity, ev.id).slice(0, 6);
  const schedule = forEvent(s.schedule, ev.id).sort((a, b) => a.start.localeCompare(b.start));
  const done = tasks.filter((t) => t.status === "done").length;
  const confirmed = vendors.filter((v) => v.status === "confirmed").length + contacts.filter((c) => c.status === "committed").length + schedule.filter((x) => x.confirmed).length;
  const pendingDecisions = approvals.length + reqs.filter((r) => r.status === "unresolved").length;
  const waiting = contacts.filter((c) => c.status === "sent_simulated");
  const unresolved = reqs.filter((r) => r.status === "unresolved");
  const deadlines = tasks.filter((t) => t.status !== "done").sort((a, b) => a.due.localeCompare(b.due)).slice(0, 5);
  const committedSpend = vendors.filter((v) => v.status === "selected" || v.status === "confirmed").reduce((sum, v) => sum + (v.unitPrice ?? 0) * ev.attendees + (v.fees ?? 0), 0);

  return (
    <>
      <PageHeader title="Overview" description="Everything that needs attention for this event, computed from live workspace records." />
      <div className="grid grid-cols-4 gap-3">
        <Stat to="/logistics" label="Plan progress" value={tasks.length ? `${Math.round((done / tasks.length) * 100)}%` : "—"} sub={`${done}/${tasks.length} tasks done`} progress={tasks.length ? (done / tasks.length) * 100 : 0} />
        <Stat to="/approvals" label="Confirmed vs pending" value={`${confirmed} / ${pendingDecisions}`} sub="arrangements / decisions" />
        <Stat to="/outreach" label="Outreach" value={String(contacts.length)} sub={`${contacts.filter((c) => c.status === "replied" || c.status === "committed").length} replied · ${waiting.length} waiting`} />
        <Stat to="/vendors" label="Selected spend (est.)" value={money(committedSpend, ev.currency)} sub={`of ${money(ev.budget, ev.currency)} budget`} />
      </div>

      <div className="mt-5 grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-5">
          <Panel title="Work queue">
            <div className="grid grid-cols-2 gap-4">
              <Queue icon={ShieldCheck} title="Needs your approval" to="/approvals" items={approvals.map((a) => ({ id: a.id, label: a.title, meta: a.target }))} />
              <Queue icon={Mail} title="Waiting for a reply" to="/outreach" items={waiting.map((c) => ({ id: c.id, label: c.name, meta: c.kind }))} />
              <Queue icon={HelpCircle} title="Missing information" to="/agent" items={unresolved.map((r) => ({ id: r.id, label: r.question ?? r.title, meta: r.category }))} />
              <Queue icon={Clock} title="Upcoming deadlines" to="/logistics" items={deadlines.map((t) => ({ id: t.id, label: t.title, meta: t.due + (t.owner ? "" : " · unassigned") }))} />
            </div>
          </Panel>
          <div className="grid grid-cols-2 gap-5">
            <Panel title="Vendor requirements" action={<Link to="/vendors" className="text-xs text-muted-foreground hover:text-foreground">Open</Link>}>
              {reqs.length === 0 ? <p className="text-xs text-muted-foreground">No requirements yet.</p> : (
                <ul className="space-y-2">{reqs.slice(0, 6).map((r) => {
                  const v = vendors.filter((x) => x.category === r.category);
                  return <li key={r.id} className="flex items-center justify-between gap-2 text-[13px]"><span className="truncate">{r.title}</span><span className="flex shrink-0 gap-1"><StatusPill status={r.status} />{v.length > 0 && <Pill>{v.length} option{v.length > 1 ? "s" : ""}</Pill>}</span></li>;
                })}</ul>
              )}
            </Panel>
            <Panel title="Outreach status" action={<Link to="/outreach" className="text-xs text-muted-foreground hover:text-foreground">Open</Link>}>
              {contacts.length === 0 ? <p className="text-xs text-muted-foreground">No contacts yet.</p> : (
                <ul className="space-y-2">{contacts.map((c) => <li key={c.id} className="flex items-center justify-between gap-2 text-[13px]"><span className="truncate">{c.name} <span className="text-muted-foreground">· {c.kind}</span></span><StatusPill status={c.status} /></li>)}</ul>
              )}
            </Panel>
          </div>
        </div>
        <div className="space-y-5">
          <Panel title="Event timeline" action={<Link to="/logistics" className="text-xs text-muted-foreground hover:text-foreground">Run of show</Link>}>
            {schedule.length === 0 ? <p className="text-xs text-muted-foreground">No schedule yet. Ask the agent to build the setup plan.</p> : (
              <ol className="space-y-2.5">{schedule.map((x) => (
                <li key={x.id} className="flex gap-3 text-[13px]"><span className="w-11 shrink-0 font-mono text-xs text-muted-foreground">{x.start}</span><span className="flex-1">{x.title}</span>{x.confirmed ? <Pill tone="green">confirmed</Pill> : <Pill>proposed</Pill>}</li>
              ))}</ol>
            )}
          </Panel>
          <Panel title="Recent agent activity" action={<Link to="/activity" className="text-xs text-muted-foreground hover:text-foreground">All</Link>}>
            <ul className="space-y-3">{activity.map((a) => (
              <li key={a.id} className="text-[13px]"><div className="leading-snug">{a.summary}</div><div className="mt-0.5 text-[11px] text-muted-foreground">{a.actor} · {formatDistanceToNow(new Date(a.at))} ago</div></li>
            ))}</ul>
          </Panel>
          <Button variant="outline" className="w-full" asChild><Link to="/agent" search={{ q: "What are we missing for this event?" }}><Sparkles className="h-4 w-4" />Ask what we're missing</Link></Button>
        </div>
      </div>
      <div className="mt-5"><EventProfile /></div>
    </>
  );
}

function Stat({ to, label, value, sub, progress }: { to: "/logistics" | "/approvals" | "/outreach" | "/vendors"; label: string; value: string; sub: string; progress?: number }) {
  return (
    <Link to={to} className="group rounded-xl border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:border-primary/40">
      <div className="flex items-center justify-between text-xs text-muted-foreground">{label}<ArrowUpRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" /></div>
      <div className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>
      {progress != null && <Progress value={progress} className="mt-3 h-1" />}
    </Link>
  );
}

function Queue({ icon: I, title, to, items }: { icon: React.ComponentType<{ className?: string }>; title: string; to: "/approvals" | "/outreach" | "/agent" | "/logistics"; items: { id: string; label: string; meta: string }[] }) {
  return (
    <Link to={to} className="block rounded-lg border p-3 transition-colors hover:bg-muted/50">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium"><I className="h-3.5 w-3.5 text-primary" />{title}<span className="ml-auto tabular-nums text-muted-foreground">{items.length}</span></div>
      {items.length === 0 ? <p className="text-xs text-muted-foreground">Nothing here.</p> : (
        <ul className="space-y-1">{items.slice(0, 3).map((i) => <li key={i.id} className="truncate text-[13px]">{i.label} <span className="text-xs text-muted-foreground">· {i.meta}</span></li>)}</ul>
      )}
    </Link>
  );
}
