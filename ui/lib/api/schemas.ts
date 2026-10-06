import type {
  AttestationTrustAnchorView,
  AttestationTrustItem,
  AccessAuthorizationView,
  AssuranceDecisionView,
  AttestationTrustView,
  CaptureHealthView,
  ClaimCatalog,
  ClaimCatalogItem,
  ClaimComparison,
  ClaimComparisonSide,
  ClaimDetail,
  ClaimHistory,
  ClaimHistoryItem,
  ClaimReason,
  ClaimSummary,
  DataGovernanceView,
  DataLifecycleDecisionView,
  DecisionLineageView,
  EvidenceTrace,
  EvidenceTraceEdge,
  EvidenceTraceNode,
  EvidenceTraceUnresolved,
  HumanApprovalEvidence,
  HumanApprovalLifecycleResult,
  HumanApprovalRevocationEvidence,
  HumanApprovalThread,
  HumanApprovalResult,
  IncidentDetail,
  IncidentEvidenceReferenceView,
  IncidentPortfolio,
  IncidentPortfolioItem,
  OverviewProjection,
  OverviewReportItem,
  ReleaseTrustView,
  ReliabilityProofInvestigationView,
  SecurityAssuranceView,
  SecurityAuditItemView,
  StringDelta,
  ValidationStudyMetric,
  ValidationStudyView,
  WorkspaceOperationsView,
  WorkspaceRecordView,
} from "./dto";

function object(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${field} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(source: Record<string, unknown>, expected: readonly string[], field: string): void {
  const actual = Object.keys(source).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    throw new Error(`${field} fields are missing or unsupported`);
  }
}

function string(value: unknown, field: string): string {
  if (typeof value !== "string") throw new Error(`${field} must be a string`);
  return value;
}

function boolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${field} must be a boolean`);
  return value;
}

function number(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${field} must be a finite number`);
  }
  return value;
}

