# Phase 7 Comparative Validation Study

This directory contains deterministic fixtures for comparing StateWake evidence,
claim profiles, workspace history, reports, integrations, and release-trust data
against simpler baselines.

The first supported study is intentionally fixture based. It does not make live
AI calls and does not claim general statistical superiority beyond the included
workloads and injected faults.

## Layout

- `workloads/` — representative workload definitions.
- `faults/` — deterministic injected failure classes.
- `baselines/` — final-output, log, trace, and StateWake-full baselines.
- `statewake_enabled/` — StateWake evidence/profile/report configuration notes.
- `metrics/` — generated metric files when a study is run.
- `reports/` — generated JSON and Markdown study reports.
