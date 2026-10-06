# Producer Capture Health & Failure Journal Investigation

StateWake exposes an optional read-only operator view over the existing `NativeCaptureSink` failure journal. The feature is deliberately narrower than a general observability or capture-monitoring system: it inspects the privacy-safe failure evidence already written by the runtime and does not attach to, drain, reconfigure, or mutate a live sink.

## Configuration

Start the read API with an existing workspace as usual and point the optional capture-health source at the same failure journal configured for the producer runtime:

```powershell
$env:STATEWAKE_UI_WORKSPACE_ROOT = "C:\path\to\statewake-workspace"
$env:STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL = "C:\path\to\capture-failures.jsonl"
python -m statewake.read_api
```

If the runtime journal capacity is known, the operator may also declare it to the read API:

```powershell
$env:STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL_CAPACITY_BYTES = "8388608"
```

That value is **operator-supplied context**, not discovered from a running `NativeCaptureSink`. If it is omitted, the UI reports capacity as not declared. A missing journal file at a configured path is valid: `NativeCaptureSink` creates the file only after the first recorded failure, so this state is represented as an empty journal rather than a missing-source error.

## Authority and privacy boundary

The canonical journal contains exactly two fields per line:

```json
{"stage":"native_capture.persist","error_type":"OSError"}
```

The reader reuses the runtime journal parser and enforces the same bounded token contract. It rejects:

- symlink traversal;
- malformed JSON;
- extra fields;
- invalid stage/error tokens;
- a partial trailing record;
- invalid UTF-8;
- byte-limit overflow;
- record-limit overflow.

It never returns local filesystem paths, raw exception messages, prompts, responses, tool payloads, arbitrary SDK metadata, or secrets.

## Read API

When `STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL` is configured:

```text
GET /api/v1/capture-health
GET /api/v1/capture-health?stage=native_capture.persist
GET /api/v1/capture-health?error_type=OSError&limit=50&offset=0
```

Only `stage`, `error_type`, `limit`, and `offset` are accepted. Filters are exact matches. Duplicate or unknown query parameters and pagination beyond the fixed ceiling fail closed. The response exposes a deterministic ETag.

The projection includes:

- journal existence and observed byte size;
- bounded read limit;
- optional declared runtime journal capacity context;
- total recorded failures;
- distinct stage/error-type counts;
- deterministic aggregate counts;
- bounded journal records in file sequence order.

## Interpretation limits

The capture-health view intentionally does **not** claim more than the journal can establish:

```text
zero journal failures != proof of complete capture
journal sequence != event timestamp or causality
failure journal != live in-memory sink state
failure journal != downstream acknowledgement state
failure journal != proof of workspace durability
```

Without a workspace, `NativeCaptureSink` results are an in-memory diagnostic window. With a workspace, the runtime sink persists a successful result before acknowledging it. The failure journal itself does not prove which runtime configuration was active, which successes occurred, whether a consumer later drained the result window, or whether an external producer emitted events StateWake never received.

The UI therefore labels an empty journal as **no recorded failures**, never as healthy/successful capture.
