# CLI Reference

The command-line executable is `statewake`.

```bash
statewake --help
statewake version
```

The CLI is a thin operational interface over the same domain and service authorities used by the library.

## Discover commands

Use:

```bash
statewake --help
statewake <command> --help
```

## Design rule

The CLI is not the architecture authority. New product behavior must first have a justified domain/service boundary and tests. CLI exposure follows the stable integration model rather than defining it.


## Signed reliability attestations

`reliability-attest` remains backward-compatible: without signing options it creates the existing unsigned canonical attestation. Signed mode is explicit and all-or-nothing. It reuses the existing signed-attestation service, `ExternalSigningAdapter`, canonical attestation store, exact `SignedAttestationTrustState`, and independently supplied authority store.

A signed invocation supplies the external signer executable and stable key reference without supplying private key bytes to StateWake:

```bash
statewake reliability-attest SUBJECT_ID \
  --chain chain.json \
  --history reliability-state.jsonl \
  --attestation-store reliability-attestations.jsonl \
  --actor operator \
  --signer-command /path/to/host-signer \
  --signing-key-id reliability-key-2026 \
  --signing-key-provider production-kms \
  --signing-key-public-digest <lowercase-sha256-hex> \
  --attestation-trust-state attestation-trust-state.json \
  --attestation-authority-store attestation-authorities.json
```

Use repeated `--signer-arg VALUE` options for non-secret signer process arguments and `--signer-timeout-seconds` to bound one signing request. `--signing-key-version` is optional. The exact trust-state snapshot is authenticated before StateWake invokes the signer, the selected signing key must be active in that state, and the resulting signature is verified before the canonical `signed-reliability-outcome-binding.v1` record is persisted. A signer failure, authority failure, revoked/superseded key, key-digest mismatch, signature failure, or trust-state mismatch fails closed without creating a signed binding.

The signer subprocess protocol is `statewake-external-signing.v1`. StateWake executes the configured command directly with no shell. It writes one UTF-8 JSON object to stdin containing only:

```json
{
  "protocol": "statewake-external-signing.v1",
  "key": {
    "key_id": "...",
    "provider": "...",
    "algorithm": "Ed25519",
    "version": "...",
    "public_key_digest": "..."
  },
  "payload_base64": "..."
}
```

The signer must return exactly one bounded UTF-8 JSON response:

```json
{
  "protocol": "statewake-external-signing.v1",
  "algorithm": "Ed25519",
  "key_id": "...",
  "signature_base64": "..."
}
```

The signature must decode to exactly 64 bytes. The provider process resolves the key reference and performs signing inside its own KMS/HSM or other host-managed custody boundary. StateWake does not accept a private-key CLI option and does not echo provider stderr into CLI failure messages.

`--output` retains its historical meaning and writes the attestation document. The canonical signed envelope/trust binding remains in `--attestation-store`; signed-mode stdout reports a bounded persistence/trust summary rather than raw signature material.

### Verifying a canonical signed attestation

`reliability-attest-verify` preserves its historical unsigned behavior when no signed-verification options are supplied. To verify the persisted signature/trust binding as well, provide the canonical attestation store and independent authority material plus either the current trust-state snapshot, the append-only trust-state history, or both:

```bash
statewake reliability-attest-verify \
  --attestation attestation.json \
  --chain chain.json \
  --history reliability-state.jsonl \
  --subject-id SUBJECT_ID \
  --attestation-store reliability-attestations.jsonl \
  --attestation-trust-history attestation-trust-history.jsonl \
  --attestation-trust-state attestation-trust-state.json \
  --attestation-authority-store attestation-authorities.json
```

Signed verification is all-or-nothing. StateWake first verifies the ordinary attestation/evidence-chain/state-transition binding. It then reads the canonical `signed-reliability-outcome-binding.v1` sidecar for that exact attestation, resolves the recorded trust-state **version and digest** from the supplied authenticated current state/history, authenticates the authority key, verifies the signing key and Ed25519 envelope, and finally confirms that the verified signed attestation is byte-for-byte equivalent at the domain-contract level to the supplied attestation document.

This allows an older attestation to remain verifiable after its signing key has later been revoked or superseded: the verifier selects the exact historical signing state recorded by the binding rather than applying the current key status retroactively. Missing bindings, unavailable exact trust states, authority mismatch, signing-key mismatch, tampering, invalid signatures, or partial signed-verification configuration fail closed. CLI output reports only bounded identifiers/digests and never emits the raw signature, public-key bytes, or authority-key bytes. Exact signed-context verification still does not create an external trusted timestamp for `occurred_at`.

### Building a portable proof from canonical signed evidence

`reliability-proof-bundle` keeps its existing manual `--signed-attestation` mode for compatibility, but it can now consume the canonical signed binding directly. Canonical mode uses the same attestation store and exact historical trust-state resolution as `reliability-attest-verify`:

