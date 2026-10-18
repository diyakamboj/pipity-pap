import { createServerFn } from "@tanstack/react-start";
import { evaluatePolicy, type ActionKind, type PolicyInput } from "./policy";

const KINDS: ActionKind[] = [
  "send_message", "accept_quote", "spend", "participant_instructions", "schedule_change", "plan_revision",
  "create_task", "create_draft", "make_payment", "sign_form", "submit_form", "publish_content",
];

// Server-side gate: every consequential action is checked here before the client applies it.
export const authorizeAction = createServerFn({ method: "POST" })
  .inputValidator((input: PolicyInput) => {
    if (!input || !KINDS.includes(input.kind)) throw new Error("Unknown action kind");
    if (typeof input.payload !== "string" || input.payload.length > 20000) throw new Error("Invalid payload");
    return input;
  })
  .handler(async ({ data }) => {
    const result = evaluatePolicy(data);
    return { ...result, checkedAt: new Date().toISOString() };
  });
