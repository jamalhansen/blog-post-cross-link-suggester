"""Cross-link opportunity scanning and report formatting domain logic."""

from datetime import date
from pathlib import Path

import typer

from local_first_common.llm import parse_json_response
from local_first_common.tracking import timed_run

from .cache import get_cached_summary, save_summary
from .posts import read_post, slugify
from .prompts import SUMMARY_SYSTEM, build_summary_prompt
from .schema import DraftLinkSuggestion, LinkSuggestion, PostSummary


class CrossLinkError(Exception):
    """Base typed error for series-cross-link-suggester."""


class LLMRunError(CrossLinkError):
    """Raised when an LLM call fails fatally during cross-link generation."""


def _extract_summary(
    provider, post_path: Path, slug: str, cache_path: str, verbose: bool
) -> dict:
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

    with timed_run(
        "series-cross-link-suggester", provider.model, source_location=slug
    ) as run:
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


extract_summary = _extract_summary


def _format_audit_report(
    opportunities: list[dict],
    all_summaries: list[dict],
    link_format: str = "markdown",
    url_prefix: str = "/blog/",
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
                link_target = f'[[{ls.target_slug}]] (on phrase: "{ls.anchor_text}")'

            lines.append(f"- [ ] Link to {ls.target_slug} — placement: {ls.placement}")
            lines.append(f'      Anchor: "{ls.anchor_text}"')
            lines.append(f'      Context: "{ls.context_phrase}"')
            lines.append(f"      Suggested: {link_target}")
            lines.append(f"      Reason: {ls.reason}")
        lines.append("")
    return "\n".join(lines)


format_audit_report = _format_audit_report


def _format_draft_suggestions(
    post_path: Path, paragraph_suggestions: list[tuple[str, list]]
) -> str:
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
                lines.append(f"  → [[{ds.target_slug}]]")
                lines.append(f'    Anchor: "{ds.anchor_text}"')
                lines.append(f"    Reason: {ds.reason}")
            except Exception:
                continue
        lines.append("")
    if not any_found:
        lines.append("No cross-link opportunities found.")
    return "\n".join(lines)


format_draft_suggestions = _format_draft_suggestions
