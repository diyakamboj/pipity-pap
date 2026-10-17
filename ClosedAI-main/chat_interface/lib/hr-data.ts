export type WorkSource =
  | "ticketing"
  | "recruiting"
  | "attendance"
  | "leave"
  | "documents"
  | "adhoc";

export type WorkStatus =
  | "needs_approval"
  | "running"
  | "queued"
  | "blocked"
  | "completed";

export type StepState = "done" | "active" | "pending" | "approval" | "failed";

export interface RunStep {
  id: string;
  label: string;
  detail?: string;
  state: StepState;
  duration?: string;
  system?: string;
}

export interface ChatMessage {
  id: string;
  role: "agent" | "user";
  time: string;
  body: string;
  approval?: {
    title: string;
    description: string;
    target: string;
  };
}

export interface WorkItem {
  id: string;
  title: string;
  source: WorkSource;
  category: string;
  subject: { name: string; role: string; initials: string };
  status: WorkStatus;
  automation?: string;
  priority: "urgent" | "high" | "normal";
  sla: string;
  updated: string;
  externalRef: string;
  progress: number;
  summary: string;
  steps: RunStep[];
  messages: ChatMessage[];
  canvas: { kind: "documents" | "checklist" | "record"; items: CanvasItem[] };
}

export interface CanvasItem {
  label: string;
  value: string;
  state?: "ok" | "pending" | "warn";
}

export const sourceMeta: Record<WorkSource, { label: string; system: string }> = {
  ticketing: { label: "Ticket", system: "Helpdesk" },
  recruiting: { label: "Hiring", system: "Recruiting ATS" },
  attendance: { label: "Attendance", system: "Time & Attendance" },
  leave: { label: "Leave", system: "Leave Management" },
  documents: { label: "Documents", system: "Employee Portal" },
  adhoc: { label: "Ad hoc", system: "Copilot" },
};

export const statusMeta: Record<WorkStatus, { label: string; tone: string }> = {
  needs_approval: { label: "Needs approval", tone: "warning" },
  running: { label: "Agent running", tone: "primary" },
  queued: { label: "Queued", tone: "muted" },
  blocked: { label: "Blocked", tone: "destructive" },
  completed: { label: "Completed", tone: "success" },
};

