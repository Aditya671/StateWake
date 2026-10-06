# StateWake UI — evidence inspection, operational trust, review, and scoped approval

This optional UI extends the StateWake v0.5.0 human-inspection surface, originally designed from the v0.4.0 UI package, without becoming a second verifier, identity provider, or publication control plane.

Implemented tasks:

- Workspace overview cards backed only by canonical verification-report records; no illustrative production counts and no synthetic reliability score.
- Bounded Claim catalog discovery over canonical verification reports, with allowlisted filters, deterministic pagination, direct workbench opening, and two-report comparison selection.
- Read-only Incident & Recovery Investigation over the canonical hash-linked security-incident evidence store, with lifecycle, affected trust state, recovery, post-recovery verification, and uncertainty kept distinct.
- Read-only Reliability Proof Bundle & Portable Verification Investigation over one explicitly configured portable reliability proof ZIP, using the existing proof verifier rather than a browser-side trust implementation.
- Read-only Producer Capture Health & Failure Journal Investigation over the canonical redacted `NativeCaptureSink` failure journal, without inferring capture success or live sink state.
- Claim Detail → Summary → Checks → Evidence → canonical JSON / Markdown.
- Optional reliability-state history for an exact report candidate, when an existing authoritative JSONL history file is explicitly configured.
- Direct comparison of two exact report receipt IDs with semantic-scope warnings and field-level deltas.
- Operational Trust & Validation Center pages for genuinely read-only workspace diagnostics, release-trust evidence, and one frozen comparative validation study.
- Authenticated append-only **review statements** bound to the exact report/candidate digest through a separate secured human-review service.
- Optional, separately authorized **HumanApprovalContract evidence** for one exact report digest, server-configured action, and server-configured scope.
- A reusable dark card system for overview metrics, verification state, evidence state, identity, history, comparison, review, and approval surfaces.
- Evidence Explorer assurance traceability that distinguishes canonical receipt integrity, content-addressed artifact verification, deterministic admission binding, and unavailable producer-authentication proof without exposing payload bytes or arbitrary receipt metadata.

The UI is optional and does not become a dependency of the Python SDK/CLI. `src/statewake/server.py` remains the bounded verification-only WSGI surface. Read requests are proxied to `statewake.read_api`; human review/approval reads and writes are proxied separately to `statewake.review_api`.

## Runtime topology

```text
existing StateWake workspace
  -> statewake.read_api (127.0.0.1:8788)
     -> canonical report validation
     -> deterministic overview projection
     -> bounded claim catalog / discovery filters
     -> optional incident / recovery investigation
     -> optional producer capture failure-journal investigation
     -> detail / evidence / history / comparison / JSON / Markdown
     -> read-only workspace operations
     -> optional release-trust projection
     -> optional frozen validation-study projection
  -> Next.js read proxy

exact immutable report/candidate basis
  -> statewake.review_api (127.0.0.1:8789)
     -> host-supplied authentication / operation authorization
     -> explicit browser Origin + CSRF verification
     -> append-only hash-linked review statements
     -> optional canonical HumanApprovalContract evidence
     -> optional independent security-audit JSONL
  -> Next.js server-side human-review proxy
     -> bearer/CSRF secrets remain server-side
  -> review / scoped approval workbench
```

## Read API and overview cards

Set `STATEWAKE_UI_WORKSPACE_ROOT` for the Python read API. To enable the optional History tab, set `STATEWAKE_UI_RELIABILITY_HISTORY` to an existing reliability-state JSONL history path. To enable Incident & Recovery Investigation, set `STATEWAKE_UI_INCIDENT_EVIDENCE` to the existing canonical incident-evidence JSONL store. To enable Producer Capture Health, set `STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL` to the runtime sink's privacy-safe failure journal; optionally set `STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL_CAPACITY_BYTES` when the runtime journal capacity is known. To enable Reliability Proof Bundle investigation, set `STATEWAKE_UI_RELIABILITY_PROOF_BUNDLE` to one existing portable reliability proof ZIP. To enable Reliability Decision Basis, Reconciliation & Lineage Investigation, set `STATEWAKE_UI_RELIABILITY_DECISION_CHAIN` to one existing canonical `ReliabilityEvidenceChain` JSON file. If the read API is not at its default loopback address, set `STATEWAKE_READ_API_ORIGIN` for Next.js.

`GET /api/v1/overview` scans only bounded canonical verification-report receipts and returns real counts with an explicit denominator and deduplication key. The UI currently surfaces:

```text
Reports evaluated
Human decisions pending
Reports with missing evidence
Verified reports
```

