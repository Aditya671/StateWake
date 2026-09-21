# v0.1.1 Release Candidate — Change Manifest

Base source: StateWake canonical baseline `8a208e3c9cd07225e7de91e8686af79bf081b4b5` / v0.1.0.

Intent: promote the existing verified public package baseline to Production/Stable without changing the public API contract.

Changed release-authority files:

- `pyproject.toml` — version `0.1.1`; classifier `Development Status :: 5 - Production/Stable`.
- `src/statewake/__init__.py` — `__version__ = "0.1.1"`.
- `uv.lock` — project package version `0.1.1`.
- `CHANGELOG.md` — v0.1.1 production/stable promotion entry.
- `README.md` — active package version/install example updated.
- `docs/governance/VERSIONING.md` — current release authority updated.
- `docs/governance/RELEASE_READINESS.md` — current baseline updated.
- `docs/governance/ROADMAP.md` — current baseline label updated.
- `docs/governance/PROJECT_PLAN.md` — current baseline updated.
- `docs/reference/API_CONTRACT.md` and `docs/reference/api-contract.json` — package version updated; contract version remains `1`.
- `docs/security/THREAT_MODEL.md`, `docs/user-guide/release.md`, `docs/user-guide/limitations.md` — active current-version references updated.
- `scripts/release/verify_versioning.py` and `scripts/release/verify_release_candidate.py` — executable release gates updated to expect `0.1.1`.

No application/runtime implementation modules were changed for this promotion.
