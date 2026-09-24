# StateWake v0.4.0 — Full Local-Machine Validation and Autonomous Agent Runbook

**Purpose:** Validate the corrected StateWake v0.4.0 candidate on a real local machine with the complete runtime dependency set, real native SDK imports, release/supply-chain tests, quality gates, adversarial tests, package build, clean-consumer installation, and Python compatibility checks.

**Primary target:** Windows 10/11 + PowerShell 7 or Windows PowerShell 5.1.  
**Project Python baseline:** 3.13 (`.python-version`), with compatibility checks on 3.11 and 3.12.  
**Package:** `statewake-ai==0.4.0`.  
**Build system:** `uv_build`.  
**Environment manager:** `uv`.  
**Do not publish** to TestPyPI/PyPI from this runbook. Publication requires separate explicit human approval.

---

## 1. Agent execution contract

A local AI coding agent may execute this runbook autonomously, but it must obey these rules.

1. **Never modify the original ZIP.** Treat it as immutable evidence.
2. Extract into a new working directory.
3. Keep all generated logs, test reports, temporary environments, wheels, SBOMs, and diagnostics **outside the release source tree whenever possible**.
4. Do not delete or weaken a failing test merely to obtain a green run.
5. Do not add `# noqa`, `type: ignore`, lint exclusions, skipped tests, `xfail`, relaxed assertions, or dependency exclusions unless the underlying project explicitly requires them and the reason is documented.
6. A `SKIPPED`, `BLOCKED`, collection error, missing dependency, timeout, or unreachable external service is **not a pass**.
7. If a source defect is found, create a working-copy fix, add/adjust a regression test for the actual invariant, rerun the targeted gate, then rerun every downstream gate affected by that change.
8. If a test is stale because the architecture intentionally changed, first prove the new architecture from `pyproject.toml`, source, and the governing release documents. Update the test to validate the new contract; do not merely invert or delete the assertion.
9. Do not regenerate `verification_manifest.txt` or `candidate-fingerprint.txt` until the final source changes are settled. If source files change, refresh those files only through the project’s actual release-scope logic.
10. Do not amend historical release evidence to make the current candidate appear previously verified.
11. Do not publish, tag, commit, or push unless separately instructed.
12. Preserve complete command output in the evidence directory.
13. At the end, classify every gate as exactly one of: `PASS`, `FAIL`, `BLOCKED`, or `SKIPPED/NOT-APPLICABLE`.
14. Final acceptance requires **zero unexplained failures** and **zero unqualified skips** in required local gates.

---

## 2. Current dependency model that must be validated

The current `pyproject.toml` declares all application/workspace/framework integrations as standard runtime dependencies. They are **not optional extras**.

Expected runtime declarations:

```text
pynacl==1.6.2
opentelemetry-api==1.44.0
filelock==3.32.4
duckdb==1.5.5
openpyxl==3.1.5
pyarrow==25.0.1
sqlalchemy==2.0.54
opentelemetry-sdk>=1.44,<2
openai-agents>=0.3,<1
langchain-core>=0.3,<2
langgraph>=0.3,<2
llama-index-core>=0.12,<1
```

Development-only dependencies:

```text
ruff==0.16.5
pytest==9.1.1
mypy==2.3.1
```

The current lockfile in the supplied candidate was observed to contain these resolved versions:

```text
pynacl                 1.6.2
opentelemetry-api      1.44.0
filelock               3.32.4
duckdb                  1.5.5
openpyxl                3.1.5
pyarrow                 25.0.1
sqlalchemy              2.0.54
opentelemetry-sdk      1.44.0
openai-agents           0.22.3
langchain-core          1.6.4
langgraph               1.2.12
llama-index-core        0.14.25
ruff                    0.16.5
pytest                  9.1.1
mypy                    2.3.1
```

The local agent must use `uv.lock` as the authoritative resolved dependency set, not the version list above if the lockfile differs in the user’s local artifact.

---

## 3. Known consistency checks to perform before testing

Because runtime/workspace/integration dependencies were recently moved from optional extras into normal project dependencies, search the current project for stale assumptions before declaring success.

Check for references such as:

- `statewake-ai[workspace]`
- `[project.optional-dependencies]`
- `optional_dependencies["workspace"]`
- `--all-extras`
- statements saying native SDKs are optional when the current package now installs them by default
- clean-consumer workflows that install the wheel with `--no-deps` and then install only a subset of required runtime packages

These references are not automatically defects: historical documents may legitimately describe older releases. **Current README, current CI workflow, current release scripts, current tests, and current user-guide documentation must match the current dependency architecture.**

PowerShell search:

```powershell
Get-ChildItem -Recurse -File README.md,docs,.github,scripts,tests -ErrorAction SilentlyContinue |
    Select-String -Pattern 'statewake-ai\[workspace\]|project\.optional-dependencies|optional_dependencies|--all-extras|optional workspace|optional integration' |
    Tee-Object -FilePath $ConsistencyLog
```

Classify every match as one of:

```text
CURRENT_AND_VALID
HISTORICAL_AND_VALID
STALE_CURRENT_DOC
STALE_CURRENT_TEST
STALE_CURRENT_WORKFLOW
STALE_CURRENT_SCRIPT
```

Any `STALE_CURRENT_*` result is a source/configuration defect and must be corrected before final acceptance.

