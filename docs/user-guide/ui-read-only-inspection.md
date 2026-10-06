# Read-only human inspection UI

StateWake's browser-facing slice is an **optional local inspection surface** for durable reliability verification reports. It does not replace `statewake.server`, claim-profile evaluation, report validation, workspace storage, approval contracts, or release authorization.

## Implemented scope

The current slice exposes bounded discovery plus source-bound investigation:

```text
workspace verification-report receipts
  -> bounded canonical claim catalog
  -> exact report selection / two-report comparison

workspace verification-report receipt
  -> content-addressed report artifact
  -> ReliabilityVerificationReport.from_dict()
  -> deterministic claim-detail projection
  -> read-only JSON API
  -> Claim workbench
     - Summary
     - Checks
     - Evidence explorer (recorded relationship graph + table)
     - History
     - canonical JSON
     - canonical Markdown
```

The UI always keeps these distinct: report decision, verification execution, evidence availability, and human approval status. It does not compute an overall trust score.

## Read API

Start the dependency-free local adapter from the repository environment:

```powershell
$env:STATEWAKE_UI_WORKSPACE_ROOT = "C:\path\to\existing\statewake-workspace"
$env:STATEWAKE_UI_INCIDENT_EVIDENCE = "C:\path\to\incident-evidence.jsonl"  # optional
$env:STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL = "C:\path\to\capture-failures.jsonl"  # optional
$env:STATEWAKE_UI_SECURITY_AUDIT = "C:\path\to\security-audit.jsonl"  # optional
$env:STATEWAKE_UI_RUNTIME_CONTAINMENT_SNAPSHOT = "C:\path\to\runtime-containment.json"  # optional
$env:STATEWAKE_UI_ASSURANCE_DECISION = "C:\path\to\assurance-decision.json"  # optional
$env:STATEWAKE_UI_DATA_LIFECYCLE_CONTEXT = "C:\path\to\data-lifecycle-context.json"  # optional
$env:STATEWAKE_UI_ASSURANCE_EXCEPTION = "C:\path\to\assurance-exception.json"  # optional
$env:STATEWAKE_UI_AUTHORIZATION_CONTEXT = "C:\path\to\authorization-context.json"  # optional
$env:STATEWAKE_UI_ATTESTATION_STORE = "C:\path\to\attestations.jsonl"  # optional
$env:STATEWAKE_UI_ATTESTATION_TRUST_STATE = "C:\path\to\trust-state.json"  # optional
$env:STATEWAKE_UI_ATTESTATION_TRUST_HISTORY = "C:\path\to\trust-history.jsonl"  # optional
$env:STATEWAKE_UI_ATTESTATION_AUTHORITY_STORE = "C:\path\to\authorities.json"  # optional
$env:STATEWAKE_UI_RELIABILITY_PROOF_BUNDLE = "C:\path\to\reliability-proof.zip"  # optional
$env:STATEWAKE_UI_RELIABILITY_DECISION_CHAIN = "C:\path\to\reliability-evidence-chain.json"  # optional
python -m statewake.read_api
```

Default listener: `127.0.0.1:8788`.

The adapter is GET-only and reads an already-existing workspace without calling the workspace initialization/recovery path.

Implemented routes:

```text
GET /api/v1/capabilities
GET /api/v1/overview
GET /api/v1/claims?limit=50&offset=0
GET /api/v1/incidents?limit=50&offset=0                 # when configured
GET /api/v1/incidents/{incident_id}                     # when configured
GET /api/v1/capture-health?limit=50&offset=0              # when configured
GET /api/v1/security-assurance?limit=50&offset=0            # when configured
GET /api/v1/assurance-decision                                 # when configured
GET /api/v1/authorization-policy                               # when configured
GET /api/v1/data-governance                                  # when configured
GET /api/v1/attestation-trust?limit=50&offset=0           # when configured
GET /api/v1/proof-bundle                                    # when configured
GET /api/v1/decision-lineage                                # when configured
GET /api/v1/workspace/operations?limit=50&offset=0
GET /api/v1/release-trust                          # when configured
GET /api/v1/validation-study                       # when configured
GET /api/v1/claims/{report_receipt_id}
GET /api/v1/claims/{report_receipt_id}/summary
GET /api/v1/claims/{report_receipt_id}/evidence
GET /api/v1/claims/{report_receipt_id}/history        # when history is configured
GET /api/v1/claims/{left_report_receipt_id}/compare/{right_report_receipt_id}
GET /api/v1/reports/{report_receipt_id}
GET /api/v1/reports/{report_receipt_id}/markdown
```

