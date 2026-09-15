> **Specification classification:** Historical reference.
>

# Reliability Core v0.1

## Purpose

Reliability Core consolidates the verified StateWake lifecycle behind one
stable assessment boundary. It is an orchestration layer, not a replacement for the
specialized domain engines.

## Inputs

A core assessment may use:

- contract
- baseline and candidate state snapshots
- optional evidence manifests
- optional recorded runs
- optional regression suite
- optional gate policy
- optional runtime enforcement context
- optional dependency inventory/change list
- optional deterministic chaos experiment

The specialized phase services remain authoritative for each input type.

## Aggregate output

`ReliabilityAssessment` exposes:

- deterministic assessment identifier
- agent and contract identity
- baseline/candidate state fingerprints
- behavioral change and risk
- gate outcome and regression counts
- runtime authorization outcome
- dependency impact counts
- chaos containment metrics
- aggregate status

Status semantics:

- `pass`: no supplied check is failing and no un-gated behavioral change is pending review.
- `warn`: a behavioral change exists without a deployment gate decision.
- `block`: a supplied gate, runtime authorization check, or chaos experiment fails.

`reliable` is true only for `pass`.

## Determinism

The assessment identifier is SHA-256 over canonical, stable assessment inputs. No wall-clock
or random value is included.

## Boundary rule

Core orchestration must reuse the existing comparison, gate, enforcement, impact, regression,
replay, and chaos services. New semantic engines must not be embedded in the aggregate layer.
