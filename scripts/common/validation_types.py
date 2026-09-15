"""Typed machine-readable result contracts shared by validation harnesses."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class ValidationResult(TypedDict):
    """One validation result with a mandatory pass/fail flag."""

    passed: bool
    probe: NotRequired[str]
    attack_id: NotRequired[str]
    category: NotRequired[str]
    description: NotRequired[str]
    error: NotRequired[str]
    error_type: NotRequired[str]
    skipped: NotRequired[bool]
    skip_reason: NotRequired[str]
    property: NotRequired[str]
    cases: NotRequired[int]
    steps: NotRequired[int]


class ValidationReport(TypedDict):
    """Common typed surface for validation campaign reports."""

    passed: bool
    results: list[ValidationResult]
    probe_count: NotRequired[int]
    attack_count: NotRequired[int]
    property_count: NotRequired[int]
    schema_version: NotRequired[str]
    seed: NotRequired[int]
