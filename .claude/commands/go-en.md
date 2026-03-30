# /project:go-en

A wizard to generate knowledge assets in a single command (English version).
Ask all required questions up front, then execute everything automatically.

## Step 0: Environment Check (first run only)

Check for the following tools and suggest installation if missing.

```bash
# Required tools
marp --version     || echo "Not installed: npm install -g @marp-team/marp-cli"
mmdc --version     || echo "Not installed: npm install -g @mermaid-js/mermaid-cli"
python3 -c "import yaml" || echo "Not installed: pip install pyyaml"
mkdocs --version   || echo "Not installed: pip install mkdocs-material"
```

If any tools are missing:
```
Warning: The following tools are not installed:

  - marp (used for slide generation)
  - mmdc (used for Mermaid SVG conversion)

  Install them now? (Y/n)
```

Y -> auto-install. N -> skip (inform that related features won't be available).
If all tools are already installed, proceed silently to Step 1.

## Step 1: Questions

Ask the following questions all at once. Number them and wait for the user's response.
Do not ask any follow-up questions.

```
Let's generate knowledge assets. Please answer the following questions.

1. Target path (path to the code you want to analyze)
   Example: ./src/auth, /Users/.../project

2. Name (used for output file names; alphanumeric + hyphens recommended)
   - For a)-e): feature name (e.g., user-authentication, payment-flow)
   - For f) g): system name (e.g., my-app, my-app)

3. Output mode (select by number, multiple allowed)
   a) Standard (structure, details, review)
   b) Full (all sections)
   c) RAG-optimized (minimal, fast)
   d) Shareable (level-based explanations)
   e) Slides (20-30 slides covering all features)
   f) Complete manual (all screens, features, APIs, screen flows, screen specs)
   g) Manual-based slides (Slidedocs from generated manual)
   h) AI documents ({name}-llms.txt + {name}-AGENTS.md)
   j) Documentation site (searchable website via MkDocs Material)
   k) Operations guide (for end users; no technical jargon, step-by-step)
   l) Quick reference (A4 one-page cheat sheet, printable)
   i) All (b + e + f + g + h + j + k + l; RAG output is included in b)

4. Answer only if you selected e), g), or h):
   - Target audience: engineer / sales / beginner (default: engineer)
   - Output format: html / pdf / pptx (default: html)
```

**Output directory is always `./docs` (fixed).** Do not ask the user.
Project-name-prefixed filenames allow multiple projects to coexist safely in the same `./docs`.

## Step 1.3: Frontend Auto-detection

Run `python3 scripts/detect_frontend.py --source-dir {target_path} --human` on the target path.

**If a frontend is detected:**
```
A frontend project was detected.

  Detected frontend:
    1. {framework} ({path}) -- {page_count} screens, {store_count} stores

  Include it in the analysis? (Y/n)
```

Y (or default) -> add the frontend path to the analysis target.
N -> analyze backend only (screen-related content will be tagged [Inferred]).

**If not detected:** proceed silently.

## Step 1.5: Database Integration Check

**After receiving the target path, check for database integration.**

### 1.5-A. Auto-detect DB connection settings

Run `python3 scripts/scan_database.py --source-dir {target_path}` to detect DB connection settings and migration directories.

### 1.5-B. Present results and confirm

**If DB connections are detected:**
```
Database connection settings detected.

  Detected connections:
    1. [{type}] {db_name} (host: {host}:{port}) -- source: {filename}
    2. [{type}] {db_name} (host: {host}:{port}) -- source: {filename}
    ...

  Detected migrations:
    - {directory_path} ({N} files)

Please confirm:
  Q1. Are there any other databases not listed above? (If so, provide type, name, and purpose)
      * Check for databases connected via custom configuration files
  Q2. What is the purpose of each database? (e.g., main DB, log DB, cache, etc.)
  Q3. Should any databases be excluded? (Log/cache DBs are typically excluded)
  Q4. Choose the analysis method (can specify per DB if multiple):
      (a) Live DB connection (provide the SQL command)
      (b) SQL dump file (provide the path)
      (c) Skip DB analysis (code analysis only)
```

**(a) If live DB connection is selected:**
```
Please provide the command to execute SQL against the database.
SQL will be piped to this command via stdin.

Examples:
  - mysql -u root -N mydb
  - docker exec -i mysql_container mysql -u root mydb
  - ssh app-server 'mysql -u app -pPASS mydb'
  - kubectl exec -i pod/mysql -- mysql -u root mydb
  - psql -U postgres -t mydb
  - Or any project-specific connection method

Also specify the DB type: mysql / postgresql
```

**If no DB connections are detected:**
```
No database connection settings were detected.

Does this project use a database?
  (a) Yes -> provide DB type, name, and purpose
  (b) No -> skip DB analysis (code analysis only)
```

### 1.5-C. Execute DB Analysis

Based on the user's answers, retrieve schema information for each target DB:

- **(a) Live DB**: `python3 scripts/scan_database.py --sql-command "{user_command}" --db-type {mysql|postgresql} --output .cache/db-{db_name}.json`
- **(b) SQL dump**: `python3 scripts/scan_database.py --dump-file {path} --output .cache/db-{db_name}.json`
- **(c) Skip**: proceed to Step 2 without DB analysis

Results are saved to `.cache/db-{db_name}.json` and referenced in subsequent analysis steps.

**Warning: Only read queries (SELECT) are executed against live databases. No writes are performed.**

### 1.5-D. Final DB Configuration Confirmation

```
Database configuration understood as follows:

  Analysis targets:
    1. {db_name} ({type}) -- {purpose} -- Tables: {N} -- Included
    2. {db_name} ({type}) -- {purpose}                -- Excluded

  Master tables detected: {N}
  Tables with active/inactive flags: {N}
  Configuration tables: {N}
  Tables with label/name columns: {N}

If this looks correct, type "OK". Otherwise, let me know what needs to be changed.
```

**Do not start analysis until the user confirms with "OK".**

## Step 2: Confirm Settings

After receiving the user's answers, display the configuration and ask for confirmation.

```
The following settings will be used:

  Target path:  {answer1}
  Frontend:     {framework} ({path}) -- {page_count} screens  *shown only if detected
  Name:         {answer2}
  Output mode:  {answer3}
  DB analysis:  {summary or "None (code analysis only)"}
  Output dir:   ./docs
  Estimated time: {estimate}

Type "OK" to proceed.
```

<!-- Estimated time calculation:
  Mode a) Standard: ~5 min
  Mode b) Full: ~10 min
  Mode c) RAG: ~3 min
  Mode d) Shareable: ~5 min
  Mode e) Slides: ~8 min (x3 min per audience)
  Mode f) Manual: ~15 min
  Mode g) Manual slides: ~8 min
  Mode h) AI docs: ~3 min
  Mode i) All: ~30-45 min
  Mode j) Site: ~2 min
  Mode k) Operations guide: ~8 min
  Mode l) Quick reference: ~3 min
  Add up when multiple modes are selected.