---

# PART A — Machine preparation

## 4. Create an isolated validation root

Do not validate inside Downloads/Desktop directly.

Open PowerShell and define paths. Change only `$Zip` if needed.

```powershell
$ErrorActionPreference = "Stop"

$Zip = "C:\Path\To\StateWake-v0.4.0-supply-chain-test-fixed.zip"
$RunStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ValidationRoot = Join-Path $env:USERPROFILE "StateWake-Validation-$RunStamp"
$SourceRoot = Join-Path $ValidationRoot "source"
$EvidenceRoot = Join-Path $ValidationRoot "evidence"
$EnvRoot = Join-Path $ValidationRoot "venvs"
$ConsumerRoot = Join-Path $ValidationRoot "consumer"

New-Item -ItemType Directory -Force -Path $ValidationRoot,$SourceRoot,$EvidenceRoot,$EnvRoot,$ConsumerRoot | Out-Null

$ConsistencyLog = Join-Path $EvidenceRoot "preflight-current-architecture-search.log"
```

Verify the input exists:

```powershell
if (-not (Test-Path $Zip -PathType Leaf)) {
    throw "StateWake ZIP not found: $Zip"
}
```

Capture the original archive hash:

```powershell
Get-FileHash $Zip -Algorithm SHA256 |
    Format-List |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "00-original-zip-sha256.txt")
```

Also copy the ZIP into the validation root without modifying it:

```powershell
Copy-Item $Zip (Join-Path $ValidationRoot "original.zip")
```

---

## 5. Extract the source candidate

```powershell
Expand-Archive -LiteralPath $Zip -DestinationPath $SourceRoot -Force
Set-Location $SourceRoot
```

The expected root should contain at least:

```text
pyproject.toml
uv.lock
src/statewake/
tests/
scripts/
docs/
verification_manifest.txt
candidate-fingerprint.txt
```

Validate:

```powershell
$Required = @(
    "pyproject.toml",
    "uv.lock",
    "src\statewake",
    "tests",
    "scripts",
    "docs",
    "verification_manifest.txt",
    "candidate-fingerprint.txt"
)

foreach ($Item in $Required) {
    if (-not (Test-Path (Join-Path $SourceRoot $Item))) {
        throw "Required project entry is missing: $Item"
    }
}
```

Capture a raw extracted-tree inventory before any tooling runs:

```powershell
Get-ChildItem -Recurse -Force -File |
    Sort-Object FullName |
    ForEach-Object {
        $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$Hash  $($_.FullName.Substring($SourceRoot.Length + 1))"
    } | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "01-extracted-tree-inventory.txt")
```

Do **not** put this generated inventory in the project root.

---

## 6. Verify host prerequisites

### 6.1 PowerShell

```powershell
$PSVersionTable | Out-File (Join-Path $EvidenceRoot "02-powershell-version.txt")
```

### 6.2 Git

Git is useful for local diff/status tracking even if the ZIP has no `.git` directory.

```powershell
git --version 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceRoot "03-git-version.txt")
```

If Git is missing and the agent needs local diff tracking, install Git using the organization-approved method. Do not block source testing solely because Git is absent.

### 6.3 uv

Check first:

```powershell
uv --version 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceRoot "04-uv-version.txt")
```

If `uv` is not installed, install it using the official Astral installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close/reopen PowerShell if PATH was updated, then rerun:

```powershell
uv --version
```

### 6.4 Install supported Python interpreters through uv

```powershell
uv python install 3.11 3.12 3.13 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "05-uv-python-install.log")

uv python list 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "06-uv-python-list.txt")
```

Primary test interpreter: **Python 3.13**.

---

# PART B — Immutable dependency and release-input preflight

## 7. Validate project metadata directly

Run from `$SourceRoot`.

```powershell
uv run --no-project python -c "import tomllib,pathlib; p=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); print(p['project']['name'], p['project']['version'], p['project']['requires-python']); print('\n'.join(p['project']['dependencies'])); print('optional=',p['project'].get('optional-dependencies',{})); print('dev=',p.get('dependency-groups',{}).get('dev',[]))" 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "07-pyproject-metadata.txt")
```

Acceptance criteria:

```text
name == statewake-ai
version == 0.4.0
requires-python == >=3.11,<3.14
project.optional-dependencies is absent or empty
all workspace + native integration packages are under project.dependencies
ruff/pytest/mypy remain under dependency-groups.dev
```

If optional runtime groups still exist unexpectedly, stop and reconcile the actual artifact before proceeding.

---

## 8. Check lockfile consistency before synchronization

This is a critical gate.

```powershell
uv lock --check 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "08-uv-lock-check-before-sync.log")

if ($LASTEXITCODE -ne 0) {
    throw "uv.lock is not consistent with pyproject.toml. Do not continue as if locked dependencies were verified."
}
```

### If `uv lock --check` fails

The autonomous agent must:

1. Read the exact resolver error.
2. Confirm the mismatch is caused by current project metadata, not network outage.
3. Save the old lockfile hash:

```powershell
Get-FileHash uv.lock -Algorithm SHA256 |
    Format-List |
    Out-File (Join-Path $EvidenceRoot "08a-old-lock-hash.txt")
```

4. Run a real lock resolution:

```powershell
uv lock 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "08b-uv-lock-refresh.log")
```

