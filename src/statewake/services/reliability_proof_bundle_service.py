"""Build and independently verify portable V1 reliability-proof bundles."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.operations import OperationalArtifact, OperationalBundle
from statewake.domain.reliability_attestation import SignedReliabilityOutcomeEnvelope
from statewake.domain.reliability_lineage import ReliabilityLineageClosure

from ..domain.cryptographic_trust import CryptographicProfile
from ..domain.reliability_attestation_trust_context import (
    ReliabilityAttestationTrustContext,
)
from ..domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from ..domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from ..domain.reliability_proof_bundle import (
    ReliabilityProofBundleDescriptor,
    ReliabilityProofSource,
)
from .operations_service import build_bundle, export_bundle, verify_bundle
from .reliability_attestation_service import (
    load_reliability_outcome_attestation,
    verify_signed_reliability_outcome_envelope,
)
from .reliability_evidence_service import load_reliability_evidence_chain
from .reliability_lineage_service import verify_reliability_lineage_closure
from .reliability_outcome_verification_service import verify_reliability_outcome
from .reliability_proof_completeness_service import (
    build_reliability_proof_completeness,
    verify_reliability_proof_completeness,
)
from .trust_service import (
    load_attestation_trust_state,
    load_authority_store,
    verify_attestation_trust_state,
)


def _canonical_json(payload: object) -> bytes:
    """Return the canonical JSON representation used for deterministic hashing."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _safe_source(root: Path, source: str) -> Path:
    """Return a sanitized source identifier constrained to the evidence root."""
    root_resolved = root.resolve()
    candidate = (root_resolved / source.replace("\\", "/")).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"reliability proof source escapes evidence root: {source}")
    return candidate


def _reference_items(
    chain: ReliabilityEvidenceChain, *, root: Path | None = None
) -> tuple[tuple[str, EvidenceReference], ...]:
    """Return the canonical proof-bundle reference items."""
    items: list[tuple[str, EvidenceReference]] = [
        ("run", chain.run),
        ("state", chain.state),
    ]
    for index, item in enumerate(chain.evidence):
        items.append((f"evidence:{index}", item))
        if item.receipt_ref is not None:
            items.append((f"evidence:{index}:receipt", item.receipt_ref))
    items.extend((("provenance", chain.provenance), ("integrity", chain.integrity)))
    if chain.reconciliation_binding_ref is not None:
        items.append(("reconciliation_binding", chain.reconciliation_binding_ref))
    if chain.reconciliation_ref is not None:
        items.append(("reconciliation", chain.reconciliation_ref))
    if chain.recovery_ref is not None:
        items.append(("recovery", chain.recovery_ref))
    if chain.attestation_ref is not None:
        items.append(("attestation_ref", chain.attestation_ref))
    if chain.decision_basis_ref is not None:
        items.append(("decision_basis", chain.decision_basis_ref))
    if chain.comparison_ref is not None:
        items.append(("comparison", chain.comparison_ref))
        if root is not None and chain.comparison_ref.source is not None:
            from .reliability_comparison_service import (
                comparison_input_references,
                load_reliability_behavioral_comparison,
            )

            comparison_path = _safe_source(root, chain.comparison_ref.source)
            if comparison_path.is_file():
                comparison = load_reliability_behavioral_comparison(comparison_path)
                for item in comparison_input_references(comparison):
                    items.append(
                        (f"comparison-input:{item.kind}:{item.identity}", item)
                    )
    return tuple(items)


