# Project Plan

## Current objective

Maintain a coherent, verifiable reliability infrastructure layer for AI systems across evidence, cybersecurity, persistence, dataset access, and operational boundaries.

## Current baseline

**StateWake v0.5.1** is the approved current source release candidate. **v0.4.1** remains the current published Production/Stable PyPI release until v0.5.1 completes its release and publication gates. The historical GitHub v0.5.0 tag/release remains immutable at its original source revision.

The completed release sequence is:

1. **v0.1.1** — Production/Stable packaging promotion.
2. **v0.2.0** — cybersecurity completion through V3 Tier 15.
3. **v0.4.0** — Persistence & Dataset Architecture completion through Tier 15.
4. **v0.4.1** — current published Production/Stable reliability and integration update.
5. **v0.5.0** — historical GitHub release/tag for the operational-trust and publication-lifecycle capability line; not reused by the current candidate.
6. **v0.5.1** — approved current patch candidate carrying the cumulative v0.5.0 capability line plus deterministic test/SDLC cleanup, CI/release orchestration hardening, cross-platform reliability fixes, production activation controls, and version-accurate registry identity; not yet published to PyPI.

## Maintenance priorities

1. Preserve deterministic verification and evidence integrity.
2. Preserve provenance, lineage, state-history, and recovery explainability.
3. Preserve the completed cybersecurity trust boundaries.
4. Preserve durable workspace, query, dataset, export, analytical, and lifecycle semantics.
5. Keep framework, database, and optional analytical technologies at adapter boundaries.
6. Keep the public Python API small and stable.
7. Derive future work only from demonstrated architecture gaps or adopter requirements.

## Release discipline

Every release candidate must be verified against its exact source identity, synchronized version sources, compatibility evidence, security evidence, package boundary, documentation, and applicable external gates.
