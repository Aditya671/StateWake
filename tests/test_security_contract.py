from __future__ import annotations

import re


def test_threat_model_has_required_sections_and_executable_references() -> None:
    from config.project_paths import PROJECT_ROOT

    root = PROJECT_ROOT
    model = (root / "docs" / "security" / "THREAT_MODEL.md").read_text(encoding="utf-8")
    for heading in (
        "## Assets and security properties",
        "## Adversaries",
        "## Trust boundaries",
        "## Threat matrix",
        "## Cryptography policy",
        "## Input and resource security",
        "## Privacy model",
        "## Out of scope / not automatically protected",
        "## Residual-risk handling",
    ):
        assert heading in model
    threat_ids = re.findall(r"\| (T\d{2}) \|", model)
    assert threat_ids == [f"T{i:02d}" for i in range(1, 16)]
    refs = sorted(set(re.findall(r"`(tests/[^`]+)`", model)))
    assert refs
    for ref in refs:
        path = root / ref.split("::", 1)[0]
        assert path.exists(), ref
        if "::" in ref:
            node_path = ref.split("::")
            assert len(node_path) in {2, 3}
            source = path.read_text(encoding="utf-8")
            assert node_path[-1] in source, ref

    matrix = (root / "docs" / "security" / "CONTROL_TEST_MATRIX.md").read_text(
        encoding="utf-8"
    )
    matrix_refs = sorted(set(re.findall(r"`(tests/[^`]+\.py)`", matrix)))
    assert matrix_refs
    for ref in matrix_refs:
        assert (root / ref).exists(), ref


def test_security_adr_is_current_and_points_to_threat_model() -> None:
    from config.project_paths import PROJECT_ROOT

    root = PROJECT_ROOT
    adr = (root / "docs" / "adr" / "0004-security-architecture.md").read_text(
        encoding="utf-8"
    )
    assert "Status" in adr and "Accepted" in adr
    assert "ReliabilityEvidenceChain" in adr
    assert "THREAT_MODEL.md" in adr