-->

Proceed to Step 3 after receiving "OK".

## Step 3: Execute Analysis

**Fact cache**:
Before entering Step 0 (fact collection) of each command, run `python3 scripts/cache_analysis.py --action check-facts --source-dir {target_path} --name {name}`.
If the cache is valid, load from `.cache/facts-{name}.yaml` and skip fact collection, displaying "Using cached facts ({date}, commit {hash})".
If the cache is invalid (source changed) or missing, run fact collection normally and save with `python3 scripts/cache_analysis.py --action save-facts --source-dir {target_path} --name {name}`.

**Module validity check**: Follow `quality-rules.md` §4a to determine each module's active status during fact collection. Do not list modules solely based on code directory existence.

Execute analysis according to the selected output mode.

**Subagent delegation rules (applied in mode i "All"):**

In mode i), each command is delegated to a subagent (Agent tool) to reduce context consumption.
Single modes (a-h, j-n) run directly in the main session as before.

Mandatory rules when delegating to subagents (strictly enforced for quality):

1. **Pass facts as file path**: Do NOT pass text summaries. Pass `.cache/facts-{name}.yaml` path and have the agent Read it
2. **Have agent Read command file**: Pass `.claude/commands/{command}.md` path for full Read
3. **Have agent Read quality rules**: Pass `templates/quality-rules.md` path for Read
4. **Specify all settings explicitly**: target path, name, frontend info, inspection mode, DB analysis path
5. **Write output directly to disk**: Use Write tool, not `--- FILE: ---` format
6. **Agent reads source code itself**: Using source paths from facts YAML

