# Testing and Validation

StateWake testing is layered:

1. unit and contract tests;
2. integration tests;
3. public product-experience tests;
4. persistence/recovery tests;
5. property/state-machine validation;
6. real-world synthetic scenarios;
7. independent-oracle real-system trial evidence and analysis;
8. chaos and deep-chaos campaigns;
9. extreme and failure-lab campaigns;
10. external integration fixtures;
11. clean-consumer/package validation.

Use the quality-gate definitions in [`../QUALITY_GATES.md`](../QUALITY_GATES.md) and the SDLC in [`../SDLC.md`](../SDLC.md) to select the required scope for a change.

The real-system trial evidence harness is documented in [`REAL_SYSTEM_VALIDATION_HARNESS.md`](REAL_SYSTEM_VALIDATION_HARNESS.md). It keeps host truth separate from StateWake observations and writes generated campaign evidence outside the release source tree.

Real framework-SDK qualification is documented in [`NATIVE_INTEGRATION_QUALIFICATION.md`](NATIVE_INTEGRATION_QUALIFICATION.md). It reuses the frozen public-trial coordinator, records exact installed SDK versions, and requires dedicated real-SDK probes rather than treating source-mode success as native compatibility.
Historical v0.1.0 campaign reports are preserved under [`../releases/v0.1.0/validation/`](../releases/v0.1.0/validation/README.md) so old observed counts and sandbox limits are not mistaken for current gate status.