function strings(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array`);
  return value.map((item, index) => string(item, `${field}[${index}]`));
}

function nullableString(value: unknown, field: string): string | null {
  if (value === null) return null;
  return string(value, field);
}

function nullableNumber(value: unknown, field: string): number | null {
  if (value === null) return null;
  return number(value, field);
}

function parseReasons(value: unknown): ClaimReason[] {
  if (!Array.isArray(value)) throw new Error("summary.reasons must be an array");
  return value.map((item, index) => {
    const source = object(item, `summary.reasons[${index}]`);
    return {
      kind: string(source.kind, `summary.reasons[${index}].kind`),
      source_ref: string(source.source_ref, `summary.reasons[${index}].source_ref`),
      text: string(source.text, `summary.reasons[${index}].text`),
    };
  });
}

function parseSummary(value: unknown): ClaimSummary {
  const source = object(value, "summary");
  if (source.schema_version !== "claim-summary.v1") {
    throw new Error("unsupported claim summary schema");
  }
  const candidate = object(source.candidate, "summary.candidate");
  const profile = object(source.profile, "summary.profile");
  const verification = object(source.verification, "summary.verification");
  const evidence = object(source.evidence, "summary.evidence");
  const human = object(source.human_decision, "summary.human_decision");
  if (source.as_of !== null) {
    throw new Error("summary.as_of must be null for the current source-bound projection");
  }
  return {
    schema_version: "claim-summary.v1",
    candidate: {
      id: string(candidate.id, "summary.candidate.id"),
      digest: string(candidate.digest, "summary.candidate.digest"),
    },
    profile: {
      id: string(profile.id, "summary.profile.id"),
      version: string(profile.version, "summary.profile.version"),
    },
    claim: string(source.claim, "summary.claim"),
    decision: string(source.decision, "summary.decision"),
    verification: {
      verified: boolean(verification.verified, "summary.verification.verified"),
      passed: number(verification.passed, "summary.verification.passed"),
      failed: number(verification.failed, "summary.verification.failed"),
      unrun: number(verification.unrun, "summary.verification.unrun"),
      unknown: number(verification.unknown, "summary.verification.unknown"),
    },
    evidence: {
      included: number(evidence.included, "summary.evidence.included"),
      omitted: number(evidence.omitted, "summary.evidence.omitted"),
      missing: number(evidence.missing, "summary.evidence.missing"),
    },
    reasons: parseReasons(source.reasons),
    human_decision: {
      required: boolean(human.required, "summary.human_decision.required"),
      approval_status: string(
        human.approval_status,
        "summary.human_decision.approval_status",
      ),
      required_actions: strings(
        human.required_actions,
        "summary.human_decision.required_actions",
      ),
    },
    caveats: strings(source.caveats, "summary.caveats"),
    residual_risks: strings(source.residual_risks, "summary.residual_risks"),
    report_digest: string(source.report_digest, "summary.report_digest"),
    generated_at: string(source.generated_at, "summary.generated_at"),
    as_of: null,
  };
}


function parseClaimCatalogItem(value: unknown, index: number): ClaimCatalogItem {
  const source = object(value, `claim catalog.items[${index}]`);
  const candidate = object(source.candidate, `claim catalog.items[${index}].candidate`);
  const profile = object(source.profile, `claim catalog.items[${index}].profile`);
  const evidence = object(source.evidence, `claim catalog.items[${index}].evidence`);
  const checks = object(source.checks, `claim catalog.items[${index}].checks`);
  return {
    record_id: string(source.record_id, `claim catalog.items[${index}].record_id`),
    captured_at: string(source.captured_at, `claim catalog.items[${index}].captured_at`),
    run_id: nullableString(source.run_id, `claim catalog.items[${index}].run_id`),
    claim: string(source.claim, `claim catalog.items[${index}].claim`),
    report_type: string(source.report_type, `claim catalog.items[${index}].report_type`),
    decision: string(source.decision, `claim catalog.items[${index}].decision`),
    verified: boolean(source.verified, `claim catalog.items[${index}].verified`),
    approval_status: string(source.approval_status, `claim catalog.items[${index}].approval_status`),
    candidate: {
      id: string(candidate.id, `claim catalog.items[${index}].candidate.id`),
      digest: string(candidate.digest, `claim catalog.items[${index}].candidate.digest`),
    },
    profile: {
      id: string(profile.id, `claim catalog.items[${index}].profile.id`),
      version: string(profile.version, `claim catalog.items[${index}].profile.version`),
    },
    evidence: {
      included: number(evidence.included, `claim catalog.items[${index}].evidence.included`),
      omitted: number(evidence.omitted, `claim catalog.items[${index}].evidence.omitted`),
      missing: number(evidence.missing, `claim catalog.items[${index}].evidence.missing`),
    },
    checks: {
      failed: number(checks.failed, `claim catalog.items[${index}].checks.failed`),
      unrun: number(checks.unrun, `claim catalog.items[${index}].checks.unrun`),
      unknown: number(checks.unknown, `claim catalog.items[${index}].checks.unknown`),
    },
    human_decision_required: boolean(source.human_decision_required, `claim catalog.items[${index}].human_decision_required`),
    report_digest: string(source.report_digest, `claim catalog.items[${index}].report_digest`),
    generated_at: string(source.generated_at, `claim catalog.items[${index}].generated_at`),
  };
}

export function parseClaimCatalog(value: unknown): ClaimCatalog {
  const source = object(value, "claim catalog");
  if (source.schema_version !== "claim-catalog.v1") {
    throw new Error("unsupported claim catalog schema");
  }
  const scope = object(source.scope, "claim catalog.scope");
  const query = object(source.query, "claim catalog.query");
  const page = object(source.page, "claim catalog.page");
  if (scope.resource !== "verification-report-records") {
    throw new Error("claim catalog scope must be verification-report-records");
  }
  if (scope.sort !== "captured_at_desc_record_id_asc") {
    throw new Error("claim catalog sort contract is unsupported");
  }
  if (!Array.isArray(source.items)) throw new Error("claim catalog.items must be an array");
  const items = source.items.map(parseClaimCatalogItem);
  const returned = number(page.returned, "claim catalog.page.returned");
  const scanned = number(scope.scanned_receipts, "claim catalog.scope.scanned_receipts");
  const total = number(scope.total_reports, "claim catalog.scope.total_reports");
  const matched = number(scope.matched_reports, "claim catalog.scope.matched_reports");
  const limit = number(page.limit, "claim catalog.page.limit");
  const offset = number(page.offset, "claim catalog.page.offset");
  const hasMore = boolean(page.has_more, "claim catalog.page.has_more");
  const nextOffset = nullableNumber(page.next_offset, "claim catalog.page.next_offset");
  const counts = [scanned, total, matched, returned, limit, offset];
  if (counts.some((value) => !Number.isInteger(value) || value < 0)) {
    throw new Error("claim catalog counts must be non-negative integers");
  }
  if (returned !== items.length) throw new Error("claim catalog returned count must match items length");
  if (total > scanned || matched > total || matched < returned || limit < 1 || limit > 200) {
    throw new Error("claim catalog pagination is inconsistent");
  }
  if (number(query.limit, "claim catalog.query.limit") !== limit || number(query.offset, "claim catalog.query.offset") !== offset) {
    throw new Error("claim catalog query/page pagination must match");
  }
  if (returned > limit) throw new Error("claim catalog returned count exceeds page limit");
  if (hasMore !== (offset + returned < matched)) {
    throw new Error("claim catalog has_more is inconsistent");
  }
  if (hasMore && nextOffset !== offset + returned) {
    throw new Error("claim catalog next_offset is inconsistent");
  }
  if (!hasMore && nextOffset !== null) {
    throw new Error("claim catalog next_offset must be null on the final page");
  }
  return {
    schema_version: "claim-catalog.v1",
    scope: {
      resource: "verification-report-records",
      deduplication_key: string(scope.deduplication_key, "claim catalog.scope.deduplication_key"),
      sort: "captured_at_desc_record_id_asc",
      scanned_receipts: scanned,
      total_reports: total,
      matched_reports: matched,
    },
    query: {
      decision: nullableString(query.decision, "claim catalog.query.decision"),
      verified: query.verified === null ? null : boolean(query.verified, "claim catalog.query.verified"),
      approval_status: nullableString(query.approval_status, "claim catalog.query.approval_status"),
      profile_id: nullableString(query.profile_id, "claim catalog.query.profile_id"),
      candidate_id: nullableString(query.candidate_id, "claim catalog.query.candidate_id"),
      text: nullableString(query.text, "claim catalog.query.text"),
      limit,
      offset,
    },
    page: { limit, offset, returned, has_more: hasMore, next_offset: nextOffset },
    items,
    limitations: strings(source.limitations, "claim catalog.limitations"),
  };
}


function parseAttestationTrustAnchor(
  value: unknown,
  field: string,
): AttestationTrustAnchorView {
  const source = object(value, field);
  return {
    key_id: string(source.key_id, `${field}.key_id`),
    public_key_digest: string(source.public_key_digest, `${field}.public_key_digest`),
    recorded_status: string(source.recorded_status, `${field}.recorded_status`),
    superseded_by: nullableString(source.superseded_by, `${field}.superseded_by`),
    current_trust_applicable: boolean(
      source.current_trust_applicable,
      `${field}.current_trust_applicable`,
    ),
  };
}

function parseAttestationTrustItem(value: unknown, index: number): AttestationTrustItem {
  const field = `attestation trust.items[${index}]`;
  const source = object(value, field);
  exactKeys(source, ["sequence", "attestation_id", "subject_id", "occurred_at", "actor", "evidence_chain_id", "evidence_chain_digest", "transition_id", "transition_digest", "reliability_state", "decision", "verification_status", "reconciliation_state", "previous_digest", "attestation_digest", "key_context", "signature_envelope_recorded", "signing_trust_context"], field);
  const key = object(source.key_context, `${field}.key_context`);
  exactKeys(key, ["signing_key_id", "key_version", "recorded_anchor_status", "effective_current_status", "currently_trusted_for_signing", "superseded_by", "public_key_digest", "trust_state_version", "historical_context"], `${field}.key_context`);
  const historical = object(key.historical_context, `${field}.key_context.historical_context`);
  exactKeys(historical, ["history_authenticated", "observed_in_authenticated_history", "ever_observed_active", "observed_statuses", "latest_observed_status", "first_observed_version", "last_observed_version", "attestation_time_binding_recorded", "attestation_time_status"], `${field}.key_context.historical_context`);
  const envelopeRecorded = boolean(source.signature_envelope_recorded, `${field}.signature_envelope_recorded`);
  const signingContext = object(source.signing_trust_context, `${field}.signing_trust_context`);
  exactKeys(signingContext, ["recorded", "authentication", "trust_state_version", "trust_state_digest", "signing_key_digest", "authority_key_id", "authority_key_digest", "signing_time_key_status", "trusted_timestamp_recorded"], `${field}.signing_trust_context`);
  const signingAuthentication = object(signingContext.authentication, `${field}.signing_trust_context.authentication`);
  exactKeys(signingAuthentication, ["status", "authenticated", "reason"], `${field}.signing_trust_context.authentication`);
  const signingRecorded = boolean(signingContext.recorded, `${field}.signing_trust_context.recorded`);
  if (envelopeRecorded !== signingRecorded) {
    throw new Error(`${field} signed-envelope and signing-context recording state must agree`);
  }
  const signingAuthStatus = string(signingAuthentication.status, `${field}.signing_trust_context.authentication.status`);
  if (!new Set(["verified", "dependency-unavailable", "authority-not-configured", "trust-state-unavailable", "not-recorded", "not-evaluated"]).has(signingAuthStatus)) {
    throw new Error(`${field} signed binding authentication status is unsupported`);
  }
  const signingAuthenticated = signingAuthentication.authenticated;
  if (signingAuthenticated !== null && typeof signingAuthenticated !== "boolean") {
    throw new Error(`${field} signed binding authentication must be boolean or null`);
  }
  if ((signingAuthStatus === "verified") !== (signingAuthenticated === true)) {
    throw new Error(`${field} verified signed binding authentication is inconsistent`);
  }
  if (signingAuthStatus !== "verified" && signingAuthenticated !== null) {
    throw new Error(`${field} unverified signed binding authentication must be null`);
  }
  if (!signingRecorded && signingAuthStatus !== "not-recorded") {
    throw new Error(`${field} absent signing context must use not-recorded status`);
  }
  if (signingRecorded && signingAuthStatus === "not-recorded") {
    throw new Error(`${field} recorded signing context cannot use not-recorded status`);
  }
  if (signingContext.trusted_timestamp_recorded !== false) {
    throw new Error(`${field} must not claim a trusted signing timestamp`);
  }
  const boundVersion = nullableNumber(signingContext.trust_state_version, `${field}.signing_trust_context.trust_state_version`);
  const boundTrustDigest = nullableString(signingContext.trust_state_digest, `${field}.signing_trust_context.trust_state_digest`);
  const boundSigningKeyDigest = nullableString(signingContext.signing_key_digest, `${field}.signing_trust_context.signing_key_digest`);
  const boundAuthorityId = nullableString(signingContext.authority_key_id, `${field}.signing_trust_context.authority_key_id`);
  const boundAuthorityDigest = nullableString(signingContext.authority_key_digest, `${field}.signing_trust_context.authority_key_digest`);
  const boundKeyStatus = nullableString(signingContext.signing_time_key_status, `${field}.signing_trust_context.signing_time_key_status`);
  if (boundVersion !== null && (!Number.isInteger(boundVersion) || boundVersion < 1)) {
    throw new Error(`${field} bound trust-state version must be a positive integer or null`);
  }
  const boundValues = [boundVersion, boundTrustDigest, boundSigningKeyDigest, boundAuthorityId, boundAuthorityDigest];
  if (!signingRecorded && boundValues.some((value) => value !== null)) {
    throw new Error(`${field} absent signing context cannot expose trust binding fields`);
  }
  if (signingRecorded && boundValues.some((value) => value === null)) {
    throw new Error(`${field} recorded signing context requires complete trust binding fields`);
  }
  for (const digest of [boundTrustDigest, boundSigningKeyDigest, boundAuthorityDigest]) {
    if (digest !== null && !/^[0-9a-f]{64}$/.test(digest)) {
      throw new Error(`${field} signing trust-context digests must be lowercase SHA-256 hex`);
    }
  }
  if (signingAuthenticated === true && boundKeyStatus !== "active") {
    throw new Error(`${field} verified signing context must bind an active signing key`);
  }
  if (signingAuthenticated !== true && boundKeyStatus !== null) {
    throw new Error(`${field} unverified signing context cannot claim signing-time key status`);
  }
  if (key.key_version !== null) {
    throw new Error(`${field}.key_context.key_version must be null`);
  }
  const trusted = key.currently_trusted_for_signing;
  if (trusted !== null && typeof trusted !== "boolean") {
    throw new Error(`${field}.key_context.currently_trusted_for_signing must be boolean or null`);
  }
  const version = nullableNumber(key.trust_state_version, `${field}.key_context.trust_state_version`);
  if (version !== null && (!Number.isInteger(version) || version < 1)) {
    throw new Error(`${field}.key_context.trust_state_version must be a positive integer or null`);
  }
  const historyAuthenticated = historical.history_authenticated;
  const observed = historical.observed_in_authenticated_history;
  const everActive = historical.ever_observed_active;
  for (const [value, name] of [
    [historyAuthenticated, "history_authenticated"],
    [observed, "observed_in_authenticated_history"],
    [everActive, "ever_observed_active"],
  ] as const) {
    if (value !== null && typeof value !== "boolean") {
      throw new Error(`${field}.key_context.historical_context.${name} must be boolean or null`);
    }
  }
  if (historyAuthenticated !== true && (observed !== null || everActive !== null)) {
    throw new Error(`${field}.key_context historical lifecycle cannot be inferred without authenticated history`);
  }
  if (historical.attestation_time_binding_recorded !== false || historical.attestation_time_status !== null) {
    throw new Error(`${field}.key_context attestation-time trust must remain unavailable without an explicit binding`);
  }
  const firstObserved = nullableNumber(historical.first_observed_version, `${field}.key_context.historical_context.first_observed_version`);
  const lastObserved = nullableNumber(historical.last_observed_version, `${field}.key_context.historical_context.last_observed_version`);
  for (const value of [firstObserved, lastObserved]) {
    if (value !== null && (!Number.isInteger(value) || value < 1)) {
      throw new Error(`${field}.key_context historical versions must be positive integers or null`);
    }
  }
  if ((firstObserved === null) !== (lastObserved === null)) {
    throw new Error(`${field}.key_context historical version bounds are inconsistent`);
  }
  if (firstObserved !== null && lastObserved !== null && firstObserved > lastObserved) {
    throw new Error(`${field}.key_context historical version bounds are reversed`);
  }
  return {
    sequence: number(source.sequence, `${field}.sequence`),
    attestation_id: string(source.attestation_id, `${field}.attestation_id`),
    subject_id: string(source.subject_id, `${field}.subject_id`),
    occurred_at: string(source.occurred_at, `${field}.occurred_at`),
    actor: string(source.actor, `${field}.actor`),
    evidence_chain_id: string(source.evidence_chain_id, `${field}.evidence_chain_id`),
    evidence_chain_digest: string(source.evidence_chain_digest, `${field}.evidence_chain_digest`),
    transition_id: string(source.transition_id, `${field}.transition_id`),
    transition_digest: string(source.transition_digest, `${field}.transition_digest`),
    reliability_state: string(source.reliability_state, `${field}.reliability_state`),
    decision: string(source.decision, `${field}.decision`),
    verification_status: string(source.verification_status, `${field}.verification_status`),
    reconciliation_state: string(source.reconciliation_state, `${field}.reconciliation_state`),
    previous_digest: string(source.previous_digest, `${field}.previous_digest`),
    attestation_digest: string(source.attestation_digest, `${field}.attestation_digest`),
    key_context: {
      signing_key_id: nullableString(key.signing_key_id, `${field}.key_context.signing_key_id`),
      key_version: null,
      recorded_anchor_status: nullableString(key.recorded_anchor_status, `${field}.key_context.recorded_anchor_status`),
      effective_current_status: string(key.effective_current_status, `${field}.key_context.effective_current_status`),
      currently_trusted_for_signing: trusted as boolean | null,
      superseded_by: nullableString(key.superseded_by, `${field}.key_context.superseded_by`),
      public_key_digest: nullableString(key.public_key_digest, `${field}.key_context.public_key_digest`),
      trust_state_version: version,
      historical_context: {
        history_authenticated: historyAuthenticated as boolean | null,
        observed_in_authenticated_history: observed as boolean | null,
        ever_observed_active: everActive as boolean | null,
        observed_statuses: strings(historical.observed_statuses, `${field}.key_context.historical_context.observed_statuses`),
        latest_observed_status: nullableString(historical.latest_observed_status, `${field}.key_context.historical_context.latest_observed_status`),
        first_observed_version: firstObserved,
        last_observed_version: lastObserved,
        attestation_time_binding_recorded: false,
        attestation_time_status: null,
      },
    },
    signature_envelope_recorded: envelopeRecorded,
    signing_trust_context: {
      recorded: signingRecorded,
      authentication: {
        status: signingAuthStatus,
        authenticated: signingAuthenticated as boolean | null,
        reason: string(signingAuthentication.reason, `${field}.signing_trust_context.authentication.reason`),
      },
      trust_state_version: boundVersion,
      trust_state_digest: boundTrustDigest,
      signing_key_digest: boundSigningKeyDigest,
      authority_key_id: boundAuthorityId,
      authority_key_digest: boundAuthorityDigest,
      signing_time_key_status: boundKeyStatus as "active" | null,
      trusted_timestamp_recorded: false,
    },
  };
}

export function parseAttestationTrust(value: unknown): AttestationTrustView {
  const source = object(value, "attestation trust");
  exactKeys(source, ["schema_version", "sources", "summary", "query", "page", "items", "limitations"], "attestation trust");
  if (source.schema_version !== "attestation-trust-investigation.v3") {
    throw new Error("unsupported attestation trust schema");
  }
  const sources = object(source.sources, "attestation trust.sources");
  exactKeys(sources, ["attestation_store", "trust_state", "authority_store", "trust_history"], "attestation trust.sources");
  const store = object(sources.attestation_store, "attestation trust.sources.attestation_store");
  exactKeys(store, ["configured", "exists", "byte_size", "read_limit_bytes", "record_limit", "signed_binding_count", "chain_integrity"], "attestation trust.sources.attestation_store");
  const trustState = object(sources.trust_state, "attestation trust.sources.trust_state");
  exactKeys(trustState, ["configured", "derived_from_history", "present", "version", "issued_at", "digest", "previous_digest", "authority_key_id", "authentication", "anchor_count", "anchors"], "attestation trust.sources.trust_state");
  const authentication = object(trustState.authentication, "attestation trust.sources.trust_state.authentication");
  exactKeys(authentication, ["status", "authenticated", "reason", "authority_key_digest"], "attestation trust.sources.trust_state.authentication");
  const authorityStore = object(sources.authority_store, "attestation trust.sources.authority_store");
  exactKeys(authorityStore, ["configured", "raw_keys_exposed"], "attestation trust.sources.authority_store");
  const history = object(sources.trust_history, "attestation trust.sources.trust_history");
  exactKeys(history, ["configured", "exists", "byte_size", "read_limit_bytes", "record_limit", "state_count", "chain_integrity", "authentication_status", "lifecycle_authoritative", "first_version", "latest_version", "tip_digest", "current_tip_alignment", "states", "transitions"], "attestation trust.sources.trust_history");
  const summary = object(source.summary, "attestation trust.summary");
  exactKeys(summary, ["total_attestations", "signing_key_references", "signed_envelope_records", "verified_signed_bindings", "unsigned_attestations", "active_key_references", "revoked_key_references", "superseded_key_references", "untrusted_key_references", "unauthenticated_key_references", "unconfigured_trust_state_references", "historically_observed_key_references", "historically_active_key_references"], "attestation trust.summary");
  const query = object(source.query, "attestation trust.query");
  exactKeys(query, ["decision", "reliability_state", "key_status", "text", "limit", "offset"], "attestation trust.query");
  const page = object(source.page, "attestation trust.page");
  exactKeys(page, ["limit", "offset", "returned", "matched", "has_more", "next_offset"], "attestation trust.page");
  if (!Array.isArray(source.items) || !Array.isArray(trustState.anchors) || !Array.isArray(history.states) || !Array.isArray(history.transitions)) {
    throw new Error("attestation trust collections must be arrays");
  }
  const items = source.items.map(parseAttestationTrustItem);
  const anchors = trustState.anchors.map((item, index) =>
    parseAttestationTrustAnchor(item, `attestation trust.sources.trust_state.anchors[${index}]`),
  );
  const authenticatedValue = authentication.authenticated;
  if (authenticatedValue !== null && typeof authenticatedValue !== "boolean") {
    throw new Error("attestation trust authentication must be boolean or null");
  }
  const authStatus = string(authentication.status, "attestation trust.authentication.status");
  if (!new Set(["verified", "failed", "not-configured", "dependency-unavailable"]).has(authStatus)) {
    throw new Error("attestation trust authentication status is unsupported");
  }
  if ((authStatus === "verified") !== (authenticatedValue === true)) {
    throw new Error("attestation trust verified authentication is inconsistent");
  }
  if (authStatus === "failed" && authenticatedValue !== false) {
    throw new Error("attestation trust failed authentication is inconsistent");
  }
  if ((authStatus === "not-configured" || authStatus === "dependency-unavailable") && authenticatedValue !== null) {
    throw new Error("attestation trust unavailable authentication must be null");
  }
  if (authenticatedValue !== true && anchors.some((anchor) => anchor.current_trust_applicable)) {
    throw new Error("unauthenticated trust state cannot be marked as current trust authority");
  }
  const limit = number(page.limit, "attestation trust.page.limit");
  const offset = number(page.offset, "attestation trust.page.offset");
  const returned = number(page.returned, "attestation trust.page.returned");
  const matched = number(page.matched, "attestation trust.page.matched");
  const hasMore = boolean(page.has_more, "attestation trust.page.has_more");
  const nextOffset = nullableNumber(page.next_offset, "attestation trust.page.next_offset");
  if (![limit, offset, returned, matched].every((item) => Number.isInteger(item) && item >= 0)) {
    throw new Error("attestation trust pagination must use non-negative integers");
  }
  if (limit < 1 || limit > 200 || returned !== items.length || returned > limit || matched < returned) {
    throw new Error("attestation trust pagination is inconsistent");
  }
  if (hasMore !== (offset + returned < matched)) {
    throw new Error("attestation trust has_more is inconsistent");
  }
  if ((hasMore && nextOffset !== offset + returned) || (!hasMore && nextOffset !== null)) {
    throw new Error("attestation trust next_offset is inconsistent");
  }
  const total = number(summary.total_attestations, "attestation trust.summary.total_attestations");
  if (!Number.isInteger(total) || total < matched) {
    throw new Error("attestation trust total count is inconsistent");
  }
  const signedBindingCount = number(store.signed_binding_count, "attestation trust.store.signed_binding_count");
  const signedEnvelopeRecords = number(summary.signed_envelope_records, "attestation trust.summary.signed_envelope_records");
  const verifiedSignedBindings = number(summary.verified_signed_bindings, "attestation trust.summary.verified_signed_bindings");
  for (const value of [signedBindingCount, signedEnvelopeRecords, verifiedSignedBindings]) {
    if (!Number.isInteger(value) || value < 0 || value > total) {
      throw new Error("attestation trust signed-binding counts are inconsistent");
    }
  }
  if (signedBindingCount !== signedEnvelopeRecords || verifiedSignedBindings > signedEnvelopeRecords) {
    throw new Error("attestation trust signed-binding counts disagree");
  }
  const anchorCount = number(trustState.anchor_count, "attestation trust.sources.trust_state.anchor_count");
  if (!Number.isInteger(anchorCount) || anchorCount !== anchors.length) {
    throw new Error("attestation trust anchor count is inconsistent");
  }
  const sourceConfigured = boolean(store.configured, "attestation trust.store.configured");
  const sourceExists = boolean(store.exists, "attestation trust.store.exists");
  const chainIntegrity = string(store.chain_integrity, "attestation trust.store.chain_integrity");
  if (!new Set(["verified", "missing", "not-configured"]).has(chainIntegrity)) {
    throw new Error("attestation trust chain-integrity status is unsupported");
  }
  if (!sourceConfigured && chainIntegrity !== "not-configured") {
    throw new Error("unconfigured attestation store cannot be verified");
  }
  if (sourceConfigured && !sourceExists && chainIntegrity !== "missing") {
    throw new Error("missing attestation store must be explicit");
  }
  if (authorityStore.raw_keys_exposed !== false) {
    throw new Error("attestation trust authority store must not expose raw keys");
  }
  for (const item of items) {
    if (["active", "revoked", "superseded"].includes(item.key_context.effective_current_status) && authenticatedValue !== true) {
      throw new Error("current key lifecycle status requires authenticated trust state");
    }
  }
  const trustVersion = nullableNumber(trustState.version, "attestation trust.trust_state.version");
  if (trustVersion !== null && (!Number.isInteger(trustVersion) || trustVersion < 1)) {
    throw new Error("attestation trust-state version must be a positive integer or null");
  }
  const derivedFromHistory = boolean(trustState.derived_from_history, "attestation trust.trust_state.derived_from_history");
  if (derivedFromHistory && !boolean(trustState.present, "attestation trust.trust_state.present")) {
    throw new Error("history-derived trust state must be present");
  }

  const historyConfigured = boolean(history.configured, "attestation trust.trust_history.configured");
  const historyExists = boolean(history.exists, "attestation trust.trust_history.exists");
  const historyStateCount = number(history.state_count, "attestation trust.trust_history.state_count");
  if (!Number.isInteger(historyStateCount) || historyStateCount < 0 || historyStateCount !== history.states.length) {
    throw new Error("attestation trust history state count is inconsistent");
  }
  const historyIntegrity = string(history.chain_integrity, "attestation trust.trust_history.chain_integrity");
  if (!new Set(["verified", "missing", "not-configured"]).has(historyIntegrity)) {
    throw new Error("attestation trust history chain-integrity status is unsupported");
  }
  if (!historyConfigured && historyIntegrity !== "not-configured") {
    throw new Error("unconfigured trust history cannot claim chain integrity");
  }
  if (historyConfigured && !historyExists && historyIntegrity !== "missing") {
    throw new Error("missing trust history must be explicit");
  }
  const historyAuthentication = string(history.authentication_status, "attestation trust.trust_history.authentication_status");
  if (!new Set(["not-configured", "not-present", "empty", "verified", "authority-not-configured", "dependency-unavailable", "unavailable"]).has(historyAuthentication)) {
    throw new Error("attestation trust history authentication status is unsupported");
  }
  const lifecycleAuthoritative = boolean(history.lifecycle_authoritative, "attestation trust.trust_history.lifecycle_authoritative");
  if (lifecycleAuthoritative !== (historyAuthentication === "verified")) {
    throw new Error("attestation trust history authority status is inconsistent");
  }
  if (!lifecycleAuthoritative && history.transitions.length !== 0) {
    throw new Error("unauthenticated trust history cannot expose derived lifecycle transitions");
  }
  const firstVersion = nullableNumber(history.first_version, "attestation trust.trust_history.first_version");
  const latestVersion = nullableNumber(history.latest_version, "attestation trust.trust_history.latest_version");
  if ((firstVersion === null) !== (latestVersion === null)) {
    throw new Error("attestation trust history version bounds are inconsistent");
  }
  if (firstVersion !== null && latestVersion !== null && (firstVersion < 1 || latestVersion < firstVersion)) {
    throw new Error("attestation trust history version bounds are invalid");
  }
  if ((historyStateCount === 0) !== (firstVersion === null)) {
    throw new Error("attestation trust history version bounds disagree with state count");
  }
  const alignment = string(history.current_tip_alignment, "attestation trust.trust_history.current_tip_alignment");
  if (!new Set(["verified", "mismatch", "not-established"]).has(alignment)) {
    throw new Error("attestation trust history current-tip alignment is unsupported");
  }
  if (alignment === "verified" && (!lifecycleAuthoritative || authenticatedValue !== true)) {
    throw new Error("trust-history tip alignment requires authenticated history and current state");
  }

  const states = history.states.map((value, index) => {
    const item = object(value, `attestation trust.trust_history.states[${index}]`);
    exactKeys(item, ["version", "issued_at", "digest", "previous_digest", "authority_key_id", "anchor_count"], `attestation trust.trust_history.states[${index}]`);
    const stateVersion = number(item.version, `attestation trust.trust_history.states[${index}].version`);
    const anchorCountValue = number(item.anchor_count, `attestation trust.trust_history.states[${index}].anchor_count`);
    if (!Number.isInteger(stateVersion) || stateVersion < 1 || !Number.isInteger(anchorCountValue) || anchorCountValue < 0) {
      throw new Error("attestation trust history state values are invalid");
    }
    return {
      version: stateVersion,
      issued_at: string(item.issued_at, `attestation trust.trust_history.states[${index}].issued_at`),
      digest: string(item.digest, `attestation trust.trust_history.states[${index}].digest`),
      previous_digest: nullableString(item.previous_digest, `attestation trust.trust_history.states[${index}].previous_digest`),
      authority_key_id: string(item.authority_key_id, `attestation trust.trust_history.states[${index}].authority_key_id`),
      anchor_count: anchorCountValue,
    };
  });
  const transitions = history.transitions.map((value, index) => {
    const item = object(value, `attestation trust.trust_history.transitions[${index}]`);
    exactKeys(item, ["from_version", "to_version", "from_digest", "to_digest", "issued_at", "authority_key_id", "authority_changed", "activated_key_ids", "revoked_key_ids", "superseded_keys", "removed_key_ids"], `attestation trust.trust_history.transitions[${index}]`);
    if (!Array.isArray(item.superseded_keys)) throw new Error("attestation trust superseded_keys must be an array");
    return {
      from_version: number(item.from_version, `attestation trust.trust_history.transitions[${index}].from_version`),
      to_version: number(item.to_version, `attestation trust.trust_history.transitions[${index}].to_version`),
      from_digest: string(item.from_digest, `attestation trust.trust_history.transitions[${index}].from_digest`),
      to_digest: string(item.to_digest, `attestation trust.trust_history.transitions[${index}].to_digest`),
      issued_at: string(item.issued_at, `attestation trust.trust_history.transitions[${index}].issued_at`),
      authority_key_id: string(item.authority_key_id, `attestation trust.trust_history.transitions[${index}].authority_key_id`),
      authority_changed: boolean(item.authority_changed, `attestation trust.trust_history.transitions[${index}].authority_changed`),
      activated_key_ids: strings(item.activated_key_ids, `attestation trust.trust_history.transitions[${index}].activated_key_ids`),
      revoked_key_ids: strings(item.revoked_key_ids, `attestation trust.trust_history.transitions[${index}].revoked_key_ids`),
      superseded_keys: item.superseded_keys.map((entry, entryIndex) => {
        const pair = object(entry, `attestation trust.trust_history.transitions[${index}].superseded_keys[${entryIndex}]`);
        exactKeys(pair, ["key_id", "superseded_by"], `attestation trust.trust_history.transitions[${index}].superseded_keys[${entryIndex}]`);
        return {
          key_id: string(pair.key_id, `attestation trust.trust_history.transitions[${index}].superseded_keys[${entryIndex}].key_id`),
          superseded_by: nullableString(pair.superseded_by, `attestation trust.trust_history.transitions[${index}].superseded_keys[${entryIndex}].superseded_by`),
        };
      }),
      removed_key_ids: strings(item.removed_key_ids, `attestation trust.trust_history.transitions[${index}].removed_key_ids`),
    };
  });

  return {
    schema_version: "attestation-trust-investigation.v3",
    sources: {
      attestation_store: {
        configured: sourceConfigured,
        exists: sourceExists,
        byte_size: number(store.byte_size, "attestation trust.store.byte_size"),
        read_limit_bytes: number(store.read_limit_bytes, "attestation trust.store.read_limit_bytes"),
        record_limit: number(store.record_limit, "attestation trust.store.record_limit"),
        signed_binding_count: number(store.signed_binding_count, "attestation trust.store.signed_binding_count"),
        chain_integrity: chainIntegrity,
      },
      trust_state: {
        configured: boolean(trustState.configured, "attestation trust.trust_state.configured"),
        derived_from_history: derivedFromHistory,
        present: boolean(trustState.present, "attestation trust.trust_state.present"),
        version: trustVersion,
        issued_at: nullableString(trustState.issued_at, "attestation trust.trust_state.issued_at"),
        digest: nullableString(trustState.digest, "attestation trust.trust_state.digest"),
        previous_digest: nullableString(trustState.previous_digest, "attestation trust.trust_state.previous_digest"),
        authority_key_id: nullableString(trustState.authority_key_id, "attestation trust.trust_state.authority_key_id"),
        authentication: {
          status: authStatus,
          authenticated: authenticatedValue as boolean | null,
          reason: string(authentication.reason, "attestation trust.authentication.reason"),
          authority_key_digest: nullableString(authentication.authority_key_digest, "attestation trust.authentication.authority_key_digest"),
        },
        anchor_count: anchorCount,
        anchors,
      },
      authority_store: {
        configured: boolean(authorityStore.configured, "attestation trust.authority_store.configured"),
        raw_keys_exposed: false,
      },
      trust_history: {
        configured: historyConfigured,
        exists: historyExists,
        byte_size: number(history.byte_size, "attestation trust.trust_history.byte_size"),
        read_limit_bytes: number(history.read_limit_bytes, "attestation trust.trust_history.read_limit_bytes"),
        record_limit: number(history.record_limit, "attestation trust.trust_history.record_limit"),
        state_count: historyStateCount,
        chain_integrity: historyIntegrity,
        authentication_status: historyAuthentication,
        lifecycle_authoritative: lifecycleAuthoritative,
        first_version: firstVersion,
        latest_version: latestVersion,
        tip_digest: nullableString(history.tip_digest, "attestation trust.trust_history.tip_digest"),
        current_tip_alignment: alignment,
        states,
        transitions,
      },
    },
    summary: {
      total_attestations: total,
      signing_key_references: number(summary.signing_key_references, "attestation trust.summary.signing_key_references"),
      signed_envelope_records: number(summary.signed_envelope_records, "attestation trust.summary.signed_envelope_records"),
      verified_signed_bindings: number(summary.verified_signed_bindings, "attestation trust.summary.verified_signed_bindings"),
      unsigned_attestations: number(summary.unsigned_attestations, "attestation trust.summary.unsigned_attestations"),
      active_key_references: number(summary.active_key_references, "attestation trust.summary.active_key_references"),
      revoked_key_references: number(summary.revoked_key_references, "attestation trust.summary.revoked_key_references"),
      superseded_key_references: number(summary.superseded_key_references, "attestation trust.summary.superseded_key_references"),
      untrusted_key_references: number(summary.untrusted_key_references, "attestation trust.summary.untrusted_key_references"),
      unauthenticated_key_references: number(summary.unauthenticated_key_references, "attestation trust.summary.unauthenticated_key_references"),
      unconfigured_trust_state_references: number(summary.unconfigured_trust_state_references, "attestation trust.summary.unconfigured_trust_state_references"),
      historically_observed_key_references: number(summary.historically_observed_key_references, "attestation trust.summary.historically_observed_key_references"),
      historically_active_key_references: number(summary.historically_active_key_references, "attestation trust.summary.historically_active_key_references"),
    },
    query: {
      decision: nullableString(query.decision, "attestation trust.query.decision"),
      reliability_state: nullableString(query.reliability_state, "attestation trust.query.reliability_state"),
      key_status: nullableString(query.key_status, "attestation trust.query.key_status"),
      text: nullableString(query.text, "attestation trust.query.text"),
      limit: number(query.limit, "attestation trust.query.limit"),
      offset: number(query.offset, "attestation trust.query.offset"),
    },
    page: { limit, offset, returned, matched, has_more: hasMore, next_offset: nextOffset },
    items,
    limitations: strings(source.limitations, "attestation trust.limitations"),
  };
}

export function parseCaptureHealth(value: unknown): CaptureHealthView {
  const source = object(value, "capture health");
  if (source.schema_version !== "capture-health.v1") {
    throw new Error("unsupported capture health schema");
  }
  const sourceInfo = object(source.source, "capture health.source");
  const observations = object(source.observations, "capture health.observations");
  const aggregates = object(source.aggregates, "capture health.aggregates");
  const query = object(source.query, "capture health.query");
  const page = object(source.page, "capture health.page");
  if (sourceInfo.resource !== "native-capture-failure-journal") {
    throw new Error("capture health source resource is unsupported");
  }
  if (!Array.isArray(source.items) || !Array.isArray(aggregates.by_stage) || !Array.isArray(aggregates.by_error_type)) {
    throw new Error("capture health lists must be arrays");
  }
  const items = source.items.map((item, index) => {
    const row = object(item, `capture health.items[${index}]`);
    return {
      sequence: number(row.sequence, `capture health.items[${index}].sequence`),
      stage: string(row.stage, `capture health.items[${index}].stage`),
      error_type: string(row.error_type, `capture health.items[${index}].error_type`),
    };
  });
  const recorded = number(observations.recorded_failure_count, "capture health.observations.recorded_failure_count");
  const returned = number(page.returned, "capture health.page.returned");
  const matched = number(page.matched, "capture health.page.matched");
  const limit = number(page.limit, "capture health.page.limit");
  const offset = number(page.offset, "capture health.page.offset");
  const hasMore = boolean(page.has_more, "capture health.page.has_more");
  const nextOffset = nullableNumber(page.next_offset, "capture health.page.next_offset");
  if (![recorded, returned, matched, limit, offset].every((item) => Number.isInteger(item) && item >= 0)) {
    throw new Error("capture health counts must be non-negative integers");
  }
  if (returned !== items.length || returned > limit || matched < returned || matched > recorded || limit < 1 || limit > 200) {
    throw new Error("capture health pagination is inconsistent");
  }
  if (hasMore !== (offset + returned < matched)) {
    throw new Error("capture health has_more is inconsistent");
  }
  if ((hasMore && nextOffset !== offset + returned) || (!hasMore && nextOffset !== null)) {
    throw new Error("capture health next_offset is inconsistent");
  }
  if (observations.capture_success_inferred !== false || observations.workspace_durability_inferred !== false || observations.timestamps_available !== false) {
    throw new Error("capture health must not infer success, durability, or timestamps");
  }
  const status = string(observations.status, "capture health.observations.status");
  if (status !== "failures-recorded" && status !== "no-failures-recorded") {
    throw new Error("capture health observation status is unsupported");
  }
  const declaredCapacity = nullableNumber(sourceInfo.declared_capacity_bytes, "capture health.source.declared_capacity_bytes");
  const remaining = nullableNumber(sourceInfo.declared_capacity_remaining_bytes, "capture health.source.declared_capacity_remaining_bytes");
  return {
    schema_version: "capture-health.v1",
    source: {
      resource: "native-capture-failure-journal",
      journal_exists: boolean(sourceInfo.journal_exists, "capture health.source.journal_exists"),
      journal_bytes: number(sourceInfo.journal_bytes, "capture health.source.journal_bytes"),
      read_limit_bytes: number(sourceInfo.read_limit_bytes, "capture health.source.read_limit_bytes"),
      declared_capacity_bytes: declaredCapacity,
      declared_capacity_state: string(sourceInfo.declared_capacity_state, "capture health.source.declared_capacity_state"),
      declared_capacity_remaining_bytes: remaining,
    },
    observations: {
      recorded_failure_count: recorded,
      distinct_stage_count: number(observations.distinct_stage_count, "capture health.observations.distinct_stage_count"),
      distinct_error_type_count: number(observations.distinct_error_type_count, "capture health.observations.distinct_error_type_count"),
      status,
      capture_success_inferred: false,
      workspace_durability_inferred: false,
      timestamps_available: false,
    },
    aggregates: {
      by_stage: aggregates.by_stage.map((item, index) => {
        const row = object(item, `capture health.aggregates.by_stage[${index}]`);
        return { stage: string(row.stage, `capture health.aggregates.by_stage[${index}].stage`), count: number(row.count, `capture health.aggregates.by_stage[${index}].count`) };
      }),
      by_error_type: aggregates.by_error_type.map((item, index) => {
        const row = object(item, `capture health.aggregates.by_error_type[${index}]`);
        return { error_type: string(row.error_type, `capture health.aggregates.by_error_type[${index}].error_type`), count: number(row.count, `capture health.aggregates.by_error_type[${index}].count`) };
      }),
    },
    query: {
      stage: nullableString(query.stage, "capture health.query.stage"),
      error_type: nullableString(query.error_type, "capture health.query.error_type"),
      limit: number(query.limit, "capture health.query.limit"),
      offset: number(query.offset, "capture health.query.offset"),
    },
    page: { limit, offset, returned, matched, has_more: hasMore, next_offset: nextOffset },
    items,
    limitations: strings(source.limitations, "capture health.limitations"),
  };
}

function parseIncidentEvidenceReference(
  value: unknown,
  field: string,
): IncidentEvidenceReferenceView {
  const source = object(value, field);
  return {
    kind: string(source.kind, `${field}.kind`),
    identity: string(source.identity, `${field}.identity`),
    digest: string(source.digest, `${field}.digest`),
    source_recorded: boolean(source.source_recorded, `${field}.source_recorded`),
  };
}

function parseIncidentPortfolioItem(value: unknown, field: string): IncidentPortfolioItem {
  const source = object(value, field);
  const recovery = object(source.recovery, `${field}.recovery`);
  const postRecovery = object(source.post_recovery, `${field}.post_recovery`);
  return {
    incident_id: string(source.incident_id, `${field}.incident_id`),
    event_id: string(source.event_id, `${field}.event_id`),
    detected_at: string(source.detected_at, `${field}.detected_at`),
    latest_recorded_at: string(source.latest_recorded_at, `${field}.latest_recorded_at`),
    actor: string(source.actor, `${field}.actor`),
    category: string(source.category, `${field}.category`),
    status: string(source.status, `${field}.status`),
    observation_count: number(source.observation_count, `${field}.observation_count`),
    evidence_ref_count: number(source.evidence_ref_count, `${field}.evidence_ref_count`),
    affected_state_count: number(source.affected_state_count, `${field}.affected_state_count`),
    uncertainty_count: number(source.uncertainty_count, `${field}.uncertainty_count`),
    key_compromise_recorded: boolean(
      source.key_compromise_recorded,
      `${field}.key_compromise_recorded`,
    ),
    recovery: {
      recorded: boolean(recovery.recorded, `${field}.recovery.recorded`),
      status: nullableString(recovery.status, `${field}.recovery.status`),
    },
    post_recovery: {
      recorded: boolean(postRecovery.recorded, `${field}.post_recovery.recorded`),
      status: nullableString(postRecovery.status, `${field}.post_recovery.status`),
    },
    forensic_continuity_verified: boolean(
      source.forensic_continuity_verified,
      `${field}.forensic_continuity_verified`,
    ),
  };
}

export function parseIncidentPortfolio(value: unknown): IncidentPortfolio {
  const source = object(value, "incident portfolio");
  if (source.schema_version !== "incident-investigation.v1") {
    throw new Error("unsupported incident portfolio schema");
  }
  const scope = object(source.scope, "incident portfolio.scope");
  const query = object(source.query, "incident portfolio.query");
  const page = object(source.page, "incident portfolio.page");
  if (!Array.isArray(source.items)) {
    throw new Error("incident portfolio.items must be an array");
  }
  const items = source.items.map((item, index) =>
    parseIncidentPortfolioItem(item, `incident portfolio.items[${index}]`),
  );
  const storeRecords = number(scope.store_records, "incident portfolio.scope.store_records");
  const total = number(scope.total_incidents, "incident portfolio.scope.total_incidents");
  const matched = number(scope.matched_incidents, "incident portfolio.scope.matched_incidents");
  const limit = number(page.limit, "incident portfolio.page.limit");
  const offset = number(page.offset, "incident portfolio.page.offset");
  const returned = number(page.returned, "incident portfolio.page.returned");
  const hasMore = boolean(page.has_more, "incident portfolio.page.has_more");
  const nextOffset = nullableNumber(page.next_offset, "incident portfolio.page.next_offset");
  if (returned !== items.length || returned > limit || matched > total || total > storeRecords) {
    throw new Error("incident portfolio counts are inconsistent");
  }
  if (hasMore !== (nextOffset !== null)) {
    throw new Error("incident portfolio pagination continuation is inconsistent");
  }
  return {
    schema_version: "incident-investigation.v1",
    scope: {
      resource: "security-incident-evidence",
      sort: "latest_recorded_at_desc_incident_id_asc",
      store_records: storeRecords,
      total_incidents: total,
      matched_incidents: matched,
    },
    query: {
      status: nullableString(query.status, "incident portfolio.query.status"),
      category: nullableString(query.category, "incident portfolio.query.category"),
      text: nullableString(query.text, "incident portfolio.query.text"),
      limit: number(query.limit, "incident portfolio.query.limit"),
      offset: number(query.offset, "incident portfolio.query.offset"),
    },
    page: { limit, offset, returned, has_more: hasMore, next_offset: nextOffset },
    items,
    limitations: strings(source.limitations, "incident portfolio.limitations"),
  };
}

export function parseIncidentDetail(value: unknown): IncidentDetail {
  const source = object(value, "incident detail");
  if (source.schema_version !== "incident-detail.v1") {
    throw new Error("unsupported incident detail schema");
  }
  if (!Array.isArray(source.lifecycle)) throw new Error("incident detail.lifecycle must be an array");
  if (!Array.isArray(source.evidence_refs)) throw new Error("incident detail.evidence_refs must be an array");
  if (!Array.isArray(source.affected_states)) throw new Error("incident detail.affected_states must be an array");
  const continuity = object(source.forensic_continuity, "incident detail.forensic_continuity");
  if (continuity.causality_established !== false) {
    throw new Error("incident detail must not assert causality");
  }
  let keyCompromise: IncidentDetail["key_compromise"] = null;
  if (source.key_compromise !== null) {
    const key = object(source.key_compromise, "incident detail.key_compromise");
    if (!Array.isArray(key.affected_evidence)) {
      throw new Error("incident detail.key_compromise.affected_evidence must be an array");
    }
    keyCompromise = {
      key_identity: string(key.key_identity, "incident detail.key_compromise.key_identity"),
      affected_key_version: string(
        key.affected_key_version,
        "incident detail.key_compromise.affected_key_version",
      ),
      affected_attestation_ids: strings(
        key.affected_attestation_ids,
        "incident detail.key_compromise.affected_attestation_ids",
      ),
      affected_evidence: key.affected_evidence.map((item, index) =>
        parseIncidentEvidenceReference(
          item,
          `incident detail.key_compromise.affected_evidence[${index}]`,
        ),
      ),
      exposure_start: string(key.exposure_start, "incident detail.key_compromise.exposure_start"),
      exposure_end: nullableString(key.exposure_end, "incident detail.key_compromise.exposure_end"),
    };
  }
  let recovery: IncidentDetail["recovery"] = null;
  if (source.recovery !== null) {
    const item = object(source.recovery, "incident detail.recovery");
    recovery = {
      recovery_id: string(item.recovery_id, "incident detail.recovery.recovery_id"),
      actor: string(item.actor, "incident detail.recovery.actor"),
      source_incident_id: string(
        item.source_incident_id,
        "incident detail.recovery.source_incident_id",
      ),
      status: string(item.status, "incident detail.recovery.status"),
      evidence_ref: parseIncidentEvidenceReference(
        item.evidence_ref,
        "incident detail.recovery.evidence_ref",
      ),
    };
  }
  let postRecovery: IncidentDetail["post_recovery"] = null;
  if (source.post_recovery !== null) {
    const item = object(source.post_recovery, "incident detail.post_recovery");
    if (!Array.isArray(item.evidence_refs)) {
      throw new Error("incident detail.post_recovery.evidence_refs must be an array");
    }
    postRecovery = {
      verification_id: string(
        item.verification_id,
        "incident detail.post_recovery.verification_id",
      ),
      actor: string(item.actor, "incident detail.post_recovery.actor"),
      status: string(item.status, "incident detail.post_recovery.status"),
      performed_at: string(item.performed_at, "incident detail.post_recovery.performed_at"),
      evidence_refs: item.evidence_refs.map((ref, index) =>
        parseIncidentEvidenceReference(
          ref,
          `incident detail.post_recovery.evidence_refs[${index}]`,
        ),
      ),
    };
  }
  return {
    schema_version: "incident-detail.v1",
    incident: parseIncidentPortfolioItem(source.incident, "incident detail.incident"),
    lifecycle: source.lifecycle.map((item, index) => {
      const entry = object(item, `incident detail.lifecycle[${index}]`);
      return {
        sequence: number(entry.sequence, `incident detail.lifecycle[${index}].sequence`),
        recorded_at: string(entry.recorded_at, `incident detail.lifecycle[${index}].recorded_at`),
        status: string(entry.status, `incident detail.lifecycle[${index}].status`),
        record_digest: string(entry.record_digest, `incident detail.lifecycle[${index}].record_digest`),
        incident_digest: string(entry.incident_digest, `incident detail.lifecycle[${index}].incident_digest`),
      };
    }),
    evidence_refs: source.evidence_refs.map((item, index) =>
      parseIncidentEvidenceReference(item, `incident detail.evidence_refs[${index}]`),
    ),
    affected_states: source.affected_states.map((item, index) => {
      const state = object(item, `incident detail.affected_states[${index}]`);
      return {
        state_id: string(state.state_id, `incident detail.affected_states[${index}].state_id`),
        state_digest: string(state.state_digest, `incident detail.affected_states[${index}].state_digest`),
        trust_context: string(state.trust_context, `incident detail.affected_states[${index}].trust_context`),
        affected_window_start: nullableString(
          state.affected_window_start,
          `incident detail.affected_states[${index}].affected_window_start`,
        ),
        affected_window_end: nullableString(
          state.affected_window_end,
          `incident detail.affected_states[${index}].affected_window_end`,
        ),
      };
    }),
    security_event_digests: strings(source.security_event_digests, "incident detail.security_event_digests"),
    uncertainty: strings(source.uncertainty, "incident detail.uncertainty"),
    key_compromise: keyCompromise,
    recovery,
    post_recovery: postRecovery,
    forensic_continuity: {
      required: boolean(continuity.required, "incident detail.forensic_continuity.required"),
      verified: boolean(continuity.verified, "incident detail.forensic_continuity.verified"),
      causality_established: false,
    },
    limitations: strings(source.limitations, "incident detail.limitations"),
  };
}

export function parseClaimDetail(value: unknown): ClaimDetail {
  const source = object(value, "claim detail");
  if (source.schema_version !== "claim-detail.v1") {
    throw new Error("unsupported claim detail schema");
  }
  const record = object(source.source, "source");
  const checks = object(source.checks, "checks");
  const evidence = object(source.evidence, "evidence");
  const links = object(source.links, "links");
  return {
    schema_version: "claim-detail.v1",
    source: {
      record_id: string(record.record_id, "source.record_id"),
      artifact_digest: string(record.artifact_digest, "source.artifact_digest"),
      producer_id: string(record.producer_id, "source.producer_id"),
      producer_type: string(record.producer_type, "source.producer_type"),
      captured_at: string(record.captured_at, "source.captured_at"),
      run_id: nullableString(record.run_id, "source.run_id"),
      sensitivity: nullableString(record.sensitivity, "source.sensitivity"),
    },
    summary: parseSummary(source.summary),
    checks: {
      passed: strings(checks.passed, "checks.passed"),
      failed: strings(checks.failed, "checks.failed"),
      unrun: strings(checks.unrun, "checks.unrun"),
      unknown: strings(checks.unknown, "checks.unknown"),
    },
    evidence: {
      included: strings(evidence.included, "evidence.included"),
      omitted: strings(evidence.omitted, "evidence.omitted"),
      missing: strings(evidence.missing, "evidence.missing"),
      source_identities: strings(evidence.source_identities, "evidence.source_identities"),
      artifact_digests: strings(evidence.artifact_digests, "evidence.artifact_digests"),
    },
    decision_rationale: strings(source.decision_rationale, "decision_rationale"),
    recovery_status: string(source.recovery_status, "recovery_status"),
    allowed_use: strings(source.allowed_use, "allowed_use"),
    prohibited_use: strings(source.prohibited_use, "prohibited_use"),
    machine_readable_appendix: strings(
      source.machine_readable_appendix,
      "machine_readable_appendix",
    ),
    profile_evaluation_digest: nullableString(
      source.profile_evaluation_digest,
      "profile_evaluation_digest",
    ),
    verifier_version: string(source.verifier_version, "verifier_version"),
    generated_at: string(source.generated_at, "generated_at"),
    report_digest: string(source.report_digest, "report_digest"),
    links: {
      canonical_json: string(links.canonical_json, "links.canonical_json"),
      canonical_markdown: string(links.canonical_markdown, "links.canonical_markdown"),
    },
  };
}

function parseHistoryItem(value: unknown, index: number): ClaimHistoryItem {
  const source = object(value, `history.items[${index}]`);
  return {
    sequence: number(source.sequence, `history.items[${index}].sequence`),
    transition_id: string(source.transition_id, `history.items[${index}].transition_id`),
    subject_id: string(source.subject_id, `history.items[${index}].subject_id`),
    from_state: string(source.from_state, `history.items[${index}].from_state`),
    to_state: string(source.to_state, `history.items[${index}].to_state`),
    occurred_at: string(source.occurred_at, `history.items[${index}].occurred_at`),
    actor: string(source.actor, `history.items[${index}].actor`),
    evidence_chain_id: string(
      source.evidence_chain_id,
      `history.items[${index}].evidence_chain_id`,
    ),
    evidence_chain_digest: string(
      source.evidence_chain_digest,
      `history.items[${index}].evidence_chain_digest`,
    ),
    decision: string(source.decision, `history.items[${index}].decision`),
    rationale: strings(source.rationale, `history.items[${index}].rationale`),
    previous_transition_digest: string(
      source.previous_transition_digest,
      `history.items[${index}].previous_transition_digest`,
    ),
    transition_digest: string(
      source.transition_digest,
      `history.items[${index}].transition_digest`,
    ),
  };
}

export function parseClaimHistory(value: unknown): ClaimHistory {
  const source = object(value, "history");
  if (source.schema_version !== "claim-history.v1") {
    throw new Error("unsupported claim history schema");
  }
  const candidate = object(source.candidate, "history.candidate");
  const profile = object(source.profile, "history.profile");
  if (!Array.isArray(source.items)) throw new Error("history.items must be an array");
  const items = source.items.map(parseHistoryItem);
  const recordedCount = number(source.recorded_count, "history.recorded_count");
  if (recordedCount !== items.length) {
    throw new Error("history.recorded_count must match history.items length");
  }
  return {
    schema_version: "claim-history.v1",
    report_record_id: string(source.report_record_id, "history.report_record_id"),
    candidate: {
      id: string(candidate.id, "history.candidate.id"),
      digest: string(candidate.digest, "history.candidate.digest"),
    },
    profile: {
      id: string(profile.id, "history.profile.id"),
      version: string(profile.version, "history.profile.version"),
    },
    recorded_count: recordedCount,
    items,
    limitations: strings(source.limitations, "history.limitations"),
  };
}

function parseStringDelta(value: unknown, field: string): StringDelta {
  const source = object(value, field);
  return {
    added: strings(source.added, `${field}.added`),
    removed: strings(source.removed, `${field}.removed`),
  };
}

function parseComparisonSide(value: unknown, field: string): ClaimComparisonSide {
  const source = object(value, field);
  const candidate = object(source.candidate, `${field}.candidate`);
  const profile = object(source.profile, `${field}.profile`);
  return {
    record_id: string(source.record_id, `${field}.record_id`),
    report_digest: string(source.report_digest, `${field}.report_digest`),
    candidate: {
      id: string(candidate.id, `${field}.candidate.id`),
      digest: string(candidate.digest, `${field}.candidate.digest`),
    },
    profile: {
      id: string(profile.id, `${field}.profile.id`),
      version: string(profile.version, `${field}.profile.version`),
    },
    claim: string(source.claim, `${field}.claim`),
    report_type: string(source.report_type, `${field}.report_type`),
    decision: string(source.decision, `${field}.decision`),
    verified: boolean(source.verified, `${field}.verified`),
    approval_status: string(source.approval_status, `${field}.approval_status`),
    generated_at: string(source.generated_at, `${field}.generated_at`),
    captured_at: string(source.captured_at, `${field}.captured_at`),
  };
}

function parseChange<T>(
  value: unknown,
  field: string,
  parser: (input: unknown, fieldName: string) => T,
): { before: T; after: T; changed: boolean } {
  const source = object(value, field);
  return {
    before: parser(source.before, `${field}.before`),
    after: parser(source.after, `${field}.after`),
    changed: boolean(source.changed, `${field}.changed`),
  };
}

export function parseClaimComparison(value: unknown): ClaimComparison {
  const source = object(value, "comparison");
  if (source.schema_version !== "claim-comparison.v1") {
    throw new Error("unsupported claim comparison schema");
  }
  const changes = object(source.changes, "comparison.changes");
  const checks = object(changes.checks, "comparison.changes.checks");
  const evidence = object(changes.evidence, "comparison.changes.evidence");
  return {
    schema_version: "claim-comparison.v1",
    semantic_scope_same: boolean(
      source.semantic_scope_same,
      "comparison.semantic_scope_same",
    ),
    non_equivalence_warnings: strings(
      source.non_equivalence_warnings,
      "comparison.non_equivalence_warnings",
    ),
    left: parseComparisonSide(source.left, "comparison.left"),
    right: parseComparisonSide(source.right, "comparison.right"),
    changes: {
      candidate_digest_changed: boolean(
        changes.candidate_digest_changed,
        "comparison.changes.candidate_digest_changed",
      ),
      decision: parseChange(changes.decision, "comparison.changes.decision", string),
      verified: parseChange(changes.verified, "comparison.changes.verified", boolean),
      approval_status: parseChange(
        changes.approval_status,
        "comparison.changes.approval_status",
        string,
      ),
      checks: {
        passed: parseStringDelta(checks.passed, "comparison.changes.checks.passed"),
        failed: parseStringDelta(checks.failed, "comparison.changes.checks.failed"),
        unrun: parseStringDelta(checks.unrun, "comparison.changes.checks.unrun"),
        unknown: parseStringDelta(checks.unknown, "comparison.changes.checks.unknown"),
      },
      evidence: {
        included: parseStringDelta(
          evidence.included,
          "comparison.changes.evidence.included",
        ),
        missing: parseStringDelta(
          evidence.missing,
          "comparison.changes.evidence.missing",
        ),
        omitted: parseStringDelta(
          evidence.omitted,
          "comparison.changes.evidence.omitted",
        ),
      },
      caveats: parseStringDelta(changes.caveats, "comparison.changes.caveats"),
      residual_risks: parseStringDelta(
        changes.residual_risks,
        "comparison.changes.residual_risks",
      ),
      human_decisions_required: parseStringDelta(
        changes.human_decisions_required,
        "comparison.changes.human_decisions_required",
      ),
    },
    limitations: strings(source.limitations, "comparison.limitations"),
  };
}

const REVIEW_CATEGORIES = new Set([
  "observation",
  "question",
  "change_requested",
  "finding",
  "review_complete",
]);

function reviewCategory(value: unknown, field: string): import("./dto").ReviewCategory {
  const parsed = string(value, field);
  if (!REVIEW_CATEGORIES.has(parsed)) {
    throw new Error(`${field} must be a supported review category`);
  }
  return parsed as import("./dto").ReviewCategory;
}

function parseReviewStatement(value: unknown, field: string): import("./dto").ReviewStatementRecord {
  const source = object(value, field);
  if (source.schema_version !== "review-statement.v1") {
    throw new Error("unsupported review statement schema");
  }
  return {
    schema_version: "review-statement.v1",
    sequence: number(source.sequence, `${field}.sequence`),
    target_record_id: string(source.target_record_id, `${field}.target_record_id`),
    candidate_identity: string(source.candidate_identity, `${field}.candidate_identity`),
    candidate_digest: string(source.candidate_digest, `${field}.candidate_digest`),
    report_digest: string(source.report_digest, `${field}.report_digest`),
    profile_id: string(source.profile_id, `${field}.profile_id`),
    profile_version: string(source.profile_version, `${field}.profile_version`),
    actor_identity_ref: string(source.actor_identity_ref, `${field}.actor_identity_ref`),
    actor_role: string(source.actor_role, `${field}.actor_role`),
    category: reviewCategory(source.category, `${field}.category`),
    statement: string(source.statement, `${field}.statement`),
    finding_refs: strings(source.finding_refs, `${field}.finding_refs`),
    limitation: nullableString(source.limitation, `${field}.limitation`),
    scope: string(source.scope, `${field}.scope`),
    created_at: string(source.created_at, `${field}.created_at`),
    idempotency_key: string(source.idempotency_key, `${field}.idempotency_key`),
    request_fingerprint: string(source.request_fingerprint, `${field}.request_fingerprint`),
    supersedes_digest: nullableString(source.supersedes_digest, `${field}.supersedes_digest`),
    previous_digest: nullableString(source.previous_digest, `${field}.previous_digest`),
    digest: string(source.digest, `${field}.digest`),
  };
}

export function parseReviewCapabilities(value: unknown): import("./dto").ReviewCapabilities {
  const source = object(value, "review capabilities");
  if (source.schema_version !== "review-capabilities.v1") {
    throw new Error("unsupported review capabilities schema");
  }
  const actor = object(source.actor, "review capabilities.actor");
  const features = object(source.features, "review capabilities.features");
  const limits = object(source.limits, "review capabilities.limits");
  let approval: { configured: true; note: string } | null = null;
  if (source.approval !== null) {
    const rawApproval = object(source.approval, "review capabilities.approval");
    if (rawApproval.configured !== true) {
      throw new Error("review capabilities.approval.configured must be true");
    }
    approval = {
      configured: true,
      note: string(rawApproval.note, "review capabilities.approval.note"),
    };
  }
  return {
    schema_version: "review-capabilities.v1",
    mode: string(source.mode, "review capabilities.mode"),
    statewake_version: string(source.statewake_version, "review capabilities.statewake_version"),
    actor: {
      identity_ref: string(actor.identity_ref, "review capabilities.actor.identity_ref"),
      role: string(actor.role, "review capabilities.actor.role"),
    },
    features: {
      review_read: boolean(features.review_read, "review capabilities.features.review_read"),
      review_write: boolean(features.review_write, "review capabilities.features.review_write"),
      approval_read: boolean(features.approval_read, "review capabilities.features.approval_read"),
      approval_write: boolean(features.approval_write, "review capabilities.features.approval_write"),
      approval_revoke: boolean(
        features.approval_revoke,
        "review capabilities.features.approval_revoke",
      ),
      approval_supersede: boolean(
        features.approval_supersede,
        "review capabilities.features.approval_supersede",
      ),
    },
    approval,
    limits: {
      statement_chars: number(limits.statement_chars, "review capabilities.limits.statement_chars"),
      limitation_chars: number(limits.limitation_chars, "review capabilities.limits.limitation_chars"),
      finding_refs: number(limits.finding_refs, "review capabilities.limits.finding_refs"),
      approval_reason_chars: number(
        limits.approval_reason_chars,
        "review capabilities.limits.approval_reason_chars",
      ),
    },
  };
}

export function parseReviewThread(value: unknown): import("./dto").ReviewThread {
  const source = object(value, "review thread");
  if (source.schema_version !== "review-thread.v1") {
    throw new Error("unsupported review thread schema");
  }
  const target = object(source.target, "review thread.target");
  if (!Array.isArray(source.items)) throw new Error("review thread.items must be an array");
  return {
    schema_version: "review-thread.v1",
    target: {
      record_id: string(target.record_id, "review thread.target.record_id"),
      candidate_identity: string(target.candidate_identity, "review thread.target.candidate_identity"),
      candidate_digest: string(target.candidate_digest, "review thread.target.candidate_digest"),
      report_digest: string(target.report_digest, "review thread.target.report_digest"),
      profile_id: string(target.profile_id, "review thread.target.profile_id"),
      profile_version: string(target.profile_version, "review thread.target.profile_version"),
    },
    items: source.items.map((item, index) => parseReviewStatement(item, `review thread.items[${index}]`)),
    limitations: strings(source.limitations, "review thread.limitations"),
  };
}

export function parseReviewStatementResult(value: unknown): import("./dto").ReviewStatementResult {
  const source = object(value, "review result");
  if (source.schema_version !== "review-statement-result.v1") {
    throw new Error("unsupported review statement result schema");
  }
  const approvalCreated = boolean(source.approval_created, "review result.approval_created");
  if (approvalCreated) throw new Error("review statement endpoint must not create approval evidence");
  return {
    schema_version: "review-statement-result.v1",
    created: boolean(source.created, "review result.created"),
    approval_created: false,
    review: parseReviewStatement(source.review, "review result.review"),
  };
}


function parseOverviewReportItem(value: unknown, field: string): OverviewReportItem {
  const source = object(value, field);
  const candidate = object(source.candidate, `${field}.candidate`);
  const profile = object(source.profile, `${field}.profile`);
  return {
    record_id: string(source.record_id, `${field}.record_id`),
    claim: string(source.claim, `${field}.claim`),
    decision: string(source.decision, `${field}.decision`),
    verified: boolean(source.verified, `${field}.verified`),
    approval_status: string(source.approval_status, `${field}.approval_status`),
    candidate: {
      id: string(candidate.id, `${field}.candidate.id`),
      digest: string(candidate.digest, `${field}.candidate.digest`),
    },
    profile: {
      id: string(profile.id, `${field}.profile.id`),
      version: string(profile.version, `${field}.profile.version`),
    },
    captured_at: string(source.captured_at, `${field}.captured_at`),
    report_digest: string(source.report_digest, `${field}.report_digest`),
  };
}

export function parseOverviewProjection(value: unknown): OverviewProjection {
  const source = object(value, "overview");
  if (source.schema_version !== "overview.v1") {
    throw new Error("unsupported overview schema");
  }
  const scope = object(source.scope, "overview.scope");
  const metrics = object(source.metrics, "overview.metrics");
  const decisions = object(source.decisions, "overview.decisions");
  if (scope.resource !== "verification-report-records") {
    throw new Error("unsupported overview resource scope");
  }
  if (!Array.isArray(source.recent_reports)) {
    throw new Error("overview.recent_reports must be an array");
  }
  return {
    schema_version: "overview.v1",
    scope: {
      resource: "verification-report-records",
      denominator: number(scope.denominator, "overview.scope.denominator"),
      deduplication_key: string(
        scope.deduplication_key,
        "overview.scope.deduplication_key",
      ),
    },
    as_of: nullableString(source.as_of, "overview.as_of"),
    metrics: {
      reports_evaluated: number(
        metrics.reports_evaluated,
        "overview.metrics.reports_evaluated",
      ),
      verified_reports: number(
        metrics.verified_reports,
        "overview.metrics.verified_reports",
      ),
      reports_missing_evidence: number(
        metrics.reports_missing_evidence,
        "overview.metrics.reports_missing_evidence",
      ),
      human_decisions_pending: number(
        metrics.human_decisions_pending,
        "overview.metrics.human_decisions_pending",
      ),
    },
    decisions: {
      accept: number(decisions.accept, "overview.decisions.accept"),
      review: number(decisions.review, "overview.decisions.review"),
      reject: number(decisions.reject, "overview.decisions.reject"),
      other: number(decisions.other, "overview.decisions.other"),
    },
    recent_reports: source.recent_reports.map((item, index) =>
      parseOverviewReportItem(item, `overview.recent_reports[${index}]`),
    ),
    limitations: strings(source.limitations, "overview.limitations"),
  };
}

function parseEvidenceReceipt(value: unknown, field: string): import("./dto").EvidenceReceiptDto {
  const receipt = object(value, field);
  return {
    receipt_id: string(receipt.receipt_id, `${field}.receipt_id`),
    receipt_digest: string(receipt.receipt_digest, `${field}.receipt_digest`),
    artifact_digest: string(receipt.artifact_digest, `${field}.artifact_digest`),
    captured_at: string(receipt.captured_at, `${field}.captured_at`),
    producer_id: string(receipt.producer_id, `${field}.producer_id`),
    run_id: nullableString(receipt.run_id, `${field}.run_id`),
  };
}

function parseHumanApprovalRevocationEvidence(
  value: unknown,
  field: string,
): HumanApprovalRevocationEvidence {
  const source = object(value, field);
  const contract = object(source.contract, `${field}.contract`);
  if (contract.schema_version !== "statewake.ai_contract.v1") {
    throw new Error("unsupported human approval revocation contract schema");
  }
  if (contract.contract_type !== "human_approval_revocation") {
    throw new Error("unsupported human approval revocation contract type");
  }
  return {
    contract: {
      schema_version: "statewake.ai_contract.v1",
      contract_type: "human_approval_revocation",
      contract_version: string(contract.contract_version, `${field}.contract.contract_version`),
      producer_id: string(contract.producer_id, `${field}.contract.producer_id`),
      run_id: string(contract.run_id, `${field}.contract.run_id`),
      actor_identity_ref: string(
        contract.actor_identity_ref,
        `${field}.contract.actor_identity_ref`,
      ),
      role: string(contract.role, `${field}.contract.role`),
      approval_action: string(contract.approval_action, `${field}.contract.approval_action`),
      approval_basis_digest: string(
        contract.approval_basis_digest,
        `${field}.contract.approval_basis_digest`,
      ),
      scope: string(contract.scope, `${field}.contract.scope`),
      target_approval_receipt_id: string(
        contract.target_approval_receipt_id,
        `${field}.contract.target_approval_receipt_id`,
      ),
      target_approval_receipt_digest: string(
        contract.target_approval_receipt_digest,
        `${field}.contract.target_approval_receipt_digest`,
      ),
      reason: string(contract.reason, `${field}.contract.reason`),
      captured_at: string(contract.captured_at, `${field}.contract.captured_at`),
      metadata: object(contract.metadata, `${field}.contract.metadata`),
    },
    receipt: parseEvidenceReceipt(source.receipt, `${field}.receipt`),
  };
}

function parseHumanApprovalEvidence(value: unknown, field: string): HumanApprovalEvidence {
  const source = object(value, field);
  const contract = object(source.contract, `${field}.contract`);
  if (contract.schema_version !== "statewake.ai_contract.v1") {
    throw new Error("unsupported human approval contract schema");
  }
  if (contract.contract_type !== "human_approval") {
    throw new Error("unsupported human approval contract type");
  }
  const metadata = object(contract.metadata, `${field}.contract.metadata`);
  const approval: HumanApprovalEvidence = {
    contract: {
      schema_version: "statewake.ai_contract.v1",
      contract_type: "human_approval",
      contract_version: string(contract.contract_version, `${field}.contract.contract_version`),
      producer_id: string(contract.producer_id, `${field}.contract.producer_id`),
      run_id: string(contract.run_id, `${field}.contract.run_id`),
      actor_identity_ref: string(
        contract.actor_identity_ref,
        `${field}.contract.actor_identity_ref`,
      ),
      role: string(contract.role, `${field}.contract.role`),
      approval_action: string(contract.approval_action, `${field}.contract.approval_action`),
      approval_basis_digest: string(
        contract.approval_basis_digest,
        `${field}.contract.approval_basis_digest`,
      ),
      scope: string(contract.scope, `${field}.contract.scope`),
      captured_at: string(contract.captured_at, `${field}.contract.captured_at`),
      metadata,
    },
    receipt: parseEvidenceReceipt(source.receipt, `${field}.receipt`),
  };
  if (source.lifecycle !== undefined) {
    const lifecycle = object(source.lifecycle, `${field}.lifecycle`);
    const status = string(lifecycle.status, `${field}.lifecycle.status`);
    if (!(["active", "revoked", "superseded"] as const).includes(status as never)) {
      throw new Error(`${field}.lifecycle.status is unsupported`);
    }
    let revocation: HumanApprovalRevocationEvidence | null = null;
    if (lifecycle.revocation !== null) {
      revocation = parseHumanApprovalRevocationEvidence(
        lifecycle.revocation,
        `${field}.lifecycle.revocation`,
      );
    }
    approval.lifecycle = {
      status: status as "active" | "revoked" | "superseded",
      superseded_by_receipt_id: nullableString(
        lifecycle.superseded_by_receipt_id,
        `${field}.lifecycle.superseded_by_receipt_id`,
      ),
      revocation,
    };
  }
  return approval;
}

export function parseHumanApprovalThread(value: unknown): HumanApprovalThread {
  const source = object(value, "human approval thread");
  if (source.schema_version !== "human-approval-thread.v1") {
    throw new Error("unsupported human approval thread schema");
  }
  const target = object(source.target, "human approval thread.target");
  const authority = object(source.authority, "human approval thread.authority");
  if (!Array.isArray(source.items)) {
    throw new Error("human approval thread.items must be an array");
  }
  const parsedItems = source.items.map((item, index) =>
    parseHumanApprovalEvidence(item, `human approval thread.items[${index}]`),
  );
  const activeApprovalReceiptIds = strings(
    source.active_approval_receipt_ids,
    "human approval thread.active_approval_receipt_ids",
  );
  const projectedActiveReceiptIds = parsedItems
    .filter((item) => item.lifecycle?.status === "active")
    .map((item) => item.receipt.receipt_id)
    .sort();
  if (activeApprovalReceiptIds.length !== new Set(activeApprovalReceiptIds).size) {
    throw new Error("human approval thread active approval identities must be unique");
  }
  if (
    [...activeApprovalReceiptIds].sort().join("|") !== projectedActiveReceiptIds.join("|")
  ) {
    throw new Error("human approval thread active approval identities disagree with lifecycle state");
  }
  return {
    schema_version: "human-approval-thread.v1",
    target: {
      record_id: string(target.record_id, "human approval thread.target.record_id"),
      candidate_identity: string(
        target.candidate_identity,
        "human approval thread.target.candidate_identity",
      ),
      candidate_digest: string(
        target.candidate_digest,
        "human approval thread.target.candidate_digest",
      ),
      report_digest: string(target.report_digest, "human approval thread.target.report_digest"),
      profile_id: string(target.profile_id, "human approval thread.target.profile_id"),
      profile_version: string(
        target.profile_version,
        "human approval thread.target.profile_version",
      ),
    },
    authority: {
      approval_action: string(
        authority.approval_action,
        "human approval thread.authority.approval_action",
      ),
      scope: string(authority.scope, "human approval thread.authority.scope"),
    },
    items: parsedItems,
    active_approval_receipt_ids: activeApprovalReceiptIds,
    limitations: strings(source.limitations, "human approval thread.limitations"),
  };
}

function parseApprovalEffects(
  value: unknown,
  field: string,
): HumanApprovalResult["effects"] {
  const effects = object(value, field);
  const parsedEffects = {
    verification_report_mutated: boolean(
      effects.verification_report_mutated,
      `${field}.verification_report_mutated`,
    ),
    machine_decision_changed: boolean(
      effects.machine_decision_changed,
      `${field}.machine_decision_changed`,
    ),
    release_published: boolean(effects.release_published, `${field}.release_published`),
    side_effect_authorized_outside_scope: boolean(
      effects.side_effect_authorized_outside_scope,
      `${field}.side_effect_authorized_outside_scope`,
    ),
  };
  if (Object.values(parsedEffects).some(Boolean)) {
    throw new Error("human approval endpoint must not mutate machine/report/publication state");
  }
  return {
    verification_report_mutated: false,
    machine_decision_changed: false,
    release_published: false,
    side_effect_authorized_outside_scope: false,
  };
}

export function parseHumanApprovalResult(value: unknown): HumanApprovalResult {
  const source = object(value, "human approval result");
  if (source.schema_version !== "human-approval-result.v1") {
    throw new Error("unsupported human approval result schema");
  }
  return {
    schema_version: "human-approval-result.v1",
    created: boolean(source.created, "human approval result.created"),
    approval: parseHumanApprovalEvidence(source.approval, "human approval result.approval"),
    effects: parseApprovalEffects(source.effects, "human approval result.effects"),
    limitations: strings(source.limitations, "human approval result.limitations"),
  };
}

export function parseHumanApprovalLifecycleResult(value: unknown): HumanApprovalLifecycleResult {
  const source = object(value, "human approval lifecycle result");
  if (source.schema_version !== "human-approval-lifecycle-result.v1") {
    throw new Error("unsupported human approval lifecycle result schema");
  }
  const operation = string(source.operation, "human approval lifecycle result.operation");
  if (operation !== "revoke" && operation !== "supersede") {
    throw new Error("unsupported human approval lifecycle operation");
  }
  const approval =
    source.approval === null
      ? null
      : parseHumanApprovalEvidence(source.approval, "human approval lifecycle result.approval");
  const revocation =
    source.revocation === null
      ? null
      : parseHumanApprovalRevocationEvidence(
          source.revocation,
          "human approval lifecycle result.revocation",
        );
  if ((operation === "revoke" && (revocation === null || approval !== null)) ||
      (operation === "supersede" && (approval === null || revocation !== null))) {
    throw new Error("human approval lifecycle result shape does not match operation");
  }
  return {
    schema_version: "human-approval-lifecycle-result.v1",
    operation,
    created: boolean(source.created, "human approval lifecycle result.created"),
    approval,
    revocation,
    effects: parseApprovalEffects(source.effects, "human approval lifecycle result.effects"),
    limitations: strings(source.limitations, "human approval lifecycle result.limitations"),
  };
}

function parseEvidenceTraceNode(value: unknown, field: string): EvidenceTraceNode {
  const source = object(value, field);
  return {
    node_id: string(source.node_id, `${field}.node_id`),
    kind: string(source.kind, `${field}.kind`),
    identity: string(source.identity, `${field}.identity`),
    label: string(source.label, `${field}.label`),
    digest: nullableString(source.digest, `${field}.digest`),
    digest_kind: nullableString(source.digest_kind, `${field}.digest_kind`),
    integrity_status: string(source.integrity_status, `${field}.integrity_status`),
    availability: string(source.availability, `${field}.availability`),
    record_id: nullableString(source.record_id, `${field}.record_id`),
    producer_id: nullableString(source.producer_id, `${field}.producer_id`),
    producer_type: nullableString(source.producer_type, `${field}.producer_type`),
    captured_at: nullableString(source.captured_at, `${field}.captured_at`),
    run_id: nullableString(source.run_id, `${field}.run_id`),
    source_event_id: nullableString(source.source_event_id, `${field}.source_event_id`),
    artifact_size: nullableNumber(source.artifact_size, `${field}.artifact_size`),
    receipt_digest: nullableString(source.receipt_digest, `${field}.receipt_digest`),
    receipt_integrity_status: nullableString(
      source.receipt_integrity_status,
      `${field}.receipt_integrity_status`,
    ),
    artifact_integrity_status: nullableString(
      source.artifact_integrity_status,
      `${field}.artifact_integrity_status`,
    ),
    admission_status: nullableString(source.admission_status, `${field}.admission_status`),
    admission_digest: nullableString(source.admission_digest, `${field}.admission_digest`),
    producer_authentication_status: nullableString(
      source.producer_authentication_status,
      `${field}.producer_authentication_status`,
    ),
  };
}

function parseEvidenceTraceEdge(value: unknown, field: string): EvidenceTraceEdge {
  const source = object(value, field);
  const occurrences = number(source.occurrences, `${field}.occurrences`);
  if (!Number.isInteger(occurrences) || occurrences < 1) {
    throw new Error(`${field}.occurrences must be a positive integer`);
  }
  return {
    edge_id: string(source.edge_id, `${field}.edge_id`),
    source: string(source.source, `${field}.source`),
    target: string(source.target, `${field}.target`),
    relationship_type: string(source.relationship_type, `${field}.relationship_type`),
    basis: string(source.basis, `${field}.basis`),
    occurrences,
  };
}

function parseEvidenceTraceUnresolved(
  value: unknown,
  field: string,
): EvidenceTraceUnresolved {
  const source = object(value, field);
  return {
    kind: string(source.kind, `${field}.kind`),
    identity: string(source.identity, `${field}.identity`),
    reason: string(source.reason, `${field}.reason`),
  };
}

export function parseEvidenceTrace(value: unknown): EvidenceTrace {
  const source = object(value, "evidence trace");
  if (source.schema_version !== "evidence-trace.v2") {
    throw new Error("unsupported evidence trace schema");
  }
  if (!Array.isArray(source.nodes)) {
    throw new Error("evidence trace.nodes must be an array");
  }
  if (!Array.isArray(source.edges)) {
    throw new Error("evidence trace.edges must be an array");
  }
  if (!Array.isArray(source.unresolved)) {
    throw new Error("evidence trace.unresolved must be an array");
  }
  const candidate = object(source.candidate, "evidence trace.candidate");
  const workspaceScan = object(source.workspace_scan, "evidence trace.workspace_scan");
  const assuranceSummary = object(
    source.assurance_summary,
    "evidence trace.assurance_summary",
  );
  const producerAuthentication = object(
    source.producer_authentication,
    "evidence trace.producer_authentication",
  );
  const nodes = source.nodes.map((item, index) =>
    parseEvidenceTraceNode(item, `evidence trace.nodes[${index}]`),
  );
  const nodeIds = new Set(nodes.map((node) => node.node_id));
  if (nodeIds.size !== nodes.length) {
    throw new Error("evidence trace node identities must be unique");
  }
  const edges = source.edges.map((item, index) =>
    parseEvidenceTraceEdge(item, `evidence trace.edges[${index}]`),
  );
  for (const edge of edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      throw new Error("evidence trace edge references an unknown node");
    }
  }
  const recordsScanned = number(
    workspaceScan.records_scanned,
    "evidence trace.workspace_scan.records_scanned",
  );
  const recordsAvailable = number(
    workspaceScan.records_available,
    "evidence trace.workspace_scan.records_available",
  );
  if (
    !Number.isInteger(recordsScanned) ||
    !Number.isInteger(recordsAvailable) ||
    recordsScanned < 0 ||
    recordsAvailable < 0 ||
    recordsScanned > recordsAvailable
  ) {
    throw new Error("evidence trace workspace scan counts are inconsistent");
  }

  const receiptsResolved = number(
    assuranceSummary.receipts_resolved,
    "evidence trace.assurance_summary.receipts_resolved",
  );
  const receiptIntegrityVerified = number(
    assuranceSummary.receipt_integrity_verified,
    "evidence trace.assurance_summary.receipt_integrity_verified",
  );
  const artifactIntegrityVerified = number(
    assuranceSummary.artifact_integrity_verified,
    "evidence trace.assurance_summary.artifact_integrity_verified",
  );
  const admissionVerified = number(
    assuranceSummary.admission_verified,
    "evidence trace.assurance_summary.admission_verified",
  );
  for (const [name, value] of [
    ["receipts_resolved", receiptsResolved],
    ["receipt_integrity_verified", receiptIntegrityVerified],
    ["artifact_integrity_verified", artifactIntegrityVerified],
    ["admission_verified", admissionVerified],
  ] as const) {
    if (!Number.isInteger(value) || value < 0) {
      throw new Error(`evidence trace assurance count ${name} must be a non-negative integer`);
    }
  }
  if (
    receiptIntegrityVerified > receiptsResolved ||
    artifactIntegrityVerified > receiptsResolved ||
    admissionVerified > receiptsResolved
  ) {
    throw new Error("evidence trace assurance counts exceed resolved receipts");
  }
  const workspaceRecords = nodes.filter((node) => node.kind === "workspace-record");
  if (workspaceRecords.length !== receiptsResolved) {
    throw new Error("evidence trace resolved receipt count does not match workspace records");
  }
  for (const node of workspaceRecords) {
    if (node.receipt_digest === null || node.receipt_integrity_status === null) {
      throw new Error("workspace evidence receipt must expose receipt integrity");
    }
    if (!/^[0-9a-f]{64}$/.test(node.receipt_digest)) {
      throw new Error("workspace evidence receipt digest must be lowercase SHA-256 hex");
    }
    if (node.receipt_integrity_status !== "verified") {
      throw new Error("parsed workspace receipts must have verified receipt integrity");
    }
    if (
      node.artifact_integrity_status !== "verified" &&
      node.artifact_integrity_status !== "invalid" &&
      node.artifact_integrity_status !== "unavailable"
    ) {
      throw new Error("workspace artifact integrity status is unsupported");
    }
    if (
      node.admission_status !== "verified" &&
      node.admission_status !== "invalid" &&
      node.admission_status !== "unavailable"
    ) {
      throw new Error("workspace evidence admission status is unsupported");
    }
    if (node.artifact_integrity_status === null || node.admission_status === null) {
      throw new Error("workspace evidence receipt must expose artifact and admission status");
    }
    if (node.producer_authentication_status !== "not-recorded") {
      throw new Error("producer authentication must remain not-recorded without persisted proof");
    }
    if (node.admission_status === "verified" && node.admission_digest === null) {
      throw new Error("verified evidence admission must include its deterministic digest");
    }
    if (
      node.admission_status === "verified" &&
      (node.receipt_integrity_status !== "verified" ||
        node.artifact_integrity_status !== "verified")
    ) {
      throw new Error("verified evidence admission requires verified receipt and artifact integrity");
    }
  }
  if (
    workspaceRecords.filter((node) => node.receipt_integrity_status === "verified").length !==
      receiptIntegrityVerified ||
    workspaceRecords.filter((node) => node.artifact_integrity_status === "verified").length !==
      artifactIntegrityVerified ||
    workspaceRecords.filter((node) => node.admission_status === "verified").length !==
      admissionVerified
  ) {
    throw new Error("evidence trace assurance summary does not match receipt nodes");
  }
  if (producerAuthentication.status !== "not-recorded") {
    throw new Error("producer authentication cannot be promoted without persisted proof");
  }
  if (producerAuthentication.authenticated !== null) {
    throw new Error("producer authentication authenticated must be null when not recorded");
  }
  return {
    schema_version: "evidence-trace.v2",
    report_record_id: string(source.report_record_id, "evidence trace.report_record_id"),
    report_digest: string(source.report_digest, "evidence trace.report_digest"),
    candidate: {
      id: string(candidate.id, "evidence trace.candidate.id"),
      digest: string(candidate.digest, "evidence trace.candidate.digest"),
    },
    nodes,
    edges,
    unresolved: source.unresolved.map((item, index) =>
      parseEvidenceTraceUnresolved(item, `evidence trace.unresolved[${index}]`),
    ),
    workspace_scan: {
      records_scanned: recordsScanned,
      records_available: recordsAvailable,
      complete: boolean(workspaceScan.complete, "evidence trace.workspace_scan.complete"),
    },
    assurance_summary: {
      receipts_resolved: receiptsResolved,
      receipt_integrity_verified: receiptIntegrityVerified,
      artifact_integrity_verified: artifactIntegrityVerified,
      admission_verified: admissionVerified,
    },
    producer_authentication: {
      status: "not-recorded",
      authenticated: null,
      reason: string(
        producerAuthentication.reason,
        "evidence trace.producer_authentication.reason",
      ),
    },
    limitations: strings(source.limitations, "evidence trace.limitations"),
  };
}

function nullableBoolean(value: unknown, field: string): boolean | null {
  if (value === null) return null;
  return boolean(value, field);
}

function stringRecord(value: unknown, field: string): Record<string, string> {
  const source = object(value, field);
  return Object.fromEntries(
    Object.entries(source).map(([key, item]) => [key, string(item, `${field}.${key}`)]),
  );
}

function objectArray(value: unknown, field: string): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array`);
  return value.map((item, index) => object(item, `${field}[${index}]`));
}

