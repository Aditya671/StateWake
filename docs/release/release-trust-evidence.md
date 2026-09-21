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
