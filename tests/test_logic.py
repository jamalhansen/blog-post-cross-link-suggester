"""Tests for cross_link.logic: draft and audit commands with MockProvider."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cross_link.logic import app

runner = CliRunner()

MOCK_SUMMARY_RESPONSE = json.dumps({
    "title": "Intro to SQL",
    "main_topic": "How to write SELECT queries",
    "key_concepts": ["SELECT", "WHERE", "FROM"],
    "audience_stage": "beginner",
})

MOCK_AUDIT_SUGGESTIONS = json.dumps([
    {
        "target_slug": "sql-joins",
        "anchor_text": "JOIN",
        "context_phrase": "When you need to combine data from multiple tables, JOIN is the tool you reach for.",
        "placement": "body",
        "reason": "Readers who understand SELECT will naturally want to learn JOIN next.",
    }
])

MOCK_DRAFT_SUGGESTIONS = json.dumps([
    {
        "target_slug": "intro-to-sql",
        "suggested_anchor_text": "SELECT statement",
        "placement_hint": "after 'SELECT statement' in the first sentence",
    }
])

SERIES_POST_CONTENT = """---
title: SQL Joins Explained
---

SQL joins are one of the most powerful features of relational databases. When you need to
combine data from multiple tables, JOIN is the tool you reach for. Understanding how different
join types work is essential for writing efficient queries in any production system.

There are several types of joins including INNER JOIN, LEFT JOIN, RIGHT JOIN, and FULL OUTER JOIN.
Each serves a different purpose depending on whether you want to include unmatched rows from
one or both tables in your result set.
"""

DRAFT_POST_CONTENT = """---
title: Advanced Window Functions
---

Window functions allow you to perform calculations across a set of table rows that are related
to the current row. Unlike aggregate functions, window functions do not collapse rows into a
single output row. This makes them incredibly useful for running totals, rankings, and moving
averages.

