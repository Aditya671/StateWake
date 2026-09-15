"""Command-line interface for the stabilized StateWake reliability lifecycle."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Final, Protocol

from statewake import __version__
from statewake.services.reliability_decision_basis_service import (
    prepare_reliability_decision_basis,
)
from statewake.services.reliability_outcome_verification_service import (
    verify_reliability_outcome,
)
from statewake.utils.json_support import metadata_from_cli
from statewake.utils.time import parse_datetime

from ..adapters.reliability_attestation import JsonlReliabilityOutcomeAttestationStore
from ..adapters.reliability_state import JsonlReliabilityStateStore
from ..services.evidence_admission_service import admit_external_evidence
from ..services.evidence_ingestion_service import (
    ingest_evidence_file,
    load_evidence_receipt,
    verify_evidence_receipt,
)
from ..services.release_proof_service import build_release_proof
from ..services.reliability_attestation_service import (
    attest_reliability_outcome,
    load_reliability_outcome_attestation,
    verify_reliability_outcome_binding,
    write_reliability_outcome_attestation,
)
from ..services.reliability_claim_profile_service import (
    get_builtin_claim_profile,
    load_claim_profile,
)
from ..services.reliability_comparison_service import (
    build_reliability_behavioral_comparison,
    load_reliability_behavioral_comparison,
    verify_reliability_behavioral_comparison,
)
from ..services.reliability_evidence_service import (
    build_reliability_evidence_chain,
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
    write_reliability_evidence_chain,
)
from ..services.reliability_lineage_service import build_reliability_lineage_closure
from ..services.reliability_proof_bundle_service import (
    build_reliability_proof_bundle,
    verify_reliability_proof_bundle,
)
from ..services.reliability_reconciliation_binding_service import (
    build_reliability_reconciliation_binding,
    load_reliability_reconciliation_binding,
    verify_reliability_reconciliation_binding,
)
from ..services.reliability_recovery_service import verify_reliability_recovery_outcome
from ..services.reliability_state_service import (
    current_reliability_state,
    reliability_state_history,
    transition_reliability_state_from_file,
)

SUPPORTED_COMMANDS: Final[tuple[str, ...]] = (
    "version",
    "evidence-ingest",
    "evidence-verify",
    "evidence-admission-verify",
    "reliability-comparison",
    "reliability-comparison-verify",
    "evidence-chain",
    "reliability-state-transition",
    "reliability-state",
    "reliability-attest",
    "reliability-attest-verify",
    "reliability-outcome-verify",
    "reliability-recovery-verify",
    "reliability-lineage-verify",
    "reliability-reconciliation-bind",
    "reliability-reconciliation-verify",
    "reliability-proof-bundle",
    "reliability-proof-verify",
    "reliability-proof-completeness-verify",
    "reliability-decision-basis-build",
    "release-proof",
)


class _ParserAdder(Protocol):
    """Expose only the public parser-registration API needed by helpers."""

    def add_parser(
        self,
        name: str,
        *,
        help: str | None = None,  # noqa: A002
    ) -> argparse.ArgumentParser:
        """Register and return a public subcommand parser."""
        ...


def supported_commands() -> tuple[str, ...]:
    """Return the stable list of supported top-level CLI commands."""
    return SUPPORTED_COMMANDS


def _json(value: object) -> None:
    """Print a JSON value in the CLI's stable machine-readable format."""
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _optional_path(value: str | None) -> Path | None:
    """Convert an optional command-line value to a path."""
    return None if value is None else Path(value)


