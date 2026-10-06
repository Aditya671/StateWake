# StateWake Examples

This directory contains executable, credential-free examples built against the public StateWake package surface.

- `first-evidence-chain.py` — minimal artifact → receipt → evidence-chain → verification → tamper-rejection walkthrough.
- `golden/` — polished reference applications exercised by the product-experience release gate.
- `real-world/` — scenario-oriented guidance that explains how the examples map to bounded reliability workflows.

Examples are development/release inputs, not production package modules. They may import `statewake` from `src/` when run from a source checkout, but production code must never import from `examples`.