export function parseDecisionLineage(value: unknown): DecisionLineageView {
  const source = object(value, "decision lineage investigation");
  if (source.schema_version !== "decision-lineage-investigation.v1") {
    throw new Error("unsupported decision lineage investigation schema");
  }
  const chain = object(source.chain, "decision lineage investigation.chain");
  const basis = object(source.decision_basis, "decision lineage investigation.decision_basis");
  const comparison = object(source.comparison, "decision lineage investigation.comparison");
  const reconciliation = object(source.reconciliation, "decision lineage investigation.reconciliation");
  const recovery = object(source.recovery, "decision lineage investigation.recovery");
  const lineage = object(source.lineage, "decision lineage investigation.lineage");
  const verification = object(source.verification, "decision lineage investigation.verification");
  const authorization = object(source.authorization, "decision lineage investigation.authorization");

  if (chain.rationale_exposed !== false) {
    throw new Error("decision lineage investigation must not expose chain rationale");
  }
  if (lineage.verified !== true || lineage.run_role !== "run") {
    throw new Error("decision lineage investigation requires verified run-rooted lineage");
  }
  if (verification.evidence_chain_verified !== true || verification.lineage_closure_verified !== true) {
    throw new Error("decision lineage investigation requires verified chain and lineage closure");
  }
  if (
    authorization.business_authorization_evaluated !== false ||
    authorization.human_approval_evaluated !== false ||
    authorization.publication_authorized !== false
  ) {
    throw new Error("decision lineage investigation must not infer authorization");
  }
  if (!Array.isArray(source.decision_inputs)) {
    throw new Error("decision lineage investigation.decision_inputs must be an array");
  }
  const decisionInputs = source.decision_inputs.map((item, index) => {
    const row = object(item, `decision lineage investigation.decision_inputs[${index}]`);
    const classification = string(row.classification, `decision lineage investigation.decision_inputs[${index}].classification`);
    if (classification !== "lineage-bound" && classification !== "verification-context") {
      throw new Error("unsupported decision input classification");
    }
    const reachable = row.reachable_to_run === null ? null : boolean(row.reachable_to_run, `decision lineage investigation.decision_inputs[${index}].reachable_to_run`);
    if (classification === "lineage-bound" && reachable !== true) {
      throw new Error("lineage-bound decision input must be reachable to run");
    }
    if (classification === "verification-context" && reachable !== null) {
      throw new Error("verification-context decision input must not invent graph reachability");
    }
    return {
      digest: string(row.digest, `decision lineage investigation.decision_inputs[${index}].digest`),
      semantic_roles: strings(row.semantic_roles, `decision lineage investigation.decision_inputs[${index}].semantic_roles`),
      classification,
      lineage_roles: strings(row.lineage_roles, `decision lineage investigation.decision_inputs[${index}].lineage_roles`),
      reachable_to_run: reachable,
    } as DecisionLineageView["decision_inputs"][number];
  });

  let parsedBasis: DecisionLineageView["decision_basis"] = { present: false };
  if (basis.present !== false) {
    if (basis.present !== true || basis.rationale_exposed !== false) {
      throw new Error("decision basis presence/rationale contract is invalid");
    }
    parsedBasis = {
      present: true,
      basis_type: string(basis.basis_type, "decision lineage investigation.decision_basis.basis_type"),
      basis_id: string(basis.basis_id, "decision lineage investigation.decision_basis.basis_id"),
      version: string(basis.version, "decision lineage investigation.decision_basis.version"),
      digest: string(basis.digest, "decision lineage investigation.decision_basis.digest"),
      decision: string(basis.decision, "decision lineage investigation.decision_basis.decision"),
      reliability_state: string(basis.reliability_state, "decision lineage investigation.decision_basis.reliability_state"),
      input_count: number(basis.input_count, "decision lineage investigation.decision_basis.input_count"),
      policy_id: nullableString(basis.policy_id, "decision lineage investigation.decision_basis.policy_id"),
      policy_version: nullableString(basis.policy_version, "decision lineage investigation.decision_basis.policy_version"),
      policy_digest: nullableString(basis.policy_digest, "decision lineage investigation.decision_basis.policy_digest"),
      rationale_count: number(basis.rationale_count, "decision lineage investigation.decision_basis.rationale_count"),
      rationale_exposed: false,
    };
  }
  if (parsedBasis.present && parsedBasis.input_count !== decisionInputs.length) {
    throw new Error("decision basis input count does not match decision input projection");
  }

  const parseComparisonInput = (raw: unknown, field: string) => {
    if (!Array.isArray(raw)) throw new Error(`${field} must be an array`);
    return raw.map((item, index) => {
      const row = object(item, `${field}[${index}]`);
      if ("source" in row || "path" in row) {
        throw new Error("decision lineage comparison inputs must not expose source paths");
      }
      return {
        role: string(row.role, `${field}[${index}].role`),
        kind: string(row.kind, `${field}[${index}].kind`),
        identity: string(row.identity, `${field}[${index}].identity`),
        digest: string(row.digest, `${field}[${index}].digest`),
      };
    });
  };
  let parsedComparison: DecisionLineageView["comparison"] = { present: false };
  if (comparison.present !== false) {
    if (comparison.present !== true) throw new Error("comparison presence contract is invalid");
    parsedComparison = {
      present: true,
      comparison_id: string(comparison.comparison_id, "decision lineage investigation.comparison.comparison_id"),
      digest: string(comparison.digest, "decision lineage investigation.comparison.digest"),
      significance: string(comparison.significance, "decision lineage investigation.comparison.significance"),
      discrepancies: strings(comparison.discrepancies, "decision lineage investigation.comparison.discrepancies"),
      before_inputs: parseComparisonInput(comparison.before_inputs, "decision lineage investigation.comparison.before_inputs"),
      after_inputs: parseComparisonInput(comparison.after_inputs, "decision lineage investigation.comparison.after_inputs"),
    };
  }

  let parsedReconciliation: DecisionLineageView["reconciliation"] = { present: false };
  if (reconciliation.present !== false) {
    if (reconciliation.present !== true) throw new Error("reconciliation presence contract is invalid");
    parsedReconciliation = {
      present: true,
      binding_digest: string(reconciliation.binding_digest, "decision lineage investigation.reconciliation.binding_digest"),
      comparison_id: string(reconciliation.comparison_id, "decision lineage investigation.reconciliation.comparison_id"),
      comparison_digest: string(reconciliation.comparison_digest, "decision lineage investigation.reconciliation.comparison_digest"),
      reconciliation_id: string(reconciliation.reconciliation_id, "decision lineage investigation.reconciliation.reconciliation_id"),
      reconciliation_digest: string(reconciliation.reconciliation_digest, "decision lineage investigation.reconciliation.reconciliation_digest"),
      reconciliation_status: string(reconciliation.reconciliation_status, "decision lineage investigation.reconciliation.reconciliation_status"),
      resolved_discrepancies: strings(reconciliation.resolved_discrepancies, "decision lineage investigation.reconciliation.resolved_discrepancies"),
      resolution: string(reconciliation.resolution, "decision lineage investigation.reconciliation.resolution"),
    };
  }

  let parsedRecovery: DecisionLineageView["recovery"] = { present: false };
  if (recovery.present !== false) {
    if (recovery.present !== true || recovery.outcome !== "recovered") {
      throw new Error("recovery presence/outcome contract is invalid");
    }
    parsedRecovery = {
      present: true,
      digest: string(recovery.digest, "decision lineage investigation.recovery.digest"),
      recovery_id: string(recovery.recovery_id, "decision lineage investigation.recovery.recovery_id"),
      recovery_digest: string(recovery.recovery_digest, "decision lineage investigation.recovery.recovery_digest"),
      recovery_status: string(recovery.recovery_status, "decision lineage investigation.recovery.recovery_status"),
      source_reconciliation_id: string(recovery.source_reconciliation_id, "decision lineage investigation.recovery.source_reconciliation_id"),
      reconciliation_id: string(recovery.reconciliation_id, "decision lineage investigation.recovery.reconciliation_id"),
      reconciliation_digest: string(recovery.reconciliation_digest, "decision lineage investigation.recovery.reconciliation_digest"),
      reconciliation_status: string(recovery.reconciliation_status, "decision lineage investigation.recovery.reconciliation_status"),
      outcome: "recovered",
    };
  }

  if (!Array.isArray(lineage.bindings)) throw new Error("decision lineage investigation.lineage.bindings must be an array");
  const bindings = lineage.bindings.map((item, index) => {
    const row = object(item, `decision lineage investigation.lineage.bindings[${index}]`);
    if (row.reachable_to_run !== true) throw new Error("every lineage binding must reach the declared run");
    return {
      role: string(row.role, `decision lineage investigation.lineage.bindings[${index}].role`),
      node_id: string(row.node_id, `decision lineage investigation.lineage.bindings[${index}].node_id`),
      identity: string(row.identity, `decision lineage investigation.lineage.bindings[${index}].identity`),
      digest: string(row.digest, `decision lineage investigation.lineage.bindings[${index}].digest`),
      reachable_to_run: true as const,
    };
  });

  return {
    schema_version: "decision-lineage-investigation.v1",
    chain: {
      chain_id: string(chain.chain_id, "decision lineage investigation.chain.chain_id"),
      digest: string(chain.digest, "decision lineage investigation.chain.digest"),
      verification_status: string(chain.verification_status, "decision lineage investigation.chain.verification_status"),
      reliability_state: string(chain.reliability_state, "decision lineage investigation.chain.reliability_state"),
      reconciliation_state: string(chain.reconciliation_state, "decision lineage investigation.chain.reconciliation_state"),
      decision: string(chain.decision, "decision lineage investigation.chain.decision"),
      evidence_count: number(chain.evidence_count, "decision lineage investigation.chain.evidence_count"),
      rationale_count: number(chain.rationale_count, "decision lineage investigation.chain.rationale_count"),
      rationale_exposed: false,
    },
    decision_basis: parsedBasis,
    decision_inputs: decisionInputs,
    comparison: parsedComparison,
    reconciliation: parsedReconciliation,
    recovery: parsedRecovery,
    lineage: {
      verified: true,
      provenance_graph_digest: string(lineage.provenance_graph_digest, "decision lineage investigation.lineage.provenance_graph_digest"),
      closure_digest: string(lineage.closure_digest, "decision lineage investigation.lineage.closure_digest"),
      run_role: "run",
      reachable_roles: strings(lineage.reachable_roles, "decision lineage investigation.lineage.reachable_roles"),
      bindings,
    },
    verification: {
      evidence_chain_verified: true,
      decision_basis_verified: boolean(verification.decision_basis_verified, "decision lineage investigation.verification.decision_basis_verified"),
      comparison_verified: boolean(verification.comparison_verified, "decision lineage investigation.verification.comparison_verified"),
      reconciliation_binding_verified: boolean(verification.reconciliation_binding_verified, "decision lineage investigation.verification.reconciliation_binding_verified"),
      recovery_outcome_verified: boolean(verification.recovery_outcome_verified, "decision lineage investigation.verification.recovery_outcome_verified"),
      lineage_closure_verified: true,
    },
    authorization: {
      business_authorization_evaluated: false,
      human_approval_evaluated: false,
      publication_authorized: false,
    },
    limitations: strings(source.limitations, "decision lineage investigation.limitations"),
  };
}

