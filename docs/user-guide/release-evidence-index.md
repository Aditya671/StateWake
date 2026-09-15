# Release Evidence Index

This index maps the public product claims to the evidence that supports them. It is intentionally evidence-first: a claim is either backed by executable validation, a documented architecture invariant, or an explicit limitation.

## Product claim map

| Claim | Evidence | Boundary |
|---|---|---|
| Evidence can be admitted with identity and integrity checks | Public API tests; five-minute example | Does not prove producer truthfulness |
| Evidence chains are independently verifiable | Chain verification tests and portable proof tests | Verification scope is defined by the chain contract |
| Tampering of retained evidence is detectable | Five-minute example; failure laboratory; real-world scenarios | Does not prove privileged deletion of an entire trailing history |
| Reliability state can be reconciled and recovered | State/reconciliation/recovery tests | Producer remains authoritative for source state |
| Attestations and proof bundles can be independently verified | Attestation/proof tests and release-proof tests | Key custody remains host-owned |
| Integrations can use the public SDK | SDK tests and golden applications | Examples use synthetic producer data |
| External evidence can be captured and validated | external-integration campaign | External provider correctness is outside StateWake's proof scope |
| Failure behavior is intentionally testable | Failure laboratory, property, chaos, and real-world campaigns | Campaign bounds are documented, not universal guarantees |
| The package can be consumed independently | Wheel build, package-boundary, and clean-consumer checks | Exact dependency/tool availability is environment-dependent |

## Executable product walkthroughs

### Five-minute first chain

`docs/examples/first-evidence-chain.py` creates evidence, admits it, builds and verifies a chain, then mutates the artifact and demonstrates rejection.

### Golden applications

- `docs/examples/golden/payment_reliability.py`
- `docs/examples/golden/enterprise_ai_reliability.py`
- `docs/examples/golden/municipal_decision_reliability.py`

Each demonstrates a valid path plus an application-specific deliberate failure.

## Validation evidence

The repository's release evidence includes:

- deterministic unit/integration regression;
- failure laboratory;
- property/state-machine campaigns;
- chaos, deep-chaos, and extreme validation;
- real-world synthetic scenario validation;
- external integration validation;
- package and artifact verification;
- source-quality and versioning verification;
- canonical archive checksum.

Exact results belong to the dated canonical verification reports rather than this index, so this page remains useful when individual campaign counts change.

## How to interpret this index

A green test is evidence for the behavior exercised by that test. It is not permission to generalize beyond the stated contract. See [Limitations](limitations.md), [Security](security.md), and [Release information](release.md) before treating the evidence as a deployment claim.
