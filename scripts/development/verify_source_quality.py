"""Verify the stabilized Python source against local quality invariants."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


ROOT = SRC_PATH
MAX_LINE_LENGTH = 88


def _public_missing_docs(tree: ast.AST, path: Path) -> list[str]:
    """Return public definitions without PEP 257 docstrings."""
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name.startswith("_") or ast.get_docstring(node) is not None:
            continue
        issues.append(f"{path}:{node.lineno}:{node.name}:missing-docstring")
    return issues


def _annotation_issues(tree: ast.AST, path: Path) -> list[str]:
    """Return functions with missing strict-mode annotations."""
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.returns is None:
            issues.append(f"{path}:{node.lineno}:{node.name}:missing-return-annotation")
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            if arg.arg not in {"self", "cls"} and arg.annotation is None:
                issues.append(
                    f"{path}:{node.lineno}:{node.name}:missing-annotation:{arg.arg}"
                )
    return issues


def main() -> None:
    """Verify source syntax, whitespace, documentation, and annotations."""
    issues: list[str] = []
    line_length_warnings: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if "\t" in line:
                issues.append(f"{path}:{line_number}:tab-character")
            if line.rstrip() != line:
                issues.append(f"{path}:{line_number}:trailing-whitespace")
            if len(line) > MAX_LINE_LENGTH:
                line_length_warnings.append(f"{path}:{line_number}:{len(line)}")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            issues.append(f"{path}:{exc.lineno}:syntax-error:{exc.msg}")
            continue
        if ast.get_docstring(tree) is None:
            issues.append(f"{path}:1:missing-module-docstring")
        issues.extend(_public_missing_docs(tree, path))
        issues.extend(_annotation_issues(tree, path))
    if issues:
        raise SystemExit("source quality verification failed:\n" + "\n".join(issues))
    count = len(list(ROOT.rglob("*.py")))
    warning = (
        f"; {len(line_length_warnings)} line-length items remain for Ruff formatting"
        if line_length_warnings
        else ""
    )
    print(f"source quality: verified {count} Python modules{warning}")


if __name__ == "__main__":
    main()
