export interface ClaimCatalogItem {
  record_id: string;
  captured_at: string;
  run_id: string | null;
  claim: string;
  report_type: string;
  decision: string;
  verified: boolean;
  approval_status: string;
  candidate: { id: string; digest: string };
  profile: { id: string; version: string };
  evidence: { included: number; omitted: number; missing: number };
  checks: { failed: number; unrun: number; unknown: number };
  human_decision_required: boolean;
  report_digest: string;
  generated_at: string;
}

export interface ClaimCatalog {
  schema_version: "claim-catalog.v1";
  scope: {
    resource: "verification-report-records";
    deduplication_key: string;
    sort: "captured_at_desc_record_id_asc";
    scanned_receipts: number;
    total_reports: number;
    matched_reports: number;
  };
  query: {
    decision: string | null;
    verified: boolean | null;
    approval_status: string | null;
    profile_id: string | null;
    candidate_id: string | null;
    text: string | null;
    limit: number;
    offset: number;
  };
  page: {
    limit: number;
    offset: number;
    returned: number;
    has_more: boolean;
    next_offset: number | null;
  };
  items: ClaimCatalogItem[];
  limitations: string[];
}

export interface ClaimReason {
  kind: string;
  source_ref: string;
  text: string;
}

export interface ClaimSummary {
  schema_version: "claim-summary.v1";
  candidate: { id: string; digest: string };
  profile: { id: string; version: string };
  claim: string;
  decision: string;
  verification: {
    verified: boolean;
    passed: number;
    failed: number;
    unrun: number;
    unknown: number;
  };
  evidence: { included: number; omitted: number; missing: number };
  reasons: ClaimReason[];
  human_decision: {
    required: boolean;
    approval_status: string;
    required_actions: string[];
  };
  caveats: string[];
  residual_risks: string[];
  report_digest: string;
  generated_at: string;
  as_of: null;
}

export interface ClaimDetail {
  schema_version: "claim-detail.v1";
  source: {
    record_id: string;
    artifact_digest: string;
    producer_id: string;
    producer_type: string;
    captured_at: string;
    run_id: string | null;
    sensitivity: string | null;
  };
  summary: ClaimSummary;
  checks: { passed: string[]; failed: string[]; unrun: string[]; unknown: string[] };
  evidence: {
    included: string[];
    omitted: string[];
    missing: string[];
    source_identities: string[];
    artifact_digests: string[];
  };
  decision_rationale: string[];
  recovery_status: string;
  allowed_use: string[];
  prohibited_use: string[];
  machine_readable_appendix: string[];
  profile_evaluation_digest: string | null;
  verifier_version: string;
  generated_at: string;
  report_digest: string;
  links: { canonical_json: string; canonical_markdown: string };
}

export interface ClaimHistoryItem {
  sequence: number;
  transition_id: string;
  subject_id: string;
  from_state: string;
  to_state: string;
  occurred_at: string;
  actor: string;
  evidence_chain_id: string;
  evidence_chain_digest: string;
  decision: string;
  rationale: string[];
  previous_transition_digest: string;
  transition_digest: string;
}

export interface ClaimHistory {
  schema_version: "claim-history.v1";
  report_record_id: string;
  candidate: { id: string; digest: string };
  profile: { id: string; version: string };
  recorded_count: number;
  items: ClaimHistoryItem[];
  limitations: string[];
}

export interface StringDelta {
  added: string[];
  removed: string[];
}

export interface ClaimComparisonSide {
  record_id: string;
  report_digest: string;
  candidate: { id: string; digest: string };
  profile: { id: string; version: string };
  claim: string;
  report_type: string;
  decision: string;
  verified: boolean;
  approval_status: string;
  generated_at: string;
  captured_at: string;
}

export interface ClaimComparison {
  schema_version: "claim-comparison.v1";
  semantic_scope_same: boolean;
  non_equivalence_warnings: string[];
  left: ClaimComparisonSide;
  right: ClaimComparisonSide;
  changes: {
    candidate_digest_changed: boolean;
    decision: { before: string; after: string; changed: boolean };
    verified: { before: boolean; after: boolean; changed: boolean };
    approval_status: { before: string; after: string; changed: boolean };
    checks: {
      passed: StringDelta;
      failed: StringDelta;
      unrun: StringDelta;
      unknown: StringDelta;
    };
    evidence: {
      included: StringDelta;
      missing: StringDelta;
      omitted: StringDelta;
    };
    caveats: StringDelta;
    residual_risks: StringDelta;
    human_decisions_required: StringDelta;
  };
  limitations: string[];
}

export interface ApiErrorEnvelope {
  error: { code: string; message: string };
}

export type ReviewCategory =
  | "observation"
  | "question"
  | "change_requested"
  | "finding"
  | "review_complete";

export interface ReviewCapabilities {
  schema_version: "review-capabilities.v1";
  mode: string;
  statewake_version: string;
  actor: { identity_ref: string; role: string };
  features: {
    review_read: boolean;
    review_write: boolean;
    approval_read: boolean;
    approval_write: boolean;
    approval_revoke: boolean;
    approval_supersede: boolean;
  };
  approval: { configured: true; note: string } | null;
  limits: {
    statement_chars: number;
    limitation_chars: number;
    finding_refs: number;
    approval_reason_chars: number;
  };
}

