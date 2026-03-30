#!/usr/bin/env python3
"""Live database introspection via user-specified SQL execution command.

Library module used by scan_database.py. Not intended to be run directly.

Executes SQL queries against a live database by piping them to the caller's
preferred client command (mysql, psql, docker exec, kubectl exec, etc.).

SECURITY MODEL:
  - The sql_command is executed as a shell command. This is by design —
    the caller provides this command via the sql_command parameter.
  - SQL queries are passed via stdin (not shell interpolation), so they
    are not subject to shell injection.
  - All table/column names from information_schema are validated against
    a safe identifier pattern before use in dynamic queries.
  - This tool must only be run locally by trusted users.
"""

import re
import subprocess
import sys
from typing import Any

# Safe SQL identifier pattern: letters, digits, underscores only
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

# Limits for sample queries
SAMPLE_LABEL_LIMIT = 20
SETTINGS_VALUE_LIMIT = 100

# Columns that typically indicate active/inactive status
ACTIVE_FLAG_COLUMNS = {
    "is_active", "is_enabled", "is_deleted", "active", "enabled",
    "disabled", "deleted", "status", "deleted_at", "deactivated_at",
    "archived", "is_archived", "is_visible", "visible", "hidden", "is_hidden",
}

# Columns that typically contain labels/display names
LABEL_COLUMNS = {
    "name", "label", "title", "display_name", "display_title",
    "description", "caption", "heading", "text", "value",
}

# Tables that typically store settings/configuration
SETTINGS_TABLE_PATTERNS = [
    r"settings?$", r"configs?$", r"configurations?$", r"options?$",
    r"feature_flags?$", r"parameters?$", r"preferences?$",
    r"system_settings?$", r"app_settings?$",
]

# SQL queries for schema introspection
INTROSPECTION_QUERIES: dict[str, dict[str, str]] = {
    "mysql": {
        "tables": (
            "SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS, TABLE_COMMENT "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME"
        ),
        "columns": (
            "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, "
            "COLUMN_DEFAULT, COLUMN_KEY, COLUMN_COMMENT, EXTRA "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        ),
        "foreign_keys": (
            "SELECT TABLE_NAME, COLUMN_NAME, "
            "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, CONSTRAINT_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND REFERENCED_TABLE_NAME IS NOT NULL "
            "ORDER BY TABLE_NAME, COLUMN_NAME"
        ),
        "indexes": (
            "SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX"
        ),
    },
    "postgresql": {
        "tables": (
            "SELECT table_name, table_type, "
            "NULL AS table_rows, NULL AS table_comment "
            "FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name"
        ),
        "columns": (
            "SELECT table_name, column_name, data_type AS column_type, "
            "is_nullable, column_default, "
            "NULL AS column_key, NULL AS column_comment, NULL AS extra "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        ),
        "foreign_keys": (
            "SELECT tc.table_name, kcu.column_name, "
            "ccu.table_name AS referenced_table_name, "
            "ccu.column_name AS referenced_column_name, "
            "tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "ON ccu.constraint_name = tc.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "AND tc.table_schema = 'public' "
            "ORDER BY tc.table_name, kcu.column_name"
        ),
        "indexes": (
            "SELECT t.relname AS table_name, i.relname AS index_name, "
            "a.attname AS column_name, "
            "CASE WHEN ix.indisunique THEN 0 ELSE 1 END AS non_unique "
            "FROM pg_index ix "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid "
            "AND a.attnum = ANY(ix.indkey) "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE n.nspname = 'public' "
            "ORDER BY t.relname, i.relname"
        ),
    },
}


def _is_safe_identifier(name: str) -> bool:
    """Check if a name is a safe SQL identifier."""
    return bool(_SAFE_IDENTIFIER.match(name))


def _quote_identifier(name: str, db_type: str) -> str:
    """Quote a SQL identifier with backticks (MySQL) or double quotes (PostgreSQL)."""
    if db_type == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def execute_sql(sql_command: str, query: str, timeout: int = 30) -> str:
    """Execute a SQL query via the user-specified command.

    SECURITY NOTE: sql_command is executed as a shell command. This is by design —
    the user provides this command themselves via --sql-command. The SQL query is
    passed via stdin (not shell interpolation), so it is not subject to shell
    injection. This tool must only be run locally by trusted users.

    Args:
        sql_command: Shell command to execute SQL (e.g., "mysql -u root mydb")
        query: SQL query to execute
        timeout: Timeout in seconds (default: 30)
    """
    try:
        result = subprocess.run(
            sql_command,
            input=query,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
        )
        if result.returncode != 0:
            print(
                f"SQL execution warning: {result.stderr.strip()}",
                file=sys.stderr,
            )
        return result.stdout
    except subprocess.TimeoutExpired:
        print(
            f"SQL execution timed out after {timeout}s",
            file=sys.stderr,
        )
        return ""
    except OSError as e:
        print(f"SQL execution error: {e}", file=sys.stderr)
        return ""


