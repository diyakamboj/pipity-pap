import { authorizeAction } from "./policy.functions";
import type { ActionKind } from "./policy";
import { forEvent, getState, log, nowIso, update } from "./store";
import type { Approval } from "./types";

export type ExecResult = { ok: true; note: string } | { ok: false; reason: string };

/** Runs an approval through the server policy gate, then applies its effect. */
export async function executeApproval(ap: Approval, opts: { bypass?: boolean } = {}): Promise<ExecResult> {
  let res;
  try {
    res = await authorizeAction({
      data: {
        kind: ap.kind as ActionKind,
        payload: ap.payload,
        // `bypass` simulates a client trying to skip approval; the server still decides.
        approvalStatus: opts.bypass ? "approved" : ap.status,
        approvedHash: opts.bypass ? "forged" : ap.approvedHash,
      },
    });
  } catch (e) {
    const reason = `Policy service error: ${(e as Error).message}`;
    log({ eventId: ap.eventId, actor: "system", kind: "failed", summary: `${ap.title} — ${reason}`, origin: "system" });
    return { ok: false, reason };
  }
  if (!res.allowed) {
    log({ eventId: ap.eventId, actor: "system", kind: "blocked", summary: `Server blocked "${ap.title}": ${res.reason}`, origin: "system" });
    return { ok: false, reason: res.reason };
  }
  const note = applyEffect(ap);
  update("approvals", ap.id, { status: "executed" });
  log({ eventId: ap.eventId, actor: "system", kind: "executed", summary: `${ap.title} — ${note}`, origin: res.delivery === "simulated" ? "simulated" : "system" });
  return { ok: true, note };
}

function applyEffect(ap: Approval): string {
  const s = getState();
  switch (ap.kind) {
    case "send_message": {
      const m = s.messages.find((x) => x.id === ap.refId);
      if (m) {
        update("messages", m.id, { status: "sent_simulated", updatedAt: nowIso() });
        update("contacts", m.contactId, { status: "sent_simulated", lastActivity: nowIso(), nextStep: "Await reply (simulated send)" });
      }
      return "Simulated send. No real email was delivered (no email integration connected).";
    }
    case "accept_quote": {
      if (ap.refId) update("vendors", ap.refId, { status: "selected" });
      return "Quote marked as selected internally. Supplier has not been contacted; nothing is booked or paid.";
    }
    case "plan_revision": {
      const n = Number(ap.meta?.attendees);
      const ev = s.events.find((e) => e.id === ap.eventId);
      if (ev && n) {
        update("events", ev.id, { attendees: n });
        for (const r of forEvent(s.requirements, ev.id)) {
          if (r.category === "badges") update("requirements", r.id, { quantity: Math.ceil(n * 1.1) });
          if (r.category === "food") update("requirements", r.id, { quantity: n });
        }
        for (const t of forEvent(s.tasks, ev.id))
          if (/badge|food/i.test(t.title) && t.status === "done") update("tasks", t.id, { status: "todo" });
      }
      return `Attendance updated to ${n}; badge and food quantities recalculated. Confirmed supplier commitments were not changed.`;
    }
    case "schedule_change": {
      const id = String(ap.meta?.scheduleId ?? "");
      if (id) update("schedule", id, { start: String(ap.meta?.start), end: String(ap.meta?.end), confirmed: false, notes: "Changed via approval; reconfirm with stakeholders" });
      return "Schedule updated; item marked proposed until reconfirmed.";
    }
    default:
      return "Applied (simulated).";
  }
}

export async function tryForbidden(eventId: string, kind: "make_payment" | "sign_form" | "submit_form" | "publish_content", label: string) {
  try {
    const res = await authorizeAction({ data: { kind, payload: label } });
    if (!res.allowed) {
      log({ eventId, actor: "system", kind: "blocked", summary: `Server blocked "${label}": ${res.reason}`, origin: "system" });
      return res.reason;
    }
    return "Unexpectedly allowed";
  } catch (e) {
    return `Policy service error: ${(e as Error).message}`;
  }
}
