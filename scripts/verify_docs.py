#!/usr/bin/env python3
"""
verify_docs.py - 生成されたドキュメントをソースコードと照合して検証する

使い方:
  python scripts/verify_docs.py --docs-dir ./docs --source-dir /path/to/project
  python scripts/verify_docs.py --docs-dir ./docs --source-dir /path/to/project --name feature-name
"""

import argparse
import glob
import json
import os
import re
import sys

# Allow importing scan_sources from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_sources import detect_project_type


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _read_file(path):
    """Read a file and return its content, or None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _collect_md_files(docs_dir, name=None):
    """Collect markdown files under docs_dir, optionally filtered by name."""
    pattern = os.path.join(docs_dir, "**", "*.md")
    files = sorted(glob.glob(pattern, recursive=True))
    if name:
        files = [
            f for f in files
            if name in os.path.basename(f) or name in os.path.relpath(f, docs_dir)
        ]
    return files


# ---------------------------------------------------------------------------
# (A) File path reference verification
# ---------------------------------------------------------------------------

_REF_PATTERN = re.compile(
    r"(?:"
    r"\(([a-zA-Z0-9_./-]+\.\w+):(\d+(?:-\d+)?)\)"
    r"|"
    r"<!--\s*source:\s*([a-zA-Z0-9_./-]+\.\w+):(\d+(?:-\d+)?)\s*-->"
    r")"
)


def extract_file_refs(md_files):
    """Extract file path references from markdown files.

    Returns a list of (file_path, line_spec) tuples.
    """
    refs = []
    seen = set()
    for md_path in md_files:
        content = _read_file(md_path)
        if content is None:
            continue
        for m in _REF_PATTERN.finditer(content):
            file_path = m.group(1) or m.group(3)
            line_spec = m.group(2) or m.group(4)
            key = (file_path, line_spec)
            if key not in seen:
                seen.add(key)
                refs.append(key)
    return refs


def verify_file_refs(refs, source_dir):
    """Verify extracted file path references against source_dir.

    Returns (results, ok_count, fail_count, warn_count).
    Each result is (status, label, message).
    """
    results = []
    ok_count = 0
    fail_count = 0
    warn_count = 0

    for file_path, line_spec in refs:
        full = os.path.join(source_dir, file_path)
        label = f"{file_path}:{line_spec}"

        if not os.path.isfile(full):
            results.append(("FAIL", label, "ファイルが存在しない"))
            fail_count += 1
            continue

        # Count lines
        content = _read_file(full)
        if content is None:
            results.append(("FAIL", label, "ファイルを読み込めない"))
            fail_count += 1
            continue

        max_line = content.count("\n") + 1

        # Parse line spec
        parts = line_spec.split("-")
        try:
            end_line = int(parts[-1])
        except ValueError:
            results.append(("WARN", label, "行番号をパースできない"))
            warn_count += 1
            continue

        if end_line > max_line:
            results.append(
                ("WARN", label, f"行番号が範囲外 (最大: {max_line}行)")
            )
            warn_count += 1
        else:
            results.append(("OK", label, ""))
            ok_count += 1

    return results, ok_count, fail_count, warn_count


# ---------------------------------------------------------------------------
# (B) Table name verification
# ---------------------------------------------------------------------------

_SNAKE_CASE_RE = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`")
_ER_ENTITY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]+)\s*\{", re.MULTILINE)
_ER_BLOCK_RE = re.compile(r"```mermaid\s*\n\s*erDiagram(.*?)```", re.DOTALL)


def extract_table_names(md_files):
    """Extract table names from markdown files.

    Looks in:
    - Markdown table cells in テーブル名 columns
    - erDiagram blocks (entity names)
    - Backtick-quoted snake_case identifiers
    """
    tables = set()

    for md_path in md_files:
        content = _read_file(md_path)
        if content is None:
            continue

        # テーブル名 column in markdown tables
        lines = content.split("\n")
        table_col_idx = None
        in_table = False
        for line in lines:
            stripped = line.strip()
            if "|" in stripped and "テーブル名" in stripped:
                cols = [c.strip() for c in stripped.split("|")]
                for idx, col in enumerate(cols):
                    if "テーブル名" in col:
                        table_col_idx = idx
                        break
                in_table = True
                continue
            if in_table and stripped.startswith("|"):
                # Skip separator row
                if re.match(r"^\|[\s:|-]+\|$", stripped):
                    continue
                cols = [c.strip() for c in stripped.split("|")]
                if table_col_idx is not None and table_col_idx < len(cols):
                    val = cols[table_col_idx].strip("`").strip()
                    if val and not val.startswith("-"):
                        tables.add(val)
            else:
                in_table = False
                table_col_idx = None

        # erDiagram entities
        for block_match in _ER_BLOCK_RE.finditer(content):
            block = block_match.group(1)
            for entity_match in _ER_ENTITY_RE.finditer(block):
                tables.add(entity_match.group(1))
            # Also catch entities in relationships: EntityA ||--o{ EntityB
            for rel_match in re.finditer(
                r"([A-Za-z][A-Za-z0-9_]+)\s*[|}{o]+--[|}{o]+\s*([A-Za-z][A-Za-z0-9_]+)",
                block,
            ):
                tables.add(rel_match.group(1))
                tables.add(rel_match.group(2))

        # Backtick-quoted snake_case names (likely table names)
        # Only match names that look like table names (with common prefixes)
        for m in _SNAKE_CASE_RE.finditer(content):
            candidate = m.group(1)
            # Filter out obvious non-table names
            if candidate.endswith(("_id", "_at", "_by", "_to", "_on", "_dir",
                                   "_key", "_name", "_type", "_date", "_path",
                                   "_size", "_code", "_flag", "_fee", "_sale",
                                   "_cost", "_amount", "_ratio", "_price",
                                   "_total", "_count", "_time", "_status")):
                continue
            if candidate.startswith(("is_", "has_", "can_", "should_",
                                     "fk_", "idx_", "uk_")):
                continue
            # Only accept names that match common table naming patterns:
            # - Start with m_, t_, r_, s_ (master, transaction, relation, system)
            # - Or are known plural forms (ending with s/es)
            # - Or are in a テーブル名 column (already handled above)
            # - Or appear in erDiagram (already handled above)
            if re.match(r"^[mtrs]_", candidate):
                tables.add(candidate)
            elif candidate.endswith("s") and len(candidate) > 4:
                tables.add(candidate)

    return sorted(tables)


def _load_db_cache_tables(source_dir):
    """Load table names from .cache/db-*.json files."""
    tables = set()
    cache_dir = os.path.join(source_dir, ".cache")
    if not os.path.isdir(cache_dir):
        return tables
    for filename in os.listdir(cache_dir):
        if filename.startswith("db-") and filename.endswith(".json"):
            content = _read_file(os.path.join(cache_dir, filename))
            if content is None:
                continue
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            # Support both list-of-table-names and dict-with-tables key
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        tables.add(item)
                    elif isinstance(item, dict) and "name" in item:
                        tables.add(item["name"])
                    elif isinstance(item, dict) and "table" in item:
                        tables.add(item["table"])
            elif isinstance(data, dict):
                for key in ("tables", "table_names"):
                    if key in data and isinstance(data[key], list):
                        for t in data[key]:
                            if isinstance(t, str):
                                tables.add(t)
                            elif isinstance(t, dict) and "name" in t:
                                tables.add(t["name"])
    return tables


def _scan_migration_tables(source_dir):
    """Extract table names from migration/schema files."""
    tables = set()

    # Laravel migrations
    mig_dir = os.path.join(source_dir, "database", "migrations")
    if os.path.isdir(mig_dir):
        for filename in os.listdir(mig_dir):
            content = _read_file(os.path.join(mig_dir, filename))
            if content is None:
                continue
            for m in re.finditer(
                r"(?:Schema::create|Schema::table)\s*\(\s*['\"](\w+)['\"]",
                content,
            ):
                tables.add(m.group(1))

    # Prisma schema
    prisma_path = os.path.join(source_dir, "prisma", "schema.prisma")
    if os.path.isfile(prisma_path):
        content = _read_file(prisma_path)
        if content:
            for m in re.finditer(r'@@map\s*\(\s*"(\w+)"\s*\)', content):
                tables.add(m.group(1))
            for m in re.finditer(r"model\s+(\w+)\s*\{", content):
                tables.add(m.group(1))

    return tables


def _scan_model_tables(source_dir, project_type):
    """Extract table names from model files."""
    tables = set()
    types = project_type.split("+")

    if "laravel" in types:
        models_dir = os.path.join(source_dir, "app", "Models")
        if os.path.isdir(models_dir):
            for filename in os.listdir(models_dir):
                if not filename.endswith(".php"):
                    continue
                content = _read_file(os.path.join(models_dir, filename))
                if content is None:
                    continue
                m = re.search(
                    r"\$table\s*=\s*['\"](\w+)['\"]", content
                )
                if m:
                    tables.add(m.group(1))

    return tables


def verify_table_names(table_names, source_dir, project_type):
    """Verify extracted table names against source artifacts.

    Returns (results, ok_count, fail_count).
    """
    known = set()
    known.update(_load_db_cache_tables(source_dir))
    known.update(_scan_migration_tables(source_dir))
    known.update(_scan_model_tables(source_dir, project_type))

    if not known:
        # Cannot verify - treat all as warnings
        return (
            [("WARN", ", ".join(table_names), "照合先のテーブル情報が見つからない")]
            if table_names
            else [],
            0,
            0,
        )

    ok_names = []
    fail_names = []
    for name in table_names:
        if name in known:
            ok_names.append(name)
        else:
            fail_names.append(name)

    results = []
    if ok_names:
        results.append(("OK", ", ".join(ok_names), ""))
    for name in fail_names:
        results.append(("FAIL", name, "ソースに見つからない"))

    return results, len(ok_names), len(fail_names)


# ---------------------------------------------------------------------------
# (C) Endpoint verification
# ---------------------------------------------------------------------------

_ENDPOINT_PATTERN = re.compile(
    r"(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s|)`]+)"
)


def extract_endpoints(md_files):
    """Extract API endpoints from markdown files.

    Returns a list of (method, path) tuples.
    """
    endpoints = []
    seen = set()

    for md_path in md_files:
        content = _read_file(md_path)
        if content is None:
            continue

        # Standard pattern: METHOD /path
        for m in _ENDPOINT_PATTERN.finditer(content):
            key = (m.group(1), m.group(2))
            if key not in seen:
                seen.add(key)
                endpoints.append(key)

        # Markdown tables with メソッド and パス columns
        lines = content.split("\n")
        method_idx = None
        path_idx = None
        in_table = False
        for line in lines:
            stripped = line.strip()
            if "|" in stripped and "メソッド" in stripped and "パス" in stripped:
                cols = [c.strip() for c in stripped.split("|")]
                for idx, col in enumerate(cols):
                    if "メソッド" in col:
                        method_idx = idx
                    if "パス" in col:
                        path_idx = idx
                in_table = True
                continue
            if in_table and stripped.startswith("|"):
                if re.match(r"^\|[\s:|-]+\|$", stripped):
                    continue
                cols = [c.strip() for c in stripped.split("|")]
                if (
                    method_idx is not None
                    and path_idx is not None
                    and method_idx < len(cols)
                    and path_idx < len(cols)
                ):
                    method = cols[method_idx].strip("`").strip().upper()
                    path = cols[path_idx].strip("`").strip()
                    if method in ("GET", "POST", "PUT", "PATCH", "DELETE") and path.startswith("/"):
                        key = (method, path)
                        if key not in seen:
                            seen.add(key)
                            endpoints.append(key)
            else:
                in_table = False
                method_idx = None
                path_idx = None

    return endpoints


def _resolve_laravel_prefixes(content, base_prefix):
    """Build a list of (start_pos, end_pos, prefix) from Route::group calls.

    This is a simplified parser that tracks nested Route::group prefix values
    and their approximate position ranges in the file.
    """
    entries = []
    # Find all prefix definitions
    for m in re.finditer(
        r"['\"]prefix['\"][\s]*=>[\s]*['\"]([^'\"]*)['\"]",
        content,
    ):
        prefix_val = m.group(1).strip("/")
        pos = m.start()

        # Find the matching function() { ... } block after this prefix
        # Look for the next 'function' keyword after the prefix
        func_match = re.search(r"function\s*\(\s*\)\s*\{", content[pos:])
        if not func_match:
            continue
        block_start = pos + func_match.end()

        # Find matching closing brace (simple brace counting)
        depth = 1
        i = block_start
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        block_end = i

        entries.append((block_start, block_end, prefix_val))

    # Sort by start position
    entries.sort(key=lambda e: e[0])

    # Also store base_prefix for the entire file
    entries.insert(0, (0, len(content), base_prefix.strip("/")))

    return entries


def _find_prefix_at(prefix_entries, pos):
    """Find the full prefix path that applies at a given position in the file.

    Walks through all prefix entries and builds the prefix stack for nested groups.
    """
    parts = []
    for start, end, prefix in prefix_entries:
        if start <= pos < end and prefix:
            parts.append(prefix)
    return "/".join(parts)


def _collect_source_routes(source_dir, project_type):
    """Collect route definitions from the source project.

    Returns a set of (method, path) tuples. Paths use {param} for variables.
    """
    routes = set()
    types = project_type.split("+")

    # Laravel — resolve nested Route::group prefixes
    if "laravel" in types:
        for route_file in ("routes/api.php", "routes/web.php"):
            full = os.path.join(source_dir, route_file)
            content = _read_file(full)
            if content is None:
                continue

            # Determine base prefix (api.php typically has /api)
            base_prefix = "/api" if "api.php" in route_file else ""

            # Extract all prefix definitions and route calls with positions
            # to build a rough prefix stack
            prefixes = _resolve_laravel_prefixes(content, base_prefix)

            for m in re.finditer(
                r"Route::(get|post|put|patch|delete|any)\s*\(\s*['\"]([^'\"]*)['\"]",
                content,
                re.IGNORECASE,
            ):
                method = m.group(1).upper()
                route_path = m.group(2).strip("/")
                # Find applicable prefix based on position in file
                prefix = _find_prefix_at(prefixes, m.start())
                full_path = prefix + ("/" + route_path if route_path else "")
                full_path = "/" + full_path.strip("/") if full_path else "/"

                if method == "ANY":
                    for mtd in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                        routes.add((mtd, full_path))
                else:
                    routes.add((method, full_path))

    # Express
    if "express" in types:
        for dirpath, _dirnames, filenames in os.walk(source_dir):
            rel = os.path.relpath(dirpath, source_dir)
            if any(ex in rel.split(os.sep) for ex in ("node_modules", ".git", "dist", "build")):
                continue
            for filename in filenames:
                if not filename.endswith((".js", ".ts")):
                    continue
                content = _read_file(os.path.join(dirpath, filename))
                if content is None:
                    continue
                for m in re.finditer(
                    r"(?:router|app)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
                    content,
                    re.IGNORECASE,
                ):
                    routes.add((m.group(1).upper(), m.group(2)))

    # Next.js
    if "nextjs" in types:
        app_dir = os.path.join(source_dir, "app")
        if os.path.isdir(app_dir):
            for dirpath, _dirnames, filenames in os.walk(app_dir):
                for filename in filenames:
                    if filename.startswith("route."):
                        rel = os.path.relpath(dirpath, app_dir)
                        path = "/" + rel.replace("\\", "/").replace("[", "{").replace("]", "}")
                        content = _read_file(os.path.join(dirpath, filename))
                        if content:
                            for m in re.finditer(
                                r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)",
                                content,
                            ):
                                routes.add((m.group(1), path))

    # Nuxt
    if "nuxt" in types:
        api_dir = os.path.join(source_dir, "server", "api")
        if os.path.isdir(api_dir):
            for dirpath, _dirnames, filenames in os.walk(api_dir):
                for filename in filenames:
                    if not filename.endswith((".ts", ".js")):
                        continue
                    rel = os.path.relpath(
                        os.path.join(dirpath, filename), api_dir
                    )
                    # Remove extension
                    rel_no_ext = os.path.splitext(rel)[0]
                    path = "/api/" + rel_no_ext.replace("\\", "/").replace("[", "{").replace("]", "}")
                    # Nuxt uses defineEventHandler, method often from filename suffix
                    name_lower = filename.lower()
                    if ".get." in name_lower:
                        routes.add(("GET", path))
                    elif ".post." in name_lower:
                        routes.add(("POST", path))
                    elif ".put." in name_lower:
                        routes.add(("PUT", path))
                    elif ".patch." in name_lower:
                        routes.add(("PATCH", path))
                    elif ".delete." in name_lower:
                        routes.add(("DELETE", path))
                    else:
                        # Default handler responds to all methods
                        for mtd in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                            routes.add((mtd, path))

    return routes


def _normalize_route(path):
    """Normalize route path for comparison.

    Strips query parameters and replaces route parameters like {id}, :id, [id]
    with a common placeholder.
    """
    # Remove query string
    path = path.split("?")[0]
    path = re.sub(r"\{[^}]+\}", "{_}", path)
    path = re.sub(r":\w+", "{_}", path)
    path = re.sub(r"\[[^\]]+\]", "{_}", path)
    return path.rstrip("/") or "/"


def verify_endpoints(endpoints, source_dir, project_type):
    """Verify extracted endpoints against source routes.

    Returns (results, ok_count, fail_count).
    """
    source_routes = _collect_source_routes(source_dir, project_type)

    if not source_routes:
        return (
            [("WARN", "全エンドポイント", "ルーティング定義が見つからない (検出精度低)")]
            if endpoints
            else [],
            0,
            0,
        )

    # Build normalized lookup
    normalized_routes = set()
    for method, path in source_routes:
        normalized_routes.add((method, _normalize_route(path)))

    ok_names = []
    fail_names = []
    for method, path in endpoints:
        norm = (method, _normalize_route(path))
        if norm in normalized_routes:
            ok_names.append(f"{method} {path}")
        else:
            fail_names.append(f"{method} {path}")

    results = []
    if ok_names:
        results.append(("OK", ", ".join(ok_names), ""))
    for name in fail_names:
        results.append(
            ("WARN", name, "ルーティングに見つからない (検出精度低)")
        )

    return results, len(ok_names), len(fail_names)


# ---------------------------------------------------------------------------
# (D) Module validity check — cross-check docs against facts cache
# ---------------------------------------------------------------------------

def _load_disabled_modules(docs_dir, name):
    """Load disabled_modules list from facts cache."""
    cache_dir = os.path.join(os.path.dirname(docs_dir), ".cache")
    if not name:
        return []
    facts_path = os.path.join(cache_dir, f"facts-{name}.yaml")
    if not os.path.isfile(facts_path):
        return []
    try:
        import yaml
        with open(facts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return []
        disabled = data.get("facts", data).get("disabled_modules", [])
        return [m.get("name", "") for m in disabled if isinstance(m, dict) and m.get("name")]
    except Exception as e:
        print(f"[WARN] Failed to load {facts_path}: {e}")
        return []


def _extract_feature_names(md_files):
    """Extract feature/module names from Tier classification tables in docs."""
    feature_names = []
    tier_pattern = re.compile(r"Tier\s*[123]", re.IGNORECASE)
    # Match table rows like: | ModuleName | description | ...
    row_pattern = re.compile(r"^\|\s*([^|]+?)\s*\|", re.MULTILINE)
    for path in md_files:
        content = _read_file(path)
        if not content:
            continue
        # Split into sections, only look at sections mentioning Tier
        sections = re.split(r"^#{1,4}\s+", content, flags=re.MULTILINE)
        for section in sections:
            if not tier_pattern.search(section):
                continue
            for match in row_pattern.finditer(section):
                name = match.group(1).strip()
                # Skip header separators and common header labels
                if name.startswith("-") or name.startswith(":"):
                    continue
                if name.lower() in ("機能名", "モジュール名", "feature", "module", "名前", "name"):
                    continue
                if name:
                    feature_names.append(name)
    return feature_names


def verify_module_validity(md_files, docs_dir, name):
    """Check if disabled modules appear in feature/Tier listings.

    Returns (results, ok_count, fail_count).
    """
    disabled = _load_disabled_modules(docs_dir, name)
    if not disabled:
        return [], 0, 0

    feature_names = _extract_feature_names(md_files)
    if not feature_names:
        return [("WARN", "Tier分類", "Tier分類テーブルが見つからない")], 0, 0

    ok_names = []
    fail_names = []
    for mod in disabled:
        # Check if disabled module appears in feature listings
        found = any(mod.lower() in feat.lower() for feat in feature_names)
        if found:
            fail_names.append(mod)
        else:
            ok_names.append(mod)

    results = []
    for mod in ok_names:
        results.append(("OK", mod, "Tier分類に含まれていない（正常）"))
    for mod in fail_names:
        results.append(
            ("FAIL", mod, "disabled_modules だが Tier分類に含まれている")
        )

    return results, len(ok_names), len(fail_names)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _print_section(title, results, total_label):
    """Print a verification section."""
    total = sum(1 for r in results if r[0] != "WARN" or r[0] == "WARN")
    print(f"\n\u2501\u2501 {title} \u2501\u2501 ({total}件)")
    for status, label, msg in results:
        if status == "OK":
            print(f"  [OK] {label}")
        elif status == "FAIL":
            print(f"  [FAIL] {label} \u2014 {msg}")
        elif status == "WARN":
            print(f"  [WARN] {label} \u2014 {msg}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="生成されたドキュメントをソースコードと照合して検証する"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="検証対象のドキュメントディレクトリ",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="照合先のソースコードディレクトリ",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="機能名でドキュメントをフィルタ (省略時は全ファイル検証)",
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)
    source_dir = os.path.abspath(args.source_dir) if args.source_dir else None

    if not os.path.isdir(docs_dir):
        print(f"[ERROR] ドキュメントディレクトリが見つかりません: {docs_dir}", file=sys.stderr)
        sys.exit(2)

    if source_dir and not os.path.isdir(source_dir):
        print(f"[ERROR] ソースディレクトリが見つかりません: {source_dir}", file=sys.stderr)
        sys.exit(2)

    source_label = source_dir if source_dir else "(未指定)"
    print(f"[INFO] 検証対象: {docs_dir} (source: {source_label})")

    md_files = _collect_md_files(docs_dir, args.name)
    if not md_files:
        print("[WARN] 対象のMarkdownファイルが見つかりません")
        sys.exit(0)

    total_ok = 0
    total_fail = 0
    total_warn = 0
    section_summaries = []

    # --- (A) File path references ---
    refs = extract_file_refs(md_files)
    if refs and source_dir:
        results_a, ok_a, fail_a, warn_a = verify_file_refs(refs, source_dir)
        _print_section("ファイルパス引用", results_a, f"{len(refs)}件")
        total_ok += ok_a
        total_fail += fail_a
        total_warn += warn_a
        section_summaries.append(
            f"  ファイルパス: {ok_a}/{ok_a + fail_a + warn_a} OK"
            + (f" ({fail_a} FAIL)" if fail_a else "")
            + (f" ({warn_a} WARN)" if warn_a else "")
        )
    elif refs and not source_dir:
        print("\n\u2501\u2501 ファイルパス引用 \u2501\u2501")
        print("  [WARN] --source-dir 未指定のためスキップ")

    # --- (B) Table names ---
    project_type = None
    table_names = extract_table_names(md_files)
    if table_names and source_dir:
        project_type = detect_project_type(source_dir)
        results_b, ok_b, fail_b = verify_table_names(
            table_names, source_dir, project_type
        )
        _print_section("テーブル名", results_b, f"{len(table_names)}件")
        total_ok += ok_b
        total_fail += fail_b
        section_summaries.append(
            f"  テーブル名:  {ok_b}/{ok_b + fail_b} OK"
            + (f" ({fail_b} FAIL)" if fail_b else "")
        )
    elif table_names and not source_dir:
        print("\n\u2501\u2501 テーブル名 \u2501\u2501")
        print("  [WARN] --source-dir 未指定のためスキップ")

    # --- (C) Endpoints ---
    endpoints = extract_endpoints(md_files)
    if endpoints and source_dir:
        if not table_names:
            project_type = detect_project_type(source_dir)
        results_c, ok_c, fail_c = verify_endpoints(
            endpoints, source_dir, project_type
        )
        _print_section("エンドポイント", results_c, f"{len(endpoints)}件")
        total_ok += ok_c
        total_fail += fail_c
        section_summaries.append(
            f"  エンドポイント: {ok_c}/{ok_c + fail_c} OK"
            + (f" ({fail_c} FAIL)" if fail_c else "")
        )
    elif endpoints and not source_dir:
        print("\n\u2501\u2501 エンドポイント \u2501\u2501")
        print("  [WARN] --source-dir 未指定のためスキップ")

    # --- (D) Module validity ---
    if args.name:
        results_d, ok_d, fail_d = verify_module_validity(
            md_files, docs_dir, args.name
        )
        if results_d:
            _print_section("モジュール有効性", results_d, f"{ok_d + fail_d}件")
            total_ok += ok_d
            total_fail += fail_d
            section_summaries.append(
                f"  モジュール有効性: {ok_d}/{ok_d + fail_d} OK"
                + (f" ({fail_d} FAIL)" if fail_d else "")
            )

    # --- Summary ---
    grand_total = total_ok + total_fail
    print(f"\n\u2501\u2501 サマリー \u2501\u2501")
    for line in section_summaries:
        print(line)
    if section_summaries:
        print(
            f"  総合: {total_ok}/{grand_total} OK"
            + (f" ({total_fail} FAIL)" if total_fail else "")
        )

    if not refs and not table_names and not endpoints:
        print("  検証対象の参照が見つかりませんでした")

    if total_fail > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
