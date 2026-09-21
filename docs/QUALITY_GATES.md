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
