"""package.py のテスト"""

import os
import sys
import zipfile
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from package import build_zip, generate_default_filename, convert_index_to_readme, _should_exclude


# ---------------------------------------------------------------------------
# generate_default_filename
# ---------------------------------------------------------------------------
class TestGenerateDefaultFilename:
    """デフォルトファイル名の生成テスト"""

    def test_with_name(self):
        result = generate_default_filename("my-project")
        today = date.today().isoformat()
        assert result == f"my-project-docs-{today}.zip"

    def test_without_name(self):
        result = generate_default_filename(None)
        today = date.today().isoformat()
        assert result == f"docs-{today}.zip"

    def test_name_included_in_filename(self):
        result = generate_default_filename("cool-app")
        assert "cool-app" in result
        assert result.endswith(".zip")


# ---------------------------------------------------------------------------
# convert_index_to_readme
# ---------------------------------------------------------------------------
class TestConvertIndexToReadme:
    """index.md → README テキスト変換テスト"""

    def test_basic_conversion(self, tmp_path):
        index = tmp_path / "index.md"
        index.write_text("# My Project\n\nSome description.\n")
        result = convert_index_to_readme(str(index))
        assert "My Project" in result
        assert "Some description." in result

    def test_missing_file_returns_fallback(self):
        result = convert_index_to_readme("/nonexistent/index.md")
        assert "README" in result or "No index.md" in result

    def test_empty_file(self, tmp_path):
        index = tmp_path / "index.md"
        index.write_text("")
        result = convert_index_to_readme(str(index))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# build_zip: 正常系
