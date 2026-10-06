"""Regression tests for the declared Python support boundary."""

from __future__ import annotations

import re
import tomllib

from scripts.common.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
SUPPORTED = (3, 11), (3, 12), (3, 13)


def _pyproject() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)


def _supports(version: tuple[int, int], specifier: str) -> bool:
    """Evaluate the simple bounded Python range used by StateWake."""
    match = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", specifier.replace(" ", ""))
    assert match is not None, f"unsupported requires-python form: {specifier}"
    lower = int(match.group(1)), int(match.group(2))
    upper = int(match.group(3)), int(match.group(4))
    return lower <= version < upper


def test_declared_python_range_covers_the_qualified_matrix() -> None:
    """The metadata range must include every explicitly qualified Python minor."""
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    specifier = project["requires-python"]
    assert isinstance(specifier, str)
    assert all(_supports(version, specifier) for version in SUPPORTED)
    assert not _supports((3, 14), specifier)


def test_python_classifiers_match_the_qualified_matrix() -> None:
    """Python-version classifiers must describe the same supported minor matrix."""
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    classifiers = project["classifiers"]
    assert isinstance(classifiers, list)
    advertised = {
        tuple(int(part) for part in classifier.rsplit("::", 1)[-1].strip().split("."))
        for classifier in classifiers
        if isinstance(classifier, str)
        and classifier.startswith("Programming Language :: Python :: 3.")
    }
    assert advertised == set(SUPPORTED)
