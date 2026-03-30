"""Tests for merge_pdf.py - PDF/Markdown merge script.

TDD: These tests are written FIRST, before the implementation.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from merge_pdf import (
    collect_files,
    concatenate_markdown,
    generate_toc,
    merge_manual,
    parse_args,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def manual_dir(tmp_path):
    """Create a realistic manual directory with chapter files and features/."""
    d = tmp_path / "manual"
    d.mkdir()

    chapters = {
        "00-index.md": "# Project Manual\n\n## Table of Contents\n",
        "01-overview.md": "# Overview\n\nThis is the overview.\n",
        "02-screen-flow.md": "# Screen Flow\n\nScreen flow details.\n",
        "03-features.md": "# Features\n\nFeatures summary.\n",
        "04-api-reference.md": "# API Reference\n\nAPI details.\n",
        "05-data-model.md": "# Data Model\n\nER diagram.\n",
        "06-screen-specs.md": "# Screen Specs\n\nScreen specifications.\n",
        "07-walkthrough.md": "# Walkthrough\n\nStep-by-step guide.\n",
        "08-review.md": "# Review\n\nReview checklist.\n",
        "09-user-guide.md": "# User Guide\n\nUser guide content.\n",
    }
    for name, content in chapters.items():
        (d / name).write_text(content, encoding="utf-8")

    features = d / "features"
    features.mkdir()
    (features / "auth.md").write_text("# Authentication\n\nAuth details.\n", encoding="utf-8")
    (features / "billing.md").write_text("# Billing\n\nBilling details.\n", encoding="utf-8")

    # Non-markdown file should be ignored
    (d / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")

    return d


@pytest.fixture()
def empty_dir(tmp_path):
    """Create an empty manual directory."""
    d = tmp_path / "empty_manual"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# collect_files
# ---------------------------------------------------------------------------


class TestCollectFiles:
    """Tests for collect_files() which gathers markdown files in order."""

    def test_collects_chapter_files_in_order(self, manual_dir):
        files = collect_files(manual_dir)
        names = [f.name for f in files]

        # Chapter files should appear in numeric order
        chapter_names = [n for n in names if n[:2].isdigit()]
        assert chapter_names == sorted(chapter_names)

    def test_chapters_appear_before_end(self, manual_dir):
        files = collect_files(manual_dir)
        names = [f.name for f in files]

        assert names[0] == "00-index.md"
        assert "09-user-guide.md" in names

    def test_feature_files_included_after_03_features(self, manual_dir):
        files = collect_files(manual_dir)
        names = [f.name for f in files]

        features_idx = names.index("03-features.md")
        # Feature files should appear right after 03-features.md
        auth_idx = names.index("auth.md")
        billing_idx = names.index("billing.md")

        assert auth_idx > features_idx
        assert billing_idx > features_idx
        # And before 04-api-reference.md
        api_idx = names.index("04-api-reference.md")
        assert auth_idx < api_idx
        assert billing_idx < api_idx

    def test_feature_files_sorted_alphabetically(self, manual_dir):
        files = collect_files(manual_dir)
        names = [f.name for f in files]

        features_idx = names.index("03-features.md")
        api_idx = names.index("04-api-reference.md")
        feature_names = names[features_idx + 1 : api_idx]
        assert feature_names == sorted(feature_names)

    def test_ignores_non_markdown_files(self, manual_dir):
        files = collect_files(manual_dir)
        extensions = {f.suffix for f in files}
        assert extensions == {".md"}

    def test_missing_directory_raises_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            collect_files(tmp_path / "nonexistent")

    def test_empty_directory_raises_error(self, empty_dir):
        with pytest.raises(ValueError, match="No markdown files"):
            collect_files(empty_dir)

    def test_no_features_dir_still_works(self, tmp_path):
        """Manual dir without features/ subdirectory should work fine."""
        d = tmp_path / "simple"
        d.mkdir()
        (d / "00-index.md").write_text("# Index\n", encoding="utf-8")
        (d / "01-overview.md").write_text("# Overview\n", encoding="utf-8")

        files = collect_files(d)
        assert len(files) == 2
        assert [f.name for f in files] == ["00-index.md", "01-overview.md"]


# ---------------------------------------------------------------------------
# generate_toc
# ---------------------------------------------------------------------------


class TestGenerateToc:
    """Tests for generate_toc() which builds a table of contents."""

    def test_extracts_h1_headings(self, manual_dir):
        files = collect_files(manual_dir)
        toc = generate_toc(files)

        assert "# Table of Contents" in toc
        assert "Overview" in toc
        assert "Screen Flow" in toc
        assert "Features" in toc

    def test_toc_entries_are_markdown_list(self, manual_dir):
        files = collect_files(manual_dir)
        toc = generate_toc(files)

        lines = [line for line in toc.split("\n") if line.startswith("- ")]
        assert len(lines) > 0

    def test_handles_files_without_headings(self, tmp_path):
        d = tmp_path / "no_headings"
        d.mkdir()
        (d / "00-readme.md").write_text("No heading here, just text.\n", encoding="utf-8")

        files = collect_files(d)
        toc = generate_toc(files)

        # Should still produce a TOC header, using filename as fallback
        assert "# Table of Contents" in toc
        assert "00-readme" in toc


# ---------------------------------------------------------------------------
# concatenate_markdown
# ---------------------------------------------------------------------------


class TestConcatenateMarkdown:
    """Tests for concatenate_markdown() which joins files with separators."""

    def test_includes_all_chapter_content(self, manual_dir):
        files = collect_files(manual_dir)
        result = concatenate_markdown(files)

        assert "# Overview" in result
        assert "# Screen Flow" in result
        assert "# Authentication" in result
        assert "# Billing" in result

    def test_page_breaks_between_chapters(self, manual_dir):
        files = collect_files(manual_dir)
        result = concatenate_markdown(files)

        # Page breaks should separate chapters
        assert "\n\n---\n\n" in result

    def test_toc_at_beginning(self, manual_dir):
        files = collect_files(manual_dir)
        result = concatenate_markdown(files, include_toc=True)

        # TOC should appear before the first chapter content
        toc_pos = result.index("# Table of Contents")
        overview_pos = result.index("# Overview")
        assert toc_pos < overview_pos

    def test_without_toc(self, manual_dir):
        files = collect_files(manual_dir)
        result = concatenate_markdown(files, include_toc=False)

        # The generated TOC line should not appear; any TOC in the
        # source files themselves is fine.
        lines = result.split("\n")
        assert lines[0] != "# Table of Contents"

    def test_single_file(self, tmp_path):
        d = tmp_path / "single"
        d.mkdir()
        (d / "00-index.md").write_text("# Single Chapter\n\nContent.\n", encoding="utf-8")

        files = collect_files(d)
        result = concatenate_markdown(files, include_toc=False)

        assert "# Single Chapter" in result
        # No separator needed for single file without TOC
        assert result.count("\n\n---\n\n") == 0


# ---------------------------------------------------------------------------
# merge_manual (integration)
# ---------------------------------------------------------------------------


class TestMergeManual:
    """Integration tests for the full merge_manual() function."""

    def test_outputs_markdown_file(self, manual_dir, tmp_path):
        output = tmp_path / "output.md"
        result = merge_manual(manual_dir, output)

        assert output.exists()
        assert output.stat().st_size > 0
        assert result["output_path"] == str(output)
        assert result["file_size"] > 0

    def test_output_contains_all_chapters(self, manual_dir, tmp_path):
        output = tmp_path / "output.md"
        merge_manual(manual_dir, output)

        content = output.read_text(encoding="utf-8")
        assert "# Overview" in content
        assert "# User Guide" in content
        assert "# Authentication" in content

    def test_reports_chapter_count(self, manual_dir, tmp_path):
        output = tmp_path / "output.md"
        result = merge_manual(manual_dir, output)

        # 10 chapters + 2 feature files = 12
        assert result["chapter_count"] == 12

    def test_reports_page_estimate(self, manual_dir, tmp_path):
        output = tmp_path / "output.md"
        result = merge_manual(manual_dir, output)

        assert "page_estimate" in result
        assert result["page_estimate"] >= 1

    def test_pdf_output_without_pandoc(self, manual_dir, tmp_path):
        output = tmp_path / "output.pdf"

        with patch("merge_pdf.shutil.which", return_value=None):
            result = merge_manual(manual_dir, output)

        # Should fall back to .md and suggest pandoc command
        assert result["fallback"]
        fallback_path = Path(result["output_path"])
        assert fallback_path.suffix == ".md"
        assert fallback_path.exists()
        assert "pandoc_command" in result

    def test_pdf_output_with_pandoc(self, manual_dir, tmp_path):
        output = tmp_path / "output.pdf"
        md_fallback = output.with_suffix(".md")

        with patch("merge_pdf.shutil.which", return_value="/usr/local/bin/pandoc"):
            with patch("merge_pdf.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0
                )
                # Create the PDF file to simulate pandoc output
                output.write_bytes(b"%PDF-1.4 fake content")

                result = merge_manual(manual_dir, output)

        assert result["output_path"] == str(output)
        assert not result["fallback"]
        mock_run.assert_called_once()

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            merge_manual(tmp_path / "nope", tmp_path / "out.md")

    def test_creates_output_parent_dirs(self, manual_dir, tmp_path):
        output = tmp_path / "nested" / "deep" / "output.md"
        merge_manual(manual_dir, output)

        assert output.exists()


# ---------------------------------------------------------------------------
# CLI (parse_args)
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_required_args(self):
        args = parse_args(["--manual-dir", "/tmp/docs", "--output", "/tmp/out.md"])
        assert args.manual_dir == "/tmp/docs"
        assert args.output == "/tmp/out.md"

    def test_missing_manual_dir_raises(self):
        with pytest.raises(SystemExit):
            parse_args(["--output", "/tmp/out.md"])

    def test_missing_output_raises(self):
        with pytest.raises(SystemExit):
            parse_args(["--manual-dir", "/tmp/docs"])

    def test_no_toc_flag(self):
        args = parse_args(
            ["--manual-dir", "/tmp/docs", "--output", "/tmp/out.md", "--no-toc"]
        )
        assert args.no_toc is True

    def test_default_toc_enabled(self):
        args = parse_args(["--manual-dir", "/tmp/docs", "--output", "/tmp/out.md"])
        assert args.no_toc is False