Subagent prompt template:
```
Execute the following document generation task.

■ Preparation (must execute first)
1. Read `templates/quality-rules.md` for quality rules
2. Read `.claude/commands/{command}.md` for generation instructions
3. Read `.cache/facts-{name}.yaml` for fact data
4. If DB analysis exists: Read `.cache/db-{db_name}.json`

■ Settings
- Target path: {target_path}
- Project name: {name}
- Frontend: {detection result or "not detected"}
- Inspection mode: {enabled/disabled}
- Document ID prefix: {prefix} (only when inspection mode enabled)

■ Execution
Follow the "Execution" section of `.claude/commands/{command}.md`.
Generate documents and save directly to ./docs/ using the Write tool.
Refer to source paths in the facts YAML and Read source code as needed
to verify accuracy.

■ Quality check
Run the self-review checklist from `templates/quality-rules.md` §5 before output.
```

### Output mode a) Standard

Follow the "Execution" section of .claude/commands/analyze.md.
Generate output in `--- FILE: docs/.../{name}.md ---` format.

### Output mode b) Full

Follow the "Execution" section of .claude/commands/analyze-full.md.
Generate output in `--- FILE: docs/.../{name}.md ---` format.

### Output mode c) RAG

Follow the "Execution" section of .claude/commands/analyze-rag.md.
Generate output in `--- FILE: docs/.../{name}.md ---` format.

### Output mode d) Shareable

Follow the "Execution" section of .claude/commands/analyze-share.md.
Generate output in `--- FILE: docs/.../{name}.md ---` format.

### Output mode e) Slides

Follow the "Execution" section of .claude/commands/analyze-slide.md.
Run Marp CLI to convert files automatically.

### Output mode f) Complete Manual

Follow the "Execution" section of .claude/commands/manual.md.

### Output mode g) Manual-based Slides

Follow the "Execution" section of .claude/commands/manual-slide.md.
If the manual hasn't been generated yet, instruct to run f) first.

### Output mode h) AI Documents

Follow the "Execution" section of .claude/commands/generate-ai-docs.md.

### Output mode j) Documentation Site

Follow the "Execution" section of .claude/commands/generate-site.md.
If docs haven't been generated yet, instruct to run f) first.

### Output mode k) Operations Guide

Follow the "Execution" section of .claude/commands/user-guide.md.

### Output mode l) Quick Reference

Follow the "Execution" section of .claude/commands/quick-ref.md.

### Output mode i) All

Delegate to subagents for parallel execution. Each agent follows the "Subagent delegation rules" above.

#### Phase 0: Fact Collection (main session)

If fact cache is invalid or missing, run Step 0 fact collection in the main session and save to `.cache/facts-{name}.yaml`.
Skip if cache is valid. **Ensure fact cache exists before starting Phase A.**

#### Phase A: Independent Document Generation (parallel subagents)

The following 7 commands have no dependencies — **launch all in parallel using the Agent tool**.
Use the subagent prompt template with the corresponding command file for each.

| # | Command file | Output |
|---|-------------|--------|
| A1 | analyze-full.md | architecture/, diagrams/, explanations/, decisions/ |
| A2 | manual.md | manual/{name}/00-08 + features/ |
| A3 | user-guide.md | manual/{name}/09-user-guide.md |
| A4 | ops-design.md | manual/{name}/12-ops-design.md |
| A5 | quick-ref.md | manual/{name}/10-quick-reference.md |
| A6 | test-spec.md | manual/{name}/11-test-spec.md |
| A7 | analyze-slide.md | slides/{name}/ |

