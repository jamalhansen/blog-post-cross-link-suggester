"""Series Cross-Link Suggester — find internal linking opportunities across blog series posts.

Two modes:
  draft   — surface cross-link candidates for a single post being written
  audit   — batch-scan a full post archive and produce a checklist report
"""

import os
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

import typer

from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
    resolve_provider,
)
from local_first_common.llm import parse_json_response
from local_first_common.providers import PROVIDERS
from local_first_common.tracking import timed_run

from .cache import get_cached_summary, init_cache, save_summary
from .posts import chunk_paragraphs, read_post, slug_from_path
from .prompts import (
    AUDIT_SYSTEM,
    DRAFT_SYSTEM,
    SUMMARY_SYSTEM,
    build_audit_prompt,
    build_draft_prompt,
    build_summary_prompt,
)
from .schema import DraftLinkSuggestion, LinkSuggestion, PostSummary

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

    title, body = read_post(post_path)
    raw = provider.complete(SUMMARY_SYSTEM, build_summary_prompt(body))
    data = parse_json_response(raw)
    summary = PostSummary(
        title=data.get("title") or title,
        main_topic=data.get("main_topic", ""),
        key_concepts=data.get("key_concepts", []),
        audience_stage=data.get("audience_stage", "intermediate"),
    )
    save_summary(cache_path, slug, post_path, summary.model_dump())
    return {"slug": slug, **summary.model_dump()}


def _format_audit_report(opportunities: list[dict]) -> str:
    """Render audit results as a markdown checklist report."""
    today = date.today().isoformat()
    lines = ["# Internal Link Opportunity Report", f"Generated: {today}", ""]
    for opp in opportunities:
        slug = opp["post_slug"]
        suggestions = opp["suggestions"]
        lines.append(f"## {slug}")
        if not suggestions:
            lines.append("_(no opportunities found)_")
        for s in suggestions:
            try:
                ls = LinkSuggestion(**s) if isinstance(s, dict) else s
                lines.append(
                    f"- [ ] Link to [[{ls.target_slug}]] — placement: {ls.placement}"
                )
                lines.append(f"      Reason: {ls.reason}")
            except Exception:
                continue
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

    if no_llm:
        dry_run = True

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

    series_posts = sorted(p for p in series_path.glob("**/*.md") if p != post_path)

    if dry_run:
        typer.echo(f"[dry-run] Would analyse {post_path.name} against {len(series_posts)} posts in {series_path}")
        return

    llm = resolve_provider(PROVIDERS, provider, model, no_llm=no_llm, debug=debug, verbose=verbose)

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
    _, body = read_post(post_path)
    paragraphs = chunk_paragraphs(body)
    if verbose:
        typer.echo(f"\nAnalysing {len(paragraphs)} paragraphs in {post_path.name} ...")

    paragraph_suggestions: list[tuple[str, list]] = []
    with timed_run("series-cross-link-suggester", llm.model, source_location=str(post_path)) as _tracking:
        for para in paragraphs:
            prompt = build_draft_prompt(para, all_summaries)
            if debug:
                typer.echo(f"\n[debug] Draft prompt:\n{prompt}\n")
            raw = llm.complete(DRAFT_SYSTEM, prompt)
            if debug:
                typer.echo(f"[debug] Response: {raw}")
            suggestions = parse_json_response(raw)
            if not isinstance(suggestions, list):
                suggestions = []
            paragraph_suggestions.append((para, suggestions))
        _tracking.item_count = len(paragraphs)
        _tracking.input_tokens = getattr(llm, "input_tokens", None) or None
        _tracking.output_tokens = getattr(llm, "output_tokens", None) or None

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

    if no_llm:
        dry_run = True

    series_path = Path(series_dir)
    if not series_path.is_dir():
        typer.echo(f"Error: Series directory not found: {series_path}", err=True)
        raise typer.Exit(1)

    posts = sorted(series_path.glob("**/*.md"))
    if not posts:
        typer.echo(f"No markdown files found in {series_path}", err=True)
        raise typer.Exit(1)

    if dry_run:
        typer.echo(f"[dry-run] Would scan {len(posts)} posts in {series_path}")
        for p in posts:
            typer.echo(f"  {p.name}")
        return

    llm = resolve_provider(PROVIDERS, provider, model, no_llm=no_llm, debug=debug, verbose=verbose)

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
    with timed_run("series-cross-link-suggester", llm.model, source_location=str(series_path)) as _tracking:
        for p in target_posts:
            slug = slug_from_path(p)
            title = next((s["title"] for s in all_summaries if s["slug"] == slug), slug)
            _, content = read_post(p)

            if verbose:
                typer.echo(f"  [finding] {slug} ...")

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
            except Exception as e:
                typer.echo(f"  Warning: failed for {slug}: {e}", err=True)
                suggestions = []
                skipped += 1

            opportunities.append({"post_slug": slug, "post_title": title, "suggestions": suggestions})
        _tracking.item_count = len(target_posts) - skipped
        _tracking.input_tokens = getattr(llm, "input_tokens", None) or None
        _tracking.output_tokens = getattr(llm, "output_tokens", None) or None

    # Generate report
    report_text = _format_audit_report(opportunities)
    output_path = Path(output) if output else Path(f"link-opportunities-{date.today().isoformat()}.md")

    output_path.write_text(report_text, encoding="utf-8")
    typer.echo(f"\nReport written to: {output_path}")
    total_suggestions = sum(len(o["suggestions"]) for o in opportunities)
    typer.echo(f"\nDone. Processed: {len(target_posts)}, Skipped: {skipped}, Suggestions: {total_suggestions}")


if __name__ == "__main__":
    app()
