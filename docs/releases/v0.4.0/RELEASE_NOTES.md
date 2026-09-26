# StateWake v0.4.0

This release record describes the original v0.4.0 promotion snapshot. The current package maturity is `Development Status :: 5 - Production/Stable`; historical gate results below apply to that snapshot.

## Release boundary

v0.4.0 is the completed StateWake AI Systems Seven-Phase Roadmap release.

This release promotes StateWake into a broader reliability-evidence infrastructure baseline for stateful AI systems. It keeps the public API contract version at `1` while adding backward-compatible evidence contracts, claim profiles, human reports, workspace guarantees, producer integrations, release-trust evidence, and comparative validation study support.

## Included capabilities

1. **AI Evidence Contracts** — digest-bound, deterministic contracts for prompts, model invocations, tool calls, retrieval, policy decisions, evaluator outputs, human approvals, and runtime traces.
2. **Built-In Claim Profiles** — eight versioned AI reliability claim profiles with deterministic evaluation and missing-evidence reporting.
3. **Human Verification Reports** — Markdown and JSON reports that preserve candidate identity, evidence, omitted/missing evidence, check states, caveats, residual risks, and human decisions.
4. **Workspace Guarantees** — durable default workspace, backup/restore, integrity sweep, migration markers, and explicit workspace tests.
5. **First-Class Producer Integrations** — thin, optional-dependency producer adapters for OpenTelemetry GenAI, OpenAI Agents-style traces, LangGraph, LlamaIndex, LangChain, CI/CD, and evaluator events.
6. **Release Trust Evidence** — digest-bound release-trust bundles for artifacts, source identity, build provenance, tests, SBOM/scans, signatures/limitations, and human release decisions.
7. **Comparative Validation Study** — deterministic fixture-backed workloads, fault injections, metrics, and reports comparing final-output-only, conventional logs, structured traces, and StateWake-full evidence.

## Explicit boundaries

- StateWake still does not run, judge, orchestrate, or host AI systems.
- Integrations are producer adapters; optional frameworks are not hard runtime dependencies.
- Reports distinguish verification from release/publication approval.
- Unsigned or environment-limited evidence is recorded as a limitation, not a pass.
- The comparative validation study is fixture-backed and does not claim general statistical superiority beyond tested workloads.

## Verification summary

The original promotion snapshot recorded compilation, module import walk, selected unit/workspace/benchmark/release/security tests, package build, package-boundary verification, manifest regeneration, and cache-free packaging. Ruff, mypy, the full PyNaCl-backed cryptographic suite, and dependency synchronization were not recorded as completed in that snapshot.
