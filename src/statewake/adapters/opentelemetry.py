"""OpenTelemetry bridge for canonical StateWake events.

OpenTelemetry API support is a declared StateWake dependency; SDK/provider configuration
remains the responsibility of the integrating application.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ..domain.events import EventEnvelope
from ..domain.evidence import EvidenceManifest
from ..domain.governance import (
    PrivacyGovernanceRuntimeConfig,
    evaluate_evidence_governance,
    project_manifest_for_telemetry,
)
from ..domain.privacy import PrivacyPolicy, Redactor


class OpenTelemetryTelemetrySink:
    """Map one canonical run to one OpenTelemetry span with ordered span events.

    The adapter accepts the OpenTelemetry tracer object rather than configuring an SDK,
    exporter, resource, or provider. Applications remain responsible for SDK setup.
    """

    def __init__(
        self,
        tracer: Any,
        *,
        instrumentation_scope: str = "statewake-ai",
        privacy_policy: PrivacyPolicy | None = None,
        privacy_governance: PrivacyGovernanceRuntimeConfig | None = None,
    ) -> None:
        """Initialize this component with its configured state."""
        if tracer is None or not hasattr(tracer, "start_span"):
            raise TypeError("tracer must provide the OpenTelemetry Tracer API.")
        self.tracer = tracer
        if privacy_policy is not None and privacy_governance is not None:
            raise ValueError(
                "privacy_policy and privacy_governance are mutually exclusive"
            )
        self.instrumentation_scope = instrumentation_scope
        effective_privacy = (
            privacy_governance.privacy_policy
            if privacy_governance is not None
            else privacy_policy
        )
        self._privacy_governance = privacy_governance
        self._redactor = (
            Redactor(effective_privacy) if effective_privacy is not None else None
        )
        self._spans: dict[str, Any] = {}

    def emit(
        self,
        event: EventEnvelope,
        *,
        evidence_manifest: EvidenceManifest | None = None,
    ) -> None:
        """Translate one canonical event into an OpenTelemetry run span/event."""
        if self._redactor is not None:
            event = self._redactor.redact_event(event)
        timestamp = _timestamp_ns(event.occurred_at)
        if evidence_manifest is not None and evidence_manifest.run_id != event.run_id:
            raise ValueError("evidence manifest run_id does not match telemetry event")
        if event.event_type == "run.started":
            attributes = _span_attributes(event)
            if evidence_manifest is not None:
                if self._privacy_governance is None:
                    raise ValueError(
                        "evidence telemetry projection requires privacy_governance"
                    )
                attributes.update(
                    _evidence_governance_attributes(
                        evidence_manifest, self._privacy_governance
                    )
                )
            span = self.tracer.start_span(
                event.name or "agent.run",
                attributes=attributes,
                start_time=timestamp,
            )
            self._spans[event.run_id] = span
            return

        span = self._spans.get(event.run_id)
        if span is None:
            raise ValueError("Received non-start event before run.started.")
        span.add_event(
            event.event_type, attributes=_event_attributes(event), timestamp=timestamp
        )

        if event.event_type in {"run.completed", "run.failed"}:
            _set_terminal_status(span, success=event.event_type == "run.completed")
            span.end(end_time=timestamp)
            self._spans.pop(event.run_id, None)

    def close(self) -> None:
        """End any incomplete spans as aborted telemetry."""
        for span in self._spans.values():
            _set_terminal_status(span, success=False)
            span.end()
        self._spans.clear()


def export_recorded_run(
    events: list[EventEnvelope],
    tracer: Any,
    *,
    privacy_policy: PrivacyPolicy | None = None,
    privacy_governance: PrivacyGovernanceRuntimeConfig | None = None,
    evidence_manifest: EvidenceManifest | None = None,
) -> None:
    """Export one validated recorded run through the OpenTelemetry bridge."""
    sink = OpenTelemetryTelemetrySink(
        tracer,
        privacy_policy=privacy_policy,
        privacy_governance=privacy_governance,
    )
    try:
        for event in events:
            sink.emit(event, evidence_manifest=evidence_manifest)
    finally:
        sink.close()


def inject_trace_context(carrier: dict[str, str], context: Any | None = None) -> None:
    """Inject the active OpenTelemetry trace context into a carrier.

    OpenTelemetry is imported lazily so this helper stays isolated from provider setup.
    """
    from opentelemetry.propagate import inject

    inject(carrier=carrier, context=context)


def extract_trace_context(carrier: Mapping[str, str]) -> Any:
    """Extract OpenTelemetry trace context from a W3C-compatible carrier."""
    from opentelemetry.propagate import extract

    return extract(carrier=dict(carrier))


def _timestamp_ns(value: datetime) -> int:
    """Return the current timestamp in nanoseconds for event capture."""
    return int(value.astimezone(UTC).timestamp() * 1_000_000_000)


def _span_attributes(event: EventEnvelope) -> dict[str, str]:
    """Build OpenTelemetry span attributes for a StateWake operation."""
    attributes = {
        "statewake.run_id": event.run_id,
        "statewake.agent": event.name or "unknown",
        "statewake.actor": event.actor,
    }
    if event.state_id:
        attributes["statewake.state_id"] = event.state_id
    return attributes


def _event_attributes(event: EventEnvelope) -> dict[str, str]:
    """Build OpenTelemetry event attributes for a StateWake event."""
    attributes = {
        "statewake.run_id": event.run_id,
        "statewake.actor": event.actor,
    }
    if event.name:
        attributes["statewake.name"] = event.name
    if event.state_id:
        attributes["statewake.state_id"] = event.state_id
    if event.payload_ref:
        attributes["statewake.payload_ref"] = event.payload_ref
    for key, value in event.metadata.items():
        attributes[f"statewake.meta.{key}"] = value
    return attributes


def _evidence_governance_attributes(
    manifest: EvidenceManifest,
    runtime: PrivacyGovernanceRuntimeConfig,
) -> dict[str, str]:
    """Return metadata-only telemetry attributes allowed by evidence governance."""
    decision = evaluate_evidence_governance(manifest, runtime.evidence_policy)
    projected = project_manifest_for_telemetry(manifest, runtime.evidence_policy)
    visible_ids = tuple(item.evidence_id for item in projected.items)
    return {
        "statewake.evidence.manifest_id": manifest.manifest_id,
        "statewake.evidence.governance_policy_id": decision.policy_id,
        "statewake.evidence.visible_ids": ",".join(visible_ids),
        "statewake.evidence.visible_count": str(len(visible_ids)),
        "statewake.evidence.omitted_count": str(len(manifest.items) - len(visible_ids)),
    }


def _set_terminal_status(span: Any, *, success: bool) -> None:
    """Set the terminal OpenTelemetry status for the completed operation."""
    try:
        from opentelemetry.trace import Status, StatusCode
    except ImportError:
        # Keep the adapter testable with a minimal tracer double when imports are unavailable.
        span.set_status("OK" if success else "ERROR")
        return
    span.set_status(Status(StatusCode.OK if success else StatusCode.ERROR))
