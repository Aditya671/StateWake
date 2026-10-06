# StateWake v0.4.1 release notes

StateWake v0.4.1 is the current **published Production/Stable release on PyPI**. This record describes the source and capability changes associated with that public release. Publication status is distinct from the narrower meaning of any individual assurance verifier: a successful verifier establishes only its documented evidence boundary and does not independently authorize a future or replacement release.

## Changes since v0.4.0

- Reconciled the maintained security-assurance documentation with its deterministic Tier 6/7/11/12/13 verifier contracts and added a regression covering the full deterministic security-verifier suite.
- Added the dated v0.4.0 technical white paper in Markdown and PDF with its source map and dependency errata. The maintained white paper directory is included in the source fingerprint.
- Clarified current release status and dependency guidance across the README, user guide, integration documentation, governance documents, and security assurance pages.
- Incorporated the compatible reliability, native SDK, workspace, and release verification changes listed under v0.4.1 in the [changelog](../../../CHANGELOG.md).
- Synchronized package metadata, import version, lockfile project entry, and API contract documentation at 0.4.1. The public API contract version remains `1`.

## Version policy

Native SDK integration additions would normally meet the project's minor-release criterion. Version 0.4.1 is an explicit pre-1.0 patch-number exception retained for this published release. Future compatibility and publication gates apply to later versions or replacement artifacts.

## Qualification boundary

The published release status does not make every local verifier a publication authority. Source integrity and local verification results apply only to the exact source fingerprint they evaluate. Any future release or replacement artifact requires its own build, clean-consumer, release-workflow, platform, provenance, and human-approval evidence.
