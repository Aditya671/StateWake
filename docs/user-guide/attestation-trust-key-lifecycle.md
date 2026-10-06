# Attestation Trust and Key Lifecycle Investigation

StateWake exposes a read-only operator view at `/attestation-trust` and `GET /api/v1/attestation-trust`. The surface reconstructs only relationships represented by the current repository authorities. It does not rotate keys, revoke anchors, sign attestations, or authorize a release.

## Sources and configuration

The read API accepts four independent configured sources:

- `STATEWAKE_UI_ATTESTATION_STORE`: the canonical append-only reliability outcome attestation JSONL chain.
- `STATEWAKE_UI_ATTESTATION_TRUST_STATE`: the current `SignedAttestationTrustState` snapshot. This is optional when the canonical history below is configured; the authenticated history tip may supply the current diagnostic state.
- `STATEWAKE_UI_ATTESTATION_TRUST_HISTORY`: the canonical append-only history of signed trust-state snapshots.
- `STATEWAKE_UI_ATTESTATION_AUTHORITY_STORE`: independently supplied authority public keys used by the existing Ed25519 trust-state verifier.

All source files are read through bounded, symlink-safe read paths. The attestation chain and trust-history predecessor chain are structurally verified before rows are projected. Historical lifecycle transitions are projected only when every trust-history snapshot authenticates against the independently configured authority store. The UI does not expose local paths, raw public keys, signatures, private key material, decision rationale, or arbitrary metadata.

## Durable trust-history authority

`JsonlAttestationTrustHistoryStore` is the canonical local persistence authority for signed trust-state history. A state is authenticated before append. The store rejects:

- version gaps or non-monotonic versions;
- `previous_digest` disagreement with the current history tip;
- non-monotonic or timezone-less `issued_at` values;
- mutation of public-key material under an existing key ID;
- reactivation or retargeting of revoked/superseded keys;
- a key ID that disappears and later reappears;
- conflicting reuse of an existing trust-state version;
- symlink traversal and invalid persisted history.

An exact retry of an already persisted signed state is idempotent. `append_attestation_trust_state(...)` may also atomically replace the separate current-state snapshot after the authenticated history append succeeds.

## What the surface can establish

The view keeps six questions separate:

1. **Attestation chain integrity:** are persisted outcome-attestation records structurally valid and hash-linked as recorded?
2. **Current trust-state authentication:** can the current state (configured directly or supplied by the history tip) be authenticated by an independently configured authority key?
3. **Current signing-key status:** only when the current trust state is authenticated, does the referenced key currently have status `active`, `revoked`, `superseded`, or is it absent from the authenticated anchor set?
4. **Historical trust-state integrity:** is the configured history predecessor-linked, version-contiguous, and lifecycle-valid?
5. **Historical lifecycle authority:** only when every history state authenticates may StateWake report observed activation, revocation, supersession, authority changes, or historical key-status observations.
6. **Signed attestation binding:** legacy attestation records remain valid, while the canonical outcome-attestation store may append a `signed-reliability-outcome-binding.v1` sidecar containing the existing `SignedReliabilityOutcomeEnvelope` and `ReliabilityAttestationTrustContext`. When the exact trust-state snapshot and independent authority store are available, StateWake can authenticate that signed envelope against the exact recorded trust-state digest/version without rewriting the legacy attestation chain.

An unauthenticated current trust-state snapshot may still be displayed as diagnostic data, including its recorded anchor statuses, but those statuses are not treated as current trust authority. Likewise, an unauthenticated history may establish structural predecessor continuity but does not authorize lifecycle conclusions.

## Historical verification boundary

The canonical history now preserves signed lifecycle evidence across trust-state versions. This makes statements such as “this key was observed active in an authenticated historical state and was later observed revoked” independently inspectable when the authority keys are available.

