# Architecture Decision Index

| ADR | Decision | Status |
| --- | --- | --- |
| [0003](../adr/0003-current-architecture.md) | StateWake is a reliability-evidence infrastructure layer centered on `ReliabilityEvidenceChain`; producer systems remain authoritative for their own execution data. | Accepted |
| [0004](../adr/0004-security-architecture.md) | StateWake security is defined around explicit trust boundaries, integrity controls, signed checkpoints, and bounded residual risk. | Accepted |

## Historical decision provenance

ADR identifiers 0001 and 0002 belong to the earlier architecture history and are superseded by ADR 0003. Their original ADR files are not present in the current source tree, so this index does not expose broken links or imply that those documents are retained. ADR 0003 records the supersession of the earlier domain-model decision.

## Current identity

StateWake is the current project identity. The package distribution is `statewake-ai`, the Python import namespace is `statewake`, and the CLI executable is `statewake`.

StateWake is the sole active project identity and naming authority.

## Decision-log boundary

This file indexes architectural decisions that are actually present in the repository. Prior release records remain under `docs/releases/`. Dated research or evaluation material is evidence, not a competing current architecture authority.
