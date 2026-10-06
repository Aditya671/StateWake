"""Bounded evidence-trace projection for one verification report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation.claim_detail import ReportSourceContext

EVIDENCE_TRACE_SCHEMA_VERSION = "evidence-trace.v2"


def _stable_id(kind: str, identity: str) -> str:
    payload = json.dumps(
        {"kind": kind, "identity": identity},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceTraceRecord:
    """Safe workspace-record context used by the trace projection."""

    record_id: str
    artifact_digest: str
    artifact_size: int
    producer_id: str
    producer_type: str
    captured_at: str
    source_ref: str
    source_event_id: str | None
    run_id: str | None
    receipt_digest: str
    receipt_integrity_status: str
    artifact_integrity_status: str
    admission_status: str
    admission_digest: str | None
    producer_authentication_status: str


@dataclass(frozen=True, slots=True)
class EvidenceTraceNode:
    """One explicit object shown in the evidence relationship projection."""

    node_id: str
    kind: str
    identity: str
    label: str
    digest: str | None = None
    digest_kind: str | None = None
    integrity_status: str = "recorded"
    availability: str = "recorded"
    record_id: str | None = None
    producer_id: str | None = None
    producer_type: str | None = None
    captured_at: str | None = None
    run_id: str | None = None
    source_event_id: str | None = None
    artifact_size: int | None = None
    receipt_digest: str | None = None
    receipt_integrity_status: str | None = None
    artifact_integrity_status: str | None = None
    admission_status: str | None = None
    admission_digest: str | None = None
    producer_authentication_status: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable safe node representation."""
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "identity": self.identity,
            "label": self.label,
            "digest": self.digest,
            "digest_kind": self.digest_kind,
            "integrity_status": self.integrity_status,
            "availability": self.availability,
            "record_id": self.record_id,
            "producer_id": self.producer_id,
            "producer_type": self.producer_type,
            "captured_at": self.captured_at,
            "run_id": self.run_id,
            "source_event_id": self.source_event_id,
            "artifact_size": self.artifact_size,
            "receipt_digest": self.receipt_digest,
            "receipt_integrity_status": self.receipt_integrity_status,
            "artifact_integrity_status": self.artifact_integrity_status,
            "admission_status": self.admission_status,
            "admission_digest": self.admission_digest,
            "producer_authentication_status": self.producer_authentication_status,
        }


@dataclass(frozen=True, slots=True)
class EvidenceTraceEdge:
    """One typed relationship whose basis is explicitly recorded or equality-derived."""

    edge_id: str
    source: str
    target: str
    relationship_type: str
    basis: str
    occurrences: int = 1

    def to_dict(self) -> dict[str, object]:
        """Return the stable edge representation."""
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "relationship_type": self.relationship_type,
            "basis": self.basis,
            "occurrences": self.occurrences,
        }