def _add_evidence_ingest_parser(subparsers: _ParserAdder) -> None:
    """Register the evidence-ingest command."""
    parser = subparsers.add_parser(
        "evidence-ingest", help="Ingest an evidence artifact and emit a receipt."
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--artifact-store", type=Path, required=True)
    parser.add_argument("--receipt-store", type=Path, required=True)
    parser.add_argument("--producer-type", required=True)
    parser.add_argument("--producer-id", required=True)
    parser.add_argument("--producer-version")
    parser.add_argument("--source-ref")
    parser.add_argument("--source-event-id")
    parser.add_argument("--run-id")
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--metadata", action="append", default=[])


def _add_evidence_chain_parser(subparsers: _ParserAdder) -> None:
    """Register the evidence-chain command."""
    parser = subparsers.add_parser(
        "evidence-chain", help="Build and persist an evidence chain."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--state-id", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--evidence-receipt", action="append", default=[])
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--integrity", type=Path, required=True)
    parser.add_argument(
        "--verification-status",
        choices=("unverified", "verified", "failed"),
        default="verified",
    )
    parser.add_argument(
        "--reliability-state",
        choices=("unknown", "reliable", "degraded", "unreliable", "recovered"),
        default="reliable",
    )
    parser.add_argument(
        "--reconciliation-state",
        choices=("pending", "verified", "stale", "missing", "invalid", "recovered"),
        default="verified",
    )
    parser.add_argument("--reconciliation")
    parser.add_argument("--recovery")
    parser.add_argument("--attestation")
    parser.add_argument("--decision-basis", type=Path)
    parser.add_argument(
        "--decision-basis-kind",
        choices=("decision-basis", "policy"),
        default="decision-basis",
    )
    parser.add_argument("--comparison", type=Path)
    parser.add_argument("--reconciliation-binding", type=Path)
    parser.add_argument(
        "--decision",
        choices=("undecided", "accept", "review", "reject"),
        default="accept",
    )
    parser.add_argument("--rationale", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)


def _add_state_and_attestation_parsers(subparsers: _ParserAdder) -> None:
    """Register state and attestation lifecycle commands."""
    parser = subparsers.add_parser("reliability-state-transition")
    parser.add_argument("subject_id")
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--occurred-at")
    parser.add_argument("--rationale", action="append", default=[])

    parser = subparsers.add_parser("reliability-state")
    parser.add_argument("subject_id")
    parser.add_argument("--history", type=Path, required=True)

    parser = subparsers.add_parser("reliability-attest")
    parser.add_argument("subject_id")
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--attestation-store", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--occurred-at")
    parser.add_argument("--output", type=Path)

    parser = subparsers.add_parser("reliability-attest-verify")
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--subject-id", required=True)

    parser = subparsers.add_parser("reliability-outcome-verify")
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)


