"""i18n.py のテスト"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from i18n import LABELS, translate_template, main as i18n_main


SAMPLE_TEMPLATE = """\
# {NAME} ドキュメント

> 生成日: {DATE} | 対象: {TARGET_PATH}

## 読む人別 クイックリンク

| あなたは... | まず読むべき資料 |
|------------|----------------|
| エンジニア（設計を知りたい） | [arc42 アーキテクチャ](architecture/{NAME}.md) |
| 営業・ビジネス | [営業向け説明](explanations/{NAME}/sales.md) |
| 初心者 | [初心者向け解説](explanations/{NAME}/beginner.md) |
| エンドユーザー（操作方法） | [操作ガイド](manual/{NAME}/09-user-guide.md) |

## 1. アーキテクチャ文書

## 2. 完全マニュアル

## 3. 操作ガイド

## 4. レベル別説明

## 5. スライド資料

## 6. AI 向けドキュメント

## 7. ダイアグラム

## 共有方法
"""


class TestTranslateTemplate:
    """translate_template 関数のテスト"""

    def test_japanese_output_unchanged(self):
        """Japanese output should be identical to input."""
        result = translate_template(SAMPLE_TEMPLATE, "ja")
        assert result == SAMPLE_TEMPLATE

    def test_english_translates_section_headers(self):
        """English output should have translated section headers."""
        result = translate_template(SAMPLE_TEMPLATE, "en")
        assert "Quick Links by Reader" in result
        assert "Architecture Documents" in result
        assert "Complete Manual" in result
        assert "Operations Guide" in result
        assert "Explanations by Level" in result
        assert "Slide Materials" in result
        assert "AI Documents" in result
        assert "Diagrams" in result
        assert "Sharing" in result

    def test_english_translates_reader_labels(self):
        """English output should translate reader role labels."""
        result = translate_template(SAMPLE_TEMPLATE, "en")
        assert "Engineer" in result
        assert "Sales/Business" in result
        assert "Beginner" in result
        assert "End User" in result

    def test_japanese_labels_removed_in_english(self):
        """Japanese section labels should not remain in English output."""
        result = translate_template(SAMPLE_TEMPLATE, "en")
        assert "読む人別 クイックリンク" not in result
        assert "アーキテクチャ文書" not in result
        assert "完全マニュアル" not in result

    def test_placeholders_preserved_in_japanese(self):
        """Placeholders like {NAME} should remain in Japanese output."""
        result = translate_template(SAMPLE_TEMPLATE, "ja")
        assert "{NAME}" in result
        assert "{DATE}" in result
        assert "{TARGET_PATH}" in result

    def test_placeholders_preserved_in_english(self):
        """Placeholders like {NAME} should remain in English output."""
        result = translate_template(SAMPLE_TEMPLATE, "en")
        assert "{NAME}" in result
        assert "{DATE}" in result
        assert "{TARGET_PATH}" in result

    def test_unknown_language_raises_error(self):
        """Unknown language code should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            translate_template(SAMPLE_TEMPLATE, "fr")

    def test_labels_dict_has_ja_and_en(self):
        """LABELS dict should have both 'ja' and 'en' keys."""
        assert "ja" in LABELS
        assert "en" in LABELS

    def test_labels_en_has_all_ja_keys(self):
        """English labels should cover all Japanese label keys."""
        for key in LABELS["ja"]:
            assert key in LABELS["en"], f"Missing English translation for: {key}"


class TestI18nCLI:
    """CLI インターフェースのテスト"""

    def test_cli_lang_en_output(self, tmp_path):
        """CLI with --lang en should produce translated output."""
        template = tmp_path / "template.md"
        template.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
        output = tmp_path / "output.md"

        sys.argv = [
            "i18n.py",
            "--template", str(template),
            "--lang", "en",
            "--output", str(output),
        ]
        i18n_main()

        result = output.read_text(encoding="utf-8")
        assert "Quick Links by Reader" in result
        assert "{NAME}" in result

    def test_cli_lang_ja_copies_as_is(self, tmp_path):
        """CLI with --lang ja should copy template unchanged."""
        template = tmp_path / "template.md"
        template.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
        output = tmp_path / "output.md"

        sys.argv = [
            "i18n.py",
            "--template", str(template),
            "--lang", "ja",
            "--output", str(output),
        ]
        i18n_main()

        result = output.read_text(encoding="utf-8")
        assert result == SAMPLE_TEMPLATE

    def test_cli_template_not_found(self, tmp_path):
        """CLI should exit with error when template file not found."""
        output = tmp_path / "output.md"
        sys.argv = [
            "i18n.py",
            "--template", "/nonexistent/template.md",
            "--lang", "en",
            "--output", str(output),
        ]
        with pytest.raises(SystemExit):
            i18n_main()

    def test_cli_invalid_lang(self, tmp_path):
        """CLI should exit with error for unsupported language."""
        template = tmp_path / "template.md"
        template.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
        output = tmp_path / "output.md"

        sys.argv = [
            "i18n.py",
            "--template", str(template),
            "--lang", "fr",
            "--output", str(output),
        ]
        with pytest.raises(SystemExit):
            i18n_main()

    def test_cli_output_file_created(self, tmp_path):
        """CLI should create the output file."""
        template = tmp_path / "template.md"
        template.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
        output = tmp_path / "subdir" / "output.md"

        sys.argv = [
            "i18n.py",
            "--template", str(template),
            "--lang", "en",
            "--output", str(output),
        ]
        i18n_main()

        assert output.exists()
