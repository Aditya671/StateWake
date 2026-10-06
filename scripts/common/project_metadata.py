"""Read release-sensitive project metadata from the canonical ``pyproject.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ProjectMetadataError(ValueError):
    """Raised when canonical project metadata is missing or malformed."""


@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    """Release-sensitive metadata derived from the project configuration."""

    distribution: str
    version: str
    import_package: str
    module_root: str
    cli_name: str
    cli_target: str
    repository_url: str

    @property
    def package_root_relative(self) -> Path:
        """Return the configured import-package directory relative to the repo root."""
        return Path(self.module_root, *self.import_package.split("."))

    @property
    def package_init_relative(self) -> Path:
        """Return the configured import package's ``__init__.py`` path."""
        return self.package_root_relative / "__init__.py"

    @property
    def cli_module(self) -> str:
        """Return the module portion of the configured console-script target."""
        module, separator, _callable = self.cli_target.partition(":")
        if not separator or not module:
            raise ProjectMetadataError(
                f"invalid console-script target for {self.cli_name!r}: {self.cli_target!r}"
            )
        return module

    @property
    def current_release_notes_relative(self) -> Path:
        """Return the release-notes path corresponding to the configured version."""
        return Path("docs", "releases", f"v{self.version}", "RELEASE_NOTES.md")

    @property
    def github_repository(self) -> tuple[str, str]:
        """Return ``(owner, repository)`` from the canonical GitHub repository URL."""
        parsed = urlparse(self.repository_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ProjectMetadataError(
                "project.urls.Repository must be an https://github.com/<owner>/<repo> URL"
            )
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) != 2:
            raise ProjectMetadataError(
                "project.urls.Repository must identify exactly one GitHub repository"
            )
        owner, repository = parts
        if repository.endswith(".git"):
            repository = repository[:-4]
        if not owner or not repository:
            raise ProjectMetadataError("GitHub repository owner/name cannot be empty")
        return owner, repository


def load_project_metadata(root: Path) -> ProjectMetadata:
    """Load release-sensitive metadata from the repository's ``pyproject.toml``."""
    with (root / "pyproject.toml").open("rb") as stream:
        document = tomllib.load(stream)

    project = document.get("project")
    if not isinstance(project, dict):
        raise ProjectMetadataError("pyproject.toml is missing [project]")

    distribution = project.get("name")
    version = project.get("version")
    scripts = project.get("scripts")
    urls = project.get("urls")
    build_backend = document.get("tool", {}).get("uv", {}).get("build-backend", {})
    import_package = build_backend.get("module-name")
    module_root = build_backend.get("module-root")

    if not isinstance(distribution, str) or not distribution:
        raise ProjectMetadataError("project.name must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ProjectMetadataError("project.version must be a non-empty string")
    if not isinstance(import_package, str) or not import_package:
        raise ProjectMetadataError("tool.uv.build-backend.module-name is required")
    if not isinstance(module_root, str) or not module_root:
        raise ProjectMetadataError("tool.uv.build-backend.module-root is required")
    if not isinstance(scripts, dict) or not scripts:
        raise ProjectMetadataError("project.scripts must define a console entry point")

    preferred_cli = import_package.split(".", 1)[0]
    cli_target = scripts.get(preferred_cli)
    if not isinstance(cli_target, str) or not cli_target:
        if len(scripts) != 1:
            raise ProjectMetadataError(
                "cannot identify the primary console script from project.scripts"
            )
        cli_name, cli_target_value = next(iter(scripts.items()))
        if not isinstance(cli_name, str) or not isinstance(cli_target_value, str):
            raise ProjectMetadataError("project.scripts contains an invalid entry")
        preferred_cli = cli_name
        cli_target = cli_target_value

    if not isinstance(urls, dict):
        raise ProjectMetadataError("project.urls is required")
    repository_url = urls.get("Repository")
    if not isinstance(repository_url, str) or not repository_url:
        raise ProjectMetadataError("project.urls.Repository is required")

    return ProjectMetadata(
        distribution=distribution,
        version=version,
        import_package=import_package,
        module_root=module_root,
        cli_name=preferred_cli,
        cli_target=cli_target,
        repository_url=repository_url,
    )
