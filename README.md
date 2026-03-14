# series-cross-link-suggester

Find internal linking opportunities across blog series posts using local AI.

Two modes:
- **draft** — while writing a new post, surface cross-link candidates from existing series content
- **audit** — batch-scan a full post archive and produce a checklist report of linking opportunities

## What it does

### Draft mode
Chunks your draft into paragraphs and retrieves semantically similar content from published posts. Proposes wikilinks or URLs with suggested placement for each match.

### Audit mode
Two-phase pipeline:
1. Extract post summaries (title, topic, key concepts, audience stage) — cached to SQLite
2. For each post, suggest 2–4 cross-links with placement guidance (intro / body / closing)

Output: a `link-opportunities-YYYY-MM-DD.md` checklist you can work through in Obsidian.

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
| `--dry-run` | `-n` | false | Preview without calling LLM |
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
| `--dry-run` | `-n` | false | Preview what would be scanned |
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
