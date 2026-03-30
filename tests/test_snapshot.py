"""snapshot.py のテスト

TDD: RED phase - テストを先に書く
"""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from snapshot import create_snapshot, compare_snapshots, main, _hash_file


# ---------------------------------------------------------------------------
# create_snapshot
# ---------------------------------------------------------------------------
class TestCreateSnapshot:
    """スナップショット作成"""

    def test_creates_valid_json(self, tmp_path):
        """生成されたスナップショットが有効な JSON 構造を持つ"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        snapshot = create_snapshot(str(docs_dir))

        assert "files" in snapshot
        assert "created_at" in snapshot
        assert isinstance(snapshot["files"], dict)
        assert isinstance(snapshot["created_at"], str)

    def test_contains_all_files(self, tmp_path):
        """ディレクトリ内の全ファイルがスナップショットに含まれる"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "a.md").write_text("file a")
        (docs_dir / "b.md").write_text("file b")
        sub = docs_dir / "sub"
        sub.mkdir()
        (sub / "c.md").write_text("file c")

        snapshot = create_snapshot(str(docs_dir))

        assert len(snapshot["files"]) == 3
        # Relative paths should be used
        paths = set(snapshot["files"].keys())
        assert "a.md" in paths
        assert "b.md" in paths
        assert os.path.join("sub", "c.md") in paths or "sub/c.md" in paths

    def test_sha256_hashes_are_correct(self, tmp_path):
        """SHA256 ハッシュが正しいこと"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        content = "Hello, World!"
        (docs_dir / "test.md").write_text(content)

        snapshot = create_snapshot(str(docs_dir))

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert snapshot["files"]["test.md"] == expected_hash

    def test_empty_directory_produces_empty_snapshot(self, tmp_path):
        """空ディレクトリでは空のスナップショットが生成される"""
        docs_dir = tmp_path / "empty_docs"
        docs_dir.mkdir()

        snapshot = create_snapshot(str(docs_dir))

        assert snapshot["files"] == {}
        assert "created_at" in snapshot

    def test_snapshot_has_iso_timestamp(self, tmp_path):
        """created_at が ISO フォーマットの日時であること"""
        from datetime import datetime

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "a.md").write_text("test")

        snapshot = create_snapshot(str(docs_dir))

        # Should not raise
        datetime.fromisoformat(snapshot["created_at"])


# ---------------------------------------------------------------------------
# compare_snapshots
# ---------------------------------------------------------------------------
class TestCompareSnapshots:
    """スナップショット比較"""

    def test_identical_snapshots_no_changes(self):
        """同一のスナップショット比較 → 変更なし"""
        snapshot = {
            "files": {"a.md": "abc123", "b.md": "def456"},
            "created_at": "2026-01-01T00:00:00",
        }

        result = compare_snapshots(snapshot, snapshot)

        assert result["added"] == []
        assert result["removed"] == []
        assert result["changed"] == []
        assert result["has_changes"] is False

    def test_added_file_reported(self):
        """新規ファイルが追加として報告される"""
        old = {
            "files": {"a.md": "abc123"},
            "created_at": "2026-01-01T00:00:00",
        }
        new = {
            "files": {"a.md": "abc123", "b.md": "def456"},
            "created_at": "2026-01-02T00:00:00",
        }

        result = compare_snapshots(old, new)

        assert "b.md" in result["added"]
        assert result["removed"] == []
        assert result["changed"] == []
        assert result["has_changes"] is True

    def test_removed_file_reported(self):
        """削除されたファイルが報告される"""
        old = {
            "files": {"a.md": "abc123", "b.md": "def456"},
            "created_at": "2026-01-01T00:00:00",
        }
        new = {
            "files": {"a.md": "abc123"},
            "created_at": "2026-01-02T00:00:00",
        }

        result = compare_snapshots(old, new)

        assert result["added"] == []
        assert "b.md" in result["removed"]
        assert result["changed"] == []
        assert result["has_changes"] is True

    def test_changed_file_reported(self):
        """変更されたファイルが報告される"""
        old = {
            "files": {"a.md": "abc123"},
            "created_at": "2026-01-01T00:00:00",
        }
        new = {
            "files": {"a.md": "xyz789"},
            "created_at": "2026-01-02T00:00:00",
        }

        result = compare_snapshots(old, new)

        assert result["added"] == []
        assert result["removed"] == []
        assert "a.md" in result["changed"]
        assert result["has_changes"] is True

    def test_mixed_changes_all_reported(self):
        """追加・削除・変更の混合がすべて報告される"""
        old = {
            "files": {
                "keep.md": "same_hash",
                "change.md": "old_hash",
                "remove.md": "remove_hash",
            },
            "created_at": "2026-01-01T00:00:00",
        }
        new = {
            "files": {
                "keep.md": "same_hash",
                "change.md": "new_hash",
                "added.md": "added_hash",
            },
            "created_at": "2026-01-02T00:00:00",
        }

        result = compare_snapshots(old, new)

        assert "added.md" in result["added"]
        assert "remove.md" in result["removed"]
        assert "change.md" in result["changed"]
        assert "keep.md" not in result["added"]
        assert "keep.md" not in result["removed"]
        assert "keep.md" not in result["changed"]
        assert result["has_changes"] is True


# ---------------------------------------------------------------------------
# _hash_file
# ---------------------------------------------------------------------------
class TestHashFile:
    """ファイルハッシュ計算"""

    def test_hash_matches_hashlib(self, tmp_path):
        """_hash_file の結果が hashlib.sha256 と一致"""
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert _hash_file(str(f)) == expected

    def test_empty_file_hash(self, tmp_path):
        """空ファイルのハッシュ"""
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert _hash_file(str(f)) == expected


# ---------------------------------------------------------------------------
# main() direct tests
# ---------------------------------------------------------------------------
class TestMainDirect:
    """main() 関数の直接テスト"""

    def test_main_create(self, tmp_path, monkeypatch, capsys):
        """main() create アクション"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")
        snapshot_dir = tmp_path / ".snapshots"

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "create", "--snapshot-dir", str(snapshot_dir)],
        )
        main()
        captured = capsys.readouterr()
        assert "Snapshot created" in captured.out
        assert snapshot_dir.exists()

    def test_main_compare_no_changes(self, tmp_path, monkeypatch, capsys):
        """main() compare で変更なし → exit 0"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        baseline = tmp_path / "baseline.json"
        snap = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snap, ensure_ascii=False))

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "compare", "--baseline", str(baseline)],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_compare_with_changes(self, tmp_path, monkeypatch, capsys):
        """main() compare で変更あり → exit 1"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        baseline = tmp_path / "baseline.json"
        snap = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snap, ensure_ascii=False))

        (docs_dir / "readme.md").write_text("# Changed!")

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "compare", "--baseline", str(baseline)],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_compare_missing_baseline(self, tmp_path, monkeypatch):
        """main() compare でベースラインなし → exit 2"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "compare"],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_compare_nonexistent_baseline(self, tmp_path, monkeypatch):
        """main() compare で存在しないベースライン → exit 2"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "compare",
             "--baseline", str(tmp_path / "nonexistent.json")],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_main_compare_reports_added_and_removed(self, tmp_path, monkeypatch, capsys):
        """main() compare で追加・削除が報告される"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "keep.md").write_text("keep")
        (docs_dir / "remove.md").write_text("remove")

        baseline = tmp_path / "baseline.json"
        snap = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snap, ensure_ascii=False))

        # Remove one file, add another
        os.remove(str(docs_dir / "remove.md"))
        (docs_dir / "added.md").write_text("new")

        monkeypatch.setattr(
            "sys.argv",
            ["snapshot.py", "--docs-dir", str(docs_dir),
             "--action", "compare", "--baseline", str(baseline)],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Added" in captured.out
        assert "Removed" in captured.out


# ---------------------------------------------------------------------------
# CLI (subprocess)
# ---------------------------------------------------------------------------
class TestCLI:
    """CLI インターフェースのテスト"""

    def test_cli_create_action(self, tmp_path):
        """--action create でスナップショット作成"""
        import subprocess

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")
        snapshot_dir = tmp_path / ".snapshots"

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "snapshot.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--docs-dir", str(docs_dir),
                "--action", "create",
                "--snapshot-dir", str(snapshot_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Snapshot file should be created
        json_files = list(snapshot_dir.glob("snapshot-*.json"))
        assert len(json_files) >= 1

    def test_cli_compare_no_changes_exit_0(self, tmp_path):
        """変更なしの場合 exit code 0"""
        import subprocess

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        # Create baseline snapshot
        baseline = tmp_path / "baseline.json"
        snapshot_data = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snapshot_data, ensure_ascii=False))

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "snapshot.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--docs-dir", str(docs_dir),
                "--action", "compare",
                "--baseline", str(baseline),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_compare_with_changes_exit_1(self, tmp_path):
        """変更ありの場合 exit code 1"""
        import subprocess

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        # Create baseline snapshot
        baseline = tmp_path / "baseline.json"
        snapshot_data = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snapshot_data, ensure_ascii=False))

        # Modify a file
        (docs_dir / "readme.md").write_text("# Changed!")

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "snapshot.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--docs-dir", str(docs_dir),
                "--action", "compare",
                "--baseline", str(baseline),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_cli_compare_added_file_exit_1(self, tmp_path):
        """ファイル追加時 exit code 1"""
        import subprocess

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        baseline = tmp_path / "baseline.json"
        snapshot_data = create_snapshot(str(docs_dir))
        baseline.write_text(json.dumps(snapshot_data, ensure_ascii=False))

        # Add a new file
        (docs_dir / "new_file.md").write_text("New content")

        script = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "snapshot.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                script,
                "--docs-dir", str(docs_dir),
                "--action", "compare",
                "--baseline", str(baseline),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
