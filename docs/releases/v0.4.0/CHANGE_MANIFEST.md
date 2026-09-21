# v0.4.0 Change Manifest

## Scope

Promote the completed StateWake AI Systems Seven-Phase Roadmap into the package baseline.

## Added package areas

- `src/statewake/ai_contracts/`
- `src/statewake/profiles/`
- `src/statewake/reports/`
- `src/statewake/workspace/backup.py`
- `src/statewake/workspace/restore.py`
- `src/statewake/workspace/integrity_sweep.py`
- `src/statewake/workspace/migrations/`
- `src/statewake/integrations/`
- `src/statewake/release_trust/`
- `src/statewake/validation_study/`

## Added documentation areas

- `docs/architecture/ai-evidence-contracts.md`
- `docs/reference/claim-profiles.md`
- `docs/user-guide/verification-reports.md`
- `docs/operations/workspace-backup-restore.md`
- `docs/integrations/phase5-producer-integrations.md`
- `docs/release/release-trust-evidence.md`
- `docs/research/comparative-validation-study.md`
- `benchmarks/`

## Compatibility

- Public API contract version remains `1`.
- Existing release-proof and OpenTelemetry export paths are preserved.
- Legacy release-proof profile compatibility is retained separately from the stricter `release_evidence_complete.v1` AI release profile.
- StateWake package/release trust evidence remains separate from StateWake-managed AI-system claim trust.

## Version movement

- Package version: `0.4.0`.
- `statewake.__version__`: `0.4.0`.
- Active release docs: `docs/releases/v0.4.0/`.
- Previous minor-version strings were removed from the promoted artifact at the user's request.
