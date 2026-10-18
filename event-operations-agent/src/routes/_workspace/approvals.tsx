import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ShieldCheck, ShieldAlert, Check, X, Pencil, Play, Ban } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Empty, PageHeader, Panel, Pill, StatusPill } from "@/components/ui-bits";
import { approve, editApprovalPayload, forEvent, getState, money, reject, update, useAppState, useCurrentEvent } from "@/lib/store";
import { executeApproval, tryForbidden } from "@/lib/actions";
import type { Approval } from "@/lib/types";
import { toast } from "sonner";

export const Route = createFileRoute("/_workspace/approvals")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Approvals — Event Operations Agent" },
      { name: "description", content: "Review every external message, quote and commitment before it happens." },
      { property: "og:title", content: "Approvals — Event Operations Agent" },
      { property: "og:description", content: "Review every external message, quote and commitment before it happens." },
    ],
  }),
  component: Approvals,
});

const KIND_LABEL: Record<string, string> = {
  send_message: "External message", accept_quote: "Accept quote", spend: "Spending commitment", participant_instructions: "Participant instructions",
  schedule_change: "Schedule change", plan_revision: "Plan revision",
};

function Approvals() {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const list = forEvent(s.approvals, ev.id).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  const pending = list.filter((a) => a.status === "pending" || a.status === "approved");
  const closed = list.filter((a) => a.status === "rejected" || a.status === "executed");
  const [blocked, setBlocked] = useState<string | null>(null);

  const forbidden = async (kind: "make_payment" | "sign_form" | "publish_content", label: string) => {
    const reason = await tryForbidden(ev.id, kind, label);
    setBlocked(`${label}: ${reason}`);
  };
  const bypass = async () => {
    const ap = list.find((a) => a.status === "pending");
    if (!ap) return setBlocked("No pending approval to test against. Ask the agent to draft outreach first.");
    const r = await executeApproval(ap, { bypass: true });
    setBlocked(r.ok ? "Unexpectedly allowed" : `Execute "${ap.title}" without approval: ${r.reason}`);
  };

  return (
    <>
      <PageHeader title="Approvals" description="The agent can draft and create internal tasks freely. External messages, quotes, spending and schedule changes wait here for you." />
      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-3">
          {pending.length === 0 ? <Empty icon={ShieldCheck} title="Nothing waiting for approval" body="Proposed actions from the agent will appear here." /> : pending.map((a) => <ApprovalCard key={a.id} a={a} />)}
          {closed.length > 0 && (
            <Panel title={`Resolved (${closed.length})`}>
              <ul className="divide-y">{closed.map((a) => <li key={a.id} className="flex items-center justify-between py-2 text-[13px]"><span>{a.title}</span><StatusPill status={a.status} /></li>)}</ul>
            </Panel>
          )}
        </div>
        <div className="space-y-3">
          <Panel title="Policy">
            <ul className="space-y-1.5 text-xs">
              <li className="flex gap-2"><Check className="h-3.5 w-3.5 text-success" />Internal drafts and tasks: allowed</li>
              <li className="flex gap-2"><ShieldCheck className="h-3.5 w-3.5 text-warning" />External messages, quotes, schedule changes: approval required</li>
              <li className="flex gap-2"><Ban className="h-3.5 w-3.5 text-destructive" />Payments, signing or submitting forms, publishing: always blocked</li>
            </ul>
            <p className="mt-3 text-[11px] text-muted-foreground">Rules are checked on the server before any action runs, not just hidden in the interface.</p>
          </Panel>
          <Panel title="Test trust controls">
            <div className="space-y-2">
              <Button variant="outline" size="sm" className="w-full justify-start" onClick={() => forbidden("make_payment", "Pay $150 badge deposit")}>Agent: pay badge deposit</Button>
              <Button variant="outline" size="sm" className="w-full justify-start" onClick={() => forbidden("sign_form", "Sign vendor application")}>Agent: sign vendor form</Button>
              <Button variant="outline" size="sm" className="w-full justify-start" onClick={bypass}>Execute a pending item without approval</Button>
            </div>
            {blocked && <div className="mt-3 flex gap-2 rounded-lg border border-destructive/30 bg-danger-soft p-2.5 text-xs"><ShieldAlert className="h-4 w-4 shrink-0 text-destructive" /><span><b>Blocked by server.</b> {blocked} Logged to Activity.</span></div>}
          </Panel>
        </div>
      </div>
    </>
  );
}