export const workItems: WorkItem[] = [
  {
    id: "WRK-2041",
    title: "Onboard Joe Marchetti — Product Designer",
    source: "recruiting",
    category: "Onboarding",
    subject: { name: "Joe Marchetti", role: "Product Designer", initials: "JM" },
    status: "needs_approval",
    automation: "auto-onboarding",
    priority: "urgent",
    sla: "Due in 3h",
    updated: "2 min ago",
    externalRef: "ATS-8871 · offer accepted",
    progress: 68,
    summary:
      "Offer accepted in the recruiting system. Copilot collected personal info, retrieved the onboarding packet and completed 4 of 5 documents. Sending to the employee portal for signature needs your approval.",
    steps: [
      {
        id: "s1",
        label: "Pull hiring event from ATS",
        detail: "candidate: Joe Marchetti · start date 2026-09-01",
        state: "done",
        duration: "0.4s",
        system: "Recruiting ATS",
      },
      {
        id: "s2",
        label: "Collect personal information",
        detail: "address, tax ID, emergency contact — from candidate portal",
        state: "done",
        duration: "1.2s",
        system: "Shared data layer",
      },
      {
        id: "s3",
        label: "Retrieve onboarding paperwork",
        detail: "5 documents from HR document library",
        state: "done",
        duration: "0.9s",
        system: "Document store",
      },
      {
        id: "s4",
        label: "Complete required fields",
        detail: "I-9, W-4, NDA, equipment agreement auto-filled",
        state: "done",
        duration: "2.6s",
      },
      {
        id: "s5",
        label: "Send packet to employee portal for signing",
        detail: "awaiting HR approval before dispatch",
        state: "approval",
        system: "Employee Portal",
      },
      { id: "s6", label: "Route NDA to Legal for counter-signature", state: "pending" },
      { id: "s7", label: "Create IT + payroll downstream tasks", state: "pending" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "9:41",
        body: "Picked up an onboarding event for Joe Marchetti (Product Designer, start 1 Sep). I'll run the onboarding automation and check in with you before anything leaves the building.",
      },
      {
        id: "m2",
        role: "agent",
        time: "9:41",
        body: "Collected personal info from the candidate portal and retrieved the 5-document onboarding packet. Employee record is missing a direct deposit form — I flagged it on the canvas.",
      },
      {
        id: "m3",
        role: "user",
        time: "9:43",
        body: "Skip direct deposit for now, payroll collects that separately.",
      },
      {
        id: "m4",
        role: "agent",
        time: "9:43",
        body: "Understood — direct deposit removed from this packet. I've completed the I-9, W-4, NDA and equipment agreement using the shared employee record.",
      },
      {
        id: "m5",
        role: "agent",
        time: "9:44",
        body: "The packet is ready to send to Joe's employee portal for e-signature. This action leaves our system, so it needs your approval.",
        approval: {
          title: "Send onboarding packet for signature",
          description: "4 documents · e-signature request to joe.marchetti@example.com",
          target: "Employee Portal",
        },
      },
    ],
    canvas: {
      kind: "documents",
      items: [
        { label: "I-9 Employment Eligibility", value: "Completed · 12/12 fields", state: "ok" },
        { label: "W-4 Withholding", value: "Completed · 9/9 fields", state: "ok" },
        { label: "Mutual NDA", value: "Completed · needs Legal counter-sign", state: "warn" },
        { label: "Equipment agreement", value: "Completed · MacBook Pro 16", state: "ok" },
        { label: "Direct deposit", value: "Excluded by HR", state: "pending" },
      ],
    },
  },
  {
    id: "WRK-2038",
    title: "Employment verification letter for mortgage lender",
    source: "ticketing",
    category: "Document request",
    subject: { name: "Sarah Chen", role: "Senior Product Manager", initials: "SC" },
    status: "running",
    automation: "auto-verification-letter",
    priority: "normal",
    sla: "Due tomorrow",
    updated: "just now",
    externalRef: "TCK-45120 · HR queue",
    progress: 42,
    summary:
      "Ticket from the helpdesk. Copilot is generating a verification letter from the shared employee record and will ask before releasing salary details externally.",
    steps: [
      { id: "s1", label: "Read ticket TCK-45120", state: "done", duration: "0.2s", system: "Helpdesk" },
      { id: "s2", label: "Look up employee record", detail: "Sarah Chen · E1001", state: "done", duration: "64ms" },
      { id: "s3", label: "Draft verification letter", state: "active", system: "Document store" },
      { id: "s4", label: "Approve salary disclosure", state: "approval" },
      { id: "s5", label: "Reply on ticket with attachment", state: "pending" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "10:02",
        body: "Ticket TCK-45120 asks for an employment verification letter including compensation. Pulling Sarah Chen's record now.",
      },
      {
        id: "m2",
        role: "agent",
        time: "10:02",
        body: "Drafting the letter on the canvas. I'll pause before including salary — that usually needs sign-off.",
      },
    ],
    canvas: {
      kind: "record",
      items: [
        { label: "Employee", value: "Sarah Chen · E1001", state: "ok" },
        { label: "Title", value: "Senior Product Manager", state: "ok" },
        { label: "Start date", value: "2021-03-15", state: "ok" },
        { label: "Compensation", value: "$165,000 / annual — pending disclosure approval", state: "warn" },
        { label: "Letterhead", value: "US entity template v4", state: "ok" },
      ],
    },
  },
  {
    id: "WRK-2036",
    title: "Missing punches — 6 employees, Seattle warehouse",
    source: "attendance",
    category: "Attendance exception",
    subject: { name: "Seattle Ops", role: "6 employees", initials: "SO" },
    status: "needs_approval",
    automation: "auto-attendance-exceptions",
    priority: "high",
    sla: "Payroll cutoff 5pm",
    updated: "14 min ago",
    externalRef: "ATT-9932 · pay period 08/01–08/15",
    progress: 80,
    summary:
      "Attendance system flagged 6 missing punches before payroll cutoff. Copilot reconciled 5 from badge logs; 1 needs a manager attestation you must approve.",
    steps: [
      { id: "s1", label: "Ingest attendance exceptions", state: "done", duration: "0.3s", system: "Time & Attendance" },
      { id: "s2", label: "Reconcile against badge logs", detail: "5 of 6 resolved automatically", state: "done", duration: "3.1s" },
      { id: "s3", label: "Request manager attestation", detail: "Priya Nair · R. Okafor shift", state: "approval" },
      { id: "s4", label: "Push corrections to payroll", state: "pending" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "9:28",
        body: "6 missing punches surfaced for the 08/01–08/15 period. I matched 5 against badge access logs with high confidence.",
      },
      {
        id: "m2",
        role: "agent",
        time: "9:30",
        body: "R. Okafor's Thursday night shift has no badge trail. I've drafted an attestation request to Priya Nair — approve to send.",
        approval: {
          title: "Send manager attestation request",
          description: "R. Okafor · Thu 08/07 night shift · 8.0h claimed",
          target: "Priya Nair (Manager)",
        },
      },
    ],
    canvas: {
      kind: "checklist",
      items: [
        { label: "M. Alvarez", value: "Reconciled from badge log", state: "ok" },
        { label: "T. Whitfield", value: "Reconciled from badge log", state: "ok" },
        { label: "J. Park", value: "Reconciled from badge log", state: "ok" },
        { label: "L. Duarte", value: "Reconciled from badge log", state: "ok" },
        { label: "K. Osei", value: "Reconciled from badge log", state: "ok" },
        { label: "R. Okafor", value: "No badge trail · attestation required", state: "warn" },
      ],
    },
  },
  {
    id: "WRK-2033",
    title: "Parental leave request — 12 weeks starting Oct 6",
    source: "leave",
    category: "Leave case",
    subject: { name: "Daniel Osei", role: "Account Executive", initials: "DO" },
    status: "queued",
    automation: "auto-leave-case",
    priority: "normal",
    sla: "Due in 2 days",
    updated: "1 hr ago",
    externalRef: "LV-3312 · manager approved",
    progress: 10,
    summary:
      "Leave system approved the request. Copilot will assemble the leave packet, check policy eligibility and schedule coverage handoff tasks.",
    steps: [
      { id: "s1", label: "Ingest approved leave event", state: "done", duration: "0.2s", system: "Leave Management" },
      { id: "s2", label: "Check policy eligibility", state: "pending" },
      { id: "s3", label: "Generate leave confirmation packet", state: "pending" },
      { id: "s4", label: "Create coverage handoff tasks", state: "pending" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "8:55",
        body: "Queued behind two urgent items. Say the word and I'll start the leave case for Daniel Osei now.",
      },
    ],
    canvas: {
      kind: "checklist",
      items: [
        { label: "Requested dates", value: "Oct 6 – Dec 29 (12 weeks)", state: "ok" },
        { label: "Tenure check", value: "Not yet run", state: "pending" },
        { label: "State top-up", value: "Not yet run", state: "pending" },
        { label: "Coverage plan", value: "Not yet drafted", state: "pending" },
      ],
    },
  },
  {
    id: "WRK-2029",
    title: "Bulk policy acknowledgement — updated remote work policy",
    source: "documents",
    category: "Policy rollout",
    subject: { name: "All staff", role: "412 employees", initials: "AS" },
    status: "blocked",
    automation: "auto-policy-ack",
    priority: "high",
    sla: "Overdue by 1 day",
    updated: "3 hrs ago",
    externalRef: "DOC-1188 · policy v7",
    progress: 55,
    summary:
      "Copilot dispatched 412 acknowledgement requests but the employee portal rejected 38 sends with stale email addresses. Needs a data fix before retrying.",
    steps: [
      { id: "s1", label: "Retrieve policy v7 + distribution list", state: "done", duration: "1.1s" },
      { id: "s2", label: "Dispatch acknowledgement requests", detail: "374 sent · 38 failed", state: "done", duration: "22s", system: "Employee Portal" },
      { id: "s3", label: "Retry failed recipients", detail: "invalid_email_address (38)", state: "failed" },
      { id: "s4", label: "Compile completion report", state: "pending" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "7:12",
        body: "374 of 412 acknowledgements delivered. 38 failed — the portal returned invalid_email_address for contractors synced from the old HRIS.",
      },
      {
        id: "m2",
        role: "agent",
        time: "7:13",
        body: "I can't correct records in the source system. Options: open a data ticket with IT, or route these 38 to their managers instead.",
      },
    ],
    canvas: {
      kind: "checklist",
      items: [
        { label: "Delivered", value: "374 recipients", state: "ok" },
        { label: "Acknowledged", value: "201 recipients", state: "ok" },
        { label: "Failed", value: "38 recipients · invalid email", state: "warn" },
        { label: "Report", value: "Blocked until retries clear", state: "pending" },
      ],
    },
  },
  {
    id: "WRK-2024",
    title: "Offboarding checklist — final pay and asset return",
    source: "ticketing",
    category: "Offboarding",
    subject: { name: "Mia Fernandes", role: "Support Lead", initials: "MF" },
    status: "completed",
    automation: "auto-offboarding",
    priority: "normal",
    sla: "Closed on time",
    updated: "Yesterday",
    externalRef: "TCK-44980 · resolved",
    progress: 100,
    summary:
      "Full offboarding run completed: access revoked, final pay calculated, asset return scheduled, exit documents archived.",
    steps: [
      { id: "s1", label: "Revoke system access", state: "done", duration: "1.4s", system: "IT" },
      { id: "s2", label: "Calculate final pay + PTO payout", state: "done", duration: "0.8s", system: "Payroll" },
      { id: "s3", label: "Schedule asset return", state: "done", duration: "0.5s" },
      { id: "s4", label: "Archive exit documents", state: "done", duration: "0.3s" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "Yesterday",
        body: "Offboarding for Mia Fernandes is complete. Final pay of $6,412.90 including 38h PTO payout was sent to payroll and the exit packet is archived.",
      },
    ],
    canvas: {
      kind: "checklist",
      items: [
        { label: "Access revoked", value: "12 systems", state: "ok" },
        { label: "Final pay", value: "$6,412.90 · payroll batch 08-14", state: "ok" },
        { label: "Assets", value: "Return label sent · due Aug 20", state: "ok" },
        { label: "Exit documents", value: "Archived to employee file", state: "ok" },
      ],
    },
  },
  {
    id: "WRK-2019",
    title: "Explain PTO carryover rules for EU contractors",
    source: "adhoc",
    category: "Ad hoc request",
    subject: { name: "Priya Nair", role: "HR Business Partner", initials: "PN" },
    status: "completed",
    priority: "normal",
    sla: "Closed",
    updated: "Yesterday",
    externalRef: "No automation · ad hoc chat",
    progress: 100,
    summary:
      "No matching automation. Handled directly in chat: Copilot read the policy library and drafted a response Priya could forward.",
    steps: [
      { id: "s1", label: "Search policy library", detail: "3 documents matched", state: "done", duration: "0.6s" },
      { id: "s2", label: "Draft explanation", state: "done", duration: "1.9s" },
    ],
    messages: [
      {
        id: "m1",
        role: "agent",
        time: "Yesterday",
        body: "EU contractors follow local statutory carryover, not the US 5-day cap. I drafted a summary per country on the canvas — worth turning into an automation if this repeats.",
      },
    ],
    canvas: {
      kind: "record",
      items: [
        { label: "Germany", value: "Statutory carryover to Mar 31", state: "ok" },
        { label: "Netherlands", value: "Statutory days expire after 6 months", state: "ok" },
        { label: "Ireland", value: "Carryover by written agreement only", state: "ok" },
      ],
    },
  },
];

