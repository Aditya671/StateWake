import { describe, expect, it } from "vitest";
import { parseClaimComparison, parseClaimDetail, parseClaimHistory } from "../lib/api/schemas";
import type { AttestationTrustView } from "../lib/api/dto";

const fixture = {
  schema_version: "claim-detail.v1",
  source: { record_id: "a".repeat(64), artifact_digest: "b".repeat(64), producer_id: "validator", producer_type: "statewake-verification-report", captured_at: "2026-09-27T00:00:00+00:00", run_id: "run-1", sensitivity: null },
  summary: {
    schema_version: "claim-summary.v1",
    candidate: { id: "candidate-a", digest: "c".repeat(64) },
    profile: { id: "tool_action_authorized.v1", version: "1" },
    claim: "Tool action is authorized",
    decision: "accepted",
    verification: { verified: true, passed: 3, failed: 0, unrun: 0, unknown: 0 },
    evidence: { included: 3, omitted: 0, missing: 0 },
    reasons: [],
    human_decision: { required: true, approval_status: "requires-human-approval", required_actions: ["publication approval"] },
    caveats: [], residual_risks: [], report_digest: "d".repeat(64), generated_at: "2026-09-27T00:00:00+00:00", as_of: null,
  },
  checks: { passed: ["contract-present"], failed: [], unrun: [], unknown: [] },
  evidence: { included: ["tool-contract"], omitted: [], missing: [], source_identities: [], artifact_digests: [] },
  decision_rationale: ["required evidence present"], recovery_status: "not-applicable",
  allowed_use: ["inspection"], prohibited_use: ["publication authorization"], machine_readable_appendix: [],
  profile_evaluation_digest: "e".repeat(64), verifier_version: "0.4.1", generated_at: "2026-09-27T00:00:00+00:00", report_digest: "d".repeat(64),
  links: { canonical_json: `/api/v1/reports/${"a".repeat(64)}`, canonical_markdown: `/api/v1/reports/${"a".repeat(64)}/markdown` },
};

describe("parseClaimDetail", () => {
  it("keeps machine decision and human authority distinct", () => {
    const parsed = parseClaimDetail(fixture);
    expect(parsed.summary.decision).toBe("accepted");
    expect(parsed.summary.human_decision.approval_status).toBe("requires-human-approval");
    expect(parsed.summary.human_decision.required).toBe(true);
  });

  it("accepts a report without a profile evaluation digest", () => {
    const parsed = parseClaimDetail({ ...fixture, profile_evaluation_digest: null });
    expect(parsed.profile_evaluation_digest).toBeNull();
  });

  it("rejects an invented as-of timestamp", () => {
    expect(() => parseClaimDetail({ ...fixture, summary: { ...fixture.summary, as_of: "2026-09-27" } })).toThrow(/as_of/);
  });
});

describe("history and comparison schemas", () => {
  it("requires recorded_count to match the returned history rows", () => {
    expect(() =>
      parseClaimHistory({
        schema_version: "claim-history.v1",
        report_record_id: "a".repeat(64),
        candidate: { id: "chain-1", digest: "b".repeat(64) },
        profile: { id: "rag_answer_verified.v1", version: "1" },
        recorded_count: 1,
        items: [],
        active_approval_receipt_ids: [],
        limitations: [],
      }),
    ).toThrow(/recorded_count/);
  });

  it("preserves non-equivalence warnings in comparison results", () => {
    const side = {
      record_id: "a".repeat(64),
      report_digest: "b".repeat(64),
      candidate: { id: "chain-1", digest: "c".repeat(64) },
      profile: { id: "rag_answer_verified.v1", version: "1" },
      claim: "RAG answer verified",
      report_type: "engineering",
      decision: "review",
      verified: false,
      approval_status: "requires-human-approval",
      generated_at: "2026-09-27T00:00:00+00:00",
      captured_at: "2026-09-27T00:00:00+00:00",
    };
    const delta = { added: [], removed: [] };
    const parsed = parseClaimComparison({
      schema_version: "claim-comparison.v1",
      semantic_scope_same: false,
      non_equivalence_warnings: ["profile-version-differs"],
      left: side,
      right: { ...side, record_id: "d".repeat(64), profile: { ...side.profile, version: "2" } },
      changes: {
        candidate_digest_changed: false,
        decision: { before: "review", after: "review", changed: false },
        verified: { before: false, after: false, changed: false },
        approval_status: {
          before: "requires-human-approval",
          after: "requires-human-approval",
          changed: false,
        },
        checks: { passed: delta, failed: delta, unrun: delta, unknown: delta },
        evidence: { included: delta, missing: delta, omitted: delta },
        caveats: delta,
        residual_risks: delta,
        human_decisions_required: delta,
      },
      limitations: ["bounded"],
    });
    expect(parsed.semantic_scope_same).toBe(false);
    expect(parsed.non_equivalence_warnings).toEqual(["profile-version-differs"]);
  });
});

describe("review schemas", () => {
  it("keeps review statement results separate from approval evidence", async () => {
    const { parseReviewStatementResult } = await import("../lib/api/schemas");
    const review = {
      schema_version: "review-statement.v1",
      sequence: 0,
      target_record_id: "a".repeat(64),
      candidate_identity: "candidate-1",
      candidate_digest: "b".repeat(64),
      report_digest: "c".repeat(64),
      profile_id: "rag_answer_verified.v1",
      profile_version: "1",
      actor_identity_ref: "reviewer:alice",
      actor_role: "reliability-reviewer",
      category: "review_complete",
      statement: "approved",
      finding_refs: [],
      limitation: null,
      scope: "candidate review",
      created_at: "2026-09-27T10:00:00+00:00",
      idempotency_key: "request-1",
      request_fingerprint: "d".repeat(64),
      supersedes_digest: null,
      previous_digest: null,
      digest: "e".repeat(64),
    };
    const parsed = parseReviewStatementResult({
      schema_version: "review-statement-result.v1",
      created: true,
      approval_created: false,
      review,
    });
    expect(parsed.review.statement).toBe("approved");
    expect(parsed.approval_created).toBe(false);
    expect(() =>
      parseReviewStatementResult({
        schema_version: "review-statement-result.v1",
        created: true,
        approval_created: true,
        review,
      }),
    ).toThrow(/must not create approval/);
  });
});


