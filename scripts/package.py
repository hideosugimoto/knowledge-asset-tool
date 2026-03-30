#!/usr/bin/env python3
"""ドキュメント成果物を ZIP にパッケージングするスクリプト.

Usage:
    python scripts/package.py --docs-dir ./docs --site-dir ./site --output ./output.zip
    python scripts/package.py --docs-dir ./docs --site-dir ./site --name my-project
"""

import argparse
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

# 除外対象のファイル名・ディレクトリ名
EXCLUDED_NAMES = {".DS_Store", "__pycache__", "Thumbs.db"}
# 除外対象の拡張子
EXCLUDED_EXTENSIONS = {".mmd"}
# slides/ から収集する拡張子
SLIDE_EXTENSIONS = {".pdf", ".pptx"}


def generate_default_filename(name=None):
    """デフォルトの ZIP ファイル名を生成する.

    Args:
        name: プロジェクト名。None の場合は省略。

    Returns:
        "{name}-docs-{YYYY-MM-DD}.zip" 形式の文字列。
    """
    today = date.today().isoformat()
    if name:
        return f"{name}-docs-{today}.zip"
    return f"docs-{today}.zip"


def convert_index_to_readme(index_path):
    """docs/index.md を読み込み、簡易テキスト README に変換する.

    Args:
        index_path: index.md のファイルパス。

    Returns:
        README テキスト文字列。ファイルが存在しない場合はフォールバック文を返す。
    """
    try:
        content = Path(index_path).read_text(encoding="utf-8")
        if not content.strip():
            return "README\n\nNo content available.\n"
        return content
    except FileNotFoundError:
        return "README\n\nNo index.md found. Please refer to the HTML documentation in html/.\n"


def _should_exclude(file_path):
    """ファイルを除外すべきかどうかを判定する."""
    name = os.path.basename(file_path)
    if name in EXCLUDED_NAMES:
        return True
    _, ext = os.path.splitext(name)
    if ext in EXCLUDED_EXTENSIONS:
        return True
    # __pycache__ がパスのどこかに含まれていたら除外
    parts = Path(file_path).parts
    if any(part in EXCLUDED_NAMES for part in parts):
        return True
    return False


def build_zip(docs_dir, site_dir, output, name=None):
    """ドキュメント成果物を ZIP にパッケージングする.

    Args:
        docs_dir: docs/ ディレクトリのパス。
        site_dir: site/ ディレクトリのパス（MkDocs ビルド出力）。
        output: 出力 ZIP ファイルのパス。
        name: プロジェクト名（デフォルトファイル名生成用）。

    Returns:
        dict: {success, path, size, file_count, error?}
    """
    # site/ ディレクトリの存在チェック
    if not os.path.isdir(site_dir):
        return {
            "success": False,
            "error": (
                f"site/ directory not found: {site_dir}\n"
                "Please run `mkdocs build` first to generate the HTML site."
            ),
        }

    # 出力先ディレクトリを作成
    output_dir = os.path.dirname(output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    file_count = 0

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. site/ → html/ としてパッケージ
        for root, dirs, files in os.walk(site_dir):
            # __pycache__ ディレクトリを走査対象から除外
            dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES]
            for fname in files:
                full_path = os.path.join(root, fname)
                if _should_exclude(full_path):
                    continue
                rel_path = os.path.relpath(full_path, site_dir)
                arc_name = os.path.join("html", rel_path)
                zf.write(full_path, arc_name)
                file_count += 1

        # 2. docs/slides/ → slides/ として PDF/PPTX のみ収集
        slides_dir = os.path.join(docs_dir, "slides")
        if os.path.isdir(slides_dir):
            for fname in os.listdir(slides_dir):
                _, ext = os.path.splitext(fname)
                if ext.lower() not in SLIDE_EXTENSIONS:
                    continue
                full_path = os.path.join(slides_dir, fname)
                if not os.path.isfile(full_path):
                    continue
                if _should_exclude(full_path):
                    continue
                arc_name = os.path.join("slides", fname)
                zf.write(full_path, arc_name)
                file_count += 1

        # 3. README.txt を ZIP ルートに追加
        index_path = os.path.join(docs_dir, "index.md")
        readme_content = convert_index_to_readme(index_path)
        zf.writestr("README.txt", readme_content)
        file_count += 1

    zip_size = os.path.getsize(output)

    return {
        "success": True,
        "path": output,
        "size": zip_size,
        "file_count": file_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="ドキュメント成果物を ZIP にパッケージング"
    )
    parser.add_argument(
        "--docs-dir",
        default="./docs",
        help="docs/ ディレクトリのパス (default: ./docs)",
    )
    parser.add_argument(
        "--site-dir",
        default="./site",
        help="site/ ディレクトリのパス (default: ./site)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="出力 ZIP ファイルパス (default: auto-generated)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="プロジェクト名（ファイル名に使用）",
    )

    args = parser.parse_args()

    output = args.output
    if output is None:
        output = generate_default_filename(args.name)

    result = build_zip(
        docs_dir=args.docs_dir,
        site_dir=args.site_dir,
        output=output,
        name=args.name,
    )

    if not result["success"]:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"ZIP created: {result['path']}")
    print(f"  Size:  {result['size']:,} bytes")
    print(f"  Files: {result['file_count']}")


if __name__ == "__main__":
    main()