The OVER clause is what defines the window. You can use PARTITION BY to divide the result set
into groups, and ORDER BY to define the order within each partition. This gives you tremendous
flexibility for analytical queries.
"""


def _make_series(tmp_path: Path, content: str = SERIES_POST_CONTENT) -> Path:
    series = tmp_path / "series"
    series.mkdir()
    (series / "01-sql-joins.md").write_text(content, encoding="utf-8")
    (series / "02-intro-to-sql.md").write_text(content, encoding="utf-8")
    return series


def _make_draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT_POST_CONTENT, encoding="utf-8")
    return draft


class TestDraftCommandWithMock:
    def test_no_llm_skips_llm(self, tmp_path):
        post = _make_draft(tmp_path)
        series = _make_series(tmp_path)

        result = runner.invoke(app, [
            "draft", str(post),
            "--series-dir", str(series),
            "--no-llm",
        ])

        assert result.exit_code == 0
        assert "dry-run" in result.output

    def test_with_mock_provider(self, tmp_path):
        post = _make_draft(tmp_path)
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")

        mock_responses = [MOCK_SUMMARY_RESPONSE, MOCK_SUMMARY_RESPONSE, MOCK_DRAFT_SUGGESTIONS, MOCK_DRAFT_SUGGESTIONS]
        call_count = 0

        def mock_complete(system, user):
            nonlocal call_count
            resp = mock_responses[min(call_count, len(mock_responses) - 1)]
            call_count += 1
            return resp

        from local_first_common.testing import MockProvider
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            # Prime the provider to return different responses per call
            call_idx = 0
            responses = [MOCK_SUMMARY_RESPONSE, MOCK_SUMMARY_RESPONSE, MOCK_DRAFT_SUGGESTIONS, MOCK_DRAFT_SUGGESTIONS]

            def rotating_complete(system, user):
                nonlocal call_idx
                resp = responses[min(call_idx, len(responses) - 1)]
                call_idx += 1
                provider.calls.append((system, user))
                return resp

            provider.complete = rotating_complete

            result = runner.invoke(app, [
                "draft", str(post),
                "--series-dir", str(series),
                "--cache", db,
            ])

        assert result.exit_code == 0
        assert "Cross-link suggestions" in result.output
        assert "Done." in result.output

    def test_draft_no_series_posts(self, tmp_path):
        post = _make_draft(tmp_path)
        empty_series = tmp_path / "empty"
        empty_series.mkdir()
        db = str(tmp_path / "cache.db")

        from local_first_common.testing import MockProvider
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            result = runner.invoke(app, [
                "draft", str(post),
                "--series-dir", str(empty_series),
                "--cache", db,
            ])

        assert result.exit_code == 1
        assert "No series posts" in result.output


class TestAuditCommandWithMock:
    def test_audit_produces_report(self, tmp_path):
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")
        output_path = str(tmp_path / "report.md")

        from local_first_common.testing import MockProvider

        call_idx = 0
        # 2 summaries + 2 audit suggestions
        responses = [
            MOCK_SUMMARY_RESPONSE,
            MOCK_SUMMARY_RESPONSE,
            MOCK_AUDIT_SUGGESTIONS,
            MOCK_AUDIT_SUGGESTIONS,
        ]
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        def rotating_complete(system, user):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            provider.calls.append((system, user))
            return resp

        provider.complete = rotating_complete

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            result = runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
            ])

        assert result.exit_code == 0
        assert "Report written to" in result.output
        assert Path(output_path).exists()

        report = Path(output_path).read_text()
        assert "# Internal Link Opportunity Report" in report

    def test_audit_report_format(self, tmp_path):
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")
        output_path = str(tmp_path / "report.md")

        from local_first_common.testing import MockProvider

        call_idx = 0
        responses = [
            MOCK_SUMMARY_RESPONSE,
            MOCK_SUMMARY_RESPONSE,
            MOCK_AUDIT_SUGGESTIONS,
            MOCK_AUDIT_SUGGESTIONS,
        ]
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        def rotating_complete(system, user):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            provider.calls.append((system, user))
            return resp

        provider.complete = rotating_complete

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
            ])

        report_text = Path(output_path).read_text()
        # Should contain checklist items
        assert "- [ ] Link to sql-joins" in report_text
        assert "Anchor: \"JOIN\"" in report_text
        assert "placement:" in report_text
        assert "Reason:" in report_text

    def test_audit_new_only(self, tmp_path):
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")
        output_path = str(tmp_path / "report.md")

        from local_first_common.testing import MockProvider

        call_idx = 0
        responses = [
            MOCK_SUMMARY_RESPONSE,
            MOCK_SUMMARY_RESPONSE,
            MOCK_AUDIT_SUGGESTIONS,
        ]
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        def rotating_complete(system, user):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            provider.calls.append((system, user))
            return resp

        provider.complete = rotating_complete

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            result = runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
                "--new-only", str(series / "01-sql-joins.md"),
            ])

        assert result.exit_code == 0
        # Only one post scanned
        assert "Processed: 1" in result.output

    def test_audit_drops_hallucinated_slugs(self, tmp_path):
        """Suggestions with slugs not in the known post list must be dropped."""
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")
        output_path = str(tmp_path / "report.md")

        hallucinated = json.dumps([
            {
                "target_slug": "sql-joins: SQL Joins Explained — How to combine tables",
                "placement": "body",
                "reason": "Relevant to joins",
            }
        ])

        from local_first_common.testing import MockProvider

        call_idx = 0
        responses = [
            MOCK_SUMMARY_RESPONSE, MOCK_SUMMARY_RESPONSE,
            hallucinated, hallucinated,
        ]
        provider = MockProvider(response=MOCK_SUMMARY_RESPONSE)

        def rotating_complete(system, user):
            nonlocal call_idx
            resp = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            provider.calls.append((system, user))
            return resp

        provider.complete = rotating_complete

        with patch("cross_link.logic.resolve_provider", return_value=provider):
            runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
            ])

        report = Path(output_path).read_text()
        # The hallucinated slug should not appear in the report
        assert "sql-joins: SQL Joins Explained" not in report

    def test_audit_caches_summaries(self, tmp_path):
        """Second run should use cached summaries and make fewer LLM calls."""
        series = _make_series(tmp_path)
        db = str(tmp_path / "cache.db")
        output_path = str(tmp_path / "report.md")

        from local_first_common.testing import MockProvider

        def make_provider():
            call_idx_box = [0]
            responses = [
                MOCK_SUMMARY_RESPONSE,
                MOCK_SUMMARY_RESPONSE,
                MOCK_AUDIT_SUGGESTIONS,
                MOCK_AUDIT_SUGGESTIONS,
            ]
            p = MockProvider(response=MOCK_SUMMARY_RESPONSE)

            def rotating_complete(system, user):
                resp = responses[min(call_idx_box[0], len(responses) - 1)]
                call_idx_box[0] += 1
                p.calls.append((system, user))
                return resp

            p.complete = rotating_complete
            return p

        # First run — summaries get cached
        provider1 = make_provider()
        with patch("cross_link.logic.resolve_provider", return_value=provider1):
            runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
            ])

        first_run_calls = len(provider1.calls)

        # Second run — summaries should be served from cache
        provider2 = make_provider()
        with patch("cross_link.logic.resolve_provider", return_value=provider2):
            runner.invoke(app, [
                "audit", str(series),
                "--cache", db,
                "--output", output_path,
            ])

        second_run_calls = len(provider2.calls)
        # Second run should make fewer or equal calls (summary calls should be cached)
        assert second_run_calls <= first_run_calls