describe("overview and human approval schemas", () => {
  it("accepts real zero-valued overview metrics without inventing dashboard values", async () => {
    const { parseOverviewProjection } = await import("../lib/api/schemas");
    const parsed = parseOverviewProjection({
      schema_version: "overview.v1",
      scope: {
        resource: "verification-report-records",
        denominator: 0,
        deduplication_key: "workspace receipt id",
      },
      as_of: null,
      metrics: {
        reports_evaluated: 0,
        verified_reports: 0,
        reports_missing_evidence: 0,
        human_decisions_pending: 0,
      },
      decisions: { accept: 0, review: 0, reject: 0, other: 0 },
      recent_reports: [],
      limitations: ["Counts apply only to canonical verification reports in scope."],
    });
    expect(parsed.metrics.reports_evaluated).toBe(0);
    expect(parsed.recent_reports).toEqual([]);
  });

  it("requires server-declared approval action and scope before displaying an approval thread", async () => {
    const { parseHumanApprovalThread } = await import("../lib/api/schemas");
    const target = {
      record_id: "a".repeat(64),
      candidate_identity: "candidate-1",
      candidate_digest: "b".repeat(64),
      report_digest: "c".repeat(64),
      profile_id: "release_evidence_complete.v1",
      profile_version: "1",
    };
    const parsed = parseHumanApprovalThread({
      schema_version: "human-approval-thread.v1",
      target,
      authority: {
        approval_action: "approve-release-evidence",
        scope: "candidate release evidence",
      },
      items: [],
      active_approval_receipt_ids: [],
      limitations: [],
    });
    expect(parsed.authority.approval_action).toBe("approve-release-evidence");
    expect(() =>
      parseHumanApprovalThread({
        schema_version: "human-approval-thread.v1",
        target,
        items: [],
        limitations: [],
      }),
    ).toThrow(/authority/);
  });

  it("preserves canonical revocation lifecycle evidence and active approval identities", async () => {
    const { parseHumanApprovalThread, parseHumanApprovalLifecycleResult } = await import(
      "../lib/api/schemas"
    );
    const receiptId = "d".repeat(64);
    const receiptDigest = "e".repeat(64);
    const approval = {
      contract: {
        schema_version: "statewake.ai_contract.v1",
        contract_type: "human_approval",
        contract_version: "1",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
        actor_identity_ref: "reviewer:alice",
        role: "reliability-reviewer",
        approval_action: "approve-release-evidence",
        approval_basis_digest: "c".repeat(64),
        scope: "candidate release evidence",
        captured_at: "2026-09-27T10:00:00+00:00",
        metadata: {},
      },
      receipt: {
        receipt_id: receiptId,
        receipt_digest: receiptDigest,
        artifact_digest: "f".repeat(64),
        captured_at: "2026-09-27T10:00:00+00:00",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
      },
    };
    const revocation = {
      contract: {
        schema_version: "statewake.ai_contract.v1",
        contract_type: "human_approval_revocation",
        contract_version: "1",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
        actor_identity_ref: "reviewer:alice",
        role: "reliability-reviewer",
        approval_action: "approve-release-evidence",
        approval_basis_digest: "c".repeat(64),
        scope: "candidate release evidence",
        target_approval_receipt_id: receiptId,
        target_approval_receipt_digest: receiptDigest,
        reason: "Approval withdrawn after release scope changed.",
        captured_at: "2026-09-27T11:00:00+00:00",
        metadata: {},
      },
      receipt: {
        receipt_id: "1".repeat(64),
        receipt_digest: "2".repeat(64),
        artifact_digest: "3".repeat(64),
        captured_at: "2026-09-27T11:00:00+00:00",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
      },
    };
    const parsed = parseHumanApprovalThread({
      schema_version: "human-approval-thread.v1",
      target: {
        record_id: "a".repeat(64),
        candidate_identity: "candidate-1",
        candidate_digest: "b".repeat(64),
        report_digest: "c".repeat(64),
        profile_id: "release_evidence_complete.v1",
        profile_version: "1",
      },
      authority: {
        approval_action: "approve-release-evidence",
        scope: "candidate release evidence",
      },
      items: [
        {
          ...approval,
          lifecycle: {
            status: "revoked",
            superseded_by_receipt_id: null,
            revocation,
          },
        },
      ],
      active_approval_receipt_ids: [],
      limitations: [],
    });
    expect(parsed.items[0]?.lifecycle?.status).toBe("revoked");
    expect(parsed.items[0]?.lifecycle?.revocation?.contract.reason).toContain("withdrawn");
    expect(parsed.active_approval_receipt_ids).toEqual([]);

    const lifecycleResult = parseHumanApprovalLifecycleResult({
      schema_version: "human-approval-lifecycle-result.v1",
      operation: "revoke",
      created: true,
      approval: null,
      revocation,
      effects: {
        verification_report_mutated: false,
        machine_decision_changed: false,
        release_published: false,
        side_effect_authorized_outside_scope: false,
      },
      limitations: [],
    });
    expect(lifecycleResult.operation).toBe("revoke");
    expect(lifecycleResult.approval).toBeNull();
  });

  it("fails closed if an approval response claims broader side effects", async () => {
    const { parseHumanApprovalResult } = await import("../lib/api/schemas");
    const approval = {
      contract: {
        schema_version: "statewake.ai_contract.v1",
        contract_type: "human_approval",
        contract_version: "1",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
        actor_identity_ref: "reviewer:alice",
        role: "reliability-reviewer",
        approval_action: "approve-release-evidence",
        approval_basis_digest: "c".repeat(64),
        scope: "candidate release evidence",
        captured_at: "2026-09-27T10:00:00+00:00",
        metadata: {},
      },
      receipt: {
        receipt_id: "d".repeat(64),
        receipt_digest: "e".repeat(64),
        artifact_digest: "f".repeat(64),
        captured_at: "2026-09-27T10:00:00+00:00",
        producer_id: "statewake.test.approver",
        run_id: "run-1",
      },
    };
    const valid = {
      schema_version: "human-approval-result.v1",
      created: true,
      approval,
      effects: {
        verification_report_mutated: false,
        machine_decision_changed: false,
        release_published: false,
        side_effect_authorized_outside_scope: false,
      },
      limitations: [],
    };
    expect(parseHumanApprovalResult(valid).approval.contract.contract_type).toBe("human_approval");
    expect(() =>
      parseHumanApprovalResult({
        ...valid,
        effects: { ...valid.effects, release_published: true },
      }),
    ).toThrow(/must not mutate/);
  });
});

describe("evidence trace schema", () => {
  it("accepts a bounded trace with explicit relationships and unresolved evidence", async () => {
    const { parseEvidenceTrace } = await import("../lib/api/schemas");
    const reportNode = "1".repeat(64);
    const artifactNode = "2".repeat(64);
    const parsed = parseEvidenceTrace({
      schema_version: "evidence-trace.v2",
      report_record_id: "a".repeat(64),
      report_digest: "b".repeat(64),
      candidate: { id: "candidate-1", digest: "c".repeat(64) },
      nodes: [
        {
          node_id: reportNode,
          kind: "verification-report",
          identity: "a".repeat(64),
          label: "Verification report",
          digest: "b".repeat(64),
          digest_kind: "report-digest",
          integrity_status: "verified",
          availability: "present",
          record_id: "a".repeat(64),
          producer_id: "statewake.test",
          producer_type: "statewake-verification-report",
          captured_at: "2026-09-29T00:00:00+00:00",
          run_id: "run-1",
          source_event_id: null,
          artifact_size: 100,
          receipt_digest: null,
          receipt_integrity_status: null,
          artifact_integrity_status: null,
          admission_status: null,
          admission_digest: null,
          producer_authentication_status: null,
        },
        {
          node_id: artifactNode,
          kind: "artifact-digest",
          identity: "d".repeat(64),
          label: "Referenced artifact",
          digest: "d".repeat(64),
          digest_kind: "artifact-sha256",
          integrity_status: "recorded",
          availability: "recorded",
          record_id: null,
          producer_id: null,
          producer_type: null,
          captured_at: null,
          run_id: null,
          source_event_id: null,
          artifact_size: null,
          receipt_digest: null,
          receipt_integrity_status: null,
          artifact_integrity_status: null,
          admission_status: null,
          admission_digest: null,
          producer_authentication_status: null,
        },
      ],
      edges: [
        {
          edge_id: "e".repeat(64),
          source: reportNode,
          target: artifactNode,
          relationship_type: "references-artifact-digest",
          basis: "report.artifact_digests",
          occurrences: 1,
        },
      ],
      unresolved: [
        { kind: "source-identity", identity: "missing", reason: "not resolved" },
      ],
      workspace_scan: { records_scanned: 1, records_available: 2, complete: false },
      assurance_summary: {
        receipts_resolved: 0,
        receipt_integrity_verified: 0,
        artifact_integrity_verified: 0,
        admission_verified: 0,
      },
      producer_authentication: {
        status: "not-recorded",
        authenticated: null,
        reason: "No persisted producer authentication proof.",
      },
      limitations: ["Descriptive evidence lineage only."],
    });
    expect(parsed.edges[0]?.relationship_type).toBe("references-artifact-digest");
    expect(parsed.workspace_scan.complete).toBe(false);
  });

  it("rejects dangling relationship endpoints", async () => {
    const { parseEvidenceTrace } = await import("../lib/api/schemas");
    expect(() =>
      parseEvidenceTrace({
        schema_version: "evidence-trace.v2",
        report_record_id: "a".repeat(64),
        report_digest: "b".repeat(64),
        candidate: { id: "candidate-1", digest: "c".repeat(64) },
        nodes: [],
        edges: [
          {
            edge_id: "e".repeat(64),
            source: "missing-source",
            target: "missing-target",
            relationship_type: "fabricated",
            basis: "none",
            occurrences: 1,
          },
        ],
        unresolved: [],
        workspace_scan: { records_scanned: 0, records_available: 0, complete: true },
        assurance_summary: {
          receipts_resolved: 0,
          receipt_integrity_verified: 0,
          artifact_integrity_verified: 0,
          admission_verified: 0,
        },
        producer_authentication: {
          status: "not-recorded",
          authenticated: null,
          reason: "No persisted producer authentication proof.",
        },
        limitations: [],
      }),
    ).toThrow(/unknown node/);
  });
});

