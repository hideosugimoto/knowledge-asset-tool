#!/usr/bin/env python3
"""
i18n.py - テンプレートの多言語変換

使い方:
  python3 scripts/i18n.py --template templates/index-template.md --lang en --output index-en.md
  python3 scripts/i18n.py --template templates/index-template.md --lang ja --output index-ja.md
"""

import argparse
import os
import sys

LABELS = {
    "ja": {
        "読む人別 クイックリンク": "読む人別 クイックリンク",
        "アーキテクチャ文書": "アーキテクチャ文書",
        "完全マニュアル": "完全マニュアル",
        "操作ガイド": "操作ガイド",
        "レベル別説明": "レベル別説明",
        "スライド資料": "スライド資料",
        "AI 向けドキュメント": "AI 向けドキュメント",
        "ダイアグラム": "ダイアグラム",
        "共有方法": "共有方法",
        "エンジニア": "エンジニア",
        "営業": "営業",
        "初心者": "初心者",
        "エンドユーザー": "エンドユーザー",
    },
    "en": {
        "読む人別 クイックリンク": "Quick Links by Reader",
        "アーキテクチャ文書": "Architecture Documents",
        "完全マニュアル": "Complete Manual",
        "操作ガイド": "Operations Guide",
        "レベル別説明": "Explanations by Level",
        "スライド資料": "Slide Materials",
        "AI 向けドキュメント": "AI Documents",
        "ダイアグラム": "Diagrams",
        "共有方法": "Sharing",
        "エンジニア": "Engineer",
        "営業": "Sales/Business",
        "初心者": "Beginner",
        "エンドユーザー": "End User",
    },
}

SUPPORTED_LANGUAGES = list(LABELS.keys())


def translate_template(content, lang):
    """テンプレート内の日本語ラベルを指定言語に変換する。

    Args:
        content: テンプレートのテキスト内容
        lang: 言語コード ('ja' or 'en')

    Returns:
        変換後のテキスト

    Raises:
        ValueError: サポートされていない言語コードの場合
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: '{lang}'. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    if lang == "ja":
        return content

    translations = LABELS[lang]
    result = content
    for ja_label, translated_label in translations.items():
        result = result.replace(ja_label, translated_label)

    return result


def main():
    """CLI エントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="テンプレートの多言語変換"
    )
    parser.add_argument(
        "--template",
        required=True,
        help="入力テンプレートファイルのパス",
    )
    parser.add_argument(
        "--lang",
        required=True,
        choices=SUPPORTED_LANGUAGES,
        help=f"出力言語 ({', '.join(SUPPORTED_LANGUAGES)})",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="出力ファイルのパス",
    )

    args = parser.parse_args()

    if not os.path.exists(args.template):
        print(f"[ERROR] テンプレートが見つかりません: {args.template}")
        sys.exit(1)

    try:
        with open(args.template, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"[ERROR] テンプレート読み込みエラー: {e}")
        sys.exit(1)

    try:
        result = translate_template(content, args.lang)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"[OK] {args.output} を生成しました (lang={args.lang})")


if __name__ == "__main__":
    main()
