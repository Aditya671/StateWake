# Current release-input boundary

The source candidate is **not** the same as the extracted development ZIP or the
installed wheel. `scripts/common/release_scope.py` is the sole current-project
file selector shared by source provenance, release-candidate fingerprinting,
Tier 5 security snapshots and active-identity scanning.

The selected inputs include `src/`, current configuration, build metadata and
lockfile, maintained tests and verification scripts, CI workflows, maintained
current documentation and relevant benchmark fixtures. Historical release
notes (`docs/releases/`), research (`docs/research/`), audit/remediation records
(`docs/verification/`), generated benchmark reports, root `verification/`
outputs and arbitrary scratch files are intentionally outside this identity.
They can be retained for history without turning into current verification
requirements. The copied historical audit report and 495-file catalog are
omitted from this clean runnable candidate; the historical audit is available
as a separate source artifact.

`verification_manifest.txt` is an exhaustive manifest **of selected release
inputs only**, not of the entire repository. `candidate-fingerprint.txt`
records the corresponding deterministic `source_tree_digest`. Both identity
files are excluded from their own digest. Build and lock verification remain
separate obligations: excluding historical material does not resolve stale
`uv.lock` dependencies. The published wheel/sdist and all their actual members
must be checked independently; source selection never authorizes arbitrary
wheel contents or bypasses package-boundary inspection.

This boundary deliberately retains current quality policies, scripts, tests,
lockfiles and CI workflow definitions despite their exclusion from the
installed Python module. A change to these inputs can change candidate identity
without changing the product module bytes. Git revision and release approval
are distinct from the source-input fingerprint.
