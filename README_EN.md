# knowledge-asset-tool

[日本語](./README.md)

Automatically generate reusable knowledge assets from your codebase.
**No API key required. Works with Claude Code subscription only.**

## Problem This Tool Solves

Engineers don't write documentation for three reasons:

- **Too expensive** → AI generates it automatically, zero cost
- **Gets stale** → Generated directly from code, always up to date
- **Nobody reads it** → Output as RAG docs, slides, and audience-specific explanations

## Quick Start

### Step 1: Create a Repository from Template

> **⚠️ Security Warning: You MUST create this as a Private repository.**
> Generated documentation contains DB schemas, API specs, and business logic from the analyzed codebase.
> Pushing to a public repository is an information leak.
> (If docs/ is accidentally pushed to a public repo, GitHub Actions will auto-remove it.)

**Option A: Command Line (recommended — guarantees Private)**

```bash
gh repo create my-knowledge-assets \
  --template hideosugimoto/knowledge-asset-tool \
  --private \
  --clone
cd my-knowledge-assets
```

**Option B: GitHub UI**

Click **"Use this template"** → **"Create a new repository"** at the top right.

> **⛔ You MUST select "Private". Selecting Public creates an information leak risk.**

### Step 2: Clone Locally (Option B only)

```bash
git clone https://github.com/{your-username}/my-knowledge-assets.git
cd my-knowledge-assets
```

### Step 3: Install Dependencies

```bash
npm install -g @marp-team/marp-cli
npm install -g @mermaid-js/mermaid-cli
pip install pyyaml
```

### Step 4: Launch Claude Code and Run

```bash
claude
```

```
/go
```

Answer the questions, type "OK", and wait. Everything runs automatically:
- Code analysis and document generation
- Mermaid diagram → SVG conversion
- MkDocs site build
- Index and portal generation

### Step 5: Review Generated Output

```bash
# View with MkDocs site (searchable, navigable)
mkdocs serve
# → http://localhost:8000

# Or open slides directly
open docs/slides/feature-name-engineer.html
```

### Step 6: Publish to GitHub (Private repos only)

```bash
# Check if repo is Private (blocks Public repos)
python scripts/push_docs.py --check-only

# Push docs (only works for Private repos)
python scripts/push_docs.py
```

---

## Commands

| Command | Output | Use Case |
|---------|--------|----------|
| `/go` | Interactive wizard | **Recommended. Answer questions, then fully automated** |
| `/project:analyze` | Structure, details, review | Code review and design verification |
| `/project:analyze-full` | All sections | Complete documentation |
| `/project:analyze-rag` | RAG + YAML | Knowledge base accumulation |
| `/project:analyze-share` | Audience-specific | Team sharing and presentations |
| `/project:analyze-slide` | Slide deck | HTML / PDF / PPTX (20-30 slides, full coverage) |
| `/project:manual` | Complete manual | All screens, features, APIs, screen flow diagrams |
| `/project:manual-slide` | Manual-based slides | Generate slides from existing manual |
| `/project:user-guide` | Operations guide | End-user step-by-step instructions, no technical jargon |
| `/project:quick-ref` | Quick reference | A4 one-page cheat sheet, printable |
| `/project:generate-ai-docs` | AI documents | llms.txt + AGENTS.md generation |
| `/project:generate-site` | Documentation site | MkDocs Material searchable website |

### /go Output Modes

| Mode | Description |
|------|-------------|
| a) Standard | Structure, details, design review |
| b) Full | All sections (pro/sales/beginner explanations, RAG, decision log) |
| c) RAG | Minimal output (RAG document + YAML metadata only) |
| d) Share | Audience-specific explanations + narrative documentation |
| e) Slide | 20-30 slides covering all features (HTML/PDF/PPTX) |
| f) Manual | Complete manual with all screens, features, APIs |
| g) Manual Slide | Generate slides from existing manual (Duarte Slidedocs format) |
| h) AI Docs | llms.txt + AGENTS.md |
| j) Site | MkDocs Material searchable documentation site |
| k) User Guide | End-user operations guide, no technical jargon |
| l) Quick Ref | A4 one-page cheat sheet, printable |
| i) All | Generate all deliverables in one pass |

## Generated File Structure

```
docs/
├── architecture/
│   ├── {name}.md                # arc42 architecture document
│   └── {name}.rag.md            # RAG-optimized document
├── diagrams/
│   ├── {name}-*.mmd             # Mermaid diagrams (source)
│   └── {name}-*.svg             # SVG converted diagrams
├── explanations/
│   └── {name}/
│       ├── pro.md               # For engineers
│       ├── sales.md             # For sales/business
│       └── beginner.md          # For beginners
├── decisions/
│   └── {name}.md                # Decision records (MADR 4.0)
├── manual/
│   └── {name}/
│       ├── 00-index.md               # Table of contents
│       ├── 01-overview.md            # System overview
│       ├── 02-screen-flow.md         # Screen flow diagrams
│       ├── 03-features.md            # Feature catalog
│       ├── features/                 # Individual feature docs
│       ├── 04-api-reference.md       # API reference (all endpoints)
│       ├── 05-data-model.md          # Data model, ER diagrams
│       ├── 06-screen-specs.md        # Screen specifications (all screens)
│       ├── 07-walkthrough.md         # Use case walkthroughs
│       ├── 08-review.md              # Design review
│       ├── 09-user-guide.md          # End-user operations guide
│       ├── 10-quick-reference.md     # A4 quick reference
│       ├── db-reconciliation.md      # Code-DB reconciliation (DB analysis only)
│       └── openapi.yaml              # OpenAPI 3.x definition
├── meta/
│   └── {name}.yaml              # Machine-readable metadata
├── slides/
│   ├── {name}-engineer.html     # Code analysis slides
│   ├── {name}-sales.html
│   ├── {name}-beginner.html
│   ├── {name}-manual-engineer.html   # Manual-based Slidedocs
│   ├── {name}-manual-sales.html
│   └── {name}-manual-beginner.html
├── {name}-llms.txt              # AI-facing index
├── {name}-AGENTS.md             # AI agent instructions
├── {name}-index.md              # Project-specific index
└── index.md                     # Portal for all projects
```

