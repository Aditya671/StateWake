# External Capture Integrity Audit — 2026-09-14

## Finding

The checked-in external capture files contain bounded projections of externally retrieved
content. They must not claim to contain the exact full external response.

## Correction

Each fixture now declares:

- `capture_kind = bounded_projection`;
- `reference_kind`;
- `capture_scope`;
- `content_sha256`.

Fixture loading verifies the SHA-256 digest before admission. The live harness likewise
binds the captured bytes to a SHA-256 digest and distinguishes HTTP observation references
from immutable source-version identifiers.

This preserves useful external evidence without storing unnecessary third-party source
material or overstating what the fixture proves.
