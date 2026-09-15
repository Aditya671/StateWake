"""Run deterministic property and state-machine checks for StateWake."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from scripts.common.validation_types import (  # noqa: E402
    ValidationReport,
    ValidationResult,
)
from statewake.domain.events import EventEnvelope  # noqa: E402
from statewake.domain.evidence import EvidenceItem, EvidenceManifest  # noqa: E402
from statewake.domain.reliability_state import (  # noqa: E402
    ALLOWED_TRANSITIONS,
    RELIABILITY_STATES,
    ReliabilityStateTransition,
)

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH

SEED = 20260913
DEFAULT_CASES = 250
DEFAULT_STEPS = 40
NOW = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Counterexample:
    """Describe a minimized failing generated case."""

    property_name: str
    seed: int
    case_index: int
    steps: tuple[str, ...]
    failure: str


class PropertyFailureError(AssertionError):
    """Represent a property violation with reproducible case data."""

    def __init__(self, counterexample: Counterexample) -> None:
        """Initialize the failure from its reproducible counterexample."""
        self.counterexample = counterexample
        super().__init__(
            f"{counterexample.property_name} failed at case "
            f"{counterexample.case_index}: {counterexample.failure}"
        )


def _digest(index: int) -> str:
    """Return a deterministic SHA-256-shaped test value."""
    return f"{index:064x}"[-64:]


def _transition(
    index: int, from_state: str, to_state: str, *, previous_digest: str = ""
) -> ReliabilityStateTransition:
    """Construct a valid generated reliability transition."""
    decision = {
        "reliable": "accept",
        "recovered": "accept",
        "degraded": "review",
        "unreliable": "reject",
    }[to_state]
    return ReliabilityStateTransition(
        transition_id=f"generated-{index}",
        subject_id="generated-subject",
        from_state=from_state,
        to_state=to_state,
        occurred_at=NOW + timedelta(seconds=index),
        actor="property-harness",
        evidence_chain_id=_digest(1000),
        evidence_chain_digest=_digest(1001),
        decision=decision,
        rationale=(f"generated-step-{index}",),
        previous_transition_digest=previous_digest,
    )


def _round_trip_property(rng: random.Random, case_index: int) -> None:
    """Verify transition serialization is an identity-preserving property."""
    from_state = rng.choice(RELIABILITY_STATES)
    to_state = rng.choice(sorted(ALLOWED_TRANSITIONS[from_state]))
    item = _transition(case_index, from_state, to_state)
    restored = ReliabilityStateTransition.from_dict(item.to_dict())
    assert restored == item
    assert restored.computed_digest == item.computed_digest


def _digest_binding_property(rng: random.Random, case_index: int) -> None:
    """Verify generated transition payloads reject single-field mutations."""
    from_state = rng.choice(RELIABILITY_STATES)
    to_state = rng.choice(sorted(ALLOWED_TRANSITIONS[from_state]))
    item = _transition(case_index, from_state, to_state)
    payload = item.to_dict()
    field = rng.choice(("actor", "decision", "rationale", "subject_id"))
    if field == "rationale":
        payload[field] = ["tampered"]
    elif field == "decision":
        payload[field] = {"accept": "review", "review": "reject", "reject": "accept"}[
            item.decision
        ]
    else:
        payload[field] = "tampered"
    try:
        ReliabilityStateTransition.from_dict(payload)
    except ValueError:
        return
    raise AssertionError(f"mutation of {field} was accepted")


def _manifest_property(rng: random.Random, case_index: int) -> None:
    """Verify evidence-manifest round trips across generated evidence sets."""
    count = rng.randrange(0, 9)
    items = tuple(
        EvidenceItem(
            evidence_id=f"e-{case_index}-{index}",
            source=rng.choice(("webhook", "queue", "database", "agent")),
            digest=_digest(case_index * 100 + index),
            metadata={"producer": f"p-{rng.randrange(4)}"},
            sensitivity=rng.choice(("public", "internal", "confidential")),
        )
        for index in range(count)
    )
    manifest = EvidenceManifest(f"m-{case_index}", f"run-{case_index}", items)
    assert EvidenceManifest.from_dict(manifest.to_dict()) == manifest


def _event_property(rng: random.Random, case_index: int) -> None:
    """Verify generated event envelopes preserve their canonical representation."""
    event = EventEnvelope(
        run_id=f"run-{case_index}",
        sequence=rng.randrange(0, 1000),
        occurred_at=NOW + timedelta(seconds=rng.randrange(10000)),
        event_type=rng.choice(("run.started", "tool.called", "decision.made")),
        actor=rng.choice(("runtime", "agent", "operator")),
        name=rng.choice((None, "agent-a", "tool-x")),
        state_id=rng.choice((None, "state-a", "state-b")),
        payload_ref=rng.choice((None, _digest(case_index + 5000))),
        metadata={"case": str(case_index), "seed": str(SEED)},
    )
    assert EventEnvelope.from_dict(event.to_dict()) == event


def _state_machine(rng: random.Random, case_index: int, steps: int) -> None:
    """Exercise valid and invalid transitions while preserving state-machine invariants."""
    state = "unknown"
    history: list[ReliabilityStateTransition] = []
    for step in range(steps):
        if rng.random() < 0.72:
            to_state = rng.choice(sorted(ALLOWED_TRANSITIONS[state]))
            previous = history[-1].computed_digest if history else ""
            item = _transition(step, state, to_state, previous_digest=previous)
            assert item.from_state == state
            assert item.to_state in ALLOWED_TRANSITIONS[state]
            assert item.previous_transition_digest == previous
            assert ReliabilityStateTransition.from_dict(item.to_dict()) == item
            history.append(item)
            state = to_state
            continue

        invalid_targets = [
            candidate
            for candidate in RELIABILITY_STATES
            if candidate not in ALLOWED_TRANSITIONS[state]
        ]
        if not invalid_targets:
            continue
        bad_state = rng.choice(invalid_targets)
        decision = {
            "reliable": "accept",
            "recovered": "accept",
            "degraded": "review",
            "unreliable": "reject",
            "unknown": "accept",
        }[bad_state]
        try:
            ReliabilityStateTransition(
                transition_id=f"invalid-{step}",
                subject_id="generated-subject",
                from_state=state,
                to_state=bad_state,
                occurred_at=NOW + timedelta(seconds=step),
                actor="property-harness",
                evidence_chain_id=_digest(1000),
                evidence_chain_digest=_digest(1001),
                decision=decision,
            )
        except ValueError:
            assert state == (history[-1].to_state if history else "unknown")
            continue
        raise AssertionError(f"invalid transition {state} -> {bad_state} was accepted")


def _run_property(
    name: str,
    cases: int,
    seed: int,
    property_fn: Callable[[random.Random, int], None],
) -> ValidationResult:
    """Execute one deterministic generated property suite."""
    for case_index in range(cases):
        case_seed = seed + case_index * 7919
        rng = random.Random(case_seed)
        try:
            property_fn(rng, case_index)
        except Exception as exc:
            steps = (f"case_seed={case_seed}",)
            counterexample = Counterexample(
                name, seed, case_index, steps, f"{type(exc).__name__}: {exc}"
            )
            raise PropertyFailureError(counterexample) from exc
    return {"property": name, "cases": cases, "passed": True}


def run(
    *, seed: int = SEED, cases: int = DEFAULT_CASES, steps: int = DEFAULT_STEPS
) -> ValidationReport:
    """Run generated properties and a state-machine campaign."""
    results: list[ValidationResult] = [
        _run_property("transition-round-trip", cases, seed, _round_trip_property),
        _run_property(
            "transition-digest-binding", cases, seed + 1, _digest_binding_property
        ),
        _run_property(
            "evidence-manifest-round-trip", cases, seed + 2, _manifest_property
        ),
        _run_property("event-round-trip", cases, seed + 3, _event_property),
    ]
    state_machine_cases = cases
    for case_index in range(state_machine_cases):
        case_seed = seed + case_index * 104729
        rng = random.Random(case_seed)
        try:
            _state_machine(rng, case_index, steps)
        except Exception as exc:
            counterexample = Counterexample(
                "reliability-state-machine",
                seed,
                case_index,
                (f"case_seed={case_seed}", f"steps={steps}"),
                f"{type(exc).__name__}: {exc}",
            )
            raise PropertyFailureError(counterexample) from exc
    results.append(
        {
            "property": "reliability-state-machine",
            "cases": state_machine_cases,
            "steps": steps,
            "passed": True,
        }
    )
    return {
        "passed": True,
        "seed": seed,
        "property_count": len(results),
        "results": results,
    }


def main() -> int:
    """Run the command-line property/state-machine campaign."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    args = parser.parse_args()
    if args.cases < 1 or args.steps < 1:
        parser.error("--cases and --steps must be positive")
    try:
        report = run(seed=args.seed, cases=args.cases, steps=args.steps)
    except PropertyFailureError as exc:
        print(
            json.dumps(
                {"passed": False, "counterexample": asdict(exc.counterexample)},
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
