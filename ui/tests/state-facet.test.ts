import { describe, expect, it } from "vitest";
import { stateFacetPresentation } from "../lib/semantics/state";

describe("stateFacetPresentation", () => {
  it("keeps unknown values neutral instead of inferring success", () => {
    expect(stateFacetPresentation("brand-new-state")).toEqual({ label: "Unrecognized state: brand-new-state", tone: "default" });
  });

  it("does not style requires-human-approval as success", () => {
    expect(stateFacetPresentation("requires-human-approval").tone).toBe("warning");
  });

  it("uses the canonical claim-profile decision vocabulary without inventing severity", () => {
    expect(stateFacetPresentation("accepted")).toEqual({ label: "Accepted", tone: "success" });
    expect(stateFacetPresentation("accepted_with_limitations").tone).toBe("warning");
    expect(stateFacetPresentation("requires_reverification").tone).toBe("warning");
    expect(stateFacetPresentation("rejected").tone).toBe("error");
  });

  it("does not turn not-approval into a positive approval state", () => {
    expect(stateFacetPresentation("not-approval")).toEqual({ label: "Not an approval", tone: "default" });
  });
});