export interface ReviewStatementRecord {
  schema_version: "review-statement.v1";
  sequence: number;
  target_record_id: string;
  candidate_identity: string;
  candidate_digest: string;
  report_digest: string;
  profile_id: string;
  profile_version: string;
  actor_identity_ref: string;
  actor_role: string;
  category: ReviewCategory;
  statement: string;
  finding_refs: string[];
  limitation: string | null;
  scope: string;
  created_at: string;
  idempotency_key: string;
  request_fingerprint: string;
  supersedes_digest: string | null;
  previous_digest: string | null;
  digest: string;
}

export interface ReviewThread {
  schema_version: "review-thread.v1";
  target: {
    record_id: string;
    candidate_identity: string;
    candidate_digest: string;
    report_digest: string;
    profile_id: string;
    profile_version: string;
  };
  items: ReviewStatementRecord[];
  limitations: string[];
}

export interface ReviewStatementInput {
  schema_version: "review-statement-input.v1";
  candidate_digest: string;
  report_digest: string;
  category: ReviewCategory;
  statement: string;
  finding_refs: string[];
  limitation: string | null;
  scope: string;
  supersedes_digest: string | null;
}

export interface ReviewStatementResult {
  schema_version: "review-statement-result.v1";
  created: boolean;
  approval_created: false;
  review: ReviewStatementRecord;
}

export interface OverviewReportItem {
  record_id: string;
  claim: string;
  decision: string;
  verified: boolean;
  approval_status: string;
  candidate: { id: string; digest: string };
  profile: { id: string; version: string };
  captured_at: string;
  report_digest: string;
}

export interface OverviewProjection {
  schema_version: "overview.v1";
  scope: {
    resource: "verification-report-records";
    denominator: number;
    deduplication_key: string;
  };
  as_of: string | null;
  metrics: {
    reports_evaluated: number;
    verified_reports: number;
    reports_missing_evidence: number;
    human_decisions_pending: number;
  };
  decisions: { accept: number; review: number; reject: number; other: number };
  recent_reports: OverviewReportItem[];
  limitations: string[];
}

export interface HumanApprovalContractDto {
  schema_version: "statewake.ai_contract.v1";
  contract_type: "human_approval";
  contract_version: string;
  producer_id: string;
  run_id: string;
  actor_identity_ref: string;
  role: string;
  approval_action: string;
  approval_basis_digest: string;
  scope: string;
  captured_at: string;
  metadata: Record<string, unknown>;
}

export interface EvidenceReceiptDto {
  receipt_id: string;
  receipt_digest: string;
  artifact_digest: string;
  captured_at: string;
  producer_id: string;
  run_id: string | null;
}

export interface HumanApprovalRevocationContractDto {
  schema_version: "statewake.ai_contract.v1";
  contract_type: "human_approval_revocation";
  contract_version: string;
  producer_id: string;
  run_id: string;
  actor_identity_ref: string;
  role: string;
  approval_action: string;
  approval_basis_digest: string;
  scope: string;
  target_approval_receipt_id: string;
  target_approval_receipt_digest: string;
  reason: string;
  captured_at: string;
  metadata: Record<string, unknown>;
}

export interface HumanApprovalRevocationEvidence {
  contract: HumanApprovalRevocationContractDto;
  receipt: EvidenceReceiptDto;
}

export interface HumanApprovalEvidence {
  contract: HumanApprovalContractDto;
  receipt: EvidenceReceiptDto;
  lifecycle?: {
    status: "active" | "revoked" | "superseded";
    superseded_by_receipt_id: string | null;
    revocation: HumanApprovalRevocationEvidence | null;
  };
}

export interface HumanApprovalThread {
  schema_version: "human-approval-thread.v1";
  target: {
    record_id: string;
    candidate_identity: string;
    candidate_digest: string;
    report_digest: string;
    profile_id: string;
    profile_version: string;
  };
  authority: {
    approval_action: string;
    scope: string;
  };
  items: HumanApprovalEvidence[];
  active_approval_receipt_ids: string[];
  limitations: string[];
}

export interface HumanApprovalInput {
  schema_version: "human-approval-input.v1";
  candidate_digest: string;
  report_digest: string;
  reason: string;
  confirmed: true;
}

export interface HumanApprovalLifecycleInput {
  schema_version: "human-approval-lifecycle-input.v1";
  candidate_digest: string;
  report_digest: string;
  reason: string;
  confirmed: true;
}

export interface HumanApprovalResult {
  schema_version: "human-approval-result.v1";
  created: boolean;
  approval: HumanApprovalEvidence;
  effects: {
    verification_report_mutated: false;
    machine_decision_changed: false;
    release_published: false;
    side_effect_authorized_outside_scope: false;
  };
  limitations: string[];
}

export interface HumanApprovalLifecycleResult {
  schema_version: "human-approval-lifecycle-result.v1";
  operation: "revoke" | "supersede";
  created: boolean;
  approval: HumanApprovalEvidence | null;
  revocation: HumanApprovalRevocationEvidence | null;
  effects: {
    verification_report_mutated: false;
    machine_decision_changed: false;
    release_published: false;
    side_effect_authorized_outside_scope: false;
  };
  limitations: string[];
}

