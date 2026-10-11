# StateWake Quality Gates

## Gate model

| Gate | Required outcome | Evidence |
| --- | --- | --- |
| Repository hygiene | no generated/transient artifacts in the release tree | repository verification |
| Formatting/lint | Ruff check and format check pass | CI logs |
| Typing | mypy strict pass | CI logs |
| Compilation | all active Python source compiles | compileall |
| Unit/contract | complete applicable pytest/unittest suites pass | test report |
| Public surface | imports, CLI, HTTP contracts remain valid | contract tests |
| Product experience | required docs and executable examples pass | product verifier |
| Persistence | initialization, durability, recovery, and cleanup pass | persistence tests |
| Adversarial | failure lab, chaos, extreme, deep, property tests pass | validation reports |
| Integrations | fixture mode passes; live mode is explicitly qualified | integration report |
| Packaging | wheel and source distribution boundaries are valid | package verifier |
| Clean consumer | supported Python versions and OS matrix install and import the built artifact | release CI |
| Security | threat/control matrix is covered; dependency scan is clean or explicitly reviewed | security evidence |
| Governance | branch/tag/review controls are verified | governance evidence |
| Approval | authorized human approves publication | release record |

## Required pull-request CI topology

The required GitHub checks are stable by design:

| Check | Platform | Authority |
| --- | --- | --- |
| `quality` | Ubuntu 24.04 / Python 3.13 | lock + validation-environment identity, release/repository/version identity, source policy, Ruff, formatting, strict mypy, compilation, zero-drift security baseline |
| `tests-linux` | Ubuntu 24.04 / Python 3.13 | complete behavioral pytest suite, product-experience verifier, CLI verifier |
| `portability-windows` | Windows Server 2025 / Python 3.13 | targeted filesystem/path/archive/SQLite/recovery/containment regressions and failure lab |
| `package` | Ubuntu 24.04 / Python 3.13 | single source-independent package build and package-boundary verification |

Supported Python/OS release compatibility is intentionally moved to the exact built-artifact matrix in Release Verification. `ubuntu-latest`/`windows-latest` are not used by required gates; explicit runner images prevent an upstream `*-latest` migration from silently changing the required baseline. A separate scheduled `Platform Canary` exercises Ubuntu 26.04 without becoming a merge requirement.

Third-party GitHub Actions are pinned to full commit SHAs. `setup-uv` also pins the uv executable version; Dependabot monitors both `github-actions` and `uv` ecosystems and proposes reviewable upgrade PRs.

## Status semantics

- **PASS** — the gate executed and met its contract.
- **FAIL** — the gate executed and found a defect.
- **BLOCKED** — the environment prevented verification.
- **SKIPPED** — deliberately not applicable to the selected workflow.

`BLOCKED` and `SKIPPED` are never silently reported as `PASS`.

## Change classification

### Documentation-only
Run link/documentation verification and relevant spelling/format checks.

### Source change
Run formatting, lint, typing, compilation, unit/contract tests, and affected integration tests.

### Persistence/security change
Run the complete affected lifecycle plus adversarial and recovery gates.

### Public API or compatibility change
Run the full contract, compatibility, clean-consumer, and release-candidate gates.

### Release candidate
Run the complete release workflow and require human approval before publication.


## Public-trial regression gate

Run `python scripts/testing/run_public_trial_regressions.py --mode source` on every release candidate. This validates the source regressions derived from the frozen 2026-09-25 public-repository trial. A source-mode PASS does not qualify real SDKs or public hosts; inspect each case's `qualification_status`. Before resuming large-host trials, run the same command with `--mode qualification` in an environment containing the advertised native integration extras. Qualification mode reads those extras from `pyproject.toml`, records the installed distribution versions, and executes dedicated credential-free real-SDK probes. Missing SDKs are `BLOCKED_ENV`; an installed SDK whose required probe skips, cannot collect, or times out is `FAIL_INTEGRATION`; a failed native assertion is `FAIL_STATEWAKE`. See `docs/testing/NATIVE_INTEGRATION_QUALIFICATION.md`.

## Real-system validation evidence harness

`python scripts/testing/system_trial.py` is the repository-side coordinator for measured system trials. Its generated datasets, workspaces, host truth ledgers, StateWake event ledgers, and reports must be written outside the release source tree. The deterministic local controls validate the harness itself. `system_trial.py qualify-native-hosts` additionally composes the existing native qualification coordinator with real credential-free SDK host exercises, durable restart/read-back, and privacy-marker checks; PASS qualifies only the installed SDK/local-host boundary. It still does **not** qualify external public hosts. A scenario configured for an external host without a supplied result envelope is `BLOCKED_ENV`, never `PASS`.

The harness must preserve the campaign outcome vocabulary and keep host truth, StateWake capture, verification, and operator interpretation distinct. StateWake output must never be used as the oracle for StateWake.

### License metadata / PEP 639

Release packaging must retain `project.license = "Apache-2.0"` and `project.license-files = ["LICENSE"]`. Deprecated `License :: ...` Trove classifiers are not part of the current StateWake package metadata. `tests/release/test_license_metadata_policy.py` protects this boundary, and release builds should inspect wheel metadata and build output for license-metadata deprecation warnings.
## Deterministic validation-state lifecycle

Verification and state mutation are separate operations:

1. prepare the environment explicitly with `uv sync --locked --group dev --extra integrations` when needed;
2. run ordinary quality/tests or `run_sdlc_validation.py --profile check`; the SDLC verifier checks lock freshness, exact installed validation versions, release identity, and security assurance without synchronizing dependencies or rewriting maintained state;
3. if a reviewed candidate intentionally changes the security-assurance snapshot, promote it explicitly with `scripts/security/promote_security_assurance_baseline.py`;
4. refresh generated release identity explicitly with `scripts/release/refresh_release_identity.py` after all maintained inputs, including a promoted security baseline, are final;
5. run `run_sdlc_validation.py --profile release`; release verification requires zero security-baseline drift and a current persisted release identity.

`uv.lock`, `ui/package-lock.json`, maintained source/documentation, the promoted security baseline, and persisted release identity are never rewritten merely to make a verification command pass. A stale or inconsistent authority remains a failure until the appropriate explicit maintenance action is performed.

Release and supply-chain checks should validate structured metadata, executable behavior, file/content digests, and real interfaces. They must not depend on incidental README wording, prose sentences, CLI display phrases, or raw YAML substrings when an executable/structured authority exists.