describe("evidence trace assurance boundaries", () => {
  it("rejects producer-authentication assurance inflation", async () => {
    const { parseEvidenceTrace } = await import("../lib/api/schemas");
    expect(() =>
      parseEvidenceTrace({
        schema_version: "evidence-trace.v2",
        report_record_id: "a".repeat(64),
        report_digest: "b".repeat(64),
        candidate: { id: "candidate-1", digest: "c".repeat(64) },
        nodes: [],
        edges: [],
        unresolved: [],
        workspace_scan: { records_scanned: 0, records_available: 0, complete: true },
        assurance_summary: { receipts_resolved: 0, receipt_integrity_verified: 0, artifact_integrity_verified: 0, admission_verified: 0 },
        producer_authentication: { status: "verified", authenticated: true, reason: "producer id matched" },
        limitations: [],
      }),
    ).toThrow(/cannot be promoted/);
  });

  it("rejects verified admission without verified receipt and artifact integrity", async () => {
    const { parseEvidenceTrace } = await import("../lib/api/schemas");
    expect(() =>
      parseEvidenceTrace({
        schema_version: "evidence-trace.v2",
        report_record_id: "a".repeat(64),
        report_digest: "b".repeat(64),
        candidate: { id: "candidate-1", digest: "c".repeat(64) },
        nodes: [{
          node_id: "1".repeat(64), kind: "workspace-record", identity: "d".repeat(64), label: "producer",
          digest: "e".repeat(64), digest_kind: "artifact-sha256", integrity_status: "verified", availability: "present",
          record_id: "d".repeat(64), producer_id: "producer-1", producer_type: "test", captured_at: "2026-09-30T00:00:00+00:00",
          run_id: "run-1", source_event_id: "event-1", artifact_size: 10, receipt_digest: "f".repeat(64),
          receipt_integrity_status: "verified", artifact_integrity_status: "invalid", admission_status: "verified",
          admission_digest: "0".repeat(64), producer_authentication_status: "not-recorded",
        }],
        edges: [], unresolved: [],
        workspace_scan: { records_scanned: 1, records_available: 1, complete: true },
        assurance_summary: { receipts_resolved: 1, receipt_integrity_verified: 1, artifact_integrity_verified: 0, admission_verified: 1 },
        producer_authentication: { status: "not-recorded", authenticated: null, reason: "No persisted producer authentication proof." },
        limitations: [],
      }),
    ).toThrow(/requires verified receipt and artifact integrity/);
  });
});

