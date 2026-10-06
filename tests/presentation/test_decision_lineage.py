"""Regression coverage for decision-basis/reconciliation/lineage projections."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.presentation.decision_lineage import build_decision_lineage_investigation
from statewake.services.reliability_decision_basis_service import (
    write_reliability_decision_basis,
)
from statewake.services.reliability_lineage_service import (
    build_reliability_lineage_closure,
)


def _write(root: Path, name: str, payload: object) -> Path:
    path = root / name
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _ref(root: Path, kind: str, identity: str, name: str) -> EvidenceReference:
    path = root / name
    return EvidenceReference(
        kind, identity, sha256(path.read_bytes()).hexdigest(), name
    )


def decision_chain_fixture(
    tmp_path: Path,
) -> tuple[ReliabilityEvidenceChain, ReliabilityDecisionBasis]:
    """Create one fully composable decision chain with verification-context input."""
    _write(tmp_path, "run.json", {"run": "run-1"})
    _write(tmp_path, "state.json", {"state": "reliable"})
    _write(tmp_path, "evidence.json", {"evidence": "e-1"})
    _write(tmp_path, "integrity.json", {"verified": True})
    run = _ref(tmp_path, "run", "run-1", "run.json")
    state = _ref(tmp_path, "state", "state-1", "state.json")
    evidence = _ref(tmp_path, "evidence", "evidence-1", "evidence.json")
    integrity = _ref(tmp_path, "integrity", "integrity-1", "integrity.json")

    basis = ReliabilityDecisionBasis(
        "1",
        "manual",
        "basis-1",
        "1",
        "accept",
        "reliable",
        ("verified inputs",),
        (run.digest, state.digest, evidence.digest, integrity.digest),
    )
    basis_path = tmp_path / "basis.json"
    write_reliability_decision_basis(basis, basis_path)
    basis_ref = _ref(tmp_path, "decision-basis", basis.basis_id, "basis.json")

    nodes = (
        ProvenanceNode("run", run.kind, run.digest, run.identity, ()),
        ProvenanceNode("state", state.kind, state.digest, state.identity, ("run",)),
        ProvenanceNode(
            "evidence", evidence.kind, evidence.digest, evidence.identity, ("run",)
        ),
        ProvenanceNode(
            "basis",
            basis_ref.kind,
            basis_ref.digest,
            basis_ref.identity,
            ("run", "state", "evidence"),
        ),
    )
    graph = ProvenanceGraph(
        nodes,
        (
            ("state", "run"),
            ("evidence", "run"),
            ("basis", "run"),
            ("basis", "state"),
            ("basis", "evidence"),
        ),
    )
    provenance_path = tmp_path / "provenance.json"
    provenance_path.write_text(
        json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    provenance = EvidenceReference(
        "provenance",
        "provenance-1",
        sha256(provenance_path.read_bytes()).hexdigest(),
        provenance_path.name,
    )
    chain = ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=run,
        state=state,
        evidence=(evidence,),
        provenance=provenance,
        integrity=integrity,
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision_basis_ref=basis_ref,
        decision="accept",
        decision_rationale=basis.rationale,
    )
    return chain, basis


def test_projection_distinguishes_lineage_and_verification_context(
    tmp_path: Path,
) -> None:
    chain, basis = decision_chain_fixture(tmp_path)
    lineage = build_reliability_lineage_closure(chain, root=tmp_path)
    payload = build_decision_lineage_investigation(
        chain, lineage, basis=basis
    ).to_dict()

    assert payload["schema_version"] == "decision-lineage-investigation.v1"
    raw_inputs = payload["decision_inputs"]
    assert isinstance(raw_inputs, list)
    decision_inputs = cast(list[dict[str, object]], raw_inputs)
    items = {str(item["digest"]): item for item in decision_inputs}
    assert items[chain.evidence[0].digest]["classification"] == "lineage-bound"
    assert items[chain.integrity.digest]["classification"] == "verification-context"
    assert items[chain.integrity.digest]["reachable_to_run"] is None
    raw_lineage = payload["lineage"]
    assert isinstance(raw_lineage, dict)
    lineage_payload = cast(dict[str, object], raw_lineage)
    assert lineage_payload["verified"] is True


def test_projection_omits_source_paths_and_free_form_rationale(tmp_path: Path) -> None:
    chain, basis = decision_chain_fixture(tmp_path)
    lineage = build_reliability_lineage_closure(chain, root=tmp_path)
    payload = build_decision_lineage_investigation(
        chain, lineage, basis=basis
    ).to_dict()
    rendered = json.dumps(payload, sort_keys=True)
    assert str(tmp_path) not in rendered
    assert "verified inputs" not in rendered
    assert payload["decision_basis"]["rationale_exposed"] is False  # type: ignore[index]
    assert payload["authorization"]["publication_authorized"] is False  # type: ignore[index]


def test_projection_rejects_missing_bound_basis(tmp_path: Path) -> None:
    chain, _ = decision_chain_fixture(tmp_path)
    lineage = build_reliability_lineage_closure(chain, root=tmp_path)
    try:
        build_decision_lineage_investigation(chain, lineage)
    except ValueError as exc:
        assert "decision basis" in str(exc)
    else:
        raise AssertionError("bound basis unexpectedly omitted")
