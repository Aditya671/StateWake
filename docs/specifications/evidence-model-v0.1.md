> **Specification classification:** Active V1 specification.
>

# Evidence Model v0.1

An `EvidenceItem` references decision-supporting material without requiring sensitive
content to live in the manifest. Each item must have a source and either a digest or a
content reference. `EvidenceManifest` binds unique evidence IDs to a run.

Opaque content can be stored locally using the content-addressed artifact store. The
store places bytes under their SHA-256 digest and verifies the digest again on retrieval.
