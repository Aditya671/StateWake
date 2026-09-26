"""Protect Markdown report structure against untrusted report text."""

from statewake.reports.markdown import render_markdown_report
from tests.unit.reports.test_human_verification_reports import _report


def test_markdown_untrusted_text_cannot_create_a_new_section():
    report = _report(
        claim="hello\n## Forged verified approval",
        caveats=("caveat\n## Forged release",),
        source_identities=("`\n## Forged source",),
    )
    rendered = render_markdown_report(report)
    assert "\n## Forged" not in rendered
    assert "Forged verified approval" in rendered
    assert "Forged release" in rendered
    assert "Forged source" in rendered
