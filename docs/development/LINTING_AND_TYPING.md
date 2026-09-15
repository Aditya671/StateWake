# Source linting and typing contract

The stabilized `src/` tree is the only runtime source tree. StateWake uses
Ruff for formatting, import organization, linting, and PEP 257 docstring
enforcement, with Pyright/Pylance in strict type-checking mode.

## Ruff language server

StateWake uses Ruff's native language server (`ruff server`), not the retired
`ruff-lsp` implementation. Ruff's migration guidance explicitly deprecates
`ruff.lint.args`, `ruff.format.args`, and `ruff.lint.run` for the native server;
those settings are therefore absent from `.vscode/settings.json`. The project
uses `ruff.configuration` for the canonical `pyproject.toml`, `ruff.lint.preview`
for preview linting, and `ruff.lineLength` for the editor-level line-length
setting.

The VS Code workspace also enables Ruff as the Python formatter and exposes
Ruff's explicit fix-all and import-organization actions. This keeps formatting,
import organization, and diagnostics on the native server path.

## Commands

```bash
uvx ruff check src tests scripts
uvx ruff format --check src tests scripts
uvx pyright
```

Ruff is configured from `pyproject.toml`; Pyright uses the `[tool.pyright]`
configuration and the VS Code Pylance workspace settings.

## Documentation requirement

Every Python module, class, and function in the active `src/` tree must have a
docstring. Ruff's `D` rules enforce the project documentation contract, and the
repository verification process independently checks the AST for missing
docstrings.

The legacy archive is intentionally excluded from lint and type-check scope.
