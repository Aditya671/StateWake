# Incident & Recovery Investigation

StateWake exposes an optional **read-only incident investigation surface** over its existing security-incident evidence authority. The feature does not introduce a new incident database, ticketing workflow, remediation engine, rollback controller, or causality model.

## Authority

The source of truth is the existing `JsonlIncidentEvidenceStore` and `SecurityIncidentEvidence` model:

```text
hash-linked incident JSONL store
  -> canonical record parser + digest/sequence verification
  -> deterministic incident grouping
  -> bounded incident-investigation projection
  -> GET-only read API
  -> incident portfolio / detail UI
```

The lifecycle vocabulary remains:

```text
Detect -> Preserve -> Contain -> Assess -> Recover -> Re-verify
```

A later lifecycle state does not erase earlier observations. `recovered` and `reverified` are intentionally different states. Timestamps establish observation order, not causality.

## Configuration

The incident store is server-configured. The browser cannot supply a path.

```powershell
$env:STATEWAKE_UI_WORKSPACE_ROOT = "C:\path\to\existing\statewake-workspace"
$env:STATEWAKE_UI_INCIDENT_EVIDENCE = "C:\path\to\incident-evidence.jsonl"
python -m statewake.read_api
```

If `STATEWAKE_UI_INCIDENT_EVIDENCE` is absent, `/api/v1/incidents` returns `INCIDENT_SOURCE_NOT_CONFIGURED` and the UI displays an unavailable/configuration state.

## Read-only integrity boundary

The read API does not call `JsonlIncidentEvidenceStore.read()` because the writer-oriented store acquires a file lock. Instead, the adapter exposes `read_incident_evidence_snapshot(...)`, which reuses the same canonical record parser while opening the configured source read-only and creating no lock file.

Before any incident is shown, the complete configured snapshot must satisfy:

- UTF-8 and JSONL parsing;
- supported incident format version;
- deterministic incident digest verification;
- hash-linked storage digest continuity;
- contiguous global sequence numbers;
- configured byte and record ceilings;
- non-regressing lifecycle status and observation time for each incident identity;
- immutable incident event context for repeated observations of the same incident.

Any violation fails the source closed. StateWake does not silently omit a broken record to produce a cleaner incident portfolio.

## Routes

```text
GET /api/v1/incidents
GET /api/v1/incidents/{incident_id}
```

The collection accepts only:

```text
status
category
q
limit
offset
```

`status` must be one of the canonical lifecycle states. `category` is an exact recorded category match. `q` is a bounded case-insensitive substring match over incident ID, event ID, actor, category, and status. `limit` is bounded to 1–200. Duplicate and unknown parameters are rejected.

Responses use deterministic ETags and `Cache-Control: no-store`.

## Portfolio semantics

One portfolio row represents all verified store observations for one deterministic `incident_id`. The current row exposes:

- incident/event identity;
- detection and latest observation timestamps;
- actor and category;
- latest recorded lifecycle state;
- observation count;
- preserved evidence-reference count;
- affected-trust-state count;
- explicit uncertainty count;
- whether key-compromise scope is recorded;
- whether recovery and post-recovery verification are recorded;
- whether the stricter forensic-continuity relationship contract verifies.

The portfolio does **not** claim that referenced external payload bytes are currently available or independently valid. It shows preserved identities and digests only.

## Incident detail semantics

The detail view exposes the bounded canonical record:

- lifecycle observations with store sequence and digests;
- evidence reference kind, identity, digest, and whether a source reference was recorded;
- affected state identity/digest, trust context, and optional affected window;
- security-event digests;
- explicit uncertainty entries;
- optional key-compromise blast-radius metadata;
- recovery identity, actor, status, source incident binding, and evidence reference;
- post-recovery verification identity, actor, time, status, and evidence references;
- forensic-continuity status.

Filesystem source paths are deliberately not sent to the browser.

For a `reverified` incident, StateWake calls the existing `verify_forensic_continuity()` relationship check. That verifies that an applied recovery and verified post-recovery evidence are drawn from the preserved incident reference set. It does not prove producer honesty, host integrity, external-system correctness, or causal explanation.

## Failure states

The read API uses explicit outcomes:

| Condition | API result |
|---|---|
| source not configured | `404 INCIDENT_SOURCE_NOT_CONFIGURED` |
| malformed/tampered incident chain | `422 INVALID_INCIDENT_SOURCE` |
| byte/record ceiling exceeded | `413 INCIDENT_SOURCE_TOO_LARGE` |
| invalid collection query | `400 INVALID_INCIDENT_QUERY` |
| unknown valid incident identity | `404 NOT_FOUND` |

The UI provides separate loading, empty, no-match, unavailable, invalid-source, and detail states.

## Explicit limits

This capability does not establish:

- root cause or causality;
- incident severity ranking;
- remediation authorization;
- successful external payload restoration;
- signer authenticity unless separately verified;
- host/KMS/storage/network recovery guarantees;
- permission to resume production activity.

Those boundaries remain with the existing StateWake evidence/trust authorities and the deploying organization.
