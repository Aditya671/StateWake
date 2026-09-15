# Governance CI Credential

`verify_repository_governance.py` reads GitHub repository governance APIs that require repository-administration read access. The ordinary Actions `GITHUB_TOKEN` is not sufficient for these administration endpoints.

## Required GitHub Actions secret

Create a repository secret named:

```text
STATEWAKE_GOVERNANCE_TOKEN
```

The secret must contain a fine-grained GitHub token with the minimum **Administration: read** access required by the governance endpoints inspected by the verifier. Keep the token read-only and scoped only to `Aditya671/StateWake`.

The publication workflow injects this secret only into the governance-verification step. It is not exposed to build, test, or publish commands.

For local/manual verification, `STATEWAKE_GOVERNANCE_TOKEN` is preferred; `GITHUB_TOKEN` remains accepted as a compatibility fallback.

The verifier is read-only and does not modify GitHub repository governance.