@dataclass(frozen=True, slots=True)
class EvidenceTraceProjection:
    """Read-only evidence lineage around one canonical verification report."""

    report_record_id: str
    report_digest: str
    candidate_identity: str
    candidate_digest: str
    nodes: tuple[EvidenceTraceNode, ...]
    edges: tuple[EvidenceTraceEdge, ...]
    unresolved: tuple[dict[str, str], ...]
    records_scanned: int
    records_available: int
    scan_complete: bool
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        """Return a deterministic digest for conditional reads."""
        return sha256(
            json.dumps(
                self.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the stable evidence-trace response."""
        return {
            "schema_version": EVIDENCE_TRACE_SCHEMA_VERSION,
            "report_record_id": self.report_record_id,
            "report_digest": self.report_digest,
            "candidate": {
                "id": self.candidate_identity,
                "digest": self.candidate_digest,
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "unresolved": list(self.unresolved),
            "workspace_scan": {
                "records_scanned": self.records_scanned,
                "records_available": self.records_available,
                "complete": self.scan_complete,
            },
            "assurance_summary": {
                "receipts_resolved": sum(
                    1 for node in self.nodes if node.kind == "workspace-record"
                ),
                "receipt_integrity_verified": sum(
                    1
                    for node in self.nodes
                    if node.kind == "workspace-record"
                    and node.receipt_integrity_status == "verified"
                ),
                "artifact_integrity_verified": sum(
                    1
                    for node in self.nodes
                    if node.kind == "workspace-record"
                    and node.artifact_integrity_status == "verified"
                ),
                "admission_verified": sum(
                    1
                    for node in self.nodes
                    if node.kind == "workspace-record"
                    and node.admission_status == "verified"
                ),
            },
            "producer_authentication": {
                "status": "not-recorded",
                "authenticated": None,
                "reason": (
                    "Workspace evidence receipts do not persist detached producer "
                    "signatures or independently configured trust keys; producer identity "
                    "must not be promoted to authenticated producer evidence."
                ),
            },
            "limitations": list(self.limitations),
        }


def build_evidence_trace(
    report: ReliabilityVerificationReport,
    source: ReportSourceContext,
    records: tuple[EvidenceTraceRecord, ...],
    *,
    records_scanned: int,
    records_available: int,
    scan_complete: bool,
    max_nodes: int,
) -> EvidenceTraceProjection:
    """Build a bounded graph using only recorded fields and exact identity equality."""
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")

    nodes: dict[tuple[str, str], EvidenceTraceNode] = {}
    edge_counts: dict[tuple[str, str, str, str], int] = {}

    def _add_node(
        kind: str,
        identity: str,
        label: str,
        *,
        digest: str | None = None,
        digest_kind: str | None = None,
        integrity_status: str = "recorded",
        availability: str = "recorded",
        record_id: str | None = None,
        producer_id: str | None = None,
        producer_type: str | None = None,
        captured_at: str | None = None,
        run_id: str | None = None,
        source_event_id: str | None = None,
        artifact_size: int | None = None,
        receipt_digest: str | None = None,
        receipt_integrity_status: str | None = None,
        artifact_integrity_status: str | None = None,
        admission_status: str | None = None,
        admission_digest: str | None = None,
        producer_authentication_status: str | None = None,
    ) -> EvidenceTraceNode:
        key = (kind, identity)
        existing = nodes.get(key)
        if existing is not None:
            return existing
        if len(nodes) >= max_nodes:
            raise OverflowError("evidence trace exceeds configured node limit")
        node = EvidenceTraceNode(
            node_id=_stable_id(kind, identity),
            kind=kind,
            identity=identity,
            label=label,
            digest=digest,
            digest_kind=digest_kind,
            integrity_status=integrity_status,
            availability=availability,
            record_id=record_id,
            producer_id=producer_id,
            producer_type=producer_type,
            captured_at=captured_at,
            run_id=run_id,
            source_event_id=source_event_id,
            artifact_size=artifact_size,
            receipt_digest=receipt_digest,
            receipt_integrity_status=receipt_integrity_status,
            artifact_integrity_status=artifact_integrity_status,
            admission_status=admission_status,
            admission_digest=admission_digest,
            producer_authentication_status=producer_authentication_status,
        )
        nodes[key] = node
        return node

    def _add_edge(
        source_node: EvidenceTraceNode,
        target_node: EvidenceTraceNode,
        relationship_type: str,
        basis: str,
    ) -> None:
        key = (
            source_node.node_id,
            target_node.node_id,
            relationship_type,
            basis,
        )
        edge_counts[key] = edge_counts.get(key, 0) + 1

    report_node = _add_node(
        "verification-report",
        source.record_id,
        "Verification report",
        digest=report.digest,
        digest_kind="report-digest",
        integrity_status="verified",
        availability="present",
        record_id=source.record_id,
        producer_id=source.producer_id,
        producer_type=source.producer_type,
        captured_at=source.captured_at,
        run_id=source.run_id,
    )
    report_artifact = _add_node(
        "artifact-digest",
        source.artifact_digest,
        "Report artifact",
        digest=source.artifact_digest,
        digest_kind="artifact-sha256",
        integrity_status="verified",
        availability="present",
    )
    _add_edge(
        report_node,
        report_artifact,
        "stores-report-artifact",
        "receipt.artifact_digest",
    )

    candidate = _add_node(
        "candidate",
        report.candidate_identity,
        "Candidate",
        digest=report.candidate_digest,
        digest_kind="candidate-digest",
    )
    _add_edge(
        report_node,
        candidate,
        "describes-candidate",
        "report.candidate_identity + report.candidate_digest",
    )

    if report.profile_evaluation_digest is not None:
        evaluation = _add_node(
            "profile-evaluation",
            report.profile_evaluation_digest,
            "Profile evaluation",
            digest=report.profile_evaluation_digest,
            digest_kind="profile-evaluation-digest",
        )
        _add_edge(
            report_node,
            evaluation,
            "references-profile-evaluation",
            "report.profile_evaluation_digest",
        )

    if source.run_id is not None:
        run_node = _add_node("run", source.run_id, "Report run")
        _add_edge(report_node, run_node, "captured-in-run", "receipt.run_id")

    source_nodes: dict[str, EvidenceTraceNode] = {}
    for identity in report.source_identities:
        source_node = _add_node("source-identity", identity, "Source identity")
        source_nodes[identity] = source_node
        _add_edge(
            report_node,
            source_node,
            "references-source-identity",
            "report.source_identities",
        )

    artifact_nodes: dict[str, EvidenceTraceNode] = {}
    for digest in report.artifact_digests:
        artifact_node = _add_node(
            "artifact-digest",
            digest,
            "Referenced artifact",
            digest=digest,
            digest_kind="artifact-sha256",
        )
        artifact_nodes[digest] = artifact_node
        _add_edge(
            report_node,
            artifact_node,
            "references-artifact-digest",
            "report.artifact_digests",
        )

    for status, values in (
        ("included", report.evidence_included),
        ("missing", report.evidence_missing),
        ("omitted", report.evidence_omitted),
    ):
        for identity in values:
            evidence_node = _add_node(
                "evidence-requirement",
                f"{status}:{identity}",
                f"Evidence {status}",
            )
            _add_edge(
                report_node,
                evidence_node,
                f"evidence-{status}",
                f"report.evidence_{status}",
            )

    matched_sources: set[str] = set()
    matched_artifacts: set[str] = set()
    for record in records:
        record_node = _add_node(
            "workspace-record",
            record.record_id,
            record.producer_type,
            digest=record.artifact_digest,
            digest_kind="artifact-sha256",
            integrity_status=record.admission_status,
            availability=(
                "present"
                if record.artifact_integrity_status != "unavailable"
                else "missing"
            ),
            record_id=record.record_id,
            producer_id=record.producer_id,
            producer_type=record.producer_type,
            captured_at=record.captured_at,
            run_id=record.run_id,
            source_event_id=record.source_event_id,
            artifact_size=record.artifact_size,
            receipt_digest=record.receipt_digest,
            receipt_integrity_status=record.receipt_integrity_status,
            artifact_integrity_status=record.artifact_integrity_status,
            admission_status=record.admission_status,
            admission_digest=record.admission_digest,
            producer_authentication_status=record.producer_authentication_status,
        )
        record_artifact_node = artifact_nodes.get(record.artifact_digest)
        if record_artifact_node is not None:
            matched_artifacts.add(record.artifact_digest)
            _add_edge(
                record_artifact_node,
                record_node,
                "recorded-by-workspace-receipt",
                "exact artifact_digest equality",
            )
        if record.admission_digest is not None:
            admission_node = _add_node(
                "evidence-admission",
                record.admission_digest,
                "Evidence admission",
                digest=record.admission_digest,
                digest_kind="admission-digest",
                integrity_status=record.admission_status,
                availability="present",
            )
            _add_edge(
                record_node,
                admission_node,
                "verified-by-evidence-admission",
                "ExternalEvidenceAdmission deterministic receipt/artifact binding",
            )
            if record_artifact_node is not None:
                _add_edge(
                    admission_node,
                    record_artifact_node,
                    "binds-admitted-artifact",
                    "admission.evidence_reference.digest",
                )
        for record_identity, basis_field in (
            (record.record_id, "receipt_id"),
            (record.source_event_id, "source_event_id"),
            (record.run_id, "run_id"),
        ):
            if record_identity is None:
                continue
            record_source_node = source_nodes.get(record_identity)
            if record_source_node is not None:
                matched_sources.add(record_identity)
                _add_edge(
                    record_source_node,
                    record_node,
                    "resolves-to-workspace-record",
                    f"exact {basis_field} equality",
                )
        if record.run_id is not None:
            run_node = _add_node("run", record.run_id, "Workspace run")
            _add_edge(
                record_node,
                run_node,
                "captured-in-run",
                "receipt.run_id",
            )

    unresolved: list[dict[str, str]] = []
    unresolved.extend(
        {
            "kind": "source-identity",
            "identity": identity,
            "reason": (
                "no matching workspace receipt was found in the bounded scan"
                if scan_complete
                else "not resolved within the bounded workspace receipt scan"
            ),
        }
        for identity in source_nodes
        if identity not in matched_sources
    )
    unresolved.extend(
        {
            "kind": "artifact-digest",
            "identity": digest,
            "reason": (
                "no matching workspace receipt was found in the bounded scan"
                if scan_complete
                else "not resolved within the bounded workspace receipt scan"
            ),
        }
        for digest in artifact_nodes
        if digest not in matched_artifacts
    )
    unresolved.extend(
        {
            "kind": "missing-evidence",
            "identity": identity,
            "reason": (
                "the canonical report records this evidence requirement as missing"
            ),
        }
        for identity in report.evidence_missing
    )

    edges = tuple(
        EvidenceTraceEdge(
            edge_id=sha256(
                json.dumps(
                    {
                        "source": key[0],
                        "target": key[1],
                        "type": key[2],
                        "basis": key[3],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            source=key[0],
            target=key[1],
            relationship_type=key[2],
            basis=key[3],
            occurrences=count,
        )
        for key, count in sorted(edge_counts.items())
    )
    limitations = [
        (
            "This projection shows only relationships explicitly recorded in the "
            "canonical report or receipt fields, plus exact-identity workspace "
            "resolution."
        ),
        (
            "An edge is descriptive evidence lineage; it does not imply causality, "
            "factual correctness, authorization, or approval."
        ),
        (
            "Arbitrary receipt metadata and artifact payload bytes are not exposed "
            "by this UI projection."
        ),
        (
            "Producer identifiers are recorded assertions, not authentication. This "
            "workspace does not persist detached producer signatures or independent "
            "producer trust keys, so producer authentication is reported as not-recorded."
        ),
    ]
    if not scan_complete:
        limitations.append(
            "Workspace receipt resolution is partial because the configured bounded "
            "scan limit was reached."
        )
    return EvidenceTraceProjection(
        report_record_id=source.record_id,
        report_digest=report.digest,
        candidate_identity=report.candidate_identity,
        candidate_digest=report.candidate_digest,
        nodes=tuple(nodes.values()),
        edges=edges,
        unresolved=tuple(unresolved),
        records_scanned=records_scanned,
        records_available=records_available,
        scan_complete=scan_complete,
        limitations=tuple(limitations),
    )


__all__ = [
    "EVIDENCE_TRACE_SCHEMA_VERSION",
    "EvidenceTraceEdge",
    "EvidenceTraceNode",
    "EvidenceTraceProjection",
    "EvidenceTraceRecord",
    "build_evidence_trace",
]
