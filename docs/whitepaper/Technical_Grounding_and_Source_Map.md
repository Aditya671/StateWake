# StateWake v0.4.0 — Technical grounding and source map

This companion document is not part of the public white paper. It records the source basis for the v0.4.0 additions and the deliberate preservation of finalized v0.3.0 sections.

| White paper location | Grounded source(s) | Interpretation limit |
|---|---|---|
| §§ 1–5; §§ 7–8; §§ 10–12 | Prior finalized v0.3.0 white paper; current v0.4.0 `src/statewake`, README and architecture | Original wording retained where still compatible; outdated v0.3.0 scope updated |
| § 6.1 | `docs/architecture/ai-evidence-contracts.md`; `src/statewake/ai_contracts/`; `tests/unit/ai_contracts/`; `tests/workspace/ai_contracts/` | Producer report is not semantic correctness; persistence is explicit |
| § 6.2 | `docs/reference/claim-profiles.md`; `src/statewake/profiles/`; `src/statewake/services/reliability_claim_profile_service.py` | Profile satisfied is not human or business authorization |
| § 6.3 | `docs/user-guide/verification-reports.md`; `src/statewake/reports/` | `UNRUN-ENV` and `UNKNOWN` must not become pass |
| § 6.4 | `docs/operations/workspace-backup-restore.md`; `src/statewake/workspace/backup.py`, `restore.py`, `integrity_sweep.py`, `migrations/` | Migration markers v2/v3 do not imply physical SQLite schema v2/v3 |
| § 6.5 | `docs/integrations/phase5-producer-integrations.md`; `src/statewake/integrations/`; `tests/unit/integrations/` | Mapping/object adapters, not proven native compatibility with all upstream SDK releases |
| § 6.6 | `docs/release/release-trust-evidence.md`; `src/statewake/release_trust/`; `tests/unit/release_trust/` | Completeness != external publication authorization; does not replace release-proof service |
| § 6.7; § 9 | `src/statewake/validation_study/{metrics,workloads,faults,chains,model}.py`; `benchmarks/reports/phase7-d0a7f7cb840c.{md,json}`; `benchmarks/metrics/study-metrics.json` | Baseline property sets and fault-detection mappings are assigned in code; percentages are not observed commercial-product performance |
| § 9 verification | Re-run `run_comparative_validation_study()` and targeted pytest suite in available source tree | 60 selected tests passed; full-suite certification is outside this companion map |

## Reproduction notes

```
PYTHONPATH=src python -c 'from statewake.validation_study import run_comparative_validation_study; s=run_comparative_validation_study(); print(s.study_id, len(s.cases))'
PYTHONPATH=src pytest -q tests/benchmarks/test_phase7_comparative_validation.py tests/benchmarks/test_phase7_workspace.py tests/unit/ai_contracts/test_ai_contracts.py tests/unit/reports/test_human_verification_reports.py tests/unit/integrations/test_phase5_integrations.py tests/unit/release_trust/test_release_trust_bundle.py tests/workspace/test_workspace_backup_restore.py tests/workspace/ai_contracts/test_workspace_ai_contracts.py
```

Observed targeted result: `60 passed`. Observed benchmark ID: `phase7-d0a7f7cb840c` / 40 cases / 5 workloads / 12 cataloged fault kinds.

## External source types

The existing 15 public references remain unchanged: W3C recommendations, industry specifications, NIST publications, technical documentation, and preprints are labeled by their actual publication status. Neither standards-inspired design nor citation implies certification or full conformance.
