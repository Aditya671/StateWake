# Integration Patterns

StateWake is designed to fit around existing AI systems.

## Embedded library

Use the `statewake` Python package when the host application already controls execution and artifact storage.

```text
Application → StateWake public API → local/existing evidence stores
```

## Service boundary

Use `statewake.server:app` when a trusted service needs an HTTP verification boundary.

```text
Application → HTTP/WSGI → StateWake verification services → evidence artifacts
```

## Evidence producer pattern

Evaluation, telemetry, testing, replay, or runtime components can remain independent producers:

```text
Producer → evidence artifact + receipt → StateWake → verification/state/attestation
```

## Avoiding tight coupling

Do not make StateWake the execution authority for the host AI system. Keep execution, model selection, orchestration, and telemetry in their existing systems and send the authoritative evidence required for the reliability claim into StateWake.
