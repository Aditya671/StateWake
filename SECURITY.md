# Security Policy

## Scope

StateWake provides reliability-evidence integrity mechanisms: evidence admission and binding, provenance validation, state-transition integrity, signed attestations, portable proof verification, and optional independent trust checkpoints.

StateWake does not automatically provide host hardening, caller authentication, tenant isolation, TLS termination, immutable storage, business-policy correctness, or protection against stolen signing keys. Those are deployment or application responsibilities documented in `docs/security/THREAT_MODEL.md`.

## Reporting a vulnerability

Do not disclose a security vulnerability in a public issue. StateWake uses GitHub private vulnerability reporting for coordinated disclosure when that repository feature is enabled. If private reporting is unavailable, contact the project maintainers through the repository's established private security channel rather than posting exploit details publicly.

## Security design

The current security architecture and executable control mapping are maintained in:

- `docs/security/THREAT_MODEL.md`
- `docs/security/CONTROL_TEST_MATRIX.md`
- `docs/security/INCIDENT_RECOVERY.md`
- `docs/adr/0004-security-architecture.md`