function ApprovalCard({ a }: { a: Approval }) {
  const s = useAppState();
  const ev = useCurrentEvent()!;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(a.payload);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const me = s.members[0];

  const saveEdit = () => {
    editApprovalPayload(a.id, text);
    // keep the linked message in sync with the edited payload
    if (a.kind === "send_message" && a.refId) {
      const [, subj = "", ...rest] = text.split("\n");
      update("messages", a.refId, { subject: subj.replace(/^Subject:\s*/, ""), body: rest.join("\n").replace(/^\n/, "") });
    }
    setEditing(false);
  };
  const run = async () => {
    setBusy(true);
    const r = await executeApproval(getState().approvals.find((x) => x.id === a.id)!);
    setBusy(false);
    r.ok ? toast.success(r.note) : toast.error(r.reason);
  };

  return (
    <div className="rounded-xl border bg-card shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
        <div>
          <div className="flex items-center gap-2"><Pill tone="violet">{KIND_LABEL[a.kind]}</Pill><StatusPill status={a.status} /></div>
          <div className="mt-1.5 text-sm font-semibold">{a.title}</div>
          <div className="text-xs text-muted-foreground">Target: {a.target} · proposed {formatDistanceToNow(new Date(a.createdAt))} ago</div>
        </div>
        <div className="text-right text-xs"><div className="text-muted-foreground">Est. cost</div><div className="font-medium">{a.cost == null ? (a.kind === "send_message" ? "None" : "Unknown") : money(a.cost, ev.currency)}</div></div>
      </div>
      <div className="space-y-3 px-4 py-3 text-[13px]">
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Exact action</div>
          {editing ? <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} className="font-mono text-xs" /> : <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 font-mono text-xs">{a.payload}</pre>}
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div><div className="mb-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">Reason</div>{a.reason}</div>
          <div><div className="mb-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">Evidence</div><span className="whitespace-pre-wrap">{a.evidence}</span></div>
        </div>
      </div>
      <div className="flex items-center justify-between border-t px-4 py-2.5">
        <span className="text-[11px] text-muted-foreground">{a.status === "approved" ? "Approved for this exact content. Any edit requires re-approval." : "Awaiting your decision."}</span>
        <div className="flex gap-2">
          {editing ? (
            <><Button size="sm" variant="ghost" onClick={() => { setText(a.payload); setEditing(false); }}>Cancel</Button><Button size="sm" onClick={saveEdit}>Save edit</Button></>
          ) : a.status === "approved" ? (
            <><Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit</Button><Button size="sm" onClick={run} disabled={busy}><Play className="h-3.5 w-3.5" />{a.kind === "send_message" ? "Send (simulated)" : "Apply"}</Button></>
          ) : (
            <>
              <Button size="sm" variant="ghost" onClick={() => reject(a.id, me)}><X className="h-3.5 w-3.5" />Reject</Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit</Button>
              <Button size="sm" onClick={() => setConfirm(true)}><Check className="h-3.5 w-3.5" />Approve</Button>
            </>
          )}
        </div>
      </div>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Approve this action?</AlertDialogTitle>
            <AlertDialogDescription>
              You are approving exactly this content for <b>{a.target}</b>. {a.kind === "send_message" && "Email isn't connected, so sending will be simulated and clearly labeled — no real message will be delivered."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs">{a.payload}</pre>
          <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={() => approve(a.id, me)}>Approve</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
