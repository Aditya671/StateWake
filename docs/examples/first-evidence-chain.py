"""Five-minute local evidence-chain demonstration.

Run from the repository root with:
    python docs/examples/first-evidence-chain.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from statewake import (  # noqa: E402
    ExternalEvidenceReceipt,
    admit_evidence,
    build_evidence_chain,
    load_evidence_chain,
    verify_evidence_chain,
    write_evidence_chain,
)


def main() -> None:
    """Run the first-evidence-chain example."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "release.json"
        payload = {"release": "demo-1", "decision": "ship", "owner": "example"}
        artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        digest = sha256(artifact.read_bytes()).hexdigest()
        receipt = ExternalEvidenceReceipt(
            producer_type="ci",
            producer_id="local-demo",
            artifact_digest=digest,
            artifact_size=artifact.stat().st_size,
            captured_at=datetime.now(UTC),
            source_ref="ci://local-demo/demo-1",
            source_event_id="demo-1",
            run_id="demo-run",
        )
        receipt_path = root / "receipt.json"
        receipt_path.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        # Keep the example focused on the evidence boundary: the chain references the receipt-bound artifact.
        run_path = root / "run.json"
        state_path = root / "state.json"
        provenance_path = root / "provenance.json"
        integrity_path = root / "integrity.json"
        for path, value in (
            (run_path, {"run_id": "demo-run"}),
            (state_path, {"state_id": "demo-state"}),
            (provenance_path, {"provenance": "demo"}),
            (integrity_path, {"integrity": "demo"}),
        ):
            path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        admit_evidence(
            receipt,
            artifact_path=artifact,
            receipt_path=receipt_path,
            expected_run_id="demo-run",
            expected_producer_type="ci",
            expected_producer_id="local-demo",
        )
        chain = build_evidence_chain(
            run_id="demo-run",
            run_path=run_path,
            state_id="demo-state",
            state_path=state_path,
            evidence_paths=(artifact,),
            provenance_path=provenance_path,
            integrity_proof_path=integrity_path,
            evidence_receipt_paths={artifact.name: receipt_path},
            verification_status="verified",
            reliability_state="reliable",
            reconciliation_state="verified",
            decision="accept",
            rationale=("demo evidence chain verified",),
        )
        # The demo intentionally exercises the loader/validator against a persisted chain.
        chain_path = root / "chain.json"
        write_evidence_chain(chain, chain_path)
        loaded = load_evidence_chain(chain_path)
        verify_evidence_chain(loaded, root=root)
        print("1. artifact created:", artifact.name)
        print("2. receipt created:", receipt.receipt_id)
        print("3. admission: PASS (receipt bound)")
        print("4. evidence chain created:", loaded.chain_id)
        print("5. verification: PASS")
        artifact.write_text(
            json.dumps({**payload, "tampered": True}, sort_keys=True), encoding="utf-8"
        )
        try:
            verify_evidence_chain(loaded, root=root)
        except (ValueError, FileNotFoundError) as exc:
            print("6. deliberate tampering: REJECTED")
            print("   reason:", exc)
        else:
            raise SystemExit("tampering was not rejected")


if __name__ == "__main__":
    main()
