"""Deterministic privacy redaction primitives for canonical metadata."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .events import EventEnvelope

DEFAULT_REDACT_KEYS = (
    "api_key",
    "authorization",
    "email",
    "password",
    "phone",
    "secret",
    "ssn",
    "token",
)


@dataclass(frozen=True, slots=True)
class RedactionRule:
    """One deterministic regular-expression redaction rule."""

    rule_id: str
    pattern: str
    replacement: str = "[REDACTED]"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.rule_id.strip():
            raise ValueError("rule_id must not be empty.")
        if not self.pattern:
            raise ValueError("pattern must not be empty.")
        re.compile(self.pattern)

    def apply(self, value: str) -> tuple[str, bool]:
        """Apply this operation to the supplied state."""
        redacted, count = re.subn(self.pattern, self.replacement, value)
        return redacted, count > 0


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    """Explicit deterministic redaction policy for event/evidence metadata."""

    policy_id: str
    redact_keys: tuple[str, ...] = DEFAULT_REDACT_KEYS
    rules: tuple[RedactionRule, ...] = ()
    replacement: str = "[REDACTED]"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty.")
        if not self.replacement:
            raise ValueError("replacement must not be empty.")
        for key in self.redact_keys:
            if not key.strip():
                raise ValueError("redact_keys must not contain empty values.")


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Redacted value plus deterministic redaction rule identifiers."""

    value: Any
    findings: tuple[str, ...] = ()

    @property
    def redacted(self) -> bool:
        """Whether this value contains redacted findings."""
        return bool(self.findings)


class Redactor:
    """Apply explicit key and regex redaction without inspecting opaque content."""

    def __init__(self, policy: PrivacyPolicy) -> None:
        """Initialize this component with its configured state."""
        self.policy = policy
        self._keys = frozenset(key.casefold() for key in policy.redact_keys)

    def redact_mapping(self, value: Mapping[str, Any]) -> RedactionResult:
        """Return a mapping with configured sensitive keys redacted recursively."""
        redacted, findings = self._redact_mapping(value, path=())
        return RedactionResult(redacted, tuple(findings))

    def redact_metadata(self, metadata: Mapping[str, str]) -> RedactionResult:
        """Return metadata with configured sensitive values redacted."""
        return self.redact_mapping(metadata)

    def redact_event(self, event: EventEnvelope) -> EventEnvelope:
        """Return an event with sensitive fields removed or redacted."""
        result = self.redact_metadata(event.metadata)
        return EventEnvelope(
            run_id=event.run_id,
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            actor=event.actor,
            name=event.name,
            state_id=event.state_id,
            payload_ref=event.payload_ref,
            metadata={str(key): str(value) for key, value in result.value.items()},
        )

    def _redact_mapping(
        self, value: Mapping[str, Any], *, path: tuple[str, ...]
    ) -> tuple[dict[str, Any], list[str]]:
        """Redact sensitive values from a mapping recursively."""
        output: dict[str, Any] = {}
        findings: list[str] = []
        for key in sorted(value):
            key_path = path + (str(key),)
            path_text = ".".join(key_path)
            item = value[key]
            if str(key).casefold() in self._keys:
                output[str(key)] = self.policy.replacement
                findings.append(f"key:{path_text}")
                continue
            redacted_item, item_findings = self._redact_value(item, key_path)
            output[str(key)] = redacted_item
            findings.extend(item_findings)
        return output, findings

    def _redact_value(self, value: Any, path: tuple[str, ...]) -> tuple[Any, list[str]]:
        """Redact a single value according to the configured privacy policy."""
        if isinstance(value, Mapping):
            return self._redact_mapping(value, path=path)  # type: ignore
        if isinstance(value, list):
            output = []
            list_findings: list[str] = []
            for index, item in enumerate(value):  # type: ignore
                redacted_item, item_findings = self._redact_value(
                    item, path + (str(index),)
                )
                output.append(redacted_item)  # type: ignore
                list_findings.extend(item_findings)
            return output, list_findings  # type: ignore
        if isinstance(value, str):
            redacted = value
            string_findings: list[str] = []
            for rule in self.policy.rules:
                redacted, matched = rule.apply(redacted)
                if matched:
                    string_findings.append(f"rule:{rule.rule_id}:{'.'.join(path)}")
            return redacted, string_findings
        return value, []


def redact_events(
    events: list[EventEnvelope], policy: PrivacyPolicy
) -> tuple[list[EventEnvelope], tuple[str, ...]]:
    """Redact canonical event metadata while preserving event identity and ordering."""
    redactor = Redactor(policy)
    output: list[EventEnvelope] = []
    findings: list[str] = []
    for event in events:
        redacted = redactor.redact_event(event)
        if redacted.metadata != event.metadata:
            findings.append(f"event:{event.sequence}")
        output.append(redacted)
    return output, tuple(findings)
