"""Series Cross-Link Suggester — find internal linking opportunities across blog series posts.

Two modes:
  draft   — surface cross-link candidates for a single post being written
  audit   — batch-scan a full post archive and produce a checklist report
"""

import os
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

import typer

from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
    resolve_provider,
    resolve_dry_run,
)
from local_first_common.llm import parse_json_response
from local_first_common.providers import PROVIDERS
from local_first_common.tracking import register_tool, timed_run

from .cache import get_cached_summary, init_cache, save_summary
from .posts import chunk_paragraphs, is_valid_post, read_post, slug_from_path, slugify, strip_code_blocks
from .prompts import (
    AUDIT_SYSTEM,
    DRAFT_SYSTEM,
    SUMMARY_SYSTEM,
    build_audit_prompt,
    build_draft_prompt,
    build_summary_prompt,
)
from .schema import DraftLinkSuggestion, LinkSuggestion, PostSummary

_TOOL = register_tool("series-cross-link-suggester")

app = typer.Typer(help=__doc__)


def _extract_summary(provider, post_path: Path, slug: str, cache_path: str, verbose: bool) -> dict:
    """Return summary dict for a post, using cache if available."""
    cached = get_cached_summary(cache_path, slug, post_path)
    if cached:
        if verbose:
            typer.echo(f"  [cached] {slug}")
        return {"slug": slug, **cached}

    if verbose:
        typer.echo(f"  [summarizing] {slug} ...")

    title, body, metadata = read_post(post_path)
    
    series = metadata.get("series")
    series_slug = None
    if series:
        series_name = series[0] if isinstance(series, list) else series
        series_slug = slugify(series_name)

    with timed_run("series-cross-link-suggester", provider.model, source_location=slug) as run:
        raw = provider.complete(SUMMARY_SYSTEM, build_summary_prompt(body))
        data = parse_json_response(raw)
        run.item_count = 1
        run.input_tokens = getattr(provider, "input_tokens", None) or None
        run.output_tokens = getattr(provider, "output_tokens", None) or None

    summary = PostSummary(
        title=data.get("title") or title,
        series_slug=series_slug,
        main_topic=data.get("main_topic", ""),
        key_concepts=data.get("key_concepts", []),
        audience_stage=data.get("audience_stage", "intermediate"),
    )
    save_summary(cache_path, slug, post_path, summary.model_dump())
    return {"slug": slug, **summary.model_dump()}


def _format_audit_report(
    opportunities: list[dict], 
    all_summaries: list[dict], 
    link_format: str = "markdown",
    url_prefix: str = "/blog/"
) -> str:
    """Render audit results as a markdown checklist report."""
    today = date.today().isoformat()
    lines = ["# Internal Link Opportunity Report", f"Generated: {today}", ""]

    # Map slug to summary for URL generation and validation
    slug_to_summary = {s["slug"]: s for s in all_summaries}
    known_slugs = set(slug_to_summary)

    for opp in opportunities:
        slug = opp["post_slug"]
        suggestions = opp["suggestions"]
        valid_suggestions = []
        for s in suggestions:
            try:
                ls = LinkSuggestion(**s) if isinstance(s, dict) else s
                if ls.target_slug not in known_slugs:
                    continue  # drop hallucinated or malformed slugs
                valid_suggestions.append(ls)
            except Exception:
                continue

        if not valid_suggestions:
            continue  # omit posts with no valid suggestions entirely

        lines.append(f"## {slug}")
        for ls in valid_suggestions:
            summary = slug_to_summary[ls.target_slug]
            if link_format == "markdown":
                # Ensure prefix ends with /
                prefix = url_prefix if url_prefix.endswith("/") else f"{url_prefix}/"
                if summary.get("series_slug"):
                    url = f"{prefix}{summary['series_slug']}/{ls.target_slug}/"
                else:
                    url = f"{prefix}{ls.target_slug}/"
                link_target = f"[{ls.anchor_text}]({url})"
            else:
                link_target = f"[[{ls.target_slug}]] (on phrase: \"{ls.anchor_text}\")"
            
            lines.append(f"- [ ] Link to {ls.target_slug} — placement: {ls.placement}")
            lines.append(f"      Anchor: \"{ls.anchor_text}\"")
            lines.append(f"      Context: \"{ls.context_phrase}\"")
            lines.append(f"      Suggested: {link_target}")
            lines.append(f"      Reason: {ls.reason}")
        lines.append("")
    return "\n".join(lines)