export interface Automation {
  id: string;
  name: string;
  trigger: string;
  source: WorkSource;
  steps: number;
  approvals: number;
  runs30d: number;
  successRate: number;
  avgTime: string;
  status: "live" | "draft" | "paused";
  description: string;
}

export const automations: Automation[] = [
  {
    id: "auto-onboarding",
    name: "Employee onboarding",
    trigger: "Offer accepted in Recruiting ATS",
    source: "recruiting",
    steps: 7,
    approvals: 2,
    runs30d: 34,
    successRate: 94,
    avgTime: "6m 20s",
    status: "live",
    description:
      "Collect personal info, retrieve and complete the onboarding packet, send for signature, route NDA to Legal, create IT and payroll tasks.",
  },
  {
    id: "auto-verification-letter",
    name: "Employment verification letter",
    trigger: "Helpdesk ticket · category HR/Documents",
    source: "ticketing",
    steps: 5,
    approvals: 1,
    runs30d: 88,
    successRate: 99,
    avgTime: "48s",
    status: "live",
    description:
      "Read the ticket, pull the employee record, generate the letter and reply on the ticket after disclosure approval.",
  },
  {
    id: "auto-attendance-exceptions",
    name: "Attendance exception reconciliation",
    trigger: "Attendance exception before payroll cutoff",
    source: "attendance",
    steps: 4,
    approvals: 1,
    runs30d: 26,
    successRate: 91,
    avgTime: "3m 05s",
    status: "live",
    description:
      "Reconcile missing punches against badge logs, request manager attestation where ambiguous, push corrections to payroll.",
  },
  {
    id: "auto-leave-case",
    name: "Leave case assembly",
    trigger: "Leave approved in Leave Management",
    source: "leave",
    steps: 4,
    approvals: 1,
    runs30d: 19,
    successRate: 97,
    avgTime: "2m 41s",
    status: "live",
    description:
      "Check policy eligibility, generate the confirmation packet, schedule coverage handoffs and update HR systems.",
  },
  {
    id: "auto-policy-ack",
    name: "Policy acknowledgement rollout",
    trigger: "New policy version published",
    source: "documents",
    steps: 4,
    approvals: 1,
    runs30d: 4,
    successRate: 72,
    avgTime: "31m",
    status: "live",
    description:
      "Distribute policy acknowledgements to a population, chase non-responders and compile a completion report.",
  },
  {
    id: "auto-offboarding",
    name: "Employee offboarding",
    trigger: "Termination ticket · HR queue",
    source: "ticketing",
    steps: 6,
    approvals: 2,
    runs30d: 11,
    successRate: 100,
    avgTime: "4m 12s",
    status: "live",
    description:
      "Revoke access, calculate final pay, schedule asset return, archive exit documents and notify downstream teams.",
  },
  {
    id: "auto-badge-reissue",
    name: "Badge reissue request",
    trigger: "Helpdesk ticket · category Facilities/Badge",
    source: "ticketing",
    steps: 3,
    approvals: 0,
    runs30d: 0,
    successRate: 0,
    avgTime: "—",
    status: "draft",
    description:
      "Drafted from 9 similar ad hoc chats. Verify identity, create the facilities request, notify the employee.",
  },
  {
    id: "auto-tuition-reimbursement",
    name: "Tuition reimbursement review",
    trigger: "Helpdesk ticket · category HR/Benefits",
    source: "ticketing",
    steps: 5,
    approvals: 1,
    runs30d: 6,
    successRate: 83,
    avgTime: "5m 58s",
    status: "paused",
    description:
      "Paused while Finance finalises the FY27 policy caps. Validate eligibility, check spend, route to Finance for payment.",
  },
];

