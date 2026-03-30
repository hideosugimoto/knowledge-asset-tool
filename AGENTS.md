# knowledge-asset-tool

Auto-generate reusable knowledge assets (docs, slides, API specs) from codebases.

## Security Rules (HIGHEST PRIORITY — NEVER VIOLATE)

### 🔒 NEVER push docs/ or site/ to public repositories

Generated documentation contains **sensitive information** from analyzed codebases:
- Database schemas (table names, columns, ER diagrams)
- API specifications (endpoints, auth mechanisms, OpenAPI definitions)
- Business logic (calculations, approval workflows)
- Screen designs (form specs, table definitions)

**FORBIDDEN operations (unless repository is confirmed Private):**
- `git add -f docs/` — FORBIDDEN
- `git add -f site/` — FORBIDDEN
- Removing `docs/` or `site/` from `.gitignore` — FORBIDDEN
- `git push --no-verify` — FORBIDDEN

**To push docs safely:**
```bash
python scripts/push_docs.py --check-only  # Check visibility first
python scripts/push_docs.py               # Only works for Private repos
```

### NEVER modify .gitignore to remove these lines:
```
docs/
site/
.cache/
```

## Tech Stack

- Python 3 (scripts)
- MkDocs Material (documentation site)
- Marp CLI (slide generation)
- Mermaid CLI (diagram generation)

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
