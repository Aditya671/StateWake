# Release Candidate Protocol

The release-candidate protocol turns the existing release workflow into an executable local candidate process.

## Gate order

```text
release contract
→ version identity
→ compatibility fixtures
→ product experience
→ source compilation
→ wheel build
→ package boundary
→ release provenance
→ human approval
```

Run the deterministic candidate gate with:

```bash
python scripts/release/verify_release_candidate.py
```

The command writes `verification/release-candidate-evidence.json`. That file is release evidence, not an authorization to publish.

## Fresh-environment requirement

A release candidate is not complete until the exact built wheel is installed into a clean Python 3.11, 3.12, and 3.13 consumer environment and the public imports and CLI are exercised. The repository's GitHub release workflow is the authoritative multi-platform implementation of that gate.

## Compatibility and rollback

The compatibility fixture suite loads the persisted public artifact forms under `tests/fixtures/compatibility/` and rejects unknown format versions. This is the supported compatibility contract for the current pre-1.0 baseline.

There is no supported in-place rollback migration between published StateWake package versions yet. The operational rollback boundary is therefore **artifact rollback**: restore the previously approved package and retain the existing evidence directory unchanged. Any schema migration that changes persisted formats requires a dedicated compatibility implementation and regression fixture before publication.

## Provenance

Candidate evidence records:

- exact package version;
- deterministic source-tree digest;
- executable gate results;
- artifact/package checks;
- explicit human-approval requirement;
- publication authorization state.

The source-tree digest is a snapshot identity when no Git repository metadata is available in the execution environment. A hosted release should additionally bind the evidence to its immutable source commit through the repository platform's provenance attestation.

## Approval boundary

The release-candidate process cannot autonomously approve publication. Human release approval remains a required final gate, and a successful candidate run explicitly records `publication_authorized: false` until that decision is made.
