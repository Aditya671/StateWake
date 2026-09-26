# StateWake Workspace Backend Migration Plan

## Boundary

The typed `StateWakeRepository` contract is the stable host-facing persistence boundary. SQLite remains the reference implementation, and the SQLAlchemy implementation is an optional alternative using the same schema and repository semantics.

## Migration path

1. Verify the source workspace before migration with `workspace.verify()`.
2. Produce a deterministic portable bundle with the existing workspace portable-bundle export.
3. Initialize the destination backend with the same workspace identity/schema contract.
4. Import the portable dataset through the destination backend's ingestion/indexing authority rather than copying database internals.
5. Verify the destination workspace and compare typed query results for representative bounded queries.
6. Keep the source workspace intact until destination verification succeeds.

## Compatibility rules

Backend changes must not reinterpret historical evidence, change typed query semantics, or bypass existing artifact/receipt ownership. Schema changes require deterministic migration tests against copied fixtures; failed migrations must leave the source recoverable.

The portable bundle is the data-portability boundary. No general migration framework is introduced until multiple concrete schema/backend migrations justify one.
