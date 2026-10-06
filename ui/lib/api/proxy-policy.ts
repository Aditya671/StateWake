const RECEIPT_ID = /^[0-9a-f]{64}$/;
const WORKSPACE_QUERY_KEYS = new Set(["limit", "offset"]);
const CLAIM_QUERY_KEYS = new Set([
  "decision",
  "verified",
  "approval_status",
  "profile_id",
  "candidate_id",
  "q",
  "limit",
  "offset",
]);
const CLAIM_QUERY_MAX = 256;
const CLAIM_TEXT_MAX = 200;
const INCIDENT_QUERY_KEYS = new Set(["status", "category", "q", "limit", "offset"]);
const CAPTURE_HEALTH_QUERY_KEYS = new Set(["stage", "error_type", "limit", "offset"]);
const SECURITY_ASSURANCE_QUERY_KEYS = new Set(["event", "operation", "reason", "method", "limit", "offset"]);
const SECURITY_AUDIT_EVENTS = new Set(["authentication_failed", "authorization_denied", "request_rejected", "request_admitted"]);
const SECURITY_AUDIT_OPERATIONS = new Set(["verify:evidence", "verify:proof", "review:read", "review:write", "approval:read", "approval:write"]);
const SECURITY_AUDIT_REASONS = new Set(["https_required", "authentication_failed", "authorization_denied", "request_admission_rejected", "authorized", "other-recorded-reason"]);
const ATTESTATION_TRUST_QUERY_KEYS = new Set([
  "decision",
  "reliability_state",
  "key_status",
  "q",
  "limit",
  "offset",
]);
const ATTESTATION_KEY_STATUSES = new Set([
  "active",
  "revoked",
  "superseded",
  "untrusted",
  "unsigned",
  "trust-state-unauthenticated",
  "trust-state-unconfigured",
]);
const INCIDENT_STATUSES = new Set([
  "detected",
  "preserved",
  "contained",
  "assessed",
  "recovered",
  "reverified",
]);

export function isAllowedReadApiPath(parts: readonly string[]): boolean {
  if (parts.length === 3) {
    return (
      parts[0] === "api" &&
      parts[1] === "v1" &&
      ["capabilities", "overview", "claims", "incidents", "capture-health", "security-assurance", "assurance-decision", "authorization-policy", "data-governance", "attestation-trust", "proof-bundle", "decision-lineage", "release-trust", "validation-study"].includes(
        parts[2] ?? "",
      )
    );
  }
  if (parts.length === 4) {
    if (
      parts[0] === "api" &&
      parts[1] === "v1" &&
      parts[2] === "workspace" &&
      parts[3] === "operations"
    ) {
      return true;
    }
    return (
      parts[0] === "api" &&
      parts[1] === "v1" &&
      (parts[2] === "claims" || parts[2] === "reports" || parts[2] === "incidents") &&
      RECEIPT_ID.test(parts[3] ?? "")
    );
  }
  if (parts.length === 5) {
    return (
      parts[0] === "api" &&
      parts[1] === "v1" &&
      RECEIPT_ID.test(parts[3] ?? "") &&
      ((parts[2] === "claims" &&
        ["summary", "history", "evidence"].includes(parts[4] ?? "")) ||
        (parts[2] === "reports" && parts[4] === "markdown"))
    );
  }
  if (parts.length === 6) {
    return (
      parts[0] === "api" &&
      parts[1] === "v1" &&
      parts[2] === "claims" &&
      RECEIPT_ID.test(parts[3] ?? "") &&
      parts[4] === "compare" &&
      RECEIPT_ID.test(parts[5] ?? "")
    );
  }
  return false;
}

