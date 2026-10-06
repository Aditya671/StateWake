"""Regression tests for independent-oracle native host qualification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.testing.native_host_qualification import (
    FRAMEWORK_CASES,
    _status_for_matrix,
    run_native_host_qualification,
)


def _require_native_sdks() -> None:
    for module in (
        "agents.tracing",
        "langchain_core",
        "langgraph",
        "llama_index.core",
        "opentelemetry.sdk.trace",
    ):
        pytest.importorskip(module)


def test_native_host_qualification_covers_all_advertised_sdk_families() -> None:
    assert set(FRAMEWORK_CASES) == {
        "openai-agents",
        "langchain",
        "langgraph",
        "llamaindex",
        "opentelemetry",
    }
    assert FRAMEWORK_CASES["opentelemetry"] == "OTEL-GENAI-SPAN-001"


def test_matrix_status_never_promotes_blocked_or_failed_environment() -> None:
    assert _status_for_matrix("PASS") == "PASS"
    assert _status_for_matrix("BLOCKED_ENV") == "BLOCKED_ENV"
    assert _status_for_matrix("FAIL") == "FAIL_STATEWAKE"


def test_real_native_host_qualification_is_durable_private_and_independent(
    tmp_path: Path,
) -> None:
    _require_native_sdks()
    summary = run_native_host_qualification(
        evidence_root=tmp_path / "evidence",
        workspaces_root=tmp_path / "workspaces",
        timeout=120,
    )
    assert summary["status"] == "PASS"
    assert summary["native_sdk_matrix_status"] == "PASS"
    assert summary["publication_authorized"] is False
    assert summary["external_public_hosts_qualified"] is False
    host_results = summary["host_results"]
    assert isinstance(host_results, list)
    assert len(host_results) == 5
    assert {item["status"] for item in host_results} == {"PASS"}
    assert all(item["restart_verified"] for item in host_results)
    assert all(item["privacy_leakage_count"] == 0 for item in host_results)

    evidence = tmp_path / "evidence"
    for name in (
        "native-sdk-qualification.json",
        "native-host-truth-ledger.jsonl",
        "native-host-event-ledger.jsonl",
        "native-host-results.jsonl",
        "native-host-qualification-summary.json",
        "NATIVE_HOST_QUALIFICATION_REPORT.md",
    ):
        assert (evidence / name).is_file()

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in evidence.rglob("*")
        if path.is_file()
    )
    for marker in (
        "SW_PRIVATE_OPENAI_INPUT",
        "SW_PRIVATE_OPENAI_OUTPUT",
        "SW_PRIVATE_TOOL",
        "SW_PRIVATE_LANGCHAIN_CHUNK",
        "SW_PRIVATE_LANGCHAIN_QUERY",
        "SW_PRIVATE_LANGGRAPH_STATE",
        "SW_PRIVATE_LLAMA_QUERY",
        "SW_PRIVATE_LLAMA_CHUNK",
        "SW_PRIVATE_OTEL_INPUT",
    ):
        assert marker not in combined

    persisted = json.loads(
        (evidence / "native-host-qualification-summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["qualification_digest"] == summary["qualification_digest"]
