# Getting Started

## Install

```bash
python -m pip install statewake-ai
```

The distribution is named `statewake-ai`; the Python package is imported as `statewake`.

## Verify the installation

```bash
python -c "import statewake; print(statewake.__version__)"
statewake version
```

## Local SQLite state storage

The reference SQLite adapter creates its database and schema automatically on first use.
Validation and corruption harnesses create disposable SQLite databases in temporary
locations so destructive probes never become repository data.

## Choose an integration boundary

Use the Python API when StateWake is embedded directly in an application. Use `statewake.server:app` when an existing WSGI service needs an HTTP verification boundary.

## Recommended integration sequence

1. Keep the source system's authoritative run/evidence artifacts in its existing storage.
2. Produce an evidence receipt for the artifact.
3. Admit the evidence through StateWake's evidence boundary.
4. Build the reliability evidence chain from authoritative references.
5. Verify the chain before using it for reliability-state decisions.
6. Record state transitions and reconciliation/recovery evidence.
7. Create an attestation when an independently consumable reliability claim is required.

## Next steps

Read [Python integration](python-integration.md) for application embedding or [HTTP API](http-api.md) for a service boundary.


## Five-minute first evidence chain

Use the local release example to walk through the complete evidence path:

```text
artifact → receipt → admission → evidence chain → verify → state decision
```

The example should be run from the repository checkout and should deliberately modify the artifact after admission. Verification must reject the tampered artifact. The important boundary is that verification proves the defined evidence invariants; it does not prove that an external model or system is universally correct.

For the complete executable walkthrough, see [First evidence chain](first-evidence-chain.md).
