# Release Governance Contract

Python 3.14 is deliberately outside the current StateWake v0.5.1 source compatibility matrix; supported Python remains 3.11, 3.12, and 3.13.

This document defines the repository-side release gates for the next StateWake public developer package. It intentionally does not authorize a release; publication remains a separate approval decision.

## Main and protected changes

`main` is the integration branch. Required pull-request verification is intentionally split into four stable checks instead of one OS/Python mega-matrix:

- `quality` — lock/environment identity, release/repository identity, Ruff, strict mypy, compilation, and zero-drift security assurance on Ubuntu 24.04 / Python 3.13;
- `tests-linux` — the full behavioral suite plus product/CLI executable verification once on Ubuntu 24.04 / Python 3.13;
- `portability-windows` — focused Windows filesystem, archive, containment, SQLite, backup/recovery, and failure-lab regressions on Windows Server 2025 / Python 3.13;
- `package` — one source-independent distribution build and package-boundary verification after the other required checks pass.

Python 3.11/3.12/3.13 and Linux/Windows consumer compatibility is established against the **exact built release wheel** in the Release Verification workflow rather than by rerunning the complete source suite in every PR matrix cell. Repository branch protection and release-tag protection are GitHub repository settings rather than source artifacts. Before publication, the repository owner must require exactly the four stable CI contexts above on `main` and ensure release tags cannot bypass the intended release workflow.

## Release verification

The release workflow builds the wheel and source distribution once. The resulting distribution directory is the release evidence set. The workflow then:

1. records SHA-256 checksums;
2. installs the exact built wheel in clean Python 3.11/3.12/3.13 consumers;
3. exercises supported public imports and the CLI;
4. runs dependency auditing against the installed wheel and its declared dependencies;
5. produces a CycloneDX JSON SBOM;
6. records GitHub build provenance attestation for the built distributions.

The dependency audit and SBOM are uploaded as machine-readable workflow artifacts; they are not treated as claims that can be reconstructed later from an unrecorded local environment.

## Publication boundary

A successful verification workflow does not by itself authorize publication. The publication workflow first resolves the exact successful Release Verification run; a production release may wait only within a bounded timeout, and manual TestPyPI must name the run ID explicitly. A non-OIDC preparation job then creates a canonical `ReleasePublicationBasis` identifying the exact tested distributions, target registry, source revision/tree identity, verification evidence, and caveats. Publication approval is durable `HumanApprovalContract` evidence over that exact basis, and the preparation job resolves the approval lifecycle and issues a fresh execution permit before uploading one immutable publication-ready bundle. Revocation, supersession, changed bytes, changed verification evidence, or changed target fails closed. The protected OIDC job does not execute StateWake source logic: it downloads the prepared distributions and invokes Trusted Publishing.

After the external publish action succeeds, a distinct reconciliation job reads the official registry release record and public distribution bytes. StateWake records `release_published: true` only through a canonical `RegistryPublicationReceipt` whose basis digest, permit digest, artifact set, sizes, and SHA-256 values all reconcile exactly. The post-publication job has no OIDC publication permission and cannot substitute a successful workflow step for registry read-back evidence. A continuing append-only registry lifecycle then records later `available`, `yanked`, `partially_available`, or `unavailable` observations against that immutable receipt. Missing individual files are reported explicitly without inferring deletion actor or cause; yank/unyank never rewrites the original publication receipt.

The `Development Status :: 5 - Production/Stable` classifier describes package maturity; it is not a certification of every host deployment. The WSGI adapter remains a thin trusted integration edge; internet-facing authentication, authorization, TLS termination, tenant isolation, rate limiting, and remote object ingestion remain host/application concerns.