export interface EvidenceTraceNode {
  node_id: string;
  kind: string;
  identity: string;
  label: string;
  digest: string | null;
  digest_kind: string | null;
  integrity_status: string;
  availability: string;
  record_id: string | null;
  producer_id: string | null;
  producer_type: string | null;
  captured_at: string | null;
  run_id: string | null;
  source_event_id: string | null;
  artifact_size: number | null;
  receipt_digest: string | null;
  receipt_integrity_status: string | null;
  artifact_integrity_status: string | null;
  admission_status: string | null;
  admission_digest: string | null;
  producer_authentication_status: string | null;
}

export interface EvidenceTraceEdge {
  edge_id: string;
  source: string;
  target: string;
  relationship_type: string;
  basis: string;
  occurrences: number;
}

export interface EvidenceTraceUnresolved {
  kind: string;
  identity: string;
  reason: string;
}

export interface EvidenceTrace {
  schema_version: "evidence-trace.v2";
  report_record_id: string;
  report_digest: string;
  candidate: { id: string; digest: string };
  nodes: EvidenceTraceNode[];
  edges: EvidenceTraceEdge[];
  unresolved: EvidenceTraceUnresolved[];
  workspace_scan: {
    records_scanned: number;
    records_available: number;
    complete: boolean;
  };
  assurance_summary: {
    receipts_resolved: number;
    receipt_integrity_verified: number;
    artifact_integrity_verified: number;
    admission_verified: number;
  };
  producer_authentication: {
    status: "not-recorded";
    authenticated: null;
    reason: string;
  };
  limitations: string[];
}

export interface CaptureFailureRecordView {
  sequence: number;
  stage: string;
  error_type: string;
}

export interface CaptureHealthView {
  schema_version: "capture-health.v1";
  source: {
    resource: "native-capture-failure-journal";
    journal_exists: boolean;
    journal_bytes: number;
    read_limit_bytes: number;
    declared_capacity_bytes: number | null;
    declared_capacity_state: string;
    declared_capacity_remaining_bytes: number | null;
  };
  observations: {
    recorded_failure_count: number;
    distinct_stage_count: number;
    distinct_error_type_count: number;
    status: "failures-recorded" | "no-failures-recorded";
    capture_success_inferred: false;
    workspace_durability_inferred: false;
    timestamps_available: false;
  };
  aggregates: {
    by_stage: Array<{ stage: string; count: number }>;
    by_error_type: Array<{ error_type: string; count: number }>;
  };
  query: {
    stage: string | null;
    error_type: string | null;
    limit: number;
    offset: number;
  };
  page: {
    limit: number;
    offset: number;
    returned: number;
    matched: number;
    has_more: boolean;
    next_offset: number | null;
  };
  items: CaptureFailureRecordView[];
  limitations: string[];
}

export interface AttestationTrustAnchorView {
  key_id: string;
  public_key_digest: string;
  recorded_status: string;
  superseded_by: string | null;
  current_trust_applicable: boolean;
}

export interface AttestationTrustItem {
  sequence: number;
  attestation_id: string;
  subject_id: string;
  occurred_at: string;
  actor: string;
  evidence_chain_id: string;
  evidence_chain_digest: string;
  transition_id: string;
  transition_digest: string;
  reliability_state: string;
  decision: string;
  verification_status: string;
  reconciliation_state: string;
  previous_digest: string;
  attestation_digest: string;
  key_context: {
    signing_key_id: string | null;
    key_version: null;
    recorded_anchor_status: string | null;
    effective_current_status: string;
    currently_trusted_for_signing: boolean | null;
    superseded_by: string | null;
    public_key_digest: string | null;
    trust_state_version: number | null;
    historical_context: {
      history_authenticated: boolean | null;
      observed_in_authenticated_history: boolean | null;
      ever_observed_active: boolean | null;
      observed_statuses: string[];
      latest_observed_status: string | null;
      first_observed_version: number | null;
      last_observed_version: number | null;
      attestation_time_binding_recorded: false;
      attestation_time_status: null;
    };
  };
  signature_envelope_recorded: boolean;
  signing_trust_context: {
    recorded: boolean;
    authentication: {
      status: string;
      authenticated: boolean | null;
      reason: string;
    };
    trust_state_version: number | null;
    trust_state_digest: string | null;
    signing_key_digest: string | null;
    authority_key_id: string | null;
    authority_key_digest: string | null;
    signing_time_key_status: "active" | null;
    trusted_timestamp_recorded: false;
  };
}