def parse_tsv_output(output: str) -> list[dict[str, str]]:
    """Parse tab-separated output from mysql/psql CLI into list of dicts.

    Assumes first line is header row.
    """
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return []

    headers = [h.strip().lower() for h in lines[0].split("\t")]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        row = {}
        for i, header in enumerate(headers):
            row[header] = values[i].strip() if i < len(values) else ""
        rows.append(row)
    return rows


def _safe_int(value: str | None) -> int | None:
    """Safely convert a string to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _group_by_table(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Group rows by table_name key."""
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        tname = row.get("table_name", "")
        if tname not in grouped:
            grouped[tname] = []
        grouped[tname].append(row)
    return grouped


def _build_table_entry(
    table_name: str,
    trow: dict[str, str],
    columns_by_table: dict[str, list[dict[str, str]]],
    fks_by_table: dict[str, list[dict[str, str]]],
    idxs_by_table: dict[str, list[dict[str, str]]],
    classify_table_fn: Any,
) -> dict[str, Any]:
    """Build a single table's schema entry from introspection data."""
    columns: list[dict[str, Any]] = []
    has_active_flag = False
    active_flag_columns: list[str] = []
    label_columns_found: list[str] = []
    primary_key: list[str] = []

    for col in columns_by_table.get(table_name, []):
        col_name = col.get("column_name", "")
        col_type = col.get("column_type", "")
        nullable = col.get("is_nullable", "YES").upper() == "YES"
        default = col.get("column_default")
        if default == "NULL" or default == "None":
            default = None

        columns.append({
            "name": col_name,
            "type": col_type,
            "nullable": nullable,
            "default": default,
        })

        if col.get("column_key", "").upper() == "PRI":
            primary_key.append(col_name)

        if col_name.lower() in ACTIVE_FLAG_COLUMNS:
            has_active_flag = True
            active_flag_columns.append(col_name)

        if col_name.lower() in LABEL_COLUMNS:
            label_columns_found.append(col_name)

    # Parse foreign keys
    foreign_keys = [
        {
            "column": fk.get("column_name", ""),
            "references_table": fk.get("referenced_table_name", ""),
            "references_column": fk.get("referenced_column_name", ""),
        }
        for fk in fks_by_table.get(table_name, [])
    ]

    # Parse indexes
    idx_groups: dict[str, dict[str, Any]] = {}
    for idx in idxs_by_table.get(table_name, []):
        idx_name = idx.get("index_name", "")
        if idx_name not in idx_groups:
            idx_groups[idx_name] = {
                "name": idx_name,
                "columns": [],
                "unique": idx.get("non_unique", "1") == "0",
            }
        idx_groups[idx_name]["columns"].append(idx.get("column_name", ""))
    indexes = list(idx_groups.values())

    is_settings_table = any(
        re.search(p, table_name, re.IGNORECASE)
        for p in SETTINGS_TABLE_PATTERNS
    )
    table_type = classify_table_fn(
        table_name, columns, foreign_keys, has_active_flag
    )

    row_count_str = trow.get("table_rows", "")
    row_count = int(row_count_str) if row_count_str and row_count_str.isdigit() else None

    return {
        "columns": columns,
        "primary_key": primary_key,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "table_type": table_type,
        "has_active_flag": has_active_flag,
        "active_flag_columns": active_flag_columns,
        "label_columns": label_columns_found,
        "is_settings_table": is_settings_table,
        "row_count": row_count,
        "table_comment": trow.get("table_comment", ""),
    }


def _enrich_active_counts(
    table_name: str,
    table_info: dict[str, Any],
    sql_command: str,
    db_type: str,
    timeout: int,
) -> dict[str, Any]:
    """Get active/inactive counts for a table. Returns enrichment dict."""
    if not table_info["has_active_flag"]:
        return {}

    for flag_col in table_info["active_flag_columns"]:
        if not _is_safe_identifier(flag_col):
            continue

        if flag_col.lower() in ("deleted_at", "deactivated_at"):
            condition = "IS NULL"
        elif flag_col.lower() in ("is_deleted", "disabled", "is_archived", "hidden", "is_hidden"):
            condition = "= 0"
        else:
            condition = "= 1"

        quoted_table = _quote_identifier(table_name, db_type)
        quoted_col = _quote_identifier(flag_col, db_type)
        count_query = (
            f"SELECT '{table_name}' AS table_name, "
            f"COUNT(*) AS total, "
            f"SUM(CASE WHEN {quoted_col} {condition} THEN 1 ELSE 0 END) AS active, "
            f"SUM(CASE WHEN NOT ({quoted_col} {condition}) THEN 1 ELSE 0 END) AS inactive "
            f"FROM {quoted_table}"
        )
        count_output = execute_sql(sql_command, count_query, timeout)
        count_rows = parse_tsv_output(count_output)
        if count_rows:
            row = count_rows[0]
            return {
                "active_count": _safe_int(row.get("active")),
                "inactive_count": _safe_int(row.get("inactive")),
                "total_count": _safe_int(row.get("total")),
            }
    return {}


