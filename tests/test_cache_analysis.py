"""cache_analysis.py のテスト

TDD: RED phase - テストを先に書く
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from cache_analysis import (
    save_cache,
    load_cache,
    is_cache_valid,
    clear_cache,
    _compute_cache_key,
    _gather_analysis_data,
    _get_git_commit_hash,
    main,
)


# ---------------------------------------------------------------------------
# save_cache / load_cache round-trip
# ---------------------------------------------------------------------------
class TestSaveAndLoadCache:
    """save_cache で保存したデータを load_cache で復元できることを確認"""

    def test_save_then_load_returns_same_data(self, tmp_path, monkeypatch):
        """保存したデータがそのまま戻ること"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"
        monkeypatch.setenv("CACHE_DIR", str(cache_dir))

        data = {
            "file_list": ["main.py", "utils.py"],
            "project_type": "generic",
            "directory_structure": {"src": ["main.py"]},
            "key_files_summary": {"main.py": "entry point"},
        }
        save_cache(str(source_dir), data, cache_base=str(cache_dir))
        loaded = load_cache(str(source_dir), cache_base=str(cache_dir))

        assert loaded is not None
        assert loaded["file_list"] == data["file_list"]
        assert loaded["project_type"] == data["project_type"]
        assert loaded["directory_structure"] == data["directory_structure"]
        assert loaded["key_files_summary"] == data["key_files_summary"]

    def test_load_nonexistent_returns_none(self, tmp_path):
        """存在しないキャッシュは None を返す"""
        cache_dir = tmp_path / ".cache"
        result = load_cache("/nonexistent/path", cache_base=str(cache_dir))
        assert result is None

    def test_cache_directory_auto_created(self, tmp_path):
        """キャッシュディレクトリが自動作成される"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / "new_cache_dir"

        save_cache(str(source_dir), {"test": True}, cache_base=str(cache_dir))
        assert cache_dir.exists()
        assert cache_dir.is_dir()


# ---------------------------------------------------------------------------
# is_cache_valid
# ---------------------------------------------------------------------------
class TestIsCacheValid:
    """キャッシュの有効性チェック"""

    def test_fresh_cache_is_valid(self, tmp_path):
        """保存直後のキャッシュは有効"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        save_cache(str(source_dir), {"test": True}, cache_base=str(cache_dir))
        assert is_cache_valid(str(source_dir), max_age_seconds=3600, cache_base=str(cache_dir)) is True

    def test_stale_cache_is_invalid(self, tmp_path):
        """max_age_seconds=0 だと即座に失効"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        save_cache(str(source_dir), {"test": True}, cache_base=str(cache_dir))
        # max_age_seconds=0 → 即座に無効
        time.sleep(0.1)
        assert is_cache_valid(str(source_dir), max_age_seconds=0, cache_base=str(cache_dir)) is False

    def test_no_cache_is_invalid(self, tmp_path):
        """キャッシュが存在しない場合は無効"""
        cache_dir = tmp_path / ".cache"
        assert is_cache_valid("/no/such/dir", max_age_seconds=3600, cache_base=str(cache_dir)) is False


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------
class TestClearCache:
    """キャッシュ全削除"""

    def test_clear_cache_removes_all_files(self, tmp_path):
        """clear_cache で全キャッシュファイルが削除される"""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "analysis-abc123.json").write_text("{}")
        (cache_dir / "analysis-def456.json").write_text("{}")

        clear_cache(cache_base=str(cache_dir))

        json_files = list(cache_dir.glob("analysis-*.json"))
        assert len(json_files) == 0

    def test_clear_cache_on_nonexistent_dir(self, tmp_path):
        """存在しないディレクトリでもエラーにならない"""
        cache_dir = tmp_path / "nonexistent_cache"
        # Should not raise
        clear_cache(cache_base=str(cache_dir))


# ---------------------------------------------------------------------------
# _compute_cache_key (hash)
# ---------------------------------------------------------------------------
class TestComputeCacheKey:
    """キャッシュキーのハッシュ計算"""

    def test_hash_changes_when_git_commit_changes(self, tmp_path, monkeypatch):
        """git commit が変わるとハッシュも変わる"""
        source_dir = str(tmp_path / "project")

        # Mock subprocess.run to return different git hashes
        import subprocess

        call_count = {"n": 0}

        def mock_run(*args, **kwargs):
            call_count["n"] += 1
            result = subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")
            if call_count["n"] <= 1:
                result.stdout = "abc123\n"
            else:
                result.stdout = "def456\n"
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        key1 = _compute_cache_key(source_dir)
        key2 = _compute_cache_key(source_dir)

        assert key1 != key2

    def test_same_inputs_produce_same_hash(self, tmp_path, monkeypatch):
        """同じ入力で同じハッシュが生成される"""
        source_dir = str(tmp_path / "project")

        import subprocess

        def mock_run(*args, **kwargs):
            result = subprocess.CompletedProcess(args=args[0], returncode=0, stdout="abc123\n", stderr="")
            return result

        monkeypatch.setattr("subprocess.run", mock_run)

        key1 = _compute_cache_key(source_dir)
        key2 = _compute_cache_key(source_dir)

        assert key1 == key2


# ---------------------------------------------------------------------------
# Cache file format
# ---------------------------------------------------------------------------
class TestCacheFileFormat:
    """キャッシュファイルのフォーマット"""

    def test_cache_file_is_valid_json(self, tmp_path):
        """キャッシュファイルが有効な JSON であること"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        data = {"file_list": ["a.py"], "project_type": "generic"}
        save_cache(str(source_dir), data, cache_base=str(cache_dir))

        # Find the cache file
        json_files = list(cache_dir.glob("analysis-*.json"))
        assert len(json_files) == 1

        with open(json_files[0], "r", encoding="utf-8") as f:
            parsed = json.load(f)

        assert "data" in parsed
        assert "created_at" in parsed
        assert parsed["data"]["file_list"] == ["a.py"]


