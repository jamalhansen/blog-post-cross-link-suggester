"""Tests for apply command in cross_link.logic."""

from typer.testing import CliRunner
from cross_link.logic import app

runner = CliRunner()

POST_CONTENT = """---
title: My Post
---
# My Post

This is the first paragraph.

This is the second paragraph. Relational databases are cool.

This is the third paragraph.
"""

REPORT_CONTENT = """# Internal Link Opportunity Report
Generated: 2026-03-28

## my-post
- [x] Link to target-post — placement: intro
      Anchor: "first paragraph"
      Context: "This is the first paragraph."
      Suggested: [first paragraph](/blog/target-post/)
      Reason: Relevant link.
- [ ] Link to other-post — placement: body
      Anchor: "databases"
      Context: "Relational databases are cool."
      Suggested: [databases](/blog/other-post/)
      Reason: Database link.
- [x] Link to last-post — placement: closing
      Anchor: "third paragraph"
      Context: "This is the third paragraph."
      Suggested: [third paragraph](/blog/last-post/)
      Reason: Final link.
"""

def test_apply_checked_links(tmp_path):
    series = tmp_path / "series"
    series.mkdir()
    post_file = series / "my-post.md"
    post_file.write_text(POST_CONTENT, encoding="utf-8")
    
    # We need the target files to exist for the slug mapping
    (series / "target-post.md").write_text("# Target", encoding="utf-8")
    (series / "last-post.md").write_text("# Last", encoding="utf-8")
    
    report = tmp_path / "report.md"
    report.write_text(REPORT_CONTENT, encoding="utf-8")
    
    result = runner.invoke(app, [
        "apply", str(report),
        "--series-dir", str(series),
    ])
    
    assert result.exit_code == 0
    assert "Modified 1 files" in result.output
    
    # Check the file content
    updated = post_file.read_text(encoding="utf-8")
    assert "[first paragraph](/blog/target-post/)" in updated
    assert "[third paragraph](/blog/last-post/)" in updated
    assert "other-post" not in updated  # unchecked

def test_apply_dry_run(tmp_path):
    series = tmp_path / "series"
    series.mkdir()
    post_file = series / "my-post.md"
    post_file.write_text(POST_CONTENT, encoding="utf-8")
    (series / "target-post.md").write_text("# Target", encoding="utf-8")
    
    report = tmp_path / "report.md"
    report.write_text(REPORT_CONTENT, encoding="utf-8")
    
    result = runner.invoke(app, [
        "apply", str(report),
        "--series-dir", str(series),
        "--dry-run",
    ])
    
    assert result.exit_code == 0
    assert "[dry-run] Would add" in result.output
    
    # File should remain unchanged
    updated = post_file.read_text(encoding="utf-8")
    assert updated == POST_CONTENT

def test_apply_markdown_links(tmp_path):
    series = tmp_path / "series"
    series.mkdir()
    post_file = series / "my-post.md"
    post_file.write_text(POST_CONTENT, encoding="utf-8")
    (series / "target-post.md").write_text("# Target", encoding="utf-8")
    
    markdown_report = """# Internal Link Opportunity Report
## my-post
- [x] Link to target-post — placement: intro
      Anchor: "first paragraph"
      Context: "This is the first paragraph."
      Suggested: [first paragraph](/blog/target-post/)
"""
    report = tmp_path / "report_md.md"
    report.write_text(markdown_report, encoding="utf-8")
    
    result = runner.invoke(app, [
        "apply", str(report),
        "--series-dir", str(series),
    ])
    
    assert result.exit_code == 0
    updated = post_file.read_text(encoding="utf-8")
    assert "[first paragraph](/blog/target-post/)" in updated

def test_apply_preserves_frontmatter(tmp_path):
    series = tmp_path / "series"
    series.mkdir()
    post_file = series / "my-post.md"
    
    # Intentionally weird formatting to ensure it's preserved
    original_content = """---
title: "My Post"
tags: ["sql", "duckdb", "python"]
# This is a comment
categories: []
---
This is the body text. Replace me."""
    post_file.write_text(original_content, encoding="utf-8")
    (series / "target-post.md").write_text("# Target", encoding="utf-8")
    
    report_content = """# Internal Link Opportunity Report
## my-post
- [x] Link to target-post — placement: body
      Anchor: "Replace me"
      Context: "This is the body text. Replace me."
      Suggested: [Replace me](/blog/target-post/)
"""
    report = tmp_path / "report.md"
    report.write_text(report_content, encoding="utf-8")
    
    result = runner.invoke(app, [
        "apply", str(report),
        "--series-dir", str(series),
    ])
    
    assert result.exit_code == 0
    updated = post_file.read_text(encoding="utf-8")
    
    # Check that frontmatter is EXACTLY the same
    assert 'title: "My Post"' in updated
    assert 'tags: ["sql", "duckdb", "python"]' in updated
    assert '# This is a comment' in updated
    assert 'categories: []' in updated
    
    # Check that body was updated
    assert '[Replace me](/blog/target-post/)' in updated