export function parseReliabilityProofInvestigation(
  value: unknown,
): ReliabilityProofInvestigationView {
  const source = object(value, "reliability proof investigation");
  if (source.schema_version !== "proof-bundle-investigation.v1") {
    throw new Error("unsupported reliability proof investigation schema");
  }
  const bundle = object(source.bundle, "reliability proof investigation.bundle");
  const proof = object(source.proof, "reliability proof investigation.proof");
  const verification = object(source.verification, "reliability proof investigation.verification");
  const lineage = object(source.lineage, "reliability proof investigation.lineage");
  const completeness = object(source.completeness, "reliability proof investigation.completeness");
  const trust = object(source.trust_context, "reliability proof investigation.trust_context");
  const dataset = object(source.portable_dataset_boundary, "reliability proof investigation.portable_dataset_boundary");
  const authorization = object(source.authorization, "reliability proof investigation.authorization");

  if (proof.bundle_type !== "reliability-proof") {
    throw new Error("reliability proof investigation must describe a reliability proof");
  }
  if (verification.verified !== true || verification.offline_reverification_succeeded !== true || verification.source_set_complete !== true) {
    throw new Error("reliability proof investigation requires successful offline verification");
  }
  if (trust.external_authority_trust_established !== false) {
    throw new Error("reliability proof investigation must not infer external authority trust");
  }
  if (dataset.this_is_reliability_proof !== true || dataset.workspace_portable_dataset_is_distinct !== true) {
    throw new Error("reliability proof investigation must preserve the dataset/proof boundary");
  }
  if (authorization.human_approval_evaluated !== false || authorization.publication_authorized !== false || authorization.release_authorized !== false) {
    throw new Error("reliability proof investigation must not authorize human/release actions");
  }
  if (!Array.isArray(source.sources)) throw new Error("reliability proof investigation.sources must be an array");
  if (!Array.isArray(source.artifacts)) throw new Error("reliability proof investigation.artifacts must be an array");
  const sources = source.sources.map((item, index) => {
    const row = object(item, `reliability proof investigation.sources[${index}]`);
    return {
      reference_key: string(row.reference_key, `reliability proof investigation.sources[${index}].reference_key`),
      source_label: string(row.source_label, `reliability proof investigation.sources[${index}].source_label`),
      artifact_id: string(row.artifact_id, `reliability proof investigation.sources[${index}].artifact_id`),
      packaged_digest: string(row.packaged_digest, `reliability proof investigation.sources[${index}].packaged_digest`),
      bound_digest: string(row.bound_digest, `reliability proof investigation.sources[${index}].bound_digest`),
    };
  });
  const artifacts = source.artifacts.map((item, index) => {
    const row = object(item, `reliability proof investigation.artifacts[${index}]`);
    if ("path" in row || "content" in row) {
      throw new Error("reliability proof investigation must not expose artifact paths or content");
    }
    return {
      artifact_id: string(row.artifact_id, `reliability proof investigation.artifacts[${index}].artifact_id`),
      kind: string(row.kind, `reliability proof investigation.artifacts[${index}].kind`),
      sha256: string(row.sha256, `reliability proof investigation.artifacts[${index}].sha256`),
      size_bytes: number(row.size_bytes, `reliability proof investigation.artifacts[${index}].size_bytes`),
      sensitivity: string(row.sensitivity, `reliability proof investigation.artifacts[${index}].sensitivity`),
      derived_from: strings(row.derived_from, `reliability proof investigation.artifacts[${index}].derived_from`),
    };
  });
  const crypto = source.cryptographic_profile === null ? null : object(source.cryptographic_profile, "reliability proof investigation.cryptographic_profile");
  return {
    schema_version: "proof-bundle-investigation.v1",
    bundle: {
      bundle_id: string(bundle.bundle_id, "reliability proof investigation.bundle.bundle_id"),
      manifest_id: string(bundle.manifest_id, "reliability proof investigation.bundle.manifest_id"),
      engine_version: string(bundle.engine_version, "reliability proof investigation.bundle.engine_version"),
      created_at: string(bundle.created_at, "reliability proof investigation.bundle.created_at"),
      artifact_count: number(bundle.artifact_count, "reliability proof investigation.bundle.artifact_count"),
    },
    proof: {
      format_version: string(proof.format_version, "reliability proof investigation.proof.format_version"),
      bundle_type: "reliability-proof",
      descriptor_digest: string(proof.descriptor_digest, "reliability proof investigation.proof.descriptor_digest"),
      subject_id: string(proof.subject_id, "reliability proof investigation.proof.subject_id"),
      attestation_id: string(proof.attestation_id, "reliability proof investigation.proof.attestation_id"),
      attestation_digest: string(proof.attestation_digest, "reliability proof investigation.proof.attestation_digest"),
      evidence_chain_id: string(proof.evidence_chain_id, "reliability proof investigation.proof.evidence_chain_id"),
      evidence_chain_digest: string(proof.evidence_chain_digest, "reliability proof investigation.proof.evidence_chain_digest"),
      transition_id: string(proof.transition_id, "reliability proof investigation.proof.transition_id"),
      transition_digest: string(proof.transition_digest, "reliability proof investigation.proof.transition_digest"),
      reliability_state: string(proof.reliability_state, "reliability proof investigation.proof.reliability_state"),
      decision: string(proof.decision, "reliability proof investigation.proof.decision"),
      verification_report_digest: string(proof.verification_report_digest, "reliability proof investigation.proof.verification_report_digest"),
    },
    verification: {
      verified: true,
      checks: strings(verification.checks, "reliability proof investigation.verification.checks"),
      failures: strings(verification.failures, "reliability proof investigation.verification.failures"),
      offline_reverification_succeeded: true,
      source_set_complete: true,
    },
    lineage: {
      required_by_format: boolean(lineage.required_by_format, "reliability proof investigation.lineage.required_by_format"),
      present: boolean(lineage.present, "reliability proof investigation.lineage.present"),
      status: string(lineage.status, "reliability proof investigation.lineage.status"),
      digest: nullableString(lineage.digest, "reliability proof investigation.lineage.digest"),
    },
    completeness: {
      required_by_format: boolean(completeness.required_by_format, "reliability proof investigation.completeness.required_by_format"),
      present: boolean(completeness.present, "reliability proof investigation.completeness.present"),
      status: string(completeness.status, "reliability proof investigation.completeness.status"),
      artifact_id: nullableString(completeness.artifact_id, "reliability proof investigation.completeness.artifact_id"),
      digest: nullableString(completeness.digest, "reliability proof investigation.completeness.digest"),
    },
    trust_context: {
      present: boolean(trust.present, "reliability proof investigation.trust_context.present"),
      portable_cryptographic_consistency_verified: boolean(trust.portable_cryptographic_consistency_verified, "reliability proof investigation.trust_context.portable_cryptographic_consistency_verified"),
      external_authority_trust_established: false,
      signing_key_id: nullableString(trust.signing_key_id, "reliability proof investigation.trust_context.signing_key_id"),
      signing_key_digest: nullableString(trust.signing_key_digest, "reliability proof investigation.trust_context.signing_key_digest"),
      trust_state_version: trust.trust_state_version === null ? null : number(trust.trust_state_version, "reliability proof investigation.trust_context.trust_state_version"),
      trust_state_digest: nullableString(trust.trust_state_digest, "reliability proof investigation.trust_context.trust_state_digest"),
      authority_key_id: nullableString(trust.authority_key_id, "reliability proof investigation.trust_context.authority_key_id"),
      authority_key_digest: nullableString(trust.authority_key_digest, "reliability proof investigation.trust_context.authority_key_digest"),
    },
    cryptographic_profile: crypto,
    sources,
    artifacts,
    portable_dataset_boundary: {
      this_is_reliability_proof: true,
      workspace_portable_dataset_is_distinct: true,
      note: string(dataset.note, "reliability proof investigation.portable_dataset_boundary.note"),
    },
    authorization: {
      human_approval_evaluated: false,
      publication_authorized: false,
      release_authorized: false,
    },
    limitations: strings(source.limitations, "reliability proof investigation.limitations"),
  };
}

