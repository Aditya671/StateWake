"""Executable consumer-contract tests for the top-level StateWake API."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import inspect
import json
from typing import Required, TypedDict, get_type_hints

import statewake
from config.project_paths import PROJECT_ROOT
from statewake.cli.main import supported_commands

ROOT = PROJECT_ROOT
MANIFEST_PATH = ROOT / "docs" / "reference" / "api-contract.json"


class ApiSymbol(TypedDict):
    """Typed public API manifest symbol entry."""

    name: Required[str]
    kind: Required[str]
    module: Required[str | None]


class ApiManifest(TypedDict):
    """Typed public API manifest."""

    symbols: list[ApiSymbol]
    contract_version: str
    package_version: str
    import_path: str


def _manifest() -> ApiManifest:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("API manifest must be a JSON object.")
    raw_symbols = payload.get("symbols")  # type: ignore
    if not isinstance(raw_symbols, list):
        raise AssertionError("API manifest symbols must be a list.")
    symbols: list[ApiSymbol] = []
    for raw_symbol in raw_symbols:  # type: ignore
        if not isinstance(raw_symbol, dict):
            raise AssertionError("API manifest symbol must be an object.")
        name = raw_symbol.get("name")
        kind = raw_symbol.get("kind")
        module = raw_symbol.get("module")
        if not isinstance(name, str) or not isinstance(kind, str):
            raise AssertionError("API manifest symbol name/kind must be strings.")
        if module is not None and not isinstance(module, str):
            raise AssertionError("API manifest symbol module must be a string or null.")
        symbols.append({"name": name, "kind": kind, "module": module})
    contract_version = payload.get("contract_version", "")
    package_version = payload.get("package_version", "")
    import_path = payload.get("import_path", "")
    if not all(
        isinstance(value, str)
        for value in (contract_version, package_version, import_path)
    ):
        raise AssertionError("API manifest contract fields must be strings.")
    return {
        "symbols": symbols,
        "contract_version": contract_version,
        "package_version": package_version,
        "import_path": import_path,
    }


def test_exported_symbol_set_and_contract_version_are_frozen() -> None:
    """Keep the top-level export set synchronized with the versioned contract."""
    manifest = _manifest()
    names: list[str] = [item["name"] for item in manifest["symbols"]]
    assert names == list(statewake.__all__)
    assert manifest["contract_version"] == statewake.__public_api_contract_version__
    assert manifest["package_version"] == statewake.__version__
    assert manifest["import_path"] == "statewake"


def test_exported_symbols_resolve_from_top_level_package() -> None:
    """Ensure every advertised symbol is importable from the stable package path."""
    for name in statewake.__all__:
        assert getattr(statewake, name) is not None


def test_manifest_modules_remain_inside_statewake_namespace() -> None:
    """Prevent the public contract from accidentally pointing at external modules."""
    for item in _manifest()["symbols"]:
        module = item["module"]
        if module is not None:
            assert module == "statewake" or module.startswith("statewake.")


def test_public_functions_have_annotations_and_stable_signatures() -> None:
    """Require advertised functions to expose typed, inspectable call contracts."""
    manifest = _manifest()
    for item in manifest["symbols"]:
        if item["kind"] != "function":
            continue
        function = getattr(statewake, item["name"])
        assert inspect.signature(function) is not None
        hints = get_type_hints(function)
        assert hints
        assert "return" in hints


def test_public_datatypes_have_documentation_and_constructor_contracts() -> None:
    """Require advertised concrete types to have documented constructors."""
    manifest = _manifest()
    for item in manifest["symbols"]:
        if item["kind"] not in {"type", "exception"}:
            continue
        value = getattr(statewake, item["name"])
        assert inspect.getdoc(value)
        if item["kind"] == "type":
            assert inspect.signature(value) is not None


def test_official_python_examples_use_only_top_level_imports() -> None:
    """Keep release examples on the frozen consumer import boundary."""
    example_root = ROOT / "docs" / "release-artifact-docs"
    for path in example_root.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "from statewake.services import" not in text
        assert "from statewake.domain import" not in text
        assert "from statewake.adapters import" not in text


def test_cli_command_names_match_the_frozen_contract() -> None:
    """Keep CLI command names synchronized with the documented contract."""
    expected = {
        "version",
        "evidence-ingest",
        "evidence-verify",
        "evidence-admission-verify",
        "reliability-comparison",
        "reliability-comparison-verify",
        "evidence-chain",
        "reliability-state-transition",
        "reliability-state",
        "reliability-attest",
        "reliability-attest-verify",
        "reliability-outcome-verify",
        "reliability-recovery-verify",
        "reliability-lineage-verify",
        "reliability-reconciliation-bind",
        "reliability-reconciliation-verify",
        "reliability-proof-bundle",
        "reliability-proof-verify",
        "reliability-proof-completeness-verify",
        "reliability-decision-basis-build",
        "release-proof",
    }
    assert set(supported_commands()) == expected
    assert len(supported_commands()) == len(expected)
