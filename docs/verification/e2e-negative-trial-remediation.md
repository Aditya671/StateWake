# Frozen negative-trial remediation (historical validation record)

Baseline: `statewake_release_scope_clean_candidate.zip`; frozen synthetic input data: `statewake_e2e_negative_trial_pack.zip`. Both originals remain unchanged.

- **TRIAL-001**: The observed-run index accepts distinct receipts with different capture times under the same run ID and producer authority. It tracks earliest/latest *observed capture timestamps*, not an attested execution start/end. Producer identity checks and receipt conflicts remain enforced; arbitrary multi-producer run ownership is not claimed.
- **TRIAL-002**: A failed-verification fixture yields a valid `review` chain for claim-profile assessment, rather than constructing an invalid `accept` that aborts before evaluation. The explicit invalid-accept negative test remains. **Follow-up:** fault-specific detection now executes `ProvenanceGraph.validate_required_edges()` on a missing required input->output relation, or constructs a prohibited `ReliabilityStateTransition`. Intact edges and permitted transitions are negative controls. The claim profile result remains independent and satisfied in these two cases; neither result represents persisted provenance or transition-history verification.

Frozen synthetic datasets: 83/83 adapter cases, 31/31 cross-layer cases meet declared expectations. Four additional tests cover out-of-order run observations, producer conflict, and two benchmark cases. These results are not native SDK qualification, complete runtime coverage, or release promotion.

Trial records remain external to the current-project release-input scope; source regressions are within it. Dependency locking, PyNaCl, real SDK compatibility and complete release gates remain machine-dependent follow-up.

Follow-up verification: 83/83 capture and 31/31 cross-layer frozen cases met their revised explicit expectations; the two study cases now require individual domain-validator detection. Source regression controls cover intact/missing edges and legal/forbidden transitions. These tests cannot qualify unavailable optional SDKs or establish an authenticated producer.