export function parseReleaseTrustView(value: unknown): ReleaseTrustView {
  const source = object(value, "release trust");
  if (source.schema_version !== "release-trust-view.v1") {
    throw new Error("unsupported release trust view schema");
  }
  const sourceIdentity = object(source.source, "release trust.source");
  const build = object(source.build, "release trust.build");
  const external = object(source.external_evidence, "release trust.external_evidence");
  const profile = object(source.structural_profile, "release trust.structural_profile");
  const content = object(source.content_verification, "release trust.content_verification");
  const signature = object(source.signature_authenticity, "release trust.signature_authenticity");
  const human = object(source.human_decision, "release trust.human_decision");
  const publication = object(source.publication_authorization, "release trust.publication_authorization");
  const publicationAuthorized = boolean(source.publication_authorized, "release trust.publication_authorized");
  const publicationConfigured = boolean(publication.configured, "release trust.publication_authorization.configured");
  const publicationState = boolean(publication.publication_authorized, "release trust.publication_authorization.publication_authorized");
  const releasePublished = boolean(source.release_published, "release trust.release_published");
  const registryPublication = object(source.registry_publication, "release trust.registry_publication");
  if (publicationAuthorized !== publicationState) {
    throw new Error("release trust publication authorization projections disagree");
  }
  if (!Array.isArray(publication.items)) {
    throw new Error("release trust.publication_authorization.items must be an array");
  }
  const publicationItems = publication.items.map((raw, index) => {
    const item = object(raw, `release trust.publication_authorization.items[${index}]`);
    const status = string(item.status, `release trust.publication_authorization.items[${index}].status`);
    if (status !== "active" && status !== "revoked" && status !== "superseded") {
      throw new Error("release trust publication authorization item has unsupported status");
    }
    return {
      status,
      approval_receipt_id: string(item.approval_receipt_id, `release trust.publication_authorization.items[${index}].approval_receipt_id`),
      actor_identity_ref: string(item.actor_identity_ref, `release trust.publication_authorization.items[${index}].actor_identity_ref`),
      role: string(item.role, `release trust.publication_authorization.items[${index}].role`),
      captured_at: string(item.captured_at, `release trust.publication_authorization.items[${index}].captured_at`),
      superseded_by_receipt_id: nullableString(item.superseded_by_receipt_id, `release trust.publication_authorization.items[${index}].superseded_by_receipt_id`),
      revocation_receipt_id: nullableString(item.revocation_receipt_id, `release trust.publication_authorization.items[${index}].revocation_receipt_id`),
    } as const;
  });
  const activeApprovalIds = strings(publication.active_approval_receipt_ids, "release trust.publication_authorization.active_approval_receipt_ids");
  const projectedActiveIds = publicationItems.filter((item) => item.status === "active").map((item) => item.approval_receipt_id).sort();
  if (JSON.stringify([...activeApprovalIds].sort()) !== JSON.stringify(projectedActiveIds)) {
    throw new Error("release trust publication active approval projection disagrees with lifecycle");
  }
  if (publicationState !== (projectedActiveIds.length > 0)) {
    throw new Error("release trust publication authorization state disagrees with lifecycle");
  }
  if (!publicationConfigured && (publicationState || publicationItems.length || activeApprovalIds.length)) {
    throw new Error("release trust unconfigured publication authority cannot contain active lifecycle state");
  }
  if (!Array.isArray(source.artifacts)) throw new Error("release trust.artifacts must be an array");
  const artifacts = source.artifacts.map((item, index) => {
    const artifact = object(item, `release trust.artifacts[${index}]`);
    return {
      name: string(artifact.name, `release trust.artifacts[${index}].name`),
      sha256: string(artifact.sha256, `release trust.artifacts[${index}].sha256`),
      size_bytes: number(artifact.size_bytes, `release trust.artifacts[${index}].size_bytes`),
      media_type: string(artifact.media_type, `release trust.artifacts[${index}].media_type`),
    };
  });
  const registryConfigured = boolean(registryPublication.configured, "release trust.registry_publication.configured");
  const registryPublished = boolean(registryPublication.release_published, "release trust.registry_publication.release_published");
  const registryReconciled = boolean(registryPublication.registry_reconciled, "release trust.registry_publication.registry_reconciled");
  const publicBytesVerified = boolean(registryPublication.public_bytes_verified, "release trust.registry_publication.public_bytes_verified");
  if (releasePublished !== registryPublished) {
    throw new Error("release trust registry publication projections disagree");
  }
  const registryArtifactsRaw = registryPublication.artifacts;
  if (!Array.isArray(registryArtifactsRaw)) {
    throw new Error("release trust.registry_publication.artifacts must be an array");
  }
  const registryArtifacts = registryArtifactsRaw.map((raw, index) => {
    const item = object(raw, `release trust.registry_publication.artifacts[${index}]`);
    const publicBytes = boolean(item.public_bytes_verified, `release trust.registry_publication.artifacts[${index}].public_bytes_verified`);
    const yanked = boolean(item.yanked, `release trust.registry_publication.artifacts[${index}].yanked`);
    if (!publicBytes) throw new Error("release trust registry artifact must have verified public bytes");
    if (yanked) throw new Error("release trust initial registry receipt cannot be yanked");
    return {
      name: string(item.name, `release trust.registry_publication.artifacts[${index}].name`),
      sha256: string(item.sha256, `release trust.registry_publication.artifacts[${index}].sha256`),
      size_bytes: number(item.size_bytes, `release trust.registry_publication.artifacts[${index}].size_bytes`),
      url: string(item.url, `release trust.registry_publication.artifacts[${index}].url`),
      package_type: string(item.package_type, `release trust.registry_publication.artifacts[${index}].package_type`),
      upload_time: nullableString(item.upload_time, `release trust.registry_publication.artifacts[${index}].upload_time`),
      yanked,
      yanked_reason: nullableString(item.yanked_reason ?? null, `release trust.registry_publication.artifacts[${index}].yanked_reason`),
      public_bytes_verified: publicBytes,
    };
  });
  const registryLifecycle = object(registryPublication.lifecycle, "release trust.registry_publication.lifecycle");
  const lifecycleConfigured = boolean(registryLifecycle.configured, "release trust.registry_publication.lifecycle.configured");
  const lifecycleStatusRaw = registryLifecycle.current_status;
  let lifecycleCurrentStatus: "available" | "yanked" | "partially_available" | "unavailable" | null = null;
  if (lifecycleStatusRaw !== null) {
    const status = string(lifecycleStatusRaw, "release trust.registry_publication.lifecycle.current_status");
    if (status !== "available" && status !== "yanked" && status !== "partially_available" && status !== "unavailable") {
      throw new Error("release trust registry lifecycle has unsupported current status");
    }
    lifecycleCurrentStatus = status;
  }
  const lifecycleCurrentObservedAt = nullableString(registryLifecycle.current_observed_at, "release trust.registry_publication.lifecycle.current_observed_at");
  const lifecycleObservationCount = number(registryLifecycle.observation_count, "release trust.registry_publication.lifecycle.observation_count");
  const lifecycleRegistryEntryPresent = nullableBoolean(registryLifecycle.registry_entry_present, "release trust.registry_publication.lifecycle.registry_entry_present");
  const lifecycleDefaultInstallEligible = nullableBoolean(registryLifecycle.default_install_eligible, "release trust.registry_publication.lifecycle.default_install_eligible");
  const lifecyclePublicBytesVerified = nullableBoolean(registryLifecycle.public_bytes_verified, "release trust.registry_publication.lifecycle.public_bytes_verified");
  const lifecycleMissingArtifacts = strings(registryLifecycle.missing_artifacts, "release trust.registry_publication.lifecycle.missing_artifacts");
  if (!Array.isArray(registryLifecycle.observations)) {
    throw new Error("release trust.registry_publication.lifecycle.observations must be an array");
  }
  const expectedArtifactMap = new Map(artifacts.map((item) => [item.name, `${item.sha256}:${item.size_bytes}`]));
  const lifecycleObservations = registryLifecycle.observations.map((raw, index) => {
    const observation = object(raw, `release trust.registry_publication.lifecycle.observations[${index}]`);
    const statusRaw = string(observation.status, `release trust.registry_publication.lifecycle.observations[${index}].status`);
    if (statusRaw !== "available" && statusRaw !== "yanked" && statusRaw !== "partially_available" && statusRaw !== "unavailable") {
      throw new Error("release trust registry lifecycle observation has unsupported status");
    }
    const status: "available" | "yanked" | "partially_available" | "unavailable" = statusRaw;
    const registryEntryPresent = boolean(observation.registry_entry_present, `release trust.registry_publication.lifecycle.observations[${index}].registry_entry_present`);
    const defaultInstallEligible = boolean(observation.default_install_eligible, `release trust.registry_publication.lifecycle.observations[${index}].default_install_eligible`);
    const observationPublicBytes = boolean(observation.public_bytes_verified, `release trust.registry_publication.lifecycle.observations[${index}].public_bytes_verified`);
    const missingArtifacts = strings(observation.missing_artifacts, `release trust.registry_publication.lifecycle.observations[${index}].missing_artifacts`);
    const unavailableReason = nullableString(observation.unavailable_reason, `release trust.registry_publication.lifecycle.observations[${index}].unavailable_reason`);
    if (!Array.isArray(observation.artifacts)) {
      throw new Error("release trust registry lifecycle observation artifacts must be an array");
    }
    const observationArtifacts = observation.artifacts.map((artifactRaw, artifactIndex) => {
      const item = object(artifactRaw, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}]`);
      return {
        name: string(item.name, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].name`),
        sha256: string(item.sha256, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].sha256`),
        size_bytes: number(item.size_bytes, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].size_bytes`),
        url: string(item.url, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].url`),
        package_type: string(item.package_type, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].package_type`),
        upload_time: nullableString(item.upload_time, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].upload_time`),
        yanked: boolean(item.yanked, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].yanked`),
        yanked_reason: nullableString(item.yanked_reason ?? null, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].yanked_reason`),
        public_bytes_verified: boolean(item.public_bytes_verified, `release trust.registry_publication.lifecycle.observations[${index}].artifacts[${artifactIndex}].public_bytes_verified`),
      };
    });
    const observedNames = new Set<string>();
    for (const artifact of observationArtifacts) {
      if (observedNames.has(artifact.name)) throw new Error("release trust registry lifecycle observation contains duplicate artifacts");
      observedNames.add(artifact.name);
      const expected = expectedArtifactMap.get(artifact.name);
      if (expected !== `${artifact.sha256}:${artifact.size_bytes}`) {
        throw new Error("release trust registry lifecycle artifacts disagree with authorized release artifacts");
      }
      if (!artifact.public_bytes_verified) {
        throw new Error("release trust registry lifecycle observed artifact must have verified public bytes");
      }
    }
    const expectedMissing = [...expectedArtifactMap.keys()].filter((name) => !observedNames.has(name)).sort();
    if (JSON.stringify([...missingArtifacts].sort()) !== JSON.stringify(expectedMissing)) {
      throw new Error("release trust registry lifecycle missing artifacts disagree with authorized release artifacts");
    }
    if (status === "unavailable") {
      if (registryEntryPresent || defaultInstallEligible || observationPublicBytes || observationArtifacts.length || missingArtifacts.length || unavailableReason === null) {
        throw new Error("release trust unavailable registry lifecycle observation is internally inconsistent");
      }
    } else if (status === "partially_available") {
      if (!registryEntryPresent || defaultInstallEligible || observationPublicBytes || !missingArtifacts.length || unavailableReason !== null) {
        throw new Error("release trust partially available registry lifecycle observation is internally inconsistent");
      }
      const yankStates = new Set(observationArtifacts.map((artifact) => artifact.yanked));
      if (yankStates.size > 1) throw new Error("release trust registry lifecycle has mixed yank state");
    } else {
      if (!registryEntryPresent || !observationPublicBytes || unavailableReason !== null || !observationArtifacts.length || missingArtifacts.length) {
        throw new Error("release trust available/yanked registry lifecycle observation is internally inconsistent");
      }
      if (defaultInstallEligible !== (status === "available")) {
        throw new Error("release trust registry lifecycle install eligibility disagrees with status");
      }
      if (observationArtifacts.some((artifact) => artifact.yanked !== (status === "yanked"))) {
        throw new Error("release trust registry lifecycle artifact yank state disagrees with observation status");
      }
    }
    return {
      observation_digest: string(observation.observation_digest, `release trust.registry_publication.lifecycle.observations[${index}].observation_digest`),
      publication_receipt_digest: string(observation.publication_receipt_digest, `release trust.registry_publication.lifecycle.observations[${index}].publication_receipt_digest`),
      predecessor_digest: string(observation.predecessor_digest, `release trust.registry_publication.lifecycle.observations[${index}].predecessor_digest`),
      basis_digest: string(observation.basis_digest, `release trust.registry_publication.lifecycle.observations[${index}].basis_digest`),
      permit_digest: string(observation.permit_digest, `release trust.registry_publication.lifecycle.observations[${index}].permit_digest`),
      target_repository: string(observation.target_repository, `release trust.registry_publication.lifecycle.observations[${index}].target_repository`),
      distribution: string(observation.distribution, `release trust.registry_publication.lifecycle.observations[${index}].distribution`),
      version: string(observation.version, `release trust.registry_publication.lifecycle.observations[${index}].version`),
      registry_api_url: string(observation.registry_api_url, `release trust.registry_publication.lifecycle.observations[${index}].registry_api_url`),
      observed_at: string(observation.observed_at, `release trust.registry_publication.lifecycle.observations[${index}].observed_at`),
      status,
      registry_entry_present: registryEntryPresent,
      default_install_eligible: defaultInstallEligible,
      public_bytes_verified: observationPublicBytes,
      missing_artifacts: missingArtifacts,
      unavailable_reason: unavailableReason,
      artifacts: observationArtifacts,
      limitations: strings(observation.limitations, `release trust.registry_publication.lifecycle.observations[${index}].limitations`),
    };
  });
  if (!lifecycleConfigured) {
    if (lifecycleCurrentStatus !== null || lifecycleCurrentObservedAt !== null || lifecycleObservationCount !== 0 || lifecycleRegistryEntryPresent !== null || lifecycleDefaultInstallEligible !== null || lifecyclePublicBytesVerified !== null || lifecycleMissingArtifacts.length || lifecycleObservations.length) {
      throw new Error("release trust unconfigured registry lifecycle cannot contain lifecycle state");
    }
  } else {
    if (!registryConfigured || !registryPublished || !lifecycleObservations.length || lifecycleObservationCount !== lifecycleObservations.length) {
      throw new Error("release trust configured registry lifecycle requires reconciled publication and observations");
    }
    const receiptDigest = nullableString(registryPublication.receipt_digest, "release trust.registry_publication.receipt_digest");
    const basisDigest = nullableString(registryPublication.basis_digest, "release trust.registry_publication.basis_digest");
    const permitDigest = nullableString(registryPublication.permit_digest, "release trust.registry_publication.permit_digest");
    const targetRepository = nullableString(registryPublication.target_repository, "release trust.registry_publication.target_repository");
    lifecycleObservations.forEach((item, index) => {
      if (item.publication_receipt_digest !== receiptDigest || item.basis_digest !== basisDigest || item.permit_digest !== permitDigest || item.target_repository !== targetRepository) {
        throw new Error("release trust registry lifecycle observation is not bound to the configured publication receipt");
      }
      const expectedPredecessor = index === 0 ? receiptDigest : lifecycleObservations[index - 1]?.observation_digest;
      if (item.predecessor_digest !== expectedPredecessor) {
        throw new Error("release trust registry lifecycle predecessor chain is invalid");
      }
    });
    const current = lifecycleObservations[lifecycleObservations.length - 1];
    if (!current || lifecycleCurrentStatus !== current.status || lifecycleCurrentObservedAt !== current.observed_at || lifecycleRegistryEntryPresent !== current.registry_entry_present || lifecycleDefaultInstallEligible !== current.default_install_eligible || lifecyclePublicBytesVerified !== current.public_bytes_verified || JSON.stringify([...lifecycleMissingArtifacts].sort()) !== JSON.stringify([...current.missing_artifacts].sort())) {
      throw new Error("release trust registry lifecycle current projection disagrees with chain tip");
    }
  }
  if (!registryConfigured) {
    if (registryPublished || registryReconciled || publicBytesVerified || registryArtifacts.length) {
      throw new Error("release trust unconfigured registry publication cannot claim publication state");
    }
  } else {
    if (!registryPublished || !registryReconciled || !publicBytesVerified || !registryArtifacts.length) {
      throw new Error("release trust configured registry publication must be fully reconciled");
    }
    const expectedArtifacts = artifacts.map((item) => `${item.name}:${item.sha256}:${item.size_bytes}`).sort();
    const observedArtifacts = registryArtifacts.map((item) => `${item.name}:${item.sha256}:${item.size_bytes}`).sort();
    if (JSON.stringify(expectedArtifacts) !== JSON.stringify(observedArtifacts)) {
      throw new Error("release trust registry artifacts disagree with authorized release artifacts");
    }
  }
  const evidence = (raw: unknown, field: string): Record<string, unknown> | null => {
    if (raw === null) return null;
    return object(raw, field);
  };
  return {
    schema_version: "release-trust-view.v1",
    bundle_digest: string(source.bundle_digest, "release trust.bundle_digest"),
    source: {
      distribution: string(sourceIdentity.distribution, "release trust.source.distribution"),
      version: string(sourceIdentity.version, "release trust.source.version"),
      source_revision: string(sourceIdentity.source_revision, "release trust.source.source_revision"),
      source_tree_sha256: string(sourceIdentity.source_tree_sha256, "release trust.source.source_tree_sha256"),
      dependency_lock_sha256: string(sourceIdentity.dependency_lock_sha256, "release trust.source.dependency_lock_sha256"),
    },
    artifacts,
    build: {
      builder: string(build.builder, "release trust.build.builder"),
      build_type: string(build.build_type, "release trust.build.build_type"),
      build_steps: strings(build.build_steps, "release trust.build.build_steps"),
      environment: stringRecord(build.environment, "release trust.build.environment"),
      started_at: nullableString(build.started_at, "release trust.build.started_at"),
      finished_at: nullableString(build.finished_at, "release trust.build.finished_at"),
    },
    tests: objectArray(source.tests, "release trust.tests"),
    external_evidence: {
      sbom: evidence(external.sbom, "release trust.external_evidence.sbom"),
      vulnerability_scan: evidence(external.vulnerability_scan, "release trust.external_evidence.vulnerability_scan"),
      signature: evidence(external.signature, "release trust.external_evidence.signature"),
      provenance: evidence(external.provenance, "release trust.external_evidence.provenance"),
    },
    structural_profile: {
      profile_id: string(profile.profile_id, "release trust.structural_profile.profile_id"),
      profile_version: string(profile.profile_version, "release trust.structural_profile.profile_version"),
      satisfied: boolean(profile.satisfied, "release trust.structural_profile.satisfied"),
      failed_requirements: strings(profile.failed_requirements, "release trust.structural_profile.failed_requirements"),
      missing_evidence: strings(profile.missing_evidence, "release trust.structural_profile.missing_evidence"),
      caveats: strings(profile.caveats, "release trust.structural_profile.caveats"),
    },
    content_verification: {
      status: string(content.status, "release trust.content_verification.status"),
      complete: nullableBoolean(content.complete, "release trust.content_verification.complete"),
      matched: strings(content.matched, "release trust.content_verification.matched"),
      missing: strings(content.missing, "release trust.content_verification.missing"),
      mismatched: strings(content.mismatched, "release trust.content_verification.mismatched"),
      limitations: strings(content.limitations, "release trust.content_verification.limitations"),
    },
    signature_authenticity: {
      status: string(signature.status, "release trust.signature_authenticity.status"),
      authenticated: nullableBoolean(signature.authenticated, "release trust.signature_authenticity.authenticated"),
      reason: string(signature.reason, "release trust.signature_authenticity.reason"),
    },
    human_decision: {
      actor_ref: string(human.actor_ref, "release trust.human_decision.actor_ref"),
      role: string(human.role, "release trust.human_decision.role"),
      decision: string(human.decision, "release trust.human_decision.decision"),
      decided_at: nullableString(human.decided_at, "release trust.human_decision.decided_at"),
      scope: string(human.scope, "release trust.human_decision.scope"),
      basis_digest: nullableString(human.basis_digest, "release trust.human_decision.basis_digest"),
    },
    publication_authorized: publicationAuthorized,
    release_published: releasePublished,
    publication_authorization: {
      configured: publicationConfigured,
      target_repository: nullableString(publication.target_repository, "release trust.publication_authorization.target_repository"),
      basis_digest: nullableString(publication.basis_digest, "release trust.publication_authorization.basis_digest"),
      expected_producer_id: nullableString(publication.expected_producer_id, "release trust.publication_authorization.expected_producer_id"),
      publication_authorized: publicationState,
      active_approval_receipt_ids: activeApprovalIds,
      items: publicationItems,
    },
    registry_publication: {
      configured: registryConfigured,
      release_published: registryPublished,
      registry_reconciled: registryReconciled,
      receipt_digest: nullableString(registryPublication.receipt_digest, "release trust.registry_publication.receipt_digest"),
      target_repository: nullableString(registryPublication.target_repository, "release trust.registry_publication.target_repository"),
      basis_digest: nullableString(registryPublication.basis_digest, "release trust.registry_publication.basis_digest"),
      permit_digest: nullableString(registryPublication.permit_digest, "release trust.registry_publication.permit_digest"),
      observed_at: nullableString(registryPublication.observed_at, "release trust.registry_publication.observed_at"),
      public_bytes_verified: publicBytesVerified,
      artifacts: registryArtifacts,
      lifecycle: {
        configured: lifecycleConfigured,
        current_status: lifecycleCurrentStatus,
        current_observed_at: lifecycleCurrentObservedAt,
        observation_count: lifecycleObservationCount,
        registry_entry_present: lifecycleRegistryEntryPresent,
        default_install_eligible: lifecycleDefaultInstallEligible,
        public_bytes_verified: lifecyclePublicBytesVerified,
        missing_artifacts: lifecycleMissingArtifacts,
        observations: lifecycleObservations,
      },
    },
    limitations: strings(source.limitations, "release trust.limitations"),
  };
}

function parseValidationMetric(value: unknown, index: number): ValidationStudyMetric {
  const source = object(value, `validation study.metrics[${index}]`);
  return {
    baseline: string(source.baseline, `validation study.metrics[${index}].baseline`),
    case_count: number(source.case_count, `validation study.metrics[${index}].case_count`),
    injected_fault_count: number(source.injected_fault_count, `validation study.metrics[${index}].injected_fault_count`),
    detected_fault_count: number(source.detected_fault_count, `validation study.metrics[${index}].detected_fault_count`),
    valid_case_count: number(source.valid_case_count, `validation study.metrics[${index}].valid_case_count`),
    false_positive_count: number(source.false_positive_count, `validation study.metrics[${index}].false_positive_count`),
    target_property_count: number(source.target_property_count, `validation study.metrics[${index}].target_property_count`),
    checkable_property_count: number(source.checkable_property_count, `validation study.metrics[${index}].checkable_property_count`),
    verification_coverage: number(source.verification_coverage, `validation study.metrics[${index}].verification_coverage`),
    fault_detection_rate: number(source.fault_detection_rate, `validation study.metrics[${index}].fault_detection_rate`),
    false_positive_rate: number(source.false_positive_rate, `validation study.metrics[${index}].false_positive_rate`),
    verification_coverage_denominator: number(source.verification_coverage_denominator, `validation study.metrics[${index}].verification_coverage_denominator`),
    fault_detection_denominator: number(source.fault_detection_denominator, `validation study.metrics[${index}].fault_detection_denominator`),
    false_positive_denominator: number(source.false_positive_denominator, `validation study.metrics[${index}].false_positive_denominator`),
  };
}

export function parseValidationStudyView(value: unknown): ValidationStudyView {
  const source = object(value, "validation study");
  if (source.schema_version !== "validation-study-view.v1") throw new Error("unsupported validation study schema");
  if (source.study_kind !== "deterministic-fixture-study") throw new Error("unsupported validation study kind");
  if (!Array.isArray(source.metrics)) throw new Error("validation study.metrics must be an array");
  return {
    schema_version: "validation-study-view.v1",
    study_id: string(source.study_id, "validation study.study_id"),
    study_digest: string(source.study_digest, "validation study.study_digest"),
    study_kind: "deterministic-fixture-study",
    baselines: objectArray(source.baselines, "validation study.baselines"),
    workloads: objectArray(source.workloads, "validation study.workloads"),
    faults: objectArray(source.faults, "validation study.faults"),
    metrics: source.metrics.map((item, index) => parseValidationMetric(item, index)),
    case_count: number(source.case_count, "validation study.case_count"),
    cases: objectArray(source.cases, "validation study.cases"),
    limitations: strings(source.limitations, "validation study.limitations"),
  };
}

function parseWorkspaceRecord(value: unknown, index: number): WorkspaceRecordView {
  const source = object(value, `workspace.records.items[${index}]`);
  let retention: WorkspaceRecordView["retention"] = null;
  if (source.retention !== null) {
    const raw = object(source.retention, `workspace.records.items[${index}].retention`);
    retention = {
      policy_id: string(raw.policy_id, `workspace.records.items[${index}].retention.policy_id`),
      sensitivity: string(raw.sensitivity, `workspace.records.items[${index}].retention.sensitivity`),
      retain_until: nullableString(raw.retain_until, `workspace.records.items[${index}].retention.retain_until`),
      legal_hold: boolean(raw.legal_hold, `workspace.records.items[${index}].retention.legal_hold`),
    };
  }
  return {
    record_id: string(source.record_id, `workspace.records.items[${index}].record_id`),
    receipt_id: string(source.receipt_id, `workspace.records.items[${index}].receipt_id`),
    artifact_digest: string(source.artifact_digest, `workspace.records.items[${index}].artifact_digest`),
    artifact_size: number(source.artifact_size, `workspace.records.items[${index}].artifact_size`),
    producer_id: string(source.producer_id, `workspace.records.items[${index}].producer_id`),
    producer_type: string(source.producer_type, `workspace.records.items[${index}].producer_type`),
    producer_version: nullableString(source.producer_version, `workspace.records.items[${index}].producer_version`),
    source_event_id: nullableString(source.source_event_id, `workspace.records.items[${index}].source_event_id`),
    run_id: nullableString(source.run_id, `workspace.records.items[${index}].run_id`),
    captured_at: string(source.captured_at, `workspace.records.items[${index}].captured_at`),
    sensitivity: string(source.sensitivity, `workspace.records.items[${index}].sensitivity`),
    verification_status: nullableString(source.verification_status, `workspace.records.items[${index}].verification_status`),
    reliability_state: nullableString(source.reliability_state, `workspace.records.items[${index}].reliability_state`),
    retention,
  };
}

export function parseWorkspaceOperationsView(value: unknown): WorkspaceOperationsView {
  const source = object(value, "workspace operations");
  if (source.schema_version !== "workspace-operations.v1") throw new Error("unsupported workspace operations schema");
  const workspace = object(source.workspace, "workspace operations.workspace");
  const health = object(source.health, "workspace operations.health");
  const storage = object(source.storage, "workspace operations.storage");
  const migration = object(source.migration, "workspace operations.migration");
  const records = object(source.records, "workspace operations.records");
  const lifecycle = object(source.lifecycle, "workspace operations.lifecycle");
  const exports = object(source.exports, "workspace operations.exports");
  const backup = object(source.backup, "workspace operations.backup");
  const audit = object(source.operational_audit, "workspace operations.operational_audit");
  if (workspace.mode !== "read-only" || workspace.backend !== "sqlite") {
    throw new Error("workspace operations must be a read-only sqlite projection");
  }
  if (!Array.isArray(health.issues) || !Array.isArray(records.items) || !Array.isArray(exports.items)) {
    throw new Error("workspace operations lists must be arrays");
  }
  return {
    schema_version: "workspace-operations.v1",
    workspace: {
      workspace_id: string(workspace.workspace_id, "workspace operations.workspace.workspace_id"),
      schema_version: string(workspace.schema_version, "workspace operations.workspace.schema_version"),
      public_api_contract_version: string(workspace.public_api_contract_version, "workspace operations.workspace.public_api_contract_version"),
      mode: "read-only",
      backend: "sqlite",
    },
    health: {
      status: string(health.status, "workspace operations.health.status"),
      healthy: boolean(health.healthy, "workspace operations.health.healthy"),
      has_errors: boolean(health.has_errors, "workspace operations.health.has_errors"),
      checked_records: number(health.checked_records, "workspace operations.health.checked_records"),
      checked_receipts: number(health.checked_receipts, "workspace operations.health.checked_receipts"),
      checked_artifacts: number(health.checked_artifacts, "workspace operations.health.checked_artifacts"),
      checked_exports: number(health.checked_exports, "workspace operations.health.checked_exports"),
      issues: health.issues.map((item, index) => {
        const issue = object(item, `workspace operations.health.issues[${index}]`);
        return {
          code: string(issue.code, `workspace operations.health.issues[${index}].code`),
          severity: string(issue.severity, `workspace operations.health.issues[${index}].severity`),
          message: string(issue.message, `workspace operations.health.issues[${index}].message`),
          object_id: nullableString(issue.object_id, `workspace operations.health.issues[${index}].object_id`),
        };
      }),
      orphan_counts: (() => {
        const raw = object(health.orphan_counts, "workspace operations.health.orphan_counts");
        return {
          artifacts: number(raw.artifacts, "workspace operations.health.orphan_counts.artifacts"),
          receipts: number(raw.receipts, "workspace operations.health.orphan_counts.receipts"),
          exports: number(raw.exports, "workspace operations.health.orphan_counts.exports"),
        };
      })(),
    },
    storage: {
      total_bytes: number(storage.total_bytes, "workspace operations.storage.total_bytes"),
      artifact_bytes: number(storage.artifact_bytes, "workspace operations.storage.artifact_bytes"),
      receipt_bytes: number(storage.receipt_bytes, "workspace operations.storage.receipt_bytes"),
      database_bytes: number(storage.database_bytes, "workspace operations.storage.database_bytes"),
      export_bytes: number(storage.export_bytes, "workspace operations.storage.export_bytes"),
      manifest_bytes: number(storage.manifest_bytes, "workspace operations.storage.manifest_bytes"),
      lock_bytes: number(storage.lock_bytes, "workspace operations.storage.lock_bytes"),
    },
    migration: {
      current_schema_version: string(migration.current_schema_version, "workspace operations.migration.current_schema_version"),
      status: string(migration.status, "workspace operations.migration.status"),
    },
    records: {
      items: records.items.map((item, index) => parseWorkspaceRecord(item, index)),
      total_count: number(records.total_count, "workspace operations.records.total_count"),
      limit: number(records.limit, "workspace operations.records.limit"),
      offset: number(records.offset, "workspace operations.records.offset"),
      has_more: boolean(records.has_more, "workspace operations.records.has_more"),
      next_offset: nullableNumber(records.next_offset, "workspace operations.records.next_offset"),
    },
    lifecycle: {
      retention_rows_in_snapshot: number(lifecycle.retention_rows_in_snapshot, "workspace operations.lifecycle.retention_rows_in_snapshot"),
      retention_rows_in_page: number(lifecycle.retention_rows_in_page, "workspace operations.lifecycle.retention_rows_in_page"),
      legal_holds_in_page: number(lifecycle.legal_holds_in_page, "workspace operations.lifecycle.legal_holds_in_page"),
      deletion_tombstones: number(lifecycle.deletion_tombstones, "workspace operations.lifecycle.deletion_tombstones"),
    },
    exports: {
      count: number(exports.count, "workspace operations.exports.count"),
      items: exports.items.map((item, index) => {
        const raw = object(item, `workspace operations.exports.items[${index}]`);
        return {
          export_id: string(raw.export_id, `workspace operations.exports.items[${index}].export_id`),
          format: string(raw.format, `workspace operations.exports.items[${index}].format`),
          created_at: string(raw.created_at, `workspace operations.exports.items[${index}].created_at`),
          disclosure_max_sensitivity: string(raw.disclosure_max_sensitivity, `workspace operations.exports.items[${index}].disclosure_max_sensitivity`),
          source_schema_version: string(raw.source_schema_version, `workspace operations.exports.items[${index}].source_schema_version`),
          output_digest: nullableString(raw.output_digest, `workspace operations.exports.items[${index}].output_digest`),
          row_count: nullableNumber(raw.row_count, `workspace operations.exports.items[${index}].row_count`),
        };
      }),
      supported_formats: strings(exports.supported_formats, "workspace operations.exports.supported_formats"),
    },
    backup: {
      history_status: string(backup.history_status, "workspace operations.backup.history_status"),
      restore_eligibility: string(backup.restore_eligibility, "workspace operations.backup.restore_eligibility"),
      note: string(backup.note, "workspace operations.backup.note"),
    },
    operational_audit: {
      status: string(audit.status, "workspace operations.operational_audit.status"),
      note: string(audit.note, "workspace operations.operational_audit.note"),
    },
    limitations: strings(source.limitations, "workspace operations.limitations"),
  };
}


const SECURITY_AUDIT_EVENTS = new Set([
  "authentication_failed",
  "authorization_denied",
  "request_rejected",
  "request_admitted",
]);
const SECURITY_AUDIT_OPERATIONS = new Set([
  "verify:evidence",
  "verify:proof",
  "review:read",
  "review:write",
  "approval:read",
  "approval:write",
]);

function parseSecurityAuditItem(value: unknown, index: number): SecurityAuditItemView {
  const source = object(value, `security assurance.items[${index}]`);
  const event = string(source.event, `security assurance.items[${index}].event`);
  if (!SECURITY_AUDIT_EVENTS.has(event)) throw new Error("unsupported security audit event");
  const operation = nullableString(source.operation, `security assurance.items[${index}].operation`);
  if (operation !== null && !SECURITY_AUDIT_OPERATIONS.has(operation)) {
    throw new Error("unsupported security audit operation");
  }
  const sequence = number(source.sequence, `security assurance.items[${index}].sequence`);
  if (!Number.isInteger(sequence) || sequence < 0) throw new Error("security audit sequence must be non-negative integer");
  if (source.path_exposed !== false) throw new Error("security assurance must not expose recorded paths");
  return {
    sequence,
    occurred_at: string(source.occurred_at, `security assurance.items[${index}].occurred_at`),
    event: event as SecurityAuditItemView["event"],
    operation: operation as SecurityAuditItemView["operation"],
    method: string(source.method, `security assurance.items[${index}].method`),
    route_kind: string(source.route_kind, `security assurance.items[${index}].route_kind`),
    path_digest: string(source.path_digest, `security assurance.items[${index}].path_digest`),
    path_exposed: false,
    reason: string(source.reason, `security assurance.items[${index}].reason`),
    reason_digest: string(source.reason_digest, `security assurance.items[${index}].reason_digest`),
    previous_digest: nullableString(source.previous_digest, `security assurance.items[${index}].previous_digest`),
    digest: string(source.digest, `security assurance.items[${index}].digest`),
  };
}

function parseCountRows(
  value: unknown,
  field: string,
  key: string,
): Array<Record<string, string | number>> {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array`);
  return value.map((item, index) => {
    const row = object(item, `${field}[${index}]`);
    const label = string(row[key], `${field}[${index}].${key}`);
    const count = number(row.count, `${field}[${index}].count`);
    if (!Number.isInteger(count) || count < 0) throw new Error(`${field} counts must be non-negative integers`);
    return { [key]: label, count };
  });
}