export interface AttestationTrustView {
  schema_version: "attestation-trust-investigation.v3";
  sources: {
    attestation_store: {
      configured: boolean;
      exists: boolean;
      byte_size: number;
      read_limit_bytes: number;
      record_limit: number;
      signed_binding_count: number;
      chain_integrity: string;
    };
    trust_state: {
      configured: boolean;
      derived_from_history: boolean;
      present: boolean;
      version: number | null;
      issued_at: string | null;
      digest: string | null;
      previous_digest: string | null;
      authority_key_id: string | null;
      authentication: {
        status: string;
        authenticated: boolean | null;
        reason: string;
        authority_key_digest: string | null;
      };
      anchor_count: number;
      anchors: AttestationTrustAnchorView[];
    };
    authority_store: { configured: boolean; raw_keys_exposed: false };
    trust_history: {
      configured: boolean;
      exists: boolean;
      byte_size: number;
      read_limit_bytes: number;
      record_limit: number;
      state_count: number;
      chain_integrity: string;
      authentication_status: string;
      lifecycle_authoritative: boolean;
      first_version: number | null;
      latest_version: number | null;
      tip_digest: string | null;
      current_tip_alignment: string;
      states: Array<{
        version: number;
        issued_at: string;
        digest: string;
        previous_digest: string | null;
        authority_key_id: string;
        anchor_count: number;
      }>;
      transitions: Array<{
        from_version: number;
        to_version: number;
        from_digest: string;
        to_digest: string;
        issued_at: string;
        authority_key_id: string;
        authority_changed: boolean;
        activated_key_ids: string[];
        revoked_key_ids: string[];
        superseded_keys: Array<{ key_id: string; superseded_by: string | null }>;
        removed_key_ids: string[];
      }>;
    };
  };
  summary: {
    total_attestations: number;
    signing_key_references: number;
    signed_envelope_records: number;
    verified_signed_bindings: number;
    unsigned_attestations: number;
    active_key_references: number;
    revoked_key_references: number;
    superseded_key_references: number;
    untrusted_key_references: number;
    unauthenticated_key_references: number;
    unconfigured_trust_state_references: number;
    historically_observed_key_references: number;
    historically_active_key_references: number;
  };
  query: {
    decision: string | null;
    reliability_state: string | null;
    key_status: string | null;
    text: string | null;
    limit: number;
    offset: number;
  };
  page: {
    limit: number;
    offset: number;
    returned: number;
    matched: number;
    has_more: boolean;
    next_offset: number | null;
  };
  items: AttestationTrustItem[];
  limitations: string[];
}

export interface IncidentPortfolioItem {
  incident_id: string;
  event_id: string;
  detected_at: string;
  latest_recorded_at: string;
  actor: string;
  category: string;
  status: string;
  observation_count: number;
  evidence_ref_count: number;
  affected_state_count: number;
  uncertainty_count: number;
  key_compromise_recorded: boolean;
  recovery: { recorded: boolean; status: string | null };
  post_recovery: { recorded: boolean; status: string | null };
  forensic_continuity_verified: boolean;
}

export interface IncidentPortfolio {
  schema_version: "incident-investigation.v1";
  scope: {
    resource: "security-incident-evidence";
    sort: "latest_recorded_at_desc_incident_id_asc";
    store_records: number;
    total_incidents: number;
    matched_incidents: number;
  };
  query: {
    status: string | null;
    category: string | null;
    text: string | null;
    limit: number;
    offset: number;
  };
  page: {
    limit: number;
    offset: number;
    returned: number;
    has_more: boolean;
    next_offset: number | null;
  };
  items: IncidentPortfolioItem[];
  limitations: string[];
}

export interface IncidentEvidenceReferenceView {
  kind: string;
  identity: string;
  digest: string;
  source_recorded: boolean;
}

export interface IncidentDetail {
  schema_version: "incident-detail.v1";
  incident: IncidentPortfolioItem;
  lifecycle: Array<{
    sequence: number;
    recorded_at: string;
    status: string;
    record_digest: string;
    incident_digest: string;
  }>;
  evidence_refs: IncidentEvidenceReferenceView[];
  affected_states: Array<{
    state_id: string;
    state_digest: string;
    trust_context: string;
    affected_window_start: string | null;
    affected_window_end: string | null;
  }>;
  security_event_digests: string[];
  uncertainty: string[];
  key_compromise: {
    key_identity: string;
    affected_key_version: string;
    affected_attestation_ids: string[];
    affected_evidence: IncidentEvidenceReferenceView[];
    exposure_start: string;
    exposure_end: string | null;
  } | null;
  recovery: {
    recovery_id: string;
    actor: string;
    source_incident_id: string;
    status: string;
    evidence_ref: IncidentEvidenceReferenceView;
  } | null;
  post_recovery: {
    verification_id: string;
    actor: string;
    status: string;
    performed_at: string;
    evidence_refs: IncidentEvidenceReferenceView[];
  } | null;
  forensic_continuity: {
    required: boolean;
    verified: boolean;
    causality_established: false;
  };
  limitations: string[];
}

