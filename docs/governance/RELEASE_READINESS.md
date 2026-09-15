# Release Readiness Decision

## Decision: RELEASE-CANDIDATE PROCESS VERIFIED; PUBLIC RELEASE NOT AUTHORIZED

**Current package baseline:** `v0.1.0`  
**Current identity:** StateWake / `statewake-ai` / `statewake` / `statewake` CLI

This document describes the current release boundary. Historical release-verification snapshots are retained under `repository historyhistorical-evaluations/` and are not current release authorities.

## Current architecture

The active product is a framework-neutral reliability-evidence infrastructure layer. Its authoritative lifecycle is:

`execution → evidence → provenance → integrity → deterministic verification → reliability state → discrepancy/comparison → reconciliation/recovery → attestation/decision`

`ReliabilityEvidenceChain` is the principal composition primitive. Producer systems remain authoritative for their own execution, telemetry, orchestration, policy, and domain semantics.

## Verified local boundary

The current development baseline includes:

- canonical evidence admission and receipt verification;
- reliability-state persistence and recovery hardening;
- framework-neutral integration SDK;
- three synthetic golden reference applications;
- deterministic failure-laboratory campaigns;
- deterministic generated property/state-machine verification;
- persistent signed trust checkpoints;
- public API integration coverage;
- package and archive integrity checks.

## Remaining publication gates

The release-candidate local candidate process is executable and verified. Public publication remains blocked until the intended external environment verifies the repository's platform-specific dependency installation and GitHub server-side governance, and a human approval decision is recorded.

The WSGI adapter remains a local/internal integration boundary. Authentication, authorization, TLS termination, tenant isolation, network policy, and host filesystem controls remain deployment responsibilities.

## Claim boundary

The repository's synthetic cross-domain scenarios demonstrate reuse of the same StateWake evidence/verification mechanism across domain-shaped payloads. They do not constitute live aviation, healthcare, municipal, financial, security, or other production integrations.