export function parseSecurityAssurance(value: unknown): SecurityAssuranceView {
  const source = object(value, "security assurance");
  exactKeys(source, ["schema_version", "source", "observations", "runtime_containment", "deployment_boundary", "aggregates", "query", "page", "items", "limitations"], "security assurance");
  if (source.schema_version !== "security-assurance-investigation.v2") {
    throw new Error("unsupported security assurance schema");
  }

  const sourceInfo = object(source.source, "security assurance.source");
  exactKeys(sourceInfo, ["resource", "configured", "exists", "byte_size", "read_limit_bytes", "record_limit", "chain_integrity", "source_path_exposed"], "security assurance.source");
  if (sourceInfo.resource !== "deployment-security-audit-journal") {
    throw new Error("security assurance source contract is invalid");
  }
  const auditConfigured = boolean(sourceInfo.configured, "security assurance.source.configured");
  const auditExists = boolean(sourceInfo.exists, "security assurance.source.exists");
  if (sourceInfo.source_path_exposed !== false || (!auditConfigured && auditExists)) {
    throw new Error("security assurance must not expose or invent an audit source");
  }
  const chainIntegrity = string(sourceInfo.chain_integrity, "security assurance.source.chain_integrity");
  if (!new Set(["verified", "missing"]).has(chainIntegrity)) throw new Error("invalid security audit chain status");
  if ((chainIntegrity === "verified") !== (auditConfigured && auditExists)) {
    throw new Error("security audit chain status is inconsistent with the source state");
  }

  const observations = object(source.observations, "security assurance.observations");
  exactKeys(observations, ["recorded_event_count", "authentication_failed_count", "authorization_denied_count", "request_rejected_count", "request_admitted_count", "distinct_operation_count", "distinct_route_kind_count", "deployment_secure_inferred", "live_configuration_observed", "runtime_configuration_snapshot_observed"], "security assurance.observations");
  if (observations.deployment_secure_inferred !== false || observations.live_configuration_observed !== false) {
    throw new Error("security assurance must not infer live deployment security");
  }
  const runtimeObserved = boolean(observations.runtime_configuration_snapshot_observed, "security assurance.observations.runtime_configuration_snapshot_observed");

  const runtime = object(source.runtime_containment, "security assurance.runtime_containment");
  exactKeys(runtime, ["snapshot_observed", "configuration_digest", "recorded_at_utc", "verification_service", "limits", "enforcement", "host_controls_evaluated"], "security assurance.runtime_containment");
  const snapshotObserved = boolean(runtime.snapshot_observed, "security assurance.runtime_containment.snapshot_observed");
  if (snapshotObserved !== runtimeObserved || runtime.host_controls_evaluated !== false) {
    throw new Error("runtime containment observation boundary is inconsistent");
  }
  const enforcementSource = object(runtime.enforcement, "security assurance.runtime_containment.enforcement");
  const enforcementKeys = ["request_body_bytes", "json_input_bytes", "json_depth", "json_nodes", "json_string_bytes", "archive_members", "archive_uncompressed_bytes", "archive_compression_ratio", "graph_nodes", "verification_seconds", "concurrency", "temporary_bytes"] as const;
  exactKeys(enforcementSource, enforcementKeys, "security assurance.runtime_containment.enforcement");

  let runtimeContainment: SecurityAssuranceView["runtime_containment"];
  if (!snapshotObserved) {
    if (runtime.configuration_digest !== null || runtime.recorded_at_utc !== null || runtime.verification_service !== null || runtime.limits !== null) {
      throw new Error("unobserved runtime containment must not fabricate configuration values");
    }
    const enforcement: Record<string, "not-observed"> = {};
    for (const key of enforcementKeys) {
      if (enforcementSource[key] !== "not-observed") throw new Error("unobserved runtime containment must not claim enforcement");
      enforcement[key] = "not-observed";
    }
    runtimeContainment = {
      snapshot_observed: false,
      configuration_digest: null,
      recorded_at_utc: null,
      verification_service: null,
      limits: null,
      enforcement,
      host_controls_evaluated: false,
    };
  } else {
    const configurationDigest = string(runtime.configuration_digest, "security assurance.runtime_containment.configuration_digest");
    if (!/^[0-9a-f]{64}$/.test(configurationDigest)) throw new Error("runtime containment digest must be lowercase SHA-256 hex");
    const recordedAt = string(runtime.recorded_at_utc, "security assurance.runtime_containment.recorded_at_utc");
    if (Number.isNaN(Date.parse(recordedAt))) throw new Error("runtime containment recorded_at_utc must be a timestamp");
    const service = object(runtime.verification_service, "security assurance.runtime_containment.verification_service");
    exactKeys(service, ["max_request_bytes", "read_only", "require_https", "allow_insecure_http", "artifact_root_count", "artifact_roots_exposed"], "security assurance.runtime_containment.verification_service");
    if (service.read_only !== true || service.artifact_roots_exposed !== false) throw new Error("runtime containment service boundary is invalid");
    const maxRequestBytes = number(service.max_request_bytes, "security assurance.runtime_containment.verification_service.max_request_bytes");
    const artifactRootCount = number(service.artifact_root_count, "security assurance.runtime_containment.verification_service.artifact_root_count");
    const requireHttps = boolean(service.require_https, "security assurance.runtime_containment.verification_service.require_https");
    const allowInsecureHttp = boolean(service.allow_insecure_http, "security assurance.runtime_containment.verification_service.allow_insecure_http");
    if (!Number.isInteger(maxRequestBytes) || maxRequestBytes < 1 || !Number.isInteger(artifactRootCount) || artifactRootCount < 0 || (requireHttps && allowInsecureHttp)) {
      throw new Error("runtime containment service configuration is invalid");
    }
    const limits = object(runtime.limits, "security assurance.runtime_containment.limits");
    const limitKeys = ["max_input_bytes", "max_archive_members", "max_archive_uncompressed_bytes", "max_archive_compression_ratio", "max_json_depth", "max_json_nodes", "max_string_bytes", "max_graph_nodes", "max_verification_seconds", "max_concurrency", "max_temporary_bytes"] as const;
    exactKeys(limits, limitKeys, "security assurance.runtime_containment.limits");
    const parsedLimits = {
      max_input_bytes: number(limits.max_input_bytes, "runtime limits.max_input_bytes"),
      max_archive_members: number(limits.max_archive_members, "runtime limits.max_archive_members"),
      max_archive_uncompressed_bytes: number(limits.max_archive_uncompressed_bytes, "runtime limits.max_archive_uncompressed_bytes"),
      max_archive_compression_ratio: number(limits.max_archive_compression_ratio, "runtime limits.max_archive_compression_ratio"),
      max_json_depth: number(limits.max_json_depth, "runtime limits.max_json_depth"),
      max_json_nodes: number(limits.max_json_nodes, "runtime limits.max_json_nodes"),
      max_string_bytes: number(limits.max_string_bytes, "runtime limits.max_string_bytes"),
      max_graph_nodes: number(limits.max_graph_nodes, "runtime limits.max_graph_nodes"),
      max_verification_seconds: number(limits.max_verification_seconds, "runtime limits.max_verification_seconds"),
      max_concurrency: number(limits.max_concurrency, "runtime limits.max_concurrency"),
      max_temporary_bytes: number(limits.max_temporary_bytes, "runtime limits.max_temporary_bytes"),
    };
    for (const [key, value] of Object.entries(parsedLimits)) {
      if (!(value > 0) || (key !== "max_archive_compression_ratio" && key !== "max_verification_seconds" && !Number.isInteger(value))) {
        throw new Error("runtime containment limits must be positive and well-typed");
      }
    }
    if (parsedLimits.max_archive_compression_ratio < 1) throw new Error("runtime archive compression ratio must be at least 1");
    const expectedEnforcement = {
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
    } as const;
    for (const key of enforcementKeys) {
      if (enforcementSource[key] !== expectedEnforcement[key]) throw new Error("runtime containment enforcement claim exceeds the current implementation");
    }
    runtimeContainment = {
      snapshot_observed: true,
      configuration_digest: configurationDigest,
      recorded_at_utc: recordedAt,
      verification_service: {
        max_request_bytes: maxRequestBytes,
        read_only: true,
        require_https: requireHttps,
        allow_insecure_http: allowInsecureHttp,
        artifact_root_count: artifactRootCount,
        artifact_roots_exposed: false,
      },
      limits: parsedLimits,
      enforcement: expectedEnforcement,
      host_controls_evaluated: false,
    };
  }

  const boundary = object(source.deployment_boundary, "security assurance.deployment_boundary");
  exactKeys(boundary, ["configuration_snapshot_available", "protected_operations", "default_public_paths", "default_require_https", "authentication_provider", "authorization_provider", "request_admission_provider", "security_event_sink", "host_responsibilities"], "security assurance.deployment_boundary");
  if (boundary.configuration_snapshot_available !== false || boundary.default_require_https !== true) {
    throw new Error("security assurance deployment boundary is inconsistent");
  }
  if (boundary.authentication_provider !== "host-provided" || boundary.authorization_provider !== "host-provided") {
    throw new Error("security assurance must preserve host-owned identity boundaries");
  }
  const aggregates = object(source.aggregates, "security assurance.aggregates");
  const query = object(source.query, "security assurance.query");
  const page = object(source.page, "security assurance.page");
  if (!Array.isArray(source.items)) throw new Error("security assurance.items must be an array");
  const items = source.items.map(parseSecurityAuditItem);
  const limit = number(page.limit, "security assurance.page.limit");
  const offset = number(page.offset, "security assurance.page.offset");
  const returned = number(page.returned, "security assurance.page.returned");
  const matched = number(page.matched, "security assurance.page.matched");
  const hasMore = boolean(page.has_more, "security assurance.page.has_more");
  const nextOffset = nullableNumber(page.next_offset, "security assurance.page.next_offset");
  if (![limit, offset, returned, matched].every((item) => Number.isInteger(item) && item >= 0) || limit < 1 || limit > 200) {
    throw new Error("security assurance pagination is invalid");
  }
  if (returned !== items.length || returned > matched) throw new Error("security assurance page counts are inconsistent");
  if (number(query.limit, "security assurance.query.limit") !== limit || number(query.offset, "security assurance.query.offset") !== offset) {
    throw new Error("security assurance query/page pagination must match");
  }
  if ((hasMore && nextOffset === null) || (!hasMore && nextOffset !== null)) {
    throw new Error("security assurance next_offset is inconsistent");
  }
  const countFields = [
    "recorded_event_count",
    "authentication_failed_count",
    "authorization_denied_count",
    "request_rejected_count",
    "request_admitted_count",
    "distinct_operation_count",
    "distinct_route_kind_count",
  ];
  const observationCounts: Record<string, number> = {};
  for (const field of countFields) {
    const count = number(observations[field], `security assurance.observations.${field}`);
    if (!Number.isInteger(count) || count < 0) throw new Error("security assurance counts must be non-negative integers");
    observationCounts[field] = count;
  }
  const byteSize = number(sourceInfo.byte_size, "security assurance.source.byte_size");
  const readLimit = number(sourceInfo.read_limit_bytes, "security assurance.source.read_limit_bytes");
  const recordLimit = number(sourceInfo.record_limit, "security assurance.source.record_limit");
  if (![byteSize, readLimit, recordLimit].every((item) => Number.isInteger(item) && item >= 0) || readLimit < 1 || recordLimit < 1) {
    throw new Error("security assurance source limits are invalid");
  }
  return {
    schema_version: "security-assurance-investigation.v2",
    source: {
      resource: "deployment-security-audit-journal",
      configured: auditConfigured,
      exists: auditExists,
      byte_size: byteSize,
      read_limit_bytes: readLimit,
      record_limit: recordLimit,
      chain_integrity: chainIntegrity as SecurityAssuranceView["source"]["chain_integrity"],
      source_path_exposed: false,
    },
    observations: {
      recorded_event_count: observationCounts.recorded_event_count!,
      authentication_failed_count: observationCounts.authentication_failed_count!,
      authorization_denied_count: observationCounts.authorization_denied_count!,
      request_rejected_count: observationCounts.request_rejected_count!,
      request_admitted_count: observationCounts.request_admitted_count!,
      distinct_operation_count: observationCounts.distinct_operation_count!,
      distinct_route_kind_count: observationCounts.distinct_route_kind_count!,
      deployment_secure_inferred: false,
      live_configuration_observed: false,
      runtime_configuration_snapshot_observed: runtimeObserved,
    },
    runtime_containment: runtimeContainment,
    deployment_boundary: {
      configuration_snapshot_available: false,
      protected_operations: strings(boundary.protected_operations, "security assurance.deployment_boundary.protected_operations"),
      default_public_paths: strings(boundary.default_public_paths, "security assurance.deployment_boundary.default_public_paths"),
      default_require_https: true,
      authentication_provider: "host-provided",
      authorization_provider: "host-provided",
      request_admission_provider: string(boundary.request_admission_provider, "security assurance.deployment_boundary.request_admission_provider") as "optional-host-provided",
      security_event_sink: string(boundary.security_event_sink, "security assurance.deployment_boundary.security_event_sink") as "optional-host-provided",
      host_responsibilities: strings(boundary.host_responsibilities, "security assurance.deployment_boundary.host_responsibilities"),
    },
    aggregates: {
      by_event: parseCountRows(aggregates.by_event, "security assurance.aggregates.by_event", "event") as Array<{ event: string; count: number }>,
      by_operation: parseCountRows(aggregates.by_operation, "security assurance.aggregates.by_operation", "operation") as Array<{ operation: string; count: number }>,
      by_reason: parseCountRows(aggregates.by_reason, "security assurance.aggregates.by_reason", "reason") as Array<{ reason: string; count: number }>,
      by_method: parseCountRows(aggregates.by_method, "security assurance.aggregates.by_method", "method") as Array<{ method: string; count: number }>,
      by_route_kind: parseCountRows(aggregates.by_route_kind, "security assurance.aggregates.by_route_kind", "route_kind") as Array<{ route_kind: string; count: number }>,
    },
    query: {
      event: nullableString(query.event, "security assurance.query.event"),
      operation: nullableString(query.operation, "security assurance.query.operation"),
      reason: nullableString(query.reason, "security assurance.query.reason"),
      method: nullableString(query.method, "security assurance.query.method"),
      limit,
      offset,
    },
    page: { limit, offset, returned, matched, has_more: hasMore, next_offset: nextOffset },
    items,
    limitations: strings(source.limitations, "security assurance.limitations"),
  };
}