**Wait for all 7 agents to complete before proceeding to Phase A verification.**

#### Phase A Verification (main session)

Verify these files exist. Re-launch the agent for any missing file.
```
docs/architecture/{name}.md
docs/manual/{name}/00-index.md
docs/manual/{name}/03-features.md
docs/manual/{name}/09-user-guide.md
docs/manual/{name}/10-quick-reference.md
docs/manual/{name}/11-test-spec.md
docs/manual/{name}/12-ops-design.md
```

#### Phase B: Dependent Document Generation (parallel subagents)

These depend on Phase A output. Launch after Phase A verification.

| # | Command file | Depends on | Output |
|---|-------------|-----------|--------|
| B1 | manual-slide.md | A2 (manual) | slides/{name}-slidedocs/ |
| B2 | generate-ai-docs.md | A1 + A2 | {name}-llms.txt, {name}-AGENTS.md |

**Wait for all agents to complete before proceeding to Phase C.**

#### Phase C: Post-processing (main session, sequential)

Run scripts and site generation directly in the main session.

1. `python scripts/translate_diagrams.py --docs-dir ./docs --source-dir {target_path} --name {name} --in-place` (skip if no translation file)
2. `python scripts/convert_diagrams.py --docs-dir ./docs --add-external-link`
3. Follow .claude/commands/generate-site.md to generate MkDocs config
4. Generate `./docs/{name}-index.md` from `templates/index-template-en.md` and add portal link to `./docs/index.md`
5. `mkdocs build` -- Build site/ for sharing

**Steps 4 and 5 are common to all modes and must always run when any artifact is generated.**

**Progress display rule (all phases):**
Create a task with TaskCreate at the start of each phase and mark completed with TaskUpdate.
Example:
- `TaskCreate("Phase A: 7 documents parallel generation")` -> all done -> `TaskUpdate(status: completed)`
- `TaskCreate("Phase B: slides + AI docs generation")` -> all done -> `TaskUpdate(status: completed)`
- `TaskCreate("Phase C: post-processing & site build")` -> all done -> `TaskUpdate(status: completed)`
- `TaskCreate("Complete manual generation")` -> execute -> `TaskUpdate(status: completed)`

## Step 4: Save Files (except slides)

For output modes a)-d), f), h), k), l), i), after generating analysis results in `--- FILE: docs/... ---` format, automatically save files:
- Write each `--- FILE: path ---` section directly to the corresponding path under `./docs`
- Create directories automatically if they don't exist
- Strip the `docs/` prefix before joining with `./docs`

## Step 5: Generate Index (all modes, required)

Whenever any artifact is generated, always execute the following.

### 5-A. Project-specific Index File

**The index file must be saved as `./docs/{name}-index.md`. Do NOT overwrite `./docs/index.md`.**
Multiple projects coexist in `./docs`, so using `index.md` directly would overwrite previous indexes.

1. Load `templates/index-template-en.md`
2. Replace placeholders to generate `./docs/{name}-index.md`:
   - `{NAME}` -> feature/system name
   - `{DATE}` -> today's date
   - `{TARGET_PATH}` -> target path
   - `{FEATURES_TABLE}` -> table of files under `features/`
   - `{DIAGRAMS_TABLE}` -> table of {NAME}-*.mmd / .svg files under `diagrams/`
3. **Remove links to files that don't exist** (delete entire sections for ungenerated artifacts)
4. Include a "Sharing" section in the index
5. Insert freshness badge:
   ```bash
   python3 scripts/freshness_badge.py --source-dir {target_path} --name {name} --docs-dir ./docs --insert
   ```

### 5-B. Add to Portal (index.md)

If `./docs/index.md` doesn't exist, create it with this header:
```markdown
# knowledge-asset-tool Documentation Portal

> Tool: knowledge-asset-tool

---

## Projects

| Project | Description | Index |
|---------|-------------|-------|
```

