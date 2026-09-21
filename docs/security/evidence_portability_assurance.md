# Tier 9 — Evidence-Portability & Independent Verification Assurance

## Status

This is a **development assurance** artifact. It is not a release approval, certification, production-readiness approval, or publication authorization.

## Objective

Tier 9 extends the existing V3 reliability proof bundle into a portable verification boundary:

```text
StateWake runtime
       ↓
portable reliability proof
       ↓
runtime-independent verifier
       ↓
explicit verification outcome
```

The existing `ReliabilityProofBundle` remains the package authority. Tier 9 adds a separate, read-only verifier that does not import the StateWake runtime.

## Reused capabilities

No second proof-bundle or ZIP/manifest implementation is introduced. Tier 9 reuses the existing V3 package produced by `reliability_proof_bundle_service.py`, including manifest integrity, evidence/source digests, lineage closure, completeness binding, transition binding, and optional attestation trust context.

## Independent verifier contract

`scripts/security/verify_reliability_proof_portability.py` reads only the portable ZIP and optional externally supplied trust-root JSON. It verifies:

- package member and manifest integrity;
- deterministic manifest and bundle identifiers;
- proof descriptor integrity and completeness coverage;
- evidence-chain identity and digest binding;
- state-history presence and exact transition binding;
- attestation digest and verification status;
- optional Ed25519 trust-state and attestation signatures when an explicit external authority key is supplied.

The verifier has no dependency on `statewake`, no access to the originating evidence filesystem, and no mutation path.

## Verification outcomes

The verifier uses the V2 vocabulary:

`VERIFIED`, `VERIFIED_WITH_LIMITATIONS`, `UNVERIFIED`, `INVALID`, `TAMPERED`, `INCOMPLETE`, `TRUST_ANCHOR_UNAVAILABLE`.

An unsigned/externally unanchored package can establish integrity and structural proof validity, but is returned as `VERIFIED_WITH_LIMITATIONS` because an external trust root was not supplied.

## Minimal disclosure

The verifier operates against the portable package. The V3 completeness contract determines the exact included artifact set, while the existing proof descriptor carries sensitivity classifications. Tier 9 does not add original payload export.

## Cross-version semantics

The package declares its proof format version through the existing V3 descriptor. Unsupported formats are rejected rather than silently interpreted under new rules.

## Residual risks

Repository code cannot prove the authenticity of a separately supplied trust root, CI administrative controls, registry controls, or the operator's handling of the portable package. Those remain explicit trust/deployment boundaries.

## Exit condition

Tier 9 is satisfied for the development candidate when an independent verifier can establish the claimed subject/outcome, package integrity, evidence-chain binding, state-transition binding, and attestation authenticity when an applicable external trust root is supplied, while explicitly surfacing limitations when that root is unavailable.
