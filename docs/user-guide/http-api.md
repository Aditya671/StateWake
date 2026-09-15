# HTTP API

StateWake includes a standard-library WSGI adapter at `statewake.server:app`.

It is an integration edge, not a hosted SaaS control plane.

## Run locally

The verification adapter is HTTPS-by-default and requires configured artifact roots. For a local development process using plain HTTP, explicitly opt in:

```bash
STATEWAKE_VERIFICATION_ARTIFACT_ROOTS=./evidence STATEWAKE_ALLOW_INSECURE_HTTP=1 python -m statewake.server
```

Default address: `http://127.0.0.1:8787`.

## Endpoints

### `GET /health`

Returns service health and the running StateWake version.

### `GET /v1/version`

Returns the StateWake package version.

### `POST /v1/evidence/verify`

Request body:

```json
{
  "chain_path": "./evidence/chain.json",
  "evidence_root": "./evidence"
}
```

The endpoint verifies the canonical evidence chain and returns its identifier and digest on success.

### `POST /v1/proof/verify`

Request body:

```json
{
  "bundle_path": "./proof-bundle"
}
```

The endpoint verifies a portable reliability proof bundle and reports its verification checks and failures.

## Production deployment

The adapter requires explicit configured artifact roots, resolved-path containment, a request-size limit, read-only verification behavior, and HTTPS by default. A production deployment must still add authentication and authorization, TLS termination where appropriate, network controls, logging, and operational monitoring. Plain HTTP is an explicit local-development opt-in only.

Do not expose arbitrary local filesystem paths to untrusted callers.