Those values are report-record counts, not a universal StateWake reliability score. If the overview cannot be verified, the UI shows it as unavailable instead of substituting conceptual numbers.

`GET /api/v1/claims` provides the claim-discovery collection. It scans only the configured bounded receipt set and reuses canonical report verification; a broken report fails the catalog closed rather than disappearing from search results. The only accepted query keys are `decision`, `verified`, `approval_status`, `profile_id`, `candidate_id`, `q`, `limit`, and `offset`. The browser proxy enforces the same allowlist and pagination ceiling before forwarding. Discovery never accepts arbitrary SQL, filesystem paths, raw workspace fields, or unbounded search.

History entries are shown only when their recorded `evidence_chain_id` and `evidence_chain_digest` match the report candidate exactly. Absence of a matching transition does not prove that no external review or action occurred.

Direct comparison accepts two durable report receipt IDs. A digest difference means the candidate bytes differ; the UI does not infer cause or severity. Profile/version/claim/report-type mismatches are shown as non-equivalence warnings.

## Incident and recovery investigation

`GET /api/v1/incidents` and `GET /api/v1/incidents/{incident_id}` are enabled only when the server is configured with `STATEWAKE_UI_INCIDENT_EVIDENCE`. The read path verifies the complete hash-linked JSONL store without acquiring the writer lock, enforces byte/record ceilings, consolidates observations by deterministic incident identity, and rejects lifecycle status/time regression.

The collection accepts only `status`, `category`, `q`, `limit`, and `offset`. The browser proxy enforces the same allowlist. The detail view shows recorded lifecycle observations, evidence identities/digests, affected trust state, explicit uncertainty, optional key-compromise scope, recovery evidence, and post-recovery verification. Source filesystem paths and arbitrary incident payloads are not exposed. `recovered` remains distinct from `reverified`; timestamps describe recorded observation order and never establish causality.

Full details are in `docs/user-guide/incident-recovery-investigation.md`.

## Producer capture health and failure-journal investigation

`GET /api/v1/capture-health` is enabled only when `STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL` is configured. The reader reuses the canonical runtime journal parser, rejects malformed/oversized/symlinked sources, and accepts only exact `stage`, `error_type`, `limit`, and `offset` query parameters. The browser shows recorded failure sequence, aggregate stages/error types, and optional declared journal-capacity context. It does not expose raw exception messages or SDK payloads and never converts an empty journal into a successful capture claim. Full details are in `docs/user-guide/producer-capture-health-investigation.md`.


## Security audit & deployment assurance investigation

`/security-assurance` is enabled when either `STATEWAKE_UI_SECURITY_AUDIT` or `STATEWAKE_UI_RUNTIME_CONTAINMENT_SNAPSHOT` is configured. The audit reader uses a lock-free bounded snapshot reader that shares the canonical `JsonlSecurityAuditStore` parser and hash-chain verification contract. The runtime snapshot is emitted by the verification service itself when `STATEWAKE_VERIFICATION_RUNTIME_SNAPSHOT` is configured, then digest-verified by the read API. The route accepts only exact `event`, `operation`, `reason`, `method`, `limit`, and `offset` query parameters.

The browser keeps recorded security events separate from effective verification-service configuration. It can show the actual request/JSON containment limits captured from `VerificationServiceConfig`, but it explicitly identifies archive limits not wired to the service-specific runtime limits and graph/deadline/concurrency/temporary-byte values that are not active service enforcement. It never exposes artifact-root paths, request paths, arbitrary reason text, request headers/bodies, tokens, principal objects, or local source paths, and it still does **not** certify live TLS termination, identity-provider correctness, tenant isolation, KMS/HSM custody, process isolation, CPU/memory quotas, network egress, or other host controls. See `docs/user-guide/security-audit-deployment-assurance-investigation.md`.

## Operational trust and validation center

The read proxy also exposes `/workspace`, `/release-trust`, and `/validation`. The workspace endpoint accepts only bounded `limit`/`offset` pagination and never arbitrary SQL or browser-supplied filesystem paths. `StateWakeWorkspace.open_read_only()` opens an existing SQLite workspace through `mode=ro` plus `query_only`, and mutation paths fail closed.

Optional server inputs:

```text
STATEWAKE_UI_RELEASE_TRUST_BUNDLE=<release-trust JSON>
STATEWAKE_UI_RELEASE_ROOT=<root containing digest-bound release files>
STATEWAKE_UI_PUBLICATION_BASIS=<canonical publication-basis JSON>
STATEWAKE_UI_PUBLICATION_APPROVAL_WORKSPACE=<canonical publication authority workspace>
STATEWAKE_UI_PUBLICATION_PRODUCER_ID=<expected publication approval producer>
STATEWAKE_UI_PUBLICATION_PERMIT=<canonical publication execution permit JSON>
STATEWAKE_UI_PUBLICATION_REGISTRY_RECEIPT=<canonical post-publication registry receipt JSON>
STATEWAKE_UI_VALIDATION_STUDY=<frozen comparative-study JSON>
```

The release view deliberately keeps structural profile satisfaction, local byte verification, signer authenticity, human release decision, publication authorization, and post-publication registry reconciliation separate. When the optional publication basis/authority inputs are configured, the UI displays the canonical active/revoked/superseded lifecycle. When the permit/registry-receipt pair is also configured, it displays publication only after the receipt is verified against the exact basis and permit. The UI remains read-only: it does not record approval, issue an execution permit, publish a package, or create registry evidence. The UI does not authenticate a signer without an independent trust root. The validation page verifies and displays one recorded deterministic fixture study; it does not run a live benchmark or generalize its measurements. Full details are in `docs/user-guide/operational-trust-validation-center.md`.

## Human-review service

StateWake does **not** claim to provide a production multi-user identity provider. The generic `create_review_application(...)` requires host-supplied authentication, operation-specific authorization, actor resolution, and CSRF verification.

For local qualification only, `python -m statewake.review_api` provides an explicit single-reviewer loopback adapter. It refuses non-loopback binding and refuses to start unless all required values are configured:

```text
STATEWAKE_UI_WORKSPACE_ROOT
STATEWAKE_UI_REVIEW_STORE
STATEWAKE_REVIEW_TOKEN
STATEWAKE_REVIEW_CSRF_TOKEN
STATEWAKE_REVIEW_ACTOR_ID
STATEWAKE_REVIEW_ROLE
STATEWAKE_REVIEW_ALLOWED_ORIGINS
```

`STATEWAKE_REVIEW_TOKEN` and `STATEWAKE_REVIEW_CSRF_TOKEN` must be distinct and at least 32 characters.

Optional security audit:

```text
STATEWAKE_REVIEW_SECURITY_AUDIT
```

The Next.js server-side proxy requires:

```text
STATEWAKE_REVIEW_API_ORIGIN=http://127.0.0.1:8789
STATEWAKE_REVIEW_API_TOKEN=<same bearer token>
STATEWAKE_REVIEW_CSRF_TOKEN=<same CSRF token>
STATEWAKE_UI_PUBLIC_ORIGIN=http://localhost:3000
```

The browser never supplies `actor_identity_ref` or `actor_role`; those come from the authenticated server boundary. Every write also requires the exact report digest in `If-Match`, exact candidate/report digests in the body, and an `Idempotency-Key`.

### Review statements

Review categories are workflow labels only:

```text
observation
question
change_requested
finding
review_complete
```

A review statement containing the word `approved` is still only review text. The review-statement endpoint cannot create approval evidence.

### Human approval

Human approval is enabled only when all three server-owned values are configured together:

```text
STATEWAKE_APPROVAL_PRODUCER_ID
STATEWAKE_APPROVAL_ACTION
STATEWAKE_APPROVAL_SCOPE
```

When enabled, the UI first reads the exact server-declared action and scope and requires an explicit human confirmation. A successful write persists the existing canonical `HumanApprovalContract`, bound to:

```text
authenticated actor + role
server-owned producer
report run ID
server-owned approval action
exact report digest as approval basis
server-owned scope
timestamp + bounded reason metadata
```

The browser cannot choose or expand the approval action/scope. Recording approval does **not** mutate the immutable verification report, change its machine decision, publish a release, or authorize anything outside the configured scope. A later `statewake release-proof` re-evaluation can consume that exact canonical approval evidence, require the machine report to remain identical to the approved basis except for generation time, and emit a new report revision with `approval_status=approved` plus digest provenance. The UI write path never performs that re-evaluation itself.

Approval lifecycle changes are append-only. Revocation writes a canonical `HumanApprovalRevocationContract` bound to one exact approval receipt and its digest. Supersession writes a replacement `HumanApprovalContract` whose canonical metadata names the exact predecessor receipt and digest. Historical approval bytes are never edited or deleted; the approval thread projects each record as `active`, `revoked`, or `superseded`. Only active approval evidence can satisfy a fresh release-proof reconciliation. The UI exposes revocation and supersession only for active approvals and only when the authenticated server boundary separately authorizes `approval:revoke` or `approval:supersede`.

## Frontend qualification

Run the real dependency-backed gates on a network-enabled development machine:

```text
npm run typecheck
npm test
npm run build
```

Keep the resolved `package-lock.json` after successful dependency resolution and include it in the final release-input identity. Do not replace the declared UI stack merely to bypass a local dependency-resolution failure.


### Attestation trust investigation

`/attestation-trust` reads the bounded attestation/trust projection. It separates attestation-chain integrity, current trust-state authentication, authenticated historical lifecycle evidence, current anchor status, and missing signed-envelope evidence. Configure the server with `STATEWAKE_UI_ATTESTATION_STORE`, optionally `STATEWAKE_UI_ATTESTATION_TRUST_STATE`, `STATEWAKE_UI_ATTESTATION_TRUST_HISTORY`, and `STATEWAKE_UI_ATTESTATION_AUTHORITY_STORE`. The history tip may supply the current diagnostic state, but lifecycle transitions become authoritative only after every history snapshot authenticates. Raw keys and signatures are never sent to the browser, and attestation-time trust is not inferred because outcome attestations do not bind a trust-state digest/version.


## Reliability proof bundle and portable verification

`/proof-bundle` reads only the server-configured `STATEWAKE_UI_RELIABILITY_PROOF_BUNDLE`. The read API first verifies the operational ZIP/manifest/provenance boundary and then calls the existing `verify_reliability_proof_bundle()` authority. The browser cannot supply a bundle path.

The projection distinguishes proof-format requirements, offline outcome verification, lineage closure, completeness witness, packaged trust-context consistency, and external authority trust. A packaged authority key is not automatically an independently trusted root.

Workspace portable dataset bundles remain a separate format whose manifest records `proof_bundle: false`; they are not accepted or displayed as reliability proofs. Raw bundle member paths and embedded bytes are intentionally omitted. See `docs/user-guide/reliability-proof-bundle-investigation.md`.


## Reliability decision basis, reconciliation and lineage investigation

`/decision-lineage` reads only the server-configured `STATEWAKE_UI_RELIABILITY_DECISION_CHAIN`. The read API verifies the canonical evidence chain and its referenced artifacts, verifies the existing decision basis, comparison/reconciliation/recovery records when present, and verifies provenance lineage closure before the browser receives a projection. The browser cannot submit a chain path or rebuild any decision.

The projection distinguishes **lineage-bound material inputs** from **verification-context inputs**. Material run/state/evidence and applicable reconciliation/recovery/comparison digests must retain provenance-node reachability. Legacy provenance/integrity/attestation decision inputs may remain valid verification context without being misrepresented as graph nodes. Reconciliation and recovery remain distinct, and a verified lineage does not establish factual correctness, business authorization, or publication permission. Raw decision rationale and local filesystem paths are omitted. See `docs/user-guide/reliability-decision-lineage-investigation.md`.


## Security assurance decision and identity-bound authorization

`/assurance-decision` reads `STATEWAKE_UI_ASSURANCE_DECISION` and optional `STATEWAKE_UI_ASSURANCE_EXCEPTION`. The server verifies deterministic assurance-policy replay and exact decision binding for modern exceptions before the browser receives a privacy-safe projection.

`/authorization-policy` reads `STATEWAKE_UI_AUTHORIZATION_CONTEXT`. The server reconstructs the existing `Principal`, `AuthorizationPolicy`, `AuthorizationRequest`, and optional recorded `AuthorizationDecision`, then requires the recorded decision (when present) to match deny-by-default policy replay. Raw principal/resource identities and filesystem paths are not exposed. The page does not claim authentication, MFA, TLS, tenant isolation, or IAM authority.

`/data-governance` reads `STATEWAKE_UI_DATA_LIFECYCLE_CONTEXT` and the already-configured workspace. The explicit context supplies the full existing `DataLifecyclePolicy`; the server then cross-checks it against the durable retention row, legal hold, deterministic lifecycle replay, and any payload-free deletion tombstone. The workspace remains the durable lifecycle authority. Optionally, `STATEWAKE_UI_PRIVACY_GOVERNANCE_SNAPSHOT` may point to a service-emitted `privacy-governance-runtime.v1` snapshot; the server digest-verifies that bounded local artifact and projects only policy identities, counts, sensitivity ceilings, and explicit enforcement boundaries. Missing snapshot evidence is shown as not observed rather than inferred from defaults. Regex patterns, replacement values, local paths, arbitrary evidence metadata, and artifact bytes are never sent to the browser. The page does not delete or disclose data, modify legal hold, prove external-copy erasure, claim live telemetry binding, scan opaque artifact content, or claim that encryption-at-rest/TLS requirements are satisfied by the host.
