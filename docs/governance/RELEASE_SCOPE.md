# Current release-input boundary

The current source tree is distinct from archival development ZIPs and the
installed wheel. `scripts/common/release_scope.py` is the sole current-project
file selector shared by source provenance, release-candidate fingerprinting,
continuous-security snapshots and active-identity scanning.

The selected inputs include `src/`, executable `examples/`, the maintained `ui/` application source, repository tooling, build metadata and
lockfile, maintained tests and verification scripts, CI workflows, maintained
current documentation, including `docs/whitepaper/`, the release index, the
release notes selected from the canonical project version, and relevant benchmark fixtures.
Prior release notes under `docs/releases/`, research under `docs/research/`,
generated benchmark reports, root `verification/` outputs, and arbitrary
scratch files are outside this identity unless explicitly selected by the
authoritative release-scope code. Historical records may remain in the source
tree without becoming current verification requirements.

`verification_manifest.txt` is an exhaustive manifest **of selected release
inputs only**, not of the entire repository. `candidate-fingerprint.txt`
records the corresponding deterministic `source_tree_digest`. Both identity
files are excluded from their own digest. Build and lock verification remain
separate obligations: excluding historical material does not establish
`uv.lock` freshness. The published wheel/sdist and all their actual members
must be checked independently; source selection never authorizes arbitrary
wheel contents or bypasses package-boundary inspection.

This boundary deliberately retains current quality policies, scripts, tests,
lockfiles and CI workflow definitions despite their exclusion from the
installed Python module. A change to these inputs can change candidate identity
without changing the product module bytes. Git revision and release approval
are distinct from the source-input fingerprint.
## Identity generation and verification lifecycle

`verification_manifest.txt` and `candidate-fingerprint.txt` are generated identity artifacts, not hand-maintained regression expectations. Generation and verification are separate authorities: `refresh_release_identity.py` updates them explicitly, while `verify_release_identity.py` only verifies an already-materialized candidate. `run_sdlc_validation.py` calls the verifier and never refreshes identity on behalf of a failing candidate.

Dependency installation is likewise outside verification. The committed lock is checked read-only and `verify_validation_environment.py` confirms that the current interpreter matches the locked validation profile; neither command synchronizes packages. The supply-chain verifier also deliberately does **not** regenerate identity. This preserves fail-closed behavior for relying parties while ordinary unit/regression tests may exercise identity generation inside isolated temporary candidates.

The continuous-security assurance baseline is a separately governed promoted state. `verify_continuous_security_assurance.py` is read-only and may re-run Tier 4 assurance when relevant drift is detected. Promotion is performed only by `promote_security_assurance_baseline.py`, which re-verifies before writing the new baseline and proves convergence to zero drift. Because the promoted baseline is itself a maintained release input, `refresh_release_identity.py` is run explicitly **after** successful security promotion and before final release verification.

