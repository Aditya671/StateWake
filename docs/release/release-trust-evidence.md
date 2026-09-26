# Release Trust Evidence

Phase 6 separates two trust layers:

1. StateWake package/release trust: how the `statewake-ai` artifact was built, checked, described, and approved or limited.
2. StateWake-managed AI-system claim trust: the evidence chains and claim profiles StateWake records for external AI workflows.

The `statewake.release_trust` package models the first layer only. It does not replace SLSA, Sigstore, SBOM generators, vulnerability scanners, CI/CD, or human release authorization. It records digest-bound references to those external artifacts so StateWake can reason about whether a release claim has enough evidence.

## Bundle contents

A release-trust bundle contains:

- package artifact digest and size;
- source identity, source-tree digest, and dependency-lock digest;
- build provenance context and build steps;
- test evidence;
- SBOM evidence;
- vulnerability-scan evidence;
- signature evidence or an explicit signing limitation;
- external build provenance evidence;
- a human release decision boundary.

Unsigned development releases must record a limitation. A missing or unavailable signature is never converted into a pass.

## Human approval boundary

The bundle may show that evidence is complete, but publication approval remains separate. An approved human decision requires a digest-bound basis. A pending decision can still produce a release-trust bundle for review, but it must not be treated as release authorization.

## Claim profile bridge

`evaluate_release_trust_bundle()` converts the bundle into references compatible with the existing `release_evidence_complete.v1` profile. This avoids adding a parallel profile system while allowing Phase 6 release evidence to feed the Phase 2 claim-profile surface.

## Content versus structural verification

`evaluate_release_trust_bundle()` evaluates supplied references and declared state structurally. It does **not** resolve artifact, SBOM or signature bytes. Use `verify_release_trust_files(bundle, root)` for an independent, local size/digest check of those files; inspect `missing`, `mismatched` and `limitations`. It deliberately does not claim cryptographic signature or trust-anchor verification, nor the truth of a scan or test result. Publication remains a separate human decision.


## Optional authenticated release verification (forward-only improvement)

`verify_release_authenticity(bundle, root, trusted_signers={"release-key-1": public_key})` checks **all** locally referenced file bytes before verifying a detached Ed25519 signature from a key independently configured by the relying application. For signed bundles, `signature.status` must be `present` and the signature JSON file must contain exactly `key_id` and `signature_hex`. Its exact file bytes must match `signature.digest`. Sign the bytes returned by `release_signature_payload(bundle)`; these are a domain-separated canonical payload excluding the detached signature reference, avoiding circular signatures.

`assess_authenticated_release` returns distinct booleans for structural profile satisfaction, verified referenced content, authenticated signer, claimed human approval and publication authorization. A valid release-signer signature does **not** independently authenticate a human actor, establish that external tests or scans ran, or authorize publication. The original structural `evaluate_release_trust_bundle` and local-content `verify_release_trust_files` retain their previous, narrower meanings.

The new `authenticate_producer_receipt` API authenticates a producer-supplied `ExternalEvidenceReceipt` with an externally configured key bound to `(producer_type, producer_id, key_id)`; it does **not** establish artifact bytes or producer honesty. Provision/revoke trust keys outside untrusted evidence. These APIs require the project's declared PyNaCl runtime dependency for real Ed25519 verification.
