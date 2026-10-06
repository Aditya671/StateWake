# Canonical Registry Publication Receipt & Post-Publication Reconciliation

StateWake keeps four different release statements separate:

```text
release candidate verified
    -> human publication authorization active
    -> publication execution permitted
    -> registry publication independently observed and reconciled
```

A successful external upload action is not itself StateWake proof that a registry now serves the authorized bytes. Post-publication reconciliation therefore reads the official release-specific registry API, validates the exact published file set, downloads every public distribution, re-hashes those bytes, and binds the result to both the canonical `ReleasePublicationBasis` and the exact `PublicationExecutionPermit`.

## Canonical receipt

`RegistryPublicationReceipt` records:

- publication-basis digest;
- publication-permit digest;
- target registry (`pypi` or `testpypi`);
- package distribution and version;
- official registry release API URL;
- observation timestamp;
- exact published filename, size, SHA-256, package type, upload time, yanked state, and public download URL for every authorized distribution.

The receipt is emitted only when the registry metadata contains exactly the authorized artifact set, every registry-reported size/SHA-256 matches the publication basis, no file is yanked, and independently downloaded public bytes match the same size/SHA-256 values. Missing, extra, duplicate, changed, yanked, malformed, or unreadable files fail closed.

The receipt is immutable and digest-bound. It does not mutate the prior execution permit. The permit continues to mean only that execution was authorized; the registry receipt is the separate evidence that publication was observed afterward.

## External registry boundary

PyPI and TestPyPI reconciliation use the release-specific JSON API:

```text
https://pypi.org/pypi/<distribution>/<version>/json
https://test.pypi.org/pypi/<distribution>/<version>/json
```

Registry artifact URLs must use HTTPS and the Python package CDN. StateWake does not accept an arbitrary registry endpoint supplied by callers for this capability.

`.github/workflows/python-publish.yml` performs reconciliation in a distinct post-publication job. That job does not receive `id-token: write`; it downloads the canonical basis/permit evidence, independently reads the target registry, writes `registry-publication-receipt.json`, and uploads that receipt as retained workflow evidence.

## Operator projection

The release-trust read API may be configured with the exact publication permit and registry receipt in addition to the existing publication basis/approval workspace. The read API verifies that the receipt is bound to the same basis and permit before projecting `release_published: true`.

The browser surface remains read-only. It displays authorization and registry reconciliation separately and cannot publish, authorize, revoke, issue a permit, or manufacture a registry receipt.

## Non-claims

A valid registry receipt proves only that, at the recorded observation time, the official registry API and public download bytes matched the exact authorized StateWake release artifacts. It does not independently authenticate the human approver or registry operator, establish the correctness of PyPI infrastructure, or guarantee future availability, unyanked state, or immutability after that observation.
## Continuing registry lifecycle

The initial `RegistryPublicationReceipt` remains immutable. StateWake records later registry state in an append-only `RegistryPublicationLifecycleObservation` chain whose first predecessor is the publication-receipt digest and whose later predecessors are the prior observation digests.

Lifecycle status is deliberately observational:

- `available` — the release endpoint is present, the complete originally authorized file set is present, no file is yanked, and all current public bytes were re-read and verified;
- `yanked` — the complete file set remains present and byte-verified, but the registry reports the release files as yanked. A later `available` observation records an unyank without rewriting history;
- `partially_available` — the release endpoint remains present but one or more originally authorized files are absent. StateWake records the exact missing filenames and verifies every file that remains, but does not infer who removed a file or why;
- `unavailable` — the release-specific registry endpoint returned HTTP 404. StateWake records that observation without relabeling it as a deliberate deletion, withdrawal, or actor-attributed event.

For PyPI/TestPyPI, mixed yanked state across files is rejected because current PyPI yank/unyank operations apply to a release rather than providing an independent supported per-file yank workflow. Permanent individual-file deletion is a different registry operation and is represented by `partially_available`, not by `yanked`.

The canonical JSONL history is append-only, file-locked, digest-chained, bounded, symlink-rejecting, and idempotent only for an exact repeated tail observation. The read-only operational-trust projection may display the current state and history, but it cannot yank, unyank, delete, restore, or otherwise mutate the registry.