def _format_draft_suggestions(post_path: Path, paragraph_suggestions: list[tuple[str, list]]) -> str:
    """Render draft mode results as readable terminal output."""
    lines = [f"Cross-link suggestions for: {post_path.name}", ""]
    any_found = False
    for i, (para, suggestions) in enumerate(paragraph_suggestions, 1):
        preview = para[:80].replace("\n", " ")
        if len(para) > 80:
            preview += "..."
        if not suggestions:
            continue
        any_found = True
        lines.append(f"Paragraph {i}: {preview}")
        for s in suggestions:
            try:
                ds = DraftLinkSuggestion(**s) if isinstance(s, dict) else s
                lines.append(
                    f"  → [[{ds.target_slug}]] — anchor: \"{ds.suggested_anchor_text}\""
                    f" ({ds.placement_hint})"
                )
            except Exception:
                continue
        lines.append("")
    if not any_found:
        lines.append("No cross-link opportunities found.")
    return "\n".join(lines)


@app.command()
def draft(
    post: Annotated[
        str,
        typer.Argument(help="Path to the draft post file to analyse"),
    ],
    series_dir: Annotated[
        str,
        typer.Option("--series-dir", "-s", help="Directory containing published series posts"),
    ] = os.environ.get("SERIES_DIR", ""),
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help=f"LLM provider. Choices: {', '.join(PROVIDERS.keys())}"),
    ] = os.environ.get("MODEL_PROVIDER", "ollama"),
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Override the provider's default model."),
    ] = None,
    cache: Annotated[
        str,
        typer.Option("--cache", "-c", help="Path to SQLite cache file for series summaries"),
    ] = ".cross-link-cache.db",
    dry_run: bool = dry_run_option(),
    no_llm: bool = no_llm_option(),
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show extra debug output."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Show raw prompts and LLM responses."),
    ] = False,
):
    """Surface cross-link candidates from existing series content for a draft post."""

    dry_run = resolve_dry_run(dry_run, no_llm)

    post_path = Path(post)
    if not post_path.exists():
        typer.echo(f"Error: Post file not found: {post_path}", err=True)
        raise typer.Exit(1)

    if not series_dir:
        typer.echo("Error: --series-dir is required (or set SERIES_DIR env var)", err=True)
        raise typer.Exit(1)

    series_path = Path(series_dir)
    if not series_path.is_dir():
        typer.echo(f"Error: Series directory not found: {series_path}", err=True)
        raise typer.Exit(1)

    series_posts = sorted(p for p in series_path.glob("**/*.md") if p != post_path and is_valid_post(p))

    llm = resolve_provider(PROVIDERS, provider, model, no_llm=no_llm, debug=debug)

    if dry_run:
        typer.echo(f"[dry-run] Would analyse {post_path.name} against {len(series_posts)} posts in {series_path}")
        raise typer.Exit(0)

    # Build summaries for all series posts
    init_cache(cache)
    all_summaries = []
    for p in series_posts:
        slug = slug_from_path(p)
        summary = _extract_summary(llm, p, slug, cache, verbose)
        all_summaries.append(summary)

    if not all_summaries:
        typer.echo("No series posts found to compare against.")
        raise typer.Exit(1)

    # Chunk the draft and get suggestions per paragraph
    _, body, _ = read_post(post_path)
    paragraphs = chunk_paragraphs(body)
    if verbose:
        typer.echo(f"\nAnalysing {len(paragraphs)} paragraphs in {post_path.name} ...")

    paragraph_suggestions: list[tuple[str, list]] = []
    for para in paragraphs:
        with timed_run("series-cross-link-suggester", llm.model, source_location=str(post_path)) as run:
            prompt = build_draft_prompt(para, all_summaries)
            if debug:
                typer.echo(f"\n[debug] Draft prompt:\n{prompt}\n")
            raw = llm.complete(DRAFT_SYSTEM, prompt)
            if debug:
                typer.echo(f"[debug] Response: {raw}")
            suggestions = parse_json_response(raw)
            if not isinstance(suggestions, list):
                suggestions = []
            
            run.item_count = 1
            run.input_tokens = getattr(llm, "input_tokens", None) or None
            run.output_tokens = getattr(llm, "output_tokens", None) or None
            
            paragraph_suggestions.append((para, suggestions))

    output = _format_draft_suggestions(post_path, paragraph_suggestions)
    typer.echo(output)

    total = sum(len(s) for _, s in paragraph_suggestions)
    typer.echo(f"\nDone. Processed: {len(paragraphs)} paragraphs, Suggestions: {total}")


