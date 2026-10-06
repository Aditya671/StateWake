import axios, { type AxiosRequestConfig } from "axios";
import type {
  AccessAuthorizationView,
  AssuranceDecisionView,
  AttestationTrustView,
  CaptureHealthView,
  ClaimCatalog,
  ClaimComparison,
  ClaimDetail,
  ClaimHistory,
  DataGovernanceView,
  DecisionLineageView,
  EvidenceTrace,
  HumanApprovalInput,
  HumanApprovalLifecycleInput,
  HumanApprovalLifecycleResult,
  HumanApprovalResult,
  HumanApprovalThread,
  IncidentDetail,
  IncidentPortfolio,
  OverviewProjection,
  ReleaseTrustView,
  ReliabilityProofInvestigationView,
  SecurityAssuranceView,
  ReviewCapabilities,
  ReviewStatementInput,
  ReviewStatementResult,
  ReviewThread,
  ValidationStudyView,
  WorkspaceOperationsView,
} from "./dto";
import { normalizeApiError } from "./errors";
import {
  parseAccessAuthorization,
  parseAssuranceDecision,
  parseAttestationTrust,
  parseCaptureHealth,
  parseClaimCatalog,
  parseClaimComparison,
  parseClaimDetail,
  parseClaimHistory,
  parseDataGovernance,
  parseDecisionLineage,
  parseEvidenceTrace,
  parseHumanApprovalLifecycleResult,
  parseHumanApprovalResult,
  parseHumanApprovalThread,
  parseIncidentDetail,
  parseIncidentPortfolio,
  parseOverviewProjection,
  parseReleaseTrustView,
  parseReliabilityProofInvestigation,
  parseSecurityAssurance,
  parseReviewCapabilities,
  parseReviewStatementResult,
  parseReviewThread,
  parseValidationStudyView,
  parseWorkspaceOperationsView,
} from "./schemas";

function signalConfig(signal?: AbortSignal): AxiosRequestConfig {
  return signal === undefined ? {} : { signal };
}

const transport = axios.create({
  baseURL: "/api/statewake",
  timeout: 15_000,
  headers: { Accept: "application/json" },
});

transport.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(normalizeApiError(error)),
);


export async function getOverview(
  signal?: AbortSignal,
): Promise<OverviewProjection> {
  const response = await transport.get("/api/v1/overview", signalConfig(signal));
  return parseOverviewProjection(response.data);
}


export async function getAssuranceDecision(
  signal?: AbortSignal,
): Promise<AssuranceDecisionView> {
  const response = await transport.get(
    "/api/v1/assurance-decision",
    signalConfig(signal),
  );
  return parseAssuranceDecision(response.data);
}

export async function getAccessAuthorization(
  signal?: AbortSignal,
): Promise<AccessAuthorizationView> {
  const response = await transport.get(
    "/api/v1/authorization-policy",
    signalConfig(signal),
  );
  return parseAccessAuthorization(response.data);
}

export async function getDataGovernance(
  signal?: AbortSignal,
): Promise<DataGovernanceView> {
  const response = await transport.get(
    "/api/v1/data-governance",
    signalConfig(signal),
  );
  return parseDataGovernance(response.data);
}

export async function getReliabilityProofInvestigation(
  signal?: AbortSignal,
): Promise<ReliabilityProofInvestigationView> {
  const response = await transport.get(
    "/api/v1/proof-bundle",
    signalConfig(signal),
  );
  return parseReliabilityProofInvestigation(response.data);
}

export async function getDecisionLineage(
  signal?: AbortSignal,
): Promise<DecisionLineageView> {
  const response = await transport.get(
    "/api/v1/decision-lineage",
    signalConfig(signal),
  );
  return parseDecisionLineage(response.data);
}

export async function getReleaseTrust(
  signal?: AbortSignal,
): Promise<ReleaseTrustView> {
  const response = await transport.get(
    "/api/v1/release-trust",
    signalConfig(signal),
  );
  return parseReleaseTrustView(response.data);
}

export async function getValidationStudy(
  signal?: AbortSignal,
): Promise<ValidationStudyView> {
  const response = await transport.get(
    "/api/v1/validation-study",
    signalConfig(signal),
  );
  return parseValidationStudyView(response.data);
}

export async function getWorkspaceOperations(
  limit = 50,
  offset = 0,
  signal?: AbortSignal,
): Promise<WorkspaceOperationsView> {
  const config: AxiosRequestConfig = {
    ...signalConfig(signal),
    params: { limit, offset },
  };
  const response = await transport.get("/api/v1/workspace/operations", config);
  return parseWorkspaceOperationsView(response.data);
}