5. Run `uv lock --check` again.
6. Treat any changed `uv.lock` as a source-candidate change requiring provenance manifest/fingerprint refresh later.

Do not hand-edit lockfile package records.

---

## 9. Search for dependency-model drift

Run the consistency search described in Section 3.

PowerShell version that is safe when individual paths are missing:

```powershell
$SearchTargets = @("README.md", "docs", ".github", "scripts", "tests") |
    ForEach-Object { Join-Path $SourceRoot $_ } |
    Where-Object { Test-Path $_ }

Get-ChildItem -Path $SearchTargets -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern 'statewake-ai\[workspace\]|project\.optional-dependencies|optional_dependencies|--all-extras|optional workspace|optional integration' |
    Tee-Object -FilePath $ConsistencyLog
```

The agent must review each match. Historical references under `docs/releases/`, `docs/research/`, or historical audit material can be valid. Current README/current CI/current release tests must describe the actual current architecture.

---

# PART C — Primary Python 3.13 environment

## 10. Create the Python 3.13 project environment outside the source tree

This avoids adding `.venv` to the release tree.

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $EnvRoot "py313"

uv sync --locked --group dev --python 3.13 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "10-uv-sync-py313.log")

if ($LASTEXITCODE -ne 0) {
    throw "Python 3.13 locked synchronization failed."
}
```

Validate interpreter:

```powershell
uv run --no-sync python -VV 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "11-python313-version.txt")
```

Expected major/minor: `3.13`.

---

## 11. Record the resolved environment

```powershell
uv tree --locked 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "12-uv-tree-py313.txt")

uv pip list 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "13-uv-pip-list-py313.txt")

uv run --no-sync python -m pip --version 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "14-pip-version-py313.txt")
```

If `python -m pip` is not installed in the uv environment, this is not necessarily a StateWake defect; `uv pip` is the package-management authority for the project.

---

# PART D — Native runtime dependency verification

## 12. Import every required runtime dependency directly

Create a one-time command; do not add this file to the source tree.

```powershell
@'
import sys
import nacl
import filelock
import duckdb
import openpyxl
import pyarrow
import sqlalchemy
import opentelemetry
import opentelemetry.sdk.trace
import agents
import agents.tracing.processor_interface
import langchain_core
import langchain_core.callbacks.base
import langgraph
import langgraph.graph
import llama_index.core
import llama_index.core.instrumentation.event_handlers

print("python", sys.version)
print("nacl", getattr(nacl, "__version__", "unknown"))
print("filelock", getattr(filelock, "__version__", "unknown"))
print("duckdb", getattr(duckdb, "__version__", "unknown"))
print("openpyxl", getattr(openpyxl, "__version__", "unknown"))
print("pyarrow", getattr(pyarrow, "__version__", "unknown"))
print("sqlalchemy", getattr(sqlalchemy, "__version__", "unknown"))
print("agents", getattr(agents, "__version__", "unknown"))
print("langchain_core", getattr(langchain_core, "__version__", "unknown"))
print("langgraph", getattr(langgraph, "__version__", "unknown"))
print("llama_index.core", getattr(llama_index.core, "__version__", "unknown"))
print("ALL_RUNTIME_IMPORTS_OK")
'@ | uv run --no-sync python - 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "15-runtime-import-smoke.log")

if ($LASTEXITCODE -ne 0) {
    throw "At least one required runtime dependency cannot be imported."
}
```

This gate is mandatory because previous isolated test environments could skip SDK tests when packages were unavailable.

---

## 13. Verify the installed StateWake package and public CLI

```powershell
uv run --no-sync python -c "import statewake; print(statewake.__version__); print(statewake.__public_api_contract_version__)" 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "16-statewake-import.txt")

uv run --no-sync statewake version 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "17-statewake-cli-version.txt")

uv run --no-sync python scripts/release/verify_cli_surface.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "18-cli-surface.log")
```

Expected version: `0.4.0`.

---

# PART E — Release and supply-chain validation first

## 14. Run the specific supply-chain test that previously failed

```powershell
uv run --no-sync python -m pytest -q tests/release/test_supply_chain_provenance.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "20-test-supply-chain-provenance.log")

if ($LASTEXITCODE -ne 0) {
    throw "Supply-chain provenance regression failed. Fix before proceeding to release qualification."
}
```

Expected current baseline: **10 passed**.

Do not hardcode success purely from the expected count; all tests in the file must pass.

---

## 15. Run all release tests

```powershell
uv run --no-sync python -m pytest -q tests/release 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "21-tests-release.log")

if ($LASTEXITCODE -ne 0) {
    throw "Release regression suite failed."
}
```

Expected baseline from the corrected artifact: **12 passed**.

---

## 16. Validate version identity and repository boundary

```powershell
uv run --no-sync python scripts/release/verify_versioning.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "22-verify-versioning.log")

uv run --no-sync python scripts/release/verify_repository_structure.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "23-verify-repository-structure.log")

