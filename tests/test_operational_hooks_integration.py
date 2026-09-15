import unittest
from dataclasses import dataclass

from statewake.domain.operational_hooks import ReliabilityFailureEvent
from statewake.services.reliability_state_service import transition_reliability_state


# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
@dataclass
class _Hook:
    events: list  # type: ignore

    def emit(self, event: ReliabilityFailureEvent) -> None:
        self.events.append(event)


class _BrokenStore:
    def read(self, subject_id):
        return []

    def append(self, transition):
        raise OSError("disk full")


class _Chain:
    reliability_state = "reliable"
    decision = "accept"
    chain_id = "chain-1"
    reconciliation_state = "not-applicable"
    recovery_ref = None
    decision_rationale = ("test",)

    def digest(self):
        return "a" * 64


class TestOperationalHooksIntegration(unittest.TestCase):
    def test_state_write_failure_emits_host_event(self):
        hook = _Hook([])
        with self.assertRaises(OSError):
            transition_reliability_state(
                "subject",
                _Chain(),  # type: ignore
                store=_BrokenStore(),  # type: ignore
                actor="test",
                failure_hook=hook,
            )
        self.assertEqual(len(hook.events), 1)
        self.assertEqual(hook.events[0].event_type, "state_write_failure")
        self.assertEqual(hook.events[0].subject_id, "subject")


if __name__ == "__main__":
    unittest.main()
