# Real-World StateWake Examples

These examples model systems that commonly need evidence-backed reliability decisions. The producer systems are synthetic and credential-free; the StateWake lifecycle is real and executable.

## Executed global scenario matrix

| Domain | Scenario | Outcome exercised |
|---|---|---|
| Payments | Payment gateway authorization | reliable / accept |
| Government | Municipal 311 prioritization | degraded / review |
| Enterprise AI | RAG assistant answer | reliable / accept |
| Decisioning | Credit / eligibility | unreliable / reject |
| Supply chain | ETA exception and recovery | recovered / accept |
| Documents | Invoice automation | reliable / accept |
| Healthcare | Hospital triage routing | reliable / accept |
| Insurance | Claims adjudication | unreliable / reject |
| Financial crime | Fraud / AML screening | unreliable / reject |
| Identity | Access authorization | reliable / accept |
| Utilities | Electric outage restoration | recovered / accept |
| Telecom | Network assurance | unreliable / reject |
| Industrial | Control anomaly | degraded / review |
| E-commerce | Fulfillment decision | reliable / accept |
| Legal / compliance | Policy compliance check | degraded / review |
| Payroll / tax | Payroll withholding | reliable / accept |
| Autonomous systems | Fleet route decision | unreliable / reject |
| Disaster response | Emergency alert / restoration | recovered / accept |

Every executed scenario covers evidence ingestion, provenance, integrity verification, reliability state transition, attestation/outcome verification, portable proof generation, portable proof verification, and deliberate evidence tampering.

## Why the examples are domain-neutral

StateWake is not the payment gateway, case-management system, RAG engine, rules engine, claims platform, or fleet controller. Those systems remain the sources of operational evidence. StateWake establishes a verifiable chain around their evidence and the resulting reliability state.

The same pattern therefore applies across jurisdictions, vendors, and architectures without requiring StateWake to become the host application's business logic.

## Run

```bash
python scripts/testing/run_real_world_scenarios.py
```

The command returns a machine-readable result and fails non-zero when any scenario fails.

## External implementation references

The producer patterns used to shape the examples were cross-checked against public GitHub projects such as Stripe payment samples, LlamaIndex / agentic-RAG examples, and public business-rule/decision-engine projects. These repositories are references for integration shape, not runtime dependencies of StateWake.

## Golden reference applications

The three polished StateWake reference applications are in `docs/examples/golden/`:

- `payment_reliability.py`
- `enterprise_ai_reliability.py`
- `municipal_decision_reliability.py`

They build on the validated scenario matrix while exercising the public integration SDK directly.