uv run --no-sync python scripts/release/verify_repository_governance.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "24-verify-repository-governance.log")
```

If repository-governance expects live Git metadata and the ZIP is not a Git checkout, classify it as `BLOCKED_BY_SOURCE_ARCHIVE_CONTEXT`, not `PASS`, and rerun it later from the Git repository checkout if required.

---

# PART F — Source quality gates

## 17. Project source-quality verifier

```powershell
uv run --no-sync python scripts/development/verify_source_quality.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "30-source-quality.log")
```

---

## 18. Ruff lint

Use the locked dev environment, not a floating Ruff release.

```powershell
uv run --no-sync ruff check src tests scripts 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "31-ruff-check.log")
```

Do not run `ruff --fix` before capturing the first failure report.

If lint fails and the defect is valid:

1. save the failure output;
2. make minimal source corrections;
3. rerun `ruff check`;
4. do not use blanket ignores to hide defects.

---

## 19. Ruff format check

```powershell
uv run --no-sync ruff format --check src tests scripts 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "32-ruff-format-check.log")
```

If only formatting fails, inspect the diff first:

```powershell
uv run --no-sync ruff format --diff src tests scripts 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "32a-ruff-format-diff.log")
```

Then format only if the changes are acceptable:

```powershell
uv run --no-sync ruff format src tests scripts
```

Rerun both format-check and lint afterwards.

---

## 20. Strict mypy

```powershell
uv run --no-sync mypy 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "33-mypy-strict.log")
```

The `pyproject.toml` config covers `src`, `tests`, `scripts`, and `docs` under strict mode, with a narrower test override.

Do not suppress a new error unless there is a documented project reason.

---

## 21. Compile all active Python

```powershell
uv run --no-sync python -m compileall -q src tests scripts docs 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "34-compileall.log")
```

A non-zero exit code is a hard failure.

---

# PART G — Native SDK integration qualification

## 22. Run only the real native SDK import/capture tests first

```powershell
$NativeTests = @(
    "tests/unit/integrations/test_native_sdk_import_contracts.py",
    "tests/unit/integrations/test_native_sdk_capture.py",
    "tests/unit/integrations/test_native_evidence_boundaries.py",
    "tests/unit/integrations/test_native_capture_durability_and_observations.py",
    "tests/unit/integrations/test_native_capture_journal_limit.py",
    "tests/unit/integrations/test_native_metadata_admission.py",
    "tests/unit/integrations/test_mapping_observation_integrity.py",
    "tests/unit/integrations/test_pending_audit_defects.py",
    "tests/unit/integrations/test_phase5_integrations.py"
)

uv run --no-sync python -m pytest -q $NativeTests 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "40-native-sdk-integrations.log")
```

### Acceptance rule

Because all SDKs are now mandatory runtime dependencies, **an integration test skipped because an SDK import is missing is a failure of local qualification**, even if pytest exits zero.

Capture skip reasons:

```powershell
uv run --no-sync python -m pytest -ra $NativeTests 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "40a-native-sdk-integrations-with-skip-reasons.log")
```

The agent must inspect the summary for `SKIPPED`/`XFAIL` and classify each one.

---

## 23. Verify workspace integrations

```powershell
uv run --no-sync python -c "import duckdb,openpyxl,pyarrow,sqlalchemy; import statewake.workspace as w; print('workspace-imports-ok'); print(w.DuckDBAnalyticalAdapter); print(w.SqlAlchemyWorkspaceRepository)" 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "41-workspace-imports.log")

uv run --no-sync python -m pytest -q tests/workspace 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "42-tests-workspace.log")
```

---

# PART H — Security and trust qualification

## 24. PyNaCl / Ed25519 trust checks

First verify PyNaCl is genuinely installed:

```powershell
uv run --no-sync python -c "from nacl.signing import SigningKey, VerifyKey; k=SigningKey.generate(); m=b'statewake-local-trust-smoke'; s=k.sign(m).signature; VerifyKey(bytes(k.verify_key)).verify(m,s); print('PYNACL_ED25519_OK')" 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "50-pynacl-ed25519-smoke.log")
```

Then run trust/security tests:

```powershell
uv run --no-sync python -m pytest -q tests/security tests/test_key_management.py tests/test_trust_anchor.py tests/test_security_audit.py tests/test_security_contract.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "51-security-tests.log")
```

---

## 25. Run every deterministic security verifier

```powershell
$SecurityScripts = @(
    "scripts/security/verify_security_assurance_boundary.py",
    "scripts/security/verify_cryptographic_trust_migration.py",
    "scripts/security/verify_data_lifecycle_confidentiality.py",
    "scripts/security/verify_forensic_continuity.py",
    "scripts/security/verify_identity_access_controls.py",
    "scripts/security/verify_recovery_resilience.py",
    "scripts/security/verify_reliability_proof_portability.py",
    "scripts/security/verify_runtime_containment.py",
    "scripts/security/verify_trust_domain_anchors.py",
    "scripts/security/verify_continuous_security_assurance.py"
)

foreach ($Script in $SecurityScripts) {
    $SafeName = ($Script -replace '[\\/]', '_') -replace '\.py$',''
    $Log = Join-Path $EvidenceRoot ("52-" + $SafeName + ".log")
    Write-Host "Running $Script"
    uv run --no-sync python $Script 2>&1 | Tee-Object -FilePath $Log
    if ($LASTEXITCODE -ne 0) {
        throw "Security verifier failed: $Script"
    }
}
```

---

# PART I — Full regression suite

## 26. Full pytest collection and run

First check collection:

```powershell
uv run --no-sync python -m pytest --collect-only -q 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "60-pytest-collect-only.log")
```

Collection must finish successfully.

Then full test run:

```powershell
uv run --no-sync python -m pytest -ra 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "61-pytest-full.log")

