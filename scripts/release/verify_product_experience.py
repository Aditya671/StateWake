"""Verify the executable public product experience and documentation contract."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import (  # noqa: E402
    DOCS_PATH,
    EXAMPLES_PATH,
    PROJECT_ROOT,
    SRC_PATH,
)

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


REPO_ROOT = PROJECT_ROOT
DOC_ROOT = DOCS_PATH / "user-guide"

REQUIRED_DOCS = (
    "index.md",
    "what-is-statewake.md",
    "getting-started.md",
    "first-evidence-chain.md",
    "python-integration.md",
    "http-api.md",
    "evidence-lifecycle.md",
    "concepts.md",
    "data-and-proof.md",
    "integration-patterns.md",
    "architecture.md",
    "security.md",
    "cli.md",
    "troubleshooting.md",
    "faq.md",
    "release.md",
    "limitations.md",
    "release-evidence-index.md",
)

EXAMPLES = (
    EXAMPLES_PATH / "first-evidence-chain.py",
    EXAMPLES_PATH / "golden" / "payment_reliability.py",
    EXAMPLES_PATH / "golden" / "enterprise_ai_reliability.py",
    EXAMPLES_PATH / "golden" / "municipal_decision_reliability.py",
)


def _markdown_targets(path: Path) -> list[str]:
    """Return relative Markdown link targets from a documentation page."""
    text = path.read_text(encoding="utf-8")
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def verify_documentation() -> list[str]:
    """Verify required product documents and local Markdown targets."""
    errors: list[str] = []
    for name in REQUIRED_DOCS:
        if not (DOC_ROOT / name).is_file():
            errors.append(f"missing product document: {name}")

    for path in DOC_ROOT.glob("*.md"):
        for target in _markdown_targets(path):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = (path.parent / target.split("#", 1)[0]).resolve()
            if not target_path.is_file():
                errors.append(
                    f"broken local link: {path.relative_to(REPO_ROOT)} -> {target}"
                )
    return errors


def run_example(path: Path, *, golden: bool = False) -> tuple[float, str]:
    """Run a public example and return elapsed seconds and combined output."""
    env = dict(__import__("os").environ)
    pythonpath = [str(REPO_ROOT), str(SRC_PATH)]
    if golden:
        pythonpath.append(str(EXAMPLES_PATH / "golden"))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    output = f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    if completed.returncode:
        raise RuntimeError(f"example failed ({path.relative_to(REPO_ROOT)}):\n{output}")
    return elapsed, output


def main() -> int:
    """Run the product-experience documentation and walkthrough gate."""
    errors = verify_documentation()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"documentation: verified {len(REQUIRED_DOCS)} required product pages")
    for example in EXAMPLES:
        golden = example.parent.name == "golden"
        elapsed, output = run_example(example, golden=golden)
        if golden:
            stdout = output.split("stdout:\n", 1)[1].split("\nstderr:\n", 1)[0]
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError as exc:
                print(f"ERROR: {example.name} did not emit one JSON result: {exc}")
                return 1
            required_true = (
                "chain_verified",
                "outcome_verified",
                "proof_bundle_verified",
                "tamper_rejected",
            )
            failed = [name for name in required_true if result.get(name) is not True]
            if failed:
                print(f"ERROR: {example.name} behavioral result failed: {failed}")
                return 1
        # first-evidence-chain.py performs its own assertions and exits non-zero if
        # admission, verification, or tamper rejection fails; no prose matching is needed.
        print(f"example: {example.relative_to(REPO_ROOT)} PASS ({elapsed:.3f}s)")
    print("product experience: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