If it already exists, **append a row** to the project table (don't delete existing rows).
If a row for the same project already exists, update it.

**Use marker comments for idempotency:**
```markdown
<!-- PROJECT:{name} -->
| **{name}** | {description} | [{name}-index.md]({name}-index.md) |
<!-- /PROJECT:{name} -->
```
If the same marker exists, replace that row. Otherwise, append at the end of the table.

## Step 5.5: Quality Check (all modes, required)

After artifacts are generated, automatically run quality checks:

```bash
# 1. Link integrity check -- detect broken links
python3 scripts/check_links.py --docs-dir ./docs

# 2. Terminology consistency check -- detect inconsistencies
python3 scripts/check_consistency.py --docs-dir ./docs

# 3. Slide overflow check -- detect image cutoff risk (slides only)
python3 scripts/check_slide_overflow.py --docs-dir ./docs

# 4. Auto-split diagrams -- split oversized diagrams
python3 scripts/split_diagram.py --docs-dir ./docs --name {name} --auto
```

- If errors are found, **attempt automatic fixes** (fix link targets, unify terminology, reduce Mermaid node counts)
- Re-run checks after fixes until errors reach 0 (max 3 iterations)
- Report unfixable errors in the completion report under "Unresolved quality issues"

## Step 6: Build Sharing Site (all modes, required)

If `mkdocs` is installed, run:

```bash
mkdocs build
```

This generates a self-contained HTML site in `site/`.
Share by copying the folder; recipients just open `site/index.html` in a browser.

If `mkdocs` is not installed: `pip3 install --break-system-packages mkdocs-material`

## Step 6.3: Screenshot Capture (optional)

If the application is running, offer to capture screenshots:

```
Is the application currently running? I can capture screenshots and insert them into the operations guide.

  (a) Yes -> provide the application URL (e.g., http://localhost:3000)
  (b) No -> skip
```

For (a):
1. Run `python3 scripts/capture_screenshots.py --url {URL} --output-dir ./docs/screenshots/{name}/ --pages auto`
2. Insert captured screenshots into the operations guide (09-user-guide.md):
   `![{screen_name}](../screenshots/{name}/{screen_name}.png)`

**Only execute if the user explicitly requests it. Do not auto-execute.**

## Step 6.5: Publish Docs to GitHub (optional)

After site build, inform the user:

```
Would you like to make the generated docs viewable on GitHub?

  Private repos only -- docs/ can be git pushed.
  Public repos are blocked to prevent information leakage.

  To execute: python scripts/push_docs.py
  To check:   python scripts/push_docs.py --check-only
```

**Only execute if the user explicitly requests it. Do not auto-execute.**
**push_docs.py uses `gh repo view --json visibility` internally to check privacy and auto-blocks pushes to public repos.**

## Step 7: Completion Report

When everything is done, report in this format:

```
Done.

  Output mode:  {mode}
  Output dir:   ./docs
  Generated files:
    - {filepath1}
    - {filepath2}
    ...

  Index:        ./docs/{name}-index.md
  Portal:       ./docs/index.md
  Sharing site: site/ (copy the folder to share)

  Unresolved issues: {N if any, otherwise omit}
```

After the completion report, log the generation:
```bash
python3 scripts/log_generation.py \
  --name {name} \
  --mode {selected_mode} \
  --source-dir {target_path} \
  --file-count {number_of_generated_files} \
  --duration-estimate {estimated_time}
```

## Important Rules

- Ask all Step 1 questions at once. No follow-up questions
- Do not start analysis until the user confirms with "OK"
- Do not ask for confirmation during analysis. Run everything automatically
- Report only if errors occur
- Apply instructions from the respective .claude/commands/ command files as-is
- **Step 5 (index) and Step 6 (site build) must always run for all modes**
- **Quality rule propagation for sub-agent delegation**: When delegating Step 3 analysis to Agent tool (sub-agents), always:
  1. Include `Read templates/quality-rules.md first and follow all rules` in the sub-agent prompt
  2. Include the command file path (e.g., `.claude/commands/manual.md`) and instruct `Follow the execution section of this file`
  3. Include the fact cache path `.cache/facts-{name}.yaml` and instruct `Use each entry's source field for source citations`
  4. **Never pass facts as text summaries**. Always pass file paths and let the sub-agent read them directly
