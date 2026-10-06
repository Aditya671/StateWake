"""Opinionated release-proof workflow over existing StateWake authorities."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from ..adapters.human_approval import WorkspaceHumanApprovalStore
from ..domain.operations import OperationalBundle
from ..domain.reliability_claim_profile import ReliabilityClaimProfile
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_verification_report import ReliabilityVerificationReport
from ..reports.json_report import render_json_report
from ..reports.markdown import render_markdown_report
from ..services.persistence import atomic_write_text
from ..services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    evaluate_claim_profile,
    load_claim_profile,
)
from ..services.reliability_evidence_service import (
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)
from ..services.reliability_proof_bundle_service import build_reliability_proof_bundle
from ..utils.json_support import loads_object


def _default_release_proof_profile() -> ReliabilityClaimProfile:
    """Return the legacy release-proof profile used by the existing workflow.

    The Phase 2 release profile remains available for AI release-evidence
    claims. This helper preserves the older proof-bundle workflow whose input
    chain predates AI contracts.
    """
    return ReliabilityClaimProfile(
        profile_id="release-evidence-complete",
        version="1",
        title="Release evidence complete",
        description=(
            "Legacy release-proof workflow requiring the core reliability "
            "evidence chain without requiring Phase 1 AI contracts."
        ),
        required_evidence_kinds=("run", "state", "provenance", "integrity"),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review", "reject"),
        required_reconciliation_states=("verified", "recovered"),
        required_reliability_states=("reliable", "recovered"),
        caveats=("Release authorization remains a separate human decision.",),
    )


def _source_identities(chain: ReliabilityEvidenceChain) -> tuple[str, ...]:
    """Return the source identities associated with the release proof."""
    refs = (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
        chain.decision_basis_ref,
        chain.comparison_ref,
        chain.reconciliation_binding_ref,
    )
    return tuple(ref.identity for ref in refs if ref is not None)


_MAX_APPROVAL_BASIS_REPORT_BYTES = 2_000_000
_MAX_APPROVAL_AUTHORITY_TEXT = 512


def _approval_reconciliation_requested(
    *,
    basis_report_path: Path | None,
    workspace_path: Path | None,
    record_id: str | None,
    producer_id: str | None,
    approval_action: str | None,
    scope: str | None,
) -> bool:
    """Return whether any canonical human-approval reconciliation input was supplied."""
    return any(
        value is not None
        for value in (
            basis_report_path,
            workspace_path,
            record_id,
            producer_id,
            approval_action,
            scope,
        )
    )


def _validate_approval_reconciliation_inputs(
    *,
    basis_report_path: Path | None,
    workspace_path: Path | None,
    record_id: str | None,
    producer_id: str | None,
    approval_action: str | None,
    scope: str | None,
    report_path: Path | None,
) -> bool:
    """Validate the all-or-nothing approval re-evaluation boundary."""
    if not _approval_reconciliation_requested(
        basis_report_path=basis_report_path,
        workspace_path=workspace_path,
        record_id=record_id,
        producer_id=producer_id,
        approval_action=approval_action,
        scope=scope,
    ):
        return False
    required = {
        "approval_basis_report_path": basis_report_path,
        "approval_workspace_path": workspace_path,
        "approval_record_id": record_id,
        "approval_producer_id": producer_id,
        "approval_action": approval_action,
        "approval_scope": scope,
        "report_path": report_path,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "human approval reconciliation requires: " + ", ".join(missing)
        )
    assert basis_report_path is not None
    assert report_path is not None
    if basis_report_path.expanduser().resolve() == report_path.expanduser().resolve():
        raise ValueError(
            "approval basis report and re-evaluated report output must be different paths"
        )
    for name, value in (
        ("approval_record_id", record_id),
        ("approval_producer_id", producer_id),
        ("approval_action", approval_action),
        ("approval_scope", scope),
    ):
        assert value is not None
        if not value.strip() or len(value) > _MAX_APPROVAL_AUTHORITY_TEXT:
            raise ValueError(
                f"{name} must be non-empty and at most {_MAX_APPROVAL_AUTHORITY_TEXT} characters"
            )
    return True


def _load_approval_basis_report(path: Path) -> ReliabilityVerificationReport:
    """Load one immutable report basis with a bounded, digest-verifying parser."""
    if path.stat().st_size > _MAX_APPROVAL_BASIS_REPORT_BYTES:
        raise ValueError("approval basis report exceeds the configured read bound")
    payload = loads_object(path.read_bytes(), field="approval basis report")
    return ReliabilityVerificationReport.from_dict(payload)


def _report_basis_payload(report: ReliabilityVerificationReport) -> dict[str, object]:
    """Return machine-verification fields that must remain stable across approval."""
    payload = dict(report.payload())
    payload.pop("generated_at", None)
    return payload


def _append_unique(values: tuple[str, ...], *extra: str) -> tuple[str, ...]:
    """Append non-empty strings while preserving deterministic first occurrence."""
    return tuple(dict.fromkeys((*values, *(value for value in extra if value))))


def _reconcile_human_approval(
    report: ReliabilityVerificationReport,
    *,
    basis_report_path: Path,
    workspace_path: Path,
    record_id: str,
    producer_id: str,
    approval_action: str,
    scope: str,
) -> ReliabilityVerificationReport:
    """Re-evaluate one release report against canonical approval evidence."""
    basis = _load_approval_basis_report(basis_report_path)
    if basis.report_type != "release":
        raise ValueError("human approval basis must be a release verification report")
    if not basis.verified:
        raise ValueError("human approval basis must be a verified release report")
    if basis.approval_status != "requires-human-approval":
        raise ValueError(
            "human approval basis must require human approval before reconciliation"
        )
    if _report_basis_payload(report) != _report_basis_payload(basis):
        raise ValueError(
            "fresh release-proof verification no longer matches the approved report basis"
        )

    lifecycle = WorkspaceHumanApprovalStore(workspace_path).lifecycle_for_target(
        record_id, report_digest=basis.digest
    )
    matching = []
    inactive_matching = []
    for item in lifecycle:
        record = item.approval
        contract = record.contract
        metadata = contract.metadata or {}
        receipt_metadata = record.receipt.metadata
        if (
            metadata.get("target_record_id") != record_id
            or metadata.get("candidate_identity") != basis.candidate_identity
            or metadata.get("candidate_digest") != basis.candidate_digest
            or metadata.get("profile_id") != basis.profile_id
            or metadata.get("profile_version") != basis.profile_version
            or receipt_metadata.get("candidate_digest") != basis.candidate_digest
        ):
            raise ValueError(
                "canonical human approval metadata does not match the approved report basis"
            )
        if (
            contract.producer_id == producer_id
            and contract.approval_action == approval_action
            and contract.scope == scope
        ):
            if item.status == "active":
                matching.append(record)
            else:
                inactive_matching.append(item.status)
    if not matching:
        if inactive_matching:
            states = ", ".join(sorted(set(inactive_matching)))
            raise ValueError(
                "no active canonical human approval matches the expected producer, "
                f"action, and scope; matching historical approval state: {states}"
            )
        raise ValueError(
            "no canonical human approval matches the expected producer, action, and scope"
        )
    matching.sort(key=lambda item: item.receipt.receipt_id)

    approval_receipt_ids = tuple(item.receipt.receipt_id for item in matching)
    approval_digests = tuple(
        digest
        for item in matching
        for digest in (item.receipt.digest, item.receipt.artifact_digest)
    )
    scope_note = (
        f"Canonical human approval was reconciled for action {approval_action!r} "
        f"within scope {scope!r}."
    )
    return replace(
        report,
        approval_status="approved",
        evidence_included=_append_unique(
            report.evidence_included, "human_approval_contract"
        ),
        checks_passed=_append_unique(
            report.checks_passed,
            "human_approval_basis_report_verified",
            "human_approval_machine_basis_revalidated",
            "human_approval_contract_integrity_verified",
            "human_approval_lifecycle_active_verified",
            "human_approval_recorded_authority_scope_matched",
        ),
        source_identities=_append_unique(
            report.source_identities,
            *(f"human-approval-receipt:{value}" for value in approval_receipt_ids),
        ),
        artifact_digests=_append_unique(
            report.artifact_digests, basis.digest, *approval_digests
        ),
        caveats=_append_unique(
            report.caveats,
            scope_note,
            (
                "Approval reconciliation verifies canonical stored evidence, exact report "
                "binding, and current active lifecycle state; it does not independently "
                "re-authenticate the human actor or expand the recorded action and scope."
            ),
        ),
        residual_risks=(
            "External correctness and publication execution remain outside this verification report.",
        ),
        human_decisions_required=(scope_note,),
        allowed_use=_append_unique(
            report.allowed_use,
            "Use the reconciled approval only for its exact recorded action and scope.",
        ),
        prohibited_use=_append_unique(
            report.prohibited_use,
            "Do not treat this approval as authorization for publication or side effects outside its recorded scope.",
        ),
        machine_readable_appendix=_append_unique(
            report.machine_readable_appendix, "human_approval_contract"
        ),
    )


def build_release_proof(
    *,
    attestation_path: Path,
    evidence_chain_path: Path,
    history_path: Path,
    evidence_root: Path,
    output: Path,
    profile: ReliabilityClaimProfile | None = None,
    profile_path: Path | None = None,
    report_path: Path | None = None,
    signed_attestation_path: Path | None = None,
    attestation_store_path: Path | None = None,
    attestation_trust_state_path: Path | None = None,
    attestation_trust_history_path: Path | None = None,
    attestation_authority_store_path: Path | None = None,
    approval_basis_report_path: Path | None = None,
    approval_workspace_path: Path | None = None,
    approval_record_id: str | None = None,
    approval_producer_id: str | None = None,
    approval_action: str | None = None,
    approval_scope: str | None = None,
) -> tuple[OperationalBundle, ReliabilityVerificationReport, ClaimProfileEvaluation]:
    """Verify, apply a bounded claim profile, then emit the existing portable proof bundle."""
    reconcile_approval = _validate_approval_reconciliation_inputs(
        basis_report_path=approval_basis_report_path,
        workspace_path=approval_workspace_path,
        record_id=approval_record_id,
        producer_id=approval_producer_id,
        approval_action=approval_action,
        scope=approval_scope,
        report_path=report_path,
    )
    if profile is not None and profile_path is not None:
        raise ValueError("profile and profile_path are mutually exclusive")
    selected = profile or (
        load_claim_profile(profile_path)
        if profile_path is not None
        else _default_release_proof_profile()
    )
    chain = load_reliability_evidence_chain(evidence_chain_path)
    verify_reliability_evidence_chain(chain, root=evidence_root)
    evaluation = evaluate_claim_profile(chain, selected)
    if not evaluation.satisfied:
        raise ValueError(
            "claim profile was not satisfied: "
            + "; ".join(evaluation.failed_conditions)
        )
    bundle, verification = build_reliability_proof_bundle(
        attestation_path=attestation_path,
        evidence_chain_path=evidence_chain_path,
        history_path=history_path,
        evidence_root=evidence_root,
        output=output,
        signed_attestation_path=signed_attestation_path,
        attestation_store_path=attestation_store_path,
        attestation_trust_state_path=attestation_trust_state_path,
        attestation_trust_history_path=attestation_trust_history_path,
        attestation_authority_store_path=attestation_authority_store_path,
    )
    signed_trust_requested = (
        signed_attestation_path is not None
        or attestation_store_path is not None
        or attestation_trust_history_path is not None
    )
    canonical_signed_trust_requested = (
        attestation_store_path is not None or attestation_trust_history_path is not None
    )
    trust_checks: tuple[str, ...] = (
        ("signed_attestation_trust_verified",) if signed_trust_requested else ()
    )
    if canonical_signed_trust_requested and attestation_trust_history_path is not None:
        trust_checks += ("historical_signing_trust_state_resolved",)
    present_kinds = set()
    for ref in (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
    ):
        if ref is not None:
            present_kinds.add(ref.kind)
    evidence_omitted = tuple(
        kind for kind in selected.required_evidence_kinds if kind not in present_kinds
    )
    report = ReliabilityVerificationReport(
        format_version="1",
        claim=selected.title,
        decision=chain.decision,
        profile_id=selected.profile_id,
        profile_version=selected.version,
        verified=verification.verified and evaluation.satisfied,
        candidate_identity=chain.chain_id,
        candidate_digest=chain.digest(),
        report_type="release",
        evidence_included=(
            tuple(
                ref.kind
                for ref in (
                    chain.run,
                    chain.state,
                    *chain.evidence,
                    chain.provenance,
                    chain.integrity,
                )
                if ref is not None
            )
            + (("signed_attestation_trust_context",) if signed_trust_requested else ())
        ),
        evidence_omitted=evidence_omitted,
        evidence_missing=evidence_omitted,
        checks_passed=(
            tuple(evaluation.passed_conditions) + verification.checks + trust_checks
        ),
        checks_failed=tuple(evaluation.failed_conditions) + verification.failures,
        source_identities=_source_identities(chain),
        rationale=chain.decision_rationale,
        caveats=(
            "Verification establishes integrity and binding of supplied evidence; "
            "it does not establish external correctness of the AI system.",
            *(
                (
                    "Signed attestation verification establishes signature, signing-key, "
                    "and exact trust-state binding; it does not establish signer honesty "
                    "or human release authorization.",
                )
                if signed_trust_requested
                else ()
            ),
            *evaluation.caveats,
        ),
        residual_risks=(
            "External correctness and release authorization remain outside "
            "this verification report.",
        ),
        human_decisions_required=("Human release approval",),
        allowed_use=("Use as release evidence input for human review.",),
        prohibited_use=("Do not treat this report as release approval.",),
        machine_readable_appendix=(
            "reliability_evidence_chain",
            "claim_profile_evaluation",
            *(("signed_attestation_trust_context",) if signed_trust_requested else ()),
        ),
        artifact_digests=(chain.digest(), verification.digest),
        profile_evaluation_digest=sha256(
            json.dumps(
                evaluation.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        approval_status="requires-human-approval",
        recovery_status=chain.reconciliation_state,
        verifier_version="statewake-" + __import__("statewake").__version__,
        generated_at=datetime.now(UTC).isoformat(),
    )
    if reconcile_approval:
        assert approval_basis_report_path is not None
        assert approval_workspace_path is not None
        assert approval_record_id is not None
        assert approval_producer_id is not None
        assert approval_action is not None
        assert approval_scope is not None
        report = _reconcile_human_approval(
            report,
            basis_report_path=approval_basis_report_path,
            workspace_path=approval_workspace_path,
            record_id=approval_record_id,
            producer_id=approval_producer_id,
            approval_action=approval_action,
            scope=approval_scope,
        )
    if report_path is not None:
        write_verification_report(report, report_path)
    return bundle, report, evaluation


def write_verification_report(
    report: ReliabilityVerificationReport, path: Path
) -> None:
    """Persist a human-readable verification report atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_json_report(report))
    atomic_write_text(path.with_suffix(".md"), render_verification_report(report))


def render_verification_report(report: ReliabilityVerificationReport) -> str:
    """Render a human-readable verification report."""
    return render_markdown_report(report)
