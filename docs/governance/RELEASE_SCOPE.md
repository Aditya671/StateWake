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

`verification_manifest.txt` and `candidate-fingerprint.txt` are generated identity artifacts, not hand-maintained regression expectations. `python scripts/release/prepare_sdlc_validation.py` is the canonical SDLC preflight: it refreshes those two derived files, verifies them immediately, checks the committed Python lock non-mutating, and runs continuous-security assurance without promotion. Direct `refresh_release_identity.py` and `verify_release_identity.py` remain available for focused maintenance and verification.

The preflight does **not** rewrite dependency locks, source/documentation, or the continuous-security baseline. The supply-chain verifier likewise deliberately does **not** regenerate identity. This preserves fail-closed behavior when a relying party verifies an already-materialized candidate. Ordinary unit/regression tests exercise identity generation in isolated temporary candidates, so a legitimate source edit does not make the entire test suite fail merely because a checked-in checksum snapshot is stale.

The continuous-security assurance baseline is different: it represents a previously promoted security state. It is never refreshed before security drift is evaluated. A changed candidate must first pass executable security re-verification; only then may `verify_continuous_security_assurance.py --promote-on-success` promote the new security baseline. Because that baseline is itself a maintained release input, the final release manifest/fingerprint are refreshed **after** successful security promotion.