if ($LASTEXITCODE -ne 0) {
    throw "Full pytest suite failed."
}
```

### Mandatory post-run review

The agent must parse the final summary and record:

```text
passed =
failed =
errors =
skipped =
xfail =
xpass =
warnings =
```

Every skipped test must have a reason. A missing mandatory runtime package is not an acceptable skip anymore.

---

# PART J — Adversarial and real-world validation

## 27. Property state machine

```powershell
uv run --no-sync python scripts/testing/property_state_machine.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "70-property-state-machine.log")
```

---

## 28. Real-world scenarios

```powershell
uv run --no-sync python scripts/testing/run_real_world_scenarios.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "71-real-world-validation.log")
```

---

## 29. Chaos validation

```powershell
uv run --no-sync python scripts/testing/run_chaos_validation.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "72-chaos-validation.log")

uv run --no-sync python scripts/testing/run_deep_chaos_validation.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "73-deep-chaos-validation.log")

uv run --no-sync python scripts/testing/run_extreme_validation.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "74-extreme-validation.log")
```

---

## 30. Failure lab

```powershell
uv run --no-sync python scripts/testing/failure_lab.py --ci 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "75-failure-lab.log")
```

---

# PART K — External integration validation

## 31. Deterministic fixture mode first

This must pass without live network services.

```powershell
uv run --no-sync python scripts/integration/run_external_integrations.py --mode ci 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "80-external-integrations-fixture.log")
```

Expected high-level status: `PASS`.

---

## 32. Live public external capture

This requires internet access and reaches the public GitHub API and NYC Open Data endpoint.

```powershell
uv run --no-sync python scripts/integration/run_external_integrations.py --mode live 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "81-external-integrations-live.log")
```

Exit behavior from the current runner:

```text
0 = PASS
2 = NO_LIVE_CAPTURES
3 = LIVE_EXTERNAL_GATE_BLOCKED
```

A network/DNS/proxy failure should be classified as `BLOCKED`, not a StateWake source failure, unless the local network is known-good and the request handling itself is defective.

---

# PART L — SDLC orchestration

## 33. Run the normal SDLC check profile

Use an output file outside the source tree.

```powershell
$SdlcCheck = Join-Path $EvidenceRoot "90-sdlc-check.json"

uv run --no-sync python scripts/release/run_sdlc_validation.py --profile check --timeout 600 --output $SdlcCheck 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "90-sdlc-check.log")
```

The JSON must have:

```text
workflow == statewake-sdlc
profile == check
status == passed
publication_authorized == false
```

---

## 34. Run the release SDLC profile

```powershell
$SdlcRelease = Join-Path $EvidenceRoot "91-sdlc-release.json"

uv run --no-sync python scripts/release/run_sdlc_validation.py --profile release --timeout 900 --output $SdlcRelease 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "91-sdlc-release.log")
```

This profile includes:

```text
repository-structure
version-identity
source-quality
ruff-check
ruff-format
strict-typecheck
source-compilation
unit-and-integration-tests
product-experience
cli-surface
property-state-machine
real-world-validation
chaos-validation
deep-chaos-validation
extreme-validation
failure-lab
external-integration-fixtures
release-candidate
```

All applicable gates must pass.

---

# PART M — Build and distribution validation

## 35. Clean previous build output

Build output is generated material and should not be part of source identity.

```powershell
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
```

---

## 36. Build wheel and source distribution

```powershell
uv build 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "100-uv-build.log")

if ($LASTEXITCODE -ne 0) {
    throw "Package build failed."
}
```

List artifacts:

```powershell
Get-ChildItem dist -File |
    Select-Object Name,Length,LastWriteTime |
    Format-Table -AutoSize |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "101-dist-list.txt")
```

---

## 37. Verify the package boundary

```powershell
uv run --no-sync python scripts/release/verify_package_boundary.py dist 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "102-package-boundary.log")
```

---

## 38. Hash the exact built artifacts

```powershell
Get-ChildItem dist -File |
    ForEach-Object { Get-FileHash $_.FullName -Algorithm SHA256 } |
    Format-Table -AutoSize |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "103-dist-sha256.txt")
```

---

# PART N — Clean consumer installation from the built wheel

## 39. Create an independent consumer environment

This step proves the built artifact is installable without relying on the editable project environment.

```powershell
$Wheel = (Get-ChildItem dist -Filter *.whl | Select-Object -First 1).FullName
if (-not $Wheel) { throw "No wheel found in dist." }

$ConsumerVenv = Join-Path $ConsumerRoot "py313"
uv venv $ConsumerVenv --python 3.13
$ConsumerPython = Join-Path $ConsumerVenv "Scripts\python.exe"
```

### Important dependency rule

Because all workspace and integration packages are now standard runtime dependencies, **install the wheel with dependencies**. Do not reproduce an old `--no-deps` consumer pattern unless the test explicitly installs every declared dependency separately.

```powershell
uv pip install --python $ConsumerPython $Wheel 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "110-consumer-wheel-install.log")
```

---

## 40. Consumer import smoke

```powershell
@'
import statewake
import nacl
import duckdb
import openpyxl
import pyarrow
import sqlalchemy
import opentelemetry.sdk.trace
import agents.tracing.processor_interface
import langchain_core.callbacks.base
import langgraph.graph
import llama_index.core.instrumentation.event_handlers

