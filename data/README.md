# Local StateWake Data Boundary

StateWake may create local runtime workspace data beneath this directory when a caller accepts the default `data/statewake/` workspace root.

Generated workspace databases, receipts, artifacts, manifests, exports, locks, and other runtime state are **not source-controlled release inputs**. The repository keeps only this README; `/data/statewake/` is ignored by Git.

Tests and validation campaigns should normally use explicit temporary directories so repository-local runtime state is not required for verification.