describe("operational trust schemas", () => {
  it("keeps release trust signals independent when publication authority is unconfigured", async () => {
    const { parseReleaseTrustView } = await import("../lib/api/schemas");
    const parsed = parseReleaseTrustView({
      schema_version: "release-trust-view.v1",
      bundle_digest: "a".repeat(64),
      source: {
        distribution: "statewake-ai",
        version: "0.4.1",
        source_revision: "rev-1",
        source_tree_sha256: "b".repeat(64),
        dependency_lock_sha256: "c".repeat(64),
      },
      artifacts: [],
      build: { builder: "uv_build", build_type: "wheel", build_steps: [], environment: {}, started_at: null, finished_at: null },
      tests: [],
      external_evidence: { sbom: null, vulnerability_scan: null, signature: null, provenance: null },
      structural_profile: { profile_id: "release_evidence_complete.v1", profile_version: "1", satisfied: true, failed_requirements: [], missing_evidence: [], caveats: [] },
      content_verification: { status: "not_configured", complete: null, matched: [], missing: [], mismatched: [], limitations: [] },
      signature_authenticity: { status: "not_verified", authenticated: null, reason: "no trusted signer configured" },
      human_decision: { actor_ref: "", role: "", decision: "undecided", decided_at: null, scope: "", basis_digest: null },
      publication_authorized: false,
      release_published: false,
      publication_authorization: {
        configured: false,
        target_repository: null,
        basis_digest: null,
        expected_producer_id: null,
        publication_authorized: false,
        active_approval_receipt_ids: [],
        items: [],
      },
      registry_publication: {
        configured: false, release_published: false, registry_reconciled: false,
        receipt_digest: null, target_repository: null, basis_digest: null, permit_digest: null,
        observed_at: null, public_bytes_verified: false, artifacts: [],
        lifecycle: {
          configured: false, current_status: null, current_observed_at: null, observation_count: 0,
          registry_entry_present: null, default_install_eligible: null, public_bytes_verified: null,
          missing_artifacts: [], observations: [],
        },
      },
      limitations: [],
    });
    expect(parsed.structural_profile.satisfied).toBe(true);
    expect(parsed.content_verification.complete).toBeNull();
    expect(parsed.signature_authenticity.authenticated).toBeNull();
    expect(parsed.publication_authorized).toBe(false);
    expect(() => parseReleaseTrustView({ ...parsed, publication_authorized: true })).toThrow(/publication/);
  });

  it("accepts only publication state consistent with the canonical lifecycle projection", async () => {
    const { parseReleaseTrustView } = await import("../lib/api/schemas");
    const approvalId = "d".repeat(64);
    const base = {
      schema_version: "release-trust-view.v1",
      bundle_digest: "a".repeat(64),
      source: { distribution: "statewake-ai", version: "0.4.1", source_revision: "rev-1", source_tree_sha256: "b".repeat(64), dependency_lock_sha256: "c".repeat(64) },
      artifacts: [],
      build: { builder: "uv_build", build_type: "wheel", build_steps: [], environment: {}, started_at: null, finished_at: null },
      tests: [],
      external_evidence: { sbom: null, vulnerability_scan: null, signature: null, provenance: null },
      structural_profile: { profile_id: "release_evidence_complete.v1", profile_version: "1", satisfied: true, failed_requirements: [], missing_evidence: [], caveats: [] },
      content_verification: { status: "verified", complete: true, matched: [], missing: [], mismatched: [], limitations: [] },
      signature_authenticity: { status: "not_verified", authenticated: null, reason: "no trusted signer configured" },
      human_decision: { actor_ref: "release-owner", role: "release approver", decision: "approved", decided_at: "2026-10-04T00:00:00+00:00", scope: "release", basis_digest: null },
      publication_authorized: true,
      release_published: false,
      publication_authorization: {
        configured: true, target_repository: "pypi", basis_digest: "e".repeat(64), expected_producer_id: "github-actions:openai/statewake", publication_authorized: true,
        active_approval_receipt_ids: [approvalId],
        items: [{ status: "active", approval_receipt_id: approvalId, actor_identity_ref: "release-owner", role: "release approver", captured_at: "2026-10-04T00:00:00+00:00", superseded_by_receipt_id: null, revocation_receipt_id: null }],
      },
      registry_publication: {
        configured: false, release_published: false, registry_reconciled: false,
        receipt_digest: null, target_repository: null, basis_digest: null, permit_digest: null,
        observed_at: null, public_bytes_verified: false, artifacts: [],
        lifecycle: {
          configured: false, current_status: null, current_observed_at: null, observation_count: 0,
          registry_entry_present: null, default_install_eligible: null, public_bytes_verified: null,
          missing_artifacts: [], observations: [],
        },
      },
      limitations: [],
    } as const;
    const parsed = parseReleaseTrustView(base);
    expect(parsed.publication_authorized).toBe(true);
    expect(parsed.publication_authorization.active_approval_receipt_ids).toEqual([approvalId]);
    expect(() => parseReleaseTrustView({ ...base, publication_authorization: { ...base.publication_authorization, active_approval_receipt_ids: [] } })).toThrow(/active approval projection/);
  });

  it("accepts reconciled registry publication only when exact artifacts agree", async () => {
    const { parseReleaseTrustView } = await import("../lib/api/schemas");
    const artifact = { name: "statewake_ai-0.4.1-py3-none-any.whl", sha256: "f".repeat(64), size_bytes: 5, media_type: "application/zip" };
    const value = {
      schema_version: "release-trust-view.v1",
      bundle_digest: "a".repeat(64),
      source: { distribution: "statewake-ai", version: "0.4.1", source_revision: "rev-1", source_tree_sha256: "b".repeat(64), dependency_lock_sha256: "c".repeat(64) },
      artifacts: [artifact],
      build: { builder: "uv_build", build_type: "wheel", build_steps: [], environment: {}, started_at: null, finished_at: null },
      tests: [],
      external_evidence: { sbom: null, vulnerability_scan: null, signature: null, provenance: null },
      structural_profile: { profile_id: "release_evidence_complete.v1", profile_version: "1", satisfied: true, failed_requirements: [], missing_evidence: [], caveats: [] },
      content_verification: { status: "verified", complete: true, matched: [artifact.name], missing: [], mismatched: [], limitations: [] },
      signature_authenticity: { status: "not_verified", authenticated: null, reason: "no trusted signer configured" },
      human_decision: { actor_ref: "release-owner", role: "release approver", decision: "approved", decided_at: "2026-10-04T00:00:00+00:00", scope: "release", basis_digest: null },
      publication_authorized: true,
      release_published: true,
      publication_authorization: {
        configured: true, target_repository: "pypi", basis_digest: "e".repeat(64), expected_producer_id: "github-actions:openai/statewake", publication_authorized: true,
        active_approval_receipt_ids: ["d".repeat(64)],
        items: [{ status: "active", approval_receipt_id: "d".repeat(64), actor_identity_ref: "release-owner", role: "release approver", captured_at: "2026-10-04T00:00:00+00:00", superseded_by_receipt_id: null, revocation_receipt_id: null }],
      },
      registry_publication: {
        configured: true, release_published: true, registry_reconciled: true,
        receipt_digest: "1".repeat(64), target_repository: "pypi", basis_digest: "e".repeat(64), permit_digest: "2".repeat(64),
        observed_at: "2026-10-04T00:02:00+00:00", public_bytes_verified: true,
        artifacts: [{ ...artifact, url: "https://files.pythonhosted.org/packages/statewake.whl", package_type: "bdist_wheel", upload_time: "2026-10-04T00:01:00+00:00", yanked: false, yanked_reason: null, public_bytes_verified: true }],
        lifecycle: {
          configured: true, current_status: "available", current_observed_at: "2026-10-04T00:03:00+00:00", observation_count: 1,
          registry_entry_present: true, default_install_eligible: true, public_bytes_verified: true, missing_artifacts: [],
          observations: [{
            observation_digest: "3".repeat(64), publication_receipt_digest: "1".repeat(64), predecessor_digest: "1".repeat(64),
            basis_digest: "e".repeat(64), permit_digest: "2".repeat(64), target_repository: "pypi",
            distribution: "statewake-ai", version: "0.4.1", registry_api_url: "https://pypi.org/pypi/statewake-ai/0.4.1/json",
            observed_at: "2026-10-04T00:03:00+00:00", status: "available", registry_entry_present: true,
            default_install_eligible: true, public_bytes_verified: true, missing_artifacts: [], unavailable_reason: null,
            artifacts: [{ ...artifact, url: "https://files.pythonhosted.org/packages/statewake.whl", package_type: "bdist_wheel", upload_time: "2026-10-04T00:01:00+00:00", yanked: false, yanked_reason: null, public_bytes_verified: true }],
            limitations: ["point-in-time observation"],
          }],
        },
      },
      limitations: [],
    } as const;
    const parsed = parseReleaseTrustView(value);
    expect(parsed.release_published).toBe(true);
    expect(parsed.registry_publication.public_bytes_verified).toBe(true);
    expect(() => parseReleaseTrustView({
      ...value,
      registry_publication: {
        ...value.registry_publication,
        artifacts: [{ ...value.registry_publication.artifacts[0], sha256: "0".repeat(64) }],
      },
    })).toThrow(/registry artifacts disagree/);
  });

  it("accepts partial registry availability only with the exact missing artifact set", async () => {
    const { parseReleaseTrustView } = await import("../lib/api/schemas");
    const wheel = { name: "statewake_ai-0.4.1-py3-none-any.whl", sha256: "f".repeat(64), size_bytes: 5, media_type: "application/zip" };
    const sdist = { name: "statewake_ai-0.4.1.tar.gz", sha256: "9".repeat(64), size_bytes: 7, media_type: "application/gzip" };
    const registryWheel = { ...wheel, url: "https://files.pythonhosted.org/packages/statewake.whl", package_type: "bdist_wheel", upload_time: "2026-10-04T00:01:00+00:00", yanked: false, yanked_reason: null, public_bytes_verified: true };
    const base = {
      schema_version: "release-trust-view.v1", bundle_digest: "a".repeat(64),
      source: { distribution: "statewake-ai", version: "0.4.1", source_revision: "rev-1", source_tree_sha256: "b".repeat(64), dependency_lock_sha256: "c".repeat(64) },
      artifacts: [wheel, sdist],
      build: { builder: "uv_build", build_type: "wheel", build_steps: [], environment: {}, started_at: null, finished_at: null }, tests: [],
      external_evidence: { sbom: null, vulnerability_scan: null, signature: null, provenance: null },
      structural_profile: { profile_id: "release_evidence_complete.v1", profile_version: "1", satisfied: true, failed_requirements: [], missing_evidence: [], caveats: [] },
      content_verification: { status: "verified", complete: true, matched: [wheel.name, sdist.name], missing: [], mismatched: [], limitations: [] },
      signature_authenticity: { status: "not_verified", authenticated: null, reason: "no trusted signer configured" },
      human_decision: { actor_ref: "release-owner", role: "release approver", decision: "approved", decided_at: "2026-10-04T00:00:00+00:00", scope: "release", basis_digest: null },
      publication_authorized: true, release_published: true,
      publication_authorization: { configured: true, target_repository: "pypi", basis_digest: "e".repeat(64), expected_producer_id: "github-actions:openai/statewake", publication_authorized: true, active_approval_receipt_ids: ["d".repeat(64)], items: [{ status: "active", approval_receipt_id: "d".repeat(64), actor_identity_ref: "release-owner", role: "release approver", captured_at: "2026-10-04T00:00:00+00:00", superseded_by_receipt_id: null, revocation_receipt_id: null }] },
      registry_publication: {
        configured: true, release_published: true, registry_reconciled: true, receipt_digest: "1".repeat(64), target_repository: "pypi", basis_digest: "e".repeat(64), permit_digest: "2".repeat(64), observed_at: "2026-10-04T00:02:00+00:00", public_bytes_verified: true,
        artifacts: [registryWheel, { ...sdist, url: "https://files.pythonhosted.org/packages/statewake.tar.gz", package_type: "sdist", upload_time: "2026-10-04T00:01:00+00:00", yanked: false, yanked_reason: null, public_bytes_verified: true }],
        lifecycle: { configured: true, current_status: "partially_available", current_observed_at: "2026-10-04T00:05:00+00:00", observation_count: 1, registry_entry_present: true, default_install_eligible: false, public_bytes_verified: false, missing_artifacts: [sdist.name], observations: [{ observation_digest: "3".repeat(64), publication_receipt_digest: "1".repeat(64), predecessor_digest: "1".repeat(64), basis_digest: "e".repeat(64), permit_digest: "2".repeat(64), target_repository: "pypi", distribution: "statewake-ai", version: "0.4.1", registry_api_url: "https://pypi.org/pypi/statewake-ai/0.4.1/json", observed_at: "2026-10-04T00:05:00+00:00", status: "partially_available", registry_entry_present: true, default_install_eligible: false, public_bytes_verified: false, missing_artifacts: [sdist.name], unavailable_reason: null, artifacts: [registryWheel], limitations: ["point-in-time observation"] }] },
      }, limitations: [],
    } as const;
    const parsed = parseReleaseTrustView(base);
    expect(parsed.registry_publication.lifecycle.current_status).toBe("partially_available");
    expect(parsed.registry_publication.lifecycle.missing_artifacts).toEqual([sdist.name]);
    expect(() => parseReleaseTrustView({ ...base, registry_publication: { ...base.registry_publication, lifecycle: { ...base.registry_publication.lifecycle, missing_artifacts: [wheel.name] } } })).toThrow(/current projection disagrees with chain tip/);
  });

  it("requires deterministic fixture-study semantics and preserves denominators", async () => {
    const { parseValidationStudyView } = await import("../lib/api/schemas");
    const parsed = parseValidationStudyView({
      schema_version: "validation-study-view.v1",
      study_id: "comparative-1",
      study_digest: "d".repeat(64),
      study_kind: "deterministic-fixture-study",
      baselines: [], workloads: [], faults: [], cases: [], case_count: 0,
      metrics: [{
        baseline: "statewake_full", case_count: 10, injected_fault_count: 7,
        detected_fault_count: 4, valid_case_count: 5, false_positive_count: 0,
        target_property_count: 58, checkable_property_count: 58,
        verification_coverage: 1, fault_detection_rate: 4 / 7, false_positive_rate: 0,
        verification_coverage_denominator: 58, fault_detection_denominator: 7,
        false_positive_denominator: 5,
      }],
      limitations: ["fixture-scoped"],
    });
    expect(parsed.metrics[0]?.fault_detection_denominator).toBe(7);
    expect(() => parseValidationStudyView({ ...parsed, study_kind: "live-benchmark" })).toThrow(/study kind/);
  });

  it("requires a read-only sqlite workspace projection", async () => {
    const { parseWorkspaceOperationsView } = await import("../lib/api/schemas");
    const fixture = {
      schema_version: "workspace-operations.v1",
      workspace: { workspace_id: "workspace-1", schema_version: "1", public_api_contract_version: "1", mode: "read-only", backend: "sqlite" },
      health: { status: "healthy", healthy: true, has_errors: false, checked_records: 0, checked_receipts: 0, checked_artifacts: 0, checked_exports: 0, issues: [], orphan_counts: { artifacts: 0, receipts: 0, exports: 0 } },
      storage: { total_bytes: 1, artifact_bytes: 0, receipt_bytes: 0, database_bytes: 1, export_bytes: 0, manifest_bytes: 0, lock_bytes: 0 },
      migration: { current_schema_version: "1", status: "current" },
      records: { items: [], total_count: 0, limit: 50, offset: 0, has_more: false, next_offset: null },
      lifecycle: { retention_rows_in_snapshot: 0, retention_rows_in_page: 0, legal_holds_in_page: 0, deletion_tombstones: 0 },
      exports: { count: 0, items: [], supported_formats: ["json"] },
      backup: { history_status: "not_recorded", restore_eligibility: "not_evaluated", note: "not recorded" },
      operational_audit: { status: "not_recorded", note: "not recorded" },
      limitations: [],
    };
    const parsed = parseWorkspaceOperationsView(fixture);
    expect(parsed.workspace.mode).toBe("read-only");
    expect(parsed.storage.database_bytes).toBe(1);
    expect(() => parseWorkspaceOperationsView({ ...fixture, workspace: { ...fixture.workspace, mode: "read-write" } })).toThrow(/read-only sqlite/);
  });
});

