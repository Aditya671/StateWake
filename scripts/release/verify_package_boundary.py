"""Verify that the built distribution contains only the intended active package boundary."""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from zipfile import ZipFile

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import DIST_PATH, PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


FORBIDDEN_MODULES = (
    "statewake.domain.chaos",
    "statewake.domain.control",
    "statewake.domain.control_audit",
    "statewake.domain.fairness",
    "statewake.domain.federation",
    "statewake.domain.impact",
    "statewake.domain.indexing",
    "statewake.domain.recording",
    "statewake.domain.remediation_execution",
    "statewake.domain.remediation_reconciliation",
    "statewake.domain.remediation_recovery",
    "statewake.domain.replay",
    "statewake.domain.runtime",
    "statewake.services.chaos_service",
    "statewake.services.control_audit_service",
    "statewake.services.federation_service",
    "statewake.services.impact_service",
    "statewake.services.index_service",
    "statewake.services.remediation_reconciliation_service",
    "statewake.services.remediation_recovery_service",
    "statewake.services.replay_service",
    "statewake.adapters.control_audit",
    "statewake.adapters.operational_index",
    "statewake.adapters.remediation_control",
    "statewake.adapters.remediation_execution",
    "statewake.adapters.remediation_reconciliation",
    "statewake.adapters.remediation_recovery",
    "statewake.adapters.runtime",
)

FORBIDDEN_PARTS = (
    "/domain/chaos.py",
    "/domain/control.py",
    "/domain/control_audit.py",
    "/domain/fairness.py",
    "/domain/federation.py",
    "/domain/impact.py",
    "/domain/indexing.py",
    "/domain/recording.py",
    "/domain/remediation_execution.py",
    "/domain/remediation_reconciliation.py",
    "/domain/remediation_recovery.py",
    "/domain/replay.py",
    "/domain/runtime.py",
    "/services/chaos_service.py",
    "/services/control_audit_service.py",
    "/services/federation_service.py",
    "/services/impact_service.py",
    "/services/index_service.py",
    "/services/remediation_reconciliation_service.py",
    "/services/remediation_recovery_service.py",
    "/services/replay_service.py",
    "/adapters/control_audit.py",
    "/adapters/operational_index.py",
    "/adapters/remediation_control.py",
    "/adapters/remediation_execution.py",
    "/adapters/remediation_reconciliation.py",
    "/adapters/remediation_recovery.py",
    "/adapters/runtime.py",
)


def _source_module_map() -> dict[str, Path]:
    """Return importable source modules keyed by fully qualified module name."""
    root = SRC_PATH
    modules: dict[str, Path] = {}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).with_suffix("")
        modules[".".join(relative.parts)] = path
    return modules


def _imports(module: str, path: Path) -> set[str]:
    """Return directly imported module names, resolving relative imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    package = module.rsplit(".", 1)[0] if "." in module else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            base = node.module or ""
        else:
            parts = package.split(".") if package else []
            if node.level > len(parts) + 1:
                continue
            base_parts = parts[: len(parts) - node.level + 1]
            base = ".".join(base_parts)
            if node.module:
                base = f"{base}.{node.module}" if base else node.module
        if base:
            imports.add(base)
        else:
            imports.update(
                f"{module.rsplit('.', 1)[0]}.{alias.name}"
                if "." in module
                else alias.name
                for alias in node.names
            )
    return imports


def _verify_cli_import_closure() -> None:
    """Ensure the retained CLI cannot depend on source-excluded modules."""
    modules = _source_module_map()
    # Reconstruct the exact excluded module names from pyproject.toml, so this
    # check stays synchronized with the distribution boundary declaration.
    project_root = PROJECT_ROOT
    with (project_root / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    excluded = {
        path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        for path in config.get("tool", {})
        .get("uv", {})
        .get("build-backend", {})
        .get("source-exclude", [])
        if path.startswith("src/") and path.endswith(".py")
    }

    start = "statewake.cli.main"
    seen: set[str] = set()
    stack = [start]
    offenders: set[tuple[str, str]] = set()
    while stack:
        module = stack.pop()
        if module in seen or module not in modules:
            continue
        seen.add(module)
        for imported in _imports(module, modules[module]):
            if imported in excluded or any(
                imported.startswith(f"{item}.") for item in excluded
            ):
                offenders.add((module, imported))
            if imported in modules:
                stack.append(imported)
    if offenders:
        formatted = ", ".join(
            f"{source} -> {target}" for source, target in sorted(offenders)
        )
        raise SystemExit("CLI imports source-excluded module(s): " + formatted)


def verify(wheel: Path) -> None:
    """Fail when forbidden historical implementations appear in the release boundary."""
    source_modules = _source_module_map()
    stale_source = sorted(set(source_modules) & set(FORBIDDEN_MODULES))
    if stale_source:
        raise SystemExit(
            "forbidden historical source modules: " + ", ".join(stale_source)
        )
    project_root = PROJECT_ROOT
    if (project_root / "legacy").exists():
        raise SystemExit(
            "stale legacy directories must remain outside the stabilized source tree"
        )
    _verify_cli_import_closure()
    with ZipFile(wheel) as archive:
        names = archive.namelist()
    offenders = [
        name for name in names if any(name.endswith(part) for part in FORBIDDEN_PARTS)
    ]
    generated = [
        name
        for name in names
        if "__pycache__/" in name or name.endswith((".pyc", ".pyo"))
    ]
    if generated:
        raise SystemExit(
            "generated Python cache artifacts in wheel: " + ", ".join(sorted(generated))
        )
    if offenders:
        raise SystemExit(
            "forbidden historical package entries: " + ", ".join(sorted(offenders))
        )
    required = {
        "statewake/__init__.py",
        "statewake/public_api.py",
        "statewake/server.py",
        "statewake/adapters/first_party_evidence.py",
    }
    missing = sorted(required - set(names))
    if missing:
        raise SystemExit(
            "required active package entries missing: " + ", ".join(missing)
        )
    print(f"package boundary: verified {wheel.name}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DIST_PATH
    if target.is_file():
        if target.suffix != ".whl":
            raise SystemExit(f"expected a wheel file, got {target}")
        verify(target)
    else:
        wheels = sorted(target.glob("*.whl"))
        if len(wheels) != 1:
            raise SystemExit(
                f"expected exactly one wheel in {target}, found {len(wheels)}"
            )
        verify(wheels[0])