from statewake import load_evidence_chain, verify_evidence_chain

print("statewake", statewake.__version__)
print("public-api", statewake.__public_api_contract_version__)
print("CLEAN_CONSUMER_IMPORTS_OK")
'@ | & $ConsumerPython - 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "111-consumer-import-smoke.log")
```

---

## 41. Consumer CLI smoke

```powershell
$ConsumerStateWake = Join-Path $ConsumerVenv "Scripts\statewake.exe"
& $ConsumerStateWake version 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "112-consumer-cli-version.log")
```

Also enumerate supported commands:

```powershell
@'
import subprocess, sys
from statewake.cli.main import supported_commands

subprocess.run([sys.executable, "-m", "statewake.cli.main", "version"], check=True)
for command in supported_commands():
    subprocess.run([sys.executable, "-m", "statewake.cli.main", command, "--help"], check=True)
print("CONSUMER_CLI_SURFACE_OK")
'@ | & $ConsumerPython - 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "113-consumer-cli-surface.log")
```

---

# PART O — Python compatibility matrix

## 42. Validate Python 3.11, 3.12, and 3.13 independently

Use a separate environment for each Python version and keep all environments outside the source tree.

```powershell
$PythonVersions = @("3.11", "3.12", "3.13")

foreach ($Version in $PythonVersions) {
    $Tag = $Version.Replace(".", "")
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $EnvRoot ("py" + $Tag)

    Write-Host "===== Python $Version ====="

    uv sync --locked --group dev --python $Version 2>&1 |
        Tee-Object -FilePath (Join-Path $EvidenceRoot ("120-sync-py" + $Tag + ".log"))
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed for Python $Version" }

    uv run --no-sync python -VV 2>&1 |
        Tee-Object -FilePath (Join-Path $EvidenceRoot ("121-version-py" + $Tag + ".txt"))

    uv run --no-sync python -c "import statewake,nacl,duckdb,openpyxl,pyarrow,sqlalchemy,agents,langchain_core,langgraph,llama_index.core,opentelemetry.sdk.trace; print('MATRIX_IMPORTS_OK')" 2>&1 |
        Tee-Object -FilePath (Join-Path $EvidenceRoot ("122-imports-py" + $Tag + ".log"))

    uv run --no-sync python -m pytest -q tests/unit/integrations tests/workspace tests/release 2>&1 |
        Tee-Object -FilePath (Join-Path $EvidenceRoot ("123-core-matrix-tests-py" + $Tag + ".log"))
    if ($LASTEXITCODE -ne 0) { throw "Core matrix tests failed for Python $Version" }
}
```

After the matrix, return the primary environment to 3.13 if more work is required:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $EnvRoot "py313"
```

---

# PART P — Release-input manifest and fingerprint integrity

## 43. Validate the current supply-chain source identity

Run the supply-chain regression again after all source changes are complete.

```powershell
uv run --no-sync python -m pytest -q tests/release/test_supply_chain_provenance.py 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "130-final-supply-chain-tests.log")
```

If the source tree was **not changed**, `verification_manifest.txt` and `candidate-fingerprint.txt` should already match.

If the local agent made legitimate source/config/test/document changes during remediation, the manifest/fingerprint will intentionally become stale. The agent must:

1. finish all source changes;
2. use `scripts/common/release_scope.py` / the project’s provenance implementation to identify the exact selected current-project files;
3. regenerate the manifest/fingerprint using the same hashing algorithm as `verify_supply_chain_provenance.py`;
4. rerun the supply-chain tests;
5. verify that unrelated generated files outside the release scope do not alter the source identity.

**Do not simply exclude a failing source file from release scope to make the digest pass.**

---

# PART Q — Optional dependency security audit

## 44. pip-audit on a clean installed wheel environment

This is a security signal, not a reason to silently upgrade locked dependencies.

Install `pip-audit` only in a separate audit environment, not the StateWake project environment:

```powershell
$AuditVenv = Join-Path $ConsumerRoot "audit-py313"
uv venv $AuditVenv --python 3.13
$AuditPython = Join-Path $AuditVenv "Scripts\python.exe"

uv pip install --python $AuditPython $Wheel pip-audit 2>&1 |
    Tee-Object -FilePath (Join-Path $EvidenceRoot "140-audit-install.log")

& $AuditPython -m pip_audit --format json --output (Join-Path $EvidenceRoot "141-pip-audit.json")
```

If vulnerabilities are reported:

- do not auto-upgrade dependencies without compatibility testing;
- capture advisory IDs, affected versions, fixed versions, exploitability/context, and project exposure;
- classify each as `BLOCK_RELEASE`, `REQUIRES_REVIEW`, or `NOT_APPLICABLE_WITH_JUSTIFICATION`.

---

# PART R — Controlled defect-repair loop for the AI agent

## 45. What the agent must do when a gate fails

For each failure, create a defect record in the evidence directory using this format:

```markdown
## DEFECT-XXX

- Gate:
- Command:
- Exit code:
- First failing test/check:
- Failure category: SOURCE / TEST-CONTRACT / CONFIG / DEPENDENCY / HOST / NETWORK / HISTORICAL-DOC / UNKNOWN
- Reproducible: YES/NO
- Minimal reproduction:
- Expected behavior:
- Actual behavior:
- Root cause:
- Files changed:
- New regression test:
- Targeted rerun result:
- Full affected rerun result:
- Remaining risk:
```

### Allowed autonomous fixes

The agent may fix, without waiting for further clarification:

- invalid imports;
- stale current tests that contradict the current declared architecture;
- incorrect package/runtime dependency declarations;
- source logic defects;
- release-script path/bootstrap defects;
- mismatched current docs that instruct an invalid installation flow;
- CI commands that no longer install/verify the actual declared runtime boundary;
- missing regression coverage for a confirmed defect;
- deterministic formatting/type/lint defects;
- stale manifest/fingerprint caused by legitimate source changes after all changes are complete.

### Do not auto-fix these by weakening policy

- remove a security check because it fails;
- skip a test because an SDK is now mandatory;
- change a negative test to accept unsafe behavior;
- remove runtime dependencies merely to satisfy a lockfile;
- suppress mypy/Ruff errors broadly;
- reduce the supported Python range to bypass a compatibility defect;
- authorize release publication;
- rewrite historical evidence to match current results.

---

# PART S — Final rerun after any fix

## 46. Mandatory rerun sequence after the final source modification

Once the last code/config/test/document change is made, rerun in this order:

```text
1. uv lock --check
2. runtime import smoke
3. tests/release/test_supply_chain_provenance.py
4. tests/release
5. source-quality verifier
6. Ruff check
7. Ruff format --check
8. mypy
9. compileall
10. native SDK integration tests
11. workspace tests
12. security tests and security scripts
13. full pytest
14. property state machine
15. real-world scenarios
16. chaos/deep-chaos/extreme/failure-lab
17. fixture external integration test
18. SDLC check
19. SDLC release
20. uv build
21. package-boundary verification
22. clean-consumer wheel install/import/CLI
23. Python 3.11/3.12/3.13 matrix
24. final supply-chain regression
```

No final artifact should be called verified if a required step above is omitted without an explicit `BLOCKED` explanation.

---

# PART T — Final evidence report

## 47. Produce `LOCAL_VALIDATION_REPORT.md` in the evidence directory

The report must contain at least:

```markdown
# StateWake v0.4.0 Local Validation Report

## Candidate
- Original ZIP path:
- Original ZIP SHA-256:
- Source working path:
- Project version:
- Candidate fingerprint before changes:
- Candidate fingerprint after changes:
- uv.lock SHA-256:

## Host
- OS:
- CPU architecture:
- PowerShell:
- uv:
- Python 3.11:
- Python 3.12:
- Python 3.13:

## Dependency qualification
- uv lock --check:
- uv sync 3.13:
- mandatory runtime imports:
- native SDK imports:
- workspace imports:
- PyNaCl Ed25519 smoke:

## Quality
- source quality:
- Ruff:
- Ruff format:
- mypy:
- compileall:

## Tests
- supply-chain test file:
- release suite:
- native integrations:
- workspace:
- security:
- full pytest:
- skipped tests and justification:

## Adversarial validation
- property state machine:
- real-world scenarios:
- chaos:
- deep chaos:
- extreme:
- failure lab:

## External validation
- fixture integrations:
- live integrations:

## Release validation
- SDLC check:
- SDLC release:
- build:
- package boundary:
- clean consumer:
- Python 3.11 matrix:
- Python 3.12 matrix:
- Python 3.13 matrix:
- dependency audit:

## Defects found and fixed
1. ...

## Open blockers
1. ...

## Final classification
- SOURCE_VERIFIED_LOCALLY: YES/NO
- BUILT_ARTIFACT_VERIFIED_LOCALLY: YES/NO
- NATIVE_SDKS_VERIFIED_LOCALLY: YES/NO
- SECURITY_GATES_VERIFIED_LOCALLY: YES/NO
- CROSS_PYTHON_MATRIX_VERIFIED_LOCALLY: YES/NO
- PUBLICATION_AUTHORIZED: NO
```

The agent should link every result to the corresponding evidence log filename.

---

# PART U — Manual operator checklist

If a human wants the shortest safe manual sequence after setup, use this order from the repository root.

