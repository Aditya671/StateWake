# Tier 7 — Trust-Domain & Anchor Assurance

## Status

This document defines the StateWake Tier 7 **development assurance** mechanism. It is not a release approval, certification, production-readiness approval, or a claim that a local checkpoint is independently trustworthy merely because it is signed.

## Objective

Tier 7 composes the existing trust-checkpoint, attestation-trust, signing-lifecycle, recovery, provenance, and audit primitives into an explicit trust-domain assurance contract. The smallest justified addition is an evidence verifier and regression suite; deployment separation itself remains a deployment-owner responsibility.

## Trust-domain model

The reference architecture distinguishes these security domains:

| Domain | Role | Boundary requirement |
|---|---|---|
| D1 | Runtime/core | Must not implicitly control all other trust functions |
| D2 | Evidence store | Evidence custody can be independently administered where required |
| D3 | Signing domain | Private signing capability stays outside StateWake core |
| D4 | Checkpoint domain | Checkpoint authority/storage can be independently administered |
| D5 | Audit/security domain | Security verification records can be independently retained |
| D6 | Build/release domain | Produces executable artifacts; addressed more fully by Tier 8 |

Independence is a spectrum rather than a binary property: same process → same host/separate module → separate process → separate credential → separate storage → separate administrative authority → separate security domain. Only separations justified by the threat model should be required.

## Existing capabilities reused

Tier 7 does not create parallel trust or key-management subsystems. It reuses:

- `TrustCheckpoint` and `compare_local_tip()` for checkpoint verification/discrepancy detection;
- `JsonTrustAnchorStore` for non-overwriting checkpoint persistence;
- `ExternalSigningAdapter` and lifecycle-provider protocols for external private-key custody;
- `SignedAttestationTrustState` and its separately supplied authority verifier for attestation-key lifecycle;
- recovery authority and non-invention semantics from Tier 6;
- security audit and provenance controls already mapped by the Tier 4/Tier 5 assurance layers.

## Key-purpose separation

At minimum, this architecture treats these purposes as distinct trust functions:

- artifact signing;
- checkpoint signing;
- release signing;
- deployment credentials/secrets.

A common implementation may use separate providers, accounts, keys, or administrative owners. StateWake must not claim that one configured key automatically provides independence for every purpose.

## Key rotation assurance

A trustworthy rotation evidence record needs, at minimum:

```text
old key identity
      ↓
rotation event
      ↓
new key identity
      ↓
activation boundary
      ↓
revocation/supersession state where applicable
      ↓
historical verification policy
```

The existing attestation trust-state continuity chain and explicit `revoked` / `superseded` states are reused. Historical signatures remain verifiable only according to the applicable historical trust policy.

## Independent checkpoint assurance

A checkpoint is an independent trust signal only when its verifier, custody, and administrative authority are appropriately separated from the failure domain under consideration. A locally signed or locally stored checkpoint is **not** called independent solely because it carries a valid signature.

The reference `JsonTrustAnchorStore` deliberately rejects conflicting overwrite and validates checkpoint sequence. Deployment may strengthen this boundary with external storage, external signing, separate credentials, or separate administrative ownership without changing StateWake core semantics.

## Trust-anchor compromise behavior

If the anchor itself is suspected compromised, the anchor must not be treated as self-authenticating authority. The required behavior is:

1. classify anchor evidence as suspect;
2. preserve the observed anchor and local history without silent overwrite;
3. obtain an independent organizational or deployment authority where available;
4. compare candidate histories/checkpoints explicitly;
5. re-establish trust only through a documented replacement authority or other independently supported evidence.

StateWake provides deterministic discrepancy detection; organizational authority, external registry custody, and out-of-band approval remain deployment responsibilities.

## Tier 7 invariants

- D1 compromise must not be described as automatically equivalent to compromise of D3/D4/D5/D6; actual separation must be demonstrated by deployment evidence.
- Checkpoint disagreement is a security discrepancy, not a repair instruction.
- Key purpose must be explicit; one key must not be presented as independent evidence for every purpose.
- Historical key state is evaluated through the applicable trust policy rather than rewritten retroactively.
- An anchor's signature proves integrity/authenticity under its configured verification authority; it does not by itself prove administrative independence.

## Verification evidence

`scripts/security/verify_trust_domain_anchors.py` checks consistency among this document, the existing trust-anchor and attestation-trust implementations, Tier 6 recovery boundaries, the release boundary, and the Tier 7 regression suite. The executable suite tests checkpoint non-overwrite, checkpoint disagreement, key-purpose separation declarations, trust-state revocation/supersession semantics, and anchor-compromise handling without claiming external independence that the repository cannot prove.

## Exit condition

Tier 7 is complete for this development baseline when executable evidence demonstrates:

- meaningful trust-domain separation requirements are explicit;
- key purposes are explicitly separated;
- checkpoint verification is deterministic;
- trust-anchor compromise behavior is explicit;
- recovery authority boundaries remain documented;
- no local signature is falsely presented as proof of independent trust.

## Boundaries and residual risk

This tier does not create separate hosts, external registries, KMS/HSM systems, administrative organizations, immutable cloud storage, or independent security operations. Those are deployment controls. The repository can verify protocol contracts and reference adapter behavior, but cannot prove real-world administrative independence without deployment evidence.

## Development-only boundary

The current package identity is `v0.3.0`. This is a promoted development assurance baseline only. No release tag, publication, package upload, or release artifact is authorized by this document.
