"""save_output.py のテスト"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from save_output import count_unverified_decisions, parse_files, resolve_path, write_files


class TestParseFiles:
    """--- FILE: パス --- 形式のパースをテスト"""

    def test_valid_input(self):
        text = (
            "--- FILE: docs/architecture/test.md ---\n"
            "# Test\n"
            "content here\n"
            "--- FILE: docs/diagrams/test.mmd ---\n"
            "flowchart TD\n"
        )
        files = parse_files(text)
        assert len(files) == 2
        assert files[0]["path"] == "docs/architecture/test.md"
        assert "# Test" in files[0]["content"]
        assert files[1]["path"] == "docs/diagrams/test.mmd"

    def test_empty_input(self):
        files = parse_files("")
        assert files == []

    def test_no_file_markers(self):
        files = parse_files("just some text without markers")
        assert files == []

    def test_single_file(self):
        text = "--- FILE: docs/test.md ---\ncontent"
        files = parse_files(text)
        assert len(files) == 1


class TestResolvePath:
    """パス解決のテスト（セキュリティ含む）"""

    def test_normal_path(self):
        result = resolve_path("docs/architecture/test.md", "/output")
        assert result == os.path.join("/output", "architecture", "test.md")

    def test_strips_docs_prefix(self):
        result = resolve_path("docs/meta/test.yaml", "/output")
        assert "docs/docs" not in result
        assert result.endswith("meta/test.yaml")

    def test_path_without_docs_prefix(self):
        result = resolve_path("architecture/test.md", "/output")
        assert result == os.path.join("/output", "architecture", "test.md")

    def test_path_traversal_blocked(self):
        """../../ によるパストラバーサルをブロック"""
        with pytest.raises(ValueError, match="outside output directory"):
            resolve_path("../../etc/cron.d/evil", "/output")

    def test_path_traversal_with_docs_prefix_blocked(self):
        """docs/../../../ によるパストラバーサルをブロック"""
        with pytest.raises(ValueError, match="outside output directory"):
            resolve_path("docs/../../../etc/passwd", "/output")

    def test_absolute_path_blocked(self):
        """絶対パスの指定をブロック"""
        with pytest.raises(ValueError, match="outside output directory"):
            resolve_path("/etc/passwd", "/output")

    def test_stays_within_output_dir(self):
        """正常なパスが output_dir 内に収まる"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_path("docs/architecture/feature.md", tmpdir)
            assert result.startswith(tmpdir)


class TestResolvePathEdgeCases:
    """resolve_path の境界値テスト"""

    def test_deeply_nested_path(self):
        result = resolve_path("docs/explanations/feature/pro.md", "/output")
        assert result == os.path.join("/output", "explanations", "feature", "pro.md")

    def test_dot_in_filename(self):
        result = resolve_path("docs/architecture/my.feature.rag.md", "/output")
        assert result.endswith("my.feature.rag.md")

    def test_traversal_disguised_in_middle(self):
        """中間の ../ もブロック"""
        with pytest.raises(ValueError, match="outside output directory"):
            resolve_path("docs/architecture/../../secret.md", "/output")


class TestWriteFiles:
    """write_files のテスト"""

    def test_write_new_files(self, tmp_path):
        files = [
            {"path": "docs/architecture/test.md", "content": "# Test\n"},
            {"path": "docs/diagrams/test.mmd", "content": "flowchart TD\n"},
        ]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=False, force=True
        )
        assert written == 2
        assert skipped == 0
        assert (tmp_path / "architecture" / "test.md").read_text() == "# Test\n"
        assert (tmp_path / "diagrams" / "test.mmd").read_text() == "flowchart TD\n"

    def test_dry_run_does_not_write(self, tmp_path):
        files = [{"path": "docs/test.md", "content": "content\n"}]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=True, force=False
        )
        assert written == 1
        assert not (tmp_path / "test.md").exists()

    def test_traversal_skipped(self, tmp_path):
        files = [{"path": "../../evil.md", "content": "evil\n"}]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=False, force=True
        )
        assert written == 0
        assert skipped == 1

    def test_force_overwrites(self, tmp_path):
        (tmp_path / "test.md").write_text("old\n")
        files = [{"path": "test.md", "content": "new\n"}]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=False, force=True
        )
        assert written == 1
        assert (tmp_path / "test.md").read_text() == "new\n"

    def test_decisions_warning(self, tmp_path):
        files = [
            {
                "path": "docs/decisions/test.md",
                "content": "| 1 | 判断 | 未確認 |\n| 2 | 判断 | 未確認 |\n",
            }
        ]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=False, force=True
        )
        assert written == 1
        assert len(warnings) == 1
        assert "2件" in warnings[0]

    def test_mixed_safe_and_unsafe(self, tmp_path):
        files = [
            {"path": "docs/architecture/safe.md", "content": "safe\n"},
            {"path": "../../etc/evil", "content": "evil\n"},
            {"path": "docs/diagrams/also-safe.mmd", "content": "graph\n"},
        ]
        written, skipped, warnings = write_files(
            files, str(tmp_path), dry_run=False, force=True
        )
        assert written == 2
        assert skipped == 1


class TestCountUnverifiedDecisions:
    def test_count_multiple(self):
        assert count_unverified_decisions("未確認\n未確認\n確認済み") == 2

    def test_count_zero(self):
        assert count_unverified_decisions("確認済み") == 0

    def test_empty_string(self):
        assert count_unverified_decisions("") == 0
