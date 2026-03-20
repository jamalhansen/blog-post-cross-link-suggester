"""SQLite cache for post summaries used by audit mode."""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def init_cache(db_path: str) -> None:
    """Create the post_summaries table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_summaries (
            slug TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            title TEXT NOT NULL,
            main_topic TEXT NOT NULL,
            key_concepts TEXT NOT NULL,
            audience_stage TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_cached_summary(db_path: str, slug: str, file_path: Path) -> dict | None:
    """Return cached summary dict if file hasn't changed since last cache, else None."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM post_summaries WHERE slug = ?", (slug,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    if row["file_hash"] != _file_hash(file_path):
        return None
    return {
        "title": row["title"],
        "main_topic": row["main_topic"],
        "key_concepts": json.loads(row["key_concepts"]),
        "audience_stage": row["audience_stage"],
    }


def save_summary(db_path: str, slug: str, file_path: Path, summary: dict) -> None:
    """Upsert a post summary into the cache."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO post_summaries
           (slug, file_path, file_hash, title, main_topic, key_concepts, audience_stage, cached_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            slug,
            str(file_path),
            _file_hash(file_path),
            summary["title"],
            summary["main_topic"],
            json.dumps(summary["key_concepts"]),
            summary["audience_stage"],
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def list_cached_slugs(db_path: str) -> list[str]:
    """Return all cached slugs."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT slug FROM post_summaries").fetchall()
    conn.close()
    return [r[0] for r in rows]
