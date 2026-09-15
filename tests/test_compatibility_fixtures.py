import json
from typing import Any

from config.project_paths import TESTS_PATH
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_evidence import ReliabilityEvidenceChain
from statewake.domain.reliability_proof_bundle import ReliabilityProofBundleDescriptor
from statewake.domain.reliability_state import ReliabilityStateTransition

FIXTURES = TESTS_PATH / "fixtures" / "compatibility"


def _load(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_released_artifact_fixtures_are_accepted_unchanged() -> None:
    cases = (
        ("evidence-receipt-v1.json", ExternalEvidenceReceipt),
        ("evidence-chain-v1.json", ReliabilityEvidenceChain),
        ("state-transition-v1.json", ReliabilityStateTransition),
        ("attestation-v1.json", ReliabilityOutcomeAttestation),
        ("decision-basis-v1.json", ReliabilityDecisionBasis),
        ("proof-bundle-descriptor-v1.json", ReliabilityProofBundleDescriptor),
    )
    for filename, cls in cases:
        payload = _load(filename)
        item = cls.from_dict(payload)
        assert item.to_dict() == payload


def test_explicit_version_markers_are_written_and_unknown_versions_rejected():
    payload = _load("evidence-receipt-v1.json")
    assert payload["format_version"] == "1"
    bad = dict(payload, format_version="99")
    try:
        ExternalEvidenceReceipt.from_dict(bad)
    except ValueError as exc:
        assert "format version" in str(exc)
    else:
        raise AssertionError("unknown receipt format version was accepted")
