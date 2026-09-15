# What is StateWake?

StateWake is a framework-neutral reliability layer for AI systems.

Its job is not to run an AI agent. Its job is to help a system establish evidence that can answer:

- What happened?
- What produced the behavior?
- Which evidence supports that conclusion?
- Has the evidence itself been verified?
- What reliability state did the system reach?
- If reality diverged from expectation, what was reconciled or recovered?
- Can another component independently verify the resulting claim?

## What StateWake provides

StateWake composes authoritative evidence from integrated systems into a verifiable lifecycle of:

**evidence → provenance → integrity → state → reconciliation/recovery → attestation → decision**

## What StateWake does not provide

StateWake does not require a particular agent runtime, model provider, vector database, observability platform, evaluation framework, or orchestration system. Those systems can continue to operate independently and provide evidence into StateWake.

StateWake also does not claim that a reliability score alone proves correctness. Reliability claims are tied to inspectable evidence and verification results.

## Who should integrate StateWake?

StateWake is useful when an AI application needs durable, reviewable reliability evidence across development, production incidents, operational recovery, or compliance-oriented workflows.