function hasOwn(source: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(source, key);
}

export function parseAssuranceDecision(value: unknown): AssuranceDecisionView {
  const source = object(value, "assurance decision");
  if (source.schema_version !== "assurance-decision-investigation.v1") {
    throw new Error("unsupported assurance decision schema");
  }
  const decision = object(source.decision, "assurance decision.decision");
  if (hasOwn(decision, "subject_id") || decision.rationale_exposed !== false) {
    throw new Error("assurance decision must not expose raw subject identity or rationale");
  }
  if (decision.system_state_unchanged !== true || decision.semantic_replay_verified !== true) {
    throw new Error("assurance decision must preserve state and verify deterministic replay");
  }
  const authorization = object(source.authorization, "assurance decision.authorization");
  if (
    authorization.factual_correctness_evaluated !== false ||
    authorization.publication_authorized !== false ||
    authorization.compliance_certified !== false ||
    authorization.host_authorization_inferred !== false
  ) {
    throw new Error("assurance decision must not infer external authorization or correctness");
  }
  const exceptionSource = object(source.exception, "assurance decision.exception");
  let exception: AssuranceDecisionView["exception"];
  if (exceptionSource.present === false) {
    exception = { present: false };
  } else if (exceptionSource.present === true) {
    if (hasOwn(exceptionSource, "authorized_by") || hasOwn(exceptionSource, "subject_id")) {
      throw new Error("assurance exception must not expose raw identities");
    }
    if (exceptionSource.system_state_preserved !== true) {
      throw new Error("assurance exception must preserve underlying assurance state");
    }
    const binding = string(exceptionSource.binding, "assurance decision.exception.binding");
    if (binding !== "exact-decision-digest" && binding !== "legacy-unbound") {
      throw new Error("unsupported assurance exception binding");
    }
    const decisionDigest = nullableString(
      exceptionSource.decision_digest,
      "assurance decision.exception.decision_digest",
    );
    if (binding === "exact-decision-digest" && decisionDigest !== decision.digest) {
      throw new Error("exact assurance exception binding must match decision digest");
    }
    if (binding === "legacy-unbound" && decisionDigest !== null) {
      throw new Error("legacy-unbound exception must not claim a decision digest");
    }
    const status = string(exceptionSource.status, "assurance decision.exception.status");
    if (status !== "active" && status !== "expired") {
      throw new Error("unsupported assurance exception status");
    }
    exception = {
      present: true,
      exception_id_digest: string(exceptionSource.exception_id_digest, "assurance decision.exception.exception_id_digest"),
      binding,
      decision_digest: decisionDigest,
      status,
      created_at: string(exceptionSource.created_at, "assurance decision.exception.created_at"),
      expires_at: string(exceptionSource.expires_at, "assurance decision.exception.expires_at"),
      authorized_by_digest: string(exceptionSource.authorized_by_digest, "assurance decision.exception.authorized_by_digest"),
      compensating_control: string(exceptionSource.compensating_control, "assurance decision.exception.compensating_control"),
      reverification_required: string(exceptionSource.reverification_required, "assurance decision.exception.reverification_required"),
      evidence_reference_digests: strings(exceptionSource.evidence_reference_digests, "assurance decision.exception.evidence_reference_digests"),
      system_state_preserved: true,
    };
  } else {
    throw new Error("assurance decision.exception.present must be a boolean");
  }
  return {
    schema_version: "assurance-decision-investigation.v1",
    decision: {
      decision: string(decision.decision, "assurance decision.decision.decision"),
      digest: string(decision.digest, "assurance decision.decision.digest"),
      subject_id_digest: string(decision.subject_id_digest, "assurance decision.decision.subject_id_digest"),
      policy_id: string(decision.policy_id, "assurance decision.decision.policy_id"),
      policy_version: string(decision.policy_version, "assurance decision.decision.policy_version"),
      policy_rule: string(decision.policy_rule, "assurance decision.decision.policy_rule"),
      generated_at: string(decision.generated_at, "assurance decision.decision.generated_at"),
      source_reliability_state: string(decision.source_reliability_state, "assurance decision.decision.source_reliability_state"),
      source_verification_status: string(decision.source_verification_status, "assurance decision.decision.source_verification_status"),
      evidence_reference_digests: strings(decision.evidence_reference_digests, "assurance decision.decision.evidence_reference_digests"),
      verification_results: strings(decision.verification_results, "assurance decision.decision.verification_results"),
      residual_risk: strings(decision.residual_risk, "assurance decision.decision.residual_risk"),
      system_state_unchanged: true,
      semantic_replay_verified: true,
      rationale_exposed: false,
    },
    exception,
    authorization: {
      factual_correctness_evaluated: false,
      publication_authorized: false,
      compliance_certified: false,
      host_authorization_inferred: false,
    },
    limitations: strings(source.limitations, "assurance decision.limitations"),
  };
}

