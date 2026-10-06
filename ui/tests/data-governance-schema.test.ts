import { describe, expect, it } from "vitest";
import { parseDataGovernance } from "../lib/api/schemas";

const decision = {
  sensitivity: "internal",
  policy_id: "governance-1",
  retain_until: "2026-10-01T00:00:00+00:00",
  expired: false,
  storage_allowed: true,
  telemetry_allowed: true,
  disclosure_allowed: true,
  deletion_allowed: false,
  reasons: ["retention window has not expired"],
  object_id_digest: "a".repeat(64),
  object_id_exposed: false,
};

const fixture = {
  schema_version: "data-governance-investigation.v2",
  source: {
    resource: "explicit-lifecycle-context-plus-workspace-metadata",
    configured: true,
    source_path_exposed: false,
    workspace_authority: true,
    second_lifecycle_store_created: false,
    privacy_governance_snapshot_configured: false,
  },
  privacy_governance_runtime: {
    observed: false,
    defaults_inferred: false,
    source_path_exposed: false,
  },
  object: {
    kind: "workspace-record",
    object_id_digest: "a".repeat(64),
    object_id_exposed: false,
    sensitivity: "internal",
    created_at: "2026-09-30T00:00:00+00:00",
    original_digest: "b".repeat(64),
  },
  policy: {
    policy_id: "governance-1",
    purpose: "reliability evidence",
    max_retention_days: 1,
    storage_max_sensitivity: "restricted",
    telemetry_max_sensitivity: "internal",
    disclosure_max_sensitivity: "internal",
    encryption_at_rest_required: true,
    tls_required: true,
  },
  durable_retention: {
    present: true,
    policy_id: "governance-1",
    sensitivity: "internal",
    retain_until: "2026-10-01T00:00:00+00:00",
    legal_hold: false,
    context_cross_check_verified: true,
  },
  current_decision: {
    ...decision,
    policy_replay_verified: true,
    deletion_already_recorded: false,
  },
  recorded_decision: { present: false },
  deletion: {
    present: false,
    payload_erasure_outside_statewake_evaluated: false,
  },
  confidentiality_requirements: {
    encryption_at_rest_required: true,
    tls_required: true,
    host_requirement_satisfaction_evaluated: false,
  },
  authorization: {
    deletion_executed_by_this_view: false,
    disclosure_executed_by_this_view: false,
    business_authorization_inferred: false,
    compliance_certified: false,
  },
  limitations: ["bounded"],
};

describe("parseDataGovernance", () => {
  it("accepts a policy-replay-verified workspace lifecycle projection", () => {
    const parsed = parseDataGovernance(fixture);
    expect(parsed.current_decision.deletion_allowed).toBe(false);
    expect(parsed.confidentiality_requirements.host_requirement_satisfaction_evaluated).toBe(false);
  });

  it("rejects raw object identity leakage", () => {
    expect(() =>
      parseDataGovernance({
        ...fixture,
        object: { ...fixture.object, object_id: "raw-object" },
      }),
    ).toThrow(/raw object identity/);
  });

  it("rejects a host-security verification claim", () => {
    expect(() =>
      parseDataGovernance({
        ...fixture,
        confidentiality_requirements: {
          ...fixture.confidentiality_requirements,
          host_requirement_satisfaction_evaluated: true,
        },
      }),
    ).toThrow(/host confidentiality requirements/);
  });

  it("rejects inconsistent durable lifecycle binding", () => {
    expect(() =>
      parseDataGovernance({
        ...fixture,
        durable_retention: {
          ...fixture.durable_retention,
          policy_id: "different-policy",
        },
      }),
    ).toThrow(/lifecycle bindings/);
  });

  it("accepts observed runtime privacy/evidence governance without inferring telemetry liveness", () => {
    const parsed = parseDataGovernance({
      ...fixture,
      source: { ...fixture.source, privacy_governance_snapshot_configured: true },
      privacy_governance_runtime: {
        observed: true,
        defaults_inferred: false,
        source_path_exposed: false,
        snapshot_digest: "c".repeat(64),
        privacy_policy: {
          policy_id: "privacy-1",
          redact_key_count: 8,
          regex_rule_count: 1,
          patterns_exposed: false,
          metadata_redaction_before_receipt_identity: true,
        },
        evidence_policy: {
          policy_id: "evidence-1",
          storage_max_sensitivity: "confidential",
          telemetry_max_sensitivity: "internal",
          require_digest_for: ["restricted"],
          storage_governance_before_artifact_write: true,
          workspace_sensitivity_indexing: true,
          telemetry_manifest_projection_supported: true,
          telemetry_runtime_binding_observed: false,
        },
        opaque_content_secret_scanning: false,
      },
    });
    expect(parsed.privacy_governance_runtime.observed).toBe(true);
    if (parsed.privacy_governance_runtime.observed) {
      expect(parsed.privacy_governance_runtime.evidence_policy.telemetry_runtime_binding_observed).toBe(false);
    }
  });

  it("rejects runtime assurance inflation", () => {
    expect(() => parseDataGovernance({
      ...fixture,
      source: { ...fixture.source, privacy_governance_snapshot_configured: true },
      privacy_governance_runtime: {
        observed: true,
        defaults_inferred: false,
        source_path_exposed: false,
        snapshot_digest: "c".repeat(64),
        privacy_policy: {
          policy_id: "privacy-1", redact_key_count: 8, regex_rule_count: 0,
          patterns_exposed: false, metadata_redaction_before_receipt_identity: true,
        },
        evidence_policy: {
          policy_id: "evidence-1", storage_max_sensitivity: "restricted", telemetry_max_sensitivity: "internal", require_digest_for: ["restricted"],
          storage_governance_before_artifact_write: true, workspace_sensitivity_indexing: true,
          telemetry_manifest_projection_supported: true, telemetry_runtime_binding_observed: true,
        },
        opaque_content_secret_scanning: false,
      },
    })).toThrow(/assurance/);
  });
});
