"""Regression tests for timezone-safe datetime parsing."""

import unittest

from statewake.utils.time import parse_datetime


class ParseDatetimeTests(unittest.TestCase):
    """Verify timezone-aware ISO-8601 datetime parsing."""

    def test_requires_explicit_timezone(self) -> None:
        """Reject ISO timestamps that do not contain timezone information."""
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            parse_datetime("2026-09-11T10:00:00", field="captured_at")

    def test_normalizes_explicit_offset_to_utc(self) -> None:
        """Normalize an explicitly offset-aware timestamp to UTC."""
        parsed = parse_datetime("2026-09-11T15:30:00+05:30", field="captured_at")
        self.assertEqual(parsed.isoformat(), "2026-09-11T10:00:00+00:00")

    def test_accepts_utc_designator(self) -> None:
        """Accept an ISO timestamp using the UTC designator."""
        parsed = parse_datetime("2026-09-11T10:00:00Z", field="captured_at")
        self.assertEqual(parsed.isoformat(), "2026-09-11T10:00:00+00:00")
