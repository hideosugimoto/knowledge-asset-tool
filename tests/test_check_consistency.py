"""check_consistency.py のテスト"""

import json
import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from check_consistency import (
    KNOWN_INCONSISTENCIES,
    Finding,
    check_file,
    load_custom_patterns,
    scan_directory,
    strip_code_blocks,
)


class TestStripCodeBlocks:
    """コードブロック除去のテスト"""

    def test_removes_fenced_code_block(self):
        text = textwrap.dedent("""\
            Some text before.
            ```python
            recieve = get_data()
            ```
            Some text after.
        """)
        result = strip_code_blocks(text)
        assert "recieve" not in result
        assert "Some text before." in result
        assert "Some text after." in result

    def test_preserves_non_code_content(self):
        text = "This has no code blocks at all."
        result = strip_code_blocks(text)
        assert result == text

    def test_removes_multiple_code_blocks(self):
        text = textwrap.dedent("""\
            Before first.
            ```
            code block 1
            ```
            Between blocks.
            ```js
            code block 2
            ```
            After last.
        """)
        result = strip_code_blocks(text)
        assert "code block 1" not in result
        assert "code block 2" not in result
        assert "Before first." in result
        assert "Between blocks." in result
        assert "After last." in result

    def test_empty_string(self):
        assert strip_code_blocks("") == ""

    def test_unclosed_code_block_treated_as_code(self):
        text = textwrap.dedent("""\
            Before.
            ```
            unclosed code with recieve
        """)
        result = strip_code_blocks(text)
        assert "recieve" not in result