export interface SecurityAssuranceRequest {
  event?: string;
  operation?: string;
  reason?: string;
  method?: string;
  limit?: number;
  offset?: number;
}

export async function getSecurityAssurance(
  request: SecurityAssuranceRequest = {},
  signal?: AbortSignal,
): Promise<SecurityAssuranceView> {
  const params: Record<string, string | number> = {};
  if (request.event) params.event = request.event;
  if (request.operation) params.operation = request.operation;
  if (request.reason) params.reason = request.reason;
  if (request.method) params.method = request.method;
  if (request.limit !== undefined) params.limit = request.limit;
  if (request.offset !== undefined) params.offset = request.offset;
  const response = await transport.get("/api/v1/security-assurance", {
    ...signalConfig(signal),
    params,
  });
  return parseSecurityAssurance(response.data);
}

export interface AttestationTrustRequest {
  decision?: string;
  reliabilityState?: string;
  keyStatus?: string;
  text?: string;
  limit?: number;
  offset?: number;
}

export async function getAttestationTrust(
  request: AttestationTrustRequest = {},
  signal?: AbortSignal,
): Promise<AttestationTrustView> {
  const params: Record<string, string | number> = {};
  if (request.decision) params.decision = request.decision;
  if (request.reliabilityState) params.reliability_state = request.reliabilityState;
  if (request.keyStatus) params.key_status = request.keyStatus;
  if (request.text) params.q = request.text;
  if (request.limit !== undefined) params.limit = request.limit;
  if (request.offset !== undefined) params.offset = request.offset;
  const response = await transport.get("/api/v1/attestation-trust", {
    ...signalConfig(signal),
    params,
  });
  return parseAttestationTrust(response.data);
}

export interface CaptureHealthRequest {
  stage?: string;
  errorType?: string;
  limit?: number;
  offset?: number;
}

export async function getCaptureHealth(
  request: CaptureHealthRequest = {},
  signal?: AbortSignal,
): Promise<CaptureHealthView> {
  const params: Record<string, string | number> = {};
  if (request.stage) params.stage = request.stage;
  if (request.errorType) params.error_type = request.errorType;
  if (request.limit !== undefined) params.limit = request.limit;
  if (request.offset !== undefined) params.offset = request.offset;
  const response = await transport.get("/api/v1/capture-health", {
    ...signalConfig(signal),
    params,
  });
  return parseCaptureHealth(response.data);
}

export interface IncidentPortfolioRequest {
  status?: string;
  category?: string;
  text?: string;
  limit?: number;
  offset?: number;
}

export async function getIncidentPortfolio(
  request: IncidentPortfolioRequest = {},
  signal?: AbortSignal,
): Promise<IncidentPortfolio> {
  const params: Record<string, string | number> = {};
  if (request.status) params.status = request.status;
  if (request.category) params.category = request.category;
  if (request.text) params.q = request.text;
  if (request.limit !== undefined) params.limit = request.limit;
  if (request.offset !== undefined) params.offset = request.offset;
  const response = await transport.get("/api/v1/incidents", {
    ...signalConfig(signal),
    params,
  });
  return parseIncidentPortfolio(response.data);
}

export async function getIncidentDetail(
  incidentId: string,
  signal?: AbortSignal,
): Promise<IncidentDetail> {
  const response = await transport.get(
    `/api/v1/incidents/${encodeURIComponent(incidentId)}`,
    signalConfig(signal),
  );
  return parseIncidentDetail(response.data);
}

export interface ClaimCatalogRequest {
  decision?: string;
  verified?: boolean;
  approvalStatus?: string;
  profileId?: string;
  candidateId?: string;
  text?: string;
  limit?: number;
  offset?: number;
}

export async function getClaimCatalog(
  request: ClaimCatalogRequest = {},
  signal?: AbortSignal,
): Promise<ClaimCatalog> {
  const params: Record<string, string | number | boolean> = {};
  if (request.decision) params.decision = request.decision;
  if (request.verified !== undefined) params.verified = request.verified;
  if (request.approvalStatus) params.approval_status = request.approvalStatus;
  if (request.profileId) params.profile_id = request.profileId;
  if (request.candidateId) params.candidate_id = request.candidateId;
  if (request.text) params.q = request.text;
  if (request.limit !== undefined) params.limit = request.limit;
  if (request.offset !== undefined) params.offset = request.offset;
  const response = await transport.get("/api/v1/claims", {
    ...signalConfig(signal),
    params,
  });
  return parseClaimCatalog(response.data);
}

export async function getClaimDetail(
  recordId: string,
  signal?: AbortSignal,
): Promise<ClaimDetail> {
  const response = await transport.get(
    `/api/v1/claims/${encodeURIComponent(recordId)}`,
    signalConfig(signal),
  );
  return parseClaimDetail(response.data);
}

