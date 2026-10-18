import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Store, Sparkles, Plus, FileText, Download, AlertTriangle, CheckCircle2, XCircle, PenLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, OriginPill, PageHeader, Panel, Pill, StatusPill, Unknowns } from "@/components/ui-bits";
import { CompareTable } from "@/components/ResultCards";
import { createApproval, forEvent, insert, log, money, uid, update, useAppState, useCurrentEvent } from "@/lib/store";
import type { ReqCategory, ReqStatus, Vendor } from "@/lib/types";
import { toast } from "sonner";

export const Route = createFileRoute("/_workspace/vendors")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Vendors — Event Operations Agent" },
      { name: "description", content: "Requirements, supplier options, quote comparison and vendor paperwork." },
      { property: "og:title", content: "Vendors — Event Operations Agent" },
      { property: "og:description", content: "Requirements, supplier options, quote comparison and vendor paperwork." },
    ],
  }),
  component: Vendors,
});

const CATS: ReqCategory[] = ["food", "badges", "printing", "shirts", "av", "artwork", "venue", "other"];

function Vendors() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const vendors = forEvent(s.vendors, ev.id);
  const [cmp, setCmp] = useState<string[]>([]);
  return (
    <>
      <PageHeader
        title="Vendors"
        description="What the event needs, who could supply it, and what paperwork is outstanding. Missing prices stay unknown, never zero."
        actions={<Button size="sm" asChild><Link to="/agent" search={{ q: "Find two suppliers for attendee badges." }}><Sparkles className="h-4 w-4" />Find suppliers</Link></Button>}
      />
      <Tabs defaultValue="suppliers">
        <TabsList>
          <TabsTrigger value="requirements">Requirements</TabsTrigger>
          <TabsTrigger value="suppliers">Suppliers ({vendors.length})</TabsTrigger>
          <TabsTrigger value="compare">Compare{cmp.length ? ` (${cmp.length})` : ""}</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="forms">Forms</TabsTrigger>
        </TabsList>
        <TabsContent value="requirements" className="mt-4"><Requirements /></TabsContent>
        <TabsContent value="suppliers" className="mt-4">
          {vendors.length === 0 ? <Empty icon={Store} title="No suppliers saved" body="Ask the agent to find options, or add one you already have a quote from." /> : (
            <div className="grid grid-cols-2 gap-3">{vendors.map((v) => <VendorCard key={v.id} v={v} selected={cmp.includes(v.id)} onToggle={() => setCmp((c) => (c.includes(v.id) ? c.filter((x) => x !== v.id) : [...c, v.id]))} />)}</div>
          )}
          <AddVendor />
        </TabsContent>
        <TabsContent value="compare" className="mt-4">
          {cmp.length < 2 ? <Empty icon={Store} title="Select at least two suppliers" body="Tick “Compare” on supplier cards to see them side by side." /> : <CompareTable ids={cmp} attendees={ev.attendees} currency={ev.currency} />}
        </TabsContent>
        <TabsContent value="documents" className="mt-4"><Documents /></TabsContent>
        <TabsContent value="forms" className="mt-4"><Forms /></TabsContent>
      </Tabs>
    </>
  );
}