export function parseAccessAuthorization(value: unknown): AccessAuthorizationView {
  const source = object(value, "access authorization");
  if (source.schema_version !== "access-authorization-investigation.v1") {
    throw new Error("unsupported access authorization schema");
  }
  const sourceBoundary = object(source.source, "access authorization.source");
  if (
    sourceBoundary.resource !== "explicit-authorization-context-artifact" ||
    sourceBoundary.configured !== true ||
    sourceBoundary.source_path_exposed !== false ||
    sourceBoundary.canonical_iam_store !== false
  ) {
    throw new Error("access authorization source boundary is unsupported");
  }
  const principal = object(source.principal, "access authorization.principal");
  if (hasOwn(principal, "principal_id") || principal.principal_id_exposed !== false) {
    throw new Error("access authorization must not expose raw principal identity");
  }
  const request = object(source.request, "access authorization.request");
  if (
    hasOwn(request, "resource_domain") ||
    hasOwn(request, "resource_id") ||
    request.resource_identity_exposed !== false
  ) {
    throw new Error("access authorization must not expose raw resource identity");
  }
  const policy = object(source.policy, "access authorization.policy");
  if (policy.deny_by_default !== true || !Array.isArray(policy.grants)) {
    throw new Error("access authorization policy must be deny-by-default with explicit grants");
  }
  const grants = policy.grants.map((item, index) => {
    const grant = object(item, `access authorization.policy.grants[${index}]`);
    return {
      role: string(grant.role, `access authorization.policy.grants[${index}].role`),
      operation: string(grant.operation, `access authorization.policy.grants[${index}].operation`),
      allowed_states: strings(grant.allowed_states, `access authorization.policy.grants[${index}].allowed_states`),
    };
  });
  const grantCount = number(policy.grant_count, "access authorization.policy.grant_count");
  if (!Number.isInteger(grantCount) || grantCount !== grants.length) {
    throw new Error("access authorization grant count is inconsistent");
  }
  if (!Array.isArray(principal.resource_scopes)) {
    throw new Error("access authorization principal.resource_scopes must be an array");
  }
  const scopes = principal.resource_scopes.map((item, index) => {
    const scope = object(item, `access authorization.principal.resource_scopes[${index}]`);
    const ids = strings(scope.resource_id_digests, `access authorization.principal.resource_scopes[${index}].resource_id_digests`);
    const count = number(scope.resource_count, `access authorization.principal.resource_scopes[${index}].resource_count`);
    if (!Number.isInteger(count) || count !== ids.length) {
      throw new Error("access authorization resource scope count is inconsistent");
    }
    return {
      resource_domain_digest: string(scope.resource_domain_digest, `access authorization.principal.resource_scopes[${index}].resource_domain_digest`),
      resource_id_digests: ids,
      resource_count: count,
    };
  });
  const status = string(principal.status, "access authorization.principal.status");
  if (status !== "ACTIVE" && status !== "REVOKED") {
    throw new Error("access authorization principal status is unsupported");
  }
  const evaluation = object(source.evaluation, "access authorization.evaluation");
  if (evaluation.policy_replay_verified !== true) {
    throw new Error("access authorization decision must be policy-replay verified");
  }
  const recordedPresent = boolean(evaluation.recorded_decision_present, "access authorization.evaluation.recorded_decision_present");
  const recordedVerified = boolean(evaluation.recorded_decision_verified, "access authorization.evaluation.recorded_decision_verified");
  if (recordedVerified !== recordedPresent) {
    throw new Error("access authorization recorded decision state is inconsistent");
  }
  const decision = object(source.decision, "access authorization.decision");
  if (hasOwn(decision, "principal_id") || hasOwn(decision, "resource_domain") || hasOwn(decision, "resource_id")) {
    throw new Error("access authorization decision must not expose raw identities");
  }
  const boundary = object(source.authorization_boundary, "access authorization.authorization_boundary");
  if (
    boundary.principal_authentication_evaluated !== false ||
    boundary.session_validity_evaluated !== false ||
    boundary.mfa_evaluated !== false ||
    boundary.tls_evaluated !== false ||
    boundary.tenant_isolation_evaluated !== false ||
    boundary.iam_provider !== false ||
    boundary.business_authorization_inferred !== false ||
    boundary.identity_provider !== "external-host"
  ) {
    throw new Error("access authorization must not infer external authentication or IAM authority");
  }
  const scopeDomainCount = number(principal.resource_scope_domain_count, "access authorization.principal.resource_scope_domain_count");
  const scopeResourceCount = number(principal.resource_scope_resource_count, "access authorization.principal.resource_scope_resource_count");
  if (!Number.isInteger(scopeDomainCount) || scopeDomainCount !== scopes.length) {
    throw new Error("access authorization scope-domain count is inconsistent");
  }
  const countedResources = scopes.reduce((total, item) => total + item.resource_count, 0);
  if (!Number.isInteger(scopeResourceCount) || scopeResourceCount !== countedResources) {
    throw new Error("access authorization scope-resource count is inconsistent");
  }
  return {
    schema_version: "access-authorization-investigation.v1",
    source: {
      resource: "explicit-authorization-context-artifact",
      configured: true,
      source_path_exposed: false,
      canonical_iam_store: false,
    },
    principal: {
      principal_id_digest: string(principal.principal_id_digest, "access authorization.principal.principal_id_digest"),
      principal_id_exposed: false,
      status,
      roles: strings(principal.roles, "access authorization.principal.roles"),
      expires_at: nullableString(principal.expires_at, "access authorization.principal.expires_at"),
      active_at_request: boolean(principal.active_at_request, "access authorization.principal.active_at_request"),
      resource_scope_domain_count: scopeDomainCount,
      resource_scope_resource_count: scopeResourceCount,
      resource_scopes: scopes,
    },
    request: {
      operation: string(request.operation, "access authorization.request.operation"),
      resource_domain_digest: string(request.resource_domain_digest, "access authorization.request.resource_domain_digest"),
      resource_id_digest: string(request.resource_id_digest, "access authorization.request.resource_id_digest"),
      resource_identity_exposed: false,
      resource_state: string(request.resource_state, "access authorization.request.resource_state"),
      requested_at: string(request.requested_at, "access authorization.request.requested_at"),
    },
    policy: { deny_by_default: true, grant_count: grantCount, grants },
    evaluation: {
      principal_active: boolean(evaluation.principal_active, "access authorization.evaluation.principal_active"),
      resource_scope_match: boolean(evaluation.resource_scope_match, "access authorization.evaluation.resource_scope_match"),
      matching_grant_count: number(evaluation.matching_grant_count, "access authorization.evaluation.matching_grant_count"),
      recorded_decision_present: recordedPresent,
      recorded_decision_verified: recordedVerified,
      policy_replay_verified: true,
    },
    decision: {
      allowed: boolean(decision.allowed, "access authorization.decision.allowed"),
      reason: string(decision.reason, "access authorization.decision.reason"),
      matched_role: nullableString(decision.matched_role, "access authorization.decision.matched_role"),
      operation: string(decision.operation, "access authorization.decision.operation"),
      resource_state: string(decision.resource_state, "access authorization.decision.resource_state"),
      principal_id_digest: string(decision.principal_id_digest, "access authorization.decision.principal_id_digest"),
      resource_domain_digest: string(decision.resource_domain_digest, "access authorization.decision.resource_domain_digest"),
      resource_id_digest: string(decision.resource_id_digest, "access authorization.decision.resource_id_digest"),
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
    limitations: strings(source.limitations, "access authorization.limitations"),
  };
}


function parseDataLifecycleDecision(
  value: unknown,
  field: string,
): DataLifecycleDecisionView {
  const source = object(value, field);
  if (hasOwn(source, "object_id") || source.object_id_exposed !== false) {
    throw new Error(`${field} must not expose raw object identity`);
  }
  return {
    sensitivity: string(source.sensitivity, `${field}.sensitivity`),
    policy_id: string(source.policy_id, `${field}.policy_id`),
    retain_until: nullableString(source.retain_until, `${field}.retain_until`),
    expired: boolean(source.expired, `${field}.expired`),
    storage_allowed: boolean(source.storage_allowed, `${field}.storage_allowed`),
    telemetry_allowed: boolean(source.telemetry_allowed, `${field}.telemetry_allowed`),
    disclosure_allowed: boolean(source.disclosure_allowed, `${field}.disclosure_allowed`),
    deletion_allowed: boolean(source.deletion_allowed, `${field}.deletion_allowed`),
    reasons: strings(source.reasons, `${field}.reasons`),
    object_id_digest: string(source.object_id_digest, `${field}.object_id_digest`),
    object_id_exposed: false,
  };
}

export function parseDataGovernance(value: unknown): DataGovernanceView {
  const source = object(value, "data governance");
  exactKeys(source, ["schema_version", "source", "privacy_governance_runtime", "object", "policy", "durable_retention", "current_decision", "recorded_decision", "deletion", "confidentiality_requirements", "authorization", "limitations"], "data governance");
  if (source.schema_version !== "data-governance-investigation.v2") {
    throw new Error("unsupported data governance schema");
  }
  const sourceBoundary = object(source.source, "data governance.source");
  exactKeys(sourceBoundary, ["resource", "configured", "source_path_exposed", "workspace_authority", "second_lifecycle_store_created", "privacy_governance_snapshot_configured"], "data governance.source");
  if (
    sourceBoundary.resource !== "explicit-lifecycle-context-plus-workspace-metadata" ||
    sourceBoundary.configured !== true ||
    sourceBoundary.source_path_exposed !== false ||
    sourceBoundary.workspace_authority !== true ||
    sourceBoundary.second_lifecycle_store_created !== false ||
    typeof sourceBoundary.privacy_governance_snapshot_configured !== "boolean"
  ) {
    throw new Error("data governance source boundary is unsupported");
  }


  const runtimeSource = object(source.privacy_governance_runtime, "data governance.privacy_governance_runtime");
  let privacyGovernanceRuntime: DataGovernanceView["privacy_governance_runtime"];
  if (runtimeSource.observed === false) {
    exactKeys(runtimeSource, ["observed", "defaults_inferred", "source_path_exposed"], "data governance.privacy_governance_runtime");
    if (runtimeSource.defaults_inferred !== false || runtimeSource.source_path_exposed !== false) {
      throw new Error("data governance must not infer an unobserved privacy runtime");
    }
    privacyGovernanceRuntime = { observed: false, defaults_inferred: false, source_path_exposed: false };
  } else if (runtimeSource.observed === true) {
    exactKeys(runtimeSource, ["observed", "defaults_inferred", "source_path_exposed", "snapshot_digest", "privacy_policy", "evidence_policy", "opaque_content_secret_scanning"], "data governance.privacy_governance_runtime");
    if (runtimeSource.defaults_inferred !== false || runtimeSource.source_path_exposed !== false || runtimeSource.opaque_content_secret_scanning !== false) {
      throw new Error("data governance privacy runtime overstates its enforcement boundary");
    }
    const privacyPolicy = object(runtimeSource.privacy_policy, "data governance.privacy_governance_runtime.privacy_policy");
    exactKeys(privacyPolicy, ["policy_id", "redact_key_count", "regex_rule_count", "patterns_exposed", "metadata_redaction_before_receipt_identity"], "data governance.privacy_governance_runtime.privacy_policy");
    if (privacyPolicy.patterns_exposed !== false || privacyPolicy.metadata_redaction_before_receipt_identity !== true) {
      throw new Error("data governance privacy redaction assurance is unsupported");
    }
    const evidencePolicy = object(runtimeSource.evidence_policy, "data governance.privacy_governance_runtime.evidence_policy");
    exactKeys(evidencePolicy, ["policy_id", "storage_max_sensitivity", "telemetry_max_sensitivity", "require_digest_for", "storage_governance_before_artifact_write", "workspace_sensitivity_indexing", "telemetry_manifest_projection_supported", "telemetry_runtime_binding_observed"], "data governance.privacy_governance_runtime.evidence_policy");
    if (
      evidencePolicy.storage_governance_before_artifact_write !== true ||
      evidencePolicy.workspace_sensitivity_indexing !== true ||
      evidencePolicy.telemetry_manifest_projection_supported !== true ||
      evidencePolicy.telemetry_runtime_binding_observed !== false
    ) {
      throw new Error("data governance evidence-governance assurance is unsupported");
    }
    const redactKeyCount = number(privacyPolicy.redact_key_count, "data governance privacy redact_key_count");
    const regexRuleCount = number(privacyPolicy.regex_rule_count, "data governance privacy regex_rule_count");
    if (!Number.isInteger(redactKeyCount) || redactKeyCount < 0 || !Number.isInteger(regexRuleCount) || regexRuleCount < 0) {
      throw new Error("data governance privacy policy counts must be non-negative integers");
    }
    privacyGovernanceRuntime = {
      observed: true,
      defaults_inferred: false,
      source_path_exposed: false,
      snapshot_digest: string(runtimeSource.snapshot_digest, "data governance privacy snapshot_digest"),
      privacy_policy: {
        policy_id: string(privacyPolicy.policy_id, "data governance privacy policy_id"),
        redact_key_count: redactKeyCount,
        regex_rule_count: regexRuleCount,
        patterns_exposed: false,
        metadata_redaction_before_receipt_identity: true,
      },
      evidence_policy: {
        policy_id: string(evidencePolicy.policy_id, "data governance evidence policy_id"),
        storage_max_sensitivity: string(evidencePolicy.storage_max_sensitivity, "data governance evidence storage_max_sensitivity"),
        telemetry_max_sensitivity: string(evidencePolicy.telemetry_max_sensitivity, "data governance evidence telemetry_max_sensitivity"),
        require_digest_for: strings(evidencePolicy.require_digest_for, "data governance evidence require_digest_for"),
        storage_governance_before_artifact_write: true,
        workspace_sensitivity_indexing: true,
        telemetry_manifest_projection_supported: true,
        telemetry_runtime_binding_observed: false,
      },
      opaque_content_secret_scanning: false,
    };
  } else {
    throw new Error("data governance privacy runtime observed must be a boolean");
  }
  if (sourceBoundary.privacy_governance_snapshot_configured !== privacyGovernanceRuntime.observed) {
    throw new Error("data governance privacy snapshot availability is inconsistent");
  }

  const objectSource = object(source.object, "data governance.object");
  if (hasOwn(objectSource, "object_id") || objectSource.object_id_exposed !== false) {
    throw new Error("data governance must not expose raw object identity");
  }
  const rawKind = string(objectSource.kind, "data governance.object.kind");
  if (rawKind !== "workspace-record" && rawKind !== "workspace-export") {
    throw new Error("unsupported data governance object kind");
  }
  const kind: "workspace-record" | "workspace-export" = rawKind;
  const objectView = {
    kind,
    object_id_digest: string(objectSource.object_id_digest, "data governance.object.object_id_digest"),
    object_id_exposed: false as const,
    sensitivity: string(objectSource.sensitivity, "data governance.object.sensitivity"),
    created_at: string(objectSource.created_at, "data governance.object.created_at"),
    original_digest: nullableString(objectSource.original_digest, "data governance.object.original_digest"),
  };

  const policy = object(source.policy, "data governance.policy");
  const maxRetention = nullableNumber(policy.max_retention_days, "data governance.policy.max_retention_days");
  if (maxRetention !== null && (!Number.isInteger(maxRetention) || maxRetention < 0)) {
    throw new Error("data governance max_retention_days must be a non-negative integer or null");
  }
  const policyView = {
    policy_id: string(policy.policy_id, "data governance.policy.policy_id"),
    purpose: string(policy.purpose, "data governance.policy.purpose"),
    max_retention_days: maxRetention,
    storage_max_sensitivity: string(policy.storage_max_sensitivity, "data governance.policy.storage_max_sensitivity"),
    telemetry_max_sensitivity: string(policy.telemetry_max_sensitivity, "data governance.policy.telemetry_max_sensitivity"),
    disclosure_max_sensitivity: string(policy.disclosure_max_sensitivity, "data governance.policy.disclosure_max_sensitivity"),
    encryption_at_rest_required: boolean(policy.encryption_at_rest_required, "data governance.policy.encryption_at_rest_required"),
    tls_required: boolean(policy.tls_required, "data governance.policy.tls_required"),
  };

  const retention = object(source.durable_retention, "data governance.durable_retention");
  if (retention.present !== true || retention.context_cross_check_verified !== true) {
    throw new Error("data governance durable retention must be cross-check verified");
  }
  const retentionView = {
    present: true as const,
    policy_id: string(retention.policy_id, "data governance.durable_retention.policy_id"),
    sensitivity: string(retention.sensitivity, "data governance.durable_retention.sensitivity"),
    retain_until: nullableString(retention.retain_until, "data governance.durable_retention.retain_until"),
    legal_hold: boolean(retention.legal_hold, "data governance.durable_retention.legal_hold"),
    context_cross_check_verified: true as const,
  };

  const currentSource = object(source.current_decision, "data governance.current_decision");
  if (currentSource.policy_replay_verified !== true) {
    throw new Error("data governance current decision must be policy-replay verified");
  }
  const currentDecision = {
    ...parseDataLifecycleDecision(currentSource, "data governance.current_decision"),
    policy_replay_verified: true as const,
    deletion_already_recorded: boolean(
      currentSource.deletion_already_recorded,
      "data governance.current_decision.deletion_already_recorded",
    ),
  };

  const recordedSource = object(source.recorded_decision, "data governance.recorded_decision");
  let recordedDecision: DataGovernanceView["recorded_decision"];
  if (recordedSource.present === false) {
    recordedDecision = { present: false };
  } else if (recordedSource.present === true) {
    if (recordedSource.policy_replay_verified !== true) {
      throw new Error("data governance recorded decision must be policy-replay verified");
    }
    recordedDecision = {
      present: true,
      evaluated_at: string(recordedSource.evaluated_at, "data governance.recorded_decision.evaluated_at"),
      decision: parseDataLifecycleDecision(recordedSource.decision, "data governance.recorded_decision.decision"),
      policy_replay_verified: true,
    };
  } else {
    throw new Error("data governance recorded_decision.present must be a boolean");
  }

  const deletionSource = object(source.deletion, "data governance.deletion");
  let deletion: DataGovernanceView["deletion"];
  if (deletionSource.present === false) {
    if (deletionSource.payload_erasure_outside_statewake_evaluated !== false) {
      throw new Error("data governance must not infer external payload erasure");
    }
    deletion = {
      present: false,
      payload_erasure_outside_statewake_evaluated: false,
    };
  } else if (deletionSource.present === true) {
    if (
      deletionSource.tombstone_cross_check_verified !== true ||
      deletionSource.payload_content_retained_in_tombstone !== false ||
      deletionSource.payload_erasure_outside_statewake_evaluated !== false
    ) {
      throw new Error("data governance deletion boundary is unsupported");
    }
    deletion = {
      present: true,
      digest: string(deletionSource.digest, "data governance.deletion.digest"),
      sensitivity: string(deletionSource.sensitivity, "data governance.deletion.sensitivity"),
      deleted_at: string(deletionSource.deleted_at, "data governance.deletion.deleted_at"),
      policy_id: string(deletionSource.policy_id, "data governance.deletion.policy_id"),
      reason: string(deletionSource.reason, "data governance.deletion.reason"),
      tombstone_cross_check_verified: true,
      payload_content_retained_in_tombstone: false,
      payload_erasure_outside_statewake_evaluated: false,
    };
  } else {
    throw new Error("data governance deletion.present must be a boolean");
  }

  const confidentiality = object(source.confidentiality_requirements, "data governance.confidentiality_requirements");
  if (confidentiality.host_requirement_satisfaction_evaluated !== false) {
    throw new Error("data governance must not claim host confidentiality requirements were verified");
  }
  const confidentialityView = {
    encryption_at_rest_required: boolean(confidentiality.encryption_at_rest_required, "data governance.confidentiality_requirements.encryption_at_rest_required"),
    tls_required: boolean(confidentiality.tls_required, "data governance.confidentiality_requirements.tls_required"),
    host_requirement_satisfaction_evaluated: false as const,
  };

  const authorization = object(source.authorization, "data governance.authorization");
  if (
    authorization.deletion_executed_by_this_view !== false ||
    authorization.disclosure_executed_by_this_view !== false ||
    authorization.business_authorization_inferred !== false ||
    authorization.compliance_certified !== false
  ) {
    throw new Error("data governance read view must not claim write or authorization effects");
  }

  if (
    retentionView.policy_id !== policyView.policy_id ||
    retentionView.sensitivity !== objectView.sensitivity ||
    currentDecision.policy_id !== policyView.policy_id ||
    currentDecision.sensitivity !== objectView.sensitivity ||
    currentDecision.object_id_digest !== objectView.object_id_digest ||
    currentDecision.retain_until !== retentionView.retain_until
  ) {
    throw new Error("data governance lifecycle bindings are inconsistent");
  }
  if (recordedDecision.present && (
    recordedDecision.decision.policy_id !== policyView.policy_id ||
    recordedDecision.decision.sensitivity !== objectView.sensitivity ||
    recordedDecision.decision.object_id_digest !== objectView.object_id_digest
  )) {
    throw new Error("data governance recorded decision binding is inconsistent");
  }
  if (deletion.present && (
    deletion.policy_id !== policyView.policy_id ||
    deletion.sensitivity !== objectView.sensitivity ||
    (objectView.original_digest !== null && deletion.digest !== objectView.original_digest)
  )) {
    throw new Error("data governance deletion binding is inconsistent");
  }
  if (currentDecision.deletion_already_recorded !== deletion.present) {
    throw new Error("data governance deletion status is inconsistent");
  }
  if (
    confidentialityView.encryption_at_rest_required !== policyView.encryption_at_rest_required ||
    confidentialityView.tls_required !== policyView.tls_required
  ) {
    throw new Error("data governance confidentiality requirements are inconsistent");
  }

  return {
    schema_version: "data-governance-investigation.v2",
    source: {
      resource: "explicit-lifecycle-context-plus-workspace-metadata",
      configured: true,
      source_path_exposed: false,
      workspace_authority: true,
      second_lifecycle_store_created: false,
      privacy_governance_snapshot_configured: privacyGovernanceRuntime.observed,
    },
    privacy_governance_runtime: privacyGovernanceRuntime,
    object: objectView,
    policy: policyView,
    durable_retention: retentionView,
    current_decision: currentDecision,
    recorded_decision: recordedDecision,
    deletion,
    confidentiality_requirements: confidentialityView,
    authorization: {
      deletion_executed_by_this_view: false,
      disclosure_executed_by_this_view: false,
      business_authorization_inferred: false,
      compliance_certified: false,
    },
    limitations: strings(source.limitations, "data governance.limitations"),
  };
}
