# Tier 15 — Cryptographic Longevity & Trust Migration

Tier 15 defines StateWake-native semantics for deliberate cryptographic and trust transitions. It does not add speculative cryptographic algorithms; it makes algorithm, key, trust-root, proof-format, and canonicalization identity explicit so historical evidence remains interpretable.

## Contract

Portable evidence may identify its proof schema version, canonicalization version, digest algorithm, signature algorithm, trust-policy version, and verifier compatibility. Key identities are versioned and retain historical status after retirement or revocation. Rotations produce an explicit successor relationship rather than silently reusing an old identity.

Trust migrations identify the old and new roots, transition authority, activation boundary, and verification policy. Proof-format migrations identify source and destination versions, canonicalization, compatibility mode, and migration authority.

Historical verification is distinct from permission to perform new signing. A retired or revoked key can remain addressable for historical verification without becoming active again.

## Existing compatibility

Existing proof bundles remain unchanged when no cryptographic profile is supplied. Tier 15 metadata is an additive optional field, allowing older evidence to remain readable while new evidence can make the cryptographic contract explicit.

## Security boundary

Private signing keys remain outside StateWake. Enterprise KMS/HSM, network protection, certificate infrastructure, and external key custody remain deployment/provider responsibilities.