export interface ReliabilityProofInvestigationView {
  schema_version: "proof-bundle-investigation.v1";
  bundle: {
    bundle_id: string;
    manifest_id: string;
    engine_version: string;
    created_at: string;
    artifact_count: number;
  };
  proof: {
    format_version: string;
    bundle_type: "reliability-proof";
    descriptor_digest: string;
    subject_id: string;
    attestation_id: string;
    attestation_digest: string;
    evidence_chain_id: string;
    evidence_chain_digest: string;
    transition_id: string;
    transition_digest: string;
    reliability_state: string;
    decision: string;
    verification_report_digest: string;
  };
  verification: {
    verified: true;
    checks: string[];
    failures: string[];
    offline_reverification_succeeded: true;
    source_set_complete: true;
  };
  lineage: {
    required_by_format: boolean;
    present: boolean;
    status: string;
    digest: string | null;
  };
  completeness: {
    required_by_format: boolean;
    present: boolean;
    status: string;
    artifact_id: string | null;
    digest: string | null;
  };
  trust_context: {
    present: boolean;
    portable_cryptographic_consistency_verified: boolean;
    external_authority_trust_established: false;
    signing_key_id: string | null;
    signing_key_digest: string | null;
    trust_state_version: number | null;
    trust_state_digest: string | null;
    authority_key_id: string | null;
    authority_key_digest: string | null;
  };
  cryptographic_profile: Record<string, unknown> | null;
  sources: Array<{
    reference_key: string;
    source_label: string;
    artifact_id: string;
    packaged_digest: string;
    bound_digest: string;
  }>;
  artifacts: Array<{
    artifact_id: string;
    kind: string;
    sha256: string;
    size_bytes: number;
    sensitivity: string;
    derived_from: string[];
  }>;
  portable_dataset_boundary: {
    this_is_reliability_proof: true;
    workspace_portable_dataset_is_distinct: true;
    note: string;
  };
  authorization: {
    human_approval_evaluated: false;
    publication_authorized: false;
    release_authorized: false;
  };
  limitations: string[];
}

export interface ReleaseTrustView {
  schema_version: "release-trust-view.v1";
  bundle_digest: string;
  source: {
    distribution: string;
    version: string;
    source_revision: string;
    source_tree_sha256: string;
    dependency_lock_sha256: string;
  };
  artifacts: Array<{
    name: string;
    sha256: string;
    size_bytes: number;
    media_type: string;
  }>;
  build: {
    builder: string;
    build_type: string;
    build_steps: string[];
    environment: Record<string, string>;
    started_at: string | null;
    finished_at: string | null;
  };
  tests: Array<Record<string, unknown>>;
  external_evidence: {
    sbom: Record<string, unknown> | null;
    vulnerability_scan: Record<string, unknown> | null;
    signature: Record<string, unknown> | null;
    provenance: Record<string, unknown> | null;
  };
  structural_profile: {
    profile_id: string;
    profile_version: string;
    satisfied: boolean;
    failed_requirements: string[];
    missing_evidence: string[];
    caveats: string[];
  };
  content_verification: {
    status: string;
    complete: boolean | null;
    matched: string[];
    missing: string[];
    mismatched: string[];
    limitations: string[];
  };
  signature_authenticity: {
    status: string;
    authenticated: boolean | null;
    reason: string;
  };
  human_decision: {
    actor_ref: string;
    role: string;
    decision: string;
    decided_at: string | null;
    scope: string;
    basis_digest: string | null;
  };
  publication_authorized: boolean;
  release_published: boolean;
  publication_authorization: {
    configured: boolean;
    target_repository: string | null;
    basis_digest: string | null;
    expected_producer_id: string | null;
    publication_authorized: boolean;
    active_approval_receipt_ids: string[];
    items: Array<{
      status: "active" | "revoked" | "superseded";
      approval_receipt_id: string;
      actor_identity_ref: string;
      role: string;
      captured_at: string;
      superseded_by_receipt_id: string | null;
      revocation_receipt_id: string | null;
    }>;
  };
  registry_publication: {
    configured: boolean;
    release_published: boolean;
    registry_reconciled: boolean;
    receipt_digest: string | null;
    target_repository: string | null;
    basis_digest: string | null;
    permit_digest: string | null;
    observed_at: string | null;
    public_bytes_verified: boolean;
    artifacts: Array<{
      name: string;
      sha256: string;
      size_bytes: number;
      url: string;
      package_type: string;
      upload_time: string | null;
      yanked: boolean;
      yanked_reason: string | null;
      public_bytes_verified: boolean;
    }>;
    lifecycle: {
      configured: boolean;
      current_status: "available" | "yanked" | "partially_available" | "unavailable" | null;
      current_observed_at: string | null;
      observation_count: number;
      registry_entry_present: boolean | null;
      default_install_eligible: boolean | null;
      public_bytes_verified: boolean | null;
      missing_artifacts: string[];
      observations: Array<{
        observation_digest: string;
        publication_receipt_digest: string;
        predecessor_digest: string;
        basis_digest: string;
        permit_digest: string;
        target_repository: string;
        distribution: string;
        version: string;
        registry_api_url: string;
        observed_at: string;
        status: "available" | "yanked" | "partially_available" | "unavailable";
        registry_entry_present: boolean;
        default_install_eligible: boolean;
        public_bytes_verified: boolean;
        missing_artifacts: string[];
        unavailable_reason: string | null;
        artifacts: Array<{
          name: string;
          sha256: string;
          size_bytes: number;
          url: string;
          package_type: string;
          upload_time: string | null;
          yanked: boolean;
          yanked_reason: string | null;
          public_bytes_verified: boolean;
        }>;
        limitations: string[];
      }>;
    };
  };
  limitations: string[];
}

export interface ValidationStudyMetric {
  baseline: string;
  case_count: number;
  injected_fault_count: number;
  detected_fault_count: number;
  valid_case_count: number;
  false_positive_count: number;
  target_property_count: number;
  checkable_property_count: number;
  verification_coverage: number;
  fault_detection_rate: number;
  false_positive_rate: number;
  verification_coverage_denominator: number;
  fault_detection_denominator: number;
  false_positive_denominator: number;
}

