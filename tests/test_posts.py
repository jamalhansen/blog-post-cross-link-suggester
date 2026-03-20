"""Tests for cross_link.posts: slug_from_path, read_post, chunk_paragraphs."""

from pathlib import Path

from cross_link.posts import chunk_paragraphs, read_post, slug_from_path


class TestSlugFromPath:
    def test_strips_numeric_prefix(self):
        assert slug_from_path(Path("07-select-choosing-your-columns.md")) == "select-choosing-your-columns"

    def test_no_numeric_prefix(self):
        assert slug_from_path(Path("my-blog-post.md")) == "my-blog-post"

    def test_two_digit_prefix(self):
        assert slug_from_path(Path("12-advanced-topic.md")) == "advanced-topic"

    def test_full_path(self, tmp_path):
        p = tmp_path / "03-intro-to-sql.md"
        assert slug_from_path(p) == "intro-to-sql"

    def test_no_extension_in_slug(self):
        result = slug_from_path(Path("01-my-post.md"))
        assert ".md" not in result


class TestReadPost:
    def test_reads_frontmatter_title(self, tmp_path):
        post = tmp_path / "post.md"
        post.write_text("---\ntitle: My Great Post\n---\n\nBody text here.", encoding="utf-8")
        title, body = read_post(post)
        assert title == "My Great Post"
        assert "Body text here." in body

    def test_falls_back_to_h1(self, tmp_path):
        post = tmp_path / "post.md"
        post.write_text("# H1 Title\n\nSome body text.", encoding="utf-8")
        title, body = read_post(post)
        assert title == "H1 Title"

    def test_falls_back_to_slug(self, tmp_path):
        post = tmp_path / "my-post.md"
        post.write_text("Just some content with no title.", encoding="utf-8")
        title, body = read_post(post)
        assert title == "my-post"

    def test_body_excludes_frontmatter(self, tmp_path):
        post = tmp_path / "post.md"
        post.write_text("---\ntitle: Title\nauthor: Jane\n---\n\nActual body.", encoding="utf-8")
        _, body = read_post(post)
        assert "author" not in body
        assert "Actual body." in body


class TestChunkParagraphs:
    def test_splits_on_double_newline(self):
        text = "First paragraph with several words.\n\nSecond paragraph with several words."
        chunks = chunk_paragraphs(text, min_words=3)
        assert len(chunks) == 2

    def test_skips_headings(self):
        text = "## Section Heading\n\nThis paragraph should be included."
        chunks = chunk_paragraphs(text, min_words=3)
        assert len(chunks) == 1
        assert "Section Heading" not in chunks[0]

    def test_skips_short_paragraphs(self):
        text = "Too short.\n\nThis paragraph is long enough for the min_words threshold."
        chunks = chunk_paragraphs(text, min_words=8)
        assert len(chunks) == 1
        assert "Too short" not in chunks[0]

    def test_custom_min_words(self):
        text = "Five words here today.\n\nAnother short paragraph too."
        chunks = chunk_paragraphs(text, min_words=3)
        assert len(chunks) == 2

    def test_empty_text(self):
        assert chunk_paragraphs("") == []

    def test_strips_blank_paragraphs(self):
        text = "First long enough paragraph.\n\n\n\nSecond long enough paragraph here."
        chunks = chunk_paragraphs(text, min_words=3)
        assert len(chunks) == 2
