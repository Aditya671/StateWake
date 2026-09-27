# StateWake v0.4.1 release notes (source candidate)

This document describes the v0.4.1 source candidate. It is not evidence that a v0.4.1 wheel, source distribution, GitHub release, or PyPI release has been published. The last recorded public release is v0.4.0.

## Changes since v0.4.0

- Added the dated v0.4.0 technical white paper in Markdown and PDF with its source map and dependency errata. The maintained white paper directory is included in the source fingerprint.
- Clarified current release status and dependency guidance across the README, user guide, integration documentation, governance documents, and security assurance pages.
- Incorporated the compatible reliability, native SDK, workspace, and release verification changes listed under v0.4.1 in the [changelog](../../../CHANGELOG.md).
- Synchronized package metadata, import version, lockfile project entry, and API contract documentation at 0.4.1. The public API contract version remains `1`.

## Version policy

Native SDK integration additions in this candidate would normally meet the project's minor-release criterion. Version 0.4.1 is an explicit pre-1.0 patch-number exception requested for this source candidate; its compatibility and publication gates still apply.

## Qualification boundary

Source integrity and local verification results apply only to the exact source fingerprint recorded in `candidate-fingerprint.txt`. A future published distribution requires build, clean consumer, release workflow, platform, and human approval evidence for that artifact.
