"""scan_sources.py のテスト"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from scan_sources import (
    categorize_file,
    detect_project_type,
    estimate_tokens,
    print_summary,
    scan_directory,
    should_exclude,
)


# ---------------------------------------------------------------------------
# detect_project_type
# ---------------------------------------------------------------------------
class TestDetectProjectType:
    """プロジェクトタイプの自動検出"""

    def test_laravel_project(self, tmp_path):
        composer = tmp_path / "composer.json"
        composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        result = detect_project_type(str(tmp_path))
        assert "laravel" in result

    def test_nuxt_project(self, tmp_path):
        (tmp_path / "nuxt.config.js").write_text("export default {}")
        result = detect_project_type(str(tmp_path))
        assert "nuxt" in result

    def test_nuxt_ts_project(self, tmp_path):
        (tmp_path / "nuxt.config.ts").write_text("export default {}")
        result = detect_project_type(str(tmp_path))
        assert "nuxt" in result

    def test_vue_project(self, tmp_path):
        (tmp_path / "vue.config.js").write_text("module.exports = {}")
        result = detect_project_type(str(tmp_path))
        assert "vue" in result

    def test_nextjs_project(self, tmp_path):
        (tmp_path / "next.config.js").write_text("module.exports = {}")
        result = detect_project_type(str(tmp_path))
        assert "nextjs" in result

    def test_nextjs_mjs_project(self, tmp_path):
        (tmp_path / "next.config.mjs").write_text("export default {}")
        result = detect_project_type(str(tmp_path))
        assert "nextjs" in result

    def test_express_project(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"express": "^4.18.0"}}))
        result = detect_project_type(str(tmp_path))
        assert "express" in result

    def test_generic_project(self, tmp_path):
        """フレームワークマーカーなし → generic"""
        (tmp_path / "main.py").write_text("print('hello')")
        result = detect_project_type(str(tmp_path))
        assert result == "generic"

    def test_laravel_plus_nuxt(self, tmp_path):
        """複合プロジェクト"""
        composer = tmp_path / "composer.json"
        composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        (tmp_path / "nuxt.config.js").write_text("export default {}")
        result = detect_project_type(str(tmp_path))
        assert "laravel" in result
        assert "nuxt" in result

    def test_empty_directory(self, tmp_path):
        result = detect_project_type(str(tmp_path))
        assert result == "generic"

    def test_invalid_composer_json(self, tmp_path):
        """壊れた composer.json → エラーにならず generic"""
        (tmp_path / "composer.json").write_text("{invalid json")
        result = detect_project_type(str(tmp_path))
        assert result == "generic"

    def test_invalid_package_json(self, tmp_path):
        """壊れた package.json → エラーにならず generic"""
        (tmp_path / "package.json").write_text("not json at all")
        result = detect_project_type(str(tmp_path))
        assert result == "generic"

    def test_nextjs_ts_config(self, tmp_path):
        (tmp_path / "next.config.ts").write_text("export default {}")
        result = detect_project_type(str(tmp_path))
        assert "nextjs" in result

    def test_composer_without_laravel(self, tmp_path):
        """composer.json にはあるが laravel 依存なし"""
        (tmp_path / "composer.json").write_text(json.dumps({"require": {"symfony/console": "^5.0"}}))
        result = detect_project_type(str(tmp_path))
        assert result == "generic"


# ---------------------------------------------------------------------------
# should_exclude
# ---------------------------------------------------------------------------
class TestShouldExclude:
    """除外パスのフィルタリング"""

    def test_node_modules_excluded(self):
        assert should_exclude("project/node_modules/express/index.js") is True

    def test_git_excluded(self):
        assert should_exclude("project/.git/config") is True

    def test_vendor_excluded(self):
        assert should_exclude("project/vendor/autoload.php") is True

    def test_dist_excluded(self):
        assert should_exclude("project/dist/bundle.js") is True

    def test_build_excluded(self):
        assert should_exclude("project/build/output.js") is True

    def test_pycache_excluded(self):
        assert should_exclude("project/__pycache__/mod.cpython-311.pyc") is True

    def test_next_excluded(self):
        assert should_exclude("project/.next/static/chunks/main.js") is True

    def test_normal_path_not_excluded(self):
        assert should_exclude("project/src/index.ts") is False

    def test_normal_path_with_similar_name(self):
        """node_modules_backup のようなディレクトリは除外しない"""
        assert should_exclude("project/not_node_modules/index.js") is False


# ---------------------------------------------------------------------------
# categorize_file
# ---------------------------------------------------------------------------
class TestCategorizeFile:
    """ファイルカテゴリ分類"""

    # critical
    def test_laravel_routes_api_critical(self):
        assert categorize_file("routes/api.php", "laravel") == "critical"

    def test_laravel_routes_web_critical(self):
        assert categorize_file("routes/web.php", "laravel") == "critical"

    def test_laravel_model_critical(self):
        assert categorize_file("app/Models/User.php", "laravel") == "critical"

    def test_laravel_controller_critical(self):
        assert categorize_file("app/Http/Controllers/UserController.php", "laravel") == "critical"

    def test_nextjs_app_route_critical(self):
        assert categorize_file("app/api/users/route.ts", "nextjs") == "critical"

    def test_nextjs_page_critical(self):
        assert categorize_file("app/page.tsx", "nextjs") == "critical"

    def test_nuxt_pages_critical(self):
        assert categorize_file("pages/index.vue", "nuxt") == "critical"

    def test_express_routes_critical(self):
        assert categorize_file("routes/users.js", "express") == "critical"

    # high
    def test_laravel_service_high(self):
        assert categorize_file("app/Services/UserService.php", "laravel") == "high"

    def test_laravel_repository_high(self):
        assert categorize_file("app/Repositories/UserRepository.php", "laravel") == "high"

    def test_middleware_high(self):
        assert categorize_file("app/Http/Middleware/Auth.php", "laravel") == "high"

    def test_nuxt_store_high(self):
        assert categorize_file("store/index.js", "nuxt") == "high"

    def test_migration_high(self):
        assert categorize_file("database/migrations/2024_create_users.php", "laravel") == "high"

    # medium
    def test_component_medium(self):
        assert categorize_file("components/Button.vue", "nuxt") == "medium"

    def test_utility_medium(self):
        assert categorize_file("utils/helpers.ts", "generic") == "medium"

    def test_test_file_medium(self):
        assert categorize_file("tests/Feature/UserTest.php", "laravel") == "medium"

    # low
    def test_lock_file_low(self):
        assert categorize_file("package-lock.json", "generic") == "low"

    def test_asset_low(self):
        assert categorize_file("public/images/logo.png", "generic") == "low"

    def test_generated_css_low(self):
        assert categorize_file("public/css/app.css", "generic") == "low"

    def test_env_example_low(self):
        assert categorize_file(".env.example", "generic") == "low"

    def test_composer_lock_low(self):
        assert categorize_file("composer.lock", "generic") == "low"

    # Additional coverage for uncovered branches
    def test_nextjs_pages_dir_critical(self):
        assert categorize_file("pages/index.tsx", "nextjs") == "critical"

    def test_nextjs_layout_critical(self):
        assert categorize_file("app/layout.tsx", "nextjs") == "critical"

    def test_generic_entry_point_critical(self):
        assert categorize_file("main.py", "generic") == "critical"

    def test_generic_model_dir_critical(self):
        assert categorize_file("models/User.py", "generic") == "critical"

    def test_generic_schema_dir_critical(self):
        assert categorize_file("schemas/user.ts", "generic") == "critical"

    def test_nuxt_composables_high(self):
        assert categorize_file("composables/useAuth.ts", "nuxt") == "high"

    def test_nextjs_lib_high(self):
        assert categorize_file("lib/db.ts", "nextjs") == "high"

    def test_nextjs_src_lib_high(self):
        assert categorize_file("src/lib/utils.ts", "nextjs") == "high"

    def test_express_middleware_high(self):
        assert categorize_file("middleware/auth.js", "express") == "high"

    def test_generic_hooks_high(self):
        assert categorize_file("hooks/useAuth.ts", "generic") == "high"

    def test_generic_migrations_high(self):
        assert categorize_file("migrations/001_init.sql", "generic") == "high"

    def test_spec_test_file_medium(self):
        assert categorize_file("app.spec.ts", "generic") == "medium"

    def test_test_ts_file_medium(self):
        assert categorize_file("app.test.ts", "generic") == "medium"

    def test_test_js_file_medium(self):
        assert categorize_file("app.test.js", "generic") == "medium"

    def test_views_dir_medium(self):
        assert categorize_file("views/home.html", "generic") == "medium"

    def test_layouts_dir_medium(self):
        assert categorize_file("layouts/default.vue", "nuxt") == "medium"

    def test_code_file_default_medium(self):
        """Code file not matching any specific rule → medium"""
        assert categorize_file("config.yaml", "generic") == "medium"

    def test_unknown_extension_low(self):
        """Unknown extension → low"""
        assert categorize_file("data.dat", "generic") == "low"

    def test_public_js_low(self):
        assert categorize_file("public/js/app.js", "generic") == "low"

    def test_vue_pages_critical(self):
        assert categorize_file("pages/about.vue", "vue") == "critical"

    def test_vue_store_high(self):
        assert categorize_file("store/auth.js", "vue") == "high"


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------
class TestEstimateTokens:
    """トークン数推定"""

    def test_basic_estimation(self):
        """1000文字 → 約250トークン"""
        assert estimate_tokens(1000) == 250

    def test_zero_chars(self):
        assert estimate_tokens(0) == 0

    def test_small_file(self):
        assert estimate_tokens(100) == 25

    def test_large_file(self):
        assert estimate_tokens(40000) == 10000


# ---------------------------------------------------------------------------
# scan_directory (integration)
# ---------------------------------------------------------------------------
class TestScanDirectory:
    """ディレクトリスキャンの統合テスト"""

    def test_empty_directory(self, tmp_path):
        result = scan_directory(str(tmp_path))
        assert result["total_files"] == 0
        assert result["categories"]["critical"] == []
        assert result["categories"]["high"] == []
        assert result["categories"]["medium"] == []
        assert result["categories"]["low"] == []
        assert result["read_order"] == []

    def test_excludes_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "express"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("console.log('hi')")
        result = scan_directory(str(tmp_path))
        all_paths = [f["path"] for cat in result["categories"].values() for f in cat]
        assert not any("node_modules" in p for p in all_paths)
        assert result["total_files"] == 1

    def test_excludes_git(self, tmp_path):
        git_dir = tmp_path / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "abc123").write_text("blob")
        (tmp_path / "main.py").write_text("print('hello')")
        result = scan_directory(str(tmp_path))
        all_paths = [f["path"] for cat in result["categories"].values() for f in cat]
        assert not any(".git" in p for p in all_paths)

    def test_excludes_vendor(self, tmp_path):
        vendor = tmp_path / "vendor" / "laravel"
        vendor.mkdir(parents=True)
        (vendor / "framework.php").write_text("<?php")
        (tmp_path / "app.php").write_text("<?php echo 'hi';")
        result = scan_directory(str(tmp_path))
        all_paths = [f["path"] for cat in result["categories"].values() for f in cat]
        assert not any("vendor" in p for p in all_paths)

    def test_read_order_critical_first(self, tmp_path):
        """read_order は critical → high → medium → low の順"""
        (tmp_path / "routes").mkdir()
        (tmp_path / "routes" / "api.php").write_text("<?php Route::get('/', fn() => 'ok');")
        composer = tmp_path / "composer.json"
        composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "Services").mkdir(parents=True)
        (tmp_path / "app" / "Services" / "UserService.php").write_text("<?php class UserService {}")
        (tmp_path / "utils.js").write_text("export default {}")
        (tmp_path / "package-lock.json").write_text("{}")

        result = scan_directory(str(tmp_path))
        order = result["read_order"]
        # critical ファイルが high より前に来ること
        critical_paths = {f["path"] for f in result["categories"]["critical"]}
        high_paths = {f["path"] for f in result["categories"]["high"]}
        if critical_paths and high_paths:
            first_critical_idx = min(order.index(p) for p in critical_paths if p in order)
            first_high_idx = min(order.index(p) for p in high_paths if p in order)
            assert first_critical_idx < first_high_idx

    def test_summary_counts_match(self, tmp_path):
        """summary のカウントが実際のファイル数と一致"""
        (tmp_path / "routes").mkdir()
        (tmp_path / "routes" / "api.php").write_text("<?php")
        composer = tmp_path / "composer.json"
        composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        (tmp_path / "utils.js").write_text("export default {}")

        result = scan_directory(str(tmp_path))
        for cat_name in ["critical", "high", "medium", "low"]:
            assert result["summary"][cat_name] == len(result["categories"][cat_name])

    def test_total_files_correct(self, tmp_path):
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.py").write_text("pass")
        result = scan_directory(str(tmp_path))
        total = sum(len(files) for files in result["categories"].values())
        assert result["total_files"] == total
        assert result["total_files"] == 3

    def test_file_entry_has_required_fields(self, tmp_path):
        (tmp_path / "app.py").write_text("x" * 400)
        result = scan_directory(str(tmp_path))
        all_files = [f for cat in result["categories"].values() for f in cat]
        assert len(all_files) == 1
        entry = all_files[0]
        assert "path" in entry
        assert "size" in entry
        assert "tokens_est" in entry
        assert entry["size"] == 400
        assert entry["tokens_est"] == 100

    def test_project_type_detected(self, tmp_path):
        (tmp_path / "next.config.js").write_text("module.exports = {}")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "page.tsx").write_text("export default function() {}")
        result = scan_directory(str(tmp_path))
        assert "nextjs" in result["project_type"]

    def test_output_json_valid(self, tmp_path):
        """出力が有効な JSON として再パース可能"""
        (tmp_path / "hello.py").write_text("print('hello')")
        result = scan_directory(str(tmp_path))
        serialized = json.dumps(result)
        reparsed = json.loads(serialized)
        assert reparsed["total_files"] == result["total_files"]


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------
class TestPrintSummary:
    """print_summary の出力テスト"""

    def test_prints_project_type(self, capsys, tmp_path):
        (tmp_path / "main.py").write_text("x" * 100)
        manifest = scan_directory(str(tmp_path))
        print_summary(manifest)
        captured = capsys.readouterr()
        assert "generic" in captured.out
        assert "Total files" in captured.out

    def test_prints_category_counts(self, capsys, tmp_path):
        (tmp_path / "routes").mkdir()
        (tmp_path / "routes" / "api.php").write_text("<?php")
        composer = tmp_path / "composer.json"
        composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        manifest = scan_directory(str(tmp_path))
        print_summary(manifest)
        captured = capsys.readouterr()
        assert "critical" in captured.out
        assert "tokens" in captured.out

    def test_prints_estimated_total_tokens(self, capsys, tmp_path):
        (tmp_path / "a.py").write_text("x" * 400)
        manifest = scan_directory(str(tmp_path))
        print_summary(manifest)
        captured = capsys.readouterr()
        assert "Estimated total tokens" in captured.out


# ---------------------------------------------------------------------------
# main (unit)
# ---------------------------------------------------------------------------
class TestMain:
    """main() 関数の直接テスト"""

    def test_main_with_output(self, tmp_path, monkeypatch):
        """main() を直接呼び出して --output で JSON を書き出す"""
        from scan_sources import main

        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "app.py").write_text("print('hi')")
        output_file = tmp_path / "out.json"

        monkeypatch.setattr(
            "sys.argv",
            ["scan_sources.py", "--source-dir", str(source_dir), "--output", str(output_file)],
        )
        main()
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["total_files"] == 1

    def test_main_without_output(self, tmp_path, monkeypatch, capsys):
        """--output なしで stdout に JSON を出力"""
        from scan_sources import main

        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "hello.py").write_text("pass")

        monkeypatch.setattr(
            "sys.argv",
            ["scan_sources.py", "--source-dir", str(source_dir)],
        )
        main()
        captured = capsys.readouterr()
        # stdout contains the summary followed by the JSON manifest
        assert "total_files" in captured.out
        assert '"project_type"' in captured.out

    def test_main_invalid_dir(self, tmp_path, monkeypatch):
        """存在しないディレクトリでエラー終了"""
        from scan_sources import main

        monkeypatch.setattr(
            "sys.argv",
            ["scan_sources.py", "--source-dir", str(tmp_path / "nonexistent")],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI (integration)
# ---------------------------------------------------------------------------
class TestCLI:
    """CLI インターフェースのテスト"""

    def test_cli_output_flag(self, tmp_path):
        """--output フラグで JSON ファイルを書き出す"""
        import subprocess

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "main.py").write_text("print('hello')")
        output_file = tmp_path / "manifest.json"

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "scan_sources.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir",
                str(source_dir),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["total_files"] == 1

    def test_cli_prints_summary(self, tmp_path):
        """サマリーが標準出力に表示される"""
        import subprocess

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "main.py").write_text("print('hello')")

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "scan_sources.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir",
                str(source_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "total" in result.stdout.lower() or "Total" in result.stdout

    def test_cli_missing_source_dir(self):
        """--source-dir なしでエラー"""
        import subprocess

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "scan_sources.py"
        )
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
