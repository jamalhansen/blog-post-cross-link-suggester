# series-cross-link-suggester

Find internal linking opportunities across blog series posts using local AI.

Two modes:
- **draft** — while writing a new post, surface cross-link candidates from existing series content
- **audit** — batch-scan a full post archive and produce a checklist report of linking opportunities

## Usage

### Draft Mode
Surface candidates for a single post being written:

```bash
uv run python src/main.py draft --file path/to/draft.md
```

### Audit Mode
Batch-scan a post archive and produce a report:

```bash
uv run python src/main.py audit --dir path/to/posts
```

## CLI Reference

All tools in this series share a common set of CLI flags for model management via [local-first-common](https://github.com/jamalhansen/local-first-common).

| Command | Argument | Description |
|---|---|---|
| `draft` | `--file` | Path to blog post draft |
| `audit` | `--dir` | Path to post archive directory |

Standard flags: `--provider`, `--model`, `--dry-run`, `--no-llm`

## Project Structure

This tool follows the [Local-First AI project blueprint](https://github.com/jamalhansen/local-first-common).

```
series-cross-link-suggester/
├── src/
│   ├── main.py          # Typer CLI entry point
│   ├── logic.py         # Core suggestion orchestration
│   ├── schema.py        # Pydantic models for links
│   ├── prompts.py       # System and user prompt builders
│   └── display.py       # Rich-based terminal formatting
├── pyproject.toml       # Managed by uv
└── tests/
    ├── test_main.py     # CLI integration tests via MockProvider
    └── ...
```
## Installation

```bash
git clone git@github.com:jamalhansen/blog-post-cross-link-suggester.git
cd blog-post-cross-link-suggester
uv sync
```

## Usage

```bash
# Draft mode
uv run series_cross_link_suggester.py draft path/to/my-draft.md --series-dir path/to/series/

# Audit mode — full archive
uv run series_cross_link_suggester.py audit path/to/series/

# Audit mode — new post only
uv run series_cross_link_suggester.py audit path/to/series/ --new-only my-new-post.md
```

## CLI Reference

### `draft`
| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--series-dir` | `-s` | `$SERIES_DIR` | Directory of published series posts |
| `--provider` | `-p` | `ollama` | LLM provider (ollama, anthropic, gemini, groq, deepseek) |
| `--model` | `-m` | — | Override provider's default model |
| `--dry-run` | `-n` | false | Call LLM but do not save results to disk/vault/DB. Print to stdout. |
| `--no-llm` | | false | Skip LLM call, use mock response. Implies `--dry-run`. |
| `--verbose` | `-v` | false | Extra debug output |
| `--debug` | `-d` | false | Show raw prompts and LLM responses |

### `audit`
| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | auto | Output report file path |
| `--cache` | `-c` | `.cross-link-cache.db` | SQLite cache for summaries |
| `--new-only` | — | — | Only find links for this post |
| `--provider` | `-p` | `ollama` | LLM provider |
| `--model` | `-m` | — | Override provider's default model |
| `--dry-run` | `-n` | false | Call LLM but do not save results to disk/vault/DB. Print to stdout. |
| `--no-llm` | | false | Skip LLM call, use mock response. Implies `--dry-run`. |
| `--verbose` | `-v` | false | Extra debug output |
| `--debug` | `-d` | false | Show raw prompts and LLM responses |

## Project structure

```
series-cross-link-suggester/
├── series_cross_link_suggester.py  # CLI (draft + audit commands)
├── tests/
│   └── test_series_cross_link_suggester.py
├── pyproject.toml
├── uv.toml                         # Local dev override (gitignored)
└── README.md
```
