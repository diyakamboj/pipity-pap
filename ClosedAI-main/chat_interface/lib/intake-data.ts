export type IntakeChannel =
  | "helpdesk"
  | "email"
  | "portal"
  | "chat"
  | "system"
  | "form"
  | "phone";

export type IntakeState = "new" | "triaged" | "waiting" | "handled";

export type IntakeDisposition =
  | "auto" // Copilot can run an existing automation end-to-end
  | "assist" // Copilot drafted something, HR confirms
  | "human"; // needs a person to decide

export interface IntakeItem {
  id: string;
  subject: string;
  requester: { name: string; role: string; initials: string };
  channel: IntakeChannel;
  clusterId: string;
  /** Free-form label — clusters are discovered, not a fixed taxonomy. */
  topic: string;
  urgency: "urgent" | "high" | "normal" | "low";
  age: string;
  ageMinutes: number;
  due: string;
  state: IntakeState;
  disposition: IntakeDisposition;
  confidence: number;
  snippet: string;
  suggestion: string;
  linkedWorkId?: string;
}

export interface IntakeCluster {
  id: string;
  label: string;
  /** Where this cluster maps in the org's mental model — or "new pattern". */
  domain: string;
  discovered: boolean;
  blurb: string;
  trend: number[];
  playbook?: string;
}

export const channelMeta: Record<IntakeChannel, string> = {
  helpdesk: "Helpdesk",
  email: "HR inbox",
  portal: "Employee portal",
  chat: "Slack",
  system: "System event",
  form: "Form",
  phone: "Phone note",
};

export const dispositionMeta: Record<
  IntakeDisposition,
  { label: string; tone: string; blurb: string }
> = {
  auto: {
    label: "Copilot can handle",
    tone: "success",
    blurb:
      "Matches a known, proven playbook — so the Copilot can run it end-to-end without human touch.",
  },
  assist: {
    label: "Copilot drafted",
    tone: "primary",
    blurb:
      "The Copilot has already prepared the work (a letter, a packet, a reply) but waits for your approval before it sends or executes.",
  },
  human: {
    label: "Needs your judgement",
    tone: "warning",
    blurb:
      "The Copilot doesn't know the right move yet, so it stops and waits for a human. No automation runs until you decide.",
  },
};

export const intakeClusters: IntakeCluster[] = [
  {
    id: "verification-letters",
    label: "Verification & letters",
    domain: "Helpdesk",
    discovered: false,
    blurb: "Employment, income and visa letters requested by staff or third parties.",
    trend: [4, 6, 5, 9, 7, 11, 12],
    playbook: "auto-verification-letter",
  },
  {
    id: "onboarding-starts",
    label: "New starters & onboarding",
    domain: "Recruiting",
    discovered: false,
    blurb: "Offer-accepted events, paperwork packets, day-one readiness.",
    trend: [2, 2, 3, 3, 5, 4, 6],
    playbook: "auto-onboarding",
  },
  {
    id: "attendance-exceptions",
    label: "Attendance exceptions",
    domain: "Time & Attendance",
    discovered: false,
    blurb: "Missing punches, overtime flags and shift corrections before payroll cutoff.",
    trend: [9, 7, 12, 8, 14, 10, 9],
    playbook: "auto-attendance-exceptions",
  },
  {
    id: "leave-requests",
    label: "Leave & absence",
    domain: "Leave Management",
    discovered: false,
    blurb: "PTO, parental and unpaid leave requests plus balance disputes.",
    trend: [6, 8, 7, 7, 9, 6, 8],
    playbook: "auto-leave-triage",
  },
  {
    id: "payroll-questions",
    label: "Pay & benefits questions",
    domain: "Cross-system",
    discovered: false,
    blurb: "Payslip queries, deductions, benefit enrolment changes.",
    trend: [5, 4, 6, 6, 8, 7, 9],
  },
  {
    id: "relocation-visa",
    label: "Relocation & work authorisation",
    domain: "New pattern",
    discovered: true,
    blurb:
      "Emerged this week from 5 unrelated requests about the Lisbon office move. No playbook yet.",
    trend: [0, 0, 1, 1, 2, 3, 5],
  },
  {
    id: "policy-clarifications",
    label: "Policy clarifications",
    domain: "New pattern",
    discovered: true,
    blurb: "Questions about the updated remote-work policy — spiking since Monday's announcement.",
    trend: [0, 1, 0, 4, 6, 9, 7],
  },
  {
    id: "employee-relations",
    label: "Employee relations & sensitive",
    domain: "Restricted",
    discovered: false,
    blurb: "Grievances and conduct reports. Never auto-actioned — routed to you only.",
    trend: [1, 0, 1, 2, 1, 1, 2],
  },
];

