
> **Package status:** StateWake is classified as `Development Status :: 5 - Production/Stable`.

# StateWake

> **Evidence-backed reliability infrastructure for AI systems.**

StateWake helps AI systems establish a verifiable record of what happened, what produced it, whether the supporting evidence is trustworthy, what state the system reached, and whether that state was verified or recovered.

It is designed to integrate with existing AI runtimes, evaluation systems, telemetry, CI/CD, storage, and operational tooling. It does not replace them.

**Project:** [GitHub repository](https://github.com/Aditya671/StateWake)  
**Version:** `v0.4.0`  
**License:** Apache-2.0

StateWake v0.4.0 supports Python `>=3.11,<3.14`. Python 3.14 is intentionally outside the supported release compatibility matrix; use a supported interpreter and avoid forced wheel installation on Python 3.14.

## Why StateWake

AI applications increasingly depend on multiple runtimes, tools, models, retrieval systems, policies, and external services. Logs and evaluation scores can show that something happened, but they do not by themselves establish a durable, independently verifiable reliability record.

StateWake makes the reliability evidence lifecycle explicit:

```text
AI-system execution
       ↓
Captured evidence
       ↓
Evidence admission + provenance
       ↓
Integrity verification
       ↓
State / behavioral comparison
       ↓
Verified reliability state
       ↓
Reconciliation / recovery evidence
       ↓
Attestation
       ↓
Evidence-backed decision
```

The central product primitive is the `ReliabilityEvidenceChain`: a verifiable composition of authoritative evidence references rather than a second copy of the source system's data.

## What StateWake provides

- Evidence admission and provenance boundaries
- Integrity verification and evidence-chain construction
- Reliability state and state-transition management
- Behavioral comparison and outcome verification
- Reconciliation and recovery evidence
- Attestation and reliability decision-basis support
- Framework-neutral Python integration APIs
- CLI and WSGI integration surfaces
- Adapters for common evidence sources, including agent runs, CI/CD artifacts, evaluation output, files, incidents, and OpenTelemetry traces

## Product boundary

StateWake is **not** a generic agent-testing platform, chaos platform, observability dashboard, agent orchestration framework, distributed task queue, or hosted control plane.

Testing, replay, regression, contracts, assertions, telemetry, and external evaluations can remain valuable producers of evidence. StateWake's V1 role is to establish trustworthy reliability evidence and system-state management around those inputs.

## Installation

The package published to PyPI/TestPyPI is `statewake-ai`; the Python import package is `statewake`.

```bash
python -m pip install statewake-ai
```

The workspace dataset/export adapters and native framework integrations are included in the package's required runtime dependencies; no workspace extra is needed.

CSV, JSON, portable-bundle, and SQLite reference persistence use Python/SQLite standard-library capabilities and do not require additional packages.

For the previously published v0.1.1 package, use:

```bash
python -m pip install statewake-ai==0.1.1
```

Release history and version-specific verification records are maintained under `docs/releases/`; see those records for historical gate outcomes.

See `pyproject.toml` for the authoritative dependency declarations and `uv.lock` for the exact locked dependency state.

## Python integration

StateWake exposes its stabilized consumer API from the top-level `statewake` package. Consumers should prefer these public imports over internal implementation modules.

```python
from pathlib import Path

from statewake import (
    admit_evidence,
    build_evidence_chain,
    read_reliability_state,
    verify_evidence_chain,
    verify_outcome,
)
```

A minimal persisted-chain verification flow is:

```python
from pathlib import Path

from statewake import load_evidence_chain, verify_evidence_chain

chain = load_evidence_chain(Path("./evidence/chain.json"))
verify_evidence_chain(chain, root=Path("./evidence"))
```

The public API contract and SDK integration documentation are maintained in the repository:

- [API contract](https://github.com/Aditya671/StateWake/blob/main/docs/reference/API_CONTRACT.md)
- [Python integration](https://github.com/Aditya671/StateWake/blob/main/docs/user-guide/python-integration.md)
- [SDK integration](https://github.com/Aditya671/StateWake/blob/main/docs/reference/SDK_INTEGRATION.md)

## CLI

The package provides the `statewake` command-line interface.

```bash
statewake version
statewake --help
```

The CLI exposes evidence ingestion and verification, evidence-chain construction, reliability-state operations, attestation, recovery verification, reconciliation, proof-bundle, decision-basis, and release-proof workflows.

## HTTP integration

StateWake's core has no HTTP-framework dependency. A small WSGI adapter is available when an application wants an HTTP boundary without making FastAPI or Flask a core dependency.

The supported WSGI application object is:

```text
statewake.server:app
```

Production deployments remain responsible for authentication, authorization, TLS, request limits, filesystem isolation, and network policy.

## Documentation

The canonical documentation lives in the GitHub repository:

- **User guide:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/user-guide)
- **API reference:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/reference)
- **Architecture:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/architecture)
- **Specifications:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/specifications)
- **Integrations:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/integrations)
- **Security:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/security)
- **Operations:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/operations)
- **Testing:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/testing)
- **Governance:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/governance)
- **Development:** [GitHub](https://github.com/Aditya671/StateWake/tree/main/docs/development)

Project-level documents:

- **Changelog:** [CHANGELOG.md](https://github.com/Aditya671/StateWake/blob/main/CHANGELOG.md)
- **Contributing:** [CONTRIBUTING.md](https://github.com/Aditya671/StateWake/blob/main/CONTRIBUTING.md)
- **Security policy:** [SECURITY.md](https://github.com/Aditya671/StateWake/blob/main/SECURITY.md)
- **Code of Conduct:** [CODE_OF_CONDUCT.md](https://github.com/Aditya671/StateWake/blob/main/CODE_OF_CONDUCT.md)
- **Third-party notices:** [THIRD_PARTY_NOTICES.md](https://github.com/Aditya671/StateWake/blob/main/THIRD_PARTY_NOTICES.md)

## Source and support

- **Source repository:** [GitHub](https://github.com/Aditya671/StateWake)
- **Issues:** [GitHub Issues](https://github.com/Aditya671/StateWake/issues)
- **Security reports:** [GitHub Security Advisories](https://github.com/Aditya671/StateWake/security/advisories/new)

## Versioning

The current public package baseline is **v0.4.0**. Historical implementation identifiers are retained only as development provenance.

See the project's versioning policy in the repository documentation:

[VERSIONING.md](https://github.com/Aditya671/StateWake/blob/main/docs/governance/VERSIONING.md)

## License

StateWake is released under the Apache License 2.0.

[LICENSE](https://github.com/Aditya671/StateWake/blob/main/LICENSE)
