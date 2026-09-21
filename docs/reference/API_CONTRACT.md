# StateWake Public API Contract

**Package version:** `v0.3.0`  
**Public API contract version:** `1`

This document is the authoritative contract for the symbols exported by the
`statewake` top-level package. Consumers should import public symbols from
`statewake`, not from `statewake.services`, `statewake.domain`, or other
implementation modules, unless an adapter/protocol is explicitly identified
as an extension boundary below.

## Stability classes

| Class | Meaning |
|---|---|
| Public | Supported for application use. Compatible changes follow `docs/governance/VERSIONING.md`. |
| Adapter extension | Public protocol/type intended for host integrations. The host remains authoritative for the external system. |
| Compatibility constant | Machine-readable version marker for the contract itself. |

A public symbol is not a promise that its internal implementation module is
stable. The top-level import path is the stable path.

## Public Python symbols

| Symbol | Kind | Stability | Contract |
|---|---|---|---|
| `admit_evidence` | function | Public | Validate/admit an external evidence receipt against an artifact and optional receipt file. |
| `load_outcome_attestation` | function | Public | Load and validate a persisted reliability outcome attestation. |
| `write_outcome_attestation` | function | Public | Persist a reliability outcome attestation. |
| `build_evidence_chain` | function | Public | Build the canonical evidence-chain representation from typed artifact references. |
| `load_evidence_chain` | function | Public | Load and validate a persisted evidence chain. |
| `write_evidence_chain` | function | Public | Persist an evidence chain through the supported persistence boundary. |
| `verify_evidence_chain` | function | Public | Verify an evidence chain and all bound sources under a supplied root. |
| `verify_outcome` | function | Public | Independently verify a reliability outcome against state history and evidence. |
| `read_reliability_state` | function | Public | Read the authoritative current state for a subject. |
| `build_release_proof` | function | Public | Verify a bounded claim profile and emit the existing portable proof bundle. |
| `build_reliability_decision_basis` | function | Public | Build a deterministic decision basis from a satisfied claim profile. |
| `prepare_reliability_decision_basis` | function | Public | Persist and bind a decision basis to an evidence chain. |
| `evaluate_claim_profile` | function | Public | Evaluate declared structural/state conditions without scoring model behavior. |
| `get_builtin_claim_profile` | function | Public | Resolve a built-in claim profile by identifier and version. |
| `load_claim_profile` | function | Public | Load a persisted claim profile. |
| `write_claim_profile` | function | Public | Persist a claim profile. |
| `render_verification_report` | function | Public | Render a verification report as human-readable text. |
| `write_verification_report` | function | Public | Persist a verification report and Markdown rendering. |
| `public_key_digest` | function | Public | Compute the SHA-256 digest used to bind an external public key. |
| `ExternalEvidenceAdmission` | type | Public | Deterministic admission result returned by evidence admission. |
| `ExternalEvidenceReceipt` | type | Public | Immutable external-evidence receipt and identity/integrity boundary. |
| `ReliabilityEvidenceChain` | type | Public | Canonical composition primitive binding reliability evidence references. |
| `ReliabilityOutcomeAttestation` | type | Public | Terminal reliability-outcome attestation bound to chain/state evidence. |
| `ReliabilityOutcomeVerificationReport` | type | Public | Structured independent outcome-verification result. |
| `ReliabilityDecisionBasis` | type | Public | Immutable semantic basis for a reliability decision. |
| `OperationalBundle` | type | Public | Auditable operational/proof package manifest returned by release-proof workflows. |
| `ReliabilityStateSnapshot` | type | Public | Current reliability-state snapshot. |
| `ReliabilityStateTransition` | type | Public | Immutable state transition and digest binding. |
| `ReliabilityClaimProfile` | type | Public | Bounded claim requirements. |
| `ClaimProfileEvaluation` | type | Public | Explainable claim-profile result. |
| `ReliabilityVerificationReport` | type | Public | Structured verification result. |
| `ReliabilityFailureEvent` | type | Public | Operational failure event payload. |
| `NullReliabilityFailureHook` | type | Public | No-op failure hook implementation. |
| `ReliabilityFailureHook` | protocol | Adapter extension | Host-facing operational failure hook. |
| `EvidenceAdapterContext` | type | Adapter extension | Producer identity/context for first-party adapters. |
| `FileEvidenceAdapter` | type | Adapter extension | Generic file evidence adapter. |
| `CICDArtifactAdapter` | type | Adapter extension | CI/CD artifact adapter. |
| `AgentRunLogAdapter` | type | Adapter extension | Agent-run log adapter. |
| `EvaluationOutputAdapter` | type | Adapter extension | Evaluation-output adapter. |
| `IncidentRecoveryRecordAdapter` | type | Adapter extension | Incident/recovery evidence adapter. |
| `OpenTelemetryTraceAdapter` | type | Adapter extension | OpenTelemetry trace evidence adapter. |
| `EvidenceRetentionAdapter` | protocol | Adapter extension | Host-owned retention/deletion policy boundary. |
| `EvidenceRetentionRequirement` | type | Adapter extension | Retention requirement value object. |
| `SigningProvider` | protocol | Adapter extension | External signing boundary; private keys remain outside StateWake. |
| `KeyLifecycleProvider` | protocol | Adapter extension | External signing-key rotation/revocation boundary. |
| `SigningKeyReference` | type | Adapter extension | Stable reference to externally managed signing key. |
| `StateWakeClient` | type | Public | Framework-neutral application integration facade. |
| `IntegrationContext` | type | Public | Producer identity and integration metadata. |
| `WebhookEvidenceAdapter` | type | Public | Webhook evidence normalization boundary. |
| `WebhookEvent` | type | Public | Webhook occurrence value object. |
| `QueueEvidenceAdapter` | type | Public | Queue/event evidence normalization boundary. |
| `QueueMessage` | type | Public | Queue delivery value object. |
| `DatabaseEvidenceAdapter` | type | Public | Database-observation evidence boundary. |
| `DatabaseChange` | type | Public | Database mutation observation value object. |
| `BatchEvidenceAdapter` | type | Public | Batch/data-pipeline evidence boundary. |
| `BatchRun` | type | Public | Batch execution value object. |
| `AgentEvidenceAdapter` | type | Public | AI/agent execution evidence boundary. |
| `AgentRunEvidence` | type | Public | AI/agent execution reference value object. |
| `StateWakeIntegrationError` | exception | Public | Base integration failure. |
| `InvalidEvidenceError` | exception | Public | Evidence cannot be represented/admitted. |
| `IdentityConflictError` | exception | Public | Event identity was reused with conflicting content. |
| `PersistenceFailureError` | exception | Public | Evidence persistence failed. |
| `TrustCheckpoint` | type | Public | Signed checkpoint binding an external history tip. |
| `TrustAnchor` | protocol | Adapter extension | Independent persistent checkpoint boundary. |
| `JsonTrustAnchorStore` | type | Adapter extension | Filesystem reference implementation of the trust-anchor boundary. |
| `Ed25519TrustCheckpointVerifier` | type | Adapter extension | Ed25519 checkpoint verifier. |
| `TrustAnchorError` | exception | Public | Trust-anchor contract failure. |
| `AnchorDiscrepancyError` | exception | Public | Independent/local trust state disagrees. |
| `create_trust_checkpoint` | function | Public | Construct a signed trust checkpoint. |
| `compare_local_tip` | function | Public | Compare a checkpoint with local history tip/count. |
| `ensure_checkpoint_sequence` | function | Public | Validate checkpoint continuity. |
| `__version__` | constant | Compatibility constant | Current package version; `v0.3.0`. |
| `__public_api_contract_version__` | constant | Compatibility constant | Current public API contract version; `1`. |