@app.command()
def audit(
    series_dir: Annotated[
        str,
        typer.Argument(help="Directory containing all series post files to scan"),
    ],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output report file path (default: link-opportunities-YYYY-MM-DD.md)"),
    ] = "",
    cache: Annotated[
        str,
        typer.Option("--cache", "-c", help="Path to SQLite cache file for post summaries"),
    ] = ".cross-link-cache.db",
    new_only: Annotated[
        Optional[str],
        typer.Option("--new-only", help="Only find inbound opportunities for this specific post file"),
    ] = None,
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help=f"LLM provider. Choices: {', '.join(PROVIDERS.keys())}"),
    ] = os.environ.get("MODEL_PROVIDER", "ollama"),
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Override the provider's default model."),
    ] = None,
    link_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Link format: 'wiki' for [[slug]] or 'markdown' for [Title](/blog/slug/)"),
    ] = "markdown",
    url_prefix: Annotated[
        str,
        typer.Option("--url-prefix", help="URL prefix for markdown links (e.g. /blog/ or /posts/)"),
    ] = os.environ.get("URL_PREFIX", "/blog/"),
    dry_run: bool = dry_run_option(),
    no_llm: bool = no_llm_option(),
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show extra debug output."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Show raw prompts and LLM responses."),
    ] = False,
):
    """Batch-scan a post archive and produce a cross-link checklist report."""

    dry_run = resolve_dry_run(dry_run, no_llm)

    series_path = Path(series_dir)
    if not series_path.is_dir():
        typer.echo(f"Error: Series directory not found: {series_path}", err=True)
        raise typer.Exit(1)

    posts = sorted(p for p in series_path.glob("**/*.md") if is_valid_post(p))
    if not posts:
        typer.echo(f"No valid markdown posts found in {series_path}", err=True)
        raise typer.Exit(1)

    llm = resolve_provider(PROVIDERS, provider, model, no_llm=no_llm, debug=debug)

    if dry_run:
        typer.echo(f"[dry-run] Would scan {len(posts)} posts in {series_path}")
        for p in posts:
            typer.echo(f"  {slug_from_path(p)}")
        raise typer.Exit(0)

    # Phase 1: extract summaries for all posts (with caching)
    typer.echo(f"Phase 1: Extracting summaries for {len(posts)} posts ...")
    init_cache(cache)
    all_summaries: list[dict] = []
    for p in posts:
        slug = slug_from_path(p)
        summary = _extract_summary(llm, p, slug, cache, verbose)
        all_summaries.append(summary)

    # Determine which posts to find opportunities for
    if new_only:
        new_slug = slug_from_path(Path(new_only))
        target_posts = [p for p in posts if slug_from_path(p) == new_slug]
        if not target_posts:
            typer.echo(f"Error: --new-only post '{new_only}' not found in series directory.", err=True)
            raise typer.Exit(1)
    else:
        target_posts = posts

    # Phase 2: find linking opportunities for each target post
    typer.echo(f"\nPhase 2: Finding opportunities for {len(target_posts)} posts ...")
    opportunities: list[dict] = []
    skipped = 0
    for p in target_posts:
        slug = slug_from_path(p)
        title = next((s["title"] for s in all_summaries if s["slug"] == slug), slug)
        _, content, _ = read_post(p)

        if verbose:
            typer.echo(f"  [finding] {slug} ...")

        with timed_run("series-cross-link-suggester", llm.model, source_location=slug) as run:
            prompt = build_audit_prompt(slug, title, content, all_summaries)
            if debug:
                typer.echo(f"\n[debug] Audit prompt for {slug}:\n{prompt}\n")

            try:
                raw = llm.complete(AUDIT_SYSTEM, prompt)
                if debug:
                    typer.echo(f"[debug] Response: {raw}")
                suggestions = parse_json_response(raw)
                if not isinstance(suggestions, list):
                    suggestions = []
                
                # Validation: anchor and context must exist in content (outside code blocks)
                content_no_code = strip_code_blocks(content)
                valid_for_post = []
                for s in suggestions:
                    try:
                        ls = LinkSuggestion(**s)
                        if ls.anchor_text not in content_no_code:
                            if verbose:
                                typer.echo(f"    ! Dropping anchor (not found outside code blocks): \"{ls.anchor_text}\"")
                            continue
                        if ls.context_phrase not in content_no_code:
                            if verbose:
                                typer.echo(f"    ! Dropping context (not found outside code blocks): \"{ls.context_phrase}\"")
                            continue
                        valid_for_post.append(ls.model_dump())
                    except Exception:
                        continue
                suggestions = valid_for_post
                
                run.item_count = 1
                run.input_tokens = getattr(llm, "input_tokens", None) or None
                run.output_tokens = getattr(llm, "output_tokens", None) or None
            except Exception as e:
                typer.echo(f"  Warning: failed for {slug}: {e}", err=True)
                suggestions = []
                skipped += 1

        opportunities.append({"post_slug": slug, "post_title": title, "suggestions": suggestions})

    # Generate report
    report_text = _format_audit_report(opportunities, all_summaries, link_format, url_prefix)
    output_path = Path(output) if output else Path(f"link-opportunities-{date.today().isoformat()}.md")

    output_path.write_text(report_text, encoding="utf-8")
    typer.echo(f"\nReport written to: {output_path}")
    total_suggestions = sum(len(o["suggestions"]) for o in opportunities)
    typer.echo(f"\nDone. Processed: {len(target_posts)}, Skipped: {skipped}, Suggestions: {total_suggestions}")


