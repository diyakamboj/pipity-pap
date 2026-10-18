export type ID = string;
export type Origin = "simulated" | "organizer" | "live" | "system";

export interface EventRecord {
  id: ID;
  name: string;
  type: string;
  date: string; // yyyy-mm-dd
  startTime: string;
  endTime: string;
  venue: string;
  location: string;
  attendees: number;
  budget: number;
  currency: string;
  goals: string;
  constraints: string;
  existing: string;
  createdAt: string;
}

export type ReqStatus = "required" | "optional" | "declined" | "unresolved";
export type ReqCategory = "av" | "badges" | "food" | "printing" | "shirts" | "venue" | "artwork" | "other";

export interface Requirement {
  id: ID;
  eventId: ID;
  title: string;
  category: ReqCategory;
  status: ReqStatus;
  question?: string;
  quantity: number | null;
  notes: string;
  origin: Origin;
}

export type ContactKind = "speaker" | "sponsor" | "other";
export type OutreachStatus =
  | "candidate"
  | "drafted"
  | "awaiting_approval"
  | "sent_simulated"
  | "replied"
  | "committed"
  | "declined";

export interface Contact {
  id: ID;
  eventId: ID;
  kind: ContactKind;
  name: string;
  org: string;
  email: string | null;
  relevance: string;
  source: { label: string; url: string | null; retrieved: string; origin: Origin };
  status: OutreachStatus;
  lastActivity: string;
  nextStep: string;
  owner: string | null;
  unknowns: string[];
  details: Record<string, string>;
}

export type MessageStatus = "draft" | "pending_approval" | "approved" | "sent_simulated" | "rejected";
export interface Message {
  id: ID;
  eventId: ID;
  contactId: ID;
  to: string;
  subject: string;
  body: string;
  status: MessageStatus;
  updatedAt: string;
}

export type VendorStatus = "estimate" | "quote_received" | "selected" | "confirmed";
export interface Vendor {
  id: ID;
  eventId: ID;
  name: string;
  category: ReqCategory;
  url: string | null;
  priceText: string;
  unitPrice: number | null;
  fees: number | null;
  includes: string;
  minQty: number | null;
  leadTime: string | null;
  fit: string;
  unknowns: string[];
  status: VendorStatus;
  origin: Origin;
  retrieved: string;
}

export interface DocFinding {
  label: string;
  kind: "match" | "missing" | "mismatch";
  evidence: string;
}
export interface VendorDocument {
  id: ID;
  eventId: ID;
  vendorId: ID;
  name: string;
  docType: string;
  expires: string | null;
  findings: DocFinding[];
  origin: Origin;
}

export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";
export interface Task {
  id: ID;
  eventId: ID;
  title: string;
  phase: "prep" | "setup" | "event" | "teardown";
  status: TaskStatus;
  owner: string | null;
  due: string;
  dependsOn: ID[];
  related: string;
  origin: Origin;
}

export interface ScheduleItem {
  id: ID;
  eventId: ID;
  start: string;
  end: string;
  title: string;
  confirmed: boolean;
  notes: string;
}

export type ApprovalKind =
  | "send_message"
  | "accept_quote"
  | "spend"
  | "participant_instructions"
  | "schedule_change"
  | "plan_revision";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "executed";

export interface Approval {
  id: ID;
  eventId: ID;
  kind: ApprovalKind;
  title: string;
  target: string;
  payload: string;
  cost: number | null;
  evidence: string;
  reason: string;
  status: ApprovalStatus;
  approvedHash: string | null;
  refId: ID | null;
  meta?: Record<string, string | number>;
  createdAt: string;
}

export type ActivityKind = "proposed" | "changed" | "approved" | "rejected" | "executed" | "blocked" | "failed" | "created";
export interface Activity {
  id: ID;
  eventId: ID;
  at: string;
  actor: "agent" | "organizer" | "system";
  kind: ActivityKind;
  summary: string;
  origin: Origin;
  sources?: string[];
}

export interface AppState {
  version: 1;
  workspace: string;
  members: string[];
  currentEventId: ID | null;
  events: EventRecord[];
  requirements: Requirement[];
  contacts: Contact[];
  messages: Message[];
  vendors: Vendor[];
  documents: VendorDocument[];
  tasks: Task[];
  schedule: ScheduleItem[];
  approvals: Approval[];
  activity: Activity[];
}