The receipt identity must be a lowercase 64-character SHA-256 value. Report reads are bounded by a configured maximum size, content-addressed bytes are reverified, and a serialized report digest is checked before presentation. Responses use `Cache-Control: no-store`; report-backed routes also expose deterministic ETags.

Claim discovery is also bounded. The server scans at most the configured receipt limit, admits only canonical verification-report records through the same verified report loader used by claim detail, sorts by recorded capture time (newest first) with receipt identity as the deterministic tie-break, and exposes only allowlisted filters: `decision`, `verified`, `approval_status`, `profile_id`, `candidate_id`, `q`, `limit`, and `offset`. `q` is a case-insensitive substring match over claim, report type, decision, approval status, profile ID, and candidate ID. It does not search raw evidence bytes, receipt metadata, rationale text, or arbitrary workspace columns.

Incident investigation is separately bounded and optional. The server reads the configured `JsonlIncidentEvidenceStore` source through a lock-free snapshot reader that reuses the canonical incident-record parser and hash-chain verification. It rejects malformed records, digest discontinuity, sequence gaps, lifecycle regression, unsupported status filters, duplicate query parameters, and byte/record-limit overflow. The UI exposes recorded incident/recovery facts only; it does not perform containment, remediation, rollback, ticketing, or causal inference.

Producer capture-health investigation is also optional and read-only. The server reads only the explicitly configured `NativeCaptureSink` failure journal, using the same privacy-safe parser as runtime replay. It exposes stage/error-type records, aggregates, pagination, and optional operator-declared journal-capacity context. It never treats an empty journal as proof that capture succeeded, and it does not attach to a live sink or infer workspace durability. See `docs/user-guide/producer-capture-health-investigation.md`.


Security assurance decision investigation is optional and read-only. It loads one explicitly configured persisted decision plus an optional operational exception, verifies record integrity, replays the existing deterministic assurance policy, and requires exact exception-to-decision binding for newly created exceptions. Legacy unbound exception records remain explicit limitations. See `docs/user-guide/security-assurance-decision-operational-exception-investigation.md`.

Identity-bound access investigation is optional and read-only. It loads one explicit `authorization-context.v1` artifact, reconstructs the existing `Principal`, `AuthorizationPolicy`, `AuthorizationRequest`, and optional recorded decision, then replay-verifies the deny-by-default policy. Raw principal/resource identities are not exposed. StateWake does not become an identity provider or IAM database. See `docs/user-guide/identity-bound-access-authorization-policy-investigation.md`.

Data-governance investigation is optional and read-only. It loads one explicit `data-lifecycle-context.v1` artifact and cross-checks the full existing `DataLifecyclePolicy` against the durable workspace retention row, legal-hold state, deterministic lifecycle decision, and any payload-free deletion tombstone. The workspace remains the durable retention/deletion authority; the context artifact supplies policy fields the current workspace schema does not persist. The browser receives only a digest of the raw object identity and does not perform deletion, disclosure, retention release, legal-hold mutation, or host TLS/encryption verification. See `docs/user-guide/data-governance-retention-disclosure-deletion-investigation.md`.

Security audit & deployment assurance investigation is optional and read-only. It verifies the explicitly configured hash-linked `JsonlSecurityAuditStore` chain through the same parser used by the runtime store, enforces byte/record ceilings, and exposes privacy-safe event categories, protected operations, reason codes, route categories, and digests. Raw recorded paths, arbitrary reason text, request headers/bodies, principal objects, tokens, and local source paths are not sent to the browser. Because `DeploymentSecurityConfig` has no canonical persisted live-configuration snapshot, the UI keeps recorded events, repository deployment requirements, and actual host configuration distinct. An empty audit journal is never presented as proof of a secure deployment. See `docs/user-guide/security-audit-deployment-assurance-investigation.md`.
Attestation trust investigation is optional and read-only. It verifies the configured canonical attestation JSONL chain, any canonical `signed-reliability-outcome-binding.v1` sidecars, the configured current signed trust-state snapshot, and the append-only trust-state history when those sources are available. Signed bindings reuse the existing `SignedReliabilityOutcomeEnvelope` and `ReliabilityAttestationTrustContext`; when the exact historical trust state and an independent authority store are available, the read API can verify the signing envelope against the key that was active in that bound state. Raw signatures, public-key bytes, authority-key bytes, and complete envelopes are not exposed to the browser. Exact signing-context binding remains distinct from a trusted timestamp for `occurred_at`. See `docs/user-guide/attestation-trust-key-lifecycle.md`.