class TestCheckFile:
    """単一ファイルのチェックテスト"""

    def test_clean_file_no_findings(self, tmp_path):
        md = tmp_path / "clean.md"
        md.write_text("This document has no terminology issues.\n")
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert findings == []

    def test_detects_typo_inconsistency(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("The Seting page is used here.\n")
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert len(findings) >= 1
        f = findings[0]
        assert f.found == "Seting"
        assert f.expected == "Setting"
        assert f.line_number == 1
        assert f.level == "error"

    def test_detects_known_code_typo(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("We need to recieve the data.\n")
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert len(findings) >= 1
        f = [x for x in findings if x.found == "recieve"][0]
        assert f.expected == "receive"

    def test_skips_content_inside_code_blocks(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text(textwrap.dedent("""\
            Normal text here.
            ```python
            path = "/info/"
            recieve = get_data()
            ```
            More normal text.
        """))
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert findings == []

    def test_multiple_inconsistencies_in_one_file(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text(textwrap.dedent("""\
            The Seting page is wrong.
            Also recieve is misspelled.
            And caculate is wrong too.
        """))
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert len(findings) >= 3
        found_terms = {f.found for f in findings}
        assert "Seting" in found_terms
        assert "recieve" in found_terms
        assert "caculate" in found_terms

    def test_reports_correct_line_numbers(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("line one\nline two has Seting\nline three\n")
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        assert len(findings) == 1
        assert findings[0].line_number == 2

    def test_case_sensitive_matching(self, tmp_path):
        """パターンは大文字小文字を区別してマッチすること"""
        md = tmp_path / "doc.md"
        md.write_text("This mentions SETING in uppercase.\n")
        # "Seting" pattern should not match "SETING" by default
        findings = check_file(str(md), KNOWN_INCONSISTENCIES)
        seting_findings = [f for f in findings if "seting" in f.found.lower()]
        # Built-in pattern is "Seting" - uppercase SETING should not match
        assert len(seting_findings) == 0

    def test_custom_patterns_applied(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("The custmer is important.\n")
        custom = [
            {"wrong": "custmer", "correct": "customer", "context": "typo"}
        ]
        findings = check_file(str(md), custom)
        assert len(findings) == 1
        assert findings[0].found == "custmer"
        assert findings[0].expected == "customer"


class TestLoadCustomPatterns:
    """カスタムパターンファイル読み込みのテスト"""

    def test_loads_valid_json(self, tmp_path):
        pf = tmp_path / "patterns.json"
        pf.write_text(json.dumps([
            {"wrong": "foo", "correct": "bar", "context": "test"}
        ]))
        patterns = load_custom_patterns(str(pf))
        assert len(patterns) == 1
        assert patterns[0]["wrong"] == "foo"
        assert patterns[0]["correct"] == "bar"

    def test_invalid_json_raises(self, tmp_path):
        pf = tmp_path / "patterns.json"
        pf.write_text("not valid json{{{")
        with pytest.raises(SystemExit):
            load_custom_patterns(str(pf))

    def test_missing_file_raises(self):
        with pytest.raises(SystemExit):
            load_custom_patterns("/nonexistent/patterns.json")

    def test_empty_list(self, tmp_path):
        pf = tmp_path / "patterns.json"
        pf.write_text("[]")
        patterns = load_custom_patterns(str(pf))
        assert patterns == []


class TestScanDirectory:
    """ディレクトリスキャンのテスト"""

    def test_empty_directory_no_findings(self, tmp_path):
        findings = scan_directory(str(tmp_path), KNOWN_INCONSISTENCIES)
        assert findings == []

    def test_non_markdown_files_skipped(self, tmp_path):
        txt = tmp_path / "file.txt"
        txt.write_text("The Seting page is wrong.\n")
        py = tmp_path / "file.py"
        py.write_text("recieve = 100\n")
        findings = scan_directory(str(tmp_path), KNOWN_INCONSISTENCIES)
        assert findings == []

    def test_scans_markdown_files_recursively(self, tmp_path):
        subdir = tmp_path / "sub" / "deep"
        subdir.mkdir(parents=True)
        md = subdir / "doc.md"
        md.write_text("The Seting page is here.\n")
        findings = scan_directory(str(tmp_path), KNOWN_INCONSISTENCIES)
        assert len(findings) >= 1
        assert findings[0].found == "Seting"

    def test_reports_include_file_path(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("Seting label.\n")
        findings = scan_directory(str(tmp_path), KNOWN_INCONSISTENCIES)
        assert len(findings) == 1
        assert str(tmp_path / "test.md") in findings[0].file_path

    def test_multiple_files_aggregated(self, tmp_path):
        (tmp_path / "a.md").write_text("Seting error.\n")
        (tmp_path / "b.md").write_text("caculate error.\n")
        findings = scan_directory(str(tmp_path), KNOWN_INCONSISTENCIES)
        assert len(findings) == 2
        found_terms = {f.found for f in findings}
        assert "Seting" in found_terms
        assert "caculate" in found_terms


class TestFinding:
    """Finding データクラスのテスト"""

    def test_finding_attributes(self):
        f = Finding(
            file_path="/tmp/test.md",
            line_number=10,
            found="Seting",
            expected="Setting",
            context="typo",
            level="error",
        )
        assert f.file_path == "/tmp/test.md"
        assert f.line_number == 10
        assert f.found == "Seting"
        assert f.expected == "Setting"
        assert f.context == "typo"
        assert f.level == "error"

    def test_finding_default_level_is_error(self):
        f = Finding(
            file_path="/tmp/test.md",
            line_number=1,
            found="x",
            expected="y",
            context="test",
        )
        assert f.level == "error"


class TestMainCLI:
    """CLI エントリポイントのテスト"""

    def test_exit_code_0_when_clean(self, tmp_path):
        md = tmp_path / "clean.md"
        md.write_text("No issues here.\n")
        from check_consistency import main

        exit_code = main(["--docs-dir", str(tmp_path)])
        assert exit_code == 0

    def test_exit_code_1_when_errors_found(self, tmp_path):
        md = tmp_path / "bad.md"
        md.write_text("The Seting page.\n")
        from check_consistency import main

        exit_code = main(["--docs-dir", str(tmp_path)])
        assert exit_code == 1

    def test_exit_code_0_when_no_errors(self, tmp_path):
        md = tmp_path / "clean.md"
        md.write_text("Everything is correct.\n")
        from check_consistency import main

        exit_code = main(["--docs-dir", str(tmp_path)])
        assert exit_code == 0

    def test_custom_patterns_flag(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("The custmer is here.\n")
        pf = tmp_path / "patterns.json"
        pf.write_text(json.dumps([
            {"wrong": "custmer", "correct": "customer", "context": "typo"}
        ]))
        from check_consistency import main

        exit_code = main([
            "--docs-dir", str(tmp_path),
            "--patterns", str(pf),
        ])
        assert exit_code == 1