describe("claim catalog schema", () => {
  const item = {
    record_id: "a".repeat(64),
    captured_at: "2026-09-29T00:00:00+00:00",
    run_id: "run-1",
    claim: "RAG answer verified",
    report_type: "engineering",
    decision: "review",
    verified: false,
    approval_status: "requires-human-approval",
    candidate: { id: "candidate-1", digest: "b".repeat(64) },
    profile: { id: "rag_answer_verified.v1", version: "1" },
    evidence: { included: 2, omitted: 0, missing: 1 },
    checks: { failed: 0, unrun: 1, unknown: 0 },
    human_decision_required: true,
    report_digest: "c".repeat(64),
    generated_at: "2026-09-29T00:00:00+00:00",
  };

  it("preserves bounded pagination and report identity without inventing authority", async () => {
    const { parseClaimCatalog } = await import("../lib/api/schemas");
    const parsed = parseClaimCatalog({
      schema_version: "claim-catalog.v1",
      scope: {
        resource: "verification-report-records",
        deduplication_key: "workspace receipt id",
        sort: "captured_at_desc_record_id_asc",
        scanned_receipts: 5,
        total_reports: 3,
        matched_reports: 1,
      },
      query: {
        decision: "review",
        verified: false,
        approval_status: null,
        profile_id: null,
        candidate_id: null,
        text: null,
        limit: 25,
        offset: 0,
      },
      page: { limit: 25, offset: 0, returned: 1, has_more: false, next_offset: null },
      items: [item],
      limitations: ["bounded"],
    });
    expect(parsed.items[0]?.human_decision_required).toBe(true);
    expect(parsed.items[0]?.approval_status).toBe("requires-human-approval");
    expect(parsed.scope.scanned_receipts).toBe(5);
  });

  it("fails closed when pagination claims more rows than are present", async () => {
    const { parseClaimCatalog } = await import("../lib/api/schemas");
    expect(() =>
      parseClaimCatalog({
        schema_version: "claim-catalog.v1",
        scope: {
          resource: "verification-report-records",
          deduplication_key: "workspace receipt id",
          sort: "captured_at_desc_record_id_asc",
          scanned_receipts: 1,
          total_reports: 1,
          matched_reports: 1,
        },
        query: {
          decision: null,
          verified: null,
          approval_status: null,
          profile_id: null,
          candidate_id: null,
          text: null,
          limit: 25,
          offset: 0,
        },
        page: { limit: 25, offset: 0, returned: 2, has_more: false, next_offset: null },
        items: [item],
        limitations: [],
      }),
    ).toThrow(/returned count/);
  });

  it("fails closed when has_more or next_offset contradicts the denominator", async () => {
    const { parseClaimCatalog } = await import("../lib/api/schemas");
    expect(() =>
      parseClaimCatalog({
        schema_version: "claim-catalog.v1",
        scope: {
          resource: "verification-report-records",
          deduplication_key: "workspace receipt id",
          sort: "captured_at_desc_record_id_asc",
          scanned_receipts: 3,
          total_reports: 3,
          matched_reports: 3,
        },
        query: {
          decision: null,
          verified: null,
          approval_status: null,
          profile_id: null,
          candidate_id: null,
          text: null,
          limit: 1,
          offset: 0,
        },
        page: { limit: 1, offset: 0, returned: 1, has_more: false, next_offset: null },
        items: [item],
        limitations: [],
      }),
    ).toThrow(/has_more/);
  });
});

describe("incident investigation schemas", () => {
  const incidentId = "1".repeat(64);
  const portfolioItem = {
    incident_id: incidentId,
    event_id: "event-1",
    detected_at: "2026-09-29T09:00:00+00:00",
    latest_recorded_at: "2026-09-29T10:00:00+00:00",
    actor: "detector",
    category: "storage-compromise",
    status: "reverified",
    observation_count: 2,
    evidence_ref_count: 2,
    affected_state_count: 1,
    uncertainty_count: 1,
    key_compromise_recorded: false,
    recovery: { recorded: true, status: "applied" },
    post_recovery: { recorded: true, status: "verified" },
    forensic_continuity_verified: true,
  };

  it("preserves recovered and reverified semantics in portfolio data", async () => {
    const { parseIncidentPortfolio } = await import("../lib/api/schemas");
    const parsed = parseIncidentPortfolio({
      schema_version: "incident-investigation.v1",
      scope: {
        resource: "security-incident-evidence",
        sort: "latest_recorded_at_desc_incident_id_asc",
        store_records: 2,
        total_incidents: 1,
        matched_incidents: 1,
      },
      query: { status: null, category: null, text: null, limit: 50, offset: 0 },
      page: { limit: 50, offset: 0, returned: 1, has_more: false, next_offset: null },
      items: [portfolioItem],
      limitations: ["bounded"],
    });
    expect(parsed.items[0]?.status).toBe("reverified");
    expect(parsed.items[0]?.recovery.status).toBe("applied");
    expect(parsed.items[0]?.forensic_continuity_verified).toBe(true);
  });

  it("fails closed if detail attempts to assert causality", async () => {
    const { parseIncidentDetail } = await import("../lib/api/schemas");
    const detail = {
      schema_version: "incident-detail.v1",
      incident: portfolioItem,
      lifecycle: [
        {
          sequence: 0,
          recorded_at: "2026-09-29T09:01:00+00:00",
          status: "reverified",
          record_digest: "2".repeat(64),
          incident_digest: "3".repeat(64),
        },
      ],
      evidence_refs: [
        { kind: "evidence", identity: "e-1", digest: "4".repeat(64), source_recorded: false },
      ],
      affected_states: [],
      security_event_digests: [],
      uncertainty: [],
      key_compromise: null,
      recovery: null,
      post_recovery: null,
      forensic_continuity: { required: true, verified: true, causality_established: false },
      limitations: ["bounded"],
    };
    expect(parseIncidentDetail(detail).forensic_continuity.causality_established).toBe(false);
    expect(() =>
      parseIncidentDetail({
        ...detail,
        forensic_continuity: { ...detail.forensic_continuity, causality_established: true },
      }),
    ).toThrow(/causality/);
  });
});

describe("capture health schema", () => {
  it("keeps zero recorded failures separate from capture success", async () => {
    const { parseCaptureHealth } = await import("../lib/api/schemas");
    const parsed = parseCaptureHealth({
      schema_version: "capture-health.v1",
      source: {
        resource: "native-capture-failure-journal",
        journal_exists: false,
        journal_bytes: 0,
        read_limit_bytes: 1024,
        declared_capacity_bytes: null,
        declared_capacity_state: "not-declared",
        declared_capacity_remaining_bytes: null,
      },
      observations: {
        recorded_failure_count: 0,
        distinct_stage_count: 0,
        distinct_error_type_count: 0,
        status: "no-failures-recorded",
        capture_success_inferred: false,
        workspace_durability_inferred: false,
        timestamps_available: false,
      },
      aggregates: { by_stage: [], by_error_type: [] },
      query: { stage: null, error_type: null, limit: 50, offset: 0 },
      page: { limit: 50, offset: 0, returned: 0, matched: 0, has_more: false, next_offset: null },
      items: [],
      limitations: ["absence is not proof of success"],
    });
    expect(parsed.observations.status).toBe("no-failures-recorded");
    expect(parsed.observations.capture_success_inferred).toBe(false);
  });

  it("rejects a server response that claims success inference", async () => {
    const { parseCaptureHealth } = await import("../lib/api/schemas");
    expect(() =>
      parseCaptureHealth({
        schema_version: "capture-health.v1",
        source: {
          resource: "native-capture-failure-journal",
          journal_exists: true,
          journal_bytes: 1,
          read_limit_bytes: 1024,
          declared_capacity_bytes: null,
          declared_capacity_state: "not-declared",
          declared_capacity_remaining_bytes: null,
        },
        observations: {
          recorded_failure_count: 0,
          distinct_stage_count: 0,
          distinct_error_type_count: 0,
          status: "no-failures-recorded",
          capture_success_inferred: true,
          workspace_durability_inferred: false,
          timestamps_available: false,
        },
        aggregates: { by_stage: [], by_error_type: [] },
        query: { stage: null, error_type: null, limit: 50, offset: 0 },
        page: { limit: 50, offset: 0, returned: 0, matched: 0, has_more: false, next_offset: null },
        items: [],
        limitations: [],
      }),
    ).toThrow(/must not infer/);
  });
});

