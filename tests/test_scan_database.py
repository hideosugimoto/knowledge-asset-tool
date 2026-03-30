"""scan_database.py のテスト"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from scan_database import (
    _classify_table,
    _normalize_driver,
    _parse_env_db_config,
    _parse_prisma_config,
    _parse_properties_config,
    _parse_table_body,
    detect_db_configs,
    detect_migration_dirs,
    generate_db_manifest,
    introspect_live_db,
    parse_migrations,
    parse_sql_dump,
    print_db_summary,
)
from live_introspection import (
    _is_safe_identifier,
    _safe_int,
    execute_sql,
    parse_tsv_output,
)


# ---------------------------------------------------------------------------
# _normalize_driver
# ---------------------------------------------------------------------------
class TestNormalizeDriver:
    """DB ドライバ名の正規化"""

    def test_mysql(self):
        assert _normalize_driver("mysql") == "mysql"

    def test_mariadb(self):
        assert _normalize_driver("mariadb") == "mysql"

    def test_postgres(self):
        assert _normalize_driver("pgsql") == "postgresql"

    def test_postgresql(self):
        assert _normalize_driver("postgresql") == "postgresql"

    def test_pg(self):
        assert _normalize_driver("pg") == "postgresql"

    def test_sqlite(self):
        assert _normalize_driver("sqlite") == "sqlite"

    def test_sqlserver(self):
        assert _normalize_driver("sqlserver") == "sqlserver"

    def test_mssql(self):
        assert _normalize_driver("mssql") == "sqlserver"

    def test_oracle(self):
        assert _normalize_driver("oracle") == "oracle"

    def test_mongodb(self):
        assert _normalize_driver("mongodb") == "mongodb"

    def test_redis(self):
        assert _normalize_driver("redis") == "redis"

    def test_unknown(self):
        assert _normalize_driver("cockroachdb") == "cockroachdb"

    def test_empty(self):
        assert _normalize_driver("") == "unknown"

    def test_case_insensitive(self):
        assert _normalize_driver("MySQL") == "mysql"
        assert _normalize_driver("PostgreSQL") == "postgresql"


# ---------------------------------------------------------------------------
# _parse_env_db_config
# ---------------------------------------------------------------------------
class TestParseEnvDbConfig:
    """".env ファイルからDB設定をパース"""

    def test_full_config(self):
        content = """
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=myapp
DB_USERNAME=root
DB_PASSWORD=secret
"""
        result = _parse_env_db_config(content, ".env")
        assert result is not None
        assert result["type"] == "mysql"
        assert result["host"] == "127.0.0.1"
        assert result["port"] == "3306"
        assert result["database"] == "myapp"
        assert result["username"] == "root"
        assert result["has_password"] is True
        assert "password" not in result
        assert result["source_file"] == ".env"

    def test_partial_config(self):
        content = "DB_CONNECTION=pgsql\nDB_HOST=localhost\n"
        result = _parse_env_db_config(content, ".env")
        assert result is not None
        assert result["type"] == "postgresql"
        assert result["host"] == "localhost"

    def test_no_db_config(self):
        content = "APP_NAME=MyApp\nAPP_ENV=local\n"
        result = _parse_env_db_config(content, ".env")
        assert result is None

    def test_quoted_values(self):
        content = 'DB_CONNECTION="mysql"\nDB_HOST="db.example.com"\n'
        result = _parse_env_db_config(content, ".env")
        assert result is not None
        assert result["driver"] == "mysql"
        assert result["host"] == "db.example.com"


# ---------------------------------------------------------------------------
# _parse_prisma_config
# ---------------------------------------------------------------------------
class TestParsePrismaConfig:
    """Prisma schema からDB設定をパース"""

    def test_postgresql(self):
        content = """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
"""
        result = _parse_prisma_config(content, "prisma/schema.prisma")
        assert result is not None
        assert result["type"] == "postgresql"
        assert result["connection_env_var"] == "DATABASE_URL"

    def test_mysql(self):
        content = 'datasource db {\n  provider = "mysql"\n  url = env("MYSQL_URL")\n}'
        result = _parse_prisma_config(content, "prisma/schema.prisma")
        assert result is not None
        assert result["type"] == "mysql"
        assert result["connection_env_var"] == "MYSQL_URL"

    def test_no_provider(self):
        content = "model User {\n  id Int @id\n}"
        result = _parse_prisma_config(content, "prisma/schema.prisma")
        assert result is None


