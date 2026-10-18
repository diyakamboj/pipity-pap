import type { AppState, EventRecord, Requirement } from "./types";
import { getState, insert, log, nowIso, setState, uid } from "./store";

export type NewEventInput = Omit<EventRecord, "id" | "createdAt">;

export function createEvent(input: NewEventInput) {
  const ev: EventRecord = { ...input, id: uid("evt"), createdAt: nowIso() };
  setState((s) => ({ ...s, events: [...s.events, ev], currentEventId: ev.id }));
  log({ eventId: ev.id, actor: "organizer", kind: "created", summary: `Created event "${ev.name}"`, origin: "organizer" });
  return ev;
}

const D = "2026-11-14";
export function loadDemo(): string {
  const eventId = uid("evt");
  const t = nowIso();
  const ev: EventRecord = {
    id: eventId,
    name: "Build with AI: Applied LLM Workshop",
    type: "Technology workshop",
    date: D,
    startTime: "13:00",
    endTime: "17:30",
    venue: "Paul G. Allen Center, Room G10",
    location: "185 E Stevens Way NE, Seattle, WA",
    attendees: 80,
    budget: 3500,
    currency: "USD",
    goals: "Hands-on intro to building LLM apps for students; secure one sponsor; 90% attendee satisfaction.",
    constraints: "Room access from 11:30. No open flames. Food must be delivered, not cooked on site.",
    existing: "Venue booked. Rainier Catering quoted for lunch.",
    createdAt: t,
  };
  const reqs: Requirement[] = [
    { id: uid("req"), eventId, title: "Lunch and coffee for attendees", category: "food", status: "required", quantity: 80, notes: "Collect dietary needs in registration form.", origin: "organizer" },
    { id: uid("req"), eventId, title: "Projector and HDMI adapters", category: "av", status: "required", quantity: 1, notes: "Room has a ceiling projector per facilities page; adapters unconfirmed.", origin: "organizer" },
  ];
  const sponsorId = uid("con");
  const cateringId = uid("ven");
  const data: Partial<AppState> = {
    requirements: reqs,
    contacts: [
      {
        id: sponsorId, eventId, kind: "sponsor", name: "Elena Ruiz", org: "Cascade Cloud Labs (fictional)", email: "elena.ruiz@cascadecloud.example",
        relevance: "Seattle developer-tools startup that has sponsored two student hackathons; sells LLM eval tooling.",
        source: { label: "Fixture: demo sponsor profile", url: null, retrieved: D, origin: "simulated" },
        status: "candidate", lastActivity: t, nextStep: "Draft sponsorship ask", owner: "Priya K.",
        unknowns: ["Sponsorship budget range", "Internal approval process"],
        details: { contribution: "Cash + API credits", proposedAmount: "$1,500 (proposed)", benefits: "Logo on slides, 5-min intro", fulfillment: "Unknown" },
      },
    ],
    vendors: [
      {
        id: cateringId, eventId, name: "Rainier Catering Co. (fictional)", category: "food", url: null,
        priceText: "$16.50 / person boxed lunch", unitPrice: 16.5, fees: 85, includes: "Sandwich, salad, cookie, compostable packaging; $85 delivery",
        minQty: 25, leadTime: "Order 7 days ahead", fit: "Delivers to campus; vegetarian and vegan options listed.",
        unknowns: ["Gluten-free availability", "Coffee service pricing"], status: "quote_received", origin: "simulated", retrieved: D,
      },
    ],
    documents: [
      {
        id: uid("doc"), eventId, vendorId: cateringId, name: "Rainier_FoodPermit_2026.pdf", docType: "Food service permit", expires: "2026-10-31",
        origin: "simulated",
        findings: [
          { label: "Business name", kind: "match", evidence: "Permit holder: Rainier Catering Co. matches quote letterhead." },
          { label: "Expiration date", kind: "mismatch", evidence: "Permit expires 2026-10-31, before event date 2026-11-14." },
          { label: "Certificate of insurance", kind: "missing", evidence: "No COI provided. Venue requires $1M general liability." },
        ],
      },
    ],
    schedule: [
      { id: uid("sch"), eventId, start: "11:30", end: "13:00", title: "Room access and setup", confirmed: true, notes: "Confirmed with facilities" },
      { id: uid("sch"), eventId, start: "13:00", end: "13:20", title: "Doors open and check-in", confirmed: false, notes: "" },
      { id: uid("sch"), eventId, start: "13:20", end: "15:00", title: "Workshop part 1", confirmed: false, notes: "" },
      { id: uid("sch"), eventId, start: "15:00", end: "15:30", title: "Lunch break", confirmed: false, notes: "Late lunch" },
      { id: uid("sch"), eventId, start: "15:30", end: "17:00", title: "Workshop part 2 + demos", confirmed: false, notes: "" },
      { id: uid("sch"), eventId, start: "17:00", end: "17:30", title: "Teardown", confirmed: true, notes: "Room must be clear by 17:30" },
    ],
  };
  setState((s) => ({
    ...s,
    events: [...s.events, ev],
    currentEventId: eventId,
    requirements: [...s.requirements, ...data.requirements!],
    contacts: [...s.contacts, ...data.contacts!],
    vendors: [...s.vendors, ...data.vendors!],
    documents: [...s.documents, ...data.documents!],
    schedule: [...s.schedule, ...data.schedule!],
  }));
  log({ eventId, actor: "system", kind: "created", summary: "Loaded demo workshop with fixture sponsor, caterer and schedule", origin: "simulated" });
  return eventId;
}

export function setCurrentEvent(id: string) {
  setState((s) => ({ ...s, currentEventId: id }));
}

export function hasEvents() {
  return getState().events.length > 0;
}

export { insert };
