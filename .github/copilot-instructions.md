# GitHub Copilot Instructions — knowledge-asset-tool

## SECURITY (HIGHEST PRIORITY)

NEVER push docs/ or site/ to public repositories.
Generated documentation contains sensitive information from analyzed codebases
(DB schemas, API specs, business logic, screen designs).

FORBIDDEN operations (unless repository is confirmed Private):
- `git add -f docs/`
- `git add -f site/`
- Removing `docs/` or `site/` from `.gitignore`
- `git push --no-verify`

To push docs safely: `python scripts/push_docs.py` (auto-blocks public repos).

## Project Overview

Tool to auto-generate knowledge assets (documentation, slides, API specs) from codebases.
Uses Claude Code slash commands (`/go`, `/project:analyze`, `/project:manual`).
Generated output goes to `docs/` which is gitignored by default.

## Project Structure

```
scripts/          — Tool scripts (Python)
templates/        — Document templates (Markdown)
.claude/commands/ — Claude Code slash commands
docs/             — Generated docs (gitignored)
site/             — MkDocs build output (gitignored)
.cache/           — DB analysis cache (gitignored)
```

## Commands

| Command | Purpose |
|---------|---------|
| `/go` | **Recommended.** Interactive wizard — generates all assets automatically |
| `/project:analyze` | Code analysis (standard: structure, details, review) |
| `/project:analyze-full` | Code analysis (full: arc42, explanations, RAG, MADR) |
| `/project:analyze-rag` | RAG document + YAML metadata only |
| `/project:analyze-share` | Audience-specific explanations + narrative |
| `/project:analyze-slide` | Slide deck (engineer/sales/beginner, HTML/PDF/PPTX) |
| `/project:manual` | Complete manual (all screens, features, APIs, OpenAPI) |
| `/project:manual-slide` | Manual-based Slidedocs generation |
| `/project:user-guide` | End-user operations guide (no technical jargon) |
| `/project:quick-ref` | A4 one-page quick reference card |
| `/project:generate-ai-docs` | AI documents (llms.txt + AGENTS.md) |
| `/project:generate-site` | MkDocs Material searchable website |
| `/project:customize` | Customize templates and settings |

`/go` delegates to the above commands internally. Individual commands are for expert use.

## Code Style

- Python 3 with type hints
- Scripts in `scripts/` — keep each script focused and under 800 lines
- Templates in `templates/` — Markdown with Jinja-style placeholders
- Use immutable patterns; avoid mutating shared state
- Always handle errors with clear messages
- Validate inputs (file paths, CLI arguments) before processing
- No hardcoded secrets — use environment variables