# ---------------------------------------------------------------------------
# _parse_properties_config
# ---------------------------------------------------------------------------
class TestParsePropertiesConfig:
    """Java .properties ファイルからDB設定をパース"""

    def test_spring_datasource(self):
        content = """
spring.datasource.url=jdbc:mysql://localhost:3306/mydb
spring.datasource.username=root
spring.datasource.password=pass
"""
        result = _parse_properties_config(content, "application.properties")
        assert result is not None
        assert result["type"] == "mysql"
        assert result["username"] == "root"
        assert result["has_password"] is True

    def test_no_datasource(self):
        content = "server.port=8080\n"
        result = _parse_properties_config(content, "application.properties")
        assert result is None


# ---------------------------------------------------------------------------
# detect_db_configs
# ---------------------------------------------------------------------------
class TestDetectDbConfigs:
    """プロジェクトからDB接続設定を自動検出"""

    def test_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DB_CONNECTION=mysql\nDB_HOST=localhost\nDB_DATABASE=app\n"
        )
        configs = detect_db_configs(str(tmp_path))
        assert len(configs) == 1
        assert configs[0]["type"] == "mysql"

    def test_prisma_schema(self, tmp_path):
        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        schema = prisma_dir / "schema.prisma"
        schema.write_text(
            'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}'
        )
        configs = detect_db_configs(str(tmp_path))
        assert len(configs) == 1
        assert configs[0]["type"] == "postgresql"

    def test_multiple_configs(self, tmp_path):
        (tmp_path / ".env").write_text(
            "DB_CONNECTION=mysql\nDB_HOST=localhost\nDB_DATABASE=app\n"
        )
        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  provider = "postgresql"\n  url = env("DB_URL")\n}'
        )
        configs = detect_db_configs(str(tmp_path))
        assert len(configs) == 2

    def test_no_configs(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        configs = detect_db_configs(str(tmp_path))
        assert configs == []

    def test_unreadable_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_bytes(b"\xff\xfe" + b"\x00" * 100)
        configs = detect_db_configs(str(tmp_path))
        assert configs == []


# ---------------------------------------------------------------------------
# detect_migration_dirs
# ---------------------------------------------------------------------------
class TestDetectMigrationDirs:
    """マイグレーションディレクトリの検出"""

    def test_laravel_migrations(self, tmp_path):
        mdir = tmp_path / "database" / "migrations"
        mdir.mkdir(parents=True)
        result = detect_migration_dirs(str(tmp_path))
        assert len(result) == 1
        assert "database/migrations" in result[0]

    def test_generic_migrations(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        result = detect_migration_dirs(str(tmp_path))
        assert len(result) == 1

    def test_prisma_migrations(self, tmp_path):
        mdir = tmp_path / "prisma" / "migrations"
        mdir.mkdir(parents=True)
        result = detect_migration_dirs(str(tmp_path))
        assert len(result) == 1

    def test_no_migrations(self, tmp_path):
        result = detect_migration_dirs(str(tmp_path))
        assert result == []

    def test_multiple_migration_dirs(self, tmp_path):
        (tmp_path / "migrations").mkdir()
        (tmp_path / "database" / "migrations").mkdir(parents=True)
        result = detect_migration_dirs(str(tmp_path))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_sql_dump
# ---------------------------------------------------------------------------
class TestParseSqlDump:
    """SQL ダンプファイルのパース"""

    def test_basic_create_table(self):
        sql = """
CREATE TABLE users (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_email (email)
);
"""
        result = parse_sql_dump(sql)
        assert result["table_count"] == 1
        assert "users" in result["tables"]
        table = result["tables"]["users"]
        assert len(table["columns"]) == 5
        assert table["has_active_flag"] is True
        assert "is_active" in table["active_flag_columns"]
        assert "name" in table["label_columns"]

    def test_multiple_tables(self):
        sql = """
CREATE TABLE products (
    id INT NOT NULL,
    name VARCHAR(100),
    status VARCHAR(20),
    PRIMARY KEY (id)
);

CREATE TABLE orders (
    id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT DEFAULT 1,
    created_at TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""
        result = parse_sql_dump(sql)
        assert result["table_count"] == 2
        assert "products" in result["tables"]
        assert "orders" in result["tables"]
        orders = result["tables"]["orders"]
        assert len(orders["foreign_keys"]) == 1
        assert orders["foreign_keys"][0]["references_table"] == "products"

    def test_settings_table(self):
        sql = """
CREATE TABLE settings (
    id INT NOT NULL,
    key VARCHAR(100),
    value TEXT,
    PRIMARY KEY (id)
);
"""
        result = parse_sql_dump(sql)
        assert result["tables"]["settings"]["is_settings_table"] is True

    def test_empty_dump(self):
        result = parse_sql_dump("")
        assert result["table_count"] == 0
        assert result["tables"] == {}

    def test_deleted_at_column(self):
        sql = """
CREATE TABLE posts (
    id INT NOT NULL,
    title VARCHAR(200),
    deleted_at TIMESTAMP DEFAULT NULL,
    PRIMARY KEY (id)
);
"""
        result = parse_sql_dump(sql)
        table = result["tables"]["posts"]
        assert table["has_active_flag"] is True
        assert "deleted_at" in table["active_flag_columns"]


# ---------------------------------------------------------------------------
# _classify_table
# ---------------------------------------------------------------------------
class TestClassifyTable:
    """テーブル種別の分類"""

    def test_system_table_migrations(self):
        result = _classify_table("migrations", [], [], False)
        assert result == "S"

    def test_system_table_sessions(self):
        result = _classify_table("sessions", [], [], False)
        assert result == "S"

    def test_system_table_jobs(self):
        result = _classify_table("failed_jobs", [], [], False)
        assert result == "S"

    def test_relation_table(self):
        fks = [
            {"column": "user_id", "references_table": "users", "references_column": "id"},
            {"column": "role_id", "references_table": "roles", "references_column": "id"},
        ]
        columns = [
            {"name": "user_id", "type": "INT"},
            {"name": "role_id", "type": "INT"},
            {"name": "created_at", "type": "TIMESTAMP"},
        ]
        result = _classify_table("user_roles", columns, fks, False)
        assert result == "R"

    def test_master_table_with_active_flag(self):
        columns = [
            {"name": "id", "type": "INT"},
            {"name": "name", "type": "VARCHAR"},
            {"name": "is_active", "type": "TINYINT"},
        ]
        result = _classify_table("categories", columns, [], True)
        assert result == "M"

    def test_master_table_prefix(self):
        columns = [{"name": "id"}, {"name": "name"}]
        result = _classify_table("m_products", columns, [], False)
        assert result == "M"

    def test_master_table_mst_prefix(self):
        columns = [{"name": "id"}, {"name": "name"}]
        result = _classify_table("mst_categories", columns, [], False)
        assert result == "M"

    def test_master_table_name_column_no_fks(self):
        columns = [{"name": "id"}, {"name": "name"}, {"name": "code"}]
        result = _classify_table("departments", columns, [], False)
        assert result == "M"

    def test_transaction_table(self):
        columns = [
            {"name": "id"},
            {"name": "user_id"},
            {"name": "amount"},
            {"name": "created_at"},
        ]
        fks = [{"column": "user_id", "references_table": "users", "references_column": "id"}]
        result = _classify_table("payments", columns, fks, False)
        assert result == "T"

    def test_default_transaction(self):
        columns = [{"name": "id"}, {"name": "data"}]
        result = _classify_table("unknown_table", columns, [], False)
        assert result == "T"


# ---------------------------------------------------------------------------
# parse_migrations
# ---------------------------------------------------------------------------
class TestParseMigrations:
    """マイグレーションファイルのパース"""

    def test_laravel_migrations(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "2024_01_01_create_users_table.php").write_text(
            "Schema::create('users', function (Blueprint $table) {});"
        )
        (mdir / "2024_01_02_create_posts_table.php").write_text(
            "Schema::create('posts', function (Blueprint $table) {});"
        )
        result = parse_migrations(str(mdir))
        assert result["total_migrations"] == 2
        assert result["total_tables"] == 2
        assert "users" in result["tables"]
        assert "posts" in result["tables"]

    def test_sql_migrations(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "001_init.sql").write_text("CREATE TABLE users (id INT);")
        result = parse_migrations(str(mdir))
        assert result["total_tables"] == 1

    def test_alter_table(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "001.php").write_text("Schema::create('users', fn() => null);")
        (mdir / "002.php").write_text("Schema::table('users', fn() => null);")
        result = parse_migrations(str(mdir))
        assert "users" in result["tables"]
        assert len(result["tables"]["users"]["modified_in"]) == 1

    def test_drop_table(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "001.php").write_text("Schema::create('temp', fn() => null);")
        (mdir / "002.php").write_text("Schema::dropIfExists('temp');")
        result = parse_migrations(str(mdir))
        assert result["tables"]["temp"].get("dropped") is True

    def test_nonexistent_dir(self, tmp_path):
        result = parse_migrations(str(tmp_path / "nonexistent"))
        assert result["migrations"] == []
        assert result["tables"] == {}

    def test_empty_dir(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        result = parse_migrations(str(mdir))
        assert result["total_migrations"] == 0

    def test_ignores_non_code_files(self, tmp_path):
        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "README.md").write_text("# Migrations")
        (mdir / "001.sql").write_text("CREATE TABLE users (id INT);")
        result = parse_migrations(str(mdir))
        assert result["total_migrations"] == 1


# ---------------------------------------------------------------------------
# generate_db_manifest
# ---------------------------------------------------------------------------
class TestGenerateDbManifest:
    """DB マニフェスト生成"""

    def test_empty_manifest(self):
        result = generate_db_manifest()
        assert result["db_connections"] == []
        assert result["schema"] == {}
        assert result["master_data_candidates"] == []
        assert result["settings_tables"] == []
        assert result["active_flag_tables"] == []
        assert result["label_sources"] == []
        assert result["migration_summary"] is None

    def test_with_dump_schema(self):
        dump = {
            "tables": {
                "products": {
                    "table_type": "M",
                    "has_active_flag": True,
                    "active_flag_columns": ["is_active"],
                    "is_settings_table": False,
                    "label_columns": ["name"],
                },
                "settings": {
                    "table_type": "S",
                    "has_active_flag": False,
                    "active_flag_columns": [],
                    "is_settings_table": True,
                    "label_columns": ["value"],
                },
            }
        }
        result = generate_db_manifest(dump_schema=dump)
        assert "products" in result["master_data_candidates"]
        assert "settings" in result["settings_tables"]
        assert len(result["active_flag_tables"]) == 1
        assert len(result["label_sources"]) == 2

    def test_with_migration_data(self):
        migration_data = {
            "total_migrations": 3,
            "total_tables": 2,
            "tables": {
                "users": {"created_in": "001.sql", "modified_in": []},
                "posts": {"created_in": "002.sql", "modified_in": []},
            },
        }
        result = generate_db_manifest(migration_data=migration_data)
        assert result["migration_summary"] is not None
        assert result["migration_summary"]["total_migrations"] == 3
        # Migration tables should be added to schema when no dump exists
        assert "users" in result["schema"]["tables"]
        assert "posts" in result["schema"]["tables"]

    def test_with_configs(self):
        configs = [
            {"source_file": ".env", "type": "mysql", "database": "app"},
        ]
        result = generate_db_manifest(configs=configs)
        assert len(result["db_connections"]) == 1
        assert result["db_connections"][0]["type"] == "mysql"

    def test_dropped_tables_excluded_from_schema(self):
        migration_data = {
            "total_migrations": 2,
            "total_tables": 2,
            "tables": {
                "users": {"created_in": "001.sql", "modified_in": []},
                "temp": {"created_in": "001.sql", "modified_in": [], "dropped": True},
            },
        }
        result = generate_db_manifest(migration_data=migration_data)
        assert "users" in result["schema"]["tables"]
        assert "temp" not in result["schema"]["tables"]


# ---------------------------------------------------------------------------
# print_db_summary
# ---------------------------------------------------------------------------
class TestPrintDbSummary:
    """サマリー表示"""

    def test_prints_connections(self, capsys):
        manifest = generate_db_manifest(
            configs=[{"source_file": ".env", "type": "mysql", "database": "app"}]
        )
        print_db_summary(manifest)
        captured = capsys.readouterr()
        assert "mysql" in captured.out
        assert "app" in captured.out

    def test_prints_no_connections(self, capsys):
        manifest = generate_db_manifest()
        print_db_summary(manifest)
        captured = capsys.readouterr()
        assert "No DB connections detected" in captured.out

    def test_prints_table_counts(self, capsys):
        dump = {
            "tables": {
                "users": {
                    "table_type": "M",
                    "has_active_flag": True,
                    "active_flag_columns": ["is_active"],
                    "is_settings_table": False,
                    "label_columns": ["name"],
                },
            }
        }
        manifest = generate_db_manifest(dump_schema=dump)
        print_db_summary(manifest)
        captured = capsys.readouterr()
        assert "Tables found: 1" in captured.out
        assert "Master" in captured.out


# ---------------------------------------------------------------------------
# main (unit)
# ---------------------------------------------------------------------------
class TestMain:
    """main() 関数のテスト"""

    def test_main_with_source_dir(self, tmp_path, monkeypatch):
        from scan_database import main

        (tmp_path / ".env").write_text("DB_CONNECTION=mysql\nDB_HOST=localhost\n")
        output_file = tmp_path / "out.json"

        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--source-dir", str(tmp_path), "--output", str(output_file)],
        )
        main()
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "db_connections" in data

    def test_main_with_dump_file(self, tmp_path, monkeypatch):
        from scan_database import main

        dump = tmp_path / "schema.sql"
        dump.write_text("CREATE TABLE users (id INT, name VARCHAR(100), PRIMARY KEY (id));")
        output_file = tmp_path / "out.json"

        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--dump-file", str(dump), "--output", str(output_file)],
        )
        main()
        data = json.loads(output_file.read_text())
        assert "users" in data["schema"]["tables"]

    def test_main_with_migrations_dir(self, tmp_path, monkeypatch):
        from scan_database import main

        mdir = tmp_path / "migrations"
        mdir.mkdir()
        (mdir / "001.sql").write_text("CREATE TABLE posts (id INT);")
        output_file = tmp_path / "out.json"

        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--migrations-dir", str(mdir), "--output", str(output_file)],
        )
        main()
        data = json.loads(output_file.read_text())
        assert data["migration_summary"]["total_tables"] == 1

    def test_main_with_dsn(self, tmp_path, monkeypatch):
        from scan_database import main

        output_file = tmp_path / "out.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "scan_database.py",
                "--dsn",
                "mysql://user:pass@localhost:3306/mydb",
                "--output",
                str(output_file),
            ],
        )
        main()
        data = json.loads(output_file.read_text())
        assert len(data["db_connections"]) == 1
        assert data["db_connections"][0]["type"] == "mysql"
        assert data["db_connections"][0]["database"] == "mydb"

    def test_main_no_args(self, monkeypatch):
        from scan_database import main

        monkeypatch.setattr("sys.argv", ["scan_database.py"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_invalid_source_dir(self, tmp_path, monkeypatch):
        from scan_database import main

        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--source-dir", str(tmp_path / "nonexistent")],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_invalid_dump_file(self, tmp_path, monkeypatch):
        from scan_database import main

        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--dump-file", str(tmp_path / "missing.sql")],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_stdout_output(self, tmp_path, monkeypatch, capsys):
        from scan_database import main

        (tmp_path / ".env").write_text("DB_CONNECTION=sqlite\n")
        monkeypatch.setattr(
            "sys.argv",
            ["scan_database.py", "--source-dir", str(tmp_path)],
        )
        main()
        captured = capsys.readouterr()
        assert "db_connections" in captured.out

    def test_main_with_sql_command(self, tmp_path, monkeypatch):
        from scan_database import main

        output_file = tmp_path / "out.json"
        # Use echo to simulate a DB that returns TSV output
        monkeypatch.setattr(
            "sys.argv",
            [
                "scan_database.py",
                "--sql-command",
                "echo 'table_name\ttable_type\ttable_rows\ttable_comment\nusers\tBASE TABLE\t100\t'",
                "--db-type",
                "mysql",
                "--output",
                str(output_file),
            ],
        )
        main()
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "schema" in data


# ---------------------------------------------------------------------------
# _is_safe_identifier
# ---------------------------------------------------------------------------
class TestIsSafeIdentifier:
    """SQL識別子のバリデーション"""

    def test_normal_name(self):
        assert _is_safe_identifier("users") is True

    def test_with_underscores(self):
        assert _is_safe_identifier("user_roles") is True

    def test_with_numbers(self):
        assert _is_safe_identifier("table_2024") is True

    def test_starts_with_number(self):
        assert _is_safe_identifier("2users") is False

    def test_with_spaces(self):
        assert _is_safe_identifier("user roles") is False

    def test_with_semicolon(self):
        assert _is_safe_identifier("users; DROP TABLE") is False

    def test_with_quotes(self):
        assert _is_safe_identifier("users'--") is False

    def test_empty(self):
        assert _is_safe_identifier("") is False

    def test_too_long(self):
        assert _is_safe_identifier("a" * 129) is False

    def test_max_length(self):
        assert _is_safe_identifier("a" * 128) is True


# ---------------------------------------------------------------------------
# parse_tsv_output
# ---------------------------------------------------------------------------
class TestParseTsvOutput:
    """TSV出力のパース"""

    def test_basic_tsv(self):
        output = "col_a\tcol_b\n1\thello\n2\tworld\n"
        result = parse_tsv_output(output)
        assert len(result) == 2
        assert result[0]["col_a"] == "1"
        assert result[0]["col_b"] == "hello"
        assert result[1]["col_a"] == "2"

    def test_empty_output(self):
        assert parse_tsv_output("") == []

    def test_header_only(self):
        assert parse_tsv_output("col_a\tcol_b\n") == []

    def test_single_row(self):
        output = "name\tvalue\nfoo\tbar\n"
        result = parse_tsv_output(output)
        assert len(result) == 1
        assert result[0]["name"] == "foo"

    def test_missing_columns(self):
        """行のカラム数がヘッダーより少ない場合"""
        output = "a\tb\tc\n1\t2\n"
        result = parse_tsv_output(output)
        assert result[0]["a"] == "1"
        assert result[0]["b"] == "2"
        assert result[0]["c"] == ""

    def test_whitespace_handling(self):
        output = "  name \t value \n foo \t bar \n"
        result = parse_tsv_output(output)
        assert result[0]["name"] == "foo"
        assert result[0]["value"] == "bar"


# ---------------------------------------------------------------------------
# execute_sql
# ---------------------------------------------------------------------------
class TestExecuteSql:
    """SQL実行のテスト"""

    def test_echo_command(self):
        result = execute_sql("cat", "hello world")
        assert result.strip() == "hello world"

    def test_failed_command(self, capsys):
        result = execute_sql("false", "SELECT 1")
        # false always returns exit code 1, stdout is empty
        assert result == ""

    def test_nonexistent_command(self):
        result = execute_sql("nonexistent_command_xyz_123", "SELECT 1")
        assert result == ""

    def test_timeout(self):
        result = execute_sql("sleep 10", "SELECT 1", timeout=1)
        assert result == ""


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------
class TestSafeInt:
    """安全な整数変換"""

    def test_valid_int(self):
        assert _safe_int("42") == 42

    def test_none(self):
        assert _safe_int(None) is None

    def test_invalid(self):
        assert _safe_int("abc") is None

    def test_empty(self):
        assert _safe_int("") is None

    def test_zero(self):
        assert _safe_int("0") == 0


# ---------------------------------------------------------------------------
# introspect_live_db
# ---------------------------------------------------------------------------
class TestIntrospectLiveDb:
    """ライブDB接続のテスト（モック）"""

    def test_unsupported_db_type(self):
        result = introspect_live_db("echo ''", db_type="oracle")
        assert result["tables"] == {}
        assert result["table_count"] == 0

    def test_empty_response(self):
        result = introspect_live_db("echo ''", db_type="mysql")
        assert result["table_count"] == 0

    def test_with_mock_tables(self, tmp_path):
        """シェルスクリプトでMySQLのTSV出力をシミュレート"""
        # Create a mock script that returns different output based on input SQL
        mock_script = tmp_path / "mock_db.sh"
        mock_script.write_text(
            '#!/bin/bash\n'
            'read -r sql\n'
            'if echo "$sql" | grep -q "information_schema.TABLES"; then\n'
            '  printf "table_name\\ttable_type\\ttable_rows\\ttable_comment\\n"\n'
            '  printf "users\\tBASE TABLE\\t100\\tUser accounts\\n"\n'
            '  printf "settings\\tBASE TABLE\\t5\\tApp settings\\n"\n'
            'elif echo "$sql" | grep -q "information_schema.COLUMNS"; then\n'
            '  printf "table_name\\tcolumn_name\\tcolumn_type\\tis_nullable\\tcolumn_default\\tcolumn_key\\tcolumn_comment\\textra\\n"\n'
            '  printf "users\\tid\\tint\\tNO\\tNULL\\tPRI\\t\\tauto_increment\\n"\n'
            '  printf "users\\tname\\tvarchar(255)\\tNO\\tNULL\\t\\t\\t\\n"\n'
            '  printf "users\\tis_active\\ttinyint(1)\\tNO\\t1\\t\\t\\t\\n"\n'
            '  printf "settings\\tid\\tint\\tNO\\tNULL\\tPRI\\t\\t\\n"\n'
            '  printf "settings\\tkey\\tvarchar(100)\\tNO\\tNULL\\t\\t\\t\\n"\n'
            '  printf "settings\\tvalue\\ttext\\tYES\\tNULL\\t\\t\\t\\n"\n'
            'elif echo "$sql" | grep -q "KEY_COLUMN_USAGE"; then\n'
            '  printf "table_name\\tcolumn_name\\treferenced_table_name\\treferenced_column_name\\tconstraint_name\\n"\n'
            'elif echo "$sql" | grep -q "STATISTICS"; then\n'
            '  printf "table_name\\tindex_name\\tcolumn_name\\tnon_unique\\n"\n'
            'else\n'
            '  printf "table_name\\ttotal\\tactive\\tinactive\\n"\n'
            '  printf "users\\t100\\t85\\t15\\n"\n'
            'fi\n'
        )
        mock_script.chmod(0o755)

        result = introspect_live_db(
            sql_command=f"bash {mock_script}",
            db_type="mysql",
        )

        assert result["table_count"] == 2
        assert "users" in result["tables"]
        assert "settings" in result["tables"]

        users = result["tables"]["users"]
        assert len(users["columns"]) == 3
        assert users["has_active_flag"] is True
        assert "is_active" in users["active_flag_columns"]
        assert users["row_count"] == 100
        assert users["primary_key"] == ["id"]

        settings = result["tables"]["settings"]
        assert settings["is_settings_table"] is True

    def test_source_field(self, tmp_path):
        """ライブDB結果にsource: live_dbが含まれる"""
        mock_script = tmp_path / "mock.sh"
        mock_script.write_text(
            '#!/bin/bash\n'
            'printf "table_name\\ttable_type\\ttable_rows\\ttable_comment\\n"\n'
            'printf "t1\\tBASE TABLE\\t10\\t\\n"\n'
        )
        mock_script.chmod(0o755)
        result = introspect_live_db(f"bash {mock_script}", db_type="mysql")
        assert result.get("source") == "live_db"
