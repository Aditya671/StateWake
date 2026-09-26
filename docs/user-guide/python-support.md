# Python support policy

StateWake v0.4.0 supports CPython **3.11, 3.12, and 3.13**.

The authoritative package metadata is:

```text
Requires-Python: >=3.11,<3.14
```

Python 3.14 is intentionally **outside the v0.4.0 supported runtime range**. A
forced wheel installation or an import that happens to succeed on Python 3.14
does not establish compatibility and must not be reported as supported.

## Why 3.14 is not enabled by metadata alone

StateWake treats interpreter support as a release qualification claim, not a
syntax claim. Adding Python 3.14 requires a fresh candidate to pass the same
clean-environment gates used for every supported interpreter, including:

- dependency resolution and lock consistency;
- static quality and compilation gates;
- full project and release regression suites;
- real native-SDK import and behavior tests for advertised integrations;
- wheel and source-distribution build and package-boundary verification;
- clean wheel consumer import and CLI checks;
- `pip check`/resolver consistency for the installed artifact;
- provenance and release-input verification.

Until those gates are completed on Python 3.14, `requires-python` must remain
`>=3.11,<3.14` and the 3.14 classifier must remain absent.

## Host applications that require Python 3.14

A host whose own package metadata requires Python 3.14 or newer is outside the StateWake v0.4.0 compatibility matrix. Do not bypass the StateWake
`Requires-Python` boundary and interpret a successful forced import as support.

The 2026-09-25 public-repository trial encountered exactly this boundary with
the pinned FastAPI Full Stack Template revision: the host required Python 3.14,
while the StateWake v0.4.0 wheel declared `<3.14`. The host route smoke remains
useful host evidence, but it is not a StateWake compatibility result.

## Future Python 3.14 qualification

Python 3.14 support can be added in a later candidate only by widening the
metadata *after* the 3.14 qualification matrix is green. The change must update
together:

- `pyproject.toml` `requires-python` and classifiers;
- CI and release consumer matrices;
- lockfile/resolved dependency evidence;
- current compatibility documentation;
- release and package-policy regression tests.

This policy prevents interpreter support from being inferred from import
success alone.
