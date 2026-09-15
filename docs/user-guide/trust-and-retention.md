# Trust, Key Management, and Retention Boundaries

StateWake does not own private signing keys, enterprise key stores, or evidence storage policy. It exposes small contracts so a host can connect its existing controls to the reliability lifecycle.

## KMS/HSM boundary

Implement `SigningProvider` with an organization's KMS, HSM, or equivalent signing service. StateWake supplies canonical bytes and receives a signature; private key material never enters the process through this contract.

`KeyLifecycleProvider` provides explicit rotation and revocation operations. Store public-key digests and trust-anchor metadata with the resulting attestation/trust state so independent verification can identify which key was authoritative.

## Retention and legal hold

Use `EvidenceRetentionRequirement` to record an artifact's retention deadline and optional legal hold. A production deployment should persist these requirements in its governance/storage system and make deletion consult `can_delete` before removing evidence.

A legal hold is an explicit blocker: ordinary retention release does not remove it. Key rotation/revocation and retention policy remain host-governed; StateWake records the evidence needed to verify the resulting reliability decision.

## Operational failure hooks

Hosts may provide a `ReliabilityFailureHook` to receive structured notifications when evidence verification or authoritative reliability-state writes fail. The hook is deliberately synchronous, small, and optional; it is not a StateWake observability pipeline or dashboard.
