# Golden Application B — Enterprise AI Reliability

## Architecture

```text
synthetic user request
        |
        v
 agent / RAG producer
        |
        +--> retrieval reference
        +--> tool references
        +--> model/prompt references
        +--> output/evaluator references
        |
        v
 AgentEvidenceAdapter
        |
        v
 canonical evidence lifecycle
```

## Evidence model

The synthetic agent producer records references for model, prompt, retrieval, tools, output, and evaluator artifacts. `AgentEvidenceAdapter` captures those references without requiring sensitive payloads.

## State transition

`unknown -> reliable` with an `accept` decision for the canonical enterprise-RAG scenario. The evidence graph binds the execution references to the reliability claim before outcome and proof verification.

## Failure catalog

1. Retrieval-version changes are represented as behavioral evidence rather than silently treated as equivalent.
2. The full scenario deliberately tampers with evidence after proof creation; verification rejects the tampered artifact.
3. The example demonstrates that a model output is not self-authenticating: the claim depends on inspectable evidence references.

## Expected output

The command prints JSON with `chain_verified`, `outcome_verified`, `proof_bundle_verified`, and `tamper_rejected` all set to `true`.

## Security notes

The adapter stores references rather than sensitive prompts, retrieved documents, or model payloads. The example uses no credentials and no external model or retrieval service.

## Limitations

StateWake does not prove universal LLM correctness, truthfulness, safety, or quality. This reference application demonstrates evidence-backed reliability claims and lifecycle consistency.

## Run and test

```bash
PYTHONPATH=src:. python docs/examples/golden/enterprise_ai_reliability.py
pytest -q tests/integration/golden/test_golden_applications.py -p no:ddtrace -p no:anyio -p no:pytest_asyncio
```
