# Release Governance Contract

Python 3.14 is deliberately outside the StateWake v0.4.0 compatibility matrix.

This document defines the repository-side release gates for the next StateWake public developer package. It intentionally does not authorize a release; publication remains a separate approval decision.

## Main and protected changes

`main` is the integration branch. Changes intended for release must pass the CI workflow, which validates the lockfile, Python 3.11/3.12/3.13 compatibility, static compilation, the active test suites, CLI smoke, example validation, and package build.

Repository branch protection and release-tag protection are GitHub repository settings rather than source artifacts. Before the next publication, the repository owner must verify that required CI checks are enforced on `main` and that release tags cannot bypass the intended release workflow.

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

A successful workflow does not by itself authorize publication. The publication decision must identify the exact tested artifact, source commit, verification result, and any known caveats.

The `Development Status :: 5 - Production/Stable` classifier describes package maturity; it is not a certification of every host deployment. The WSGI adapter remains a thin trusted integration edge; internet-facing authentication, authorization, TLS termination, tenant isolation, rate limiting, and remote object ingestion remain host/application concerns.
