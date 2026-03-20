"""Tests for cross_link.cache: SQLite-backed post summary caching."""

from pathlib import Path

from cross_link.cache import get_cached_summary, init_cache, list_cached_slugs, save_summary


SAMPLE_SUMMARY = {
    "title": "Intro to SQL",
    "main_topic": "How to write basic SELECT queries",
    "key_concepts": ["SELECT", "WHERE", "FROM"],
    "audience_stage": "beginner",
}


class TestInitCache:
    def test_creates_table(self, tmp_path):
        db = str(tmp_path / "cache.db")
        init_cache(db)
        # Should be callable twice without error (CREATE TABLE IF NOT EXISTS)
        init_cache(db)

    def test_db_file_created(self, tmp_path):
        db = str(tmp_path / "cache.db")
        init_cache(db)
        assert Path(db).exists()


class TestSaveAndGetSummary:
    def test_roundtrip(self, tmp_path):
        db = str(tmp_path / "cache.db")
        post = tmp_path / "post.md"
        post.write_text("some content", encoding="utf-8")
        init_cache(db)

        save_summary(db, "intro-to-sql", post, SAMPLE_SUMMARY)
        result = get_cached_summary(db, "intro-to-sql", post)

        assert result is not None
        assert result["title"] == "Intro to SQL"
        assert result["key_concepts"] == ["SELECT", "WHERE", "FROM"]
        assert result["audience_stage"] == "beginner"

    def test_cache_miss_unknown_slug(self, tmp_path):
        db = str(tmp_path / "cache.db")
        post = tmp_path / "post.md"
        post.write_text("content", encoding="utf-8")
        init_cache(db)

        result = get_cached_summary(db, "nonexistent", post)
        assert result is None

    def test_cache_invalidated_on_file_change(self, tmp_path):
        db = str(tmp_path / "cache.db")
        post = tmp_path / "post.md"
        post.write_text("original content", encoding="utf-8")
        init_cache(db)

        save_summary(db, "my-post", post, SAMPLE_SUMMARY)
        # Modify the file
        post.write_text("changed content", encoding="utf-8")

        result = get_cached_summary(db, "my-post", post)
        assert result is None

    def test_upsert_overwrites(self, tmp_path):
        db = str(tmp_path / "cache.db")
        post = tmp_path / "post.md"
        post.write_text("content", encoding="utf-8")
        init_cache(db)

        save_summary(db, "my-post", post, SAMPLE_SUMMARY)
        updated = {**SAMPLE_SUMMARY, "title": "Updated Title"}
        save_summary(db, "my-post", post, updated)

        result = get_cached_summary(db, "my-post", post)
        assert result["title"] == "Updated Title"


class TestListCachedSlugs:
    def test_empty_cache(self, tmp_path):
        db = str(tmp_path / "cache.db")
        init_cache(db)
        assert list_cached_slugs(db) == []

    def test_returns_slugs(self, tmp_path):
        db = str(tmp_path / "cache.db")
        init_cache(db)

        for slug, filename in [("post-one", "post1.md"), ("post-two", "post2.md")]:
            post = tmp_path / filename
            post.write_text("content", encoding="utf-8")
            save_summary(db, slug, post, SAMPLE_SUMMARY)

        slugs = list_cached_slugs(db)
        assert set(slugs) == {"post-one", "post-two"}