describe("attestation trust schema", () => {
  const base: AttestationTrustView = {
    schema_version: "attestation-trust-investigation.v3",
    sources: {
      attestation_store: {
        configured: true,
        exists: true,
        byte_size: 100,
        read_limit_bytes: 1024,
        record_limit: 100,
        signed_binding_count: 0,
        chain_integrity: "verified",
      },
      trust_state: {
        configured: true,
        derived_from_history: false,
        present: true,
        version: 3,
        issued_at: "2026-09-29T11:00:00+00:00",
        digest: "d".repeat(64),
        previous_digest: "c".repeat(64),
        authority_key_id: "authority-1",
        authentication: {
          status: "verified",
          authenticated: true,
          reason: "verified",
          authority_key_digest: "e".repeat(64),
        },
        anchor_count: 1,
        anchors: [{
          key_id: "key-active",
          public_key_digest: "f".repeat(64),
          recorded_status: "active",
          superseded_by: null,
          current_trust_applicable: true,
        }],
      },
      authority_store: { configured: true, raw_keys_exposed: false },
      trust_history: {
        configured: true,
        exists: true,
        byte_size: 500,
        read_limit_bytes: 4096,
        record_limit: 100,
        state_count: 2,
        chain_integrity: "verified",
        authentication_status: "verified",
        lifecycle_authoritative: true,
        first_version: 2,
        latest_version: 3,
        tip_digest: "d".repeat(64),
        current_tip_alignment: "verified",
        states: [
          { version: 2, issued_at: "2026-09-29T10:00:00+00:00", digest: "c".repeat(64), previous_digest: null, authority_key_id: "authority-1", anchor_count: 1 },
          { version: 3, issued_at: "2026-09-29T11:00:00+00:00", digest: "d".repeat(64), previous_digest: "c".repeat(64), authority_key_id: "authority-1", anchor_count: 1 },
        ],
        transitions: [{
          from_version: 2,
          to_version: 3,
          from_digest: "c".repeat(64),
          to_digest: "d".repeat(64),
          issued_at: "2026-09-29T11:00:00+00:00",
          authority_key_id: "authority-1",
          authority_changed: false,
          activated_key_ids: [],
          revoked_key_ids: [],
          superseded_keys: [],
          removed_key_ids: [],
        }],
      },
    },
    summary: {
      total_attestations: 1,
      signing_key_references: 1,
      signed_envelope_records: 0,
      verified_signed_bindings: 0,
      unsigned_attestations: 0,
      active_key_references: 1,
      revoked_key_references: 0,
      superseded_key_references: 0,
      untrusted_key_references: 0,
      unauthenticated_key_references: 0,
      unconfigured_trust_state_references: 0,
      historically_observed_key_references: 1,
      historically_active_key_references: 1,
    },
    query: { decision: null, reliability_state: null, key_status: null, text: null, limit: 50, offset: 0 },
    page: { limit: 50, offset: 0, returned: 1, matched: 1, has_more: false, next_offset: null },
    items: [{
      sequence: 0,
      attestation_id: "att-1",
      subject_id: "agent-1",
      occurred_at: "2026-09-29T10:00:00+00:00",
      actor: "operator",
      evidence_chain_id: "chain-att-1",
      evidence_chain_digest: "a".repeat(64),
      transition_id: "transition-att-1",
      transition_digest: "b".repeat(64),
      reliability_state: "reliable",
      decision: "accept",
      verification_status: "verified",
      reconciliation_state: "verified",
      previous_digest: "",
      attestation_digest: "1".repeat(64),
      key_context: {
        signing_key_id: "key-active",
        key_version: null,
        recorded_anchor_status: "active",
        effective_current_status: "active",
        currently_trusted_for_signing: true,
        superseded_by: null,
        public_key_digest: "f".repeat(64),
        trust_state_version: 3,
        historical_context: {
          history_authenticated: true,
          observed_in_authenticated_history: true,
          ever_observed_active: true,
          observed_statuses: ["active"],
          latest_observed_status: "active",
          first_observed_version: 2,
          last_observed_version: 3,
          attestation_time_binding_recorded: false,
          attestation_time_status: null,
        },
      },
      signature_envelope_recorded: false,
      signing_trust_context: {
        recorded: false,
        authentication: { status: "not-recorded", authenticated: null, reason: "not recorded" },
        trust_state_version: null,
        trust_state_digest: null,
        signing_key_digest: null,
        authority_key_id: null,
        authority_key_digest: null,
        signing_time_key_status: null,
        trusted_timestamp_recorded: false,
      },
    }],
    limitations: ["Signature-envelope authenticity is not evaluated."],
  };

  it("accepts a bounded authenticated projection without raw key material", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const parsed = parseAttestationTrust(base);
    expect(parsed.sources.trust_state.authentication.authenticated).toBe(true);
    expect(parsed.items[0]?.key_context.effective_current_status).toBe("active");
    expect(JSON.stringify(parsed)).not.toContain("private_key");
  });

  it("fails closed if unauthenticated trust state is presented as current authority", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const malformed = structuredClone(base);
    malformed.sources.trust_state.authentication = {
      status: "failed",
      authenticated: false,
      reason: "signature failed",
      authority_key_digest: "e".repeat(64),
    };
    expect(() => parseAttestationTrust(malformed)).toThrow(/current trust authority|current key lifecycle/);
  });

  it("rejects inconsistent signed-envelope and signing-context evidence", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const malformed = structuredClone(base);
    malformed.items[0]!.signature_envelope_recorded = true;
    expect(() => parseAttestationTrust(malformed)).toThrow(/recording state must agree/);
  });

  it("accepts a verified canonical signed binding without raw cryptographic material", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const signed = structuredClone(base);
    signed.sources.attestation_store.signed_binding_count = 1;
    signed.summary.signed_envelope_records = 1;
    signed.summary.verified_signed_bindings = 1;
    signed.items[0]!.signature_envelope_recorded = true;
    signed.items[0]!.signing_trust_context = {
      recorded: true,
      authentication: { status: "verified", authenticated: true, reason: "verified" },
      trust_state_version: 3,
      trust_state_digest: "d".repeat(64),
      signing_key_digest: "f".repeat(64),
      authority_key_id: "authority-1",
      authority_key_digest: "e".repeat(64),
      signing_time_key_status: "active",
      trusted_timestamp_recorded: false,
    };
    const parsed = parseAttestationTrust(signed);
    expect(parsed.items[0]?.signing_trust_context.authentication.authenticated).toBe(true);
    const serialized = JSON.stringify(parsed);
    expect(serialized).not.toContain('"signature":');
    expect(serialized).not.toContain('"signature_hex":');
    expect(serialized).not.toContain('"public_key":');
    expect(serialized).not.toContain('"private_key":');
  });

  it("rejects historical lifecycle claims without authenticated history", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const malformed = structuredClone(base);
    malformed.sources.trust_history.authentication_status = "authority-not-configured";
    malformed.sources.trust_history.lifecycle_authoritative = false;
    malformed.sources.trust_history.transitions = [];
    malformed.items[0]!.key_context.historical_context.history_authenticated = null;
    expect(() => parseAttestationTrust(malformed)).toThrow(/historical lifecycle/);
  });

  it("rejects invented attestation-time trust status and unknown assurance fields", async () => {
    const { parseAttestationTrust } = await import("../lib/api/schemas");
    const malformed = structuredClone(base) as typeof base & { stronger_assurance?: boolean };
    malformed.items[0]!.key_context.historical_context.attestation_time_binding_recorded = true as false;
    expect(() => parseAttestationTrust(malformed)).toThrow(/attestation-time trust/);
    const unknown = structuredClone(base) as typeof base & { stronger_assurance?: boolean };
    unknown.stronger_assurance = true;
    expect(() => parseAttestationTrust(unknown)).toThrow(/missing or unsupported/);
  });
});

