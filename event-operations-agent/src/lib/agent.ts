// Demo-mode orchestrating agent. Deterministic workflows that read and write real app records.
// No language model or web search is connected; every generated record is labeled "simulated".
import type { Contact, EventRecord, Message, ReqCategory, Requirement, Task, Vendor } from "./types";
import { createApproval, forEvent, getState, insert, log, nowIso, uid, update } from "./store";

export type Card =
  | { type: "questions"; ids: string[] }
  | { type: "vendors"; ids: string[] }
  | { type: "drafts"; ids: string[] }
  | { type: "compare"; ids: string[] }
  | { type: "tasks"; ids: string[] }
  | { type: "approval"; id: string; affected: string[] }
  | { type: "blocked"; reason: string }
  | { type: "missing"; fields: string[] };

export interface AgentResult {
  text: string;
  cards: Card[];
}
export type StepFn = (label: string) => Promise<void>;

export const STARTERS = [
  "What are we missing for this event?",
  "Find two suppliers for attendee badges.",
  "Prepare an invitation for a workshop speaker.",
  "Compare these vendor quotes.",
  "Build our setup plan.",
  "What changes if our attendance increases to 120?",
];

const today = () => new Date().toISOString().slice(0, 10);
function daysBefore(date: string, n: number) {
  const d = new Date(date + "T12:00:00");
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export async function runAgent(prompt: string, ev: EventRecord, step: StepFn): Promise<AgentResult> {
  const p = prompt.toLowerCase();
  if (/(pay|deposit|purchase|buy|sign|submit|publish)/.test(p)) return blockedAction(p, ev, step);
  if (/missing|need|what are we/.test(p)) return missing(ev, step);
  if (/badge|lanyard|supplier|vendor for|find two/.test(p) && !/compare/.test(p)) return badgeSuppliers(ev, step);
  if (/invit|speaker|host|sponsor|outreach/.test(p)) return outreach(ev, step, /sponsor/.test(p));
  if (/compare|quote/.test(p)) return compare(ev, step);
  if (/plan|setup|task|run.of.show/.test(p)) return buildPlan(ev, step);
  if (/attend|increase|headcount|more people/.test(p)) return attendance(p, ev, step);
  return {
    text: "I can run these demo workflows: find missing needs, find badge suppliers, draft speaker or sponsor outreach, compare quotes, build the setup plan, or analyze an attendance change. Try one of the suggestions.",
    cards: [],
  };
}

const CANDIDATE_NEEDS: { category: ReqCategory; title: string; question: string; qty?: (e: EventRecord) => number | null }[] = [
  { category: "badges", title: "Attendee name badges and lanyards", question: "Do attendees need printed name badges?", qty: (e) => Math.ceil(e.attendees * 1.1) },
  { category: "av", title: "Microphone for host", question: "Does the venue provide a microphone, or do we need to rent one?", qty: () => 1 },
  { category: "food", title: "Food and dietary accommodations", question: "Will you serve food, and do you need dietary counts?", qty: (e) => e.attendees },
  { category: "artwork", title: "Print-ready artwork for badges and signage", question: "Is print-ready artwork (logo, badge layout) ready?" },
  { category: "shirts", title: "Event t-shirts", question: "Do you want event t-shirts for attendees or volunteers?", qty: (e) => e.attendees },
];

async function missing(ev: EventRecord, step: StepFn): Promise<AgentResult> {
  await step("Reviewing event requirements");
  const reqs = forEvent(getState().requirements, ev.id);
  // Any existing record in a category (including declined ones) means we don't suggest it again.
  const covered = (c: ReqCategory, title: string) =>
    reqs.some((r) => r.category === c && (c !== "av" || /mic/i.test(r.title) === /mic/i.test(title)));
  const fresh: Requirement[] = [];
  for (const n of CANDIDATE_NEEDS) {
    if (covered(n.category, n.title)) continue;
    fresh.push({
      id: uid("req"), eventId: ev.id, title: n.title, category: n.category, status: "unresolved", question: n.question,
      quantity: n.qty ? n.qty(ev) : null, notes: "Suggested by agent from event type and attendee count.", origin: "simulated",
    });
    if (fresh.length >= 4) break;
  }
  await step("Saving results");
  if (fresh.length) insert("requirements", fresh);
  const unresolved = forEvent(getState().requirements, ev.id).filter((r) => r.status === "unresolved");
  log({ eventId: ev.id, actor: "agent", kind: "proposed", summary: `Identified ${fresh.length} possible needs for review`, origin: "simulated" });
  const gaps: string[] = [];
  if (!ev.venue) gaps.push("Venue");
  if (!ev.budget) gaps.push("Budget");
  return {
    text: unresolved.length
      ? `I found ${unresolved.length} open question${unresolved.length > 1 ? "s" : ""}. Mark each as required, optional or declined; I won't suggest declined items again.`
      : "Nothing new to suggest. Every known need is resolved or declined.",
    cards: [...(unresolved.length ? [{ type: "questions" as const, ids: unresolved.slice(0, 5).map((r) => r.id) }] : []), ...(gaps.length ? [{ type: "missing" as const, fields: gaps }] : [])],
  };
}

async function badgeSuppliers(ev: EventRecord, step: StepFn): Promise<AgentResult> {
  await step("Reviewing event requirements");
  const s = getState();
  const req = forEvent(s.requirements, ev.id).find((r) => r.category === "badges");
  if (req?.status === "declined") return { text: "Badges were declined for this event, so I didn't search for suppliers.", cards: [] };
  const qty = req?.quantity ?? Math.ceil(ev.attendees * 1.1);
  await step("Researching options (fixture data, no live search connected)");
  const existing = forEvent(s.vendors, ev.id).filter((v) => v.category === "badges");
  if (existing.length >= 2) return { text: "Two badge suppliers are already saved for this event.", cards: [{ type: "vendors", ids: existing.map((v) => v.id) }] };
  const vs: Vendor[] = [
    {
      id: uid("ven"), eventId: ev.id, name: "Emerald City Print Shop (fictional)", category: "badges", url: null,
      priceText: "$1.85 / badge incl. lanyard (estimate, 50-149 qty tier)", unitPrice: 1.85, fees: null,
      includes: "4x3 in. full-color card stock badge, clip, plain black lanyard", minQty: 50, leadTime: "5 business days after artwork approval",
      fit: `Covers ${qty} badges; local pickup possible in Seattle.`, unknowns: ["Delivery fee", "Rush pricing", "Custom-printed lanyard cost"],
      status: "estimate", origin: "simulated", retrieved: today(),
    },
    {
      id: uid("ven"), eventId: ev.id, name: "BadgeWorks Online (fictional)", category: "badges", url: null,
      priceText: "$129 per 100-pack PVC badges; lanyards $0.60 each (estimate)", unitPrice: 1.89, fees: 14.95,
      includes: "PVC badge, slot punch; lanyards sold separately", minQty: 100, leadTime: null,
      fit: "Must order 100 minimum; shipping time not published.", unknowns: ["Ship time to Seattle", "Artwork setup fee"],
      status: "estimate", origin: "simulated", retrieved: today(),
    },
  ];
  await step("Saving results");
  insert("vendors", vs);
  if (!req)
    insert("requirements", [{ id: uid("req"), eventId: ev.id, title: "Attendee name badges and lanyards", category: "badges", status: "required", quantity: qty, notes: "Added when suppliers were researched.", origin: "simulated" }]);
  log({ eventId: ev.id, actor: "agent", kind: "created", summary: `Saved 2 badge supplier options (fixture data) for ${qty} badges`, origin: "simulated", sources: ["Demo fixtures"] });
  await step("Preparing a recommendation");
  return {
    text: `Saved two badge options for ${qty} badges to Vendors. Emerald City is cheaper per unit with a known lead time; BadgeWorks has a 100-unit minimum and unknown shipping. These are fixture estimates, not real quotes.`,
    cards: [{ type: "vendors", ids: vs.map((v) => v.id) }],
  };
}

async function outreach(ev: EventRecord, step: StepFn, sponsorOnly: boolean): Promise<AgentResult> {
  await step("Reviewing event requirements");
  const s = getState();
  let contacts = forEvent(s.contacts, ev.id);
  await step("Researching options (fixture data, no live search connected)");
  const fresh: Contact[] = [];
  if (!sponsorOnly && !contacts.some((c) => c.kind === "speaker")) {
    fresh.push({
      id: uid("con"), eventId: ev.id, kind: "speaker", name: "Dr. Maya Lindqvist", org: "Fictional — ML educator", email: "maya.lindqvist@example.org",
      relevance: "Fictional workshop host profile: teaches applied LLM courses; ideal for a hands-on beginner session.",
      source: { label: "Fixture: demo speaker profile", url: null, retrieved: today(), origin: "simulated" },
      status: "candidate", lastActivity: nowIso(), nextStep: "Review invitation draft", owner: "Jordan P.",
      unknowns: ["Availability on " + ev.date, "Honorarium expectation", "Travel needs"],
      details: { topic: "Building your first LLM app", format: "90-min hands-on workshop", equipment: "Projector, mic (unconfirmed)", honorarium: "Unknown" },
    });
  }
  if (fresh.length) insert("contacts", fresh);
  contacts = forEvent(getState().contacts, ev.id).filter((c) => (sponsorOnly ? c.kind === "sponsor" : true));
  const drafted = new Set(forEvent(getState().messages, ev.id).map((m) => m.contactId));
  const msgs: Message[] = [];
  await step("Saving results");
  for (const c of contacts) {
    if (drafted.has(c.id) || !c.email) continue;
    const body =
      c.kind === "speaker"
        ? `Hi ${c.name.split(" ").slice(-1)[0] === c.name ? c.name : c.name.replace(/^Dr\. /, "Dr. ")},\n\nI'm organizing "${ev.name}", a ${ev.type.toLowerCase()} for ${ev.attendees} students on ${ev.date} at ${ev.venue}. We'd love for you to lead a ${c.details.format ?? "session"} on "${c.details.topic ?? "applied AI"}".\n\nCould you share your availability, any honorarium expectation, and the equipment you'd need? We can provide a projector; microphone availability is still being confirmed.\n\nThanks,\nThe ${s.workspace} team`
        : `Hi ${c.name.split(" ")[0]},\n\nWe're hosting "${ev.name}" for ${ev.attendees} student builders on ${ev.date}. Given ${c.org.replace(" (fictional)", "")}'s work in developer tools, we think a sponsorship would be a strong fit.\n\nWe're proposing ${c.details.proposedAmount ?? "a contribution"} in exchange for ${c.details.benefits ?? "recognition at the event"}. Happy to adjust to your approval process.\n\nBest,\nThe ${s.workspace} team`;
    const m: Message = {
      id: uid("msg"), eventId: ev.id, contactId: c.id, to: c.email,
      subject: c.kind === "speaker" ? `Invitation to lead a workshop at ${ev.name}` : `Sponsorship opportunity: ${ev.name}`,
      body, status: "pending_approval", updatedAt: nowIso(),
    };
    msgs.push(m);
    update("contacts", c.id, { status: "awaiting_approval", nextStep: "Approve draft in Approvals", lastActivity: nowIso() });
  }
  insert("messages", msgs);
  for (const m of msgs) {
    const c = contacts.find((x) => x.id === m.contactId)!;
    createApproval({
      eventId: ev.id, kind: "send_message", title: `Send ${c.kind} outreach to ${c.name}`, target: m.to,
      payload: messagePayload(m), cost: null, evidence: c.source.label + ". " + c.relevance,
      reason: c.kind === "speaker" ? "Event needs a confirmed workshop host." : "Sponsorship would offset catering and badge costs.", refId: m.id,
    });
  }
  return {
    text: msgs.length
      ? `Drafted ${msgs.length} message${msgs.length > 1 ? "s" : ""}. Nothing has been sent; each is waiting in Approvals. Contacts are fictional fixtures.`
      : "All contacts already have drafts. Review them in Outreach.",
    cards: msgs.length ? [{ type: "drafts", ids: msgs.map((m) => m.id) }] : [],
  };
}

export function messagePayload(m: Pick<Message, "to" | "subject" | "body">) {
  return `To: ${m.to}\nSubject: ${m.subject}\n\n${m.body}`;
}

async function compare(ev: EventRecord, step: StepFn): Promise<AgentResult> {
  await step("Reviewing saved vendor records");
  const vs = forEvent(getState().vendors, ev.id);
  if (vs.length < 2) return { text: "I need at least two saved suppliers to compare. Ask me to find badge suppliers first.", cards: [] };
  await step("Preparing a recommendation");
  return { text: "Here is a side-by-side of saved suppliers. Unknown prices and fees are shown as unknown, not zero.", cards: [{ type: "compare", ids: vs.map((v) => v.id) }] };
}

async function buildPlan(ev: EventRecord, step: StepFn): Promise<AgentResult> {
  await step("Reviewing event requirements, suppliers and outreach");
  const s = getState();
  const reqs = forEvent(s.requirements, ev.id).filter((r) => r.status === "required" || r.status === "optional");
  const vendors = forEvent(s.vendors, ev.id);
  const speakers = forEvent(s.contacts, ev.id).filter((c) => c.kind === "speaker");
  const existing = new Set(forEvent(s.tasks, ev.id).map((t) => t.title));
  const mk = (title: string, phase: Task["phase"], due: string, related: string, owner: string | null, deps: string[] = []): Task => ({
    id: uid("tsk"), eventId: ev.id, title, phase, status: "todo", owner, due, dependsOn: deps, related, origin: "simulated",
  });
  await step("Building tasks and dependencies");
  const list: Task[] = [];
  const venue = mk("Confirm venue access and setup time", "prep", daysBefore(ev.date, 14), `Venue: ${ev.venue}`, "Saachi A.");
  list.push(venue);
  if (reqs.some((r) => r.category === "av")) list.push(mk("Verify microphone and projector availability", "prep", daysBefore(ev.date, 10), "Requirement: AV", "Marcus L.", [venue.id]));
  const art = reqs.some((r) => r.category === "artwork" || r.category === "badges") ? mk("Obtain print-ready artwork", "prep", daysBefore(ev.date, 12), "Requirement: artwork", null) : null;
  if (art) list.push(art);
  const badgeReq = reqs.find((r) => r.category === "badges");
  if (badgeReq) {
    const v = vendors.find((x) => x.category === "badges");
    list.push(mk(`Finalize badge quantities (${badgeReq.quantity ?? "qty unknown"})`, "prep", daysBefore(ev.date, 9), v ? `Vendor: ${v.name}` : "Requirement: badges", "Priya K.", art ? [art.id] : []));
  }
  const food = reqs.find((r) => r.category === "food");
  if (food) {
    const v = vendors.find((x) => x.category === "food");
    list.push(mk("Confirm food quantity and dietary requirements", "prep", daysBefore(ev.date, 8), v ? `Vendor: ${v.name}` : "Requirement: food", "Jordan P."));
  }
  if (speakers.length) list.push(mk("Confirm speaker arrival and session requirements", "prep", daysBefore(ev.date, 5), `Contact: ${speakers[0].name}`, "Jordan P."));
  const brief = mk("Prepare volunteer briefing", "prep", daysBefore(ev.date, 2), "Run of show", null);
  list.push(brief);
  const room = mk("Complete room setup", "setup", ev.date, "Schedule: setup", "Marcus L.", [venue.id, brief.id]);
  list.push(room);
  const check = mk("Run final equipment check", "setup", ev.date, "Requirement: AV", "Marcus L.", [room.id]);
  list.push(check);
  list.push(mk("Complete teardown", "teardown", ev.date, "Schedule: teardown", "Saachi A.", [check.id]));
  const fresh = list.filter((t) => !existing.has(t.title));
  await step("Saving results");
  insert("tasks", fresh);
  log({ eventId: ev.id, actor: "agent", kind: "created", summary: `Created ${fresh.length} logistics tasks from ${reqs.length} requirements and ${vendors.length} suppliers`, origin: "simulated" });
  return {
    text: fresh.length
      ? `Created ${fresh.length} tasks with owners, deadlines and dependencies. ${fresh.filter((t) => !t.owner).length} are unassigned. Task creation is internal and doesn't need approval.`
      : "The plan is already up to date.",
    cards: fresh.length ? [{ type: "tasks", ids: fresh.map((t) => t.id) }] : [],
  };
}

async function attendance(p: string, ev: EventRecord, step: StepFn): Promise<AgentResult> {
  const n = Number(p.match(/(\d{2,4})/)?.[1]);
  if (!n || n === ev.attendees) return { text: `Current attendance is ${ev.attendees}. Tell me the new number, e.g. "What changes if attendance increases to 120?"`, cards: [{ type: "missing", fields: ["New attendee count"] }] };
  await step("Reviewing tasks, suppliers and schedule");
  const s = getState();
  const vendors = forEvent(s.vendors, ev.id);
  const affected: string[] = [];
  for (const v of vendors) {
    if (v.unitPrice != null) affected.push(`${v.name}: ${ev.attendees} → ${n} units, est. +$${((n - ev.attendees) * v.unitPrice).toFixed(2)}`);
    else affected.push(`${v.name}: quantity change; price unknown`);
    if (v.status === "confirmed") affected.push(`⚠ ${v.name} is a confirmed commitment and must be renegotiated, not silently changed.`);
  }
  forEvent(s.tasks, ev.id).filter((t) => /badge|food|room/i.test(t.title)).forEach((t) => affected.push(`Task: ${t.title}`));
  if (n > 100) affected.push("Venue: Room G10 capacity unverified above 100 — confirm with facilities.");
  await step("Preparing a proposed plan revision");
  const ap = createApproval({
    eventId: ev.id, kind: "plan_revision", title: `Revise plan for ${n} attendees`, target: ev.name,
    payload: `Change attendance ${ev.attendees} → ${n}. Update badge and food requirement quantities. Flag affected tasks.`,
    cost: vendors.reduce((sum, v) => sum + (v.unitPrice ? (n - ev.attendees) * v.unitPrice : 0), 0) || null,
    evidence: affected.join("\n"), reason: "Attendance change affects quantities and confirmed commitments.", refId: ev.id, meta: { attendees: n },
  });
  return { text: `This affects ${affected.length} items. I prepared a plan revision for approval; nothing changed yet.`, cards: [{ type: "approval", id: ap.id, affected }] };
}

async function blockedAction(p: string, ev: EventRecord, step: StepFn): Promise<AgentResult> {
  const { authorizeAction } = await import("./policy.functions");
  const kind = /sign/.test(p) ? "sign_form" : /submit/.test(p) ? "submit_form" : /publish/.test(p) ? "publish_content" : "make_payment";
  await step("Checking action policy on the server");
  try {
    const res = await authorizeAction({ data: { kind, payload: p } });
    if (!res.allowed) {
      log({ eventId: ev.id, actor: "system", kind: "blocked", summary: `Server blocked agent request (${kind.replace("_", " ")}): ${res.reason}`, origin: "system" });
      return { text: "I can't do that.", cards: [{ type: "blocked", reason: res.reason }] };
    }
    return { text: "Policy allowed this action.", cards: [] };
  } catch (e) {
    log({ eventId: ev.id, actor: "system", kind: "failed", summary: `Policy check failed: ${(e as Error).message}`, origin: "system" });
    return { text: `The policy check failed: ${(e as Error).message}. No action was taken.`, cards: [] };
  }
}
