# Five-minute first evidence chain

The goal of this tutorial is to make the core promise executable:

```text
artifact → receipt → admission/binding → evidence chain → verify → tamper rejection
```

Run:

```bash
python docs/examples/first-evidence-chain.py
```

The example creates one small local JSON artifact, creates a producer receipt, persists a chain through the public loader, verifies the chain, then changes the source artifact. The final verification must reject the tampered bytes.

## What verification means

A successful verification proves the declared evidence identity, integrity, and binding invariants. It does **not** prove that a model's output is universally true, that a producer was honest, or that a public HTTP deployment is secure.