describe("reliability proof investigation schema", () => {
  const proofFixture = {
    schema_version: "proof-bundle-investigation.v1",
    bundle: {
      bundle_id: "a".repeat(64),
      manifest_id: "b".repeat(64),
      engine_version: "0.4.1",
      created_at: "2026-09-29T00:00:00+00:00",
      artifact_count: 1,
    },
    proof: {
      format_version: "3",
      bundle_type: "reliability-proof",
      descriptor_digest: "c".repeat(64),
      subject_id: "agent-1",
      attestation_id: "att-1",
      attestation_digest: "d".repeat(64),
      evidence_chain_id: "chain-1",
      evidence_chain_digest: "e".repeat(64),
      transition_id: "transition-1",
      transition_digest: "f".repeat(64),
      reliability_state: "reliable",
      decision: "accept",
      verification_report_digest: "1".repeat(64),
    },
    verification: {
      verified: true,
      checks: ["attestation_integrity"],
      failures: [],
      offline_reverification_succeeded: true,
      source_set_complete: true,
    },
    lineage: { required_by_format: true, present: true, status: "verified", digest: "2".repeat(64) },
    completeness: { required_by_format: true, present: true, status: "verified", artifact_id: "proof-completeness", digest: "3".repeat(64) },
    trust_context: {
      present: false,
      portable_cryptographic_consistency_verified: false,
      external_authority_trust_established: false,
      signing_key_id: null,
      signing_key_digest: null,
      trust_state_version: null,
      trust_state_digest: null,
      authority_key_id: null,
      authority_key_digest: null,
    },
    cryptographic_profile: null,
    sources: [{ reference_key: "run", source_label: "run.json", artifact_id: "source-1", packaged_digest: "4".repeat(64), bound_digest: "4".repeat(64) }],
    artifacts: [{ artifact_id: "proof-attestation", kind: "reliability-outcome-attestation", sha256: "5".repeat(64), size_bytes: 100, sensitivity: "restricted", derived_from: [] }],
    portable_dataset_boundary: { this_is_reliability_proof: true, workspace_portable_dataset_is_distinct: true, note: "distinct format" },
    authorization: { human_approval_evaluated: false, publication_authorized: false, release_authorized: false },
    limitations: ["bounded verification only"],
  };

  it("preserves verification, authority, and dataset boundaries", async () => {
    const { parseReliabilityProofInvestigation } = await import("../lib/api/schemas");
    const parsed = parseReliabilityProofInvestigation(proofFixture);
    expect(parsed.verification.verified).toBe(true);
    expect(parsed.authorization.publication_authorized).toBe(false);
    expect(parsed.trust_context.external_authority_trust_established).toBe(false);
    expect(parsed.portable_dataset_boundary.workspace_portable_dataset_is_distinct).toBe(true);
  });

  it("rejects invented release authorization", async () => {
    const { parseReliabilityProofInvestigation } = await import("../lib/api/schemas");
    expect(() => parseReliabilityProofInvestigation({
      ...proofFixture,
      authorization: { ...proofFixture.authorization, release_authorized: true },
    })).toThrow(/authorize/);
  });

  it("rejects artifact path/content leakage", async () => {
    const { parseReliabilityProofInvestigation } = await import("../lib/api/schemas");
    expect(() => parseReliabilityProofInvestigation({
      ...proofFixture,
      artifacts: [{ ...proofFixture.artifacts[0], path: "proof/secret.json" }],
    })).toThrow(/paths or content/);
  });
});

describe("decision lineage investigation schema", () => {
  const decisionFixture = {
    schema_version: "decision-lineage-investigation.v1",
    chain: {
      chain_id: "chain-1",
      digest: "a".repeat(64),
      verification_status: "verified",
      reliability_state: "reliable",
      reconciliation_state: "verified",
      decision: "accept",
      evidence_count: 1,
      rationale_count: 1,
      rationale_exposed: false,
    },
    decision_basis: {
      present: true,
      basis_type: "manual",
      basis_id: "basis-1",
      version: "1",
      digest: "b".repeat(64),
      decision: "accept",
      reliability_state: "reliable",
      input_count: 2,
      policy_id: null,
      policy_version: null,
      policy_digest: null,
      rationale_count: 1,
      rationale_exposed: false,
    },
    decision_inputs: [
      {
        digest: "c".repeat(64),
        semantic_roles: ["evidence:0"],
        classification: "lineage-bound",
        lineage_roles: ["evidence:0"],
        reachable_to_run: true,
      },
      {
        digest: "d".repeat(64),
        semantic_roles: ["integrity"],
        classification: "verification-context",
        lineage_roles: [],
        reachable_to_run: null,
      },
    ],
    comparison: { present: false },
    reconciliation: { present: false },
    recovery: { present: false },
    lineage: {
      verified: true,
      provenance_graph_digest: "e".repeat(64),
      closure_digest: "f".repeat(64),
      run_role: "run",
      reachable_roles: ["evidence:0", "decision_basis"],
      bindings: [
        {
          role: "run",
          node_id: "run",
          identity: "run-1",
          digest: "1".repeat(64),
          reachable_to_run: true,
        },
      ],
    },
    verification: {
      evidence_chain_verified: true,
      decision_basis_verified: true,
      comparison_verified: false,
      reconciliation_binding_verified: false,
      recovery_outcome_verified: false,
      lineage_closure_verified: true,
    },
    authorization: {
      business_authorization_evaluated: false,
      human_approval_evaluated: false,
      publication_authorized: false,
    },
    limitations: ["bounded relationships only"],
  };

  it("keeps graph lineage and verification context distinct", async () => {
    const { parseDecisionLineage } = await import("../lib/api/schemas");
    const parsed = parseDecisionLineage(decisionFixture);
    expect(parsed.decision_inputs[0]!.reachable_to_run).toBe(true);
    expect(parsed.decision_inputs[1]!.reachable_to_run).toBeNull();
    expect(parsed.authorization.publication_authorized).toBe(false);
  });

  it("rejects invented reachability for verification context", async () => {
    const { parseDecisionLineage } = await import("../lib/api/schemas");
    const malformed = structuredClone(decisionFixture);
    malformed.decision_inputs[1]!.reachable_to_run = true;
    expect(() => parseDecisionLineage(malformed)).toThrow(/must not invent graph reachability/);
  });

  it("rejects invented business authorization", async () => {
    const { parseDecisionLineage } = await import("../lib/api/schemas");
    const malformed = structuredClone(decisionFixture);
    malformed.authorization.business_authorization_evaluated = true;
    expect(() => parseDecisionLineage(malformed)).toThrow(/must not infer authorization/);
  });
});