For attestations with a canonical signed sidecar, StateWake can establish that the recorded envelope verifies under a key that was `active` in the exact authenticated trust-state digest/version bound by the persisted `ReliabilityAttestationTrustContext`. This remains distinct from a trusted timestamp for the attestation event: `ReliabilityOutcomeAttestation.occurred_at` is application data, not an external timestamp authority. The UI therefore continues to keep `attestation_time_binding_recorded = false` and never infers chronological trust from `occurred_at`.

Legacy unsigned attestations remain readable and valid but have no recorded envelope/trust-context binding. Historical verification is also distinct from new signing permission: a key that is revoked or superseded may remain verifiable for a persisted historical binding, but it is never reactivated for current signing.

## Operational signed-attestation creation boundary

The read-only Attestation Trust UI remains an inspection surface and never becomes a signing control plane. Operational signed-attestation creation is exposed through the existing `reliability-attest` CLI command only when the complete external-signing configuration is supplied. The CLI uses `ExternalCommandSigningProvider` -> `ExternalSigningAdapter` -> `attest_signed_reliability_outcome(...)`; it does not introduce a second attestation, signature, or trust-state authority.

Before any external signing call, StateWake authenticates the exact supplied `SignedAttestationTrustState` against the independently supplied authority store and verifies that the referenced signing key is active. The external signer receives only the stable `SigningKeyReference` metadata and canonical payload bytes through the `statewake-external-signing.v1` subprocess protocol. Private key bytes remain outside StateWake. After signing, StateWake verifies the Ed25519 signature against the exact trust-state anchor and persists the canonical attestation plus `signed-reliability-outcome-binding.v1` sidecar atomically under the existing attestation-store lock.

This operational reachability does not alter historical semantics: exact signing-context binding still does not create a trusted external timestamp for `occurred_at`, current key status remains distinct from historical signing-state status, and the UI continues to expose only bounded diagnostic projections rather than raw signatures or key material.

## Operational signed-attestation verification boundary

The existing `reliability-attest-verify` command can also verify the canonical signed sidecar without creating a parallel verifier. Signed verification reuses `verify_persisted_signed_reliability_outcome(...)`, `resolve_reliability_attestation_trust_state(...)`, and `verify_reliability_attestation_trust_context(...)`, while ordinary unsigned invocation keeps the established attestation/evidence/state verification behavior.

The signed path requires the canonical attestation JSONL store and the independent authority store plus at least one source of signed trust states: the current snapshot, the append-only history, or both. The resolver selects only a state whose `version` **and** digest equal the values persisted in `ReliabilityAttestationTrustContext`. Supplying only a newer current state is therefore insufficient for an older binding unless its exact historical state is also available. Every supplied history state is structurally validated and authenticated before it can participate in resolution.

After exact-state resolution, StateWake authenticates the authority key, validates the recorded signing-key digest/status in that historical state, verifies the Ed25519 envelope, and requires the verified envelope attestation to equal the separately supplied attestation document. A later revocation remains a current lifecycle fact but does not invalidate an authentic historical signature that was bound to an earlier active state. Conversely, no current or historical state is accepted merely because its version is numerically close to the recorded version.

The command reports bounded verification metadata only. It does not expose raw signatures, public-key bytes, authority-key bytes, or complete signed envelopes, and it does not reinterpret `occurred_at` as a trusted signing timestamp.

## Query boundary

The collection endpoint supports only bounded, allowlisted filters:

- `decision`: `accept`, `review`, `reject`
- `reliability_state`: `reliable`, `degraded`, `unreliable`, `recovered`
- `key_status`: `active`, `revoked`, `superseded`, `untrusted`, `unsigned`, `trust-state-unauthenticated`, `trust-state-unconfigured`
- `q`: bounded case-insensitive search over attestation ID, subject ID, actor, evidence-chain ID, transition ID, and signing-key ID
- `limit` and `offset`: bounded pagination

Arbitrary filesystem paths, SQL, raw-key access, mutation requests, and unbounded scans are not part of this capability.
