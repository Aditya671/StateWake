# CLI Reference

The command-line executable is `statewake`.

```bash
statewake --help
statewake version
```

The CLI is a thin operational interface over the same domain and service authorities used by the library.

## Discover commands

Use:

```bash
statewake --help
statewake <command> --help
```

## Design rule

The CLI is not the architecture authority. New product behavior must first have a justified domain/service boundary and tests. CLI exposure follows the stable integration model rather than defining it.


## Supported commands

The following command names are part of the current CLI surface:

```text
version
evidence-ingest
evidence-verify
evidence-admission-verify
reliability-comparison
reliability-comparison-verify
evidence-chain
reliability-state-transition
reliability-state
reliability-attest
reliability-attest-verify
reliability-outcome-verify
reliability-recovery-verify
reliability-lineage-verify
reliability-reconciliation-bind
reliability-reconciliation-verify
reliability-proof-bundle
reliability-proof-verify
reliability-proof-completeness-verify
reliability-decision-basis-build
release-proof
```

Command names are compatibility-sensitive. New commands are additive; removal or
renaming requires a breaking-version decision. Flag additions are normally
backward-compatible. Exact human-readable help and error text are not frozen.
