# Canonical Release Publication Authorization & Execution Boundary

StateWake keeps **release verification**, **human publication authorization**, and **registry publication** as three different statements.

## Authority chain

```text
verified release candidate + exact distributions
    -> ReleasePublicationBasis
    -> canonical HumanApprovalContract lifecycle
       (active / revoked / superseded)
    -> fresh PublicationExecutionPermit
    -> protected external publisher (GitHub Environment + PyPI Trusted Publishing)
    -> official registry metadata + public artifact read-back
    -> canonical RegistryPublicationReceipt
```

`ReleasePublicationBasis` binds the decision to the package/version, target registry (`testpypi` or `pypi`), source revision and source-tree digest, verification-evidence digest, and every distribution filename/size/SHA-256. The basis is immutable and has its own canonical digest.

Publication approval reuses `WorkspaceHumanApprovalStore`; there is no second approval database or mutable release flag. An approval is effective only while its lifecycle projection is `active` and its producer/action/scope/basis metadata match the exact publication basis. Revocation and supersession append evidence and preserve history.

`issue_publication_execution_permit()` is the final StateWake-side gate. It re-reads the exact distribution directory, rejects extra/missing/changed files, optionally re-checks the verification-evidence digest, resolves the current approval lifecycle, and emits a point-in-time permit. A permit records `publication_authorized: true` but deliberately records `release_published: false` because registry acceptance has not happened yet.

## External execution boundary

`.github/workflows/release-verification.yml` is the only release-distribution builder. It builds the exact wheel/source distribution once, verifies those immutable bytes across supported consumers/integrations, and retains the distributions plus release evidence as GitHub Actions artifacts. `.github/workflows/python-publish.yml` resolves a **successful Release Verification run for the exact source revision** before publication: manual TestPyPI uses an explicit run ID, while a production release polls the matching verification run with a bounded timeout so release-event ordering cannot race verification completion. A non-OIDC preparation job downloads the exact artifacts, rechecks their SHA-256 file set and source identity, freezes the target-specific canonical basis, records event-scoped authorization, issues a fresh permit, and uploads one immutable publication-ready bundle. The protected `testpypi` or `pypi` job has only two responsibilities: download that prepared bundle and invoke Trusted Publishing/OIDC. It never builds, tests, authorizes source, or mutates the publication basis. StateWake does not store a long-lived registry token.

Repository operators must configure the GitHub environments and their required-reviewer rules independently. StateWake records the GitHub event actor/source run available to the job; it does not claim to capture the identity of an environment reviewer unless GitHub supplies that identity as canonical input.

## Post-publication reconciliation

A successful external publisher step remains insufficient by itself. A separate post-publication job reads the official PyPI/TestPyPI release API and the public distribution bytes, verifies the exact authorized artifact set, and emits a digest-bound `RegistryPublicationReceipt` tied to both this basis and the exact execution permit. See `release-registry-publication-reconciliation.md`.

## UI boundary

The operational trust center can display the configured publication basis, active/revoked/superseded approval lifecycle, and an independently verified registry receipt. The UI is read-only: it cannot create publication approval, issue a permit, publish a distribution, or create registry evidence.

## Non-claims

The publication permit does not prove registry acceptance. A valid registry receipt proves only the observed registry state and public bytes at its recorded time; it does not guarantee future availability, continued unyanked status, or the correctness of external registry administration.
