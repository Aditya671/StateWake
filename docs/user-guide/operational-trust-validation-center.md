# Operational Trust & Validation Center

StateWake exposes an optional **read-only operational inspection center** for three authorities that already exist in the Python product: durable workspace state, release-trust evidence, and the deterministic comparative validation study. The center is presentation and inspection only. It does not create a second verifier, execute a benchmark, repair a workspace, authenticate a signer without a trust root, or publish a release.

## Authority model

The center preserves the following distinctions:

```text
workspace bytes + SQLite operational index
    -> read-only workspace diagnostics and bounded records

release-trust bundle
    -> structural claim-profile evaluation
    -> optional local byte/digest verification
    -> signer authentication status (separate, not inferred)
    -> recorded human release decision (separate)
    -> optional canonical publication-authorization lifecycle (read-only)

frozen comparative-study JSON
    -> digest validation
    -> case/metric consistency validation
    -> explicit denominators and fixture scope
    -> display only; no live benchmark execution
```

These results must not be collapsed into a universal trust score. A structurally complete bundle does not prove its files are present. Matching file digests do not authenticate a signer. Signature evidence does not authorize publication. A recorded fixture-study result does not establish behavior on untested systems.

## Read API configuration

The existing local read API remains the boundary:

```powershell
$env:STATEWAKE_UI_WORKSPACE_ROOT = "C:\path\to\existing\statewake-workspace"
$env:STATEWAKE_UI_RELEASE_TRUST_BUNDLE = "C:\path\to\release-trust.json"      # optional
$env:STATEWAKE_UI_RELEASE_ROOT = "C:\path\to\release-root"                  # optional byte verification
$env:STATEWAKE_UI_PUBLICATION_BASIS = "C:\path\to\publication-basis.json"      # optional, all three together
$env:STATEWAKE_UI_PUBLICATION_APPROVAL_WORKSPACE = "C:\path\to\publication-authority"
$env:STATEWAKE_UI_PUBLICATION_PRODUCER_ID = "github-actions:owner/repository"
$env:STATEWAKE_UI_PUBLICATION_PERMIT = "C:\path\to\publication-permit.json"       # optional, both together
$env:STATEWAKE_UI_PUBLICATION_REGISTRY_RECEIPT = "C:\path\to\registry-publication-receipt.json"
$env:STATEWAKE_UI_PUBLICATION_REGISTRY_LIFECYCLE = "C:\path\to\registry-publication-lifecycle.jsonl"  # optional after receipt
$env:STATEWAKE_UI_VALIDATION_STUDY = "C:\path\to\comparative-study.json"    # optional
python -m statewake.read_api
```

Operational routes:

```text
GET /api/v1/workspace/operations?limit=50&offset=0
GET /api/v1/release-trust
GET /api/v1/validation-study
```

`workspace/operations` accepts only `limit` and `offset`. `limit` is bounded to 1–200, duplicate parameters are rejected, and arbitrary SQL/filter/path input is not accepted. Release-trust and validation-study inputs are server-configured paths, never browser-supplied file paths.

## Workspace inspection boundary

`StateWakeWorkspace.open_read_only()` opens an already initialized workspace without creating directories, manifests, operation locks, recovery state, or migrations. Its SQLite repository uses URI `mode=ro`, enables foreign-key enforcement, and enables `PRAGMA query_only=ON`. Mutation entry points reject operations before durable writes.

Workspace inspection reports:

- workspace identity and schema;
- integrity/health verification results;
- storage accounting;
- bounded receipt/record pages;
- retention and legal-hold state for displayed records;
- deletion-tombstone count;
- export metadata without output filesystem paths or raw query definitions;
- explicit `not_recorded` results where backup history or an operational audit stream is not a canonical repository authority.

Opening the page does not export, delete, restore, migrate, repair, or lock the workspace.

## Release-trust boundary

The release-trust view reuses the canonical `ReleaseTrustBundle` and built-in `release_evidence_complete.v1` profile. If `STATEWAKE_UI_RELEASE_ROOT` is configured, referenced local files are independently re-read and checked against recorded size/digest constraints through the existing release-content verifier.

The browser receives separate fields for:

- structural profile satisfaction;
- local content verification;
- signature evidence;
- signer-authentication status;
- human release decision;
- publication authorization.

The current read-only center deliberately reports signer authenticity as `not_verified` because no independent trust anchor is supplied to this UI boundary. When all publication-authorization inputs are configured, it loads the exact publication basis and canonical approval workspace, verifies that the basis matches the release-trust source identity, and projects active/revoked/superseded publication approval state. When the publication permit and registry receipt are additionally configured together, it verifies that the receipt is bound to that exact basis and permit before reporting registry publication and public-byte reconciliation. When an optional registry-lifecycle JSONL is configured, every observation is revalidated against that same receipt/basis/permit chain before the UI displays current availability, yank state, missing artifacts, or observed unavailability. Without those inputs it reports the corresponding state as unconfigured/false. The surface never creates approval, issues an execution permit, publishes a release, or creates registry evidence.

## Comparative validation-study boundary

The validation page reads one frozen study artifact through `load_study_report()`. The loader is size-bounded, reconstructs the canonical study model, validates any supplied digest, validates baseline/workload/fault identities, and checks metric numerators and denominators against the recorded cases before projection.

The UI shows recorded cases, baselines, injected faults, coverage/detection denominators, and limitations. It does not run tests or benchmarks and must not generalize fixture measurements to production systems.

## UI behavior

The Next.js UI exposes three operator pages:

```text
/release-trust
/validation
/workspace
```

Each page has explicit loading, unavailable/error, and bounded data states. Tables are the primary representation for operational records and evidence; horizontal scrolling is used for narrow displays rather than hiding fields. The same-origin proxy allowlist permits only the implemented GET paths and bounded workspace pagination query.

The existing Claim Workbench, Evidence Explorer, history, comparison, review statements, and scoped human-approval flows remain independent and unchanged in authority.

## Limits

This center does not establish:

- factual truth of external evidence;
- producer honesty;
- signer identity without an independently configured trust anchor;
- registry publication or deployment merely from viewing an active approval or execution permit;
- future registry availability or continued unyanked status from a point-in-time publication receipt;
- backup history when the current schema does not record it;
- production performance or behavior outside the recorded validation study;
- authorization to mutate workspace or release state.