export async function getClaimHistory(
  recordId: string,
  signal?: AbortSignal,
): Promise<ClaimHistory> {
  const response = await transport.get(
    `/api/v1/claims/${encodeURIComponent(recordId)}/history`,
    signalConfig(signal),
  );
  return parseClaimHistory(response.data);
}

export async function getEvidenceTrace(
  recordId: string,
  signal?: AbortSignal,
): Promise<EvidenceTrace> {
  const response = await transport.get(
    `/api/v1/claims/${encodeURIComponent(recordId)}/evidence`,
    signalConfig(signal),
  );
  return parseEvidenceTrace(response.data);
}

export async function getClaimComparison(
  leftRecordId: string,
  rightRecordId: string,
  signal?: AbortSignal,
): Promise<ClaimComparison> {
  const response = await transport.get(
    `/api/v1/claims/${encodeURIComponent(leftRecordId)}/compare/${encodeURIComponent(rightRecordId)}`,
    signalConfig(signal),
  );
  return parseClaimComparison(response.data);
}

export async function getCanonicalJson(
  path: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await transport.get<string>(path, {
    ...signalConfig(signal),
    responseType: "text",
    headers: { Accept: "application/json" },
  });
  return response.data;
}

export async function getCanonicalMarkdown(
  path: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await transport.get<string>(path, {
    ...signalConfig(signal),
    responseType: "text",
    headers: { Accept: "text/markdown" },
  });
  return response.data;
}


const reviewTransport = axios.create({
  baseURL: "/api/statewake-review",
  timeout: 15_000,
  headers: { Accept: "application/json" },
});

reviewTransport.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(normalizeApiError(error)),
);

export async function getReviewCapabilities(
  signal?: AbortSignal,
): Promise<ReviewCapabilities> {
  const response = await reviewTransport.get(
    "/api/v1/review-capabilities",
    signalConfig(signal),
  );
  return parseReviewCapabilities(response.data);
}

export async function getReviewThread(
  recordId: string,
  signal?: AbortSignal,
): Promise<ReviewThread> {
  const response = await reviewTransport.get(
    `/api/v1/claims/${encodeURIComponent(recordId)}/reviews`,
    signalConfig(signal),
  );
  return parseReviewThread(response.data);
}

export async function createReviewStatement(
  recordId: string,
  input: ReviewStatementInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<ReviewStatementResult> {
  const response = await reviewTransport.post(
    `/api/v1/claims/${encodeURIComponent(recordId)}/reviews`,
    input,
    {
      ...signalConfig(signal),
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "If-Match": `"${input.report_digest}"`,
      },
    },
  );
  return parseReviewStatementResult(response.data);
}


export async function getHumanApprovals(
  recordId: string,
  signal?: AbortSignal,
): Promise<HumanApprovalThread> {
  const response = await reviewTransport.get(
    `/api/v1/claims/${encodeURIComponent(recordId)}/approvals`,
    signalConfig(signal),
  );
  return parseHumanApprovalThread(response.data);
}

export async function createHumanApproval(
  recordId: string,
  input: HumanApprovalInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<HumanApprovalResult> {
  const response = await reviewTransport.post(
    `/api/v1/claims/${encodeURIComponent(recordId)}/approvals`,
    input,
    {
      ...signalConfig(signal),
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "If-Match": `"${input.report_digest}"`,
      },
    },
  );
  return parseHumanApprovalResult(response.data);
}

async function transitionHumanApproval(
  recordId: string,
  approvalReceiptId: string,
  operation: "revoke" | "supersede",
  input: HumanApprovalLifecycleInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<HumanApprovalLifecycleResult> {
  const response = await reviewTransport.post(
    `/api/v1/claims/${encodeURIComponent(recordId)}/approvals/${encodeURIComponent(approvalReceiptId)}/${operation}`,
    input,
    {
      ...signalConfig(signal),
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "If-Match": `"${input.report_digest}"`,
      },
    },
  );
  return parseHumanApprovalLifecycleResult(response.data);
}

export async function revokeHumanApproval(
  recordId: string,
  approvalReceiptId: string,
  input: HumanApprovalLifecycleInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<HumanApprovalLifecycleResult> {
  return transitionHumanApproval(
    recordId,
    approvalReceiptId,
    "revoke",
    input,
    idempotencyKey,
    signal,
  );
}

export async function supersedeHumanApproval(
  recordId: string,
  approvalReceiptId: string,
  input: HumanApprovalLifecycleInput,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<HumanApprovalLifecycleResult> {
  return transitionHumanApproval(
    recordId,
    approvalReceiptId,
    "supersede",
    input,
    idempotencyKey,
    signal,
  );
}

