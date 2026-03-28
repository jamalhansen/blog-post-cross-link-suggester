# series-cross-link-suggester

Find internal linking opportunities across blog series posts using local AI.

Three modes:
- **draft** — surface cross-link candidates from existing series content for a post being written
- **audit** — batch-scan a full post archive and produce a markdown checklist report
- **apply** — automatically insert links into posts for items checked in an audit report

## Installation

```bash
git clone git@github.com:jamalhansen/series-cross-link-suggester.git
cd series-cross-link-suggester
uv sync
```

## Usage

### Draft mode

Surface link candidates while writing a new post:

```bash
uv run cross-link draft path/to/draft.md --series-dir path/to/series/
```

### Audit mode

Scan all posts and generate a `link-opportunities-YYYY-MM-DD.md` checklist:

```bash
# Full archive scan
uv run cross-link audit path/to/series/

# New post only — find inbound links other posts should add
uv run cross-link audit path/to/series/ --new-only path/to/series/my-new-post.md

# Generate standard markdown links for Hugo instead of WikiLinks
uv run cross-link audit path/to/series/ --format markdown

# Custom output path
uv run cross-link audit path/to/series/ --output report.md
```

### Apply mode

Automatically apply checked (`- [x]`) links from a report:

```bash
uv run cross-link apply report.md --series-dir path/to/series/
```

### Preview without side effects

```bash
# See what would be scanned without calling the LLM
uv run cross-link draft path/to/draft.md --series-dir path/to/series/ --dry-run
uv run cross-link audit path/to/series/ --dry-run

# Skip the LLM entirely (uses mock responses, implies --dry-run)
uv run cross-link draft path/to/draft.md --series-dir path/to/series/ --no-llm
```

## CLI Reference

### `draft`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `POST` | — | — | Path to draft post file |
| `--series-dir` | `-s` | `$SERIES_DIR` | Directory of published series posts |
| `--cache` | `-c` | `.cross-link-cache.db` | SQLite cache for series summaries |
| `--provider` | `-p` | `ollama` | LLM provider (ollama, anthropic, gemini, groq, deepseek) |
| `--model` | `-m` | — | Override provider's default model |
| `--dry-run` | `-n` | false | Call LLM but do not write output files. Print to stdout. |
| `--no-llm` | — | false | Skip LLM call entirely, use mock. Implies `--dry-run`. |
| `--verbose` | `-v` | false | Show per-paragraph progress |
| `--debug` | `-d` | false | Show raw prompts and LLM responses |

### `audit`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `SERIES_DIR` | — | — | Directory containing all series post files |
| `--output` | `-o` | auto | Output report path (default: `link-opportunities-YYYY-MM-DD.md`) |
| `--cache` | `-c` | `.cross-link-cache.db` | SQLite cache for post summaries |
| `--new-only` | — | — | Only find link opportunities for this specific post file |
| `--format` | `-f` | `wiki` | Link format: `wiki` ([[slug]]) or `markdown` ([Title](/posts/slug/)) |
| `--provider` | `-p` | `ollama` | LLM provider |
| `--model` | `-m` | — | Override provider's default model |
| `--dry-run` | `-n` | false | Call LLM but do not write output files. Print to stdout. |
| `--no-llm` | — | false | Skip LLM call entirely, use mock. Implies `--dry-run`. |
| `--verbose` | `-v` | false | Show per-post progress |
| `--debug` | `-d` | false | Show raw prompts and LLM responses |

### `apply`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `REPORT` | — | — | Path to the checklist report file |
| `--series-dir` | `-s` | `$SERIES_DIR` | Directory containing series posts |
| `--dry-run` | `-n` | false | Show what would be added without modifying files |
| `--verbose` | `-v` | false | Show per-file progress |

## Audit report format

```markdown
# Internal Link Opportunity Report
Generated: 2025-03-20

## sql-thinks-in-sets-not-loops
- [ ] Link to [[i-know-python-why-learn-sql]] — placement: intro
      Reason: Prerequisite framing for Python developers new to SQL
- [ ] Link to [[sql-joins-explained]] — placement: body
      Reason: JOIN is the natural next topic after set-based thinking
```

## Caching

The `audit` command caches post summaries in a SQLite database (default: `.cross-link-cache.db`). Summaries are invalidated automatically when a post file changes (MD5 hash check). This makes repeated runs fast — only new or modified posts are re-summarized.

## Project structure

```
series-cross-link-suggester/
├── src/
│   └── cross_link/
│       ├── logic.py      # Typer CLI (draft, audit, and apply commands)
│       ├── posts.py      # slug_from_path, read_post, chunk_paragraphs
│       ├── cache.py      # SQLite summary cache
│       ├── prompts.py    # LLM prompt builders
│       └── schema.py     # Pydantic models
├── tests/
│   ├── test_cache.py
│   ├── test_posts.py
│   ├── test_prompts.py
│   ├── test_logic.py
│   └── test_series_cross_link_suggester.py
├── pyproject.toml
└── README.md
```
