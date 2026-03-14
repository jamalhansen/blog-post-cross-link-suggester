"""Tests for series-cross-link-suggester CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from local_first_common.testing import MockProvider

from series_cross_link_suggester import app

runner = CliRunner()


class TestDraftCommand:
    def test_dry_run(self, tmp_path):
        """Dry run should report what it would do without calling LLM."""
        post = tmp_path / "my-post.md"
        post.write_text("# My Post\n\nSome content here.")
        series = tmp_path / "series"
        series.mkdir()

        result = runner.invoke(app, [
            "draft", str(post),
            "--series-dir", str(series),
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert "dry-run" in result.output

    def test_missing_post_file(self, tmp_path):
        """Should fail fast if the post file doesn't exist."""
        result = runner.invoke(app, [
            "draft", str(tmp_path / "nonexistent.md"),
            "--series-dir", str(tmp_path),
        ])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_missing_series_dir(self, tmp_path):
        """Should fail fast if series-dir is not provided."""
        post = tmp_path / "my-post.md"
        post.write_text("# My Post")

        result = runner.invoke(app, ["draft", str(post)])

        assert result.exit_code == 1


class TestAuditCommand:
    def test_dry_run(self, tmp_path):
        """Dry run should list posts it would scan."""
        series = tmp_path / "series"
        series.mkdir()
        (series / "post-01.md").write_text("# Post 1")
        (series / "post-02.md").write_text("# Post 2")

        result = runner.invoke(app, [
            "audit", str(series),
            "--dry-run",
        ])

        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "2 posts" in result.output

    def test_missing_series_dir(self, tmp_path):
        """Should fail fast if series directory doesn't exist."""
        result = runner.invoke(app, ["audit", str(tmp_path / "nonexistent")])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_empty_series_dir(self, tmp_path):
        """Should fail gracefully if no markdown files found."""
        empty = tmp_path / "empty"
        empty.mkdir()

        result = runner.invoke(app, ["audit", str(empty)])

        assert result.exit_code == 1
