# StateWake Limitations

This page is part of the public product experience. It states the boundaries of what the current v0.3.0 baseline establishes and what remains the responsibility of an integrating system.

## Verification does not prove truth

StateWake verifies declared evidence identity, integrity, binding, completeness, and reliability-state contracts. It does not prove that an AI model is universally truthful, safe, unbiased, or semantically correct.

## Producer systems remain authoritative

StateWake does not replace the source system that produced an event, model output, retrieval result, transaction, policy decision, or operational record. A StateWake chain references authoritative evidence rather than becoming a second business-system database.

## Local history has a trust boundary

A retained local evidence history can detect mutations of retained records. It cannot, by itself, prove that a privileged attacker did not delete an entire valid trailing history segment. Independent trust anchors or equivalent external controls are required for that stronger property.

## Deployment security is host-owned

Authentication, authorization, TLS termination, secret and signing-key storage, filesystem permissions, path isolation, rate limiting, tenant isolation, network exposure, and host security remain deployment responsibilities.

## HTTP boundary

The WSGI adapter is a trusted integration boundary. It must not be exposed directly to an untrusted network without an application security layer and appropriate request/path controls.

## External integrations

External integration support is evidence-oriented. Successful capture and verification establish only the declared StateWake contract for the captured evidence; they do not establish correctness of the external provider itself.

## Synthetic reference applications

The golden and cross-domain applications use synthetic data. They demonstrate integration and verification semantics rather than production authorization, policy, settlement, medical, aviation, municipal, or other domain-specific correctness.

## Performance

Performance measurements in the release evidence are local engineering measurements, not service-level objectives. Results depend on Python version, hardware, storage, concurrency, payload size, and deployment topology.

## Native development tools

The canonical source policy expects Ruff and mypy verification. A release evidence record must state when those tools were unavailable in the validation environment rather than converting a substitute check into an equivalent claim.
