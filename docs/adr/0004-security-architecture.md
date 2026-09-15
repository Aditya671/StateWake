# ADR 0004 — StateWake Security Architecture

## Status

Accepted — 2026-09-13.

## Context

StateWake is a reliability-evidence system centered on the `ReliabilityEvidenceChain` composition primitive. Its security objective is to make admitted evidence, provenance, state, attestations, and portable proofs resistant to unauthorized mutation and ambiguity. It is not an authentication system, host-hardening system, network perimeter, policy engine, or immutable storage service by itself.

failure testing, generated verification, and independent trust checkpoints exposed the controls and residual risks that must be made explicit.

## Decision

Security is modeled as: asset + adversary + capability + attack + control + residual risk.

The primary trust path is:

```text
Producer
  | untrusted evidence / metadata / transport
  v
Adapter / HTTP boundary
  | validation + size/path constraints
  v
StateWake evidence and reliability core
  | content digests + hash chains + typed state transitions
  v
Persistence / portable proof boundary
  | locking + atomic writes + manifest cross-checks
  v
Independent trust anchor (optional but stronger)
  | signed checkpoint + separate key/store boundary
  v
Verifier / relying party
```

Private signing material remains outside StateWake when external signing is used. Ed25519 is the current signing algorithm for attestation and trust-checkpoint signatures. Canonical byte representations are signed rather than Python object layouts.

The complete threat and control model is maintained in `docs/security/THREAT_MODEL.md`, with executable mappings in `docs/security/CONTROL_TEST_MATRIX.md`.

## Consequences

- Integrity controls are explicit and test-linked.
- Local hash chains are not described as proof against deletion of trailing history; independent checkpoints are the control for that gap.
- HTTP deployment remains bounded and read-only, with HTTPS required by default.
- Sensitive source payload duplication is minimized where reference + digest + metadata is sufficient.
- Resource exhaustion beyond explicit application limits remains a deployment responsibility.
- A compromised host, Python runtime, signing key, or administrator with simultaneous control of history and anchor storage is outside the guarantees.

## Rejected alternatives

- Treating cryptography alone as the security architecture.
- Making StateWake responsible for application authentication or tenant isolation.
- Claiming the local filesystem trust-anchor reference implementation is independently immutable.
- Replacing domain validation with broad exception suppression.