```bash
statewake reliability-proof-bundle \
  --attestation attestation.json \
  --chain chain.json \
  --history reliability-state.jsonl \
  --evidence-root evidence-root \
  --output reliability-proof.zip \
  --attestation-store reliability-attestations.jsonl \
  --attestation-trust-history attestation-trust-history.jsonl \
  --attestation-trust-state attestation-trust-state.json \
  --attestation-authority-store attestation-authorities.json
```

`--attestation-trust-state` is optional when the authenticated history already contains the exact recorded signing state. When both current state and history are supplied, they are available as candidate states but the proof packages only the exact `(trust_state_version, trust_state_digest)` recorded by the canonical signed binding. This means a proof can package a historical state in which the signing key was active even when the current state later marks that key revoked or superseded.

Canonical mode verifies the persisted `signed-reliability-outcome-binding.v1` before packaging anything. It then emits the already recorded envelope, the exact authenticated signing-state snapshot, the authority key required to authenticate that snapshot, and a bundle-local `ReliabilityAttestationTrustContext`. The bundle-local context changes only the portable artifact IDs; its attestation, envelope, signing-key, trust-state, and authority digests remain bound to the verified canonical evidence.

Manual `--signed-attestation` input and canonical `--attestation-store`/`--attestation-trust-history` input are mutually exclusive. Partial canonical configuration, a missing sidecar, an unavailable exact trust state, authority/signing-key mismatch, tampering, or signature failure fails closed. Offline `reliability-proof-verify` remains self-contained and does not require the original attestation store or trust history.

### Propagating canonical signed trust through `release-proof`

The higher-level `release-proof` workflow accepts the same manual and canonical signed-trust inputs as `reliability-proof-bundle`. Canonical mode verifies the persisted signed binding and exact historical signing state before the release claim profile is reported as verified:

```bash
statewake release-proof \
  --attestation attestation.json \
  --chain chain.json \
  --history reliability-state.jsonl \
  --evidence-root evidence-root \
  --output release-proof.zip \
  --report release-verification.json \
  --attestation-store reliability-attestations.jsonl \
  --attestation-trust-history attestation-trust-history.jsonl \
  --attestation-trust-state attestation-trust-state.json \
  --attestation-authority-store attestation-authorities.json
```

Unsigned `release-proof` behavior remains unchanged when no signed-trust options are supplied. In signed mode the release verification report records `signed_attestation_trust_verified`; when canonical history is used it also records `historical_signing_trust_state_resolved`. The report exposes only the bounded trust-context fact and does not include raw signatures or public-key material. Signature/trust verification still does not authorize a release: human release approval remains a separate decision.

The same all-or-nothing and mutual-exclusion rules used by `reliability-proof-bundle` apply to `release-proof`. A missing canonical sidecar, unavailable exact historical state, authority mismatch, signing-key mismatch, tampered signature, or partial trust configuration fails the release-proof operation rather than silently falling back to unsigned assurance.

### Re-evaluating a release proof after canonical human approval

The Review API records `HumanApprovalContract` evidence against one exact immutable verification-report digest. It intentionally does not mutate that report. After approval has been recorded, `release-proof` can re-run the machine verification and reconcile the canonical approval into a **new** report:

```bash
statewake release-proof \
  --attestation attestation.json \
  --chain chain.json \
  --history reliability-state.jsonl \
  --evidence-root evidence-root \
  --output release-proof-approved.zip \
  --report release-verification-approved.json \
  --human-approval-basis-report release-verification.json \
  --human-approval-workspace workspace \
  --human-approval-record-id <report-receipt-id> \
  --human-approval-producer-id statewake.review-api \
  --human-approval-action approve-release-evidence \
  --human-approval-scope "candidate release evidence"
```

All six `--human-approval-*` values plus `--report` are required together. The basis report and output report must be different paths. Reconciliation verifies the immutable basis-report digest, reruns the release proof, requires every machine-verification field except `generated_at` to remain identical, reads the approval through the canonical workspace approval store, and requires the recorded producer/action/scope plus candidate/profile metadata to match the approved basis exactly.

A successful re-evaluation emits a new report with `approval_status=approved`, includes the basis-report and approval receipt/artifact digests as provenance, and records the exact reconciled action/scope. It does **not** modify the original report, independently re-authenticate the human actor from the persisted contract, publish a release, or authorize side effects beyond the recorded scope. Ordinary `release-proof` behavior remains unchanged when no human-approval inputs are supplied.

## Supported commands

The following command names are part of the current CLI surface:

```text
version
evidence-ingest
evidence-verify
evidence-admission-verify
reliability-comparison
reliability-comparison-verify
evidence-chain
reliability-state-transition
reliability-state
reliability-attest
reliability-attest-verify
reliability-outcome-verify
reliability-recovery-verify
reliability-lineage-verify
reliability-reconciliation-bind
reliability-reconciliation-verify
reliability-proof-bundle
reliability-proof-verify
reliability-proof-completeness-verify
reliability-decision-basis-build
release-proof
```

Command names are compatibility-sensitive. New commands are additive; removal or
renaming requires a breaking-version decision. Flag additions are normally
backward-compatible. Exact human-readable help and error text are not frozen.