export interface ValidationStudyView {
  schema_version: "validation-study-view.v1";
  study_id: string;
  study_digest: string;
  study_kind: "deterministic-fixture-study";
  baselines: Array<Record<string, unknown>>;
  workloads: Array<Record<string, unknown>>;
  faults: Array<Record<string, unknown>>;
  metrics: ValidationStudyMetric[];
  case_count: number;
  cases: Array<Record<string, unknown>>;
  limitations: string[];
}

export interface WorkspaceRecordView {
  record_id: string;
  receipt_id: string;
  artifact_digest: string;
  artifact_size: number;
  producer_id: string;
  producer_type: string;
  producer_version: string | null;
  source_event_id: string | null;
  run_id: string | null;
  captured_at: string;
  sensitivity: string;
  verification_status: string | null;
  reliability_state: string | null;
  retention: {
    policy_id: string;
    sensitivity: string;
    retain_until: string | null;
    legal_hold: boolean;
  } | null;
}

export interface WorkspaceOperationsView {
  schema_version: "workspace-operations.v1";
  workspace: {
    workspace_id: string;
    schema_version: string;
    public_api_contract_version: string;
    mode: "read-only";
    backend: "sqlite";
  };
  health: {
    status: string;
    healthy: boolean;
    has_errors: boolean;
    checked_records: number;
    checked_receipts: number;
    checked_artifacts: number;
    checked_exports: number;
    issues: Array<{
      code: string;
      severity: string;
      message: string;
      object_id: string | null;
    }>;
    orphan_counts: { artifacts: number; receipts: number; exports: number };
  };
  storage: {
    total_bytes: number;
    artifact_bytes: number;
    receipt_bytes: number;
    database_bytes: number;
    export_bytes: number;
    manifest_bytes: number;
    lock_bytes: number;
  };
  migration: { current_schema_version: string; status: string };
  records: {
    items: WorkspaceRecordView[];
    total_count: number;
    limit: number;
    offset: number;
    has_more: boolean;
    next_offset: number | null;
  };
  lifecycle: {
    retention_rows_in_snapshot: number;
    retention_rows_in_page: number;
    legal_holds_in_page: number;
    deletion_tombstones: number;
  };
  exports: {
    count: number;
    items: Array<{
      export_id: string;
      format: string;
      created_at: string;
      disclosure_max_sensitivity: string;
      source_schema_version: string;
      output_digest: string | null;
      row_count: number | null;
    }>;
    supported_formats: string[];
  };
  backup: {
    history_status: string;
    restore_eligibility: string;
    note: string;
  };
  operational_audit: { status: string; note: string };
  limitations: string[];
}

export interface DecisionLineageInputView {
  digest: string;
  semantic_roles: string[];
  classification: "lineage-bound" | "verification-context";
  lineage_roles: string[];
  reachable_to_run: true | null;
}

export interface DecisionLineageView {
  schema_version: "decision-lineage-investigation.v1";
  chain: {
    chain_id: string;
    digest: string;
    verification_status: string;
    reliability_state: string;
    reconciliation_state: string;
    decision: string;
    evidence_count: number;
    rationale_count: number;
    rationale_exposed: false;
  };
  decision_basis:
    | { present: false }
    | {
        present: true;
        basis_type: string;
        basis_id: string;
        version: string;
        digest: string;
        decision: string;
        reliability_state: string;
        input_count: number;
        policy_id: string | null;
        policy_version: string | null;
        policy_digest: string | null;
        rationale_count: number;
        rationale_exposed: false;
      };
  decision_inputs: DecisionLineageInputView[];
  comparison:
    | { present: false }
    | {
        present: true;
        comparison_id: string;
        digest: string;
        significance: string;
        discrepancies: string[];
        before_inputs: Array<{ role: string; kind: string; identity: string; digest: string }>;
        after_inputs: Array<{ role: string; kind: string; identity: string; digest: string }>;
      };
  reconciliation:
    | { present: false }
    | {
        present: true;
        binding_digest: string;
        comparison_id: string;
        comparison_digest: string;
        reconciliation_id: string;
        reconciliation_digest: string;
        reconciliation_status: string;
        resolved_discrepancies: string[];
        resolution: string;
      };
  recovery:
    | { present: false }
    | {
        present: true;
        digest: string;
        recovery_id: string;
        recovery_digest: string;
        recovery_status: string;
        source_reconciliation_id: string;
        reconciliation_id: string;
        reconciliation_digest: string;
        reconciliation_status: string;
        outcome: "recovered";
      };
  lineage: {
    verified: true;
    provenance_graph_digest: string;
    closure_digest: string;
    run_role: "run";
    reachable_roles: string[];
    bindings: Array<{
      role: string;
      node_id: string;
      identity: string;
      digest: string;
      reachable_to_run: true;
    }>;
  };
  verification: {
    evidence_chain_verified: true;
    decision_basis_verified: boolean;
    comparison_verified: boolean;
    reconciliation_binding_verified: boolean;
    recovery_outcome_verified: boolean;
    lineage_closure_verified: true;
  };
  authorization: {
    business_authorization_evaluated: false;
    human_approval_evaluated: false;
    publication_authorized: false;
  };
  limitations: string[];
}

