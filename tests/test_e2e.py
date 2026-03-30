"""E2E テスト: スクリプトパイプライン全体の統合テスト

TDD: RED phase - テストを先に書く

サンプルプロジェクトとサンプルドキュメントに対して
各スクリプトを順番に実行し、期待通りの結果が得られることを確認する。
"""

import json
import os
import subprocess
import sys
import zipfile

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_PROJECT = os.path.join(FIXTURES_DIR, "sample-project")
SAMPLE_DOCS = os.path.join(FIXTURES_DIR, "sample-docs")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


def run_script(script_name, args):
    """ヘルパー: スクリプトを実行して結果を返す"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    result = subprocess.run(
        [sys.executable, script_path] + args,
        capture_output=True,
        text=True,
    )
    return result


# ---------------------------------------------------------------------------
# scan_sources.py
# ---------------------------------------------------------------------------
class TestScanSourcesE2E:
    """scan_sources.py のE2Eテスト"""

    def test_scan_produces_valid_manifest(self, tmp_path):
        """サンプルプロジェクトのスキャンで有効なマニフェストが生成される"""
        output_file = str(tmp_path / "manifest.json")
        result = run_script("scan_sources.py", [
            "--source-dir", SAMPLE_PROJECT,
            "--output", output_file,
        ])

        assert result.returncode == 0
        assert os.path.exists(output_file)

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "project_type" in manifest
        assert "express" in manifest["project_type"]
        assert manifest["total_files"] > 0
        assert len(manifest["read_order"]) > 0

    def test_scan_detects_express_project(self, tmp_path):
        """Express プロジェクトとして検出される"""
        output_file = str(tmp_path / "manifest.json")
        result = run_script("scan_sources.py", [
            "--source-dir", SAMPLE_PROJECT,
            "--output", output_file,
        ])

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "express" in manifest["project_type"]

    def test_scan_categorizes_routes_as_critical(self, tmp_path):
        """routes/ ディレクトリが critical に分類される"""
        output_file = str(tmp_path / "manifest.json")
        run_script("scan_sources.py", [
            "--source-dir", SAMPLE_PROJECT,
            "--output", output_file,
        ])

        with open(output_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        critical_paths = [f["path"] for f in manifest["categories"]["critical"]]
        assert any("routes/" in p for p in critical_paths)


# ---------------------------------------------------------------------------
# check_links.py
# ---------------------------------------------------------------------------
class TestCheckLinksE2E:
    """check_links.py のE2Eテスト"""

    def test_no_broken_links_in_sample_docs(self):
        """サンプルドキュメントにリンク切れがないこと"""
        result = run_script("check_links.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# check_consistency.py
# ---------------------------------------------------------------------------
class TestCheckConsistencyE2E:
    """check_consistency.py のE2Eテスト"""

    def test_no_consistency_errors_in_sample_docs(self):
        """サンプルドキュメントに用語不整合がないこと"""
        result = run_script("check_consistency.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# check_slide_overflow.py
# ---------------------------------------------------------------------------
class TestCheckSlideOverflowE2E:
    """check_slide_overflow.py のE2Eテスト"""

    def test_no_overflow_issues_in_sample_docs(self):
        """サンプルドキュメントにスライド溢れがないこと"""
        result = run_script("check_slide_overflow.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# validate.py
# ---------------------------------------------------------------------------
class TestValidateE2E:
    """validate.py のE2Eテスト"""

    def test_validate_passes_on_sample_docs(self):
        """サンプルドキュメントのバリデーションが通ること"""
        result = run_script("validate.py", [
            "--name", "sample-app",
            "--output-dir", SAMPLE_DOCS,
        ])
        assert result.returncode == 0
        assert "FAIL" not in result.stdout or "バリデーション完了（問題なし）" in result.stdout


# ---------------------------------------------------------------------------
# package.py
# ---------------------------------------------------------------------------
class TestPackageE2E:
    """package.py のE2Eテスト"""

    def test_package_creates_valid_zip(self, tmp_path):
        """パッケージスクリプトが有効な ZIP を生成する"""
        # package.py requires a site/ directory (MkDocs output)
        # Create a minimal site/ for testing
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html><body>Sample</body></html>")

        output_zip = str(tmp_path / "output.zip")
        result = run_script("package.py", [
            "--docs-dir", SAMPLE_DOCS,
            "--site-dir", str(site_dir),
            "--output", output_zip,
        ])

        assert result.returncode == 0
        assert os.path.exists(output_zip)

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert any(n.startswith("html/") for n in names)
            assert "README.txt" in names


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
class TestFullPipelineE2E:
    """スクリプトパイプライン全体の統合テスト"""

    def test_full_pipeline_on_sample_project(self, tmp_path):
        """全スクリプトをサンプルプロジェクトに対して順番に実行"""
        # Step 1: scan_sources
        manifest_file = str(tmp_path / "manifest.json")
        r1 = run_script("scan_sources.py", [
            "--source-dir", SAMPLE_PROJECT,
            "--output", manifest_file,
        ])
        assert r1.returncode == 0, f"scan_sources failed: {r1.stderr}"

        # Step 2: check_links
        r2 = run_script("check_links.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert r2.returncode == 0, f"check_links failed: {r2.stderr}"

        # Step 3: check_consistency
        r3 = run_script("check_consistency.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert r3.returncode == 0, f"check_consistency failed: {r3.stderr}"

        # Step 4: check_slide_overflow
        r4 = run_script("check_slide_overflow.py", [
            "--docs-dir", SAMPLE_DOCS,
        ])
        assert r4.returncode == 0, f"check_slide_overflow failed: {r4.stderr}"

        # Step 5: validate
        r5 = run_script("validate.py", [
            "--name", "sample-app",
            "--output-dir", SAMPLE_DOCS,
        ])
        assert r5.returncode == 0, f"validate failed: {r5.stderr}"

        # Step 6: package
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html><body>Docs</body></html>")
        output_zip = str(tmp_path / "output.zip")

        r6 = run_script("package.py", [
            "--docs-dir", SAMPLE_DOCS,
            "--site-dir", str(site_dir),
            "--output", output_zip,
        ])
        assert r6.returncode == 0, f"package failed: {r6.stderr}"
        assert os.path.exists(output_zip)