function VendorCard({ v, selected, onToggle }: { v: Vendor; selected: boolean; onToggle: () => void }) {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const pending = s.approvals.find((a) => a.refId === v.id && a.kind === "accept_quote" && (a.status === "pending" || a.status === "approved"));
  const total = v.unitPrice == null ? null : v.unitPrice * Math.max(ev.attendees, v.minQty ?? 0) + (v.fees ?? 0);
  const requestAccept = () => {
    createApproval({
      eventId: ev.id, kind: "accept_quote", title: `Select ${v.name} for ${v.category}`, target: v.name,
      payload: `Select supplier: ${v.name}\nCategory: ${v.category}\nTerms: ${v.priceText}\nIncludes: ${v.includes}\nQuantity basis: ${Math.max(ev.attendees, v.minQty ?? 0)}\nEstimated total: ${total == null ? "Unknown" : money(total, ev.currency)}${v.fees == null ? " (fees unknown)" : ""}`,
      cost: total, evidence: `${v.origin === "simulated" ? "Fixture data" : "Supplier record"} retrieved ${v.retrieved}. Unknowns: ${v.unknowns.join(", ") || "none"}`,
      reason: v.fit, refId: v.id,
    });
    toast.success("Sent to Approvals");
  };
  return (
    <div className="rounded-xl border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-2">
        <div><div className="text-sm font-semibold">{v.name}</div><div className="mt-0.5 flex gap-1"><Pill>{v.category}</Pill><StatusPill status={v.status} /><OriginPill origin={v.origin} /></div></div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground"><Checkbox checked={selected} onCheckedChange={onToggle} />Compare</label>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div className="col-span-2"><dt className="text-muted-foreground">Price</dt><dd>{v.priceText}</dd></div>
        <div className="col-span-2"><dt className="text-muted-foreground">Includes</dt><dd>{v.includes}</dd></div>
        <div><dt className="text-muted-foreground">Minimum qty</dt><dd>{v.minQty ?? "Unknown"}</dd></div>
        <div><dt className="text-muted-foreground">Lead time</dt><dd>{v.leadTime ?? "Unknown"}</dd></div>
        <div><dt className="text-muted-foreground">Est. total</dt><dd>{money(total, ev.currency)}{total != null && v.fees == null ? " + fees?" : ""}</dd></div>
        <div><dt className="text-muted-foreground">Source</dt><dd>{v.url ? <a className="underline" href={v.url} target="_blank" rel="noreferrer">Website</a> : `Fixture · ${v.retrieved}`}</dd></div>
        <div className="col-span-2"><dt className="text-muted-foreground">Fit</dt><dd>{v.fit}</dd></div>
      </dl>
      <div className="mt-3"><Unknowns items={v.unknowns} /></div>
      <div className="mt-3 flex items-center justify-between border-t pt-3">
        <Select value={v.status} onValueChange={(st) => { if (st === "selected" || st === "confirmed") return toast.error("Selecting or confirming requires approval."); update("vendors", v.id, { status: st as Vendor["status"] }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `${v.name} → ${st}`, origin: "organizer" }); }}>
          <SelectTrigger className="h-7 w-36 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="estimate">Estimate</SelectItem><SelectItem value="quote_received">Quote received</SelectItem><SelectItem value="selected">Selected</SelectItem><SelectItem value="confirmed">Confirmed</SelectItem></SelectContent>
        </Select>
        {v.status === "selected" ? (
          <Button size="sm" variant="outline" onClick={() => { update("vendors", v.id, { status: "confirmed" }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Organizer confirmed commitment with ${v.name} (supplier confirmation recorded manually)`, origin: "organizer" }); }}>Record supplier confirmation</Button>
        ) : v.status !== "confirmed" && (
          <Button size="sm" variant="outline" disabled={!!pending} onClick={requestAccept}>{pending ? "Awaiting approval" : "Request selection"}</Button>
        )}
      </div>
    </div>
  );
}

function AddVendor() {
  const ev = useCurrentEvent()!;
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", category: "printing" as ReqCategory, priceText: "", unitPrice: "", minQty: "", leadTime: "" });
  if (!open) return <Button variant="outline" size="sm" className="mt-3" onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Add supplier manually</Button>;
  const save = () => {
    if (!f.name.trim()) return toast.error("Supplier name is required");
    const num = (x: string) => (x.trim() === "" || isNaN(Number(x)) ? null : Number(x));
    insert("vendors", [{ id: uid("ven"), eventId: ev.id, name: f.name, category: f.category, url: null, priceText: f.priceText || "Unknown", unitPrice: num(f.unitPrice), fees: null, includes: "Unknown", minQty: num(f.minQty), leadTime: f.leadTime || null, fit: "Added by organizer", unknowns: ["Fees"], status: "quote_received", origin: "organizer", retrieved: new Date().toISOString().slice(0, 10) }]);
    log({ eventId: ev.id, actor: "organizer", kind: "created", summary: `Added supplier ${f.name}`, origin: "organizer" });
    setOpen(false);
  };
  return (
    <Panel title="Add supplier" className="mt-3">
      <div className="grid grid-cols-3 gap-2">
        <Input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <Select value={f.category} onValueChange={(v) => setF({ ...f, category: v as ReqCategory })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{CATS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select>
        <Input placeholder="Price description" value={f.priceText} onChange={(e) => setF({ ...f, priceText: e.target.value })} />
        <Input placeholder="Unit price (blank = unknown)" value={f.unitPrice} onChange={(e) => setF({ ...f, unitPrice: e.target.value })} />
        <Input placeholder="Min qty (blank = unknown)" value={f.minQty} onChange={(e) => setF({ ...f, minQty: e.target.value })} />
        <Input placeholder="Lead time (blank = unknown)" value={f.leadTime} onChange={(e) => setF({ ...f, leadTime: e.target.value })} />
      </div>
      <div className="mt-3 flex justify-end gap-2"><Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button size="sm" onClick={save}>Save</Button></div>
    </Panel>
  );
}

function Requirements() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const reqs = forEvent(s.requirements, ev.id);
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState<ReqCategory>("other");
  return (
    <Panel title="Requirements checklist">
      {reqs.length === 0 && <p className="mb-3 text-xs text-muted-foreground">No requirements yet. Ask the agent what you're missing.</p>}
      <ul className="divide-y">
        {reqs.map((r) => (
          <li key={r.id} className="flex items-center gap-3 py-2 text-[13px]">
            <span className={`flex-1 ${r.status === "declined" ? "text-muted-foreground line-through" : ""}`}>{r.title}</span>
            <Pill>{r.category}</Pill>
            <Input className="h-7 w-20 text-xs" placeholder="qty" value={r.quantity ?? ""} onChange={(e) => update("requirements", r.id, { quantity: e.target.value === "" ? null : Number(e.target.value) || null })} />
            <OriginPill origin={r.origin} />
            <Select value={r.status} onValueChange={(v) => { update("requirements", r.id, { status: v as ReqStatus }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Marked "${r.title}" as ${v}`, origin: "organizer" }); }}>
              <SelectTrigger className="h-7 w-32 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{["required", "optional", "declined", "unresolved"].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent>
            </Select>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex gap-2">
        <Input placeholder="Add a requirement…" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Select value={cat} onValueChange={(v) => setCat(v as ReqCategory)}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent>{CATS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select>
        <Button disabled={!title.trim()} onClick={() => { insert("requirements", [{ id: uid("req"), eventId: ev.id, title, category: cat, status: "required", quantity: null, notes: "", origin: "organizer" }]); setTitle(""); }}>Add</Button>
      </div>
    </Panel>
  );
}

function Documents() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const docs = forEvent(s.documents, ev.id);
  if (!docs.length) return <Empty icon={FileText} title="No vendor documents" body="Permits, insurance certificates and applications you collect will be reviewed here." />;
  return (
    <div className="space-y-3">
      {docs.map((d) => {
        const v = s.vendors.find((x) => x.id === d.vendorId);
        const expired = d.expires && d.expires < ev.date;
        return (
          <Panel key={d.id} title={<span className="flex items-center gap-2"><FileText className="h-4 w-4" />{d.name}</span>} action={<OriginPill origin={d.origin} />}>
            <div className="mb-3 flex flex-wrap gap-4 text-xs"><span><span className="text-muted-foreground">Type:</span> {d.docType}</span><span><span className="text-muted-foreground">Vendor:</span> {v?.name ?? "Unknown"}</span><span className={expired ? "text-destructive" : ""}><span className="text-muted-foreground">Expires:</span> {d.expires ?? "Unknown"}{expired ? " (before event)" : ""}</span></div>
            <ul className="space-y-2">{d.findings.map((f) => (
              <li key={f.label} className="flex gap-2 text-[13px]">
                {f.kind === "match" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : f.kind === "missing" ? <AlertTriangle className="h-4 w-4 shrink-0 text-warning" /> : <XCircle className="h-4 w-4 shrink-0 text-destructive" />}
                <div><span className="font-medium">{f.label}</span> <StatusPill status={f.kind} /><div className="text-xs text-muted-foreground">{f.evidence}</div></div>
              </li>
            ))}</ul>
            <p className="mt-3 rounded bg-muted p-2 text-[11px] text-muted-foreground">This review checks the supplied document against event records only. It is not a determination of legal compliance.</p>
          </Panel>
        );
      })}
    </div>
  );
}

