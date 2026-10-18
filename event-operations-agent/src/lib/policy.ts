// Shared action policy. Evaluated on the server before any approval-gated action runs.
export type ActionKind =
  | "send_message"
  | "accept_quote"
  | "spend"
  | "participant_instructions"
  | "schedule_change"
  | "plan_revision"
  | "create_task"
  | "create_draft"
  | "make_payment"
  | "sign_form"
  | "submit_form"
  | "publish_content";

export const ALWAYS_BLOCKED: ActionKind[] = ["make_payment", "sign_form", "submit_form", "publish_content"];
export const NEEDS_APPROVAL: ActionKind[] = [
  "send_message",
  "accept_quote",
  "spend",
  "participant_instructions",
  "schedule_change",
  "plan_revision",
];

export function hashPayload(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(16);
}

export interface PolicyInput {
  kind: ActionKind;
  payload: string;
  approvalStatus?: string | null;
  approvedHash?: string | null;
}
export type PolicyResult = { allowed: true; delivery: "internal" | "simulated" } | { allowed: false; reason: string };

export function evaluatePolicy(input: PolicyInput): PolicyResult {
  if (ALWAYS_BLOCKED.includes(input.kind)) {
    const why: Record<string, string> = {
      make_payment: "Payments and purchases are disabled. The agent cannot spend money.",
      sign_form: "Signatures and legal attestations must be made by a human.",
      submit_form: "Legal forms are never submitted automatically.",
      publish_content: "Public content is never published automatically.",
    };
    return { allowed: false, reason: why[input.kind] };
  }
  if (NEEDS_APPROVAL.includes(input.kind)) {
    if (input.approvalStatus !== "approved" || !input.approvedHash)
      return { allowed: false, reason: "This action requires explicit organizer approval." };
    if (input.approvedHash !== hashPayload(input.payload))
      return { allowed: false, reason: "The action changed after it was approved. Re-approval is required." };
    return { allowed: true, delivery: input.kind === "send_message" || input.kind === "participant_instructions" ? "simulated" : "internal" };
  }
  return { allowed: true, delivery: "internal" };
}
