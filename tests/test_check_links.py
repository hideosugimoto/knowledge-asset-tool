"""check_links.py のテスト"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from check_links import (
    extract_links,
    find_markdown_files,
    heading_exists,
    is_external_url,
    resolve_link_target,
    validate_links,
)


class TestIsExternalUrl:
    """外部URLの判定テスト"""

    def test_http_url(self):
        assert is_external_url("http://example.com") is True

    def test_https_url(self):
        assert is_external_url("https://example.com/page") is True

    def test_relative_path(self):
        assert is_external_url("../other.md") is False

    def test_absolute_path(self):
        assert is_external_url("/docs/file.md") is False

    def test_anchor_only(self):
        assert is_external_url("#section") is False

    def test_mailto(self):
        assert is_external_url("mailto:user@example.com") is True


class TestExtractLinks:
    """Markdownリンク抽出テスト"""

    def test_standard_link(self):
        content = "See [guide](./guide.md) for details."
        links = extract_links(content)
        assert len(links) == 1
        assert links[0] == (1, "guide", "./guide.md")

    def test_image_link(self):
        content = "![diagram](images/arch.png)"
        links = extract_links(content)
        assert len(links) == 1
        assert links[0] == (1, "diagram", "images/arch.png")

    def test_multiple_links(self):
        content = "[a](a.md)\n[b](b.md)\n[c](c.md)"
        links = extract_links(content)
        assert len(links) == 3

    def test_link_with_anchor(self):
        content = "[section](other.md#heading)"
        links = extract_links(content)
        assert len(links) == 1
        assert links[0] == (1, "section", "other.md#heading")

    def test_anchor_only_link(self):
        content = "[top](#overview)"
        links = extract_links(content)
        assert len(links) == 1
        assert links[0] == (1, "top", "#overview")

    def test_no_links(self):
        content = "Just plain text with no links."
        links = extract_links(content)
        assert links == []

    def test_external_links_included_in_extraction(self):
        content = "[site](https://example.com)"
        links = extract_links(content)
        assert len(links) == 1

    def test_line_numbers_correct(self):
        content = "line1\n[link1](a.md)\nline3\n[link2](b.md)"
        links = extract_links(content)
        assert links[0][0] == 2
        assert links[1][0] == 4

    def test_multiple_links_on_same_line(self):
        content = "[a](a.md) and [b](b.md)"
        links = extract_links(content)
        assert len(links) == 2
        assert links[0][0] == 1
        assert links[1][0] == 1


class TestHeadingExists:
    """見出し存在チェックテスト"""

    def test_h1_exists(self):
        content = "# Overview\nSome text."
        assert heading_exists(content, "overview") is True

    def test_h2_exists(self):
        content = "## Getting Started\nSome text."
        assert heading_exists(content, "getting-started") is True

    def test_heading_not_found(self):
        content = "# Overview\n## Setup"
        assert heading_exists(content, "nonexistent") is False

    def test_heading_with_special_chars(self):
        content = "## What's New?\nText."
        assert heading_exists(content, "whats-new") is True

    def test_heading_case_insensitive(self):
        content = "## My Section\nText."
        assert heading_exists(content, "my-section") is True

    def test_empty_content(self):
        assert heading_exists("", "anything") is False

    def test_heading_with_multiple_words(self):
        content = "### API Rate Limiting\nDetails."
        assert heading_exists(content, "api-rate-limiting") is True


class TestResolveLinkTarget:
    """リンクターゲット解決テスト"""

    def test_relative_same_dir(self, tmp_path):
        source = tmp_path / "docs" / "guide.md"
        source.parent.mkdir(parents=True)
        source.write_text("content")
        target = tmp_path / "docs" / "other.md"
        target.write_text("content")

        resolved = resolve_link_target(str(source), "other.md")
        assert resolved == str(target)

    def test_relative_parent_dir(self, tmp_path):
        source = tmp_path / "docs" / "sub" / "page.md"
        source.parent.mkdir(parents=True)
        source.write_text("content")
        target = tmp_path / "docs" / "index.md"
        target.write_text("content")

        resolved = resolve_link_target(str(source), "../index.md")
        assert os.path.normpath(resolved) == str(target)

    def test_strips_anchor(self, tmp_path):
        source = tmp_path / "docs" / "a.md"
        source.parent.mkdir(parents=True)
        source.write_text("content")

        resolved = resolve_link_target(str(source), "b.md#section")
        assert resolved.endswith("b.md")
        assert "#" not in resolved


class TestFindMarkdownFiles:
    """Markdownファイル探索テスト"""

    def test_finds_md_files(self, tmp_path):
        (tmp_path / "a.md").write_text("# A")
        (tmp_path / "b.md").write_text("# B")
        (tmp_path / "c.txt").write_text("not md")

        files = find_markdown_files(str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith(".md") for f in files)

    def test_recursive_search(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.md").write_text("# Root")
        (sub / "nested.md").write_text("# Nested")

        files = find_markdown_files(str(tmp_path))
        assert len(files) == 2

    def test_empty_directory(self, tmp_path):
        files = find_markdown_files(str(tmp_path))
        assert files == []


class TestValidateLinks:
    """リンクバリデーション統合テスト"""

    def test_valid_link_no_errors(self, tmp_path):
        target = tmp_path / "other.md"
        target.write_text("# Other\nContent.")
        source = tmp_path / "index.md"
        source.write_text("[Other](other.md)")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_broken_link_reported(self, tmp_path):
        source = tmp_path / "index.md"
        source.write_text("[Missing](missing.md)")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1
        assert "missing.md" in errors[0]["link"]
        assert "index.md" in errors[0]["source"]
        assert errors[0]["line"] == 1
        assert "not found" in errors[0]["reason"].lower()

    def test_valid_anchor_no_errors(self, tmp_path):
        target = tmp_path / "guide.md"
        target.write_text("# Setup\n## Installation\nSteps here.")
        source = tmp_path / "index.md"
        source.write_text("[Install](guide.md#installation)")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_broken_anchor_reported(self, tmp_path):
        target = tmp_path / "guide.md"
        target.write_text("# Setup\n## Installation\nSteps here.")
        source = tmp_path / "index.md"
        source.write_text("[Bad](guide.md#nonexistent)")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1
        assert "nonexistent" in errors[0]["reason"].lower()

    def test_self_anchor_valid(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("# Title\n## Details\nSee [above](#title).")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_self_anchor_broken(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("# Title\nSee [missing](#no-such-heading).")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1

    def test_external_urls_skipped(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[Google](https://google.com)\n[Local](missing.md)")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1
        assert "missing.md" in errors[0]["link"]

    def test_image_link_checked(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("![diagram](images/arch.png)")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1
        assert "arch.png" in errors[0]["link"]

    def test_image_link_valid(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        (img_dir / "arch.png").write_text("fake png")
        source = tmp_path / "page.md"
        source.write_text("![diagram](images/arch.png)")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_relative_path_parent_dir(self, tmp_path):
        (tmp_path / "root.md").write_text("# Root")
        sub = tmp_path / "sub"
        sub.mkdir()
        source = sub / "page.md"
        source.write_text("[Root](../root.md)")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_ignore_pattern(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[Missing](generated/output.md)")

        errors = validate_links(str(tmp_path), ignore_patterns=["generated/*"])
        assert errors == []

    def test_ignore_pattern_partial_match(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[a](generated/a.md)\n[b](real/b.md)")

        errors = validate_links(str(tmp_path), ignore_patterns=["generated/*"])
        assert len(errors) == 1
        assert "real/b.md" in errors[0]["link"]

    def test_file_with_no_links(self, tmp_path):
        source = tmp_path / "plain.md"
        source.write_text("Just text, no links at all.")

        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_empty_directory_no_errors(self, tmp_path):
        errors = validate_links(str(tmp_path))
        assert errors == []

    def test_error_contains_required_fields(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[bad](missing.md)")

        errors = validate_links(str(tmp_path))
        assert len(errors) == 1
        error = errors[0]
        assert "source" in error
        assert "line" in error
        assert "link" in error
        assert "reason" in error


SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "check_links.py"
)


class TestCLI:
    """CLIインターフェーステスト"""

    def test_exit_code_0_no_broken_links(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("No links here.")

        exit_code = os.system(
            f"{sys.executable} {SCRIPT_PATH} --docs-dir {tmp_path}"
        )
        assert os.WEXITSTATUS(exit_code) == 0

    def test_exit_code_1_broken_links(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[broken](missing.md)")

        exit_code = os.system(
            f"{sys.executable} {SCRIPT_PATH} --docs-dir {tmp_path}"
        )
        assert os.WEXITSTATUS(exit_code) == 1

    def test_ignore_flag(self, tmp_path):
        source = tmp_path / "page.md"
        source.write_text("[skip](generated/out.md)")

        exit_code = os.system(
            f"{sys.executable} {SCRIPT_PATH} --docs-dir {tmp_path} --ignore 'generated/*'"
        )
        assert os.WEXITSTATUS(exit_code) == 0
