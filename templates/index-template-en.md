# {NAME} Documentation

> Generated: {DATE} | Target: {TARGET_PATH} | Tool: knowledge-asset-tool

---

## Quick Links by Reader

| You are... | Start here |
|------------|-----------|
| Engineer (want to understand the design) | [arc42 Architecture](architecture/{NAME}.md) -> [API Reference](manual/{NAME}/04-api-reference.md) |
| Engineer (first time) | [Beginner Guide](explanations/{NAME}/beginner.md) -> [Complete Manual](manual/{NAME}/00-index.md) |
| Sales / Business | [Sales Explanation](explanations/{NAME}/sales.md) or [Sales Slides](slides/{NAME}-sales.html) |
| End User (how to use) | [Operations Guide](manual/{NAME}/09-user-guide.md) -> [Quick Reference](manual/{NAME}/10-quick-reference.md) |
| AI Agent | [llms.txt]({NAME}-llms.txt) / [AGENTS.md]({NAME}-AGENTS.md) |

---

## 1. Architecture Documents

| Document | Description | File |
|----------|-------------|------|
| arc42 (12 sections) | Full system design documentation | [architecture/{NAME}.md](architecture/{NAME}.md) |
| RAG Document | AI-search-optimized chunks | [architecture/{NAME}.rag.md](architecture/{NAME}.rag.md) |
| Decision Records (MADR) | Design decisions and rationale | [decisions/{NAME}.md](decisions/{NAME}.md) |
| YAML Metadata | Machine-readable component list | [meta/{NAME}.yaml](meta/{NAME}.yaml) |

---

## 2. Complete Manual

| Chapter | Description | File |
|---------|-------------|------|
| Table of Contents | Links to all chapters | [00-index.md](manual/{NAME}/00-index.md) |
| Chapter 1 | System Overview / Tech Stack | [01-overview.md](manual/{NAME}/01-overview.md) |
| Chapter 2 | Screen Flow / Screen List | [02-screen-flow.md](manual/{NAME}/02-screen-flow.md) |
| Chapter 3 | Feature Catalog | [03-features.md](manual/{NAME}/03-features.md) |
| Chapter 4 | API Reference | [04-api-reference.md](manual/{NAME}/04-api-reference.md) |
| Chapter 5 | Data Model | [05-data-model.md](manual/{NAME}/05-data-model.md) |
| Chapter 6 | Screen Specifications | [06-screen-specs.md](manual/{NAME}/06-screen-specs.md) |
| Chapter 7 | Use Case Walkthroughs | [07-walkthrough.md](manual/{NAME}/07-walkthrough.md) |
| Chapter 8 | Design Review / Improvement Proposals | [08-review.md](manual/{NAME}/08-review.md) |
| OpenAPI | Swagger/OpenAPI 3.0 Definition | [openapi.yaml](manual/{NAME}/openapi.yaml) |

### Chapter 3 Feature Catalog (Individual Files)

{FEATURES_TABLE}

---

## 3. Operations Guide (for End Users)

| Document | Description | File |
|----------|-------------|------|
| Operations Guide | Step-by-step instructions without technical jargon | [09-user-guide.md](manual/{NAME}/09-user-guide.md) |
| Quick Reference | A4 one-page cheat sheet (printable) | [10-quick-reference.md](manual/{NAME}/10-quick-reference.md) |

---

## 4. Explanations by Level

| Target Reader | Description | File |
|--------------|-------------|------|
| Engineer | Technical details, design intent, code examples | [pro.md](explanations/{NAME}/pro.md) |
| Sales / Business | Business value, quantitative impact, adoption steps | [sales.md](explanations/{NAME}/sales.md) |
| Beginner Engineer | Gentle explanations, glossary, learning path | [beginner.md](explanations/{NAME}/beginner.md) |

---

## 5. Slide Materials

### Code Analysis Based

| Target Reader | HTML | PDF | PPTX |
|--------------|------|-----|------|
| Engineer | [HTML](slides/{NAME}-engineer.html) | [PDF](slides/{NAME}-engineer.pdf) | [PPTX](slides/{NAME}-engineer.pptx) |
| Sales | [HTML](slides/{NAME}-sales.html) | [PDF](slides/{NAME}-sales.pdf) | [PPTX](slides/{NAME}-sales.pptx) |
| Beginner | [HTML](slides/{NAME}-beginner.html) | [PDF](slides/{NAME}-beginner.pdf) | [PPTX](slides/{NAME}-beginner.pptx) |

### Manual Based (Slidedocs Format)

| Target Reader | HTML | PDF | PPTX |
|--------------|------|-----|------|
| Engineer | [HTML](slides/{NAME}-manual-engineer.html) | [PDF](slides/{NAME}-manual-engineer.pdf) | [PPTX](slides/{NAME}-manual-engineer.pptx) |
| Sales | [HTML](slides/{NAME}-manual-sales.html) | [PDF](slides/{NAME}-manual-sales.pdf) | [PPTX](slides/{NAME}-manual-sales.pptx) |
| Beginner | [HTML](slides/{NAME}-manual-beginner.html) | [PDF](slides/{NAME}-manual-beginner.pdf) | [PPTX](slides/{NAME}-manual-beginner.pptx) |

---

## 6. AI Documents

| Document | Purpose | File |
|----------|---------|------|
| llms.txt | Index for AI to discover and understand the project | [{NAME}-llms.txt]({NAME}-llms.txt) |
| AGENTS.md | Task instructions for AI agents | [{NAME}-AGENTS.md]({NAME}-AGENTS.md) |

---

## 7. Diagrams (Mermaid -> SVG)

{DIAGRAMS_TABLE}

---

## Sharing

### Share as a Folder (Recommended)

Simply copy the `site/` folder to share as a searchable documentation site.

```
Copy site/ -> Open index.html in browser
```

- Full-text search
- Dark mode toggle
- Automatic Mermaid diagram rendering
- Auto-generated navigation and table of contents

### Local Preview

```bash
mkdocs serve
# -> http://localhost:8000
```