## Security: 4-Layer Leak Prevention

Generated docs contain sensitive information. The following defenses are **automatically applied** to repositories created from this template.

```
Layer 1: .gitignore       — git add . never includes docs/ (no user action needed)
Layer 2: AI instructions  — AI tools are told not to git add -f docs/ (auto-loaded)
Layer 3: GitHub Actions   — If docs/ pushed to Public repo → auto-delete + Issue
Layer 4: push_docs.py     — Private-verified push (the only sanctioned method)
```

| Layer | Target | Mechanism | Auto-applied |
|-------|--------|-----------|:------------:|
| `.gitignore` | Humans + all AI | Block docs/, site/ from `git add .` | Yes |
| AI instruction files | Claude Code, Copilot, Cursor, Windsurf, Codex | Prohibit `git add -f docs/` and `.gitignore` modification | Yes |
| GitHub Actions | Everything (last line of defense) | Auto-remove docs/ + create Issue | Yes |
| `push_docs.py` | Sanctioned publish path | Check `gh repo view --json visibility` before push | Yes |

### AI Instruction Files

These files are included in the template and auto-loaded by each AI tool:

| File | AI Tool |
|------|---------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Claude Code, Codex, multi-tool standard |
| `.cursorrules` | Cursor |
| `.windsurfrules` | Windsurf |
| `.github/copilot-instructions.md` | GitHub Copilot |

## Quality Assurance Pipeline

All commands include multi-layered QA for accurate, practical documentation.

### Analysis Process

```
Step 0:  Fact Collection + Business Context + Framework Selection (single pass)
Step 0b: Storyline Design (Pyramid Principle)
Step 0c: Priority Mapping (Tier 1/2/3)
→ Writing (with thinking frameworks)
→ Self-Review (9-item checklist)
→ Quality check scripts (link integrity, terminology, diagram reverse-link, slide overflow)
→ verify_docs.py (mechanical verification)
```

### Quality Mechanisms

| Mechanism | Description |
|-----------|-------------|
| **Fact Collection** | Extract facts as structured YAML. Anything not in facts is prohibited |
| **Source Citations** | All claims include `(file:line)` references |
| **Thinking Frameworks** | Auto-select MECE, So What?, 4+1 View, ATAM based on system profile |
| **Storyline Design** | Conclusion-first pyramid structure, not template filling |
| **Priority Mapping** | Deep-dive core features, summarize auxiliary |
| **Self-Review** | Fact reconciliation, count matching, citation verification |
| **Quality Scripts** | Broken links, terminology consistency, diagram reverse-link, slide overflow |
| **Verification** | Mechanical check that paths, tables, endpoints actually exist |

## Applied Standards

| Deliverable | Standard | Source |
|-------------|----------|--------|
| Architecture docs | **arc42** v9 | [arc42.org](https://arc42.org/) |
| Architecture diagrams | **C4 Model** | [c4model.com](https://c4model.com/) |
| API reference | **OpenAPI 3.x** | [openapis.org](https://spec.openapis.org/) |
| Decision records | **MADR 4.0** | [adr.github.io/madr](https://adr.github.io/madr/) |
| Data models | **Crow's Foot** + data dictionary | Industry standard |
| Readable slides | **Duarte Slidedocs** | [duarte.com](https://www.duarte.com/resources/books/slidedocs/) |
| RAG documents | Chunk optimization + YAML frontmatter | Industry best practice |
| AI overview | **llms.txt** spec | [llmstxt.org](https://llmstxt.org/) |
| AI agent instructions | **AGENTS.md** standard | [agents.md](https://agents.md/) |

## Database-Aware Analysis

Generate accurate documentation that considers database state, not just source code.

The `/go` wizard auto-detects DB settings from `.env`, Prisma, Spring configs, etc.

### Supported Methods

| Method | Description | DB Connection |
|--------|-------------|---------------|
| Live DB | Execute SQL via user-specified command | Required |
| SQL Dump | Parse schema from `.sql` file | Not required |
| Migrations | Infer table structure from migration files | Not required |

### What DB Analysis Improves

- **Master data status**: Functions referencing inactive records annotated with [DB Inactive]
- **Feature flags**: Features disabled in DB settings annotated with [Feature OFF]
- **Display labels**: Japanese labels from DB reflected in documentation
- **Code-DB reconciliation**: Table/column mismatches reported as risks

## Automatic Tool Updates

`.github/workflows/sync-template.yml` checks for upstream updates every Monday.
If updates are found, a PR is created automatically. **Your docs/ are never overwritten.**

## Future Extensions (v2)

- claude-memory-kit integration (auto-reference across sessions)
- Local RAG search (ask-my-codebase command)
- Auto-conversion to MCP tool definitions

See [EXTENSION.md](./EXTENSION.md) for details.
