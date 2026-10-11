# StateWake Software Development Lifecycle

## 1. Purpose

StateWake uses a traceable, evidence-driven SDLC. Every change must move through explicit engineering gates before it can become part of the canonical baseline or a public release.

The workflow is:

```text
PLAN → DESIGN → IMPLEMENT → VERIFY → HARDEN → RELEASE → OPERATE → LEARN
  ↑                                                            │
  └────────────────────── feedback / defects ─────────────────┘
```

The lifecycle is deliberately implementation-first and evidence-first. Historical phase numbers do not authorize new work.

## 2. Plan

Before implementation:

- define the problem and user-visible outcome;
- identify the affected product boundary;
- identify compatibility and security implications;
- locate existing and historical implementations;
- select the smallest valid change;
- define acceptance criteria and regression coverage.

A change is not planned by inventing a new implementation when a verified existing implementation can be restored or corrected.

## 3. Design

The design review must identify:

- domain and architectural boundaries;
- public API impact;
- persistence and compatibility impact;
- failure modes and recovery behavior;
- security and privacy impact;
- operational and deployment impact;
- documentation and migration impact.

Material architectural changes require an ADR.

## 4. Implement

Implementation rules:

1. preserve runtime semantics unless the change explicitly requires behavior change;
2. keep framework and transport concerns at adapters;
3. keep public API additions intentional and tested;
4. use deterministic software before model-dependent behavior;
5. avoid diagnostic suppressions and convenience workarounds;
6. keep runtime data outside source-controlled code;
7. make filesystem, process, and network behavior portable across supported platforms.

## 5. Verify

SDLC verification is intentionally read-only with respect to maintained candidate state. `run_sdlc_validation.py` checks `uv.lock` with `uv lock --check`, verifies that the current interpreter already contains the exact locked `dev` + `integrations` validation profile, verifies persisted release identity, and evaluates continuous-security assurance without promoting any baseline. Dependency installation, security-baseline promotion, and release-identity refresh are explicit maintenance actions outside the verifier.

Verification proceeds from cheapest deterministic checks to broader system checks:

1. formatting and linting;
2. strict type checking;
3. source compilation;
4. unit and contract tests;
5. integration tests;
6. public API and CLI smoke tests;
7. documentation/example verification;
8. persistence and recovery tests;
9. adversarial, chaos, property, and failure-lab validation;
10. external integration fixtures;
11. package build and clean-consumer installation;
12. release provenance and governance checks.

A missing tool or unavailable environment is recorded as **not verified**, never silently converted into a pass.

### CI execution ownership

Ordinary pull-request CI does not call the monolithic SDLC coordinator inside every OS/Python matrix cell. The four stable required checks own distinct concerns: static/repository quality, one full Linux behavioral run, focused Windows portability, and one package build. The SDLC coordinator remains the local/release orchestration surface, while Release Verification is the only workflow that runs the complete release profile.

Release Verification builds distributions once after the release profile passes. All consumer, workspace, integration, dependency-audit, SBOM, and provenance jobs consume those exact immutable artifacts, and every release-verification job has an explicit execution timeout. Publication resolves and downloads a successful Release Verification run for the exact source revision and therefore never rebuilds or substitutes a later checkout. Production release publication uses a bounded resolver so a release event cannot race an in-progress verification run; manual TestPyPI requires the exact successful run ID.

## 6. Harden

Security and reliability review covers:

- evidence integrity;
- provenance and identity binding;
- replay/idempotency;
- state corruption;
- archive safety;
- persistence durability;
- attestation authenticity;
- trust-anchor handling;
- HTTP boundaries;
- privacy;
- key material;
- availability;
- dependency/supply-chain risk.

The documented threat model remains the authority for deployment-owned residual risk.

## 7. Release

A release candidate must satisfy the release protocol, package identity, compatibility, product experience, source compilation, build, package boundary, provenance, and human approval gates.

A successful automated candidate check **does not authorize publication**. Human release approval remains mandatory.

## 8. Operate

Production operators own deployment controls such as TLS termination, authentication, authorization, host hardening, storage isolation, backups, retention, and network policy.

StateWake records reliability evidence and recovery state; it does not replace those deployment controls.

## 9. Learn

Defects become evidence for improving the system:

- reproduce the defect;
- identify the broken invariant;
- fix the source of the defect;
- add regression coverage;
- rerun affected and broader gates;
- document the architectural or operational lesson when material.

The canonical baseline is promoted only from a verified artifact.


### Frozen public-trial regressions

The release SDLC includes `public-trial-regressions` after external fixture validation and before release-candidate qualification. The SDLC uses source mode; real native-SDK/public-host qualification remains a separate environment-dependent gate and must not be inferred from source-mode success. Native qualification reuses the same coordinator in `--mode qualification`, records the installed integration versions, and requires the dedicated real-SDK probes documented in `docs/testing/NATIVE_INTEGRATION_QUALIFICATION.md`.

## Validation environment preparation

Environment creation is explicit and separate from verification. Run `uv sync --locked --group dev --extra integrations` (or `make sync`) when the validation environment needs to be created or updated. `run_sdlc_validation.py` never performs a sync. It verifies lock freshness with `uv lock --check` and then `verify_validation_environment.py` confirms that every required validation distribution is installed at a version present in the committed `uv.lock`. Individual gates execute with that already-prepared interpreter.

A source change may legitimately stale generated release identity or the promoted security baseline. Those states are not repaired by verification. Use the explicit refresh/promotion commands only after reviewing the candidate, then rerun verification against the materialized state.
