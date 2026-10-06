"""Persist and strictly reload effective privacy/evidence-governance policy evidence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from statewake.domain.governance import (
    EvidenceGovernancePolicy,
    PrivacyGovernanceRuntimeConfig,
)
from statewake.domain.privacy import PrivacyPolicy, RedactionRule

PRIVACY_GOVERNANCE_RUNTIME_SCHEMA_VERSION = "privacy-governance-runtime.v1"
_EXPECTED_ENFORCEMENT = {
    "metadata_redaction_before_receipt_identity": True,
    "storage_governance_before_artifact_write": True,
    "workspace_sensitivity_indexing": True,
    "telemetry_manifest_projection_supported": True,
    "opaque_content_secret_scanning": False,
}


def _canonical(payload: object) -> bytes:
    """Return deterministic canonical JSON bytes."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_exact_keys(value: Any, *, expected: set[str], name: str) -> dict[str, Any]:
    """Return one exact-shape JSON object."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _string(value: Any, name: str) -> str:
    """Return one strict JSON string."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _text(value: Any, name: str) -> str:
    """Return one non-empty JSON string."""
    text = _string(value, name)
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


def _bool(value: Any, name: str) -> bool:
    """Return one strict JSON boolean."""
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _string_array(value: Any, name: str) -> tuple[str, ...]:
    """Return one exact JSON array of non-empty strings."""
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array of strings")
    output: list[str] = []
    for item in value:
        output.append(_text(item, f"{name} item"))
    return tuple(output)


def _digest(value: Any, name: str) -> str:
    """Return one lowercase SHA-256 hexadecimal digest."""
    digest = _text(value, name)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def runtime_config_payload(config: PrivacyGovernanceRuntimeConfig) -> dict[str, Any]:
    """Return the exact runtime policy contract without request or artifact content."""
    privacy = config.privacy_policy
    evidence = config.evidence_policy
    return {
        "schema_version": PRIVACY_GOVERNANCE_RUNTIME_SCHEMA_VERSION,
        "privacy_policy": {
            "policy_id": privacy.policy_id,
            "redact_keys": list(privacy.redact_keys),
            "replacement": privacy.replacement,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "pattern": rule.pattern,
                    "replacement": rule.replacement,
                }
                for rule in privacy.rules
            ],
        },
        "evidence_governance_policy": {
            "policy_id": evidence.policy_id,
            "storage_max_sensitivity": evidence.storage_max_sensitivity,
            "telemetry_max_sensitivity": evidence.telemetry_max_sensitivity,
            "require_digest_for": list(evidence.require_digest_for),
        },
        "enforcement": dict(_EXPECTED_ENFORCEMENT),
    }


def runtime_config_digest(config: PrivacyGovernanceRuntimeConfig) -> str:
    """Return the deterministic digest of the exact effective runtime policy."""
    return hashlib.sha256(_canonical(runtime_config_payload(config))).hexdigest()


def write_privacy_governance_runtime_snapshot(
    path: Path,
    config: PrivacyGovernanceRuntimeConfig,
) -> None:
    """Atomically persist effective runtime policy evidence with restrictive permissions."""
    target = path.expanduser()
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
        raise ValueError("privacy governance snapshot path cannot traverse a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    payload = runtime_config_payload(config)
    payload["digest"] = runtime_config_digest(config)
    raw = _canonical(payload) + b"\n"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        fd = os.open(temp, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                offset += os.write(fd, raw[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def load_privacy_governance_runtime_snapshot(
    path: Path,
    *,
    max_bytes: int,
) -> PrivacyGovernanceRuntimeConfig:
    """Load, strictly validate, and digest-verify one bounded runtime snapshot."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    target = path.expanduser()
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
        raise ValueError("privacy governance snapshot path cannot traverse a symlink")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(target, flags)
    try:
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    if len(raw) > max_bytes:
        raise OverflowError("privacy governance runtime snapshot exceeds read limit")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "privacy governance runtime snapshot is invalid UTF-8 JSON"
        ) from exc

    root = _require_exact_keys(
        payload,
        expected={
            "schema_version",
            "privacy_policy",
            "evidence_governance_policy",
            "enforcement",
            "digest",
        },
        name="privacy governance runtime snapshot",
    )
    if root["schema_version"] != PRIVACY_GOVERNANCE_RUNTIME_SCHEMA_VERSION:
        raise ValueError("unsupported privacy governance runtime schema version")

    privacy = _require_exact_keys(
        root["privacy_policy"],
        expected={"policy_id", "redact_keys", "replacement", "rules"},
        name="privacy_policy",
    )
    evidence = _require_exact_keys(
        root["evidence_governance_policy"],
        expected={
            "policy_id",
            "storage_max_sensitivity",
            "telemetry_max_sensitivity",
            "require_digest_for",
        },
        name="evidence_governance_policy",
    )
    enforcement = _require_exact_keys(
        root["enforcement"],
        expected=set(_EXPECTED_ENFORCEMENT),
        name="enforcement",
    )
    parsed_enforcement = {
        name: _bool(enforcement[name], name) for name in _EXPECTED_ENFORCEMENT
    }
    if parsed_enforcement != _EXPECTED_ENFORCEMENT:
        raise ValueError("privacy governance enforcement claims are unsupported")

    parsed_rules: list[RedactionRule] = []
    rules = privacy["rules"]
    if not isinstance(rules, list):
        raise ValueError("rules must be an array")
    for raw_rule in rules:
        rule = _require_exact_keys(
            raw_rule,
            expected={"rule_id", "pattern", "replacement"},
            name="privacy rule",
        )
        parsed_rules.append(
            RedactionRule(
                rule_id=_text(rule["rule_id"], "privacy rule rule_id"),
                pattern=_text(rule["pattern"], "privacy rule pattern"),
                replacement=_string(rule["replacement"], "privacy rule replacement"),
            )
        )

    config = PrivacyGovernanceRuntimeConfig(
        privacy_policy=PrivacyPolicy(
            policy_id=_text(privacy["policy_id"], "privacy_policy.policy_id"),
            redact_keys=_string_array(privacy["redact_keys"], "redact_keys"),
            rules=tuple(parsed_rules),
            replacement=_text(privacy["replacement"], "privacy_policy.replacement"),
        ),
        evidence_policy=EvidenceGovernancePolicy(
            policy_id=_text(
                evidence["policy_id"], "evidence_governance_policy.policy_id"
            ),
            storage_max_sensitivity=_text(
                evidence["storage_max_sensitivity"],
                "evidence_governance_policy.storage_max_sensitivity",
            ),
            telemetry_max_sensitivity=_text(
                evidence["telemetry_max_sensitivity"],
                "evidence_governance_policy.telemetry_max_sensitivity",
            ),
            require_digest_for=_string_array(
                evidence["require_digest_for"], "require_digest_for"
            ),
        ),
    )
    supplied_digest = _digest(root["digest"], "digest")
    if supplied_digest != runtime_config_digest(config):
        raise ValueError("privacy governance runtime snapshot digest mismatch")
    return config


__all__ = [
    "PRIVACY_GOVERNANCE_RUNTIME_SCHEMA_VERSION",
    "PrivacyGovernanceRuntimeConfig",
    "load_privacy_governance_runtime_snapshot",
    "runtime_config_digest",
    "runtime_config_payload",
    "write_privacy_governance_runtime_snapshot",
]
