# Python Integration

The frozen public Python contract is documented in [`docs/reference/API_CONTRACT.md`](../reference/API_CONTRACT.md). The machine-readable export manifest is [`docs/reference/api-contract.json`](../reference/api-contract.json).

StateWake exposes a small stable public API through the `statewake` package, including a framework-neutral integration SDK.

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

## Integration rule

Consumers should import supported functions and domain types from `statewake` where available. Internal modules under `statewake.domain`, `statewake.services`, and `statewake.adapters` are implementation details unless explicitly documented as integration surfaces.

## Why this boundary matters

An application can integrate StateWake without adopting StateWake's storage implementation, HTTP layer, CLI, or framework choices. The application remains the authority over its own execution and source artifacts.

## Dependency model

StateWake is dependency-light and framework-neutral, but its released runtime declares `PyNaCl` and `opentelemetry-api` as dependencies.

## Embedding example

```python
from pathlib import Path
from statewake import load_evidence_chain, verify_evidence_chain

chain = load_evidence_chain(Path("./evidence/chain.json"))
verify_evidence_chain(chain, root=Path("./evidence"))
```

For long-lived applications, prefer the stable top-level functions and pin StateWake according to the compatibility policy in `docs/governance/VERSIONING.md`.

## Integration SDK

For applications that need a configured evidence boundary, use `StateWakeClient` and `IntegrationContext` from the top-level package. The SDK also provides `WebhookEvidenceAdapter`, `QueueEvidenceAdapter`, `DatabaseEvidenceAdapter`, `BatchEvidenceAdapter`, and `AgentEvidenceAdapter`. See `docs/reference/SDK_INTEGRATION.md` for the complete integration contract.
