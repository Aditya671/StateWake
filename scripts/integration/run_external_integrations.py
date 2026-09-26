"""Run credential-free external integration captures through StateWake."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from statewake import IntegrationContext, StateWakeClient  # noqa: E402
from statewake.utils.time import parse_datetime  # noqa: E402

REPO_ROOT = PROJECT_ROOT
SRC_ROOT = SRC_PATH


@dataclass(frozen=True, slots=True)
class ExternalCapture:
    """Describe one externally sourced response prepared for StateWake."""

    system: str
    source_url: str
    reference: str
    reference_kind: str
    capture_kind: str
    capture_scope: str
    content_sha256: str
    captured_at: str
    content: bytes


MAX_EXTERNAL_BODY_BYTES: Final[int] = 1_048_576


def _fetch_json(url: str) -> tuple[bytes, str]:
    """Fetch a bounded JSON response from a public HTTPS endpoint."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "statewake-external-test/0.1",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read(MAX_EXTERNAL_BODY_BYTES + 1)
        if len(body) > MAX_EXTERNAL_BODY_BYTES:
            raise ValueError("external response exceeds 1 MiB test limit")
        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise ValueError(f"unexpected external content type: {content_type}")
        return body, response.headers.get("ETag", "")


def capture_public_github() -> ExternalCapture:
    """Capture a public GitHub repository metadata response."""
    url = "https://api.github.com/repos/stripe-samples/starter"
    body, etag = _fetch_json(url)
    reference = f"etag:{etag}" if etag else "default-branch:main"
    reference_kind = "http_etag" if etag else "request_observation"
    return ExternalCapture(
        system="github-rest",
        source_url=url,
        reference=reference,
        reference_kind=reference_kind,
        capture_kind="http_response",
        capture_scope="full_http_response_bounded_to_1MiB",
        content_sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime.now(UTC).isoformat(),
        content=body,
    )


def capture_public_municipal() -> ExternalCapture:
    """Capture one bounded NYC Open Data public record."""
    url = "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=1"
    body, etag = _fetch_json(url)
    reference = f"etag:{etag}" if etag else "query:$limit=1"
    reference_kind = "http_etag" if etag else "query_observation"
    return ExternalCapture(
        system="nyc-open-data",
        source_url=url,
        reference=reference,
        reference_kind=reference_kind,
        capture_kind="http_response",
        capture_scope="full_http_response_bounded_to_1MiB",
        content_sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime.now(UTC).isoformat(),
        content=body,
    )


def ingest_capture(capture: ExternalCapture, root: Path) -> dict[str, object]:
    """Ingest and verify one external capture through the public SDK."""
    client = StateWakeClient.for_root(
        IntegrationContext(f"external:{capture.system}", run_id="external-integration"),
        root=root,
    )
    receipt = client.ingest_bytes(
        capture.content,
        producer_type=capture.system,
        source_ref=capture.source_url,
        source_event_id=hashlib.sha256(capture.content).hexdigest(),
        captured_at=parse_datetime(capture.captured_at, field="captured_at"),
        metadata={"reference": capture.reference},
    )
    if hashlib.sha256(capture.content).hexdigest() != capture.content_sha256:
        raise ValueError("external capture content hash does not match its metadata")
    client.verify_receipt(receipt)
    return {
        "system": capture.system,
        "source_url": capture.source_url,
        "reference": capture.reference,
        "reference_kind": capture.reference_kind,
        "capture_kind": capture.capture_kind,
        "capture_scope": capture.capture_scope,
        "content_sha256": capture.content_sha256,
        "artifact_sha256": receipt.artifact_digest,
        "receipt_id": receipt.receipt_id,
        "verified": True,
    }


def load_fixture(path: Path) -> ExternalCapture:
    """Load a previously captured external response fixture."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    content = bytes.fromhex(payload["content_hex"])
    content_sha256 = payload.get("content_sha256")
    if not isinstance(content_sha256, str) or len(content_sha256) != 64:
        raise ValueError("external fixture content_sha256 must be a SHA-256 hex digest")
    if hashlib.sha256(content).hexdigest() != content_sha256:
        raise ValueError("external fixture content_sha256 does not match content")
    return ExternalCapture(
        system=payload["system"],
        source_url=payload["source_url"],
        reference=payload["reference"],
        reference_kind=payload["reference_kind"],
        capture_kind=payload["capture_kind"],
        capture_scope=payload["capture_scope"],
        content_sha256=content_sha256,
        captured_at=payload["captured_at"],
        content=content,
    )


def main() -> int:
    """Run external integrations in live, fixture, or CI mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "fixture", "ci"), default="ci")
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    captures: list[ExternalCapture] = []
    if args.mode == "fixture":
        if args.fixture is None:
            parser.error("--fixture is required in fixture mode")
        captures = [load_fixture(args.fixture)]
    elif args.mode == "live":
        captures = []
        failures: list[dict[str, str]] = []
        targets = (
            ("github", capture_public_github),
            ("municipal", capture_public_municipal),
        )
        for target, capture_fn in targets:
            try:
                captures.append(capture_fn())
            except (OSError, ValueError, urllib.error.URLError) as exc:
                failures.append(
                    {
                        "target": target,
                        "error_type": type(exc).__name__,
                        "message": (
                            "live external endpoint could not be reached or validated"
                        ),
                    }
                )
        if failures:
            print(
                json.dumps(
                    {
                        "status": "LIVE_EXTERNAL_GATE_BLOCKED",
                        "verified": False,
                        "successful_captures": len(captures),
                        "failures": failures,
                    },
                    sort_keys=True,
                )
            )
            return 3
    else:
        captures = []
        fixture_dir = REPO_ROOT / "tests" / "fixtures" / "external_captures"
        captures.extend(
            load_fixture(path) for path in sorted(fixture_dir.glob("*.json"))
        )

    if not captures:
        print(json.dumps({"status": "NO_LIVE_CAPTURES", "verified": False}))
        return 2

    with TemporaryDirectory() as directory:
        results = [
            ingest_capture(capture, Path(directory) / capture.system)
            for capture in captures
        ]
    print(json.dumps({"status": "PASS", "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
