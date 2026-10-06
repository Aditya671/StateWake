# Data Governance, Retention, Disclosure & Deletion Investigation

StateWake exposes an optional **read-only lifecycle investigation** for one workspace-controlled record or export. It reuses the existing `DataLifecyclePolicy`, `assess_data_lifecycle()`, durable workspace retention row, legal-hold state, and payload-free `DeletionRecord` authorities.

It does not create a second lifecycle database, delete data, disclose data, alter legal hold, or certify host confidentiality controls.

## Configuration

The read API uses the existing workspace root plus one explicit lifecycle context artifact:

```powershell
$env:STATEWAKE_UI_WORKSPACE_ROOT = "C:\path\to\existing\statewake-workspace"
$env:STATEWAKE_UI_DATA_LIFECYCLE_CONTEXT = "C:\path\to\data-lifecycle-context.json"
# Optional: effective runtime privacy/evidence-governance evidence
$env:STATEWAKE_UI_PRIVACY_GOVERNANCE_SNAPSHOT = "C:\path\to\privacy-governance-runtime.json"
```

The endpoint is:

```text
GET /api/v1/data-governance
```

The browser page is:

```text
/data-governance
```

The endpoint accepts **no query parameters**. Browser-supplied filesystem paths are not supported.

The privacy/evidence-governance snapshot is optional. When absent, the browser reports that runtime policy enforcement was **not observed** and does not infer repository defaults. When present, the read API strictly validates its shape, digest, symlink boundary, and configured byte ceiling before projecting a privacy-safe summary.

## Why an explicit lifecycle context exists

The workspace schema deliberately persists only the lifecycle metadata required for durable enforcement:

- `object_id`;
- `policy_id`;
- sensitivity;
- `retain_until`;
- legal-hold state;
- payload-free deletion tombstones.

It does **not** persist a full `DataLifecyclePolicy` snapshot containing purpose, storage/telemetry/disclosure ceilings, or deployment confidentiality requirements. The investigation therefore consumes one explicit bounded policy-context JSON artifact and cross-checks that artifact against the existing durable workspace state instead of inventing missing policy fields from the database.

This artifact is an investigation input, not a new canonical lifecycle store.

## Context format

Schema version:

```text
data-lifecycle-context.v1
```

Representative record context:

```json
{
  "schema_version": "data-lifecycle-context.v1",
  "object_kind": "workspace-record",
  "object_id": "<workspace record id>",
  "sensitivity": "internal",
  "created_at": "2026-09-30T00:00:00+00:00",
  "legal_hold": false,
  "policy": {
    "policy_id": "governance-1",
    "purpose": "reliability-evidence-retention",
    "max_retention_days": 30,
    "storage_max_sensitivity": "restricted",
    "telemetry_max_sensitivity": "internal",
    "disclosure_max_sensitivity": "internal",
    "encryption_at_rest_required": true,
    "tls_required": true
  },
  "recorded_decision": null
}
```

For a workspace export, use:

```text
object_kind = "workspace-export"
object_id   = "export:<export_id>"
```

A recorded deterministic decision may optionally be supplied as:

```json
{
  "recorded_decision": {
    "evaluated_at": "2026-10-31T00:00:00+00:00",
    "decision": {
      "object_id": "<same exact object id>",
      "sensitivity": "internal",
      "policy_id": "governance-1",
      "retain_until": "2026-10-30T00:00:00+00:00",
      "expired": true,
      "storage_allowed": true,
      "telemetry_allowed": true,
      "disclosure_allowed": true,
      "deletion_allowed": true,
      "reasons": []
    }
  }
}
```

The server does not trust that decision merely because it is well formed. It replays `assess_data_lifecycle()` at the recorded evaluation timestamp and requires exact equality.

## Verification sequence

Before returning the browser projection, StateWake verifies:

1. the context file is not a symlink and stays within the configured byte ceiling;
2. the file is strict UTF-8 JSON with no unsupported fields or scalar coercion;
3. timestamps are timezone-aware;
4. the full `DataLifecyclePolicy` is valid under the existing domain contract;
5. any recorded decision exactly matches deterministic policy replay;
6. the workspace opens through the existing read-only SQLite boundary;
7. the configured object exists as the named workspace record/export;
8. the context creation time and sensitivity agree with durable workspace state;
9. the durable retention row exists;
10. durable policy identity, sensitivity, legal-hold state and retention deadline agree with the context policy;
11. any deletion tombstone binds the same object, policy, sensitivity and original digest;
12. a deletion tombstone with a finite retention deadline was not recorded before that deadline.

Any mismatch fails the endpoint closed with `INVALID_DATA_GOVERNANCE_SOURCE`.

## Runtime privacy and evidence-governance evidence

When `STATEWAKE_UI_PRIVACY_GOVERNANCE_SNAPSHOT` is configured, the existing Data Governance page additionally shows:

- the digest of the observed effective runtime policy;
- privacy-policy identity plus redaction-key/rule counts;
- evidence-governance policy identity and storage/telemetry sensitivity ceilings;
- sensitivities requiring digests;
- whether pre-receipt metadata redaction, pre-write storage governance, and workspace sensitivity indexing are part of the recorded runtime contract; and
- whether telemetry manifest projection is supported.

Regex patterns, replacement values, artifact bytes, arbitrary metadata, local snapshot paths, and secrets are not sent to the browser. The projection explicitly records that opaque content secret scanning is not performed and that a live OpenTelemetry runtime binding is not established merely by the policy snapshot.

## Interpretation boundary

The response separates:

```text
storage eligibility
telemetry eligibility
disclosure eligibility
retention expiry
legal hold
deletion eligibility
deletion history
```

These are not interchangeable.

In particular:

```text
expired ≠ deletion permitted while legal hold is active

deletion eligible ≠ deletion executed

deletion tombstone ≠ proof every external copy was erased

encryption_at_rest_required ≠ host encryption verified

tls_required ≠ live TLS verified
```

The operator surface never performs deletion, export, disclosure, migration, retention release, or legal-hold modification.

## Privacy boundary

The browser receives a SHA-256 digest of the workspace object identity rather than the raw object ID. Local source paths, export paths, raw query definitions, payload bytes and arbitrary metadata remain outside the projection.

A deletion tombstone may expose its original content digest, policy identity, sensitivity, deletion timestamp and recorded reason because those are the canonical payload-free historical fields. The tombstone itself does not contain deleted content.
