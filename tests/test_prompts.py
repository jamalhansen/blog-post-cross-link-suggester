"""Tests for cross_link.prompts: prompt builder functions."""

from cross_link.prompts import (
    build_audit_prompt,
    build_draft_prompt,
    build_summary_prompt,
)

SAMPLE_SUMMARIES = [
    {
        "slug": "intro-to-sql",
        "title": "Intro to SQL",
        "main_topic": "How to write SELECT queries",
        "key_concepts": ["SELECT", "WHERE", "FROM"],
        "audience_stage": "beginner",
    },
    {
        "slug": "sql-joins",
        "title": "SQL Joins Explained",
        "main_topic": "How to combine tables with JOIN",
        "key_concepts": ["JOIN", "INNER JOIN", "LEFT JOIN"],
        "audience_stage": "intermediate",
    },
]


class TestBuildSummaryPrompt:
    def test_returns_content(self):
        content = "This is a blog post about SQL."
        result = build_summary_prompt(content)
        assert "SQL" in result

    def test_caps_at_4000_chars(self):
        long_content = "x" * 5000
        result = build_summary_prompt(long_content)
        assert len(result) == 4000


class TestBuildAuditPrompt:
    def test_includes_target_info(self):
        prompt = build_audit_prompt("window-functions", "Window Functions", "Some content...", SAMPLE_SUMMARIES)
        assert "window-functions" in prompt
        assert "Window Functions" in prompt

    def test_includes_other_posts(self):
        prompt = build_audit_prompt("window-functions", "Window Functions", "Content", SAMPLE_SUMMARIES)
        assert "intro-to-sql" in prompt
        assert "sql-joins" in prompt

    def test_slugs_in_brackets(self):
        # Slugs must be in [brackets] so the model copies only the slug value
        prompt = build_audit_prompt("window-functions", "Window Functions", "Content", SAMPLE_SUMMARIES)
        assert "[intro-to-sql]" in prompt
        assert "[sql-joins]" in prompt

    def test_excludes_target_post_itself(self):
        summaries = SAMPLE_SUMMARIES + [{
            "slug": "window-functions",
            "title": "Window Functions",
            "main_topic": "ROW_NUMBER and RANK",
            "key_concepts": ["ROW_NUMBER", "RANK"],
            "audience_stage": "advanced",
        }]
        prompt = build_audit_prompt("window-functions", "Window Functions", "Content", summaries)
        # Should only appear once (in the target section), not in the other posts list
        assert prompt.count("window-functions") == 1

    def test_truncates_content(self):
        long_content = "word " * 1000
        prompt = build_audit_prompt("slug", "Title", long_content, SAMPLE_SUMMARIES)
        # The 800-char cap on content means the full 5000-char content won't appear
        assert len(prompt) < len(long_content)


class TestBuildDraftPrompt:
    def test_includes_paragraph(self):
        paragraph = "When you use SELECT, you choose which columns to return."
        prompt = build_draft_prompt(paragraph, SAMPLE_SUMMARIES)
        assert paragraph in prompt

    def test_includes_all_posts(self):
        paragraph = "SQL paragraph text here."
        prompt = build_draft_prompt(paragraph, SAMPLE_SUMMARIES)
        assert "intro-to-sql" in prompt
        assert "sql-joins" in prompt

    def test_slugs_in_brackets(self):
        paragraph = "SQL paragraph text here."
        prompt = build_draft_prompt(paragraph, SAMPLE_SUMMARIES)
        assert "[intro-to-sql]" in prompt
        assert "[sql-joins]" in prompt

    def test_includes_concepts(self):
        paragraph = "Some paragraph."
        prompt = build_draft_prompt(paragraph, SAMPLE_SUMMARIES)
        assert "SELECT" in prompt
