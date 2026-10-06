# Reliability Proof Bundle & Portable Verification Investigation

StateWake's read-only UI can inspect one **explicitly configured portable reliability proof bundle** without rebuilding or modifying it.

Configure the local read API with:

```powershell
$env:STATEWAKE_UI_RELIABILITY_PROOF_BUNDLE = "C:\path\to\reliability-proof.zip"
python -m statewake.read_api
```

The corresponding route is:

```text
GET /api/v1/proof-bundle
```

The browser surface is `/proof-bundle`.

## Authority chain

The UI does not implement an independent verifier. The server first uses the existing `verify_bundle()` operational-package authority to verify ZIP/member/manifest/provenance integrity, then uses `verify_reliability_proof_bundle()` to reproduce the reliability outcome from the packaged artifacts.

```text
configured proof ZIP
  -> OperationalBundle verification
  -> ReliabilityProofBundleDescriptor
  -> packaged evidence/source completeness
  -> lineage closure when required by format
  -> completeness witness when required by format
  -> packaged trust-context consistency when present
  -> ReliabilityOutcomeVerificationReport reproduction
  -> read-only presentation projection
```

A malformed, tampered, structurally incomplete, oversized, or symlinked configured bundle fails closed and is not rendered as a partially trusted proof.

## Format semantics

StateWake currently recognizes reliability-proof descriptor format versions `1`, `2`, and `3`.

- Format `1` does not require a lineage-closure artifact or completeness witness.
- Formats `2` and `3` require verified lineage closure.
- Format `3` additionally requires the canonical proof-completeness witness.

The UI therefore reports legacy absence as **not required by format**, not as missing evidence.

## Trust-context boundary

When a proof includes `ReliabilityAttestationTrustContext`, offline verification checks the signed attestation envelope, packaged trust-state snapshot, packaged authority store, signing-key binding, and attestation binding using the existing proof verifier.

This establishes **portable cryptographic consistency within the proof bundle**. It does not independently establish that the authority key packaged inside the same proof is trusted by the current operator. External trust-root configuration remains a relying-application responsibility.

### Canonical signed-proof construction

Proof construction can use the canonical `JsonlReliabilityOutcomeAttestationStore` instead of requiring an operator to export and resupply a separate signed-envelope JSON document. In canonical mode StateWake reads the unique `signed-reliability-outcome-binding.v1` for the supplied attestation, authenticates the configured trust-state history/current state, resolves the exact version and digest recorded by the binding, verifies the envelope against that historical state, and only then packages the portable proof trust artifacts.

The persisted trust context is runtime-storage evidence and may reference runtime artifact IDs. The portable proof therefore rebuilds the context through the existing trust-context builder using proof-local artifact IDs while preserving the verified attestation, envelope, signing-key, trust-state, and authority identities/digests. No signature is regenerated and no trust state is inferred from the attestation timestamp.

The original manual signed-envelope proof path remains supported for backward compatibility; manual and canonical trust-input modes cannot be combined in one build.

## Data exposed to the browser

The read projection exposes only bounded inspection metadata:

- bundle and manifest identity;
- proof format and descriptor identity;
- subject, attestation, evidence-chain, and transition identities/digests;
- verification checks;
- format-specific lineage/completeness state;
- packaged source reference keys and digests;
- artifact IDs, kinds, sizes, sensitivities, digests, and derivation IDs;
- trust-context key identities and digests when present;
- explicit limitations and authorization boundaries.

It intentionally omits ZIP member paths and raw embedded artifact/source bytes.

## Portable dataset is a different format

A StateWake workspace portable dataset ZIP and a reliability proof bundle are not interchangeable.

The workspace portable-bundle format explicitly records `proof_bundle: false`. It packages bounded dataset rows and checksums for data portability. It is not the `ReliabilityProofBundleDescriptor` format and is not accepted by `/api/v1/proof-bundle` as a reliability proof.

## What a verified proof does not mean

A successful offline verification means the bounded StateWake relationships, identities, digests, completeness requirements, and verification checks encoded by the proof were reproduced successfully.

It does **not** by itself establish:

- factual correctness of an external AI/model/tool output;
- human publication approval;
- release authorization;
- business authorization;
- independent trust in a packaged authority key;
- correctness of systems outside the proof's explicit verification boundary.

The UI is read-only and does not build, sign, export, approve, publish, or mutate proof bundles.