describe("security assurance investigation schema", () => {
  const securityFixture = {
    schema_version: "security-assurance-investigation.v2",
    source: {
      resource: "deployment-security-audit-journal",
      configured: true,
      exists: true,
      byte_size: 512,
      read_limit_bytes: 8192,
      record_limit: 100,
      chain_integrity: "verified",
      source_path_exposed: false,
    },
    observations: {
      recorded_event_count: 1,
      authentication_failed_count: 0,
      authorization_denied_count: 0,
      request_rejected_count: 0,
      request_admitted_count: 1,
      distinct_operation_count: 1,
      distinct_route_kind_count: 1,
      deployment_secure_inferred: false,
      live_configuration_observed: false,
      runtime_configuration_snapshot_observed: true,
    },
    runtime_containment: {
      snapshot_observed: true,
      configuration_digest: "d".repeat(64),
      recorded_at_utc: "2026-09-30T12:00:00+00:00",
      verification_service: {
        max_request_bytes: 1048576,
        read_only: true,
        require_https: true,
        allow_insecure_http: false,
        artifact_root_count: 1,
        artifact_roots_exposed: false,
      },
      limits: {
        max_input_bytes: 67108864,
        max_archive_members: 256,
        max_archive_uncompressed_bytes: 134217728,
        max_archive_compression_ratio: 100,
        max_json_depth: 64,
        max_json_nodes: 10000,
        max_string_bytes: 262144,
        max_graph_nodes: 10000,
        max_verification_seconds: 30,
        max_concurrency: 4,
        max_temporary_bytes: 134217728,
      },
      enforcement: {
        request_body_bytes: "verification-service-enforced",
        json_input_bytes: "verification-service-enforced",
        json_depth: "verification-service-enforced",
        json_nodes: "verification-service-enforced",
        json_string_bytes: "verification-service-enforced",
        archive_members: "domain-control-not-wired-to-service-runtime-limits",
        archive_uncompressed_bytes: "domain-control-not-wired-to-service-runtime-limits",
        archive_compression_ratio: "domain-control-not-wired-to-service-runtime-limits",
        graph_nodes: "configured-limit-not-enforced-by-verification-service",
        verification_seconds: "cooperative-primitive-not-wired-to-verification-service",
        concurrency: "configured-limit-not-enforced-by-verification-service",
        temporary_bytes: "configured-limit-not-enforced-by-verification-service",
      },
      host_controls_evaluated: false,
    },
    deployment_boundary: {
      configuration_snapshot_available: false,
      protected_operations: ["verify:evidence"],
      default_public_paths: ["/health", "/v1/version"],
      default_require_https: true,
      authentication_provider: "host-provided",
      authorization_provider: "host-provided",
      request_admission_provider: "optional-host-provided",
      security_event_sink: "optional-host-provided",
      host_responsibilities: ["tls-termination-and-network-boundary"],
    },
    aggregates: {
      by_event: [{ event: "request_admitted", count: 1 }],
      by_operation: [{ operation: "verify:evidence", count: 1 }],
      by_reason: [{ reason: "authorized", count: 1 }],
      by_method: [{ method: "POST", count: 1 }],
      by_route_kind: [{ route_kind: "evidence-verification", count: 1 }],
    },
    query: { event: null, operation: null, reason: null, method: null, limit: 50, offset: 0 },
    page: { limit: 50, offset: 0, returned: 1, matched: 1, has_more: false, next_offset: null },
    items: [{
      sequence: 0,
      occurred_at: "2026-09-29T12:00:00+00:00",
      event: "request_admitted",
      operation: "verify:evidence",
      method: "POST",
      route_kind: "evidence-verification",
      path_digest: "a".repeat(64),
      path_exposed: false,
      reason: "authorized",
      reason_digest: "b".repeat(64),
      previous_digest: null,
      digest: "c".repeat(64),
    }],
    limitations: ["bounded audit evidence only"],
  };

  it("preserves observed evidence without inferring live deployment security", async () => {
    const { parseSecurityAssurance } = await import("../lib/api/schemas");
    const parsed = parseSecurityAssurance(securityFixture);
    expect(parsed.observations.deployment_secure_inferred).toBe(false);
    expect(parsed.deployment_boundary.configuration_snapshot_available).toBe(false);
    expect(parsed.items[0]?.path_exposed).toBe(false);
  });

  it("rejects a response that claims live deployment security or exposes paths", async () => {
    const { parseSecurityAssurance } = await import("../lib/api/schemas");
    const claimedSecure = structuredClone(securityFixture);
    claimedSecure.observations.deployment_secure_inferred = true as false;
    expect(() => parseSecurityAssurance(claimedSecure)).toThrow(/must not infer live deployment security/);

    const leakedPath = structuredClone(securityFixture);
    leakedPath.items[0]!.path_exposed = true as false;
    expect(() => parseSecurityAssurance(leakedPath)).toThrow(/must not expose recorded paths/);
  });

  it("rejects runtime-containment enforcement inflation and unknown assurance fields", async () => {
    const { parseSecurityAssurance } = await import("../lib/api/schemas");
    const inflated = structuredClone(securityFixture);
    inflated.runtime_containment.enforcement.concurrency = "verification-service-enforced" as never;
    expect(() => parseSecurityAssurance(inflated)).toThrow(/exceeds the current implementation/);

    const unknown = structuredClone(securityFixture) as typeof securityFixture & { stronger_assurance?: boolean };
    unknown.stronger_assurance = true;
    expect(() => parseSecurityAssurance(unknown)).toThrow(/fields are missing or unsupported/);
  });
});

describe("assurance decision investigation schema", () => {
  const fixture = {
    schema_version: "assurance-decision-investigation.v1",
    decision: {
      decision: "ALLOW_WITH_LIMITATIONS",
      digest: "a".repeat(64),
      subject_id_digest: "b".repeat(64),
      policy_id: "statewake-security-assurance",
      policy_version: "1",
      policy_rule: "reliability-degraded",
      generated_at: "2026-09-30T00:00:00+00:00",
      source_reliability_state: "degraded",
      source_verification_status: "verified",
      evidence_reference_digests: ["c".repeat(64)],
      verification_results: ["verified"],
      residual_risk: ["manual review remains"],
      system_state_unchanged: true,
      semantic_replay_verified: true,
      rationale_exposed: false,
    },
    exception: {
      present: true,
      exception_id_digest: "d".repeat(64),
      binding: "exact-decision-digest",
      decision_digest: "a".repeat(64),
      status: "active",
      created_at: "2026-09-30T00:00:00+00:00",
      expires_at: "2026-10-01T00:00:00+00:00",
      authorized_by_digest: "e".repeat(64),
      compensating_control: "manual verification",
      reverification_required: "before expiry",
      evidence_reference_digests: ["c".repeat(64)],
      system_state_preserved: true,
    },
    authorization: {
      factual_correctness_evaluated: false,
      publication_authorized: false,
      compliance_certified: false,
      host_authorization_inferred: false,
    },
    limitations: ["bounded read artifact"],
  };

  it("preserves exact exception binding without inferring authorization", async () => {
    const { parseAssuranceDecision } = await import("../lib/api/schemas");
    const parsed = parseAssuranceDecision(fixture);
    expect(parsed.exception.present).toBe(true);
    expect(parsed.authorization.publication_authorized).toBe(false);
  });

  it("rejects raw identity leakage or false state mutation", async () => {
    const { parseAssuranceDecision } = await import("../lib/api/schemas");
    const leaked = structuredClone(fixture) as typeof fixture & { decision: typeof fixture.decision & { subject_id?: string } };
    leaked.decision.subject_id = "raw-subject";
    expect(() => parseAssuranceDecision(leaked)).toThrow(/must not expose raw subject identity/);

    const mutated = structuredClone(fixture);
    mutated.decision.system_state_unchanged = false as true;
    expect(() => parseAssuranceDecision(mutated)).toThrow(/preserve state/);
  });
});

describe("access authorization investigation schema", () => {
  const fixture = {
    schema_version: "access-authorization-investigation.v1",
    source: {
      resource: "explicit-authorization-context-artifact",
      configured: true,
      source_path_exposed: false,
      canonical_iam_store: false,
    },
    principal: {
      principal_id_digest: "a".repeat(64),
      principal_id_exposed: false,
      status: "ACTIVE",
      roles: ["reader"],
      expires_at: null,
      active_at_request: true,
      resource_scope_domain_count: 1,
      resource_scope_resource_count: 1,
      resource_scopes: [{ resource_domain_digest: "b".repeat(64), resource_id_digests: ["c".repeat(64)], resource_count: 1 }],
    },
    request: {
      operation: "READ",
      resource_domain_digest: "b".repeat(64),
      resource_id_digest: "c".repeat(64),
      resource_identity_exposed: false,
      resource_state: "verified",
      requested_at: "2026-09-30T00:00:00+00:00",
    },
    policy: {
      deny_by_default: true,
      grant_count: 1,
      grants: [{ role: "reader", operation: "READ", allowed_states: ["verified"] }],
    },
    evaluation: {
      principal_active: true,
      resource_scope_match: true,
      matching_grant_count: 1,
      recorded_decision_present: true,
      recorded_decision_verified: true,
      policy_replay_verified: true,
    },
    decision: {
      allowed: true,
      reason: "authorized",
      matched_role: "reader",
      operation: "READ",
      resource_state: "verified",
      principal_id_digest: "a".repeat(64),
      resource_domain_digest: "b".repeat(64),
      resource_id_digest: "c".repeat(64),
    },
    authorization_boundary: {
      principal_authentication_evaluated: false,
      identity_provider: "external-host",
      session_validity_evaluated: false,
      mfa_evaluated: false,
      tls_evaluated: false,
      tenant_isolation_evaluated: false,
      iam_provider: false,
      business_authorization_inferred: false,
    },
    limitations: ["not an IAM database"],
  };

  it("accepts a replay-verified privacy-safe authorization projection", async () => {
    const { parseAccessAuthorization } = await import("../lib/api/schemas");
    const parsed = parseAccessAuthorization(fixture);
    expect(parsed.decision.allowed).toBe(true);
    expect(parsed.authorization_boundary.principal_authentication_evaluated).toBe(false);
  });

  it("rejects raw principal/resource identity or invented IAM authority", async () => {
    const { parseAccessAuthorization } = await import("../lib/api/schemas");
    const leakedPrincipal = structuredClone(fixture) as typeof fixture & { principal: typeof fixture.principal & { principal_id?: string } };
    leakedPrincipal.principal.principal_id = "alice";
    expect(() => parseAccessAuthorization(leakedPrincipal)).toThrow(/must not expose raw principal identity/);

    const leakedResource = structuredClone(fixture) as typeof fixture & { request: typeof fixture.request & { resource_id?: string } };
    leakedResource.request.resource_id = "secret-resource";
    expect(() => parseAccessAuthorization(leakedResource)).toThrow(/must not expose raw resource identity/);

    const iam = structuredClone(fixture);
    iam.authorization_boundary.iam_provider = true as false;
    expect(() => parseAccessAuthorization(iam)).toThrow(/must not infer external authentication or IAM authority/);
  });
});
