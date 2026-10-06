import { describe, expect, it } from "vitest";
import { isAllowedReadApiPath, isAllowedReadApiQuery } from "../lib/api/proxy-policy";

const id = "a".repeat(64);
const other = "b".repeat(64);

describe("read proxy policy", () => {
  it("allows only implemented bounded read resources", () => {
    expect(isAllowedReadApiPath(["api", "v1", "capabilities"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "overview"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "incidents"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "release-trust"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "proof-bundle"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "decision-lineage"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "validation-study"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "workspace", "operations"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "incidents", id])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id, "summary"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id, "history"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id, "evidence"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id, "compare", other])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "reports", id])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "reports", id, "markdown"])).toBe(true);
  });

  it("allows bounded claim discovery filters without arbitrary query syntax", () => {
    const parts = ["api", "v1", "claims"];
    expect(
      isAllowedReadApiQuery(
        parts,
        new URLSearchParams("decision=review&verified=false&q=alpha&limit=50&offset=0"),
      ),
    ).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("verified=yes"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("q="))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("sql=select"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=10&limit=20"))).toBe(false);
  });

  it("allows bounded incident investigation filters without arbitrary query syntax", () => {
    const parts = ["api", "v1", "incidents"];
    expect(
      isAllowedReadApiQuery(
        parts,
        new URLSearchParams("status=reverified&category=storage-compromise&q=detector&limit=50&offset=0"),
      ),
    ).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("status=closed"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("q="))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("sql=select"))).toBe(false);
    expect(
      isAllowedReadApiQuery(parts, new URLSearchParams("status=recovered&status=reverified")),
    ).toBe(false);
  });

  it("allows only bounded workspace pagination query parameters", () => {
    const parts = ["api", "v1", "workspace", "operations"];
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=50&offset=0"))).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=200&offset=10"))).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=50&limit=60"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("sql=select"))).toBe(false);
    expect(
      isAllowedReadApiQuery(["api", "v1", "release-trust"], new URLSearchParams("x=1")),
    ).toBe(false);
    expect(
      isAllowedReadApiQuery(["api", "v1", "proof-bundle"], new URLSearchParams("path=%2Ftmp%2Fproof.zip")),
    ).toBe(false);
    expect(
      isAllowedReadApiQuery(["api", "v1", "decision-lineage"], new URLSearchParams("path=%2Ftmp%2Fchain.json")),
    ).toBe(false);
  });

  it("denies traversal, list expansion, and future write-like resources", () => {
    expect(isAllowedReadApiPath(["api", "v1", "claims", ".."])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "incidents", "../secret"])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "workspace", "restore"])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "release-trust", "publish"])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "proof-bundle", "export"])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "decision-lineage", "rebuild"])).toBe(false);
    expect(isAllowedReadApiPath(["api", "v1", "claims", id, "reviews"])).toBe(false);
  });
});

describe("capture health proxy policy", () => {
  it("allows only bounded failure-journal filters", () => {
    const parts = ["api", "v1", "capture-health"];
    expect(isAllowedReadApiPath(parts)).toBe(true);
    expect(
      isAllowedReadApiQuery(
        parts,
        new URLSearchParams("stage=native_capture.persist&error_type=OSError&limit=50&offset=0"),
      ),
    ).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("stage="))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("path=C%3A%5Csecret"))).toBe(false);
    expect(
      isAllowedReadApiQuery(parts, new URLSearchParams("stage=a&stage=b")),
    ).toBe(false);
  });
});

describe("attestation trust proxy policy", () => {
  it("allows only bounded trust investigation filters", () => {
    const parts = ["api", "v1", "attestation-trust"];
    expect(isAllowedReadApiPath(parts)).toBe(true);
    expect(
      isAllowedReadApiQuery(
        parts,
        new URLSearchParams(
          "decision=reject&reliability_state=unreliable&key_status=revoked&q=agent-1&limit=50&offset=0",
        ),
      ),
    ).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("key_status=trusted"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("q="))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("path=%2Fsecret"))).toBe(false);
    expect(
      isAllowedReadApiQuery(parts, new URLSearchParams("key_status=active&key_status=revoked")),
    ).toBe(false);
  });
});

describe("security assurance proxy policy", () => {
  it("allows only bounded deployment-security audit filters", () => {
    const parts = ["api", "v1", "security-assurance"];
    expect(isAllowedReadApiPath(parts)).toBe(true);
    expect(
      isAllowedReadApiQuery(
        parts,
        new URLSearchParams(
          "event=authorization_denied&operation=review%3Awrite&reason=authorization_denied&method=POST&limit=50&offset=0",
        ),
      ),
    ).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("event=success"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("reason=secret"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("method=POST%20SECRET"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("path=%2Fsecret"))).toBe(false);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("limit=201"))).toBe(false);
    expect(
      isAllowedReadApiQuery(parts, new URLSearchParams("event=request_admitted&event=request_rejected")),
    ).toBe(false);
  });
});

describe("assurance decision and authorization policy proxy boundaries", () => {
  it("allows the exact read-only paths", async () => {
    const { isAllowedReadApiPath, isAllowedReadApiQuery } = await import("../lib/api/proxy-policy");
    expect(isAllowedReadApiPath(["api", "v1", "assurance-decision"])).toBe(true);
    expect(isAllowedReadApiPath(["api", "v1", "authorization-policy"])).toBe(true);
    expect(isAllowedReadApiQuery(["api", "v1", "assurance-decision"], new URLSearchParams())).toBe(true);
    expect(isAllowedReadApiQuery(["api", "v1", "authorization-policy"], new URLSearchParams())).toBe(true);
  });

  it("rejects arbitrary query input on the fixed-source paths", async () => {
    const { isAllowedReadApiQuery } = await import("../lib/api/proxy-policy");
    expect(isAllowedReadApiQuery(["api", "v1", "assurance-decision"], new URLSearchParams("path=/tmp/x"))).toBe(false);
    expect(isAllowedReadApiQuery(["api", "v1", "authorization-policy"], new URLSearchParams("principal=alice"))).toBe(false);
  });
});


describe("data governance proxy boundary", () => {
  it("allows only the exact fixed-source read path without query input", async () => {
    const { isAllowedReadApiPath, isAllowedReadApiQuery } = await import("../lib/api/proxy-policy");
    const parts = ["api", "v1", "data-governance"];
    expect(isAllowedReadApiPath(parts)).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams())).toBe(true);
    expect(isAllowedReadApiQuery(parts, new URLSearchParams("path=/tmp/secret"))).toBe(false);
  });
});