def build_reliability_proof_bundle(
    *,
    attestation_path: Path,
    evidence_chain_path: Path,
    history_path: Path,
    evidence_root: Path,
    output: Path,
    signed_attestation_path: Path | None = None,
    attestation_trust_state_path: Path | None = None,
    attestation_authority_store_path: Path | None = None,
    cryptographic_profile: CryptographicProfile | None = None,
) -> tuple[OperationalBundle, ReliabilityOutcomeVerificationReport]:
    """Verify an outcome, then package its exact evidence graph using OperationalBundle."""
    attestation = load_reliability_outcome_attestation(attestation_path)
    chain = load_reliability_evidence_chain(evidence_chain_path)
    report = verify_reliability_outcome(
        attestation,
        chain,
        subject_id=attestation.subject_id,
        history_path=history_path,
        evidence_root=evidence_root,
    )
    if not report.verified:
        raise ValueError(
            "cannot create a reliability proof bundle from an unverified outcome: "
            + "; ".join(report.failures)
        )

    trust_inputs = (
        signed_attestation_path,
        attestation_trust_state_path,
        attestation_authority_store_path,
    )
    trust_supplied = any(item is not None for item in trust_inputs)
    if trust_supplied and not all(item is not None for item in trust_inputs):
        raise ValueError(
            "signed_attestation_path, attestation_trust_state_path, and attestation_authority_store_path must be supplied together"
        )

    lineage_closure = verify_reliability_lineage_closure(chain, root=evidence_root)

    trust_context = None
    signed_envelope: SignedReliabilityOutcomeEnvelope | None = None
    trust_state = None
    authority_store = None
    if trust_supplied:
        assert signed_attestation_path is not None
        assert attestation_trust_state_path is not None
        assert attestation_authority_store_path is not None
        envelope_payload = json.loads(
            signed_attestation_path.read_text(encoding="utf-8")
        )
        if not isinstance(envelope_payload, dict):
            raise ValueError(
                "signed reliability attestation envelope must be a JSON object"
            )
        signed_envelope = SignedReliabilityOutcomeEnvelope.from_dict(envelope_payload)
        trust_state = load_attestation_trust_state(attestation_trust_state_path)
        authority_store = load_authority_store(attestation_authority_store_path)
        verify_attestation_trust_state(attestation_trust_state_path, authority_store)
        verify_signed_reliability_outcome_envelope(
            signed_envelope,
            trusted_public_keys={
                anchor.key_id: anchor.public_key for anchor in trust_state.anchors
            },
            trust_state=trust_state,
        )
        signed_attestation = signed_envelope.attestation
        if signed_envelope.key_id != attestation.signing_key_id:
            raise ValueError(
                "signed attestation key id does not match the attestation signing_key_id"
            )
        if (
            signed_attestation.get("attestation_id") != attestation.attestation_id
            or signed_attestation.get("digest") != attestation.digest
        ):
            raise ValueError(
                "signed attestation does not match the packaged reliability outcome attestation"
            )
        anchor = next(
            (
                item
                for item in trust_state.anchors
                if item.key_id == signed_envelope.key_id
            ),
            None,
        )
        if anchor is None:
            raise ValueError(
                "signed attestation key is absent from the attestation trust state"
            )
        if trust_state.authority_key_id not in authority_store:
            raise ValueError(
                "attestation trust-state authority key is absent from the authority store"
            )
        trust_context = ReliabilityAttestationTrustContext(
            format_version="1",
            envelope_artifact_id="proof-attestation-envelope",
            envelope_digest=sha256(
                _canonical_json(signed_envelope.to_dict())
            ).hexdigest(),
            attestation_id=attestation.attestation_id,
            attestation_digest=attestation.digest,
            signing_key_id=signed_envelope.key_id,
            signing_key_digest=sha256(anchor.public_key).hexdigest(),
            trust_state_artifact_id="proof-attestation-trust-state",
            trust_state_digest=trust_state.digest(),
            trust_state_version=trust_state.version,
            authority_store_artifact_id="proof-attestation-authority-store",
            authority_key_id=trust_state.authority_key_id,
            authority_key_digest=sha256(
                authority_store[trust_state.authority_key_id]
            ).hexdigest(),
        )

    evidence_root = evidence_root.resolve()
    if not history_path.is_file():
        raise FileNotFoundError(history_path)
    history_bytes = history_path.read_bytes()

    source_records: list[ReliabilityProofSource] = []
    source_artifacts: list[OperationalArtifact] = []
    seen_sources: dict[str, tuple[str, str]] = {}
    for key, reference in _reference_items(chain, root=evidence_root):
        if reference.source is None:
            raise ValueError(
                f"reliability proof requires a local source for {key}:"
                f"{reference.identity}"
            )
        path = _safe_source(evidence_root, reference.source)
        if not path.is_file():
            raise FileNotFoundError(path)
        content = path.read_bytes()
        actual = sha256(content).hexdigest()
        if reference.kind == "receipt":
            receipt = ExternalEvidenceReceipt.from_dict(
                json.loads(content.decode("utf-8"))
            )
            if (
                receipt.digest != reference.digest
                or receipt.receipt_id != reference.identity
            ):
                raise ValueError(
                    f"reliability proof receipt binding mismatch for {reference.identity}"
                )
            bound_digest = receipt.digest
        else:
            if actual != reference.digest:
                raise ValueError(
                    f"reliability proof source digest mismatch for {reference.identity}"
                )
            bound_digest = reference.digest
        prior = seen_sources.get(reference.source)
        if prior is not None:
            if prior[1] != actual:
                raise ValueError(
                    f"conflicting proof sources share the same path: {reference.source}"
                )
            artifact_id = prior[0]
        else:
            artifact_id = (
                "source-"
                + sha256(f"{reference.source}\0{actual}".encode()).hexdigest()[:16]
            )
            seen_sources[reference.source] = (artifact_id, actual)
            source_artifacts.append(
                OperationalArtifact(
                    artifact_id=artifact_id,
                    path=reference.source.replace("\\", "/"),
                    kind=reference.kind,
                    sha256=actual,
                    size_bytes=path.stat().st_size,
                    sensitivity="internal",
                )
            )
        source_records.append(
            ReliabilityProofSource(
                key,
                reference.source.replace("\\", "/"),
                artifact_id,
                actual,
                reference_digest=bound_digest,
            )
        )

    with tempfile.TemporaryDirectory() as staging_dir_name:
        staging = Path(staging_dir_name)
        artifacts_dir = staging / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        special = {
            "proof-attestation": (
                "proof/attestation.json",
                "reliability-outcome-attestation",
                attestation_path.read_bytes(),
            ),
            "proof-evidence-chain": (
                "proof/evidence-chain.json",
                "reliability-evidence-chain",
                evidence_chain_path.read_bytes(),
            ),
            "proof-state-history": (
                "proof/state-history.jsonl",
                "reliability-state-history",
                history_bytes,
            ),
            "proof-verification-report": (
                "proof/verification-report.json",
                "reliability-verification-report",
                _canonical_json(report.to_dict()) + b"\n",
            ),
        }
        raw_descriptor = ReliabilityProofBundleDescriptor(
            format_version="3",
            bundle_type="reliability-proof",
            subject_id=attestation.subject_id,
            attestation_artifact_id="proof-attestation",
            evidence_chain_artifact_id="proof-evidence-chain",
            state_history_artifact_id="proof-state-history",
            verification_report_artifact_id="proof-verification-report",
            attestation_id=attestation.attestation_id,
            attestation_digest=attestation.digest,
            evidence_chain_id=chain.chain_id,
            evidence_chain_digest=chain.digest(),
            transition_id=attestation.transition_id,
            transition_digest=attestation.transition_digest,
            reliability_state=attestation.reliability_state,
            decision=attestation.decision,
            verification_report_digest=report.digest,
            sources=tuple(source_records),
            attestation_trust_context=trust_context,
            lineage_closure=lineage_closure,
            completeness_artifact_id="proof-completeness",
            completeness_digest="0" * 64,
        )
        completeness = build_reliability_proof_completeness(
            raw_descriptor,
            expected_source_reference_keys=tuple(
                sorted(key for key, _ in _reference_items(chain, root=evidence_root))
            ),
            artifact_ids=tuple(
                artifact_id
                for artifact_id in (
                    "proof-attestation",
                    "proof-evidence-chain",
                    "proof-state-history",
                    "proof-verification-report",
                    "proof-descriptor",
                    "proof-lineage-closure",
                    "proof-completeness",
                    *(item.artifact_id for item in source_artifacts),
                    *(
                        item
                        for item in (
                            "proof-attestation-envelope"
                            if trust_context is not None
                            else None,
                            "proof-attestation-trust-state"
                            if trust_context is not None
                            else None,
                            "proof-attestation-authority-store"
                            if trust_context is not None
                            else None,
                            "proof-attestation-trust-context"
                            if trust_context is not None
                            else None,
                        )
                        if item is not None
                    ),
                )
            ),
        )
        raw_descriptor = ReliabilityProofBundleDescriptor(
            **{
                **raw_descriptor.to_dict(include_digest=False),
                "sources": tuple(source_records),
                "attestation_trust_context": trust_context,
                "lineage_closure": lineage_closure,
                "completeness_artifact_id": "proof-completeness",
                "completeness_digest": completeness.digest,
            },  # type: ignore
        )
        special["proof-completeness"] = (
            "proof/completeness.json",
            "reliability-proof-completeness",
            _canonical_json(completeness.to_dict()) + b"\n",
        )
        special["proof-descriptor"] = (
            "proof/descriptor.json",
            "reliability-proof-descriptor",
            _canonical_json(raw_descriptor.to_dict()) + b"\n",
        )
        special["proof-lineage-closure"] = (
            "proof/lineage-closure.json",
            "reliability-lineage-closure",
            _canonical_json(lineage_closure.to_dict()) + b"\n",
        )
        if (
            trust_context is not None
            and signed_envelope is not None
            and trust_state is not None
            and authority_store is not None
        ):
            special["proof-attestation-envelope"] = (
                "proof/attestation-envelope.json",
                "signed-reliability-outcome-attestation",
                _canonical_json(signed_envelope.to_dict()) + b"\n",
            )
            special["proof-attestation-trust-state"] = (
                "proof/attestation-trust-state.json",
                "attestation-trust-state",
                _canonical_json(trust_state.to_dict()) + b"\n",
            )
            authority_payload = {
                "keys": {
                    trust_state.authority_key_id: __import__("base64")
                    .urlsafe_b64encode(authority_store[trust_state.authority_key_id])
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
            special["proof-attestation-authority-store"] = (
                "proof/attestation-authority.json",
                "attestation-authority-store",
                _canonical_json(authority_payload) + b"\n",
            )
            special["proof-attestation-trust-context"] = (
                "proof/attestation-trust-context.json",
                "reliability-attestation-trust-context",
                _canonical_json(trust_context.to_dict()) + b"\n",
            )

        spec_artifacts: list[dict[str, object]] = []
        for artifact in source_artifacts:
            content = (evidence_root / artifact.path).read_bytes()
            spec_artifacts.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "path": artifact.path,
                    "kind": artifact.kind,
                    "sha256": artifact.sha256,
                    "sensitivity": artifact.sensitivity,
                }
            )
            target = staging / artifact.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for artifact_id, (member_path, kind, content) in special.items():
            target = staging / member_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            spec_artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "path": member_path,
                    "kind": kind,
                    "sha256": sha256(content).hexdigest(),
                    "sensitivity": "restricted"
                    if artifact_id.startswith("proof-")
                    else "internal",
                }
            )

        artifact_paths = [str(item["path"]) for item in spec_artifacts]
        if len(artifact_paths) != len(set(artifact_paths)):
            raise ValueError(
                "reliability proof bundle contains duplicate artifact paths"
            )

        # Build through the existing OperationalBundle authority; no second ZIP/manifest implementation is introduced.
        spec = {
            "bundle_id": "pending",
            "agent_name": attestation.subject_id,
            "created_at": attestation.occurred_at,
            "artifacts": spec_artifacts,
        }
        spec_path = staging / "bundle-spec.json"
        spec_path.write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        bundle, files = build_bundle(spec_path)
        export_bundle(bundle, files, output)

    return bundle, report


