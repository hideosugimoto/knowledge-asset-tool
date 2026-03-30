#!/usr/bin/env python3
"""Scan a project to detect database connections and extract schema information.

Supports multiple modes:
  1. Live DB via user-specified command (--sql-command) — highest accuracy
  2. SQL dump file (--dump-file) — no DB connection needed
  3. Migration files only (--migrations-dir) — schema structure only
  4. Auto-detect from project (--source-dir) — detects configs and migrations

Outputs a JSON manifest of database schema, master data status, labels,
and settings for use in knowledge asset generation.

Usage:
    # Live DB: pipe SQL to your preferred client
    python3 scripts/scan_database.py --sql-command "mysql -u root -N mydb"
    python3 scripts/scan_database.py --sql-command "docker exec -i db mysql -u root mydb"
    python3 scripts/scan_database.py --sql-command "psql -U postgres -t mydb" --db-type postgresql

    # SQL dump analysis (no DB connection needed)
    python3 scripts/scan_database.py --dump-file schema.sql

    # Auto-detect DB config from project
    python3 scripts/scan_database.py --source-dir /path/to/project

    # Migration files only
    python3 scripts/scan_database.py --migrations-dir /path/to/migrations
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# DB config detection patterns
# ---------------------------------------------------------------------------

# Patterns for .env files
ENV_DB_PATTERNS = {
    "host": re.compile(r"^DB_HOST\s*=\s*(.+)$", re.MULTILINE),
    "port": re.compile(r"^DB_PORT\s*=\s*(.+)$", re.MULTILINE),
    "database": re.compile(r"^DB_DATABASE\s*=\s*(.+)$", re.MULTILINE),
    "username": re.compile(r"^DB_USERNAME\s*=\s*(.+)$", re.MULTILINE),
    "password": re.compile(r"^DB_PASSWORD\s*=\s*(.+)$", re.MULTILINE),
    "driver": re.compile(r"^DB_CONNECTION\s*=\s*(.+)$", re.MULTILINE),
}

# Files to search for DB configuration
DB_CONFIG_FILES = [
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    "config/database.php",
    "config/database.yml",
    "config/database.yaml",
    "knexfile.js",
    "knexfile.ts",
    "prisma/schema.prisma",
    "drizzle.config.ts",
    "drizzle.config.js",
    "typeorm.config.ts",
    "ormconfig.json",
    "ormconfig.ts",
    "sequelize.config.js",
    "config/config.json",
    "database.yml",
    "alembic.ini",
    "sqlalchemy.url",
    "settings.py",
    "config/settings.py",
    "config/application.yml",
    "src/main/resources/application.properties",
    "src/main/resources/application.yml",
]

# Migration directory patterns
MIGRATION_DIR_PATTERNS = [
    "database/migrations",
    "migrations",
    "db/migrate",
    "db/migrations",
    "alembic/versions",
    "src/migrations",
    "prisma/migrations",
    "drizzle/migrations",
    "knex/migrations",
    "typeorm/migrations",
]

# Patterns to detect active/inactive flags in SQL
ACTIVE_FLAG_COLUMNS = [
    "is_active",
    "is_enabled",
    "is_deleted",
    "active",
    "enabled",
    "disabled",
    "deleted",
    "status",
    "deleted_at",
    "deactivated_at",
    "archived",
    "is_archived",
    "is_visible",
    "visible",
    "hidden",
    "is_hidden",
]

# Columns that typically contain labels/display names
LABEL_COLUMNS = [
    "name",
    "label",
    "title",
    "display_name",
    "display_title",
    "description",
    "caption",
    "heading",
    "text",
    "value",
]

# Tables that typically store settings/configuration
SETTINGS_TABLE_PATTERNS = [
    r"settings?$",
    r"configs?$",
    r"configurations?$",
    r"options?$",
    r"feature_flags?$",
    r"parameters?$",
    r"preferences?$",
    r"system_settings?$",
    r"app_settings?$",
]


def detect_db_configs(source_dir: str) -> list[dict[str, Any]]:
    """Detect database connection configurations from project files.

    Returns a list of detected DB configurations with their source file.
    """
    root = Path(source_dir)
    configs: list[dict[str, Any]] = []

    for config_file in DB_CONFIG_FILES:
        filepath = root / config_file
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if config_file.startswith(".env"):
            config = _parse_env_db_config(content, str(filepath))
            if config:
                configs.append(config)

        elif config_file == "prisma/schema.prisma":
            config = _parse_prisma_config(content, str(filepath))
            if config:
                configs.append(config)

        elif config_file.endswith(".properties"):
            config = _parse_properties_config(content, str(filepath))
            if config:
                configs.append(config)

        elif config_file == "settings.py" or config_file == "config/settings.py":
            parsed_configs = _parse_django_config(content, str(filepath))
            configs.extend(parsed_configs)

    return configs


def _parse_env_db_config(content: str, source_file: str) -> dict[str, Any] | None:
    """Parse DB configuration from .env file content."""
    result: dict[str, Any] = {"source_file": source_file}
    found = False

    for key, pattern in ENV_DB_PATTERNS.items():
        match = pattern.search(content)
        if match:
            value = match.group(1).strip().strip("\"'")
            if key == "password":
                result["has_password"] = bool(value)
            else:
                result[key] = value
            found = True

    if not found:
        return None

    # Normalize driver name
    driver = result.get("driver", "")
    result["type"] = _normalize_driver(driver)

    return result


def _parse_prisma_config(content: str, source_file: str) -> dict[str, Any] | None:
    """Parse DB configuration from Prisma schema file."""
    provider_match = re.search(r'provider\s*=\s*"(\w+)"', content)
    url_match = re.search(r'url\s*=\s*env\("(\w+)"\)', content)

    if not provider_match:
        return None

    provider = provider_match.group(1)
    env_var = url_match.group(1) if url_match else "DATABASE_URL"

    return {
        "source_file": source_file,
        "type": _normalize_driver(provider),
        "driver": provider,
        "connection_env_var": env_var,
    }


def _parse_properties_config(
    content: str, source_file: str
) -> dict[str, Any] | None:
    """Parse DB config from Java .properties file."""
    url_match = re.search(
        r"spring\.datasource\.url\s*=\s*(.+)", content
    )
    if not url_match:
        return None

    url = url_match.group(1).strip()
    driver_match = re.search(r"jdbc:(\w+):", url)
    db_type = _normalize_driver(driver_match.group(1)) if driver_match else "unknown"

    username_match = re.search(
        r"spring\.datasource\.username\s*=\s*(.+)", content
    )
    password_match = re.search(
        r"spring\.datasource\.password\s*=\s*(.+)", content
    )

    return {
        "source_file": source_file,
        "type": db_type,
        "url": url,
        "username": username_match.group(1).strip() if username_match else None,
        "has_password": password_match is not None,
    }


def _parse_django_config(
    content: str, source_file: str
) -> list[dict[str, Any]]:
    """Parse DB configuration from Django settings.py."""
    configs: list[dict[str, Any]] = []

    # Look for DATABASES = { ... } pattern
    db_block = re.search(
        r"DATABASES\s*=\s*\{(.+?)\n\}", content, re.DOTALL
    )
    if not db_block:
        return configs

    block = db_block.group(1)

    # Find named database connections
    db_names = re.findall(r"['\"](\w+)['\"]\s*:\s*\{", block)
    for db_name in db_names:
        start_pos = block.find(f"'{db_name}'")
        if start_pos == -1:
            start_pos = block.find(f'"{db_name}"')
        if start_pos == -1:
            continue
        engine_match = re.search(
            rf"['\"]ENGINE['\"]\s*:\s*['\"]([^'\"]+)['\"]",
            block[start_pos:],
        )
        if engine_match:
            engine = engine_match.group(1)
            db_type = _normalize_driver(engine.split(".")[-1])
            configs.append(
                {
                    "source_file": source_file,
                    "name": db_name,
                    "type": db_type,
                    "engine": engine,
                }
            )

    return configs


def _normalize_driver(driver: str) -> str:
    """Normalize database driver name to a standard type."""
    driver_lower = driver.lower()

    if any(k in driver_lower for k in ("mysql", "mariadb")):
        return "mysql"
    if any(k in driver_lower for k in ("postgres", "pgsql", "pg", "postgresql")):
        return "postgresql"
    if "sqlite" in driver_lower:
        return "sqlite"
    if any(k in driver_lower for k in ("sqlserver", "mssql")):
        return "sqlserver"
    if "oracle" in driver_lower:
        return "oracle"
    if "mongodb" in driver_lower or "mongo" in driver_lower:
        return "mongodb"
    if "redis" in driver_lower:
        return "redis"

    return driver_lower if driver_lower else "unknown"


def detect_migration_dirs(source_dir: str) -> list[str]:
    """Detect migration directories in the project."""
    root = Path(source_dir)
    found: list[str] = []

    for pattern in MIGRATION_DIR_PATTERNS:
        migration_dir = root / pattern
        if migration_dir.is_dir():
            found.append(str(migration_dir))

    return found


def parse_sql_dump(dump_content: str) -> dict[str, Any]:
    """Parse a SQL dump file to extract schema information.

    Extracts CREATE TABLE statements, column definitions, indexes,
    and foreign keys.
    """
    tables: dict[str, dict[str, Any]] = {}

    # Match CREATE TABLE statements
    # Find each CREATE TABLE and extract body by balanced parentheses
    create_table_header = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\(",
        re.IGNORECASE,
    )

    for match in create_table_header.finditer(dump_content):
        table_name = match.group(1)
        # Extract body by finding matching closing parenthesis
        start = match.end()
        depth = 1
        pos = start
        while pos < len(dump_content) and depth > 0:
            if dump_content[pos] == "(":
                depth += 1
            elif dump_content[pos] == ")":
                depth -= 1
            pos += 1
        body = dump_content[start : pos - 1]
        table_info = _parse_table_body(table_name, body)
        tables[table_name] = table_info

    return {
        "tables": tables,
        "table_count": len(tables),
    }


def _parse_table_body(table_name: str, body: str) -> dict[str, Any]:
    """Parse the body of a CREATE TABLE statement."""
    columns: list[dict[str, Any]] = []
    primary_key: list[str] = []
    foreign_keys: list[dict[str, str]] = []
    indexes: list[dict[str, Any]] = []
    has_active_flag = False
    active_flag_columns: list[str] = []
    label_columns_found: list[str] = []
    is_settings_table = any(
        re.search(p, table_name, re.IGNORECASE)
        for p in SETTINGS_TABLE_PATTERNS
    )

    lines = body.split("\n")
    for line in lines:
        line = line.strip().rstrip(",")
        if not line:
            continue

        # Skip constraint/index lines
        if re.match(
            r"^\s*(PRIMARY\s+KEY|UNIQUE|INDEX|KEY|CONSTRAINT|FOREIGN\s+KEY|CHECK)",
            line,
            re.IGNORECASE,
        ):
            # Extract PRIMARY KEY columns
            pk_match = re.search(
                r"PRIMARY\s+KEY\s*\(([^)]+)\)", line, re.IGNORECASE
            )
            if pk_match:
                primary_key = [
                    c.strip().strip("`\"'") for c in pk_match.group(1).split(",")
                ]

            # Extract FOREIGN KEY
            fk_match = re.search(
                r"FOREIGN\s+KEY\s*\([`\"']?(\w+)[`\"']?\)\s*REFERENCES\s+[`\"']?(\w+)[`\"']?\s*\([`\"']?(\w+)[`\"']?\)",
                line,
                re.IGNORECASE,
            )
            if fk_match:
                foreign_keys.append(
                    {
                        "column": fk_match.group(1),
                        "references_table": fk_match.group(2),
                        "references_column": fk_match.group(3),
                    }
                )

            # Extract INDEX
            idx_match = re.search(
                r"(?:UNIQUE\s+)?(?:INDEX|KEY)\s+[`\"']?(\w+)[`\"']?\s*\(([^)]+)\)",
                line,
                re.IGNORECASE,
            )
            if idx_match:
                idx_cols = [
                    c.strip().strip("`\"'") for c in idx_match.group(2).split(",")
                ]
                indexes.append(
                    {
                        "name": idx_match.group(1),
                        "columns": idx_cols,
                        "unique": "UNIQUE" in line.upper(),
                    }
                )
            continue

        # Parse column definition
        col_match = re.match(
            r"[`\"']?(\w+)[`\"']?\s+(\w+(?:\([^)]*\))?)",
            line,
            re.IGNORECASE,
        )
        if col_match:
            col_name = col_match.group(1)
            col_type = col_match.group(2)

            nullable = "NOT NULL" not in line.upper()
            default = None
            default_match = re.search(
                r"DEFAULT\s+(['\"]?[^,'\")]+['\"]?)", line, re.IGNORECASE
            )
            if default_match:
                default = default_match.group(1).strip().strip("'\"")

            columns.append(
                {
                    "name": col_name,
                    "type": col_type,
                    "nullable": nullable,
                    "default": default,
                }
            )

            # Check for active/inactive flag columns
            if col_name.lower() in ACTIVE_FLAG_COLUMNS:
                has_active_flag = True
                active_flag_columns.append(col_name)

            # Check for label columns
            if col_name.lower() in LABEL_COLUMNS:
                label_columns_found.append(col_name)

    # Determine table type
    table_type = _classify_table(
        table_name, columns, foreign_keys, has_active_flag
    )

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
    }


def _classify_table(
    table_name: str,
    columns: list[dict[str, Any]],
    foreign_keys: list[dict[str, str]],
    has_active_flag: bool,
) -> str:
    """Classify a table as Master/Transaction/Relation/System.

    M: Master (reference data, has active flags, few FKs)
    T: Transaction (business events, has timestamps, many FKs)
    R: Relation (junction/pivot table, mostly FKs)
    S: System (framework tables: migrations, sessions, cache, etc.)
    """
    name_lower = table_name.lower()

    # System tables
    system_patterns = [
        "migration", "session", "cache", "job", "failed_job",
        "password_reset", "personal_access_token", "oauth",
        "telescope", "horizon", "pulse",
    ]
    if any(p in name_lower for p in system_patterns):
        return "S"

    col_names = {c["name"].lower() for c in columns}

    # Relation tables (mostly foreign keys)
    if len(foreign_keys) >= 2 and len(columns) <= len(foreign_keys) + 3:
        return "R"

    # Master tables
    if has_active_flag or name_lower.startswith("m_") or name_lower.startswith("mst_"):
        return "M"
    if "name" in col_names and len(foreign_keys) == 0:
        return "M"

    # Transaction tables
    if any(c in col_names for c in ("created_at", "updated_at", "transaction_date")):
        if len(foreign_keys) >= 1:
            return "T"

    return "T"  # Default to transaction


def parse_migrations(migrations_dir: str) -> dict[str, Any]:
    """Parse migration files to extract schema evolution information."""
    migration_dir = Path(migrations_dir)
    migrations: list[dict[str, Any]] = []
    tables_created: dict[str, dict[str, Any]] = {}

    if not migration_dir.is_dir():
        return {"migrations": [], "tables": {}}

    # Collect and sort migration files
    migration_files = sorted(
        f
        for f in migration_dir.iterdir()
        if f.is_file()
        and f.suffix in (".php", ".sql", ".py", ".rb", ".ts", ".js")
    )

    for mf in migration_files:
        try:
            content = mf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        migration_info: dict[str, Any] = {
            "file": mf.name,
            "tables_created": [],
            "tables_modified": [],
            "tables_dropped": [],
        }

        # Detect CREATE TABLE
        creates = re.findall(
            r"(?:Schema::create|CREATE\s+TABLE|create_table|createTable)\s*\(?['\"`]?(\w+)['\"`]?",
            content,
            re.IGNORECASE,
        )
        migration_info["tables_created"] = creates

        for table in creates:
            if table not in tables_created:
                tables_created[table] = {
                    "created_in": mf.name,
                    "modified_in": [],
                    "columns_added": [],
                    "columns_removed": [],
                }

        # Detect ALTER TABLE / Schema::table
        alters = re.findall(
            r"(?:Schema::table|ALTER\s+TABLE|change_table|table\.)\s*\(?['\"`]?(\w+)['\"`]?",
            content,
            re.IGNORECASE,
        )
        migration_info["tables_modified"] = list(set(alters))

        for table in alters:
            if table in tables_created:
                tables_created[table]["modified_in"].append(mf.name)

        # Detect DROP TABLE
        drops = re.findall(
            r"(?:Schema::drop(?:IfExists)?|DROP\s+TABLE|drop_table|dropTable)\s*\(?['\"`]?(\w+)['\"`]?",
            content,
            re.IGNORECASE,
        )
        migration_info["tables_dropped"] = drops

        for table in drops:
            if table in tables_created:
                tables_created[table]["dropped"] = True
                tables_created[table]["dropped_in"] = mf.name

        if creates or alters or drops:
            migrations.append(migration_info)

    return {
        "migrations": migrations,
        "tables": tables_created,
        "total_migrations": len(migrations),
        "total_tables": len(tables_created),
    }


# ---------------------------------------------------------------------------
# Live DB connection (delegated to live_introspection module)
# ---------------------------------------------------------------------------
from live_introspection import (  # noqa: E402
    execute_sql,
    introspect_live_db as _introspect_live_db_raw,
    parse_tsv_output,
    _safe_int,
)


def introspect_live_db(
    sql_command: str,
    db_type: str = "mysql",
    timeout: int = 30,
) -> dict[str, Any]:
    """Introspect a live database. Delegates to live_introspection module."""
    return _introspect_live_db_raw(
        sql_command=sql_command,
        db_type=db_type,
        timeout=timeout,
        classify_table_fn=_classify_table,
    )


def generate_db_manifest(
    configs: list[dict[str, Any]] | None = None,
    dump_schema: dict[str, Any] | None = None,
    migration_data: dict[str, Any] | None = None,
    migration_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a unified DB manifest from all available sources."""
    manifest: dict[str, Any] = {
        "db_connections": configs or [],
        "schema": {},
        "master_data_candidates": [],
        "settings_tables": [],
        "active_flag_tables": [],
        "label_sources": [],
        "migration_summary": None,
    }

    # Process SQL dump schema
    if dump_schema and "tables" in dump_schema:
        manifest["schema"] = dump_schema

        for table_name, table_info in dump_schema["tables"].items():
            if table_info.get("has_active_flag"):
                manifest["active_flag_tables"].append(
                    {
                        "table": table_name,
                        "flag_columns": table_info["active_flag_columns"],
                    }
                )

            if table_info.get("is_settings_table"):
                manifest["settings_tables"].append(table_name)

            if table_info.get("label_columns"):
                manifest["label_sources"].append(
                    {
                        "table": table_name,
                        "columns": table_info["label_columns"],
                    }
                )

            if table_info.get("table_type") == "M":
                manifest["master_data_candidates"].append(table_name)

    # Process migration data
    if migration_data:
        manifest["migration_summary"] = {
            "total_migrations": migration_data.get("total_migrations", 0),
            "total_tables": migration_data.get("total_tables", 0),
            "tables": migration_data.get("tables", {}),
            "migration_dirs": migration_dirs or [],
        }

        # If no dump schema, use migration data for table list
        if not dump_schema:
            for table_name, info in migration_data.get("tables", {}).items():
                if not info.get("dropped"):
                    if table_name not in manifest["schema"].get("tables", {}):
                        if "tables" not in manifest["schema"]:
                            manifest["schema"]["tables"] = {}
                        manifest["schema"]["tables"][table_name] = {
                            "source": "migration",
                            "created_in": info.get("created_in"),
                        }

    return manifest


