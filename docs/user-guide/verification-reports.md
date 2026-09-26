# Human Verification Reports

StateWake verification reports are portable, human-readable artifacts for bounded
reliability claims. They do not approve a release, certify model quality, or
replace a business, engineering, security, or compliance decision.

## Report purpose

A report answers:

- which candidate was inspected;
- which claim profile was applied;
- which evidence was included, omitted, or missing;
- which checks passed, failed, were unavailable in the environment, or remain
  unknown;
- which caveats and residual risks must travel with the result;
- which human decisions remain outside StateWake verification.

## Candidate identity

Every report records both `candidate_identity` and `candidate_digest`. The
identity is the smallest complete review unit, such as a reliability evidence
chain, proof bundle, workflow run, or release candidate. The digest binds the
human-readable report back to the inspected machine-readable artifact.

## Gate states

Reports preserve grounded gate states:

| State | Meaning |
| --- | --- |
| `PASS` | The check ran and succeeded. |
| `FAIL` | The check ran and failed. |
| `UNRUN-ENV` | The check could not run because a required tool, dependency, credential, network, or environment was unavailable. |
| `UNKNOWN` | The check is not yet defined clearly enough to run. |

Missing, unrun, or unknown evidence is never converted into a pass.

## Evidence sections

Reports separate:

- `evidence_included`: evidence actually available to the report;
- `evidence_omitted`: evidence deliberately left out of the portable report;
- `evidence_missing`: required evidence that was not present;
- `source_identities`: source artifacts or records that support the report;
- `artifact_digests`: exact digests for evidence bundles, chains, or appendices.

Sensitive payloads should be redacted while preserving digest references so the
report remains inspectable without exposing raw prompt, tool, credential, or
private content.

## Decision versus approval

The report field `decision` is the StateWake verification or claim-profile
decision. The field `approval_status` is separate and defaults to
`not-approval`. A report can say that a profile decision is acceptable while
still requiring a human owner to approve release, operational use, or business
action.

## Renderers

The reusable rendering surface is available from `statewake.reports`:

```python
from statewake.reports import render_json_report, render_markdown_report
```

`render_json_report` emits deterministic JSON including the report digest.
`render_markdown_report` emits a human-readable report with the same underlying
report digest.