def _add_proof_parsers(subparsers: _ParserAdder) -> None:
    """Register proof, recovery, and decision-basis commands."""
    parser = subparsers.add_parser("reliability-recovery-verify")
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)

    parser = subparsers.add_parser("reliability-lineage-verify")
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)

    parser = subparsers.add_parser("reliability-reconciliation-bind")
    parser.add_argument("comparison", type=Path)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("--output", type=Path, required=True)

    parser = subparsers.add_parser("reliability-reconciliation-verify")
    parser.add_argument("binding", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("reconciliation", type=Path)
    parser.add_argument("--root", type=Path)

    parser = subparsers.add_parser("reliability-proof-bundle")
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signed-attestation", type=Path)
    parser.add_argument("--attestation-trust-state", type=Path)
    parser.add_argument("--attestation-authority-store", type=Path)

    parser = subparsers.add_parser("reliability-proof-verify")
    parser.add_argument("bundle", type=Path)

    parser = subparsers.add_parser("reliability-proof-completeness-verify")
    parser.add_argument("bundle", type=Path)

    parser = subparsers.add_parser("reliability-decision-basis-build")
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-basis", type=Path, required=True)
    parser.add_argument("--output-chain", type=Path, required=True)
    parser.add_argument("--profile", default="release-evidence-complete")

    parser = subparsers.add_parser("release-proof")
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--report", type=Path)


def build_parser() -> argparse.ArgumentParser:
    """Build the stabilized public CLI parser."""
    parser = argparse.ArgumentParser(
        prog="statewake",
        description="""
        Verify evidence, reliability state, decisions, recovery, and portable proof.
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("version", help="Print the installed StateWake version.")

    evidence = subparsers.add_parser(
        "evidence-verify", help="Verify a persisted evidence receipt."
    )
    evidence.add_argument("path", type=Path)
    evidence.add_argument("--artifact-store", type=Path, required=True)
    evidence.add_argument("--receipt-store", type=Path, required=True)

    admission = subparsers.add_parser(
        "evidence-admission-verify", help="Verify an evidence admission boundary."
    )
    admission.add_argument("--receipt", type=Path, required=True)
    admission.add_argument("--artifact", type=Path, required=True)
    admission.add_argument("--receipt-file", type=Path)
    admission.add_argument("--run-id")
    admission.add_argument("--producer-type")
    admission.add_argument("--producer-id")

    comparison = subparsers.add_parser(
        "reliability-comparison", help="Build a behavioral comparison artifact."
    )
    comparison.add_argument("before_state", type=Path)
    comparison.add_argument("after_state", type=Path)
    comparison.add_argument("--output", type=Path, required=True)
    comparison.add_argument("--before-evidence", type=Path)
    comparison.add_argument("--after-evidence", type=Path)
    comparison.add_argument("--before-events", type=Path)
    comparison.add_argument("--before-run-id")
    comparison.add_argument("--after-events", type=Path)
    comparison.add_argument("--after-run-id")

    comparison_verify = subparsers.add_parser("reliability-comparison-verify")
    comparison_verify.add_argument("comparison", type=Path)
    comparison_verify.add_argument("--root", type=Path)

    _add_evidence_ingest_parser(subparsers)
    _add_evidence_chain_parser(subparsers)
    _add_state_and_attestation_parsers(subparsers)
    _add_proof_parsers(subparsers)
    return parser


def _run_evidence_ingest(args: argparse.Namespace) -> None:
    """Execute evidence ingestion from the CLI."""
    metadata = metadata_from_cli(args.metadata)
    receipt = ingest_evidence_file(
        args.artifact,
        artifact_store_root=args.artifact_store,
        receipt_store_root=args.receipt_store,
        producer_type=args.producer_type,
        producer_id=args.producer_id,
        producer_version=args.producer_version,
        source_ref=args.source_ref,
        source_event_id=args.source_event_id,
        run_id=args.run_id,
        captured_at=parse_datetime(args.captured_at, field="captured_at"),
        metadata=metadata,
    )
    _json(receipt.to_dict())


def _run_evidence_chain(args: argparse.Namespace) -> None:
    """Execute evidence-chain construction from the CLI."""
    receipts = dict(
        zip(args.evidence, (Path(item) for item in args.evidence_receipt), strict=False)
    )
    chain = build_reliability_evidence_chain(
        run_id=args.run_id,
        run_path=args.run,
        state_id=args.state_id,
        state_path=args.state,
        evidence_paths=tuple(args.evidence),
        provenance_path=args.provenance,
        integrity_proof_path=args.integrity,
        verification_status=args.verification_status,
        reliability_state=args.reliability_state,
        reconciliation_state=args.reconciliation_state,
        reconciliation_path=_optional_path(args.reconciliation),
        recovery_path=_optional_path(args.recovery),
        attestation_path=_optional_path(args.attestation),
        decision_basis_path=args.decision_basis,
        decision_basis_kind=args.decision_basis_kind,
        comparison_path=args.comparison,
        reconciliation_binding_path=args.reconciliation_binding,
        decision=args.decision,
        rationale=tuple(args.rationale),
        evidence_receipt_paths=receipts,
    )
    write_reliability_evidence_chain(chain, args.output)
    _json(chain.to_dict())


def _run_state_transition(args: argparse.Namespace) -> None:
    """Execute a reliability-state transition from the CLI."""
    occurred_at = (
        None
        if args.occurred_at is None
        else parse_datetime(args.occurred_at, field="occurred_at")
    )
    transition = transition_reliability_state_from_file(
        args.subject_id,
        args.chain,
        history_path=args.history,
        actor=args.actor,
        evidence_root=args.evidence_root,
        occurred_at=occurred_at,
        rationale=tuple(args.rationale),
    )
    _json(transition.to_dict())


def _run_attestation(args: argparse.Namespace) -> None:
    """Create a reliability outcome attestation from authoritative state."""
    chain = load_reliability_evidence_chain(args.chain)
    history = JsonlReliabilityStateStore(args.history).read(args.subject_id)
    transition = next(
        (
            item
            for item in reversed(history)
            if item.evidence_chain_id == chain.chain_id
        ),
        None,
    )
    if transition is None:
        raise ValueError(
            f"no reliability-state transition found for evidence chain {chain.chain_id}"
        )
    occurred_at = (
        None
        if args.occurred_at is None
        else parse_datetime(args.occurred_at, field="occurred_at")
    )
    attestation = attest_reliability_outcome(
        chain,
        transition,
        actor=args.actor,
        store=JsonlReliabilityOutcomeAttestationStore(args.attestation_store),
        occurred_at=occurred_at,
    )
    if args.output is not None:
        write_reliability_outcome_attestation(attestation, args.output)
    _json(attestation.to_dict())


def _run_dispatch(args: argparse.Namespace) -> None:
    """Dispatch a parsed CLI command to its implementation."""
    handlers: dict[str, Callable[[argparse.Namespace], None]] = {
        "version": lambda _: print(__version__),
        "evidence-ingest": _run_evidence_ingest,
        "evidence-verify": lambda a: _run_evidence_verify(a),
        "evidence-admission-verify": lambda a: _run_admission_verify(a),
        "reliability-comparison": lambda a: _run_comparison(a),
        "reliability-comparison-verify": lambda a: _run_comparison_verify(a),
        "evidence-chain": _run_evidence_chain,
        "reliability-state-transition": _run_state_transition,
        "reliability-state": lambda a: _run_state(a),
        "reliability-attest": _run_attestation,
        "reliability-attest-verify": lambda a: _run_attestation_verify(a),
        "reliability-outcome-verify": lambda a: _run_outcome_verify(a),
        "reliability-recovery-verify": lambda a: _run_recovery_verify(a),
        "reliability-lineage-verify": lambda a: _run_lineage_verify(a),
        "reliability-reconciliation-bind": lambda a: _run_reconciliation_bind(a),
        "reliability-reconciliation-verify": lambda a: _run_reconciliation_verify(a),
        "reliability-proof-bundle": lambda a: _run_proof_bundle(a),
        "reliability-proof-verify": lambda a: _run_proof_verify(a),
        "reliability-proof-completeness-verify": lambda a: (
            _run_proof_completeness_verify(a)
        ),
        "reliability-decision-basis-build": lambda a: _run_decision_basis(a),
        "release-proof": lambda a: _run_release_proof(a),
    }
    handlers[args.command](args)


def _run_evidence_verify(args: argparse.Namespace) -> None:
    """Verify a persisted evidence receipt."""
    receipt = load_evidence_receipt(args.path)
    verify_evidence_receipt(
        receipt,
        artifact_store_root=args.artifact_store,
        receipt_store_root=args.receipt_store,
    )
    _json({"verified": True, "receipt_id": receipt.receipt_id})


def _run_admission_verify(args: argparse.Namespace) -> None:
    """Verify an external evidence admission boundary."""
    receipt = load_evidence_receipt(args.receipt)
    admission = admit_external_evidence(
        receipt,
        artifact_path=args.artifact,
        receipt_path=args.receipt_file,
        expected_run_id=args.run_id,
        expected_producer_type=args.producer_type,
        expected_producer_id=args.producer_id,
    )
    _json(admission.to_dict())


def _run_comparison(args: argparse.Namespace) -> None:
    """Build a behavioral comparison artifact."""
    comparison = build_reliability_behavioral_comparison(
        before_state_path=args.before_state,
        after_state_path=args.after_state,
        output=args.output,
        before_evidence_path=args.before_evidence,
        after_evidence_path=args.after_evidence,
        before_events_path=args.before_events,
        before_run_id=args.before_run_id,
        after_events_path=args.after_events,
        after_run_id=args.after_run_id,
    )
    _json(comparison.to_dict())


def _run_comparison_verify(args: argparse.Namespace) -> None:
    """Verify a behavioral comparison artifact."""
    comparison = load_reliability_behavioral_comparison(args.comparison)
    root = args.root or args.comparison.parent
    verify_reliability_behavioral_comparison(comparison, root=root)
    _json({"verified": True, "comparison_id": comparison.comparison_id})


def _run_state(args: argparse.Namespace) -> None:
    """Read current reliability state and history."""
    store = JsonlReliabilityStateStore(args.history)
    _json(
        {
            "current": current_reliability_state(
                args.subject_id, store=store
            ).to_dict(),
            "history": reliability_state_history(
                args.subject_id, history_path=args.history
            ),
        }
    )


def _run_attestation_verify(args: argparse.Namespace) -> None:
    """Verify an outcome attestation against state history and its chain."""
    attestation = load_reliability_outcome_attestation(args.attestation)
    chain = load_reliability_evidence_chain(args.chain)
    history = JsonlReliabilityStateStore(args.history).read(args.subject_id)
    transition = next(
        (item for item in history if item.transition_id == attestation.transition_id),
        None,
    )
    if transition is None:
        raise ValueError(
            f"reliability-state transition not found: {attestation.transition_id}"
        )
    verify_reliability_outcome_binding(attestation, chain, transition)
    _json({"verified": True, "attestation_id": attestation.attestation_id})


def _run_outcome_verify(args: argparse.Namespace) -> None:
    """Independently verify a reliability outcome."""
    report = verify_reliability_outcome(
        load_reliability_outcome_attestation(args.attestation),
        load_reliability_evidence_chain(args.chain),
        subject_id=args.subject_id,
        history_path=args.history,
        evidence_root=args.evidence_root,
    )
    _json(report.to_dict())
    if not report.verified:
        raise SystemExit(1)


def _run_recovery_verify(args: argparse.Namespace) -> None:
    """Verify recovery evidence bound to an evidence chain."""
    result = verify_reliability_recovery_outcome(
        load_reliability_evidence_chain(args.chain),
        root=args.evidence_root,
    )
    _json({"verified": True, "binding": result.to_dict()})


def _run_lineage_verify(args: argparse.Namespace) -> None:
    """Verify evidence lineage closure."""
    closure = build_reliability_lineage_closure(
        load_reliability_evidence_chain(args.chain),
        root=args.evidence_root,
    )
    _json({"verified": True, "closure": closure.to_dict()})


def _run_reconciliation_bind(args: argparse.Namespace) -> None:
    """Bind a reconciliation result to a detected comparison discrepancy."""
    binding = build_reliability_reconciliation_binding(
        comparison_path=args.comparison,
        reconciliation_path=args.reconciliation,
        output=args.output,
    )
    _json(binding.to_dict())


def _run_reconciliation_verify(args: argparse.Namespace) -> None:
    """Verify a reconciliation binding."""
    binding = load_reliability_reconciliation_binding(args.binding)
    comparison = load_reliability_behavioral_comparison(args.comparison)
    root = args.root or args.reconciliation.parent
    verify_reliability_reconciliation_binding(
        binding,
        comparison=comparison,
        reconciliation_path=args.reconciliation,
        root=root,
    )
    _json({"verified": True, "digest": binding.digest})


def _run_proof_bundle(args: argparse.Namespace) -> None:
    """Build a portable reliability proof bundle."""
    bundle, report = build_reliability_proof_bundle(
        attestation_path=args.attestation,
        evidence_chain_path=args.chain,
        history_path=args.history,
        evidence_root=args.evidence_root,
        output=args.output,
        signed_attestation_path=args.signed_attestation,
        attestation_trust_state_path=args.attestation_trust_state,
        attestation_authority_store_path=args.attestation_authority_store,
    )
    _json(
        {
            "bundle_id": bundle.bundle_id,
            "manifest_id": bundle.manifest_id,
            "verification": report.to_dict(),
        }
    )


def _run_proof_verify(args: argparse.Namespace) -> None:
    """Verify a portable reliability proof bundle."""
    report, descriptor = verify_reliability_proof_bundle(args.bundle)
    _json(
        {
            "verified": report.verified,
            "bundle_type": descriptor.bundle_type,
            "subject_id": descriptor.subject_id,
            "attestation_id": descriptor.attestation_id,
            "verification": report.to_dict(),
        }
    )
    if not report.verified:
        raise SystemExit(1)


def _run_proof_completeness_verify(args: argparse.Namespace) -> None:
    """Verify the completeness witness in a portable proof bundle."""
    report, descriptor = verify_reliability_proof_bundle(args.bundle)
    complete = descriptor.completeness_artifact_id is not None
    if complete:
        payload = descriptor.completeness_artifact_id
        _json(
            {
                "verified": report.verified,
                "completeness_verified": report.verified,
                "completeness_artifact_id": payload,
            }
        )
    else:
        _json(
            {
                "verified": False,
                "completeness_verified": False,
                "completeness_artifact_id": None,
            }
        )
        raise SystemExit(1)


def _run_decision_basis(args: argparse.Namespace) -> None:
    """Create and bind a reliability decision basis to an evidence chain."""
    chain = load_reliability_evidence_chain(args.chain)
    verify_reliability_evidence_chain(chain, root=args.evidence_root)
    profile = (
        load_claim_profile(Path(args.profile)) if Path(args.profile).is_file() else None
    )
    if profile is None:
        profile = get_builtin_claim_profile(args.profile)
    bound = prepare_reliability_decision_basis(
        chain,
        profile,
        basis_path=args.output_basis,
        output_chain_path=args.output_chain,
    )
    _json(
        {
            "chain_id": bound.chain_id,
            "decision_basis_ref": None
            if bound.decision_basis_ref is None
            else bound.decision_basis_ref.to_dict(),
            "output_chain": str(args.output_chain),
            "output_basis": str(args.output_basis),
        }
    )


def _run_release_proof(args: argparse.Namespace) -> None:
    """Build and report final release-proof verification evidence."""
    bundle, report, evaluation = build_release_proof(
        attestation_path=args.attestation,
        evidence_chain_path=args.chain,
        history_path=args.history,
        evidence_root=args.evidence_root,
        output=args.output,
        profile_path=args.profile,
        report_path=args.report,
    )
    _json(
        {
            "bundle_id": bundle.bundle_id,  # type: ignore
            "manifest_id": bundle.manifest_id,  # type: ignore
            "profile": {
                "id": evaluation.profile_id,
                "version": evaluation.profile_version,
                "satisfied": evaluation.satisfied,
            },
            "report": report.to_dict(),
        }  # type: ignore
    )


def main() -> None:
    """Parse and execute the StateWake CLI."""
    args = build_parser().parse_args()
    _run_dispatch(args)


if __name__ == "__main__":
    main()
