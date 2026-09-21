# Built-in Claim Profiles

StateWake claim profiles declare the minimum evidence and state conditions required for a bounded reliability claim. They do not score model quality, approve release, execute policy, or replace human authorization.

## Phase 2 profile catalog

| Profile ID | Required AI contract evidence | Decision boundary |
| --- | --- | --- |
| `rag_answer_verified.v1` | `prompt_evidence`, `model_invocation`, `retrieval_evidence` | Accept only when the answer has digest-bound prompt, model, and retrieval evidence. |
| `tool_action_authorized.v1` | `tool_call`, `policy_evidence` | Accept only when the tool action and authorization policy evidence are both present. |
| `model_invocation_reconstructable.v1` | `model_invocation`, `runtime_trace` | Accept only when the invocation and runtime trace can be reconstructed. |
| `human_approval_recorded.v1` | `human_approval` | Accept only when approval actor, role, scope, basis, and timestamp evidence exists. |
| `incident_recovery_verified.v1` | `runtime_trace` plus recovery reference | Accept only when failure and recovery remain separately visible. |
| `release_evidence_complete.v1` | `policy_evidence`, `human_approval` | Accept the evidence profile only; publication remains a separate human decision. |
| `ai_decision_with_limitations.v1` | `policy_evidence`, `evaluator_evidence` | Return `accepted_with_limitations` only when caveats remain visible. |
| `policy_reverification_required.v1` | `policy_evidence` | Return `requires_reverification` when stale, missing, or invalid trust state blocks acceptance. |

## Evaluation result

`evaluate_claim_profile(chain, profile)` returns a `ClaimProfileEvaluation` with:

- `profile_id` and `profile_version`;
- `satisfied` for legacy boolean use;
- `decision` using the Phase 2 vocabulary: `accepted`, `rejected`, `accepted_with_limitations`, or `requires_reverification`;
- `passed_requirements` and `failed_requirements`;
- `missing_evidence` with exact missing contract labels such as `ai-contract:retrieval_evidence`;
- `caveats` copied from the selected profile.

## Public access

Python:

```python
from statewake import get_builtin_claim_profile, list_builtin_claim_profiles

profile = get_builtin_claim_profile("rag_answer_verified.v1")
profiles = list_builtin_claim_profiles()
```

CLI:

```bash
statewake claim-profiles
statewake claim-profiles --id rag_answer_verified.v1
```

Legacy IDs such as `release-evidence-complete` remain accepted as aliases where possible, but new work should use the Phase 2 profile IDs.
