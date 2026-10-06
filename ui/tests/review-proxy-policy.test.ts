import { describe, expect, it } from "vitest";
import { isAllowedReviewApiPath } from "../lib/api/review-proxy-policy";

const id = "a".repeat(64);

describe("review proxy policy", () => {
  it("allows only capabilities and exact review or approval threads", () => {
    expect(isAllowedReviewApiPath(["api", "v1", "review-capabilities"])).toBe(true);
    expect(isAllowedReviewApiPath(["api", "v1", "claims", id, "reviews"])).toBe(true);
    expect(isAllowedReviewApiPath(["api", "v1", "claims", id, "approvals"])).toBe(true);
    expect(
      isAllowedReviewApiPath(["api", "v1", "claims", id, "approvals", id, "revoke"]),
    ).toBe(true);
    expect(
      isAllowedReviewApiPath(["api", "v1", "claims", id, "approvals", id, "supersede"]),
    ).toBe(true);
  });

  it("denies invented approval routes, traversal, collection expansion, and malformed identities", () => {
    expect(isAllowedReviewApiPath(["api", "v1", "claims", id, "approve"])).toBe(false);
    expect(isAllowedReviewApiPath(["api", "v1", "claims", "..", "reviews"])).toBe(false);
    expect(isAllowedReviewApiPath(["api", "v1", "claims", id])).toBe(false);
    expect(isAllowedReviewApiPath(["api", "v1", "reviews"])).toBe(false);
    expect(
      isAllowedReviewApiPath(["api", "v1", "claims", id, "approvals", "bad", "revoke"]),
    ).toBe(false);
    expect(
      isAllowedReviewApiPath(["api", "v1", "claims", id, "approvals", id, "delete"]),
    ).toBe(false);
  });
});