def _apply_links_to_file(file_path: Path, link_details: list[dict]) -> bool:
    """Insert links into a markdown file based on anchor text.
    link_details is a list of dicts with 'anchor', 'context', and 'replacement'.
    Only replaces text outside of code blocks.
    """
    raw = file_path.read_text(encoding="utf-8")
    
    # Split by frontmatter delimiters
    parts = raw.split("---", 2)
    if len(parts) < 3:
        # No frontmatter or malformed, treat as whole body
        header = ""
        body = raw
    else:
        # parts[0] is usually empty, parts[1] is frontmatter, parts[2] is body
        header = f"---{parts[1]}---"
        body = parts[2]

    # Split body into chunks: [text, code, text, code, ...]
    # We use a regex that captures the code blocks to keep them in the split results
    body_chunks = re.split(r"(```.*?```)", body, flags=re.DOTALL)
    
    modified = False
    for detail in link_details:
        anchor = detail["anchor"]
        context = detail["context"]
        replacement = detail["replacement"]

        # Only search and replace in the text chunks (indices 0, 2, 4...)
        for i in range(0, len(body_chunks), 2):
            text_chunk = body_chunks[i]
            
            if context in text_chunk:
                new_chunk = text_chunk.replace(anchor, replacement, 1)
                if new_chunk != text_chunk:
                    body_chunks[i] = new_chunk
                    modified = True
                    break # Link applied for this detail
            elif anchor in text_chunk:
                new_chunk = text_chunk.replace(anchor, replacement, 1)
                if new_chunk != text_chunk:
                    body_chunks[i] = new_chunk
                    modified = True
                    break # Link applied for this detail

    if modified:
        new_body = "".join(body_chunks)
        file_path.write_text(f"{header}{new_body}", encoding="utf-8")
    
    return modified


