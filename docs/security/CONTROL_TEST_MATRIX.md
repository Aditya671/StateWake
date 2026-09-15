# Security Control → Executable Test Matrix

This matrix is the executable security-control index. Test references are repository-relative pytest/unittest node identifiers or test modules. The matrix is intentionally narrow: it maps controls that already exist in code to executable evidence rather than inventing security controls that are not implemented.

| Control | Threats | Executable evidence |
|---|---|---|
| Content-addressed evidence + receipt cross-check | T01 | `tests/test_external_evidence_ingestion.py` |
| Producer/source identity conflict detection | T02 | `tests/test_external_evidence_ingestion.py` |
| Deterministic duplicate ingestion | T03 | `tests/test_external_evidence_ingestion.py` |
| Valid state-transition enforcement | T04 | `tests/test_reliability_state.py` |
| Provenance validation | T05 | `tests/unit/test_provenance.py` |
| Portable proof integrity checks | T06 | `tests/test_reliability_proof_bundle.py` |
| ZIP member/path safety | T07 | `tests/test_hardening_archives.py` |
| Durable/locked persistent stores | T08 | `tests/test_hardening_boundaries.py` |
| Ed25519 signed attestation verification | T09 | `tests/test_reliability_proof_bundle.py`, `tests/unit/test_reliability_attestation.py` |
| Independent checkpoint verification | T10 | `tests/test_trust_anchor.py` |
| HTTPS/request/path boundaries | T11 | `tests/test_http_api.py` |
| Deterministic privacy redaction | T12 | `tests/unit/test_privacy.py` |
| External signing boundary | T13 | `tests/test_key_management.py` |
| Explicit HTTP request-size limit | T14 | `tests/test_http_api.py` |
| Release/dependency governance checks | T15 | `tests/test_release_governance.py` |

## Coverage interpretation

A mapped test demonstrates the corresponding control behavior. It does not demonstrate complete operational security for the deployment. Controls requiring external infrastructure—KMS/HSM policy, TLS termination, authentication, repository settings, immutable object storage, rate limiting, host isolation—must be verified by the deployment owner.
