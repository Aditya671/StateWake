> **Specification classification:** Historical reference.
>

# Reconciliation Recovery Specification v0.1

## Scope

The reconciliation recovery model makes scheduled reconciliation failures durable and recoverable without advancing the scheduler success checkpoint.

## Rules

1. A reconciliation occurrence is claimed before work but the schedule checkpoint is not advanced.
2. A successful occurrence is marked complete and advances the checkpoint only across contiguous completed occurrences.
3. A failed occurrence records attempts, last error, status, and deterministic next retry time.
4. Retry delay is exponential and capped by the configured policy.
5. Recovery claims only failed occurrences whose retry time has elapsed.
6. Recovery does not consume unrelated newly due occurrences.
7. Attempts beyond `max_attempts` transition the occurrence to `dead` and are never automatically retried.
8. Durable failure history is append/update visible through the existing reconciliation history boundary.
9. The reliability core never executes arbitrary jobs; hosts provide reconciliation workers/functions.
