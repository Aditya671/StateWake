# Architecture Decision Index

| ADR | Decision | Status |
| --- | --- | --- |
| [0003](../adr/0003-current-architecture.md) | StateWake is a reliability-evidence infrastructure layer centered on `ReliabilityEvidenceChain`; producer systems remain authoritative for their own execution data. | Accepted |
| [0001](../adr/historical/0001-project-boundary.md) | Historical project-boundary decision; superseded by ADR 0003 for the current product architecture. | Superseded |
| [0002](../adr/historical/0002-domain-primitives.md) | Historical initial domain-primitives decision; superseded by ADR 0003 for the current domain model. | Superseded |

## Current identity

StateWake is the current project identity. The package distribution is `statewake-ai`, the Python import namespace is `statewake`, and the CLI executable is `statewake`.

StateWake is the sole active project identity and naming authority.

## Decision-log boundary

This file indexes architectural decisions. Dated evaluation reports, business-plan comparisons, release-verification snapshots, and remediation responses are historical evidence rather than competing current architecture authorities. Historical copies are retained under `repository historyhistorical-evaluations/`.
