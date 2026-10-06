# StateWake

> **Evidence-backed reliability infrastructure for AI systems.**

StateWake provides a deterministic reliability layer around AI and software systems. It captures evidence, preserves provenance and integrity, tracks reliability state, supports verification and recovery, and produces auditable records that can be independently inspected instead of relying on a model, log stream, or dashboard to assert that a system behaved correctly.

StateWake is designed to integrate with existing agent runtimes, retrieval systems, evaluators, CI/CD pipelines, telemetry, storage, and release workflows. It does **not** replace those systems or become a second execution authority.

- **Source version:** `0.5.0`
- **Public API contract:** `1`
- **Distribution:** [`statewake-ai`](https://pypi.org/project/statewake-ai/)
- **Import package:** `statewake`
- **CLI:** `statewake`
- **Supported Python:** `>=3.11,<3.14`
- **License:** [Apache-2.0](https://github.com/Aditya671/StateWake/blob/main/LICENSE)
- **Repository:** [github.com/Aditya671/StateWake](https://github.com/Aditya671/StateWake)

> **Release status:** the repository source is on the `v0.5.0` line. The latest published PyPI release remains `v0.4.1` until the v0.5.0 publication workflow, governance checks, and explicit publication authorization are completed.

---

## Why StateWake exists

Modern AI systems can involve models, agents, retrieval, tools, policies, external services, human approval, telemetry, and deployment automation. A log or evaluation score can show an observation, but it does not by itself establish a durable reliability record.

StateWake makes that record explicit:

```text
System / agent execution
        ↓
Captured evidence
        ↓
Evidence admission + identity
        ↓
Provenance + integrity verification
        ↓
Reliability evaluation / comparison
        ↓
Reliability state
        ↓
Reconciliation / recovery evidence
        ↓
Attestation / decision basis
        ↓
Durable workspace + query / export
        ↓
Human review / approval / release evidence
```

The core idea is simple: **evidence and state transitions should remain verifiable outside the component that produced them.**

---

## What StateWake provides

### Reliability evidence and state

- Deterministic evidence admission and canonical external-evidence receipts.
- `ReliabilityEvidenceChain` construction and integrity verification.
- Reliability state snapshots and hash-linked state transitions.
- Reliability outcome verification and verification reports.
- Behavioral comparison, reconciliation, recovery evidence, and decision-basis construction.
- Reliability outcome attestations and portable proof bundles.
- Claim profiles with explicit missing-evidence and caveat handling.

### Producer and application integration

- Framework-neutral `StateWakeClient` integration API.
- File, CI/CD, evaluation, incident/recovery, OpenTelemetry, webhook, queue, database, batch, and agent evidence adapters.
- Distinct producer identity, run identity, source-event identity, artifact identity, and receipt identity.
- Idempotent repeated evidence with conflict detection when an identity is reused for different content.

### Native AI/framework integrations

StateWake includes optional native integration surfaces for:

- OpenAI Agents
- LangChain Core
- LangGraph
- LlamaIndex Core
- OpenTelemetry SDK

The current v0.5.0 source includes independent-oracle, credential-free native-host qualification support for these five integration families. Host-owned truth and StateWake observations remain separate evidence streams.

### Durable workspace and data access

- Durable operational indexing and historical query surfaces.
- JSON, CSV, XLSX, Parquet, SQLite, and portable dataset/export support where applicable.
- Workspace integrity verification, retention/lifecycle state, backup/restore, and migration markers.
- Analytical access through the maintained workspace adapters without turning an analytical projection into evidence authority.

### Trust, security, and recovery

- Content and evidence integrity verification.
- Independent trust checkpoints and trust-anchor comparison.
- External Ed25519 signing boundaries without passing private key material into StateWake.
- Signing-key lifecycle, revocation, supersession, and historical trust interpretation.
- Security-incident evidence, affected trust state, recovery evidence, and post-recovery verification.
- Continuous security/release assurance records that preserve `UNKNOWN`, `STALE`, `CONFLICT`, and other non-success states rather than silently upgrading certainty.

### Human review and approval

- Append-only review statements bound to an exact report/candidate digest.
- Canonical human-approval evidence with scoped action and authority boundaries.
- Approval revocation and supersession lifecycle while preserving historical evidence.
- Fresh reconciliation that consumes currently active approval evidence instead of treating a historical approval as permanently valid.

### Release and registry evidence

The v0.5.0 source extends the reliability model to software publication itself:

- Release publication basis bound to exact source, verification evidence, target registry, and distribution digests.
- Publication execution permits that fail closed if candidate bytes or approval state change.
- PyPI/TestPyPI publication receipts.
- Independent registry read-back of exact distribution files.
- Digest-chained registry lifecycle observations for available, yanked, partially available, and unavailable states.
- Separation between **verification**, **human authorization**, **publication execution**, and **post-publication registry evidence**.

---

## Product boundary

StateWake is **not**:

- an agent orchestration framework;
- a general observability platform;
- a hosted control plane;
- a generic chaos-testing product;
- an identity provider;
- a replacement for CI/CD, telemetry, or model evaluation;
- proof that an upstream model answer is factually correct;
- proof that an external producer is honest merely because evidence is signed;
- automatic authorization to publish, deploy, pay, message, delete, or perform another consequential action.

StateWake records and verifies the boundaries it controls. External truth, permissions, business policy, infrastructure security, and independent trust roots remain explicit responsibilities of the integrating system.

---

## Installation

The package distribution is named `statewake-ai`; Python code imports `statewake`.

### Current public PyPI release

```bash
python -m pip install statewake-ai
```

At the time of this source snapshot, PyPI still publishes the `v0.4.1` release.

### Install the v0.5.0 source candidate from this repository

```bash
git clone https://github.com/Aditya671/StateWake.git
cd StateWake
python -m pip install .
```

Or with `uv`:

```bash
uv sync
```

### v0.5.0 PyPI installation after publication

```bash
python -m pip install statewake-ai==0.5.0
```

### Native integration extras

Install one integration family:

```bash
python -m pip install "statewake-ai[integrations-openai-agents]"
python -m pip install "statewake-ai[integrations-langchain]"
python -m pip install "statewake-ai[integrations-langgraph]"
python -m pip install "statewake-ai[integrations-llamaindex]"
python -m pip install "statewake-ai[integrations-opentelemetry]"
```

Or all maintained integration extras:

```bash
python -m pip install "statewake-ai[integrations]"
```

For the checked-out v0.5.0 source, use the equivalent local extras, for example:

```bash
python -m pip install ".[integrations]"
```

`pyproject.toml` is the authority for dependency declarations and `uv.lock` records the repository's locked Python dependency state.

---

## Quick start

### Verify an existing evidence chain

```python
from pathlib import Path

from statewake import load_evidence_chain, verify_evidence_chain

chain = load_evidence_chain(Path("./evidence/chain.json"))
verify_evidence_chain(chain, root=Path("./evidence"))
```

### Integrate an application with `StateWakeClient`

```python
from statewake import IntegrationContext, StateWakeClient

client = StateWakeClient.for_root(
    IntegrationContext(
        producer_id="orders-service",
        run_id="run-123",
    )
)

receipt = client.ingest_bytes(
    b"event payload",
    producer_type="application",
    source_ref="event-123",
    source_event_id="event-123",
)

client.verify_receipt(receipt)
```

The SDK is intentionally thin: it captures producer evidence and delegates persistence and verification to StateWake's canonical authorities rather than creating a parallel evidence model.

### Public Python API

The stable consumer surface is exported from the top-level `statewake` package. Prefer:

```python
from statewake import (
    admit_evidence,
    build_evidence_chain,
    read_reliability_state,
    verify_evidence_chain,
    verify_outcome,
)
```

over imports from internal implementation modules.

See the complete [public API contract](https://github.com/Aditya671/StateWake/blob/main/docs/reference/API_CONTRACT.md).

---

## CLI

StateWake installs the `statewake` command:

```bash
statewake version
statewake --help
```

The CLI exposes the maintained evidence, verification, reliability-state, attestation, recovery, reconciliation, proof-bundle, decision-basis, release-proof, and related operational workflows.

Discover the current command surface with:

```bash
statewake --help
statewake <command> --help
```

See the [CLI reference](https://github.com/Aditya671/StateWake/blob/main/docs/user-guide/cli.md).

---

## HTTP and service boundaries

StateWake's core does not require FastAPI or Flask.

### Verification WSGI boundary

```text
statewake.server:app
```

The WSGI boundary exposes bounded verification endpoints such as health/version, evidence verification, and proof verification. It is designed as an internal/trusted integration edge rather than a ready-made public multi-tenant service.

Authentication, authorization, TLS termination, tenant isolation, request limits, network policy, and monitoring remain deployment responsibilities.

### Read and review services

The optional workspace UI uses separate Python boundaries:

- `statewake.read_api` for bounded, read-only projections of canonical workspace evidence.
- `statewake.review_api` for separately authenticated and authorized human review/approval operations.

The split is intentional: reading evidence and creating approval/review evidence are different authorities.

---

## Optional web UI

The repository includes an optional Next.js UI under [`ui/`](https://github.com/Aditya671/StateWake/tree/main/ui).

It provides human-facing inspection surfaces for areas such as:

- workspace overview and claim/report discovery;
- evidence and verification detail;
- reliability-state history and report comparison;
- incident and recovery investigation;
- producer capture-health/failure-journal inspection;
- portable proof-bundle verification;
- decision basis, reconciliation, and lineage inspection;
- operational trust and assurance projections;
- review statements and scoped human approvals.

The UI is **not** a second verifier or control plane. Verification and authority remain in the Python services and canonical evidence stores.

The UI has its own dependency-backed TypeScript/test/build qualification boundary. See [`ui/README.md`](https://github.com/Aditya671/StateWake/blob/main/ui/README.md) before treating the frontend as deployment-qualified.

---

## Native integration model

```text
Host framework / SDK
        ↓
Native StateWake integration adapter
        ↓
Canonical evidence admission
        ↓
Durable receipt / workspace
        ↓
Reliability evidence lifecycle
```

Native adapters must preserve host/framework semantics rather than inventing missing events or treating a callback as proof that an external action succeeded.

The v0.5.0 source includes a local independent-oracle qualification harness that exercises actual installed SDK APIs without requiring paid model calls. This evidence qualifies the tested local SDK/host boundary only; it does not claim external public repositories or live providers were independently qualified.

See:

- [Native framework capabilities](https://github.com/Aditya671/StateWake/blob/main/docs/integrations/native-framework-capabilities.md)
- [Native integration verification](https://github.com/Aditya671/StateWake/blob/main/docs/integrations/native-integration-verification.md)
- [SDK integration](https://github.com/Aditya671/StateWake/blob/main/docs/reference/SDK_INTEGRATION.md)

---

## Workspace model

StateWake keeps canonical reliability evidence separate from derived views and analytical projections.

```text
Canonical evidence / receipts
          ↓
Durable workspace
          ├── query / history
          ├── deterministic projections
          ├── exports / portable datasets
          ├── operational diagnostics
          └── optional analytics
```

A query result, spreadsheet, Parquet dataset, UI card, or analytical database is not automatically promoted into canonical evidence. Derived surfaces must preserve their source identity and limitations.

See:

- [Workspace production operations](https://github.com/Aditya671/StateWake/blob/main/docs/operations/workspace-production-operations.md)
- [Workspace backend migration](https://github.com/Aditya671/StateWake/blob/main/docs/operations/workspace-backend-migration.md)
- [Backup and restore](https://github.com/Aditya671/StateWake/blob/main/docs/operations/workspace-backup-restore.md)

---

## Human approval and release publication

StateWake treats approval as evidence with a lifecycle, not as a mutable boolean.

```text
verification evidence
       ↓
human approval
       ↓
active / revoked / superseded lifecycle
       ↓
release publication basis
       ↓
execution permit
       ↓
registry publication
       ↓
registry read-back / reconciliation
       ↓
continuing registry lifecycle
```

Important invariants include:

- historical approvals remain immutable evidence;
- only currently active approval can satisfy a fresh authorization boundary;
- publication authority is bound to exact candidate/distribution digests;
- an uploader reporting success is not equivalent to registry proof;
- registry state may later become yanked, partially available, or unavailable without rewriting historical publication evidence.

See:

- [Human approval lifecycle](https://github.com/Aditya671/StateWake/blob/main/docs/architecture/human-approval-lifecycle.md)
- [Release publication authorization](https://github.com/Aditya671/StateWake/blob/main/docs/architecture/release-publication-authorization.md)
- [Registry publication reconciliation](https://github.com/Aditya671/StateWake/blob/main/docs/architecture/release-registry-publication-reconciliation.md)

---

## Security model

StateWake's security model follows several separation rules:

- **Integrity is not truth.** A digest can prove bytes are unchanged without proving their claim is factually correct.
- **A signature is not authorization.** Cryptographic verification and permission are separate decisions.
- **Authentication is not application approval.** A verified identity does not automatically gain authority for every action.
- **Recovery is not silent success.** Recovery evidence and post-recovery verification remain explicit.
- **Unknown stays unknown.** Missing or failed evidence is not converted into a positive result.
- **Private keys remain external.** Signing providers are referenced through host-managed custody boundaries.

Security policy and reporting information:

- [SECURITY.md](https://github.com/Aditya671/StateWake/blob/main/SECURITY.md)
- [Security documentation](https://github.com/Aditya671/StateWake/tree/main/docs/security)

---

## Repository structure

```text
StateWake/
├── src/statewake/          # Python package
├── tests/                  # behavioral, integration, security, release tests
├── scripts/                # development, testing, security, release tooling
├── examples/               # executable public examples and reference applications
├── docs/                   # user, architecture, security, release documentation
├── ui/                     # optional Next.js inspection/review UI
├── benchmarks/             # bounded benchmark assets
├── data/                   # local runtime-data boundary; generated workspace content is ignored
├── pyproject.toml          # package + tool configuration
├── uv.lock                 # locked Python dependency graph
├── verification_manifest.txt
└── candidate-fingerprint.txt
```

`pyproject.toml` explicitly maps distribution `statewake-ai` to the `src/statewake` import package through the configured `uv_build` backend.

---

## Development

StateWake uses Python `3.11` through `3.13`.

Create/sync the development environment:

```bash
uv sync --all-extras --group dev
```

Common local gates:

```bash
uv run pytest
uv run ruff check src tests scripts examples
uv run ruff format --check src tests scripts examples
uv run mypy
uv build
```

Release-specific verification is intentionally stricter than ordinary development testing. See:

- [SDLC](https://github.com/Aditya671/StateWake/blob/main/docs/SDLC.md)
- [Quality gates](https://github.com/Aditya671/StateWake/blob/main/docs/QUALITY_GATES.md)
- [Definition of Done](https://github.com/Aditya671/StateWake/blob/main/docs/DEFINITION_OF_DONE.md)
- [Contributing](https://github.com/Aditya671/StateWake/blob/main/CONTRIBUTING.md)

---

## Release status and evidence

Release records are versioned under [`docs/releases/`](https://github.com/Aditya671/StateWake/tree/main/docs/releases).

For the v0.5.0 source line:

- package version is `0.5.0`;
- public API contract remains `1`;
- v0.4.1 release records remain historical and are not rewritten;
- verification and publication authorization remain separate gates;
- external public-host qualification remains separate from local native-SDK qualification;
- publication must be proven by registry evidence rather than inferred from an upload command.

See the current [v0.5.0 release notes](https://github.com/Aditya671/StateWake/blob/main/docs/releases/v0.5.0/RELEASE_NOTES.md) and [CHANGELOG](https://github.com/Aditya671/StateWake/blob/main/CHANGELOG.md).

---

## Documentation

- [Documentation index](https://github.com/Aditya671/StateWake/tree/main/docs)
- [User guide](https://github.com/Aditya671/StateWake/tree/main/docs/user-guide)
- [API/reference](https://github.com/Aditya671/StateWake/tree/main/docs/reference)
- [Architecture](https://github.com/Aditya671/StateWake/tree/main/docs/architecture)
- [Integrations](https://github.com/Aditya671/StateWake/tree/main/docs/integrations)
- [Security](https://github.com/Aditya671/StateWake/tree/main/docs/security)
- [Operations](https://github.com/Aditya671/StateWake/tree/main/docs/operations)
- [Testing](https://github.com/Aditya671/StateWake/tree/main/docs/testing)
- [Governance](https://github.com/Aditya671/StateWake/tree/main/docs/governance)
- [Release history](https://github.com/Aditya671/StateWake/tree/main/docs/releases)
- [v0.5.0 technical white paper (Markdown)](https://github.com/Aditya671/StateWake/blob/main/docs/whitepaper/StateWake_Technical_White_Paper_v0.5.0.md)
- [v0.5.0 technical white paper (PDF)](https://github.com/Aditya671/StateWake/blob/main/docs/whitepaper/StateWake_Technical_White_Paper_v0.5.0.pdf)

---

## Support and project links

- [GitHub repository](https://github.com/Aditya671/StateWake)
- [PyPI package](https://pypi.org/project/statewake-ai/)
- [Issue tracker](https://github.com/Aditya671/StateWake/issues)
- [Security advisories](https://github.com/Aditya671/StateWake/security/advisories/new)
- [Changelog](https://github.com/Aditya671/StateWake/blob/main/CHANGELOG.md)
- [Code of Conduct](https://github.com/Aditya671/StateWake/blob/main/CODE_OF_CONDUCT.md)
- [Third-party notices](https://github.com/Aditya671/StateWake/blob/main/THIRD_PARTY_NOTICES.md)

---

## License

StateWake is released under the [Apache License 2.0](https://github.com/Aditya671/StateWake/blob/main/LICENSE).
