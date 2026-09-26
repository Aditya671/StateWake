from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_ci_targets_main_and_supported_python_matrix():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in text
    assert '"3.11"' in text and '"3.12"' in text and '"3.13"' in text
    assert "uv lock --check" in text
    assert "uv build" in text


def test_release_workflow_tests_built_wheel_and_persists_security_evidence():
    text = (ROOT / ".github/workflows/release-verification.yml").read_text(
        encoding="utf-8"
    )
    assert "tags: ['v*']" in text
    assert "uv build" in text
    assert "pip install dist/*.whl pip-audit" in text
    assert "pip-audit --format=json --output=pip-audit.json" in text
    assert "name: release-dependency-audit" in text
    assert "format: cyclonedx-json" in text
    assert "actions/attest-build-provenance@v3" in text


def test_release_governance_separates_maturity_from_deployment_security():
    text = (ROOT / "docs/governance/RELEASE_GOVERNANCE.md").read_text(encoding="utf-8")
    assert "does not by itself authorize publication" in text
    assert "not a certification of every host deployment" in text
