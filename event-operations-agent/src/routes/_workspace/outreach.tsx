import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Megaphone, Plus, Sparkles, Mail } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Empty, OriginPill, PageHeader, Pill, StatusPill, Unknowns } from "@/components/ui-bits";
import { createApproval, editApprovalPayload, forEvent, insert, log, nowIso, uid, update, useAppState, useCurrentEvent } from "@/lib/store";
import { messagePayload } from "@/lib/agent";
import type { Contact, ContactKind, OutreachStatus } from "@/lib/types";
import { toast } from "sonner";

export const Route = createFileRoute("/_workspace/outreach")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Outreach — Event Operations Agent" },
      { name: "description", content: "Research, draft and track speaker and sponsor outreach." },
      { property: "og:title", content: "Outreach — Event Operations Agent" },
      { property: "og:description", content: "Research, draft and track speaker and sponsor outreach." },
    ],
  }),
  component: Outreach,
});

function Outreach() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const [tab, setTab] = useState<"all" | ContactKind>("all");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const contacts = forEvent(s.contacts, ev.id).filter((c) => tab === "all" || c.kind === tab);
  const sel = s.contacts.find((c) => c.id === open);

  return (
    <>
      <PageHeader
        title="Outreach"
        description="Speakers, sponsors and other contacts. Every external message needs approval; sends are simulated until email is connected."
        actions={<>
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}><Plus className="h-4 w-4" />Add contact</Button>
          <Button size="sm" asChild><Link to="/agent" search={{ q: "Prepare an invitation for a workshop speaker." }}><Sparkles className="h-4 w-4" />Research & draft</Link></Button>
        </>}
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)} className="mb-3">
        <TabsList><TabsTrigger value="all">All</TabsTrigger><TabsTrigger value="speaker">Speakers</TabsTrigger><TabsTrigger value="sponsor">Sponsors</TabsTrigger><TabsTrigger value="other">Other</TabsTrigger></TabsList>
      </Tabs>
      {contacts.length === 0 ? (
        <Empty icon={Megaphone} title="No contacts yet" body="Ask the agent to research a workshop host or add a contact you already know." />
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full text-[13px]">
            <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>{["Person / org", "Type", "Relevance", "Source", "Status", "Last activity", "Next step", "Owner"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} onClick={() => setOpen(c.id)} className="cursor-pointer border-b last:border-0 hover:bg-muted/40">
                  <td className="px-3 py-2.5"><div className="font-medium">{c.name}</div><div className="text-xs text-muted-foreground">{c.org}</div></td>
                  <td className="px-3"><Pill>{c.kind}</Pill></td>
                  <td className="max-w-56 truncate px-3 text-xs text-muted-foreground">{c.relevance}</td>
                  <td className="px-3"><OriginPill origin={c.source.origin} /></td>
                  <td className="px-3"><StatusPill status={c.status} /></td>
                  <td className="px-3 text-xs text-muted-foreground">{formatDistanceToNow(new Date(c.lastActivity))} ago</td>
                  <td className="px-3 text-xs">{c.nextStep}</td>
                  <td className="px-3 text-xs">{c.owner ?? <span className="text-muted-foreground">Unassigned</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Sheet open={!!sel} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent className="w-[560px] overflow-y-auto sm:max-w-[560px]">{sel && <ContactDetail c={sel} />}</SheetContent>
      </Sheet>
      <AddContact open={adding} onClose={() => setAdding(false)} />
    </>
  );
}

function ContactDetail({ c }: { c: Contact }) {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const msg = s.messages.find((m) => m.contactId === c.id);
  const ap = msg && s.approvals.find((a) => a.refId === msg.id && a.kind === "send_message");
  const [subject, setSubject] = useState(msg?.subject ?? "");
  const [body, setBody] = useState(msg?.body ?? "");
  const [reply, setReply] = useState("");

  const saveDraft = () => {
    if (!msg) {
      if (!c.email) return toast.error("This contact has no known email address. Add one before drafting.");
      const m = { id: uid("msg"), eventId: ev.id, contactId: c.id, to: c.email, subject, body, status: "pending_approval" as const, updatedAt: nowIso() };
      insert("messages", [m]);
      createApproval({ eventId: ev.id, kind: "send_message", title: `Send ${c.kind} outreach to ${c.name}`, target: m.to, payload: messagePayload(m), cost: null, evidence: c.source.label, reason: c.relevance, refId: m.id });
      update("contacts", c.id, { status: "awaiting_approval", nextStep: "Approve draft", lastActivity: nowIso() });
      return toast.success("Draft saved and sent to Approvals");
    }
    update("messages", msg.id, { subject, body, status: "pending_approval", updatedAt: nowIso() });
    if (ap) editApprovalPayload(ap.id, messagePayload({ to: msg.to, subject, body }));
    log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Edited draft to ${c.name}`, origin: "organizer" });
    toast.success(ap?.status === "approved" ? "Draft updated — previous approval invalidated" : "Draft updated");
  };

  const recordReply = () => {
    if (!reply.trim()) return;
    update("contacts", c.id, { status: "replied", lastActivity: nowIso(), nextStep: "Review reply and confirm conditions", details: { ...c.details, lastReply: reply } });
    log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `Logged reply from ${c.name}`, origin: "organizer" });
    setReply("");
  };

  return (
    <>
      <SheetHeader><SheetTitle>{c.name}</SheetTitle></SheetHeader>
      <div className="space-y-5 px-4 pb-6 text-[13px]">
        <div className="flex flex-wrap gap-1.5"><Pill>{c.kind}</Pill><StatusPill status={c.status} /><OriginPill origin={c.source.origin} /></div>
        <p className="text-muted-foreground">{c.relevance}</p>
        <div className="text-xs text-muted-foreground">Source: {c.source.url ? <a className="underline" href={c.source.url} target="_blank" rel="noreferrer">{c.source.label}</a> : c.source.label} · retrieved {c.source.retrieved}</div>
        <dl className="grid grid-cols-2 gap-2 rounded-lg border p-3">
          {Object.entries(c.details).map(([k, v]) => <div key={k}><dt className="text-[11px] capitalize text-muted-foreground">{k.replace(/([A-Z])/g, " $1")}</dt><dd>{v}</dd></div>)}
          <div><dt className="text-[11px] text-muted-foreground">Email</dt><dd>{c.email ?? "Unknown"}</dd></div>
          <div>
            <dt className="text-[11px] text-muted-foreground">Status</dt>
            <dd>
              <Select value={c.status} onValueChange={(v) => { update("contacts", c.id, { status: v as OutreachStatus, lastActivity: nowIso() }); log({ eventId: ev.id, actor: "organizer", kind: "changed", summary: `${c.name} status → ${v}`, origin: "organizer" }); }}>
                <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>{["candidate", "drafted", "awaiting_approval", "sent_simulated", "replied", "committed", "declined"].map((x) => <SelectItem key={x} value={x} disabled={x === "sent_simulated"}>{x.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </dd>
          </div>
        </dl>
        <div><div className="mb-1 text-xs font-medium">Unknowns (not invented)</div><Unknowns items={c.unknowns} /></div>

        <div className="space-y-2 rounded-lg border p-3">
          <div className="flex items-center justify-between"><div className="flex items-center gap-1.5 text-xs font-semibold"><Mail className="h-3.5 w-3.5" />Message</div>{msg && <StatusPill status={msg.status} />}</div>
          <div className="text-xs"><span className="text-muted-foreground">Recipient:</span> {msg?.to ?? c.email ?? "Unknown — add an email"}</div>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" disabled={msg?.status === "sent_simulated"} />
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={9} placeholder="Message body" disabled={msg?.status === "sent_simulated"} />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">{msg?.status === "sent_simulated" ? "Simulated send — no real email was delivered." : "Saving sends this to Approvals. Edits invalidate prior approval."}</span>
            <div className="flex gap-2">
              {ap && <Button size="sm" variant="outline" asChild><Link to="/approvals">View approval</Link></Button>}
              <Button size="sm" onClick={saveDraft} disabled={msg?.status === "sent_simulated" || !subject.trim() || !body.trim()}>Save draft</Button>
            </div>
          </div>
        </div>

        <div className="space-y-2 rounded-lg border p-3">
          <div className="text-xs font-semibold">Log a reply</div>
          {c.details.lastReply && <p className="rounded bg-muted p-2 text-xs">“{c.details.lastReply}”</p>}
          <Textarea value={reply} onChange={(e) => setReply(e.target.value)} rows={2} placeholder="Paste the reply and any conditions…" />
          <Button size="sm" variant="outline" onClick={recordReply} disabled={!reply.trim()}>Save reply</Button>
        </div>
      </div>
    </>
  );
}

function AddContact({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ev = useCurrentEvent()!;
  const s = useAppState();
  const [f, setF] = useState({ name: "", org: "", email: "", kind: "speaker" as ContactKind, relevance: "" });
  const save = () => {
    if (!f.name.trim()) return toast.error("Name is required");
    if (f.email && !/^\S+@\S+\.\S+$/.test(f.email)) return toast.error("Email looks invalid");
    insert("contacts", [{
      id: uid("con"), eventId: ev.id, kind: f.kind, name: f.name.trim(), org: f.org, email: f.email || null, relevance: f.relevance || "Added by organizer",
      source: { label: "Entered by organizer", url: null, retrieved: new Date().toISOString().slice(0, 10), origin: "organizer" },
      status: "candidate", lastActivity: nowIso(), nextStep: "Draft message", owner: s.members[0], unknowns: f.email ? [] : ["Email address"], details: {},
    }]);
    log({ eventId: ev.id, actor: "organizer", kind: "created", summary: `Added contact ${f.name}`, origin: "organizer" });
    setF({ name: "", org: "", email: "", kind: "speaker", relevance: "" });
    onClose();
  };
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader><SheetTitle>Add contact</SheetTitle></SheetHeader>
        <div className="space-y-3 px-4">
          <div className="space-y-1"><Label className="text-xs">Type</Label>
            <Select value={f.kind} onValueChange={(v) => setF({ ...f, kind: v as ContactKind })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="speaker">Speaker</SelectItem><SelectItem value="sponsor">Sponsor</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent></Select>
          </div>
          {(["name", "org", "email", "relevance"] as const).map((k) => <div key={k} className="space-y-1"><Label className="text-xs capitalize">{k}</Label><Input value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></div>)}
          <Button onClick={save} className="w-full">Add contact</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
