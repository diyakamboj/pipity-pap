import { Link } from "@tanstack/react-router";
import { ShieldAlert, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill, StatusPill, OriginPill, Unknowns } from "@/components/ui-bits";
import type { Card } from "@/lib/agent";
import { log, money, update, useAppState, useCurrentEvent } from "@/lib/store";
import type { ReqStatus } from "@/lib/types";

export function ResultCard({ card }: { card: Card }) {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const box = "rounded-lg border bg-card p-3";
  switch (card.type) {
    case "questions":
      return (
        <div className={box}>
          <div className="mb-2 text-xs font-semibold">Missing-information checklist</div>
          <ul className="divide-y">
            {card.ids.map((id) => {
              const r = s.requirements.find((x) => x.id === id);
              if (!r) return null;
              return (
                <li key={id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <div className="text-[13px]">{r.question ?? r.title}</div>
                    <div className="text-[11px] text-muted-foreground">{r.title}{r.quantity ? ` · qty ${r.quantity}` : ""}</div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {(["required", "optional", "declined"] as ReqStatus[]).map((st) => (
                      <Button key={st} size="sm" variant={r.status === st ? "default" : "outline"} className="h-7 px-2 text-xs"
                        onClick={() => { update("requirements", id, { status: st }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Marked "${r.title}" as ${st}`, origin: "organizer" }); }}>
                        {st}
                      </Button>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      );
    case "vendors":
      return (
        <div className="grid grid-cols-2 gap-2">
          {card.ids.map((id) => {
            const v = s.vendors.find((x) => x.id === id);
            if (!v) return null;
            return (
              <div key={id} className={box}>
                <div className="flex items-start justify-between gap-2"><div className="text-[13px] font-medium">{v.name}</div><OriginPill origin={v.origin} /></div>
                <div className="mt-1 text-xs">{v.priceText}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">Min {v.minQty ?? "unknown"} · Lead time: {v.leadTime ?? "unknown"}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">Source: {v.url ? <a href={v.url} className="underline">{v.url}</a> : `demo fixture, retrieved ${v.retrieved}`}</div>
                <div className="mt-2"><Unknowns items={v.unknowns} /></div>
              </div>
            );
          })}
          <Link to="/vendors" className="col-span-2 text-xs text-primary hover:underline">Open in Vendors →</Link>
        </div>
      );
    case "drafts":
      return (
        <div className="space-y-2">
          {card.ids.map((id) => {
            const m = s.messages.find((x) => x.id === id);
            if (!m) return null;
            return (
              <div key={id} className={box}>
                <div className="flex items-center justify-between"><div className="text-xs"><span className="text-muted-foreground">To:</span> {m.to}</div><StatusPill status={m.status} /></div>
                <div className="mt-1 text-[13px] font-medium">{m.subject}</div>
                <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap font-sans text-xs text-muted-foreground">{m.body}</pre>
              </div>
            );
          })}
          <Link to="/approvals" className="text-xs text-primary hover:underline">Review in Approvals →</Link>
        </div>
      );
    case "compare":
      return <CompareTable ids={card.ids} attendees={ev.attendees} currency={ev.currency} />;
    case "tasks":
      return (
        <div className={box}>
          <ul className="divide-y">
            {card.ids.map((id) => {
              const t = s.tasks.find((x) => x.id === id);
              if (!t) return null;
              return (
                <li key={id} className="flex items-center justify-between gap-2 py-1.5 text-[13px]">
                  <span>{t.title}</span>
                  <span className="flex shrink-0 items-center gap-2 text-[11px] text-muted-foreground">{t.owner ?? <Pill tone="amber">unassigned</Pill>}<span className="font-mono">{t.due}</span>{t.dependsOn.length > 0 && <Pill>{t.dependsOn.length} dep</Pill>}</span>
                </li>
              );
            })}
          </ul>
          <Link to="/logistics" className="mt-2 inline-block text-xs text-primary hover:underline">Open in Logistics →</Link>
        </div>
      );
    case "approval": {
      const ap = s.approvals.find((a) => a.id === card.id);
      return (
        <div className={box}>
          <div className="flex items-center justify-between"><div className="text-[13px] font-medium">{ap?.title}</div>{ap && <StatusPill status={ap.status} />}</div>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">{card.affected.map((a) => <li key={a}>• {a}</li>)}</ul>
          <Link to="/approvals" className="mt-2 inline-block text-xs text-primary hover:underline">Review proposed revision →</Link>
        </div>
      );
    }
    case "blocked":
      return (
        <div className="flex gap-2 rounded-lg border border-destructive/30 bg-danger-soft p-3 text-[13px]">
          <ShieldAlert className="h-4 w-4 shrink-0 text-destructive" />
          <div><div className="font-medium text-destructive">Blocked by server policy</div><div className="mt-0.5 text-xs">{card.reason} Recorded in Activity.</div></div>
        </div>
      );
    case "missing":
      return (
        <div className="rounded-lg border border-warning/30 bg-warning-soft p-3 text-xs">
          <span className="font-medium">I need from you:</span> {card.fields.join(", ")}.
          <Link to="/" className="ml-1 inline-flex items-center gap-0.5 text-primary hover:underline">Edit event<ExternalLink className="h-3 w-3" /></Link>
        </div>
      );
  }
}

export function CompareTable({ ids, attendees, currency }: { ids: string[]; attendees: number; currency: string }) {
  const s = useAppState();
  const vs = ids.map((id) => s.vendors.find((v) => v.id === id)).filter(Boolean) as NonNullable<ReturnType<typeof s.vendors.find>>[];
  const rows: [string, (v: (typeof vs)[number]) => React.ReactNode][] = [
    ["Category", (v) => v.category],
    ["Status", (v) => <StatusPill status={v.status} />],
    ["Price basis", (v) => v.priceText],
    ["Unit price", (v) => money(v.unitPrice, currency)],
    ["Fees", (v) => money(v.fees, currency)],
    [`Est. total (${attendees})`, (v) => (v.unitPrice == null ? "Unknown" : `${money(v.unitPrice * Math.max(attendees, v.minQty ?? 0) + (v.fees ?? 0), currency)}${v.fees == null ? " + unknown fees" : ""}`)],
    ["Minimum qty", (v) => v.minQty ?? "Unknown"],
    ["Lead time", (v) => v.leadTime ?? "Unknown"],
    ["Includes", (v) => v.includes],
    ["Unknowns", (v) => <Unknowns items={v.unknowns} />],
    ["Origin", (v) => <OriginPill origin={v.origin} />],
  ];
  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-xs">
        <thead><tr className="border-b bg-muted/50"><th className="w-32 p-2 text-left font-medium text-muted-foreground"></th>{vs.map((v) => <th key={v.id} className="p-2 text-left font-semibold">{v.name}</th>)}</tr></thead>
        <tbody>{rows.map(([l, f]) => <tr key={l} className="border-b last:border-0"><td className="p-2 text-muted-foreground">{l}</td>{vs.map((v) => <td key={v.id} className="p-2 align-top">{f(v)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