function Forms() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const food = forEvent(s.vendors, ev.id).find((v) => v.category === "food");
  const foodReq = forEvent(s.requirements, ev.id).find((r) => r.category === "food");
  const fields: { label: string; value: string | null; note?: string; human?: boolean }[] = [
    { label: "Event name", value: ev.name },
    { label: "Event date", value: ev.date },
    { label: "Event address", value: ev.location || null },
    { label: "Expected attendance", value: String(ev.attendees) },
    { label: "Food vendor business name", value: food?.name.replace(" (fictional)", "") ?? null },
    { label: "Number of meals", value: foodReq?.quantity ? String(foodReq.quantity) : null },
    { label: "Food prepared on site?", value: /no cook|not cooked|delivered/i.test(ev.constraints) ? "No (delivered)" : null, note: /no cook|not cooked|delivered/i.test(ev.constraints) ? "From event constraints" : "Ambiguous — confirm with caterer" },
    { label: "Vendor permit number", value: null, note: "Not found in documents" },
    { label: "Responsible organizer phone", value: null },
    { label: "Applicant signature & attestation", value: null, human: true },
  ];
  const filled = fields.filter((f) => f.value).length;
  const download = () => {
    const lines = [
      "TEMPORARY FOOD SERVICE EVENT APPLICATION — DRAFT (not submitted, not signed)",
      `Generated ${new Date().toISOString()} by Event Operations Agent (demo form template)`, "",
      ...fields.map((f) => `${f.label}: ${f.human ? "[REQUIRES HUMAN SIGNATURE]" : f.value ?? "[UNANSWERED]"}${f.note ? `  (${f.note})` : ""}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "food-service-application-draft.txt";
    a.click();
    URL.revokeObjectURL(a.href);
    log({ eventId: ev.id, actor: "agent", kind: "created", summary: `Generated form draft (${filled}/${fields.length} fields mapped). Not signed or submitted.`, origin: "system" });
  };
  return (
    <Panel title="Temporary food service application (demo template)" action={<Button size="sm" variant="outline" onClick={download}><Download className="h-3.5 w-3.5" />Download draft</Button>}>
      <p className="mb-3 text-xs text-muted-foreground">Fields are mapped from event and vendor records. {filled} of {fields.length} filled. The agent never signs or submits forms.</p>
      <table className="w-full text-[13px]">
        <tbody>{fields.map((f) => (
          <tr key={f.label} className="border-b last:border-0">
            <td className="w-64 py-2 text-muted-foreground">{f.label}</td>
            <td className="py-2">{f.human ? <Pill tone="red"><PenLine className="h-3 w-3" />Human signature required</Pill> : f.value ?? <Pill tone="amber">Unanswered</Pill>}</td>
            <td className="py-2 text-xs text-muted-foreground">{f.note}</td>
          </tr>
        ))}</tbody>
      </table>
    </Panel>
  );
}
