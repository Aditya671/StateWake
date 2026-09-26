# StateWake v0.4.0 Release Verification

## Candidate

StateWake v0.4.0 seven-phase promoted candidate.

## Runnable gates in this sandbox

- Source and test compilation.
- StateWake module import walk.
- Unit, workspace, benchmark, release, supply-chain, and runnable security subsets.
- Package build.
- Package boundary verification.
- Verification manifest regeneration.
- Candidate fingerprint regeneration.
- Cache-free artifact packaging.

## Environment-limited gates

The following gates are release-environment checks when unavailable in the sandbox:

- Ruff lint and format checks.
- mypy strict type checking.
- Full PyNaCl-backed cryptographic proof tests.
- Network-dependent dependency synchronization, if package-index access is unavailable.

Unavailable gates must be reported as `UNRUN-ENV`; they are not passes.

## Promotion rule

v0.4.0 is promotable only when every runnable gate passes, every unavailable gate is explicitly recorded, the package version is synchronized across project-owned files, and the promoted ZIP contains no cache or transient execution artifacts.
