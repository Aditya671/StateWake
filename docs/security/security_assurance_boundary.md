# StateWake Tier 4 — Security Assurance Evidence

**Status:** development assurance artifact; not a release approval.

## Scope

This artifact records the Tier 4 assurance boundary for the current StateWake
candidate. It verifies that the canonical security model, executable control
matrix, recovery guidance, security architecture decision, and security-sensitive
regression tests remain mutually traceable.

## Security assurance questions

| Question | Evidence boundary |
|---|---|
| Security-critical assets | `docs/security/THREAT_MODEL.md` |
| Trust boundaries | `docs/security/THREAT_MODEL.md` |
| Security invariants and controls | `docs/security/THREAT_MODEL.md`, `docs/security/CONTROL_TEST_MATRIX.md` |
| Executable control evidence | `tests/` references in the threat model and control matrix |
| Cryptographic boundary | `docs/security/THREAT_MODEL.md`, `docs/adr/0004-security-architecture.md`, key-management tests |
| State-transition security | reliability-state tests and threat-model T04 |
| Recovery semantics | `docs/security/INCIDENT_RECOVERY.md` |
| Privacy leakage boundary | privacy tests and threat-model T12 |
| Portable proof/archive boundary | proof-bundle and archive tests, T06/T07 |
| Authorization boundary | deployment-security tests and threat-model T11 |

## Deterministic assurance check

The repository includes `scripts/security/verify_security_assurance_boundary.py`. It checks:

1. all canonical threat-model sections exist;
2. threats T01–T15 are represented exactly once in the threat matrix;
3. every executable evidence reference resolves to an existing test/module and,
   where a node is specified, to a matching source symbol;
4. the control matrix references existing test modules;
5. incident-recovery evidence preserves authoritative-source, revocation,
   rotation, independent-checkpoint, and non-invention semantics; and
6. the accepted security ADR retains the bounded cryptographic and architecture
   claims it is intended to govern.

This verifier is an evidence-consistency check. It is not a substitute for an
independent human security review, penetration test, KMS/HSM assessment, or
host/deployment assessment.

## Residual risk

The existing threat model remains authoritative for residual risks, including
compromised hosts/runtimes, stolen signing keys, privileged storage attackers,
unprotected deployment infrastructure, malicious dependencies, and semantically
incorrect but structurally valid producer decisions.

Tier 4 does not turn these residual risks into passes. Unknown, unverified, or
deployment-dependent properties remain explicitly outside the StateWake core
claim.

## Development status

This artifact supports the Tier 4 development assurance gate only. It does not
change the package version, create a release, publish an artifact, or authorize
production deployment.
