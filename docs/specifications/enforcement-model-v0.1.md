> **Specification classification:** Historical reference.
>

# Runtime Enforcement Model v0.1

The enforcement model turns selected contract statements into an explicit runtime decision boundary.

## Policy model

- `constraints` are executable **hard** constraints for backward compatibility with
  existing contracts.
- `advisory_constraints` are executable **advisory** constraints and never block an
  otherwise authorized action.
- Tool authority is evaluated independently from policy constraints: a tool/action not
  declared by the contract is unauthorized and cannot execute.
- `escalation_conditions` are evaluated as trigger conditions. A matching condition
  creates an `EscalationRequest` and blocks the pre-action decision until an explicit
  higher-level handler resolves it.

## Evaluation boundary

`PolicyEvaluator` is a replaceable interface. The default evaluator implements a small,
side-effect-free expression language: boolean logic, comparisons, literals, dotted mapping
lookups, and membership operations. Arbitrary Python execution, function calls,
comprehensions, and object mutation are rejected.

## Hooks

`RuntimeEnforcer.pre_action()` is the hard enforcement boundary. A runtime adapter must
check its returned `PolicyDecision.allowed` before performing the external action.

`RuntimeEnforcer.post_action()` evaluates the resulting context after an action. A failed
post-action decision cannot undo an already executed external operation; it provides a
containment/escalation signal instead.

## Authorization

`authorize_tool_call()` returns both `authorized` and `allowed` so adapters can distinguish
"outside declared authority" from "declared action blocked by policy".

## Local-first

The default implementation uses only the Python standard library and requires no model,
network, vendor SDK, or paid service.
