# Repository Governance Gate

This document defines the final GitHub-side controls required before the next public package publication. It is deliberately separate from the application implementation and is verified by `scripts/release/verify_repository_governance.py`.

## Required controls

### Protected `main`

`main` must require pull-request review and the release CI checks. Administrator bypass must be disabled for the required protections.

### Protected release tags

Release tags must be covered by an active GitHub ruleset so a release tag cannot be created or modified outside the intended release process.

### Private vulnerability reporting

GitHub private vulnerability reporting must be enabled for `Aditya671/StateWake`. The repository's `SECURITY.md` points reporters to the private reporting flow; the feature must actually be enabled for that route to be real.

## Verification

Run with a GitHub token that has permission to read repository administration/security settings:

```text
STATEWAKE_GOVERNANCE_TOKEN=... python scripts/release/verify_repository_governance.py
```

The script is **read-only**. It intentionally fails when a required repository control cannot be verified; it never substitutes a source-level approximation for a GitHub repository setting.

## Owner action required when verification fails

In the repository settings:

1. Configure branch protection for `main` with required PR review and required CI checks.
2. Configure an active tag ruleset covering release tags (for example, `v*`).
3. Enable **Private vulnerability reporting** under the repository's security settings.
4. Re-run the verification script before the next publication.

These are repository-hosting controls and cannot be truthfully implemented by changing Python source or documentation alone.
