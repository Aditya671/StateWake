"""Release regressions for the PEP 639 license metadata boundary."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
LICENSE_FILE = ROOT / "LICENSE"


def _project() -> dict[str, object]:
    with PYPROJECT.open("rb") as handle:
        parsed = tomllib.load(handle)
    project = parsed["project"]
    assert isinstance(project, dict)
    return project


def test_license_uses_spdx_expression_and_explicit_license_file() -> None:
    project = _project()
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert LICENSE_FILE.is_file()
    assert "Apache License" in LICENSE_FILE.read_text(encoding="utf-8")


def test_deprecated_license_trove_classifiers_are_not_advertised() -> None:
    project = _project()
    classifiers = project["classifiers"]
    assert isinstance(classifiers, list)
    assert not any(
        isinstance(classifier, str) and classifier.startswith("License ::")
        for classifier in classifiers
    )