export interface SecurityAuditItemView {
  sequence: number;
  occurred_at: string;
  event: "authentication_failed" | "authorization_denied" | "request_rejected" | "request_admitted";
  operation: "verify:evidence" | "verify:proof" | "review:read" | "review:write" | "approval:read" | "approval:write" | null;
  method: string;
  route_kind: string;
  path_digest: string;
  path_exposed: false;
  reason: string;
  reason_digest: string;
  previous_digest: string | null;
  digest: string;
}

export interface SecurityAssuranceView {
  schema_version: "security-assurance-investigation.v2";
  source: {
    resource: "deployment-security-audit-journal";
    configured: boolean;
    exists: boolean;
    byte_size: number;
    read_limit_bytes: number;
    record_limit: number;
    chain_integrity: "verified" | "missing";
    source_path_exposed: false;
  };
  observations: {
    recorded_event_count: number;
    authentication_failed_count: number;
    authorization_denied_count: number;
    request_rejected_count: number;
    request_admitted_count: number;
    distinct_operation_count: number;
    distinct_route_kind_count: number;
    deployment_secure_inferred: false;
    live_configuration_observed: false;
    runtime_configuration_snapshot_observed: boolean;
  };
  runtime_containment:
    | {
        snapshot_observed: false;
        configuration_digest: null;
        recorded_at_utc: null;
        verification_service: null;
        limits: null;
        enforcement: Record<string, "not-observed">;
        host_controls_evaluated: false;
      }
    | {
        snapshot_observed: true;
        configuration_digest: string;
        recorded_at_utc: string;
        verification_service: {
          max_request_bytes: number;
          read_only: true;
          require_https: boolean;
          allow_insecure_http: boolean;
          artifact_root_count: number;
          artifact_roots_exposed: false;
        };
        limits: {
          max_input_bytes: number;
          max_archive_members: number;
          max_archive_uncompressed_bytes: number;
          max_archive_compression_ratio: number;
          max_json_depth: number;
          max_json_nodes: number;
          max_string_bytes: number;
          max_graph_nodes: number;
          max_verification_seconds: number;
          max_concurrency: number;
          max_temporary_bytes: number;
        };
        enforcement: {
          request_body_bytes: "verification-service-enforced";
          json_input_bytes: "verification-service-enforced";
          json_depth: "verification-service-enforced";
          json_nodes: "verification-service-enforced";
          json_string_bytes: "verification-service-enforced";
          archive_members: "domain-control-not-wired-to-service-runtime-limits";
          archive_uncompressed_bytes: "domain-control-not-wired-to-service-runtime-limits";
          archive_compression_ratio: "domain-control-not-wired-to-service-runtime-limits";
          graph_nodes: "configured-limit-not-enforced-by-verification-service";
          verification_seconds: "cooperative-primitive-not-wired-to-verification-service";
          concurrency: "configured-limit-not-enforced-by-verification-service";
          temporary_bytes: "configured-limit-not-enforced-by-verification-service";
        };
        host_controls_evaluated: false;
      };
  deployment_boundary: {
    configuration_snapshot_available: false;
    protected_operations: string[];
    default_public_paths: string[];
    default_require_https: true;
    authentication_provider: "host-provided";
    authorization_provider: "host-provided";
    request_admission_provider: "optional-host-provided";
    security_event_sink: "optional-host-provided";
    host_responsibilities: string[];
  };
  aggregates: {
    by_event: Array<{ event: string; count: number }>;
    by_operation: Array<{ operation: string; count: number }>;
    by_reason: Array<{ reason: string; count: number }>;
    by_method: Array<{ method: string; count: number }>;
    by_route_kind: Array<{ route_kind: string; count: number }>;
  };
  query: {
    event: string | null;
    operation: string | null;
    reason: string | null;
    method: string | null;
    limit: number;
    offset: number;
  };
  page: {
    limit: number;
    offset: number;
    returned: number;
    matched: number;
    has_more: boolean;
    next_offset: number | null;
  };
  items: SecurityAuditItemView[];
  limitations: string[];
}


export interface AssuranceDecisionView {
  schema_version: "assurance-decision-investigation.v1";
  decision: {
    decision: string;
    digest: string;
    subject_id_digest: string;
    policy_id: string;
    policy_version: string;
    policy_rule: string;
    generated_at: string;
    source_reliability_state: string;
    source_verification_status: string;
    evidence_reference_digests: string[];
    verification_results: string[];
    residual_risk: string[];
    system_state_unchanged: true;
    semantic_replay_verified: true;
    rationale_exposed: false;
  };
  exception:
    | { present: false }
    | {
        present: true;
        exception_id_digest: string;
        binding: "exact-decision-digest" | "legacy-unbound";
        decision_digest: string | null;
        status: "active" | "expired";
        created_at: string;
        expires_at: string;
        authorized_by_digest: string;
        compensating_control: string;
        reverification_required: string;
        evidence_reference_digests: string[];
        system_state_preserved: true;
      };
  authorization: {
    factual_correctness_evaluated: false;
    publication_authorized: false;
    compliance_certified: false;
    host_authorization_inferred: false;
  };
  limitations: string[];
}

