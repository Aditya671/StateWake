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

The release SDLC includes `public-trial-regressions` after external fixture validation and before release-candidate qualification. The SDLC uses source mode; real native-SDK/public-host qualification remains a separate environment-dependent gate and must not be inferred from source-mode success.