def print_db_summary(manifest: dict[str, Any]) -> None:
    """Print a human-readable summary of DB analysis results."""
    print("\n=== Database Analysis Summary ===\n")

    # Connections
    connections = manifest.get("db_connections", [])
    if connections:
        print(f"Detected DB connections: {len(connections)}")
        for i, conn in enumerate(connections, 1):
            db_type = conn.get("type", "unknown")
            source = conn.get("source_file", "unknown")
            name = conn.get("name") or conn.get("database", "")
            print(f"  {i}. [{db_type}] {name} (from: {os.path.basename(source)})")
    else:
        print("  No DB connections detected.")

    print()

    # Schema
    schema = manifest.get("schema", {})
    tables = schema.get("tables", {})
    if tables:
        print(f"Tables found: {len(tables)}")

        # Count by type
        type_counts: dict[str, int] = {}
        for info in tables.values():
            t = info.get("table_type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, count in sorted(type_counts.items()):
            label = {"M": "Master", "T": "Transaction", "R": "Relation", "S": "System"}.get(t, t)
            print(f"  {label}: {count}")
    else:
        print("  No table schema found.")

    print()

    # Active flags
    active_tables = manifest.get("active_flag_tables", [])
    if active_tables:
        print(f"Tables with active/inactive flags: {len(active_tables)}")
        for item in active_tables:
            print(f"  - {item['table']}: {', '.join(item['flag_columns'])}")

    # Settings tables
    settings = manifest.get("settings_tables", [])
    if settings:
        print(f"\nSettings/config tables: {', '.join(settings)}")

    # Label sources
    labels = manifest.get("label_sources", [])
    if labels:
        print(f"\nTables with label/name columns: {len(labels)}")
        for item in labels:
            print(f"  - {item['table']}: {', '.join(item['columns'])}")

    # Migration summary
    migration_info = manifest.get("migration_summary")
    if migration_info:
        print(f"\nMigration files: {migration_info.get('total_migrations', 0)}")
        print(f"Tables created via migration: {migration_info.get('total_tables', 0)}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a project for database configuration and schema information."
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="Path to the project root (auto-detects DB config and migrations).",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="Database connection string (for metadata only, no live connection).",
    )
    parser.add_argument(
        "--sql-command",
        default=None,
        help=(
            "Shell command to execute SQL queries against the database. "
            "SQL is piped to stdin. Example: 'mysql -u root -N mydb', "
            "'docker exec -i db mysql -u root mydb', "
            "'psql -U postgres -t mydb'"
        ),
    )
    parser.add_argument(
        "--db-type",
        default="mysql",
        choices=["mysql", "postgresql"],
        help="Database type for live introspection (default: mysql).",
    )
    parser.add_argument(
        "--dump-file",
        default=None,
        help="Path to a SQL dump file to analyze.",
    )
    parser.add_argument(
        "--migrations-dir",
        default=None,
        help="Path to migration files directory.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON manifest. If omitted, prints to stdout.",
    )
    args = parser.parse_args()

    # Validate at least one input is provided
    if not any([args.source_dir, args.dsn, args.dump_file, args.migrations_dir, args.sql_command]):
        print(
            "Error: at least one of --source-dir, --dsn, --dump-file, "
            "--migrations-dir, or --sql-command is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    configs: list[dict[str, Any]] = []
    dump_schema: dict[str, Any] | None = None
    migration_data: dict[str, Any] | None = None
    migration_dirs: list[str] = []

    # Auto-detect from source directory
    if args.source_dir:
        source_dir = os.path.abspath(args.source_dir)
        if not os.path.isdir(source_dir):
            print(f"Error: {source_dir} is not a directory.", file=sys.stderr)
            sys.exit(1)

        configs = detect_db_configs(source_dir)
        migration_dirs = detect_migration_dirs(source_dir)

        for mdir in migration_dirs:
            mdata = parse_migrations(mdir)
            if migration_data is None:
                migration_data = mdata
            else:
                migration_data["migrations"].extend(mdata["migrations"])
                migration_data["tables"].update(mdata["tables"])
                migration_data["total_migrations"] += mdata["total_migrations"]
                migration_data["total_tables"] = len(migration_data["tables"])

    # Parse SQL dump
    if args.dump_file:
        dump_path = os.path.abspath(args.dump_file)
        if not os.path.isfile(dump_path):
            print(f"Error: {dump_path} is not a file.", file=sys.stderr)
            sys.exit(1)
        try:
            content = Path(dump_path).read_text(encoding="utf-8")
            dump_schema = parse_sql_dump(content)
        except (OSError, UnicodeDecodeError) as e:
            print(f"Error reading dump file: {e}", file=sys.stderr)
            sys.exit(1)

    # Parse migrations directory
    if args.migrations_dir:
        mdir = os.path.abspath(args.migrations_dir)
        if not os.path.isdir(mdir):
            print(f"Error: {mdir} is not a directory.", file=sys.stderr)
            sys.exit(1)
        migration_data = parse_migrations(mdir)
        migration_dirs = [mdir]

    # DSN (metadata only)
    if args.dsn:
        # Parse DSN to extract connection info
        dsn_match = re.match(
            r"(\w+)://(?:(\w+)(?::([^@]*))?@)?([^/:]+)(?::(\d+))?/(\w+)",
            args.dsn,
        )
        if dsn_match:
            configs.append(
                {
                    "source_file": "command-line --dsn",
                    "type": _normalize_driver(dsn_match.group(1)),
                    "username": dsn_match.group(2),
                    "host": dsn_match.group(4),
                    "port": dsn_match.group(5),
                    "database": dsn_match.group(6),
                }
            )
        else:
            redacted = re.sub(r"://[^@]+@", "://<redacted>@", args.dsn)
            print(
                f"Warning: Could not parse DSN: {redacted}",
                file=sys.stderr,
            )

    # Live DB introspection via user-specified command
    if args.sql_command:
        live_schema = introspect_live_db(
            sql_command=args.sql_command,
            db_type=args.db_type,
            timeout=30,
        )
        if live_schema.get("table_count", 0) > 0:
            # Live DB takes priority over dump schema
            dump_schema = live_schema

    # Generate manifest
    manifest = generate_db_manifest(
        configs=configs,
        dump_schema=dump_schema,
        migration_data=migration_data,
        migration_dirs=migration_dirs,
    )

    # Output
    print_db_summary(manifest)

    if args.output:
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"Manifest written to: {output_path}")
    else:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
