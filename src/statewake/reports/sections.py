"""Section-building helpers for deterministic Markdown reports."""

from __future__ import annotations


def bullet_lines(label: str, values: tuple[str, ...]) -> list[str]:
    """Render a named bullet section, preserving explicit empty state."""
    if not values:
        return [f"- {label}: none"]
    return [f"- {label}: `{value}`" for value in values]


__all__ = ["bullet_lines"]