# ---------------------------------------------------------------------------
class TestBuildZipValid:
    """site/ + slides/ が揃っている場合の正常系"""

    def _setup_dirs(self, tmp_path):
        """テスト用ディレクトリ構造を作成"""
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")
        (site_dir / "css").mkdir()
        (site_dir / "css" / "style.css").write_text("body{}")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        slides_dir = docs_dir / "slides"
        slides_dir.mkdir()
        (slides_dir / "pres.pdf").write_bytes(b"%PDF-fake")
        (slides_dir / "pres.pptx").write_bytes(b"PK-fake")
        (slides_dir / "pres.html").write_text("<html>slide</html>")

        index_md = docs_dir / "index.md"
        index_md.write_text("# Test Project\n\nDescription here.\n")

        return str(docs_dir), str(site_dir)

    def test_zip_created(self, tmp_path):
        docs_dir, site_dir = self._setup_dirs(tmp_path)
        output = str(tmp_path / "output.zip")
        result = build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        assert result["success"] is True
        assert os.path.exists(output)

    def test_zip_contains_html_dir(self, tmp_path):
        docs_dir, site_dir = self._setup_dirs(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any(n.startswith("html/") for n in names)
            assert "html/index.html" in names
            assert "html/css/style.css" in names

    def test_zip_contains_slides_dir(self, tmp_path):
        docs_dir, site_dir = self._setup_dirs(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert "slides/pres.pdf" in names
            assert "slides/pres.pptx" in names

    def test_zip_contains_readme(self, tmp_path):
        docs_dir, site_dir = self._setup_dirs(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert "README.txt" in names
            content = zf.read("README.txt").decode("utf-8")
            assert "Test Project" in content

    def test_result_contains_metadata(self, tmp_path):
        docs_dir, site_dir = self._setup_dirs(tmp_path)
        output = str(tmp_path / "output.zip")
        result = build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        assert "path" in result
        assert "size" in result
        assert "file_count" in result
        assert result["size"] > 0
        assert result["file_count"] > 0


# ---------------------------------------------------------------------------
# build_zip: site/ が存在しない場合
# ---------------------------------------------------------------------------
class TestBuildZipMissingSite:
    """site/ ディレクトリが存在しない場合"""

    def test_missing_site_returns_error(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        output = str(tmp_path / "output.zip")

        result = build_zip(
            docs_dir=str(docs_dir),
            site_dir=str(tmp_path / "nonexistent_site"),
            output=output,
        )

        assert result["success"] is False
        assert "mkdocs build" in result["error"].lower() or "site" in result["error"].lower()
        assert not os.path.exists(output)


# ---------------------------------------------------------------------------
# build_zip: スライドファイルなし
# ---------------------------------------------------------------------------
class TestBuildZipNoSlides:
    """docs/slides/ にファイルがない or ディレクトリがない場合"""

    def test_no_slides_dir_still_creates_zip(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Project\n")

        output = str(tmp_path / "output.zip")
        result = build_zip(docs_dir=str(docs_dir), site_dir=str(site_dir), output=output)

        assert result["success"] is True
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any(n.startswith("html/") for n in names)
            assert not any(n.startswith("slides/") for n in names)

    def test_empty_slides_dir_still_creates_zip(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "slides").mkdir()
        (docs_dir / "index.md").write_text("# Project\n")

        output = str(tmp_path / "output.zip")
        result = build_zip(docs_dir=str(docs_dir), site_dir=str(site_dir), output=output)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# build_zip: 除外ファイル
# ---------------------------------------------------------------------------
class TestBuildZipExclusions:
    """除外対象ファイルが ZIP に含まれないことを確認"""

    def _setup_with_junk(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")
        (site_dir / ".DS_Store").write_bytes(b"\x00\x00")
        pycache = site_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "mod.cpython-311.pyc").write_bytes(b"\x00")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        slides_dir = docs_dir / "slides"
        slides_dir.mkdir()
        (slides_dir / "pres.pdf").write_bytes(b"%PDF")
        (slides_dir / "diagram.mmd").write_text("flowchart TD")
        (slides_dir / ".DS_Store").write_bytes(b"\x00")

        (docs_dir / "index.md").write_text("# Test\n")
        return str(docs_dir), str(site_dir)

    def test_ds_store_excluded(self, tmp_path):
        docs_dir, site_dir = self._setup_with_junk(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert not any(".DS_Store" in n for n in names)

    def test_pycache_excluded(self, tmp_path):
        docs_dir, site_dir = self._setup_with_junk(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)

    def test_mmd_excluded(self, tmp_path):
        docs_dir, site_dir = self._setup_with_junk(tmp_path)
        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=docs_dir, site_dir=site_dir, output=output)

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert not any(n.endswith(".mmd") for n in names)


# ---------------------------------------------------------------------------
# build_zip: --name / --output フラグ
# ---------------------------------------------------------------------------
class TestBuildZipNaming:
    """ファイル名の生成テスト"""

    def test_custom_output_path(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Test\n")

        custom = str(tmp_path / "custom" / "my-archive.zip")
        result = build_zip(docs_dir=str(docs_dir), site_dir=str(site_dir), output=custom)

        assert result["success"] is True
        assert result["path"] == custom
        assert os.path.exists(custom)

    def test_name_flag_in_default_filename(self):
        filename = generate_default_filename("cool-project")
        assert "cool-project" in filename
        assert date.today().isoformat() in filename


# ---------------------------------------------------------------------------
# build_zip: 空の site/ ディレクトリ
# ---------------------------------------------------------------------------
class TestBuildZipEmptySite:
    """空の site/ ディレクトリでも ZIP は作成される"""

    def test_empty_site_creates_small_zip(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Test\n")

        output = str(tmp_path / "output.zip")
        result = build_zip(docs_dir=str(docs_dir), site_dir=str(site_dir), output=output)

        assert result["success"] is True
        assert result["size"] > 0
        # README.txt のみ含まれる（html/ 内にファイルがない場合）
        assert result["file_count"] >= 1


# ---------------------------------------------------------------------------
# build_zip: slides/ 内の HTML ファイルは含めない（PDF/PPTX のみ）
# ---------------------------------------------------------------------------
class TestBuildZipSlideFileTypes:
    """slides/ ディレクトリから PDF と PPTX のみ収集"""

    def test_only_pdf_and_pptx_included(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        slides_dir = docs_dir / "slides"
        slides_dir.mkdir()
        (slides_dir / "pres.pdf").write_bytes(b"%PDF")
        (slides_dir / "pres.pptx").write_bytes(b"PK")
        (slides_dir / "pres.html").write_text("<html>slide</html>")
        (slides_dir / "notes.txt").write_text("notes")

        (docs_dir / "index.md").write_text("# Test\n")

        output = str(tmp_path / "output.zip")
        build_zip(docs_dir=str(docs_dir), site_dir=str(site_dir), output=output)

        with zipfile.ZipFile(output, "r") as zf:
            slide_names = [n for n in zf.namelist() if n.startswith("slides/")]
            assert "slides/pres.pdf" in slide_names
            assert "slides/pres.pptx" in slide_names
            assert "slides/pres.html" not in slide_names
            assert "slides/notes.txt" not in slide_names


# ---------------------------------------------------------------------------
# _should_exclude
# ---------------------------------------------------------------------------
class TestShouldExclude:
    """除外判定ロジックの直接テスト"""

    def test_ds_store(self):
        assert _should_exclude("/some/path/.DS_Store") is True

    def test_mmd_extension(self):
        assert _should_exclude("/docs/diagrams/flow.mmd") is True

    def test_pycache_in_path(self):
        assert _should_exclude("__pycache__/module.pyc") is True

    def test_normal_file_not_excluded(self):
        assert _should_exclude("/docs/index.html") is False

    def test_thumbs_db(self):
        assert _should_exclude("/site/Thumbs.db") is True


# ---------------------------------------------------------------------------
# main() CLI エントリポイント
# ---------------------------------------------------------------------------
class TestMainCLI:
    """main() 関数の CLI テスト"""

    def test_main_success(self, tmp_path, monkeypatch, capsys):
        from package import main

        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Test\n")
        output = str(tmp_path / "result.zip")

        monkeypatch.setattr(
            "sys.argv",
            ["package.py", "--docs-dir", str(docs_dir), "--site-dir", str(site_dir), "--output", output],
        )
        main()

        captured = capsys.readouterr()
        assert "ZIP created" in captured.out
        assert "Size:" in captured.out
        assert "Files:" in captured.out

    def test_main_missing_site_exits(self, tmp_path, monkeypatch):
        from package import main

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        output = str(tmp_path / "result.zip")

        monkeypatch.setattr(
            "sys.argv",
            ["package.py", "--docs-dir", str(docs_dir), "--site-dir", str(tmp_path / "no-site"), "--output", output],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_default_filename_with_name(self, tmp_path, monkeypatch, capsys):
        from package import main

        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html></html>")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "index.md").write_text("# Test\n")

        monkeypatch.setattr(
            "sys.argv",
            ["package.py", "--docs-dir", str(docs_dir), "--site-dir", str(site_dir), "--name", "my-proj"],
        )
        monkeypatch.chdir(tmp_path)
        main()

        captured = capsys.readouterr()
        assert "my-proj" in captured.out