export interface ConnectedSystem {
  name: string;
  kind: string;
  status: "live" | "degraded";
  inbound: string;
  lastSync: string;
}

export const connectedSystems: ConnectedSystem[] = [
  { name: "Helpdesk / Ticketing", kind: "Requests", status: "live", inbound: "42 open HR tickets", lastSync: "12s ago" },
  { name: "Recruiting ATS", kind: "Hiring events", status: "live", inbound: "5 accepted offers", lastSync: "38s ago" },
  { name: "Time & Attendance", kind: "Exceptions", status: "live", inbound: "6 exceptions", lastSync: "1m ago" },
  { name: "Leave Management", kind: "Leave events", status: "live", inbound: "3 approved leaves", lastSync: "2m ago" },
  { name: "Employee Portal", kind: "Documents & signing", status: "degraded", inbound: "38 failed sends", lastSync: "4m ago" },
  { name: "Payroll", kind: "Downstream actions", status: "live", inbound: "corrections queue", lastSync: "5m ago" },
];

export interface ActivityEvent {
  id: string;
  time: string;
  workId: string;
  text: string;
  tone: "primary" | "warning" | "success" | "destructive" | "muted";
}

export const activityFeed: ActivityEvent[] = [
  { id: "a1", time: "10:02", workId: "WRK-2038", text: "Drafting verification letter for Sarah Chen", tone: "primary" },
  { id: "a2", time: "9:44", workId: "WRK-2041", text: "Waiting on approval to send Joe's onboarding packet", tone: "warning" },
  { id: "a3", time: "9:30", workId: "WRK-2036", text: "Attestation request drafted for R. Okafor's shift", tone: "warning" },
  { id: "a4", time: "9:28", workId: "WRK-2036", text: "Reconciled 5 of 6 missing punches from badge logs", tone: "success" },
  { id: "a5", time: "7:13", workId: "WRK-2029", text: "38 acknowledgement sends rejected by Employee Portal", tone: "destructive" },
  { id: "a6", time: "Yesterday", workId: "WRK-2024", text: "Offboarding for Mia Fernandes completed", tone: "success" },
  { id: "a7", time: "Yesterday", workId: "WRK-2019", text: "Ad hoc PTO carryover question answered from policy library", tone: "muted" },
];

export function getWorkItem(id: string) {
  return workItems.find((w) => w.id.toLowerCase() === id.toLowerCase());
}

export function getAutomation(id: string) {
  return automations.find((a) => a.id === id);
}

export const inboxCounts = {
  needsApproval: workItems.filter((w) => w.status === "needs_approval").length,
  running: workItems.filter((w) => w.status === "running").length,
  queued: workItems.filter((w) => w.status === "queued").length,
  blocked: workItems.filter((w) => w.status === "blocked").length,
  completedToday: 14,
  hoursSaved: "31h",
  autoResolved: "68%",
};