export const intakeItems: IntakeItem[] = [
  {
    id: "IN-8841",
    subject: "Employment verification for mortgage lender",
    requester: { name: "Sarah Chen", role: "Senior Product Manager", initials: "SC" },
    channel: "helpdesk",
    clusterId: "verification-letters",
    topic: "Verification letter · includes salary",
    urgency: "normal",
    age: "22m",
    ageMinutes: 22,
    due: "Tomorrow 5pm",
    state: "triaged",
    disposition: "assist",
    confidence: 0.94,
    snippet:
      "My lender needs a letter confirming employment, title, start date and annual compensation.",
    suggestion: "Letter drafted from the employee record; salary disclosure needs sign-off.",
    linkedWorkId: "WRK-2038",
  },
  {
    id: "IN-8840",
    subject: "Offer accepted — Joe Marchetti, Product Designer",
    requester: { name: "Recruiting ATS", role: "System event", initials: "AT" },
    channel: "system",
    clusterId: "onboarding-starts",
    topic: "New starter · 1 Sep",
    urgency: "urgent",
    age: "31m",
    ageMinutes: 31,
    due: "Today 1pm",
    state: "triaged",
    disposition: "assist",
    confidence: 0.97,
    snippet: "Candidate accepted. Start date 2026-09-01. Onboarding packet not yet issued.",
    suggestion: "Packet complete — approve to send for e-signature.",
    linkedWorkId: "WRK-2041",
  },
  {
    id: "IN-8839",
    subject: "6 missing punches — Seattle warehouse",
    requester: { name: "Time & Attendance", role: "System event", initials: "TA" },
    channel: "system",
    clusterId: "attendance-exceptions",
    topic: "Missing punches · pay period 08/01–08/15",
    urgency: "high",
    age: "1h",
    ageMinutes: 62,
    due: "Payroll cutoff 5pm",
    state: "triaged",
    disposition: "assist",
    confidence: 0.88,
    snippet: "Six exceptions flagged before payroll close. Five match badge access logs.",
    suggestion: "One shift needs a manager attestation before corrections push to payroll.",
    linkedWorkId: "WRK-2036",
  },
  {
    id: "IN-8838",
    subject: "Can I carry over unused PTO into next year?",
    requester: { name: "Dan Okafor", role: "Warehouse Associate", initials: "DO" },
    channel: "chat",
    clusterId: "leave-requests",
    topic: "Balance question · carry-over",
    urgency: "low",
    age: "1h",
    ageMinutes: 74,
    due: "3 days",
    state: "new",
    disposition: "auto",
    confidence: 0.91,
    snippet: "I've got 6 days left and I'm not going to use them before December.",
    suggestion: "Answer from the leave policy and attach his current balance.",
  },
  {
    id: "IN-8837",
    subject: "Parental leave — expecting in November",
    requester: { name: "Amara Diallo", role: "Staff Engineer", initials: "AD" },
    channel: "portal",
    clusterId: "leave-requests",
    topic: "Parental leave · plan required",
    urgency: "normal",
    age: "2h",
    ageMinutes: 128,
    due: "This week",
    state: "new",
    disposition: "assist",
    confidence: 0.79,
    snippet: "Wanted to start the paperwork early and understand the top-up policy.",
    suggestion: "Build an entitlement summary and a draft leave plan for review.",
  },
  {
    id: "IN-8836",
    subject: "Deduction on August payslip I don't recognise",
    requester: { name: "Marcus Webb", role: "Account Executive", initials: "MW" },
    channel: "email",
    clusterId: "payroll-questions",
    topic: "Payslip discrepancy",
    urgency: "high",
    age: "3h",
    ageMinutes: 186,
    due: "Today",
    state: "new",
    disposition: "assist",
    confidence: 0.72,
    snippet: "There's a $180 line called 'BEN-ADJ' I've never seen before.",
    suggestion: "Reconcile against the benefits change log, then reply with a breakdown.",
  },
  {
    id: "IN-8835",
    subject: "Does the new remote policy apply to contractors?",
    requester: { name: "Priya Raman", role: "Engineering Manager", initials: "PR" },
    channel: "chat",
    clusterId: "policy-clarifications",
    topic: "Remote-work policy · scope",
    urgency: "normal",
    age: "4h",
    ageMinutes: 240,
    due: "2 days",
    state: "new",
    disposition: "human",
    confidence: 0.41,
    snippet: "The announcement says 'employees' — my team has four long-term contractors.",
    suggestion: "Policy is ambiguous. Decide once and I'll answer the other 6 like it.",
  },
  {
    id: "IN-8834",
    subject: "Which days count as core hours in the new policy?",
    requester: { name: "Tom Whitfield", role: "Support Lead", initials: "TW" },
    channel: "chat",
    clusterId: "policy-clarifications",
    topic: "Remote-work policy · core hours",
    urgency: "low",
    age: "5h",
    ageMinutes: 300,
    due: "2 days",
    state: "new",
    disposition: "human",
    confidence: 0.38,
    snippet: "Tuesday/Thursday anchor days were mentioned but the doc says three days.",
    suggestion: "Same root ambiguity as IN-8835 — resolve together.",
  },
  {
    id: "IN-8833",
    subject: "Relocating to Lisbon — what happens to my contract?",
    requester: { name: "Elena Ruiz", role: "Data Analyst", initials: "ER" },
    channel: "email",
    clusterId: "relocation-visa",
    topic: "Relocation · entity change",
    urgency: "high",
    age: "6h",
    ageMinutes: 360,
    due: "This week",
    state: "new",
    disposition: "human",
    confidence: 0.29,
    snippet: "My partner's job is moving us in October. Can I stay on the same team?",
    suggestion: "No playbook exists. Five similar requests arrived this week.",
  },
  {
    id: "IN-8832",
    subject: "Work permit renewal — expires in 60 days",
    requester: { name: "Kenji Watanabe", role: "Security Engineer", initials: "KW" },
    channel: "form",
    clusterId: "relocation-visa",
    topic: "Work authorisation · renewal",
    urgency: "urgent",
    age: "7h",
    ageMinutes: 420,
    due: "Today",
    state: "new",
    disposition: "human",
    confidence: 0.34,
    snippet: "Immigration counsel needs an HR letter and the last 6 payslips.",
    suggestion: "Letter + payslips can be assembled; filing route needs your call.",
  },
  {
    id: "IN-8831",
    subject: "Confidential: concern about a manager's conduct",
    requester: { name: "Withheld", role: "Restricted", initials: "··" },
    channel: "form",
    clusterId: "employee-relations",
    topic: "Grievance · restricted handling",
    urgency: "urgent",
    age: "8h",
    ageMinutes: 480,
    due: "Today",
    state: "new",
    disposition: "human",
    confidence: 0,
    snippet: "Content hidden. Restricted-handling rule matched — the Copilot did not read this.",
    suggestion: "Opened for you only. Nothing was indexed or actioned.",
  },
  {
    id: "IN-8830",
    subject: "Visa support letter for spouse application",
    requester: { name: "Aisha Karim", role: "Finance Analyst", initials: "AK" },
    channel: "email",
    clusterId: "verification-letters",
    topic: "Verification letter · immigration",
    urgency: "normal",
    age: "9h",
    ageMinutes: 540,
    due: "2 days",
    state: "new",
    disposition: "auto",
    confidence: 0.9,
    snippet: "The consulate wants confirmation of employment and salary on letterhead.",
    suggestion: "Standard template, no salary disclosure exception needed.",
  },
  {
    id: "IN-8829",
    subject: "Benefit enrolment change after marriage",
    requester: { name: "Luis Ferreira", role: "Solutions Architect", initials: "LF" },
    channel: "portal",
    clusterId: "payroll-questions",
    topic: "Benefits · qualifying life event",
    urgency: "normal",
    age: "11h",
    ageMinutes: 660,
    due: "5 days",
    state: "waiting",
    disposition: "auto",
    confidence: 0.86,
    snippet: "Adding my spouse to the medical plan, effective from the wedding date.",
    suggestion: "Waiting on the marriage certificate upload; will proceed automatically.",
  },
  {
    id: "IN-8828",
    subject: "Overtime flag — 3 engineers above threshold",
    requester: { name: "Time & Attendance", role: "System event", initials: "TA" },
    channel: "system",
    clusterId: "attendance-exceptions",
    topic: "Overtime threshold breach",
    urgency: "normal",
    age: "13h",
    ageMinutes: 780,
    due: "Tomorrow",
    state: "handled",
    disposition: "auto",
    confidence: 0.93,
    snippet: "Three engineers exceeded 48h in the week ending 08/09.",
    suggestion: "Manager notifications sent, compliance log updated.",
  },
  {
    id: "IN-8827",
    subject: "Reference request for former employee",
    requester: { name: "Northwind Talent", role: "External recruiter", initials: "NT" },
    channel: "email",
    clusterId: "verification-letters",
    topic: "Reference · ex-employee",
    urgency: "low",
    age: "1d",
    ageMinutes: 1500,
    due: "3 days",
    state: "handled",
    disposition: "auto",
    confidence: 0.95,
    snippet: "Confirming dates of employment for a candidate who left in 2024.",
    suggestion: "Dates-only response sent per policy.",
  },
];

export function itemsForCluster(clusterId: string) {
  return intakeItems.filter((i) => i.clusterId === clusterId);
}

export const intakeStats = {
  open: intakeItems.filter((i) => i.state !== "handled").length,
  needsJudgement: intakeItems.filter((i) => i.disposition === "human" && i.state !== "handled")
    .length,
  readyToRelease: intakeItems.filter((i) => i.disposition === "auto" && i.state === "new").length,
  newPatterns: intakeClusters.filter((c) => c.discovered).length,
  arrivedToday: 34,
  autoAbsorbed: 22,
};
