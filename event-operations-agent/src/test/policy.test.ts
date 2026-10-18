import { describe, expect, it } from "vitest";
import { evaluatePolicy, hashPayload } from "@/lib/policy";

describe("action policy", () => {
  it("always blocks payments", () => {
    expect(evaluatePolicy({ kind: "make_payment", payload: "x" }).allowed).toBe(false);
  });
  it("requires approval for external messages", () => {
    expect(evaluatePolicy({ kind: "send_message", payload: "hi", approvalStatus: "pending" }).allowed).toBe(false);
  });
  it("rejects an approval for different content", () => {
    expect(evaluatePolicy({ kind: "send_message", payload: "edited", approvalStatus: "approved", approvedHash: hashPayload("hi") }).allowed).toBe(false);
  });
  it("allows approved unchanged message as simulated send", () => {
    expect(evaluatePolicy({ kind: "send_message", payload: "hi", approvalStatus: "approved", approvedHash: hashPayload("hi") })).toEqual({ allowed: true, delivery: "simulated" });
  });
  it("allows internal task creation", () => {
    expect(evaluatePolicy({ kind: "create_task", payload: "t" }).allowed).toBe(true);
  });
});
