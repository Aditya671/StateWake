"""Regression tests for the native SDK optional-integration package boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib

from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT

FRAMEWORK_REQUIREMENTS = {
    "openai-agents>=0.3,<1",
    "langchain-core>=0.3,<2",
    "langgraph>=0.3,<2",
    "llama-index-core>=0.12,<1",
    "opentelemetry-sdk>=1.44,<2",
}


def _project() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]


def test_framework_sdks_are_not_base_runtime_dependencies() -> None:
    """Installing StateWake base must not force any native framework SDK."""
    project = _project()
    raw_dependencies = project["dependencies"]
    assert isinstance(raw_dependencies, list)
    assert all(isinstance(item, str) for item in raw_dependencies)
    dependencies = set(raw_dependencies)
    assert FRAMEWORK_REQUIREMENTS.isdisjoint(dependencies)


def test_each_native_framework_has_one_explicit_extra() -> None:
    """Each adapter family has an independently requestable dependency boundary."""
    project = _project()
    extras = project["optional-dependencies"]  # type: ignore[index]
    assert extras == {
        "integrations-openai-agents": ["openai-agents>=0.3,<1"],
        "integrations-langchain": ["langchain-core>=0.3,<2"],
        "integrations-langgraph": ["langgraph>=0.3,<2"],
        "integrations-llamaindex": ["llama-index-core>=0.12,<1"],
        "integrations-opentelemetry": ["opentelemetry-sdk>=1.44,<2"],
        "integrations": [
            "openai-agents>=0.3,<1",
            "langchain-core>=0.3,<2",
            "langgraph>=0.3,<2",
            "llama-index-core>=0.12,<1",
            "opentelemetry-sdk>=1.44,<2",
        ],
    }


def test_all_integrations_extra_is_exact_union() -> None:
    """The convenience extra cannot silently omit or add a framework family."""
    project = _project()
    raw_extras = project["optional-dependencies"]
    assert isinstance(raw_extras, dict)
    integrations = raw_extras["integrations"]
    assert isinstance(integrations, list)
    assert all(isinstance(item, str) for item in integrations)
    assert set(integrations) == FRAMEWORK_REQUIREMENTS


def test_integrations_module_import_does_not_import_framework_sdks() -> None:
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