export interface AccessAuthorizationView {
  schema_version: "access-authorization-investigation.v1";
  source: {
    resource: "explicit-authorization-context-artifact";
    configured: true;
    source_path_exposed: false;
    canonical_iam_store: false;
  };
  principal: {
    principal_id_digest: string;
    principal_id_exposed: false;
    status: "ACTIVE" | "REVOKED";
    roles: string[];
    expires_at: string | null;
    active_at_request: boolean;
    resource_scope_domain_count: number;
    resource_scope_resource_count: number;
    resource_scopes: Array<{
      resource_domain_digest: string;
      resource_id_digests: string[];
      resource_count: number;
    }>;
  };
  request: {
    operation: string;
    resource_domain_digest: string;
    resource_id_digest: string;
    resource_identity_exposed: false;
    resource_state: string;
    requested_at: string;
  };
  policy: {
    deny_by_default: true;
    grant_count: number;
    grants: Array<{
      role: string;
      operation: string;
      allowed_states: string[];
    }>;
  };
  evaluation: {
    principal_active: boolean;
    resource_scope_match: boolean;
    matching_grant_count: number;
    recorded_decision_present: boolean;
    recorded_decision_verified: boolean;
    policy_replay_verified: true;
  };
  decision: {
    allowed: boolean;
    reason: string;
    matched_role: string | null;
    operation: string;
    resource_state: string;
    principal_id_digest: string;
    resource_domain_digest: string;
    resource_id_digest: string;
  };
  authorization_boundary: {
    principal_authentication_evaluated: false;
    identity_provider: "external-host";
    session_validity_evaluated: false;
    mfa_evaluated: false;
    tls_evaluated: false;
    tenant_isolation_evaluated: false;
    iam_provider: false;
    business_authorization_inferred: false;
  };
  limitations: string[];
}

export interface DataLifecycleDecisionView {
  sensitivity: string;
  policy_id: string;
  retain_until: string | null;
  expired: boolean;
  storage_allowed: boolean;
  telemetry_allowed: boolean;
  disclosure_allowed: boolean;
  deletion_allowed: boolean;
  reasons: string[];
  object_id_digest: string;
  object_id_exposed: false;
}

export interface DataGovernanceView {
  schema_version: "data-governance-investigation.v2";
  source: {
    resource: "explicit-lifecycle-context-plus-workspace-metadata";
    configured: true;
    source_path_exposed: false;
    workspace_authority: true;
    second_lifecycle_store_created: false;
    privacy_governance_snapshot_configured: boolean;
  };
  privacy_governance_runtime:
    | {
        observed: false;
        defaults_inferred: false;
        source_path_exposed: false;
      }
    | {
        observed: true;
        defaults_inferred: false;
        source_path_exposed: false;
        snapshot_digest: string;
        privacy_policy: {
          policy_id: string;
          redact_key_count: number;
          regex_rule_count: number;
          patterns_exposed: false;
          metadata_redaction_before_receipt_identity: true;
        };
        evidence_policy: {
          policy_id: string;
          storage_max_sensitivity: string;
          telemetry_max_sensitivity: string;
          require_digest_for: string[];
          storage_governance_before_artifact_write: true;
          workspace_sensitivity_indexing: true;
          telemetry_manifest_projection_supported: true;
          telemetry_runtime_binding_observed: false;
        };
        opaque_content_secret_scanning: false;
      };
  object: {
    kind: "workspace-record" | "workspace-export";
    object_id_digest: string;
    object_id_exposed: false;
    sensitivity: string;
    created_at: string;
    original_digest: string | null;
  };
  policy: {
    policy_id: string;
    purpose: string;
    max_retention_days: number | null;
    storage_max_sensitivity: string;
    telemetry_max_sensitivity: string;
    disclosure_max_sensitivity: string;
    encryption_at_rest_required: boolean;
    tls_required: boolean;
  };
  durable_retention: {
    present: true;
    policy_id: string;
    sensitivity: string;
    retain_until: string | null;
    legal_hold: boolean;
    context_cross_check_verified: true;
  };
  current_decision: DataLifecycleDecisionView & {
    policy_replay_verified: true;
    deletion_already_recorded: boolean;
  };
  recorded_decision:
    | { present: false }
    | {
        present: true;
        evaluated_at: string;
        decision: DataLifecycleDecisionView;
        policy_replay_verified: true;
      };
  deletion:
    | {
        present: false;
        payload_erasure_outside_statewake_evaluated: false;
      }
    | {
        present: true;
        digest: string;
        sensitivity: string;
        deleted_at: string;
        policy_id: string;
        reason: string;
        tombstone_cross_check_verified: true;
        payload_content_retained_in_tombstone: false;
        payload_erasure_outside_statewake_evaluated: false;
      };
  confidentiality_requirements: {
    encryption_at_rest_required: boolean;
    tls_required: boolean;
    host_requirement_satisfaction_evaluated: false;
  };
  authorization: {
    deletion_executed_by_this_view: false;
    disclosure_executed_by_this_view: false;
    business_authorization_inferred: false;
    compliance_certified: false;
  };
  limitations: string[];
}
