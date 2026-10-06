# Artifact Separation

StateWake distinguishes source, built distributions, generated verification evidence, and historical release records so one artifact role is not mistaken for another.

## Artifact roles

1. **Source repository** — `src/`, tests, examples, scripts, UI source, maintained documentation, CI definitions, packaging metadata, and release-governance inputs.
2. **Python distributions** — the wheel and source distribution produced from the exact candidate by the configured build backend.
3. **Generated release evidence** — checksums, attestations, SBOMs, audit output, release-candidate evidence, and similar run-specific files produced by verification/publishing workflows.
4. **Historical release records** — versioned notes and evidence retained beneath `docs/releases/`; these records are not rewritten merely because the current package advances.

## Production distribution boundary

The installable Python runtime is the built `statewake-ai` distribution. Repository tests, scripts, UI source, CI automation, benchmark fixtures, and project documentation support development and verification but are not installed as runtime package modules unless the build configuration explicitly includes them.

Built filenames are derived from the authoritative project metadata rather than hard-coded in governance policy. For example, a release wheel follows the normalized distribution/version form produced by the build backend (such as `statewake_ai-<version>-py3-none-any.whl`).

## Generated-output rule

`dist/`, `build/`, verification output, runtime workspaces, caches, UI build products, and local evidence are generated surfaces. They must not become source authorities and are excluded from maintained source identity except where a release workflow deliberately stages exact built distributions for publication evidence.

## Naming rule

Active files are named by purpose. Development-sequence identifiers such as historical `tier*` or `phase*` labels are not used in active file/module/test names when a stable purpose name exists. Historical release records and immutable evidence may retain original names where changing them would falsify the record.

The maintained rename history is recorded in `docs/governance/rename_map.tsv`.
