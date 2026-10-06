# Canonical Human Approval Revocation and Supersession Lifecycle

## Authority and invariant

`HumanApprovalContract` remains the canonical approval fact. Approval history is immutable: StateWake never edits or deletes a recorded approval to represent a later decision. Lifecycle changes are represented by new canonical evidence and projected into an effective state only after receipt, artifact, authority, report-basis, and lifecycle-link validation succeeds.

The effective lifecycle states are:

- `active` — the approval has no accepted revocation or superseding successor;
- `revoked` — a canonical `HumanApprovalRevocationContract` names the exact approval receipt and receipt digest;
- `superseded` — a replacement `HumanApprovalContract` names the exact predecessor receipt and digest in canonical metadata.

A lifecycle inconsistency fails closed. A predecessor cannot be both revoked and superseded, a non-active predecessor cannot transition again, links must remain within the same exact report basis and configured approval authority, and transition timestamps cannot precede the targeted approval.

## Secured HTTP boundary

The review service keeps approval creation, revocation, and supersession as distinct authorization operations:

```text
approval:write
approval:revoke
approval:supersede
```

Lifecycle writes require the same authenticated actor, allowed Origin, CSRF validation, exact `If-Match` report digest, exact candidate/report digests, bounded idempotency key, and server-owned approval producer/action/scope used by approval creation. Browser input cannot select a different actor or broaden the approval authority.

The exact lifecycle routes are:

```text
POST /api/v1/claims/{report_receipt}/approvals/{approval_receipt}/revoke
POST /api/v1/claims/{report_receipt}/approvals/{approval_receipt}/supersede
```

Both append evidence only. They do not mutate the verification report or machine decision, publish a release, or execute an external side effect.

## Release-proof reconciliation

A historical verification report remains an immutable snapshot. Revoking an approval therefore does not rewrite a previously generated report. Instead, every fresh release-proof reconciliation loads the canonical approval lifecycle for the exact machine-report basis and accepts only matching `active` approval evidence. A revoked or superseded historical approval cannot satisfy a new reconciliation.

This keeps these facts separate:

```text
historical report state
historical approval evidence
current effective approval lifecycle state
fresh release-proof reconciliation result
publication authorization
```

## UI behavior

The review UI displays the full approval history while identifying each record as active, revoked, or superseded. Revocation and supersession controls appear only for active approvals and only when the capability response grants the corresponding operation. The client cross-checks `active_approval_receipt_ids` against the per-record lifecycle projection and rejects inconsistent responses instead of rendering a misleading active state.
