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
    ClaimProfileRegistry,
    evaluate_claim_profile,
    get_builtin_claim_profile,
    list_builtin_claim_profiles,
    load_claim_profile,
    write_claim_profile,
)

D = "a" * 64


def ref(kind: str, identity: str, source: str | None = None) -> EvidenceReference:
    return EvidenceReference(kind, identity, D, source or f"{identity}.json")


def ai_ref(contract_type: str, suffix: str = "1") -> EvidenceReference:
    return ref(
        "evidence",
        f"ai-contract:{contract_type}:run-1:{suffix}",
        f"statewake.ai_contracts.{contract_type}",
    )


def chain(**changes):  # type: ignore
    values = {
        "chain_id": "c1",
        "run": ref("run", "run-1"),
        "state": ref("state", "state-1"),
        "evidence": (
            ai_ref("prompt_evidence"),
            ai_ref("model_invocation"),
            ai_ref("retrieval_evidence"),
            ai_ref("policy_evidence"),
            ai_ref("human_approval"),
            ai_ref("tool_call"),
            ai_ref("runtime_trace"),
            ai_ref("evaluator_evidence"),
        ),
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
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([p.version for p in BUILTIN_CLAIM_PROFILES], ["1"] * 8)
        self.assertTrue(all(len(p.digest) == 64 for p in BUILTIN_CLAIM_PROFILES))

    def test_rag_profile_accepts_required_contract_evidence(self):
        profile = get_builtin_claim_profile("rag_answer_verified.v1")
        result = evaluate_claim_profile(chain(), profile)
        self.assertTrue(result.satisfied)
        self.assertEqual(result.decision, "accepted")
        self.assertEqual(result.failed_conditions, ())

    def test_rag_profile_rejects_answer_without_retrieval_digest(self):
        profile = get_builtin_claim_profile("rag_answer_verified.v1")
        incomplete = chain(
            evidence=(ai_ref("prompt_evidence"), ai_ref("model_invocation"))
        )
        result = evaluate_claim_profile(incomplete, profile)
        self.assertFalse(result.satisfied)
        self.assertEqual(result.decision, "rejected")
        self.assertIn("ai-contract:retrieval_evidence", result.failed_conditions)
        self.assertIn("ai-contract:retrieval_evidence", result.missing_evidence)

    def test_tool_profile_rejects_side_effect_without_authorization(self):
        profile = get_builtin_claim_profile("tool_action_authorized.v1")
        result = evaluate_claim_profile(chain(evidence=(ai_ref("tool_call"),)), profile)
        self.assertFalse(result.satisfied)
        self.assertIn("ai-contract:policy_evidence", result.failed_conditions)

    def test_recovery_profile_keeps_failure_and_recovery_distinct(self):
        profile = get_builtin_claim_profile("incident_recovery_verified.v1")
        result = evaluate_claim_profile(chain(), profile)
        self.assertFalse(result.satisfied)
        self.assertIn("evidence-kind:recovery", result.failed_conditions)
        self.assertIn("recovery_present", result.failed_conditions)

    def test_release_profile_requires_unresolved_limitations_visibility(self):
        profile = get_builtin_claim_profile("release_evidence_complete.v1")
        result = evaluate_claim_profile(chain(), profile)
        self.assertTrue(result.satisfied)
        self.assertEqual(
            profile.caveats,
            ("Release authorization remains a separate human decision.",),
        )

    def test_ai_decision_with_limitations_reports_limited_acceptance(self):
        profile = get_builtin_claim_profile("ai_decision_with_limitations.v1")
        result = evaluate_claim_profile(chain(decision="review"), profile)
        self.assertTrue(result.satisfied)
        self.assertEqual(result.decision, "accepted_with_limitations")
        self.assertTrue(result.caveats)

    def test_policy_reverification_required_blocks_acceptance(self):
        profile = get_builtin_claim_profile("policy_reverification_required.v1")
        stale = chain(
            verification_status="failed",
            reliability_state="degraded",
            reconciliation_state="stale",
            decision="reject",
            evidence=(ai_ref("policy_evidence"),),
        )
        result = evaluate_claim_profile(stale, profile)
        self.assertEqual(result.decision, "requires_reverification")
        self.assertFalse(result.satisfied)

    def test_profile_registry_rejects_duplicate_profile_id_version(self):
        profile = BUILTIN_CLAIM_PROFILES[0]
        with self.assertRaises(ValueError):
            ClaimProfileRegistry((profile, profile))

    def test_profile_decision_is_deterministic_for_same_evidence(self):
        profile = get_builtin_claim_profile("rag_answer_verified.v1")
        first = evaluate_claim_profile(chain(), profile).to_dict()
        second = evaluate_claim_profile(chain(), profile).to_dict()
        self.assertEqual(first, second)

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

    def test_profile_missing_evidence_reports_exact_contract_ids(self):
        profile = get_builtin_claim_profile("model_invocation_reconstructable.v1")
        result = evaluate_claim_profile(
            chain(evidence=(ai_ref("model_invocation"),)), profile
        )
        self.assertIn("ai-contract:runtime_trace", result.missing_evidence)

    def test_legacy_profile_aliases_still_resolve(self):
        self.assertEqual(
            get_builtin_claim_profile("release-evidence-complete").profile_id,
            "release_evidence_complete.v1",
        )

    def test_list_builtin_claim_profiles_is_public(self):
        self.assertEqual(list_builtin_claim_profiles(), BUILTIN_CLAIM_PROFILES)

    def test_profile_contract_does_not_score_or_evaluate_models(self):
        profile = ReliabilityClaimProfile(
            profile_id="example",
            version="1",
            title="Example",
            required_evidence_kinds=("state",),
            required_verification_conditions=("chain_verified",),
            allowed_decisions=("accept", "review", "reject"),
        )
        self.assertTrue(evaluate_claim_profile(chain(), profile).satisfied)
