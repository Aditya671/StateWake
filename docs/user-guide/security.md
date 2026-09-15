# Security

StateWake is designed to make reliability evidence verifiable, not to replace application security infrastructure.

## Core security properties

- deterministic integrity checks;
- content and receipt identity binding;
- provenance and lineage binding;
- explicit state-transition history;
- portable proof verification;
- optional signed attestation/trust mechanisms.

## Deployment responsibilities

Applications embedding StateWake remain responsible for:

- authentication and authorization;
- TLS and certificate management;
- secret/key storage;
- filesystem permissions and path isolation;
- request-size and rate limits;
- network exposure controls;
- tenant isolation where applicable;
- operational logging and alerting.

## HTTP warning

Never expose the WSGI adapter to an untrusted network without an application security layer. Its verification endpoints accept local paths and are intended for a trusted integration boundary.

Security vulnerabilities should be reported according to `SECURITY.md` rather than through public issue discussion.


## Verification boundary

| Detects | Does not establish |
| --- | --- |
| altered artifacts | model truth or semantic correctness |
| broken evidence bindings | security of an exposed WSGI host |
| incomplete proof material | protection of secrets embedded in source artifacts |

A successful StateWake verification means the supplied evidence satisfies StateWake's defined integrity, binding, and completeness invariants. It does not mean that every external system or model is correct.
