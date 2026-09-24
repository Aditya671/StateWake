"""Durable diagnostics must enforce configured disk and restart limits."""

from pathlib import Path

import pytest

from statewake.integrations.native_capture import (
    NativeCaptureCapacityError,
    NativeCaptureSink,
)


def test_journal_rejects_unbounded_append_and_startup(tmp_path: Path) -> None:
    path = tmp_path / "failures.jsonl"
    sink = NativeCaptureSink(failure_journal=path, failure_journal_max_bytes=80)
    sink.fail("native", ValueError("private-value"))
    before = path.read_bytes()
    with pytest.raises(NativeCaptureCapacityError, match="size limit"):
        sink.fail("native", ValueError("private-value"))
    assert path.read_bytes() == before
    assert sink.failure_count == 1
    with pytest.raises(NativeCaptureCapacityError, match="size limit"):
        NativeCaptureSink(failure_journal=path, failure_journal_max_bytes=8)


def _create_directory_symlink_or_skip(link: Path, target: Path) -> None:
    """Create a directory symlink or skip when the platform disallows it."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip(
                "Windows symlink creation requires Developer Mode "
                "or SeCreateSymbolicLinkPrivilege."
            )
        raise


def test_journal_rejects_symlinked_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    _create_directory_symlink_or_skip(link, real)
    with pytest.raises(ValueError, match="symlink"):
        NativeCaptureSink(failure_journal=link / "failures.jsonl")
