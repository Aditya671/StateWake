# UI Review Statement Boundary

## Decision

StateWake may expose append-only **human review statements** only through an explicitly secured boundary. Review statements are not claim decisions, verification results, `HumanApprovalContract` records, release approvals, or side-effect authorization.

## Gap demonstrated before implementation

The existing source contains canonical verification reports, human-approval evidence contracts, deployment authentication/authorization hooks, and a hash-linked security audit store. It did not contain a general reviewer-comment repository. Reusing report rationale as comments would overwrite machine-owned semantics; using `HumanApprovalContract` as a comment record would incorrectly grant approval semantics.

Therefore this frontier adds one narrowly scoped record type and repository rather than a general workflow database.

## Authority boundaries

- Machine claim/profile decisions remain owned by existing reliability evaluation/report authorities.
- Human approval remains owned by `HumanApprovalContract`; this frontier does not write it.
- Review actor identity and role are supplied by the authenticated server boundary, never editable request fields.
- A review statement is bound to one report receipt, candidate identity/digest, report digest, profile ID/version, actor, role, scope, category, time, and append-chain digest.
- Corrections append a new record referencing the superseded record; historical text is never overwritten.

## Write preconditions

A review statement is accepted only when all of the following hold:

1. authentication succeeds;
2. operation-specific `review:write` authorization succeeds;
3. browser `Origin` is explicitly allowed;
4. the host-provided CSRF verifier succeeds;
5. `If-Match` identifies the exact report digest;
6. candidate/report digests in the request match the immutable canonical report;
7. a bounded idempotency key is present;
8. body/text/reference limits pass;
9. any superseded record exists under the same target/report and actor.

Exact idempotent retries return the original record. Reusing a key with changed content fails with conflict.

## Local qualification mode

`statewake.review_api` includes an explicit loopback single-reviewer adapter so the UI can be exercised locally without pretending StateWake has a production identity system. It requires server-held bearer/CSRF secrets plus configured actor identity/role and allowed browser origins. The Next.js review proxy keeps those secrets server-side and does not forward browser cookies or browser-supplied Authorization headers.

This mode is for local qualification and self-hosted bounded use. A production multi-user deployment must supply its own identity/session, authorization, CSRF, TLS, secret custody, rate/admission policy, and deployment audit integration through the generic providers.

## Non-goals

This boundary does not implement:

- approval/rejection writes;
- revocation;
- release authorization;
- tenant administration;
- free-text full-text indexing;
- LLM-generated review statements;
- automatic consensus or reviewer scoring.