def _enrich_sample_labels(
    table_name: str,
    table_info: dict[str, Any],
    sql_command: str,
    db_type: str,
    timeout: int,
) -> dict[str, Any]:
    """Get sample labels from a table. Returns enrichment dict."""
    if not table_info["label_columns"]:
        return {}

    safe_cols = [c for c in table_info["label_columns"][:3] if _is_safe_identifier(c)]
    if not safe_cols:
        return {}

    cols = ", ".join(_quote_identifier(c, db_type) for c in safe_cols)
    quoted_table = _quote_identifier(table_name, db_type)
    label_query = f"SELECT {cols} FROM {quoted_table} LIMIT {SAMPLE_LABEL_LIMIT}"
    label_output = execute_sql(sql_command, label_query, timeout)
    label_rows = parse_tsv_output(label_output)
    if label_rows:
        return {"sample_labels": label_rows[:SAMPLE_LABEL_LIMIT]}
    return {}


def _enrich_settings_values(
    table_name: str,
    table_info: dict[str, Any],
    sql_command: str,
    db_type: str,
    timeout: int,
) -> dict[str, Any]:
    """Get settings values from a table. Returns enrichment dict."""
    if not table_info["is_settings_table"]:
        return {}

    quoted_table = _quote_identifier(table_name, db_type)
    settings_query = f"SELECT * FROM {quoted_table} LIMIT {SETTINGS_VALUE_LIMIT}"
    settings_output = execute_sql(sql_command, settings_query, timeout)
    settings_rows = parse_tsv_output(settings_output)
    if settings_rows:
        return {"settings_values": settings_rows}
    return {}


def introspect_live_db(
    sql_command: str,
    db_type: str = "mysql",
    timeout: int = 30,
    classify_table_fn: Any = None,
) -> dict[str, Any]:
    """Introspect a live database using user-specified SQL execution command.

    Args:
        sql_command: Shell command to pipe SQL into (e.g., "mysql -u root -N mydb")
        db_type: Database type ("mysql" or "postgresql")
        timeout: Query timeout in seconds
        classify_table_fn: Function to classify tables (from scan_database module)

    Returns:
        Schema dict compatible with parse_sql_dump output format.
    """
    queries = INTROSPECTION_QUERIES.get(db_type)
    if not queries:
        print(f"Unsupported DB type for live introspection: {db_type}", file=sys.stderr)
        return {"tables": {}, "table_count": 0}

    # Step 1: Get table list
    table_output = execute_sql(sql_command, queries["tables"], timeout)
    table_rows = parse_tsv_output(table_output)

    if not table_rows:
        print("No tables found or unable to query database.", file=sys.stderr)
        return {"tables": {}, "table_count": 0}

    # Step 2-4: Get columns, foreign keys, indexes
    column_rows = parse_tsv_output(execute_sql(sql_command, queries["columns"], timeout))
    fk_rows = parse_tsv_output(execute_sql(sql_command, queries["foreign_keys"], timeout))
    idx_rows = parse_tsv_output(execute_sql(sql_command, queries["indexes"], timeout))

    columns_by_table = _group_by_table(column_rows)
    fks_by_table = _group_by_table(fk_rows)
    idxs_by_table = _group_by_table(idx_rows)

    # Build base table entries (only for safe identifiers)
    tables: dict[str, dict[str, Any]] = {}
    for trow in table_rows:
        table_name = trow.get("table_name", "")
        if not table_name or not _is_safe_identifier(table_name):
            continue

        tables[table_name] = _build_table_entry(
            table_name, trow,
            columns_by_table, fks_by_table, idxs_by_table,
            classify_table_fn,
        )

    # Step 5-7: Enrich with active counts, labels, settings (immutable merge)
    enriched_tables: dict[str, dict[str, Any]] = {}
    for table_name, table_info in tables.items():
        enriched_tables[table_name] = {
            **table_info,
            **_enrich_active_counts(table_name, table_info, sql_command, db_type, timeout),
            **_enrich_sample_labels(table_name, table_info, sql_command, db_type, timeout),
            **_enrich_settings_values(table_name, table_info, sql_command, db_type, timeout),
        }

    return {
        "tables": enriched_tables,
        "table_count": len(enriched_tables),
        "source": "live_db",
    }
