"""Regression tests for native SDK optional-integration package boundaries."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib

from scripts.common.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def _project() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]


def _integration_extras() -> dict[str, set[str]]:
    project = _project()
    raw = project.get("optional-dependencies", {})
    assert isinstance(raw, dict)
    return {
        str(name): {str(item) for item in values}
        for name, values in raw.items()
        if str(name).startswith("integrations-") and isinstance(values, list)
    }


def test_native_framework_extras_are_independent_from_base_runtime() -> None:
    """Native SDK extras must remain optional and independently requestable."""
    project = _project()
    dependencies = project.get("dependencies", [])
    assert isinstance(dependencies, list)
    base = {str(item) for item in dependencies}
    extras = _integration_extras()
    assert extras
    component_union = set().union(*extras.values())
    assert component_union
    assert base.isdisjoint(component_union)
    assert all(values for values in extras.values())


def test_integrations_convenience_extra_is_union_of_component_extras() -> None:
    """The aggregate extra follows component extras without a frozen framework list."""
    project = _project()
    raw = project.get("optional-dependencies", {})
    assert isinstance(raw, dict)
    aggregate = raw.get("integrations")
    assert isinstance(aggregate, list)
    component_union = set().union(*_integration_extras().values())
    assert {str(item) for item in aggregate} == component_union


def test_integrations_module_import_does_not_eagerly_import_framework_sdks() -> None:
    """Public integration helpers remain importable without eager SDK imports."""
    script = r"""
import builtins

blocked = ("agents", "langchain_core", "langgraph", "llama_index")
original = builtins.__import__

def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and (name == "opentelemetry.sdk" or any(
        name == prefix or name.startswith(prefix + ".") for prefix in blocked
    )):
        raise ModuleNotFoundError(name=name)
    return original(name, globals, locals, fromlist, level)

builtins.__import__ = guarded
import statewake.integrations
print("STATEWAKE_BASE_INTEGRATIONS_IMPORT_OK")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STATEWAKE_BASE_INTEGRATIONS_IMPORT_OK" in result.stdout
