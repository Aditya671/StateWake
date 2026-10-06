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


def test_failure_journal_snapshot_uses_runtime_redaction_contract(
    tmp_path: Path,
) -> None:
    from statewake.integrations.native_capture import (
        read_native_capture_failure_journal_snapshot,
    )

    path = tmp_path / "failures.jsonl"
    path.write_text(
        '{"stage":"native_capture.persist","error_type":"OSError"}\n'
        '{"stage":"langchain.retriever_start","error_type":"AttributeError"}\n',
        encoding="utf-8",
    )
    snapshot = read_native_capture_failure_journal_snapshot(
        path, max_bytes=1024, max_records=10
    )
    assert snapshot.exists is True
    assert snapshot.byte_size == path.stat().st_size
    assert [item.to_dict() for item in snapshot.records] == [
        {"sequence": 0, "stage": "native_capture.persist", "error_type": "OSError"},
        {
            "sequence": 1,
            "stage": "langchain.retriever_start",
            "error_type": "AttributeError",
        },
    ]


def test_failure_journal_snapshot_rejects_partial_or_extra_fields(
    tmp_path: Path,
) -> None:
    from statewake.integrations.native_capture import (
        read_native_capture_failure_journal_snapshot,
    )

    path = tmp_path / "failures.jsonl"
    path.write_text(
        '{"stage":"native_capture.persist","error_type":"OSError"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="partial trailing entry"):
        read_native_capture_failure_journal_snapshot(
            path, max_bytes=1024, max_records=10
        )

    path.write_text(
        '{"stage":"native_capture.persist","error_type":"OSError","message":"secret"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid failure journal entry"):
        read_native_capture_failure_journal_snapshot(
            path, max_bytes=1024, max_records=10
        )


def test_failure_journal_snapshot_missing_file_is_a_zero_record_snapshot(
    tmp_path: Path,
) -> None:
    from statewake.integrations.native_capture import (
        read_native_capture_failure_journal_snapshot,
    )

    snapshot = read_native_capture_failure_journal_snapshot(
        tmp_path / "not-created-yet.jsonl", max_bytes=1024, max_records=10
    )
    assert snapshot.exists is False
    assert snapshot.byte_size == 0
    assert snapshot.records == ()