@app.command()
def apply(
    report: Annotated[str, typer.Argument(help="Path to the checklist report file")],
    series_dir: Annotated[
        str,
        typer.Option("--series-dir", "-s", help="Directory containing series posts"),
    ] = os.environ.get("SERIES_DIR", ""),
    dry_run: bool = dry_run_option(),
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show extra debug output."),
    ] = False,
):
    """Apply checked link opportunities from a report file to the actual post files."""
    report_path = Path(report)
    if not report_path.exists():
        typer.echo(f"Error: Report file not found: {report_path}", err=True)
        raise typer.Exit(1)

    if not series_dir:
        typer.echo("Error: --series-dir is required", err=True)
        raise typer.Exit(1)

    series_path = Path(series_dir)
    if not series_path.is_dir():
        typer.echo(f"Error: Series directory not found: {series_path}", err=True)
        raise typer.Exit(1)

    report_text = report_path.read_text(encoding="utf-8")

    # Parse checked links: {source_slug: [detail_dicts]}
    actions: dict[str, list[dict]] = {}
    current_source = None
    
    # Simple state machine to parse the new report format
    lines = report_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        source_match = re.match(r"^##\s+(.+)", line)
        if source_match:
            current_source = source_match.group(1).strip()
            i += 1
            continue

        link_match = re.search(r"^\s*-\s+\[x\]\s+Link\s+to\s+(.+?)\s+—", line)
        if link_match and current_source:
            # We found a checked link, now look ahead for details
            detail = {"target": link_match.group(1).strip()}
            i += 1
            while i < len(lines) and not lines[i].startswith("##") and not lines[i].strip().startswith("-"):
                detail_line = lines[i].strip()
                if detail_line.startswith("Anchor:"):
                    detail["anchor"] = detail_line.split("Anchor:", 1)[1].strip().strip('"')
                elif detail_line.startswith("Context:"):
                    detail["context"] = detail_line.split("Context:", 1)[1].strip().strip('"')
                elif detail_line.startswith("Suggested:"):
                    detail["replacement"] = detail_line.split("Suggested:", 1)[1].strip()
                i += 1
            
            if "anchor" in detail and "replacement" in detail:
                if current_source not in actions:
                    actions[current_source] = []
                actions[current_source].append(detail)
            continue
        i += 1

    if not actions:
        typer.echo("No checked link opportunities found in report (use [x] to select).")
        return

    # Map slugs to actual file paths
    all_files = list(series_path.glob("**/*.md"))
    slug_to_path_map = {slug_from_path(f): f for f in all_files}

    modified_count = 0
    for source_slug, link_details in actions.items():
        if source_slug not in slug_to_path_map:
            typer.echo(f"Warning: Could not find file for slug '{source_slug}'", err=True)
            continue

        file_path = slug_to_path_map[source_slug]
        if dry_run:
            typer.echo(f"[dry-run] Would add {len(link_details)} links to {file_path.name}")
            for d in link_details:
                typer.echo(f"  + Replace \"{d['anchor']}\" with \"{d['replacement']}\"")
        else:
            if verbose:
                typer.echo(f"Applying links to {file_path.name} ...")
            if _apply_links_to_file(file_path, link_details):
                modified_count += 1

    if dry_run:
        typer.echo(f"\nDry run complete. Would have modified {len(actions)} files.")
    else:
        typer.echo(f"\nDone. Modified {modified_count} files.")


if __name__ == "__main__":
    app()
