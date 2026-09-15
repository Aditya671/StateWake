# Persisted Artifact Compatibility Policy

StateWake treats persisted public artifacts as compatibility contracts. A format may evolve only through an explicit format version or an explicitly documented legacy compatibility rule.

| Artifact | Canonical status | Current format | Compatibility rule |
|---|---|---:|---|
| External evidence receipt | Active V1 | 1 (legacy unversioned accepted) | Writers emit `format_version: 1`; readers accept legacy unversioned receipts as V1. The marker is outside the hashed payload. |
| Reliability evidence chain | Active V1 | 1 (legacy unversioned accepted) | Writers emit `format_version: 1`; readers accept legacy unversioned chains. The marker is outside the hashed payload. |
| Reliability proof bundle | Active V1 | 3 | Versions 1–3 remain explicitly validated by the descriptor. |
| Reliability state transition | Active V1 | 1 | Compatibility fixtures cover the released transition shape. |
| Reliability outcome attestation | Active V1 | 1 (legacy unversioned accepted) | Writers emit `format_version: 1`; readers accept legacy unversioned attestations. The marker is outside the hashed payload. |
| Reliability decision basis | Active V1 | 1 | Version 1 is validated by the domain contract. |

## Rules

1. Readers must reject unknown explicitly versioned formats.
2. Readers may accept known legacy unversioned forms only where the legacy shape is already part of the supported baseline.
3. A writer must not silently reinterpret an older artifact as a newer artifact.
4. Any format change requires a fixture representing the old form and a regression test proving it remains readable, or a documented major/minor compatibility decision.
5. Artifact digests remain over the canonical payload defined by each artifact contract; serialization metadata such as `format_version` is deliberately outside the hashed payload.
6. Writers emit the current explicit `format_version`; readers may accept a legacy unversioned form only where this table explicitly permits it.

The current baseline deliberately does **not** retrofit a new field into already hashed receipt/chain payloads, because doing so would invalidate existing digests. The next format-changing release must introduce an explicit migration/version envelope rather than silently changing canonical bytes.
