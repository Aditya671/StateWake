# Governance CI Credential

`verify_repository_governance.py` reads GitHub repository governance APIs that require repository-administration read access. The ordinary Actions `GITHUB_TOKEN` is not sufficient for these administration endpoints.

## Required GitHub Actions secret

Create a repository secret named:

```text
STATEWAKE_GOVERNANCE_TOKEN
```

The secret must contain a fine-grained GitHub token with the minimum **Administration: read** access required by the governance endpoints inspected by the verifier. Keep the token read-only and scoped only to `Aditya671/StateWake`.

The Release Verification workflow injects this secret only into its dedicated read-only `repository-governance` job. That job also exposes its ordinary `GITHUB_TOKEN` as a least-privilege fallback; the verifier prefers `STATEWAKE_GOVERNANCE_TOKEN`, and the fallback succeeds only when GitHub grants the ordinary token enough read access to every inspected governance endpoint. If it cannot read an endpoint, verification fails closed rather than skipping the check. Neither token is exposed to source quality, tests, package consumers, provenance, or publication commands.

For local/manual verification, `STATEWAKE_GOVERNANCE_TOKEN` is preferred; `GITHUB_TOKEN` remains accepted as a compatibility fallback.

The verifier is read-only and does not modify GitHub repository governance.
