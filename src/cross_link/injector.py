"""Markdown link injection domain logic."""

from pathlib import Path

from local_first_common.obsidian import split_frontmatter
from local_first_common.text import split_markdown_protected


def apply_links_to_file(file_path: Path, link_details: list[dict]) -> bool:
    """Insert links into a markdown file based on anchor text.
    link_details is a list of dicts with 'anchor', 'context', and 'replacement'.
    Only replaces text outside of code blocks.
    """
    raw = file_path.read_text(encoding="utf-8")

    parts = split_frontmatter(raw)
    if parts is None:
        header, body = "", raw
    else:
        fm_yaml, body = parts
        header = f"---\n{fm_yaml}---\n"

    # Split body into chunks: [text, protected, text, protected, ...]
    # Protected elements: fenced code, inline code, markdown links, wiki links
    body_chunks = split_markdown_protected(body)

    modified = False
    for detail in link_details:
        anchor = detail["anchor"]
        replacement = detail["replacement"]

        # Only search and replace in the text chunks (indices 0, 2, 4...)
        for i in range(0, len(body_chunks), 2):
            text_chunk = body_chunks[i]

            if anchor in text_chunk:
                new_chunk = text_chunk.replace(anchor, replacement, 1)
                if new_chunk != text_chunk:
                    body_chunks[i] = new_chunk
                    modified = True
                    break  # Link applied for this detail

    if modified:
        new_body = "".join(body_chunks)
        file_path.write_text(f"{header}{new_body}", encoding="utf-8")

    return modified


_apply_links_to_file = apply_links_to_file