# ---------------------------------------------------------------------------
# _gather_analysis_data
# ---------------------------------------------------------------------------
class TestGatherAnalysisData:
    """解析データ収集"""

    def test_gathers_file_list(self, tmp_path):
        """ファイルリストが収集される"""
        (tmp_path / "app.py").write_text("print('hi')")
        (tmp_path / "utils.py").write_text("pass")

        data = _gather_analysis_data(str(tmp_path))

        assert "app.py" in data["file_list"]
        assert "utils.py" in data["file_list"]

    def test_gathers_directory_structure(self, tmp_path):
        """ディレクトリ構造が収集される"""
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("pass")

        data = _gather_analysis_data(str(tmp_path))

        assert "src" in data["directory_structure"]

    def test_detects_express_project(self, tmp_path):
        """Express プロジェクトが検出される"""
        import json as _json
        (tmp_path / "package.json").write_text(
            _json.dumps({"dependencies": {"express": "^4.18.0"}})
        )

        data = _gather_analysis_data(str(tmp_path))
        assert data["project_type"] == "express"

    def test_generic_project(self, tmp_path):
        """フレームワークなしは generic"""
        (tmp_path / "main.py").write_text("print('hi')")

        data = _gather_analysis_data(str(tmp_path))
        assert data["project_type"] == "generic"

    def test_excludes_node_modules(self, tmp_path):
        """node_modules は除外される"""
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")
        (tmp_path / "app.js").write_text("const x = 1;")

        data = _gather_analysis_data(str(tmp_path))
        assert not any("node_modules" in f for f in data["file_list"])


# ---------------------------------------------------------------------------
# _get_git_commit_hash
# ---------------------------------------------------------------------------
class TestGetGitCommitHash:
    """git commit ハッシュ取得"""

    def test_returns_empty_for_non_git_dir(self, tmp_path):
        """git リポジトリでないディレクトリは空文字を返す"""
        result = _get_git_commit_hash(str(tmp_path))
        assert result == ""

    def test_returns_string(self, tmp_path):
        """戻り値が文字列であること"""
        result = _get_git_commit_hash(str(tmp_path))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class TestCLI:
    """CLI インターフェースのテスト"""

    def test_main_save_action(self, tmp_path, monkeypatch, capsys):
        """main() を直接呼び出して save アクション"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        (source_dir / "app.py").write_text("print('hi')")
        cache_dir = tmp_path / ".cache"

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(source_dir),
             "--action", "save", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "Cache saved" in captured.out
        assert cache_dir.exists()

    def test_main_load_no_cache(self, tmp_path, monkeypatch, capsys):
        """main() load で キャッシュなし"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(source_dir),
             "--action", "load", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "No cache found" in captured.out

    def test_main_load_with_cache(self, tmp_path, monkeypatch, capsys):
        """main() load で キャッシュあり"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        save_cache(str(source_dir), {"test": True}, cache_base=str(cache_dir))

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(source_dir),
             "--action", "load", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "test" in captured.out

    def test_main_check_valid(self, tmp_path, monkeypatch, capsys):
        """main() check で有効なキャッシュ"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        save_cache(str(source_dir), {"test": True}, cache_base=str(cache_dir))

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(source_dir),
             "--action", "check", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "Cache is valid" in captured.out

    def test_main_check_invalid(self, tmp_path, monkeypatch, capsys):
        """main() check で無効なキャッシュ"""
        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(source_dir),
             "--action", "check", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "invalid or missing" in captured.out

    def test_main_clear(self, tmp_path, monkeypatch, capsys):
        """main() clear アクション"""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "analysis-aaa.json").write_text("{}")

        monkeypatch.setattr(
            "sys.argv",
            ["cache_analysis.py", "--source-dir", str(tmp_path),
             "--action", "clear", "--cache-dir", str(cache_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "Cleared" in captured.out

    def test_cli_save_action(self, tmp_path):
        """--action save で保存"""
        import subprocess

        source_dir = tmp_path / "project"
        source_dir.mkdir()
        (source_dir / "main.py").write_text("print('hi')")
        cache_dir = tmp_path / ".cache"

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "cache_analysis.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir", str(source_dir),
                "--action", "save",
                "--cache-dir", str(cache_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_load_action(self, tmp_path):
        """--action load でロード"""
        import subprocess

        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "cache_analysis.py"
        )
        # Load without prior save → should indicate no cache
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir", str(source_dir),
                "--action", "load",
                "--cache-dir", str(cache_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_check_action(self, tmp_path):
        """--action check でキャッシュ有効性チェック"""
        import subprocess

        source_dir = tmp_path / "project"
        source_dir.mkdir()
        cache_dir = tmp_path / ".cache"

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "cache_analysis.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir", str(source_dir),
                "--action", "check",
                "--cache-dir", str(cache_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_clear_action(self, tmp_path):
        """--action clear でキャッシュ全削除"""
        import subprocess

        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "analysis-abc.json").write_text("{}")

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "cache_analysis.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--source-dir", str(tmp_path),
                "--action", "clear",
                "--cache-dir", str(cache_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert len(list(cache_dir.glob("analysis-*.json"))) == 0
