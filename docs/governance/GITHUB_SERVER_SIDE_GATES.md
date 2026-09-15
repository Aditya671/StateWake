# GitHub Server-Side Release Gates

These controls are intentionally repository-hosting settings. They are not represented by a source file and GitHub's web UI does not provide an "upload settings file" operation for them.

Repository: `Aditya671/StateWake`
Default branch: `main`

## Gate 1 — Protect `main`

Open the repository on GitHub, then:

`Settings` → `Branches` → `Branch protection rules` → `Add classic branch protection rule`

Use branch pattern:

```text
main
```

Enable at minimum:

- **Require a pull request before merging**
- **Require approvals**: 1 approval is the recommended minimum for this repository
- **Dismiss stale pull request approvals when new commits are pushed**
- **Require status checks to pass before merging**
- Select the release CI checks that must pass. The important repository gate is the CI workflow's status check(s), not a hard-coded job name in documentation.
- **Include administrators / enforce branch protection for administrators**
- **Restrict force pushes** / do not allow force pushes
- **Restrict deletions** / do not allow branch deletion

Recommended additional controls:

- Require conversation resolution before merging
- Require branches to be up to date before merging
- Require signed commits only if the maintainer workflow is ready to enforce them consistently

GitHub documents branch protection as the mechanism for requiring reviews and status checks and for preventing deletion/force-push behavior on protected branches.

## Gate 2 — Protect release tags

Use a repository ruleset for release tags:

`Settings` → `Rules` → `Rulesets` → `New ruleset` → `New branch or tag ruleset`

Recommended configuration:

**Name**

```text
Protect release tags
```

**Enforcement status**

```text
Active
```

**Target refs / tag pattern**

```text
v*
```

Enable rules that prevent ordinary users from creating, updating, or deleting matching release tags. The exact control labels can vary with the GitHub ruleset UI; the outcome must be that `v*` release tags are protected from unintended mutation.

## Gate 3 — Enable private vulnerability reporting

Open:

`Settings` → `Security and quality` → `Advanced Security`

Under **Private vulnerability reporting**, click **Enable**.

After enabling it, open the repository's **Security and quality** tab and verify that the private vulnerability reporting flow exposes **Report a vulnerability** on the Advisories page.

`SECURITY.md` is still useful policy documentation, but GitHub explicitly treats private vulnerability reporting as a separate repository feature; the feature itself must be enabled for the private reporting route to exist.

## Local verification after changing GitHub settings

From the repository checkout, use a GitHub token with permission to read the required repository administration/security settings:

```bash
STATEWAKE_GOVERNANCE_TOKEN=... python scripts/release/verify_repository_governance.py
```

The verifier is read-only and fails closed if it cannot verify a required control.

## Important distinction

Uploading `SECURITY.md`, workflow files, or a JSON configuration file does **not** turn on these GitHub server-side settings automatically.

The source repository contains the policy and verification artifacts; the actual protections must be enabled in GitHub's repository settings (or through GitHub's administration API/CLI by an authorized maintainer).