Reliability proof investigation is optional and read-only. It verifies the configured ZIP first through the existing `OperationalBundle` verifier and then through `verify_reliability_proof_bundle()`, reproducing the packaged reliability outcome without the original runtime or filesystem. Format-version semantics remain explicit: v1 does not require lineage/completeness, v2 requires lineage, and v3 requires lineage plus the completeness witness. Packaged trust context demonstrates portable cryptographic consistency but is not promoted into independent operator trust in the authority material carried by the same ZIP. ZIP member paths and raw embedded bytes are not exposed. Workspace portable dataset bundles remain a separate `proof_bundle: false` format. See `docs/user-guide/reliability-proof-bundle-investigation.md`.

Reliability decision-lineage investigation is optional and read-only. It starts from the explicitly configured `ReliabilityEvidenceChain`, applies the existing chain, decision-basis, reconciliation/recovery, and lineage verifiers, and then projects only the verified relationships needed for operator inspection. Canonical decision-basis generation binds material inputs (run/state/evidence and applicable comparison/reconciliation/recovery artifacts) without recursively binding the provenance or integrity files that contain the basis itself. Legacy provenance/integrity/attestation inputs remain verifiable as **verification context**, but the UI never pretends they are provenance-graph nodes. Reconciliation, recovery, and lineage closure remain separate facts, and none of them imply factual correctness or business authorization. See `docs/user-guide/reliability-decision-lineage-investigation.md`.

## Browser package

The optional Next.js package lives under `ui/`. It uses strict TypeScript, React, Next.js App Router, Ant Design and Axios as required by the v0.4.0 UI implementation plan. It remains separate from the Python package dependency graph.

The browser calls a same-origin GET-only Next.js route handler, which forwards only `/api/v1/...` paths to `STATEWAKE_READ_API_ORIGIN` (default `http://127.0.0.1:8788`) without changing StateWake result semantics.

The Evidence explorer is a bounded read projection, not a new graph authority. It shows relationships explicitly recorded by the canonical verification report and receipt fields, plus exact workspace identity/digest matches. It never invents causal edges. For each resolved external-evidence receipt, the read API reuses the canonical receipt parser, content-addressed artifact verifier, and `ExternalEvidenceAdmission` service to keep **receipt integrity**, **artifact-byte integrity**, and **admission binding** separate. The browser receives only deterministic receipt/admission digests and bounded producer/run/event identifiers; arbitrary receipt metadata and artifact payload bytes are not sent to the browser. Producer identifiers are recorded assertions, not proof of authenticity: detached producer signatures and independently configured producer trust keys are not persisted by the workspace receipt model, so the Evidence explorer reports producer authentication as **not recorded** rather than inferring it. If the configured receipt scan bound is reached, the response is marked partial and unresolved identities are reported as *not resolved within the bounded scan*, never as proof that the evidence does not exist.

The accessible relationship table is the complete bounded response; the visual relationship map is a secondary overview and may cap rendered nodes for readability. The UI also links the same report to recorded history and comparison without merging those distinct authorities. The Claim catalog adds discovery and two-report comparison selection without creating a second search index, reliability ranking, release control, or stronger causal/authorization interpretation.

## Operational trust and validation

The same read API now exposes the existing workspace, release-trust, and comparative-validation authorities through an optional **Operational Trust & Validation Center**. Workspace inspection uses a true read-only SQLite handle and bounded pagination. Release-trust keeps structural profile satisfaction, local byte verification, signer-authentication status, human release decision, and publication authority separate. Validation-study reads a frozen digest-consistent fixture study and does not execute a live benchmark.

See `docs/user-guide/operational-trust-validation-center.md` for configuration, boundaries, and limitations.

## Authority boundary

A browser-rendered success state is never authority by itself. The displayed report digest, candidate identity/digest, recorded checks/evidence and approval state come from the canonical StateWake report. Canonical JSON and Markdown are rendered again by the existing StateWake report renderers.

The browser must not be used to infer factual correctness, signer authenticity, human publication approval, or permission to execute a side effect unless separate StateWake evidence explicitly establishes that bounded claim.
