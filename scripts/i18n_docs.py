#!/usr/bin/env python3
"""Post-process generated docs to translate fixed labels.

A lightweight post-processor that reads all generated docs for a project
and translates fixed labels (section titles, table headers) using the
mapping defined in scripts/i18n.py.

Usage:
    python scripts/i18n_docs.py --docs-dir ./docs --name system-name --lang en
    python scripts/i18n_docs.py --docs-dir ./docs --name system-name --lang ja
"""

import argparse
import sys
from pathlib import Path

# Import label mappings from the existing i18n module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import LABELS, SUPPORTED_LANGUAGES

# Extended label mappings for document content (beyond index template labels)
DOC_LABELS = {
    "ja": {
        # Section titles commonly found in generated docs
        "## 概要": "## 概要",
        "## システム概要": "## システム概要",
        "## 技術スタック": "## 技術スタック",
        "## 画面一覧": "## 画面一覧",
        "## 画面遷移図": "## 画面遷移図",
        "## 機能一覧": "## 機能一覧",
        "## API一覧": "## API一覧",
        "## APIリファレンス": "## APIリファレンス",
        "## データモデル": "## データモデル",
        "## ER図": "## ER図",
        "## 画面詳細設計": "## 画面詳細設計",
        "## ユースケース": "## ユースケース",
        "## 設計レビュー": "## 設計レビュー",
        "## 改善提案": "## 改善提案",
        "## 目次": "## 目次",
        "## 前提条件": "## 前提条件",
        "## 用語集": "## 用語集",
        # Table headers
        "| 画面名": "| 画面名",
        "| 機能名": "| 機能名",
        "| エンドポイント": "| エンドポイント",
        "| テーブル名": "| テーブル名",
        "| カラム名": "| カラム名",
        "| 型": "| 型",
        "| 説明": "| 説明",
        "| メソッド": "| メソッド",
        "| パス": "| パス",
        "| 認証": "| 認証",
        # Common labels
        "生成日時": "生成日時",
        "対象パス": "対象パス",
        "ツール": "ツール",
        "必須": "必須",
        "任意": "任意",
        "なし": "なし",
        "あり": "あり",
        "備考": "備考",
    },
    "en": {
        "## 概要": "## Overview",
        "## システム概要": "## System Overview",
        "## 技術スタック": "## Tech Stack",
        "## 画面一覧": "## Screen List",
        "## 画面遷移図": "## Screen Flow Diagram",
        "## 機能一覧": "## Feature List",
        "## API一覧": "## API List",
        "## APIリファレンス": "## API Reference",
        "## データモデル": "## Data Model",
        "## ER図": "## ER Diagram",
        "## 画面詳細設計": "## Screen Specifications",
        "## ユースケース": "## Use Cases",
        "## 設計レビュー": "## Design Review",
        "## 改善提案": "## Improvement Proposals",
        "## 目次": "## Table of Contents",
        "## 前提条件": "## Prerequisites",
        "## 用語集": "## Glossary",
        # Table headers
        "| 画面名": "| Screen Name",
        "| 機能名": "| Feature Name",
        "| エンドポイント": "| Endpoint",
        "| テーブル名": "| Table Name",
        "| カラム名": "| Column Name",
        "| 型": "| Type",
        "| 説明": "| Description",
        "| メソッド": "| Method",
        "| パス": "| Path",
        "| 認証": "| Auth",
        # Common labels
        "生成日時": "Generated",
        "対象パス": "Target",
        "ツール": "Tool",
        "必須": "Required",
        "任意": "Optional",
        "なし": "None",
        "あり": "Yes",
        "備考": "Notes",
    },
}


def translate_doc_content(content: str, lang: str) -> str:
    """Translate fixed labels in document content.

    Uses both the base i18n.py LABELS and the extended DOC_LABELS
    mappings. Only replaces known fixed labels -- does not attempt
    to translate free-form text.

    Args:
        content: Document text content.
        lang: Target language code ('ja' or 'en').

    Returns:
        Content with fixed labels translated.

    Raises:
        ValueError: If language is not supported.
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: '{lang}'. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    if lang == "ja":
        return content

    result = content

    # Apply base i18n labels (Japanese -> target language)
    base_translations = LABELS.get(lang, {})
    ja_labels = LABELS.get("ja", {})
    for ja_key, ja_value in ja_labels.items():
        target_value = base_translations.get(ja_key, ja_value)
        if ja_value != target_value:
            result = result.replace(ja_value, target_value)

    # Apply extended doc labels
    ja_doc = DOC_LABELS.get("ja", {})
    target_doc = DOC_LABELS.get(lang, {})
    for key, ja_value in ja_doc.items():
        target_value = target_doc.get(key, ja_value)
        if ja_value != target_value:
            result = result.replace(ja_value, target_value)

    return result


def process_docs(docs_dir: Path, name: str, lang: str) -> dict:
    """Process all docs for a project and translate fixed labels.

    Args:
        docs_dir: Path to the docs directory.
        name: Project name.
        lang: Target language code.

    Returns:
        Dict with keys: files_processed, files_modified.
    """
    files_processed = 0
    files_modified = 0

    # Collect all markdown files related to this project
    search_paths = [
        docs_dir / f"{name}-index.md",
        docs_dir / "architecture",
        docs_dir / "manual" / name,
        docs_dir / "manual" / name / "features",
        docs_dir / "explanations" / name,
        docs_dir / "decisions",
    ]

    md_files: list[Path] = []
    for p in search_paths:
        if p.is_file() and p.suffix == ".md":
            md_files.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*.md")):
                md_files.append(f)

    for md_file in md_files:
        try:
            original = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        translated = translate_doc_content(original, lang)
        files_processed += 1

        if translated != original:
            md_file.write_text(translated, encoding="utf-8")
            files_modified += 1
            print(f"  [MODIFIED] {md_file.relative_to(docs_dir)}")

    return {
        "files_processed": files_processed,
        "files_modified": files_modified,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-process generated docs to translate fixed labels."
    )
    parser.add_argument(
        "--docs-dir",
        default="./docs",
        help="Path to the docs directory (default: ./docs)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Project / system name",
    )
    parser.add_argument(
        "--lang",
        required=True,
        choices=SUPPORTED_LANGUAGES,
        help=f"Target language ({', '.join(SUPPORTED_LANGUAGES)})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    docs_dir = Path(args.docs_dir)
    name = args.name
    lang = args.lang

    if not docs_dir.is_dir():
        print(f"[ERROR] docs directory not found: {docs_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Translating fixed labels to '{lang}' for project '{name}'...")
    result = process_docs(docs_dir, name, lang)
    print(
        f"[OK] Processed {result['files_processed']} files, "
        f"modified {result['files_modified']} files."
    )


if __name__ == "__main__":
    main()
