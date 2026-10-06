"""Credential-free native-SDK host qualification with independent host truth.

This module is research/testing infrastructure. It composes the existing native
SDK qualification authority with small real-SDK host exercises; it does not add
a StateWake runtime authority and never treats StateWake observations as host
truth.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal

from scripts.testing.run_public_trial_regressions import run_matrix
from statewake.integrations.native_capture import NativeCaptureSink
from statewake.workspace import StateWakeWorkspace
from statewake.workspace.models import WorkspaceRecordQuery

QualificationStatus = Literal[
    "PASS", "FAIL_STATEWAKE", "FAIL_INTEGRATION", "BLOCKED_ENV"
]

FRAMEWORK_CASES: Final = {
    "openai-agents": "OA-RESPONSES-001",
    "langchain": "LC-RAG-SYNTHETIC-001",
    "langgraph": "LG-STARTER-CHECKPOINT-002",
    "llamaindex": "LI-RAG-ROOT-DIAGNOSTIC-002",
    "opentelemetry": "OTEL-GENAI-SPAN-001",
}


@dataclass(frozen=True, slots=True)
class NativeHostProbeResult:
    """Bounded qualification result for one installed native SDK host exercise."""

    framework: str
    qualification_case_id: str
    status: QualificationStatus
    installed_distribution: str | None
    installed_version: str | None
    required_observations_met: tuple[str, ...]
    required_observations_missing: tuple[str, ...]
    forbidden_observations_seen: tuple[str, ...]
    statewake_failure_count: int
    durable_record_count: int
    restart_verified: bool
    privacy_leakage_count: int
    wall_ms: float
    evidence_digest: str
    reason: str | None


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def _matrix_case(record: dict[str, object], case_id: str) -> dict[str, object] | None:
    raw = record.get("results")
    if not isinstance(raw, list):
        return None
    for item in raw:
        if isinstance(item, dict) and item.get("case_id") == case_id:
            return item
    return None


def _dependency(case: dict[str, object] | None) -> tuple[str | None, str | None]:
    if case is None:
        return None, None
    deps = case.get("dependencies")
    if not isinstance(deps, list) or not deps or not isinstance(deps[0], dict):
        return None, None
    distribution = deps[0].get("distribution")
    version = deps[0].get("installed_version")
    return (
        distribution if isinstance(distribution, str) else None,
        version if isinstance(version, str) else None,
    )


def _truth_event(
    framework: str, sequence: int, key: str, value: object
) -> dict[str, object]:
    return {
        "framework": framework,
        "sequence": sequence,
        "event_key": key,
        "value": str(value),
        "source": "independent-native-host-ledger",
    }


def _observation_rows(
    framework: str, sink: NativeCaptureSink
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sequence, item in enumerate(sink.snapshot(), 1):
        payload = item.payload
        contract_type = payload.get("contract_type")
        rows.append(
            {
                "framework": framework,
                "sequence": sequence,
                "observation_key": f"capture.{contract_type}",
                "logical_run_id": payload.get("run_id"),
                "producer_id": payload.get("producer_id"),
                "native_event_id": payload.get("span_id"),
                "contract_type": contract_type,
                "contract_digest": item.digest,
                "actual": "captured",
                "detector": "statewake-native-integration",
            }
        )
    return rows


def _durability(workspace_root: Path, expected: int) -> tuple[int, bool]:
    workspace = StateWakeWorkspace.open_read_only(workspace_root)
    try:
        page = workspace.query(WorkspaceRecordQuery(limit=1000))
        report = workspace.verify()
        verified = report is None or not report.has_errors
        return page.total_count, verified and page.total_count == expected
    finally:
        workspace.close()


def _scan_markers(root: Path, records: object, markers: tuple[str, ...]) -> int:
    serialized = json.dumps(records, sort_keys=True, ensure_ascii=False)
    count = sum(serialized.count(marker) for marker in markers)
    for path in root.rglob("*"):
        if not path.is_file() or "privacy" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count += sum(text.count(marker) for marker in markers)
    return count


def _openai_probe(
    workspace: Path,
) -> tuple[
    list[dict[str, object]],
    NativeCaptureSink,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from agents.tracing import (
        function_span,
        generation_span,
        set_trace_processors,
        set_tracing_disabled,
        trace,
    )

    from statewake.integrations.native_openai_agents import (
        create_agents_trace_processor,
    )

    markers = ("SW_PRIVATE_OPENAI_INPUT", "SW_PRIVATE_OPENAI_OUTPUT", "SW_PRIVATE_TOOL")
    statewake = StateWakeWorkspace.open(workspace)
    sink = NativeCaptureSink(
        workspace=statewake,
        failure_journal=workspace / "native-capture-failures.jsonl",
    )
    processor = create_agents_trace_processor(
        sink, side_effect_classifications={"statewake_host_tool": "none"}
    )
    set_tracing_disabled(False)
    set_trace_processors([processor])
    try:
        with trace("statewake-independent-oracle-host"):
            with generation_span(
                input=[{"role": "user", "content": markers[0]}],
                output=[{"role": "assistant", "content": markers[1]}],
                model="statewake-host-model",
            ):
                pass
            with function_span(
                name="statewake_host_tool",
                input=json.dumps({"value": markers[2]}),
                output=json.dumps({"ok": True, "value": markers[2]}),
            ):
                pass
    finally:
        set_trace_processors([])
        statewake.close()
    truth = [
        _truth_event("openai-agents", 1, "host.trace.completed", True),
        _truth_event("openai-agents", 2, "host.generation.completed", True),
        _truth_event("openai-agents", 3, "host.tool.completed", True),
    ]
    return (
        truth,
        sink,
        ("capture.runtime_trace", "capture.model_invocation", "capture.tool_call"),
        ("assurance.tool_authorized",),
        markers,
    )


def _langchain_probe(
    workspace: Path,
) -> tuple[
    list[dict[str, object]],
    NativeCaptureSink,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from typing import Any

    from langchain_core.documents import Document
    from langchain_core.retrievers import BaseRetriever

    from statewake.integrations.native_langchain import (
        create_langchain_callback_handler,
    )

    marker = "SW_PRIVATE_LANGCHAIN_CHUNK"

    class LocalRetriever(BaseRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Any]:
            return [Document(id="host-doc-1", page_content=marker)]

    statewake = StateWakeWorkspace.open(workspace)
    sink = NativeCaptureSink(
        workspace=statewake,
        failure_journal=workspace / "native-capture-failures.jsonl",
    )
    handler = create_langchain_callback_handler(
        sink,
        corpus_identity="host-corpus-1",
        corpus_snapshot_id="host-snapshot-1",
        citation_boundary="document-id",
    )
    docs = LocalRetriever().invoke(
        "SW_PRIVATE_LANGCHAIN_QUERY", config={"callbacks": [handler]}
    )
    statewake.close()
    truth = [
        _truth_event("langchain", 1, "host.retrieval.count", len(docs)),
        _truth_event("langchain", 2, "host.retrieval.document_id", docs[0].id),
    ]
    return (
        truth,
        sink,
        ("capture.retrieval", "capture.runtime_trace"),
        ("assurance.current_source_used",),
        (marker, "SW_PRIVATE_LANGCHAIN_QUERY"),
    )


def _langgraph_probe(
    workspace: Path,
) -> tuple[
    list[dict[str, object]],
    NativeCaptureSink,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from typing import TypedDict

    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    from statewake.integrations.native_langgraph import capture_langgraph_history

    marker = "SW_PRIVATE_LANGGRAPH_STATE"

    class GraphState(TypedDict):
        count: int
        private: str

    def increment(state: GraphState) -> GraphState:
        return {"count": state["count"] + 1, "private": state["private"]}

    graph = StateGraph(GraphState)
    graph.add_node("increment", increment)
    graph.add_edge(START, "increment")
    graph.add_edge("increment", END)
    compiled = graph.compile(checkpointer=MemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "statewake-host-thread"}}
    final = compiled.invoke({"count": 1, "private": marker}, config)

    statewake = StateWakeWorkspace.open(workspace)
    sink = NativeCaptureSink(
        workspace=statewake,
        failure_journal=workspace / "native-capture-failures.jsonl",
    )
    captured = capture_langgraph_history(compiled, config, sink)
    statewake.close()
    truth = [
        _truth_event("langgraph", 1, "host.graph.final_count", final["count"]),
        _truth_event("langgraph", 2, "host.graph.checkpoint_count", len(captured)),
    ]
    return (
        truth,
        sink,
        ("capture.observation",),
        ("assurance.execution_completed",),
        (marker,),
    )


def _llamaindex_probe(
    workspace: Path,
) -> tuple[
    list[dict[str, object]],
    NativeCaptureSink,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from llama_index.core.instrumentation.events.retrieval import (
        RetrievalEndEvent,
        RetrievalStartEvent,
    )
    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
    from llama_index_instrumentation import get_dispatcher

    from statewake.integrations.native_llamaindex import (
        attach_llamaindex_event_handler,
        detach_llamaindex_event_handler,
    )

    query_marker = "SW_PRIVATE_LLAMA_QUERY"
    chunk_marker = "SW_PRIVATE_LLAMA_CHUNK"
    statewake = StateWakeWorkspace.open(workspace)
    sink = NativeCaptureSink(
        workspace=statewake,
        failure_journal=workspace / "native-capture-failures.jsonl",
    )
    handler = attach_llamaindex_event_handler(
        sink,
        corpus_identity="host-llama-corpus",
        corpus_snapshot_id="host-llama-snapshot",
        citation_boundary="node-id",
    )
    dispatcher = get_dispatcher()
    query = QueryBundle(query_marker)
    node = NodeWithScore(node=TextNode(id_="host-node-1", text=chunk_marker), score=1.0)
    try:
        dispatcher.event(
            RetrievalStartEvent(str_or_query_bundle=query, span_id="host-span")
        )
        dispatcher.event(
            RetrievalEndEvent(
                str_or_query_bundle=query,
                nodes=[node],
                span_id="host-span",
            )
        )
    finally:
        detach_llamaindex_event_handler(handler)
        statewake.close()
    truth = [
        _truth_event("llamaindex", 1, "host.retrieval.count", 1),
        _truth_event("llamaindex", 2, "host.retrieval.node_id", "host-node-1"),
    ]
    return (
        truth,
        sink,
        ("capture.retrieval", "capture.observation"),
        ("assurance.current_source_used",),
        (query_marker, chunk_marker),
    )


def _opentelemetry_probe(
    workspace: Path,
) -> tuple[
    list[dict[str, object]],
    NativeCaptureSink,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    from opentelemetry.sdk.trace import TracerProvider

    from statewake.integrations.native_opentelemetry import create_genai_span_processor

    marker = "SW_PRIVATE_OTEL_INPUT"
    statewake = StateWakeWorkspace.open(workspace)
    sink = NativeCaptureSink(
        workspace=statewake,
        failure_journal=workspace / "native-capture-failures.jsonl",
    )
    provider = TracerProvider()
    provider.add_span_processor(create_genai_span_processor(sink))
    tracer = provider.get_tracer("statewake-independent-host")
    with tracer.start_as_current_span("host-chat") as span:
        span.set_attribute("statewake.run_id", "otel-host-run")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "statewake-host-model")
        span.set_attribute("gen_ai.input.messages", marker)
    provider.shutdown()
    statewake.close()
    truth = [_truth_event("opentelemetry", 1, "host.span.completed", True)]
    return (
        truth,
        sink,
        ("capture.runtime_trace",),
        ("capture.raw_prompt",),
        (marker,),
    )


_PROBES = {
    "openai-agents": _openai_probe,
    "langchain": _langchain_probe,
    "langgraph": _langgraph_probe,
    "llamaindex": _llamaindex_probe,
    "opentelemetry": _opentelemetry_probe,
}


def _status_for_matrix(matrix_status: object) -> QualificationStatus:
    if matrix_status == "PASS":
        return "PASS"
    if matrix_status == "BLOCKED_ENV":
        return "BLOCKED_ENV"
    return "FAIL_STATEWAKE"


def run_native_host_qualification(
    *,
    evidence_root: Path,
    workspaces_root: Path,
    timeout: int = 180,
) -> dict[str, object]:
    """Run native SDK qualification plus independent-oracle host exercises."""
    evidence_root.mkdir(parents=True, exist_ok=True)
    workspaces_root.mkdir(parents=True, exist_ok=True)
    matrix = run_matrix(timeout=timeout, mode="qualification")
    (evidence_root / "native-sdk-qualification.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    matrix_digest = _digest(matrix)

    truth_rows: list[dict[str, object]] = []
    observation_rows: list[dict[str, object]] = []
    results: list[NativeHostProbeResult] = []
    for framework, case_id in FRAMEWORK_CASES.items():
        case = _matrix_case(matrix, case_id)
        distribution, version = _dependency(case)
        if case is None:
            result = NativeHostProbeResult(
                framework,
                case_id,
                "FAIL_INTEGRATION",
                distribution,
                version,
                (),
                (),
                (),
                0,
                0,
                False,
                0,
                0.0,
                _digest({"missing_case": case_id}),
                "native qualification case is missing",
            )
            results.append(result)
            continue
        case_status = case.get("status")
        if case_status != "PASS":
            prerequisite_status: QualificationStatus = (
                "BLOCKED_ENV" if case_status == "BLOCKED_ENV" else "FAIL_STATEWAKE"
            )
            result = NativeHostProbeResult(
                framework,
                case_id,
                prerequisite_status,
                distribution,
                version,
                (),
                (),
                (),
                0,
                0,
                False,
                0,
                0.0,
                _digest({"case": case_id, "status": case_status}),
                "native SDK compatibility prerequisite did not pass",
            )
            results.append(result)
            continue

        workspace = workspaces_root / framework
        start = time.perf_counter()
        try:
            truth, sink, required, forbidden, markers = _PROBES[framework](workspace)
            observations = _observation_rows(framework, sink)
            keys = {str(item["observation_key"]) for item in observations}
            met = tuple(item for item in required if item in keys)
            missing = tuple(item for item in required if item not in keys)
            forbidden_seen = tuple(item for item in forbidden if item in keys)
            durable_count, restart_verified = _durability(
                workspace, len(sink.snapshot())
            )
            leakage = _scan_markers(workspace, (truth, observations), markers)
            probe_status: QualificationStatus = "PASS"
            reason: str | None = None
            if (
                missing
                or forbidden_seen
                or sink.failure_count
                or not restart_verified
                or leakage
            ):
                probe_status = "FAIL_STATEWAKE"
                reason = (
                    "native host evidence failed StateWake qualification invariants"
                )
            digest = _digest(
                {
                    "framework": framework,
                    "truth": truth,
                    "observations": observations,
                    "required": required,
                    "forbidden": forbidden,
                    "durable_record_count": durable_count,
                    "restart_verified": restart_verified,
                    "privacy_leakage_count": leakage,
                }
            )
            truth_rows.extend(truth)
            observation_rows.extend(observations)
            result = NativeHostProbeResult(
                framework=framework,
                qualification_case_id=case_id,
                status=probe_status,
                installed_distribution=distribution,
                installed_version=version,
                required_observations_met=met,
                required_observations_missing=missing,
                forbidden_observations_seen=forbidden_seen,
                statewake_failure_count=sink.failure_count,
                durable_record_count=durable_count,
                restart_verified=restart_verified,
                privacy_leakage_count=leakage,
                wall_ms=(time.perf_counter() - start) * 1000.0,
                evidence_digest=digest,
                reason=reason,
            )
        except ModuleNotFoundError:
            result = NativeHostProbeResult(
                framework,
                case_id,
                "BLOCKED_ENV",
                distribution,
                version,
                (),
                (),
                (),
                0,
                0,
                False,
                0,
                (time.perf_counter() - start) * 1000.0,
                _digest({"framework": framework, "blocked": True}),
                "installed native SDK environment is incomplete",
            )
        except (
            Exception
        ) as exc:  # framework boundary; raw exception text is not persisted
            result = NativeHostProbeResult(
                framework,
                case_id,
                "FAIL_INTEGRATION",
                distribution,
                version,
                (),
                (),
                (),
                0,
                0,
                False,
                0,
                (time.perf_counter() - start) * 1000.0,
                _digest({"framework": framework, "error_type": type(exc).__name__}),
                f"native host execution failed with {type(exc).__name__}",
            )
        results.append(result)

    _write_jsonl(evidence_root / "native-host-truth-ledger.jsonl", truth_rows)
    _write_jsonl(evidence_root / "native-host-event-ledger.jsonl", observation_rows)
    _write_jsonl(
        evidence_root / "native-host-results.jsonl",
        [asdict(item) for item in results],
    )
    statuses = {item.status for item in results}
    matrix_status = _status_for_matrix(matrix.get("status"))
    if matrix_status == "PASS" and statuses <= {"PASS"}:
        overall: QualificationStatus = "PASS"
    elif matrix_status == "BLOCKED_ENV" or statuses <= {"PASS", "BLOCKED_ENV"}:
        overall = "BLOCKED_ENV"
    elif "FAIL_INTEGRATION" in statuses:
        overall = "FAIL_INTEGRATION"
    else:
        overall = "FAIL_STATEWAKE"

    summary: dict[str, object] = {
        "schema_version": 1,
        "workflow": "statewake-independent-oracle-native-host-qualification",
        "status": overall,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "native_sdk_matrix_status": matrix.get("status"),
        "native_sdk_matrix_digest": matrix_digest,
        "host_results": [asdict(item) for item in results],
        "truth_ledger_sha256": sha256(
            (evidence_root / "native-host-truth-ledger.jsonl").read_bytes()
        ).hexdigest(),
        "event_ledger_sha256": sha256(
            (evidence_root / "native-host-event-ledger.jsonl").read_bytes()
        ).hexdigest(),
        "publication_authorized": False,
        "external_public_hosts_qualified": False,
    }
    summary["qualification_digest"] = _digest(summary)
    (evidence_root / "native-host-qualification-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# StateWake Independent-Oracle Native Host Qualification",
        "",
        f"- Overall status: **{overall}**",
        f"- Python: `{summary['python_version']}`",
        f"- Native SDK matrix: **{matrix.get('status')}**",
        f"- Qualification digest: `{summary['qualification_digest']}`",
        "- Publication authorized: **No**",
        "- External public hosts qualified: **No**",
        "",
        "| Framework | SDK | Host qualification | Durable restart | Privacy leakage |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for item in results:
        sdk = (
            f"{item.installed_distribution}={item.installed_version}"
            if item.installed_distribution
            else "unknown"
        )
        lines.append(
            f"| `{item.framework}` | {sdk} | {item.status} | "
            f"{'yes' if item.restart_verified else 'no'} | {item.privacy_leakage_count} |"
        )
    lines.extend(
        [
            "",
            "This report proves only the credential-free native SDK and local host boundary in the tested environment. It does not claim paid/live model success, factual correctness of upstream frameworks, or qualification of external public host repositories.",
            "",
        ]
    )
    (evidence_root / "NATIVE_HOST_QUALIFICATION_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return summary
