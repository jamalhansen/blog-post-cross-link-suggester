"""Post file utilities: slug derivation, reading, chunking, frontmatter."""

import re
from pathlib import Path

import frontmatter


def slug_from_path(path: Path) -> str:
    """Derive a URL slug from a filename (strips numeric prefix and extension).

    If the filename is 'index.md' or '_index.md', the parent directory name
    is used as the slug.

    Examples:
        07-select-choosing-your-columns.md -> select-choosing-your-columns
        my-blog-post/index.md              -> my-blog-post
        my-blog-post.md                    -> my-blog-post
    """
    if path.name.lower() in ("index.md", "_index.md"):
        name = path.parent.name
    else:
        name = path.stem
    return re.sub(r"^\d+-", "", name)


def read_post(path: Path) -> tuple[str, str, dict]:
    """Read a markdown post, returning (title, body_text, metadata).

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

    return title, body, post.metadata


def is_valid_post(path: Path) -> bool:
    """Determine if a file is a candidate for cross-linking.

    Excludes:
    - Hidden files/directories (starting with . but not . or ..)
    - Brainstorms, outlines, and drafts based on filename/title/frontmatter
    - Posts explicitly marked as drafts or unpublished
    """
    # Skip truly hidden files/dirs (starting with . but not . or ..)
    if any(p.startswith(".") and p not in (".", "..") for p in path.parts):
        return False

    # Skip files with specific keywords in filename
    # We allow "index.md" and "_index.md" for Hugo compatibility
    skip_keywords = {"brainstorm", "outline", "planning", "draft"}
    if any(kw in path.name.lower() for kw in skip_keywords):
        return False

    # Skip "index" files ONLY if they are not exactly index.md or _index.md
    if "index" in path.name.lower() and path.name.lower() not in ("index.md", "_index.md"):
        return False

    try:
        title, _, metadata = read_post(path)
    except Exception:
        return False

    # Check title for same keywords
    if any(kw in title.lower() for kw in skip_keywords):
        return False

    # Check frontmatter
    if metadata.get("draft") is True:
        return False
    if metadata.get("status") and str(metadata.get("status")).lower() != "published":
        return False
    if metadata.get("type") == "index":
        return False

    return True


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
