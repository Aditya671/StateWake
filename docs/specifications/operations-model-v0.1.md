> **Specification classification:** Active V1 specification.
>

# Operations Model v0.1

## Purpose

Reliability Operations packages verified lifecycle artifacts into a reproducible, inspectable handoff without creating a second reliability engine.

## Operational bundle

A bundle contains a canonical manifest plus explicitly selected artifacts. Each artifact records:

- stable identifier;
- source path within the bundle specification root;
- artifact kind;
- SHA-256 digest;
- byte size;
- evidence sensitivity;
- `derived_from` provenance references.

The bundle and manifest identifiers are SHA-256 values over their canonical manifest payloads. A `pending` identifier may be used when authoring a bundle spec; the builder derives the final identifiers deterministically.

## Integrity

Bundle verification checks:

1. manifest presence and schema;
2. manifest identifier;
3. bundle identifier;
4. exact artifact membership;
5. artifact byte size;
6. artifact SHA-256 digest;
7. provenance references.

The ZIP writer uses sorted members, fixed timestamps and a fixed compression configuration to make equivalent inputs produce reproducible archives.

## Retention

Retention is an explicit, deterministic lifecycle decision over a verified bundle. A policy may define a maximum age and a sensitivity ceiling. The default operation is planning/inspection; the engine does not delete artifacts implicitly.

## Privacy

Operational packages reuse the sensitivity classifications introduced by the sensitivity-governance model. A retention ceiling above the allowed sensitivity produces a quarantine decision instead of silent retention or deletion.

## Scope boundary

This phase does not introduce a database-backed control plane, object-store SDK, scheduler, or destructive garbage collector. Hosts may build those adapters later around the deterministic manifest and verification boundary.
