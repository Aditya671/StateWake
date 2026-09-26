# StateWake Threat Model v0.1

**Status:** canonical security model for the StateWake reliability-evidence core.

## Scope

This model covers the StateWake reliability-evidence core, evidence adapters, persistence, portable proof bundles, HTTP verification adapter, signing/key-management boundary, privacy/redaction primitives, and independent trust checkpoints.

StateWake does **not** automatically secure the host operating system, Python runtime, filesystem, deployment network, credentials, business policy, or external producer systems.

## Assets and security properties

| Asset | Desired properties | Primary controls | Residual risk |
|---|---|---|---|
| Evidence authenticity | producer attribution, source binding | producer identity validation, external receipt binding | compromised producer/key can create authentic-but-false evidence |
| Evidence integrity | byte/content integrity | SHA-256 content addressing, receipt/artifact cross-checks | compromise of trusted write boundary remains possible |
| Provenance integrity | acyclic, traceable relationships | provenance validation and cycle rejection | operator may supply semantically incorrect provenance |
| Reliability state integrity | valid transitions, continuity | typed transitions, digest binding, persistence checks | valid transitions can still encode wrong business judgment |
| Attestation integrity | signed outcome binding | Ed25519 signatures, key/trust-state binding | stolen signing key |
| Trust-anchor checkpoints | external history-tip binding | signed checkpoints, sequence/rollback/disagreement detection | filesystem reference store is not independently immutable |
| Audit evidence | durable, attributable records | JSONL/SQLite durability, locking, content digests | privileged storage attacker can delete local history |
| Public API behavior | predictable validation/errors | typed façade tests and explicit contracts | undocumented future changes until API freeze |
| Availability | bounded verification workload | HTTP request cap, read-only adapter, deployment resource limits | CPU/memory exhaustion outside explicit caps |
| Key material | confidentiality and lifecycle control | external signing boundary, lifecycle provider | KMS/HSM/provider compromise |

## Adversaries

| ID | Adversary | Capability assumed | Key attacks |
|---|---|---|---|
| A1 | Accidental producer | buggy input | malformed evidence, invalid transitions |
| A2 | Compromised producer | valid producer credentials/runtime | false evidence, replay, conflicting identity |
| A3 | Malicious producer | intentional evidence manipulation | fabricated/tampered evidence |
| A4 | Replay attacker | captured valid event | duplicate/replayed event |
| A5 | Storage attacker | modify/delete persisted files | artifact, receipt, state, bundle mutation/deletion |
| A6 | Privileged insider | operational access | key misuse, storage manipulation, configuration weakening |
| A7 | Supply-chain attacker | dependency/build influence | malicious package/build artifact |
| A8 | Network attacker | transport manipulation where TLS is absent/broken | request mutation/replay/interception |

## Trust boundaries

1. **Producer → adapter:** all producer input is untrusted until validated.
2. **HTTP client → WSGI adapter:** request body, paths, method, and scheme are untrusted.
3. **Adapter → StateWake core:** typed records and validated evidence cross into the core.
4. **Core → persistent store:** filesystem/SQLite writes are durability and corruption boundaries.
5. **Core → external signing provider:** private signing material stays outside the core.
6. **Local history → independent trust anchor:** checkpoint verification depends on a separately managed key/store boundary; the bundled filesystem reference adapter is only a reference implementation.
7. **Portable proof → verifier:** archive members, manifests, signatures, and source references are untrusted until every required cross-check passes.

## Threat matrix

