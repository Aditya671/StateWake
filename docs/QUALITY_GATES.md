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
## Deterministic validation-state preflight

Development changes are expected to change source digests. Therefore ordinary regression tests must not fail solely because a previously generated `verification_manifest.txt` or `candidate-fingerprint.txt` is stale. The supported candidate flow is:

1. run `scripts/release/prepare_sdlc_validation.py`; it refreshes only the derived release identity, immediately verifies it, checks `uv.lock` freshness, and executes continuous-security assurance without baseline promotion;
2. run the remaining behavioral/static gates;
3. verify release identity again after the check profile so an unexpected test/tool mutation cannot be hidden;
4. for the release profile, promote the continuous-security baseline only after successful affected security re-verification, then refresh and verify release identity one final time before candidate finalization.

The preflight deliberately does **not** regenerate `uv.lock`, `ui/package-lock.json`, current source/documentation, or `docs/security/security_assurance_baseline_manifest.txt`. Those are governed inputs, not disposable caches. A stale lock, stale source file, or failed security re-verification remains a failure instead of being rewritten merely to make the SDLC green.

Release and supply-chain checks should validate structured metadata, executable behavior, file/content digests, and real interfaces. They must not depend on incidental README wording, prose sentences, CLI display phrases, or raw YAML substrings when an executable/structured authority exists.