export function isAllowedReadApiQuery(
  parts: readonly string[],
  searchParams: URLSearchParams,
): boolean {
  if (searchParams.size === 0) return true;
  const workspaceOperations =
    parts.length === 4 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "workspace" &&
    parts[3] === "operations";
  const claimCatalog =
    parts.length === 3 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "claims";
  const incidentPortfolio =
    parts.length === 3 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "incidents";
  const captureHealth =
    parts.length === 3 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "capture-health";
  const attestationTrust =
    parts.length === 3 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "attestation-trust";
  const securityAssurance =
    parts.length === 3 &&
    parts[0] === "api" &&
    parts[1] === "v1" &&
    parts[2] === "security-assurance";
  if (!workspaceOperations && !claimCatalog && !incidentPortfolio && !captureHealth && !attestationTrust && !securityAssurance) return false;

  const allowed = claimCatalog
    ? CLAIM_QUERY_KEYS
    : incidentPortfolio
      ? INCIDENT_QUERY_KEYS
      : captureHealth
        ? CAPTURE_HEALTH_QUERY_KEYS
        : securityAssurance
          ? SECURITY_ASSURANCE_QUERY_KEYS
          : attestationTrust
            ? ATTESTATION_TRUST_QUERY_KEYS
            : WORKSPACE_QUERY_KEYS;
  for (const key of searchParams.keys()) {
    if (!allowed.has(key)) return false;
    if (searchParams.getAll(key).length !== 1) return false;
  }
  const limit = searchParams.get("limit");
  const offset = searchParams.get("offset");
  if (
    limit !== null &&
    (!/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > 200)
  ) {
    return false;
  }
  if (offset !== null && (!/^\d+$/.test(offset) || Number(offset) < 0)) {
    return false;
  }
  if (securityAssurance) {
    const event = searchParams.get("event");
    if (event !== null && !SECURITY_AUDIT_EVENTS.has(event)) return false;
    const operation = searchParams.get("operation");
    if (operation !== null && !SECURITY_AUDIT_OPERATIONS.has(operation)) return false;
    const reason = searchParams.get("reason");
    if (reason !== null && !SECURITY_AUDIT_REASONS.has(reason)) return false;
    const method = searchParams.get("method");
    if (method !== null && (!/^[A-Za-z]{1,16}$/.test(method) || method !== method.trim())) return false;
    return true;
  }
  if (attestationTrust) {
    const decision = searchParams.get("decision");
    if (decision !== null && !new Set(["accept", "review", "reject"]).has(decision)) return false;
    const reliabilityState = searchParams.get("reliability_state");
    if (reliabilityState !== null && !new Set(["reliable", "degraded", "unreliable", "recovered"]).has(reliabilityState)) return false;
    const keyStatus = searchParams.get("key_status");
    if (keyStatus !== null && !ATTESTATION_KEY_STATUSES.has(keyStatus)) return false;
    const text = searchParams.get("q");
    if (text !== null && (text.trim().length === 0 || text.length > CLAIM_TEXT_MAX)) return false;
    return true;
  }
  if (captureHealth) {
    for (const key of ["stage", "error_type"]) {
      const value = searchParams.get(key);
      if (value !== null && (value.trim().length === 0 || value.length > 128)) {
        return false;
      }
    }
    return true;
  }
  if (incidentPortfolio) {
    const status = searchParams.get("status");
    if (status !== null && !INCIDENT_STATUSES.has(status)) return false;
    const category = searchParams.get("category");
    if (category !== null && (category.trim().length === 0 || category.length > CLAIM_QUERY_MAX)) {
      return false;
    }
    const text = searchParams.get("q");
    if (text !== null && (text.trim().length === 0 || text.length > CLAIM_TEXT_MAX)) {
      return false;
    }
    return true;
  }
  if (!claimCatalog) return true;

  const verified = searchParams.get("verified");
  if (verified !== null && verified !== "true" && verified !== "false") return false;
  for (const key of ["decision", "approval_status", "profile_id", "candidate_id"]) {
    const value = searchParams.get(key);
    if (value !== null && (value.trim().length === 0 || value.length > CLAIM_QUERY_MAX)) {
      return false;
    }
  }
  const text = searchParams.get("q");
  if (text !== null && (text.trim().length === 0 || text.length > CLAIM_TEXT_MAX)) {
    return false;
  }
  return true;
}

export function encodedReadApiPath(parts: readonly string[]): string {
  if (!isAllowedReadApiPath(parts)) {
    throw new Error("unsupported StateWake read API path");
  }
  return `/${parts.map(encodeURIComponent).join("/")}`;
}