| Threat | Asset | Precondition | Attack | Detection / prevention | Containment | Recovery | Evidence of control | Residual risk |
|---|---|---|---|---|---|---|---|---|
| T01 | Evidence integrity | artifact exists | mutate content | digest + receipt verification | reject evidence | restore authoritative artifact | `tests/test_external_evidence_ingestion.py::ExternalEvidenceIngestionTests::test_tampered_artifact_is_detected` | trusted storage compromise |
| T02 | Evidence identity | receipt exists | change producer/source identity | receipt binding and conflict checks | reject admission | reconcile producer record | `tests/test_external_evidence_ingestion.py::ExternalEvidenceIngestionTests::test_source_event_conflict_is_rejected` | compromised producer |
| T03 | Replay/idempotency | repeated event | duplicate or conflicting delivery | deterministic receipt identity + conflict detection | reject conflict / accept exact duplicate | producer retry semantics | `tests/test_external_evidence_ingestion.py::ExternalEvidenceIngestionTests::test_concurrent_duplicate_ingestion_is_idempotent` | replay policy is producer-dependent |
| T04 | State integrity | prior state | invalid transition | transition validation and digest binding | reject transition | restore last verified state | `tests/test_reliability_state.py` | semantically wrong but structurally valid policy |
| T05 | Provenance integrity | provenance graph | cycle/mutation | graph validation + digest checks | reject graph | reconstruct from authoritative inputs | `tests/unit/test_provenance.py` | privileged writer |
| T06 | Proof integrity | proof bundle | mutate descriptor/source/attestation | manifest, digest, signature, trust-context checks | fail closed | rebuild from authoritative evidence | `tests/test_reliability_proof_bundle.py::TestReliabilityProofBundle::test_tampered_source_fails_closed` | dependency on verifier correctness |
| T07 | Archive safety | ZIP input | duplicate/traversal/extra member | exact member-set validation + safe names | reject archive | regenerate bundle | `tests/test_hardening_archives.py` | decompression/resource risk requires deployment budget |
| T08 | Persistent history | JSONL/SQLite | interleaving/corruption/partial write | locking, atomicity, fsync, strict parsing | reject/recover only valid partial tail | restore/reconcile | `tests/test_hardening_boundaries.py` | privileged storage deletion |
| T09 | Attestation authenticity | signed outcome | alter signed payload/signature | Ed25519 verification + key binding | reject attestation | re-attest with valid key | `tests/test_reliability_proof_bundle.py::TestReliabilityProofBundle::test_tampered_signed_envelope_fails_offline` | stolen key |
| T10 | Trust checkpoint | anchored history | rollback/deletion/conflict | signature, sequence, previous-digest and tip comparison | mark discrepancy | investigate/reconcile from independent source | `tests/test_trust_anchor.py::TestTrustAnchor::test_anchor_disagreement_detects_deleted_trailing_history` | reference store may share trust domain |
| T11 | HTTP boundary | verifier availability/integrity | oversized/malformed/path-escape request | HTTPS default, Content-Length, max body, root jail, read-only | reject request | correct deployment/client | `tests/test_http_api.py::test_http_rejects_oversized_request` | no authentication/tenant isolation in adapter |
| T12 | Privacy | sensitive metadata | persist secrets/PII unnecessarily | explicit redaction policy | redact before persistence/transport | reissue redacted evidence where possible | `tests/unit/test_privacy.py::PrivacyTests::test_key_and_regex_redaction_are_deterministic` | opaque payloads are not inspected |
| T13 | Key material | signing key | compromise or misuse | external signer boundary + lifecycle provider | revoke/rotate | re-attest under replacement key | `tests/test_key_management.py::TestKeyManagement::test_external_signing_does_not_accept_private_material` | provider/KMS security |
| T14 | Availability | verification service | resource exhaustion | explicit HTTP request cap; deployment limits for deeper archive/JSON workloads | rate-limit/isolate externally | restart/scale/quarantine | `tests/test_http_api.py::test_http_rejects_oversized_request` | no universal memory/CPU budget in core |
| T15 | Supply chain | build/dependency path | malicious dependency/artifact | lockfile/build verification; external CI/repository controls | quarantine release | rebuild from trusted source | `tests/test_release_governance.py` | native CI/repository settings required |

## Cryptography policy

- **Algorithm:** Ed25519 for current StateWake signatures.
- **Signature representation:** signatures are carried as explicit encoded bytes/text according to the relevant serialized contract; verifiers reconstruct the canonical signed payload bytes before verification.
- **Hash:** SHA-256 is used for content addressing and digest binding.
- **Key ownership:** external signing providers own private signing material; StateWake receives signatures, not private keys.
- **Key lifecycle:** rotation and revocation are host/provider responsibilities exposed through `KeyLifecycleProvider`.
- **Trust checkpoints:** checkpoint signing keys are identified by key ID and bound to a public-key SHA-256 digest.
- **Compromise:** stop trusting the compromised key, revoke it through the configured lifecycle provider, rotate to a replacement, and re-attest/re-anchor affected material according to organizational incident policy.

## Input and resource security

Explicit current limits/controls:

- WSGI verification request body: **1 MiB default** (`VerificationServiceConfig.max_request_bytes`).
- Verification adapter is read-only.
- Verification paths must resolve inside configured artifact roots.
- HTTPS is required by default.
- ZIP member names are validated and the archive must match the expected manifest member set.
- No universal JSON nesting, provenance-node, list-length, or proof-bundle byte ceiling is currently enforced by the core. Such limits remain deployment/workload controls until explicitly introduced.

## Privacy model

The preferred evidence shape is reference + digest + metadata rather than unnecessary duplication of sensitive source payloads. `PrivacyPolicy` and `Redactor` provide deterministic metadata/event redaction. Redaction does not inspect opaque payload references. Applications remain responsible for deciding whether the underlying source payload itself may be stored or transmitted.

## Out of scope / not automatically protected

StateWake does not automatically protect against:

- compromised operating systems or Python runtimes;
- stolen or compromised signing keys;
- unprotected disks or hostile administrators;
- insecure deployment networking when TLS/authentication is not provided by the host;
- unlimited CPU/memory consumption in every verification path;
- incorrect business policy or incorrect producer decisions;
- malicious dependencies unless the deployment supply-chain controls detect them.

## Residual-risk handling

A verification result establishes the integrity properties covered by the controls. It does not prove that the underlying business decision was correct, that a producer was honest, or that the host environment was uncompromised. Residual risks must remain visible to the relying application and deployment owner.