```powershell
# Use the isolated Python 3.13 project environment.
$env:UV_PROJECT_ENVIRONMENT = Join-Path $EnvRoot "py313"

# Lock + environment.
uv lock --check
uv sync --locked --group dev --python 3.13

# Mandatory SDK/runtime import smoke.
uv run --no-sync python -c "import statewake,nacl,duckdb,openpyxl,pyarrow,sqlalchemy,agents.tracing.processor_interface,langchain_core.callbacks.base,langgraph.graph,llama_index.core.instrumentation.event_handlers,opentelemetry.sdk.trace; print('imports-ok')"

# The previously problematic release tests.
uv run --no-sync python -m pytest -q tests/release/test_supply_chain_provenance.py
uv run --no-sync python -m pytest -q tests/release

# Quality.
uv run --no-sync python scripts/development/verify_source_quality.py
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync mypy
uv run --no-sync python -m compileall -q src tests scripts docs

# Native SDKs + workspace + security.
uv run --no-sync python -m pytest -ra tests/unit/integrations
uv run --no-sync python -m pytest -q tests/workspace
uv run --no-sync python -m pytest -q tests/security tests/test_key_management.py tests/test_trust_anchor.py tests/test_security_audit.py tests/test_security_contract.py

# Full regression.
uv run --no-sync python -m pytest -ra

# Adversarial campaigns.
uv run --no-sync python scripts/testing/property_state_machine.py
uv run --no-sync python scripts/testing/run_real_world_scenarios.py
uv run --no-sync python scripts/testing/run_chaos_validation.py
uv run --no-sync python scripts/testing/run_deep_chaos_validation.py
uv run --no-sync python scripts/testing/run_extreme_validation.py
uv run --no-sync python scripts/testing/failure_lab.py --ci

# Integration fixture and live smoke.
uv run --no-sync python scripts/integration/run_external_integrations.py --mode ci
uv run --no-sync python scripts/integration/run_external_integrations.py --mode live

# Orchestrated project gates.
uv run --no-sync python scripts/release/run_sdlc_validation.py --profile check --timeout 600
uv run --no-sync python scripts/release/run_sdlc_validation.py --profile release --timeout 900

# Build + boundary.
uv build
uv run --no-sync python scripts/release/verify_package_boundary.py dist
```

Then perform the clean-consumer and Python-version matrix steps described above.

---

# PART V — Acceptance criteria

## 48. Local source acceptance

StateWake may be classified `SOURCE_VERIFIED_LOCALLY` only when all of the following are true:

- `uv lock --check` passes;
- `uv sync --locked --group dev --python 3.13` passes;
- every required runtime dependency imports;
- native SDK integration tests run with actual installed SDKs;
- supply-chain provenance tests pass;
- all release tests pass;
- source quality, Ruff, formatting, mypy, and compilation pass;
- security and PyNaCl-backed trust tests pass;
- full pytest passes;
- required skips are zero or individually justified as truly non-applicable;
- workspace tests pass;
- adversarial campaigns pass;
- fixture integration validation passes;
- SDLC check and release profiles pass;
- no unresolved current dependency-model drift remains.

## 49. Built-artifact acceptance

StateWake may be classified `BUILT_ARTIFACT_VERIFIED_LOCALLY` only when:

- source acceptance passes;
- `uv build` succeeds;
- package boundary verification passes;
- exact dist hashes are recorded;
- the wheel installs into a clean environment **with its declared dependencies**;
- StateWake public imports and CLI work from that clean wheel environment;
- all mandatory native framework SDK imports work in the consumer environment.

## 50. Compatibility acceptance

StateWake may be classified `CROSS_PYTHON_MATRIX_VERIFIED_LOCALLY` only when:

- Python 3.11 locked sync + required core tests pass;
- Python 3.12 locked sync + required core tests pass;
- Python 3.13 locked sync + required core tests pass.

## 51. What local validation does not authorize

Even a completely green local run does **not** by itself authorize:

- a Git tag;
- GitHub release creation;
- TestPyPI upload;
- PyPI publication;
- external provenance attestation;
- human release approval.

Those remain separate repository/CI/human gates.

---

# PART W — Important project-specific cautions

1. **All runtime dependencies are now mandatory.** Do not rely on older instructions that install `statewake-ai[workspace]` as an optional extra.
2. The current project still contains historical release documents. Historical statements must not be interpreted as verification of the current native-SDK behavior.
3. `verification_manifest.txt` is a manifest of the project’s selected release inputs, not every extracted ZIP member.
4. Generated evidence should remain outside the release source tree or in project-designated generated output locations.
5. Do not classify a missing native SDK as a legitimate skip: the SDKs are now standard project dependencies.
6. Do not confuse fixture-mode external integration validation with live network qualification.
7. Do not confuse successful file/digest verification with signer authenticity or human publication authorization.
8. The primary local Python is 3.13, but the declared package supports 3.11, 3.12, and 3.13.
9. A clean consumer test must validate the built wheel, not source-tree imports.
10. If current GitHub workflow commands still model the older optional-dependency architecture, record and fix that as a current release-workflow defect before calling the candidate release-ready.

---

## 52. Expected final outcome

A successful local-machine campaign should leave the operator with:

```text
original.zip                         immutable input
source/                              tested working candidate
evidence/
  00-original-zip-sha256.txt
  ... all command logs ...
  141-pip-audit.json
  LOCAL_VALIDATION_REPORT.md
venvs/
  py311/
  py312/
  py313/
consumer/
  py313/
  audit-py313/
```

The final report must make it possible for another engineer or AI agent to answer, without guessing:

- exactly which artifact was tested;
- exactly which Python and dependency versions were used;
- which StateWake capability was exercised by each gate;
- every command that ran;
- every test that passed, failed, skipped, or was blocked;
- what changes were made after a failure;
- whether the same corrected source passed regression afterwards;
- whether the built wheel works independently of the source checkout;
- whether all native SDKs really imported and executed;
- whether release/supply-chain identity still matches the corrected candidate;
- what, if anything, still blocks release promotion.

**Do not shorten this process for the first complete local qualification of the current StateWake v0.4.0 candidate.** Once a full green baseline is recorded, future changes can use the project’s change-classification rules in `docs/QUALITY_GATES.md` to select smaller affected-gate subsets during development, while still running the complete release profile before promotion.
