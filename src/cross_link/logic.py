"""Series Cross-Link Suggester — find internal linking opportunities across blog series posts.

Two modes:
  draft   — surface cross-link candidates for a single post being written
  audit   — batch-scan a full post archive and produce a checklist report
"""

import os
from pathlib import Path
from typing import Annotated, Optional

import typer

from local_first_common.cli import (
    dry_run_option,
    no_llm_option,
)
from local_first_common.providers import PROVIDERS

app = typer.Typer(help=__doc__)


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

    if dry_run:
        typer.echo(f"[dry-run] Would analyse {post_path.name} against posts in {series_path}")
        return

    # TODO: implement draft mode
    # 1. Load draft post
    # 2. Chunk into paragraphs
    # 3. For each chunk, retrieve semantically similar content from series posts
    # 4. Propose wikilink or URL for each match with suggested placement
    typer.echo("Draft mode: not yet implemented. Coming soon.")
    typer.echo("\nDone. Processed: 0, Skipped: 0")


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

    # TODO: implement audit mode
    # Phase 1: extract post summaries (title, topic, key concepts, audience stage), cache to SQLite
    # Phase 2: for each post, find 2-4 linking opportunities using all summaries as context
    # Output: markdown checklist report with [ ] items per post
    typer.echo("Audit mode: not yet implemented. Coming soon.")
    typer.echo(f"\nDone. Processed: 0, Skipped: {len(posts)}")


if __name__ == "__main__":
    app()
