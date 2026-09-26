"""Section-building helpers for deterministic Markdown reports."""

from __future__ import annotations


def safe_report_text(value: str) -> str:
    """Render caller-supplied text as one Markdown-safe inline value.

    Untrusted newlines must not create headings or unrelated report bullets.
    Backticks and Markdown metacharacters must not escape field boundaries.
    """
    single_line = " ".join(value.splitlines())
    single_line = "".join(
        " " if ord(char) < 32 or ord(char) == 127 else char for char in single_line
    )
    escaped = single_line.replace("\\", "\\\\")
    escaped = escaped.replace("`", "&#96;")
    for marker in ("*", "[", "]", "<", ">", "|", "#"):
        escaped = escaped.replace(marker, "\\" + marker)
    return escaped


def bullet_lines(label: str, values: tuple[str, ...]) -> list[str]:
    """Render a named bullet section, preserving explicit empty state."""
    if not values:
        return [f"- {label}: none"]
    return [f"- {label}: `{safe_report_text(value)}`" for value in values]


__all__ = ["bullet_lines", "safe_report_text"]
