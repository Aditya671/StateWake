import tempfile
import unittest
from pathlib import Path

from statewake.domain.reliability_claim_profile import ReliabilityClaimProfile
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_claim_profile_service import (
    BUILTIN_CLAIM_PROFILES,
    evaluate_claim_profile,
    load_claim_profile,
    write_claim_profile,
)

D = "a" * 64


def ref(kind: str, identity: str) -> EvidenceReference:
    return EvidenceReference(kind, identity, D, f"{identity}.json")


def chain(**changes):  # type: ignore
    values = {
        "chain_id": "c1",
        "run": ref("run", "run-1"),
        "state": ref("state", "state-1"),
        "evidence": (ref("evidence", "e1"),),
        "provenance": ref("provenance", "p1"),
        "integrity": ref("integrity", "i1"),
        "verification_status": "verified",
        "reliability_state": "reliable",
        "reconciliation_state": "verified",
        "decision": "accept",
        "decision_rationale": ("bounded claim",),
    }
    values.update(changes)  # type: ignore
    return ReliabilityEvidenceChain(**values)  # type: ignore


class TestReliabilityClaimProfiles(unittest.TestCase):
    def test_builtin_profiles_are_versioned_and_deterministic(self):
        ids = [p.profile_id for p in BUILTIN_CLAIM_PROFILES]
        self.assertEqual(len(ids), 4)
        self.assertEqual([p.version for p in BUILTIN_CLAIM_PROFILES], ["1"] * 4)
        self.assertTrue(all(len(p.digest) == 64 for p in BUILTIN_CLAIM_PROFILES))

    def test_release_profile_accepts_verified_reliable_chain(self):
        profile = BUILTIN_CLAIM_PROFILES[0]
        result = evaluate_claim_profile(chain(), profile)
        self.assertTrue(result.satisfied)
        self.assertEqual(result.failed_conditions, ())

    def test_recovery_profile_requires_recovery_reference(self):
        profile = [
            p
            for p in BUILTIN_CLAIM_PROFILES
            if p.profile_id == "incident-recovery-verified"
        ][0]
        result = evaluate_claim_profile(chain(), profile)
        self.assertFalse(result.satisfied)
        self.assertIn("evidence-kind:recovery", result.failed_conditions)
        self.assertIn("recovery_present", result.failed_conditions)

    def test_profile_round_trip_and_tamper_detection(self):
        profile = BUILTIN_CLAIM_PROFILES[0]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile.json"
            write_claim_profile(profile, path)
            self.assertEqual(load_claim_profile(path), profile)
            payload = path.read_text(encoding="utf-8").replace(
                '"accept"', '"reject"', 1
            )
            path.write_text(payload, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_claim_profile(path)

    def test_profile_contract_does_not_score_or_evaluate_models(self):
        profile = ReliabilityClaimProfile(
            profile_id="example",
            version="1",
            title="Example",
            required_evidence_kinds=("evidence",),
            required_verification_conditions=("chain_verified",),
            allowed_decisions=("accept", "review", "reject"),
        )
        self.assertEqual(evaluate_claim_profile(chain(), profile).satisfied, True)
