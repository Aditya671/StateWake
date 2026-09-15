# External / Live-Sandbox Integrations

## Scope

The external-integration harness adds an external-integration evidence layer without turning StateWake into a
network client, webhook server, queue consumer, database manager, or external-system
orchestrator.

The current harness supports two modes:

- `--mode live`: reaches credential-free public HTTPS endpoints directly.
- `--mode fixture`: replays externally captured responses whose source and immutable
  external reference are recorded.
- `--mode ci`: runs the checked-in external captures without requiring network access.

## External references captured during this validation cycle

The GitHub connector was used to retrieve live public repository data from:

- `stripe-samples/starter`, repository metadata and `README.md`.
- `venmo/business-rules`, `README.md`.

The checked-in fixtures record the source URL, an external reference, a capture timestamp,
and a SHA-256 digest of the stored payload. Fixtures intentionally contain bounded projections,
not full external responses. The stored payload is then admitted through the public `StateWakeClient` and
cryptographically verified by the existing StateWake evidence boundary.

These captures prove a real external-source-to-StateWake ingestion path, but they are
not a substitute for repeating live network execution in a network-enabled runner.

## Live network targets

The harness defines two credential-free targets:

1. GitHub REST repository metadata for `stripe-samples/starter`.
2. NYC Open Data Socrata API, one bounded 311 record query.

The isolated artifact-validation sandbox has DNS/network access disabled. The operator separately confirmed that `--mode live` succeeds on the local network-enabled environment. This document distinguishes that local operational confirmation from the sandbox execution result.

## Failure behavior

The live fetcher has bounded response size and a timeout. Network failure, timeout,
non-JSON content, or oversized response causes the integration to fail rather than
being converted into a successful evidence result.

StateWake records the successfully captured external bytes; it does not claim that an
unreachable external system was reliable.

## Acceptance status

| Acceptance criterion | Status |
|---|---|
| External system selected | PASS |
| External reference recorded | PASS |
| Real external data captured | PASS — GitHub connector |
| Captured bytes admitted through StateWake | PASS |
| Receipt/artifact verified | PASS |
| Credential-free repeatable fixture mode | PASS |
| Live public HTTPS execution on operator network-enabled environment | PASS — locally confirmed |
| Live public HTTPS execution from this isolated artifact sandbox | BLOCKED — network disabled |
| Controlled external network failure semantics | PASS by harness contract/tests |
| No credentials committed | PASS |

The external-integration capability therefore remains **partially verified** until a network-enabled sandbox executes
`python scripts/integration/run_external_integrations.py --mode live` successfully. No production reliability claim is implied by fixture-mode success alone.