## Error contract

Normal validation failures use `ValueError` at domain/value-object boundaries.
Integration adapters expose the `StateWakeIntegrationError` hierarchy for
machine-classifiable integration failures. Trust-anchor discrepancies use
`AnchorDiscrepancyError` so a caller can distinguish disagreement from generic
invalid input.

The package does not promise exact exception-message strings as a compatibility
contract.

## Serialization contract

Portable/persisted representations carry explicit format markers where the
current data model defines them. Current supported formats include:

- evidence receipt: format `1`;
- reliability evidence chain: format `1`;
- reliability state/transition: format `1`;
- attestation and related reports: format `1`;
- trust checkpoint: format `1`;
- decision basis: format `1`;
- behavioral comparison: format `1`;
- proof bundle: formats `1`, `2`, and `3`, with format-specific completeness rules.

Persisted data is not defined by Python class layout. Unsupported explicit
format versions must be rejected rather than silently interpreted.

## Compatibility rules

`docs/governance/VERSIONING.md` is authoritative for semantic versioning. In summary:

- **MAJOR** — incompatible public Python, data-contract, or HTTP changes;
- **MINOR** — backward-compatible public capability/integration additions;
- **PATCH** — backward-compatible fixes and hardening.

The following compatibility dimensions are tracked separately:

1. Python source/import compatibility;
2. package/binary compatibility;
3. serialization compatibility;
4. behavioral compatibility;
5. CLI compatibility;
6. HTTP compatibility;
7. proof compatibility.

A change may preserve one dimension while breaking another.

## CLI contract

The executable is `statewake`. Supported command names are the values returned
by the public `supported_commands()` helper in the CLI implementation and are
listed in `docs/user-guide/cli.md` by capability.

Stable behavior:

- successful commands exit `0`;
- argparse usage errors exit `2`;
- negative proof verification exits `1`;
- machine-readable command output is JSON on stdout where the command emits a
  result;
- callers must not depend on exact human-readable error-message text.

The CLI is a thin interface over the same domain/service authorities used by
the Python package.

## HTTP contract

The WSGI application is `statewake.server:app`.

| Method | Path | Success | Error behavior |
|---|---|---|---|
| GET | `/health` | `200` with `status` and `version` | — |
| GET | `/v1/version` | `200` with `version` | — |
| POST | `/v1/evidence/verify` | `200` with `verified`, `chain_id`, `digest` | structured JSON error/status |
| POST | `/v1/proof/verify` | `200` when verified; `422` when verification result is false | structured JSON error/status |

Verification POST requests require `Content-Length`, are bounded by the
configured request-size limit (default 1 MiB), require HTTPS by default, and
must resolve requested filesystem paths inside configured artifact roots.

The HTTP adapter is a trusted local/internal integration edge, not a
multi-tenant internet-facing service. Authentication, authorization, network
policy, TLS termination, tenant isolation, rate limiting, and monitoring remain
deployment responsibilities.

## Official examples

Official examples must import from `statewake` only. Implementation-module
imports are not part of the public contract and must not appear in the release
quickstart examples.

## Contract tests

`tests/test_public_api_contract.py` is the executable consumer-contract gate.
It checks the exported symbol set, contract version, public annotations and
basic public importability. The end-to-end behavior of the principal evidence
facade is covered separately by `tests/test_public_api.py`.
