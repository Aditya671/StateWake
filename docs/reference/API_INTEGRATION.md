# API and Integration Guide

The authoritative frozen Python contract is [`docs/reference/API_CONTRACT.md`](API_CONTRACT.md), with its machine-readable export manifest at [`docs/reference/api-contract.json`](api-contract.json).

## Python package

The supported integration surface is the top-level package:

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

Consumers should not depend on `services.*` or `adapters.*` imports unless they are intentionally extending an internal implementation boundary.

## HTTP / WSGI

The standard-library WSGI application is exposed as:

```text
statewake.server:app
```

Local development can use:

```bash
python -m statewake.server
```

Endpoints:

- `GET /health`
- `GET /v1/version`
- `POST /v1/evidence/verify` with `{ "chain_path": "...", "evidence_root": "..." }`
- `POST /v1/proof/verify` with `{ "bundle_path": "..." }`

The HTTP adapter delegates to the same verification authorities used by the Python API and CLI. It does not create a second reliability implementation.

### Deployment security boundary

The verification endpoints consume local filesystem paths but now require configured artifact roots, resolved-path containment, request-size limits, read-only behavior, and HTTPS by default. Treat the adapter as a **trusted local/internal integration boundary**, not an internet-facing multi-tenant API. A production gateway must provide authentication, authorization, TLS termination as appropriate, tenant isolation, rate limiting, logging, and network controls.

Flask, Gunicorn, mod_wsgi, or another WSGI-compatible host can embed `statewake.server:app`; the core package itself has no HTTP-framework dependency.
