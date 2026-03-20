"""Post file utilities: slug derivation, reading, chunking, frontmatter."""

import re
from pathlib import Path

import frontmatter


def slug_from_path(path: Path) -> str:
    """Derive a URL slug from a filename (strips numeric prefix and extension).

    Examples:
        07-select-choosing-your-columns.md -> select-choosing-your-columns
        my-blog-post.md                    -> my-blog-post
    """
    name = path.stem
    return re.sub(r"^\d+-", "", name)


def read_post(path: Path) -> tuple[str, str]:
    """Read a markdown post, returning (title, body_text).

    Title is taken from frontmatter 'title' field, falling back to the first
    H1 heading in the body, then to the filename slug.
    """
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)

    title = post.metadata.get("title", "")
    body = post.content

    if not title:
        match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
        title = match.group(1).strip() if match else slug_from_path(path)

    return title, body


def chunk_paragraphs(text: str, min_words: int = 20) -> list[str]:
    """Split body text into non-trivial paragraphs.

    Paragraphs shorter than min_words are skipped (headings, short notes).
    """
    paragraphs = re.split(r"\n{2,}", text.strip())
    result = []
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        # Skip headings and very short chunks
        if cleaned.startswith("#"):
            continue
        if len(cleaned.split()) < min_words:
            continue
        result.append(cleaned)
    return result