def verify_reliability_proof_bundle(
    bundle_path: Path,
) -> tuple[ReliabilityOutcomeVerificationReport, ReliabilityProofBundleDescriptor]:
    """Verify a portable proof bundle without requiring the original runtime or filesystem."""
    bundle = verify_bundle(bundle_path)
    artifact_by_id = {item.artifact_id: item for item in bundle.artifacts}
    descriptor_candidates = [
        item for item in bundle.artifacts if item.kind == "reliability-proof-descriptor"
    ]
    if len(descriptor_candidates) != 1:
        raise ValueError("reliability proof bundle must contain exactly one descriptor")
    descriptor_artifact = descriptor_candidates[0]

    with ZipFile(bundle_path) as archive:

        def content_for(artifact_id: str) -> bytes:
            """Return the persisted content associated with a proof-bundle reference."""
            item = artifact_by_id.get(artifact_id)
            if item is None:
                raise ValueError(f"proof bundle is missing artifact: {artifact_id}")
            return archive.read(f"artifacts/{item.artifact_id}/{item.path}")

        descriptor_payload = json.loads(
            content_for(descriptor_artifact.artifact_id).decode("utf-8")
        )
        descriptor = ReliabilityProofBundleDescriptor.from_dict(descriptor_payload)
        required_ids = {
            descriptor.attestation_artifact_id,
            descriptor.evidence_chain_artifact_id,
            descriptor.state_history_artifact_id,
            descriptor.verification_report_artifact_id,
            descriptor_artifact.artifact_id,
        }
        context = descriptor.attestation_trust_context
        lineage = descriptor.lineage_closure
        lineage_candidates = [
            item
            for item in bundle.artifacts
            if item.kind == "reliability-lineage-closure"
        ]
        if descriptor.format_version in {"2", "3"}:
            if lineage is None:
                raise ValueError(
                    f"format version {descriptor.format_version} reliability proof must contain a lineage closure"
                )
            if len(lineage_candidates) != 1:
                raise ValueError(
                    f"format version {descriptor.format_version} reliability proof must contain exactly one lineage closure artifact"
                )
            required_ids.add(lineage_candidates[0].artifact_id)
        elif lineage is not None or lineage_candidates:
            raise ValueError(
                "format version 1 reliability proof cannot contain lineage closure"
            )
        completeness_candidates = [
            item
            for item in bundle.artifacts
            if item.kind == "reliability-proof-completeness"
        ]
        if descriptor.format_version == "3":
            if descriptor.completeness_artifact_id != "proof-completeness":
                raise ValueError(
                    "format version 3 reliability proof has an invalid completeness artifact identity"
                )
            if descriptor.completeness_artifact_id not in artifact_by_id:
                raise ValueError(
                    "format version 3 reliability proof is missing completeness artifact"
                )
            if (
                len(completeness_candidates) != 1
                or completeness_candidates[0].artifact_id
                != descriptor.completeness_artifact_id
            ):
                raise ValueError(
                    "format version 3 reliability proof must contain exactly one completeness artifact"
                )
            required_ids.add(descriptor.completeness_artifact_id)
        elif (
            descriptor.completeness_artifact_id is not None
            or descriptor.completeness_digest is not None
            or completeness_candidates
        ):
            raise ValueError(
                "legacy reliability proof cannot contain completeness binding"
            )
        if context is not None:
            required_ids.update(
                {
                    context.envelope_artifact_id,
                    context.trust_state_artifact_id,
                    context.authority_store_artifact_id,
                }
            )
            context_candidates = [
                item
                for item in bundle.artifacts
                if item.kind == "reliability-attestation-trust-context"
            ]
            if len(context_candidates) != 1:
                raise ValueError(
                    "proof bundle with attestation trust context must contain exactly one context artifact"
                )
            required_ids.add(context_candidates[0].artifact_id)
        if not required_ids.issubset(artifact_by_id):
            missing = sorted(required_ids - set(artifact_by_id))
            raise ValueError(f"proof bundle is missing required artifacts: {missing}")

        attestation_bytes = content_for(descriptor.attestation_artifact_id)
        chain_bytes = content_for(descriptor.evidence_chain_artifact_id)
        history_bytes = content_for(descriptor.state_history_artifact_id)
        report_bytes = content_for(descriptor.verification_report_artifact_id)
        lineage_bytes = None
        completeness_bytes = None
        if descriptor.format_version in {"2", "3"}:
            lineage_bytes = content_for(lineage_candidates[0].artifact_id)
        if descriptor.format_version == "3":
            completeness_bytes = content_for(descriptor.completeness_artifact_id or "")
        envelope_bytes = trust_state_bytes = authority_bytes = context_bytes = None
        if context is not None:
            envelope_bytes = content_for(context.envelope_artifact_id)
            trust_state_bytes = content_for(context.trust_state_artifact_id)
            authority_bytes = content_for(context.authority_store_artifact_id)
            context_artifact = next(
                item
                for item in bundle.artifacts
                if item.kind == "reliability-attestation-trust-context"
            )
            context_bytes = content_for(context_artifact.artifact_id)

    with tempfile.TemporaryDirectory() as materialized_name:
        root = Path(materialized_name)
        attestation_path = root / "proof" / "attestation.json"
        chain_path = root / "proof" / "evidence-chain.json"
        history_path = root / "proof" / "state-history.jsonl"
        attestation_path.parent.mkdir(parents=True, exist_ok=True)
        attestation_path.write_bytes(attestation_bytes)
        chain_path.write_bytes(chain_bytes)
        history_path.write_bytes(history_bytes)
        chain_for_completeness = load_reliability_evidence_chain(chain_path)
        # Materialize all referenced source artifacts before evaluating nested comparison-input references.
        source_lookup = {item.reference_key: item for item in descriptor.sources}
        if len(source_lookup) != len(descriptor.sources):
            raise ValueError("duplicate proof source references")
        with ZipFile(bundle_path) as archive:
            for source in descriptor.sources:
                artifact = artifact_by_id.get(source.artifact_id)
                if artifact is None:
                    raise ValueError(
                        f"proof source artifact missing: {source.artifact_id}"
                    )
                target = _safe_source(root, source.source)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(
                    archive.read(f"artifacts/{artifact.artifact_id}/{artifact.path}")
                )
        expected_source_keys = tuple(
            sorted(
                key for key, _ in _reference_items(chain_for_completeness, root=root)
            )
        )
        actual_source_keys = tuple(
            sorted(item.reference_key for item in descriptor.sources)
        )
        if actual_source_keys != expected_source_keys:
            missing = sorted(set(expected_source_keys) - set(actual_source_keys))
            extra = sorted(set(actual_source_keys) - set(expected_source_keys))
            raise ValueError(
                f"portable reliability proof source set is incomplete: missing={missing}, extra={extra}"
            )
        if descriptor.format_version == "3":
            assert descriptor.completeness_artifact_id is not None
            assert completeness_bytes is not None
            completeness_path = root / "proof" / "completeness.json"
            completeness_path.write_bytes(completeness_bytes)
            packaged_completeness = __import__(
                "statewake.domain.reliability_proof_completeness",
                fromlist=["ReliabilityProofCompleteness"],
            ).ReliabilityProofCompleteness.from_dict(
                json.loads(completeness_bytes.decode("utf-8"))
            )
            if packaged_completeness.digest != descriptor.completeness_digest:
                raise ValueError(
                    "packaged reliability proof completeness does not match descriptor digest"
                )
            verify_reliability_proof_completeness(
                descriptor,
                packaged_completeness,
                artifact_ids=tuple(item.artifact_id for item in bundle.artifacts),
                expected_source_reference_keys=expected_source_keys,
            )
        if descriptor.format_version in {"2", "3"}:
            assert lineage is not None and lineage_bytes is not None
            packaged_lineage = ReliabilityLineageClosure.from_dict(
                json.loads(lineage_bytes.decode("utf-8"))
            )
            if packaged_lineage != lineage:
                raise ValueError(
                    "packaged lineage closure does not match proof descriptor"
                )

        if context is not None:
            assert (
                envelope_bytes is not None
                and trust_state_bytes is not None
                and authority_bytes is not None
                and context_bytes is not None
            )
            context_payload = json.loads(context_bytes.decode("utf-8"))
            packaged_context = ReliabilityAttestationTrustContext.from_dict(
                context_payload
            )
            if packaged_context != context:
                raise ValueError(
                    "packaged attestation trust context does not match proof descriptor"
                )
            envelope_path = root / "proof" / "attestation-envelope.json"
            trust_state_path = root / "proof" / "attestation-trust-state.json"
            authority_path = root / "proof" / "attestation-authority.json"
            envelope_path.write_bytes(envelope_bytes)
            trust_state_path.write_bytes(trust_state_bytes)
            authority_path.write_bytes(authority_bytes)
            actual_envelope_digest = sha256(
                _canonical_json(
                    SignedReliabilityOutcomeEnvelope.from_dict(
                        json.loads(envelope_bytes.decode("utf-8"))
                    ).to_dict()
                )
            ).hexdigest()
            if actual_envelope_digest != context.envelope_digest:
                raise ValueError("packaged signed-attestation envelope digest mismatch")
            packaged_state = load_attestation_trust_state(trust_state_path)
            packaged_authorities = load_authority_store(authority_path)
            if (
                packaged_state.digest() != context.trust_state_digest
                or packaged_state.version != context.trust_state_version
            ):
                raise ValueError(
                    "packaged attestation trust state does not match trust context"
                )
            if packaged_state.authority_key_id != context.authority_key_id:
                raise ValueError(
                    "packaged attestation authority identity does not match trust context"
                )
            authority_key = packaged_authorities.get(context.authority_key_id)
            if (
                authority_key is None
                or sha256(authority_key).hexdigest() != context.authority_key_digest
            ):
                raise ValueError(
                    "packaged attestation authority key does not match trust context"
                )
            verify_attestation_trust_state(trust_state_path, packaged_authorities)
            packaged_envelope = SignedReliabilityOutcomeEnvelope.from_dict(
                json.loads(envelope_bytes.decode("utf-8"))
            )
            anchor = next(
                (
                    item
                    for item in packaged_state.anchors
                    if item.key_id == packaged_envelope.key_id
                ),
                None,
            )
            if (
                anchor is None
                or sha256(anchor.public_key).hexdigest() != context.signing_key_digest
            ):
                raise ValueError(
                    "packaged attestation signing key does not match trust context"
                )
            signed_attestation = verify_signed_reliability_outcome_envelope(
                packaged_envelope,
                trusted_public_keys={
                    item.key_id: item.public_key for item in packaged_state.anchors
                },
                trust_state=packaged_state,
            )
            if (
                signed_attestation.attestation_id != context.attestation_id
                or signed_attestation.digest != context.attestation_digest
            ):
                raise ValueError("signed attestation does not match trust context")

        attestation = load_reliability_outcome_attestation(attestation_path)
        chain = load_reliability_evidence_chain(chain_path)
        report = verify_reliability_outcome(
            attestation,
            chain,
            subject_id=descriptor.subject_id,
            history_path=history_path,
            evidence_root=root,
        )
        packaged_report_payload = json.loads(report_bytes.decode("utf-8"))
        if not isinstance(packaged_report_payload, dict):
            raise ValueError("packaged verification result must be an object")
        packaged_report_payload.pop("digest", None)
        packaged_report = ReliabilityOutcomeVerificationReport(
            **packaged_report_payload
        )
        if (
            packaged_report.to_dict() != report.to_dict()
            or packaged_report.digest != descriptor.verification_report_digest
        ):
            raise ValueError(
                "packaged verification result does not reproduce the offline verification result"
            )
        if (
            attestation.attestation_id != descriptor.attestation_id
            or attestation.digest != descriptor.attestation_digest
        ):
            raise ValueError("packaged attestation does not match proof descriptor")
        if (
            chain.chain_id != descriptor.evidence_chain_id
            or chain.digest() != descriptor.evidence_chain_digest
        ):
            raise ValueError("packaged evidence chain does not match proof descriptor")
        if (
            attestation.transition_id != descriptor.transition_id
            or attestation.transition_digest != descriptor.transition_digest
        ):
            raise ValueError(
                "packaged transition binding does not match proof descriptor"
            )
        if descriptor.format_version in {"2", "3"}:
            assert lineage is not None and packaged_lineage is not None  # type: ignore
            verified_lineage = verify_reliability_lineage_closure(
                chain,
                root=root,
                closure=packaged_lineage,  # type: ignore
            )
            if verified_lineage != lineage:
                raise ValueError(
                    "reconstructed reliability lineage closure does not match proof descriptor"
                )
        if not report.verified:
            raise ValueError(
                "portable reliability proof verification failed: "
                + "; ".join(report.failures)
            )
        return report, descriptor
