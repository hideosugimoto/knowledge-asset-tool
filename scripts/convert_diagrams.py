#!/usr/bin/env python3
"""
convert_diagrams.py - .mmd ファイルを SVG に一括変換し、
Markdown 内のリンクを SVG 参照に書き換えるスクリプト。

使い方:
  python scripts/convert_diagrams.py --docs-dir ./docs
  python scripts/convert_diagrams.py --docs-dir ./docs --dry-run
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

MMDC_TIMEOUT = 30


def find_mmdc():
    """mmdc コマンドのパスを探す。"""
    path = shutil.which("mmdc")
    if path:
        return path
    print("[ERROR] mmdc が見つかりません。")
    print("   npm install -g @mermaid-js/mermaid-cli でインストールしてください。")
    sys.exit(1)


def convert_mmd_to_svg(mmdc_path, mmd_path, svg_path):
    """1つの .mmd ファイルを SVG に変換する。"""
    try:
        result = subprocess.run(
            [mmdc_path, "-i", mmd_path, "-o", svg_path, "-t", "neutral", "-b", "transparent"],
            capture_output=True,
            text=True,
            timeout=MMDC_TIMEOUT,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, None
    except subprocess.TimeoutExpired:
        return False, "timeout"


def update_markdown_links(md_path, mmd_to_svg_map, dry_run, add_external_link=False):
    """Markdown ファイル内の .mmd リンクを .svg に書き換える。"""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = 0

    for mmd_rel, svg_rel in mmd_to_svg_map.items():
        mmd_basename = os.path.basename(mmd_rel)
        svg_basename = os.path.basename(svg_rel)

        # [text](path.mmd) → [text](path.svg)
        new_content = re.sub(
            rf'\(([^)]*?){re.escape(mmd_basename)}\)',
            lambda m: f'({m.group(1)}{svg_basename})',
            content,
        )
        if new_content != content:
            changes += content.count(mmd_basename) - new_content.count(mmd_basename)
            content = new_content

    # --add-external-link: 画像リンク ![...](....svg) の直後に別ウィンドウリンクを挿入
    if add_external_link:
        svg_img_pattern = re.compile(
            r"(!\[[^\]]*\]\(([^)]+\.svg)\))"
            r"(?!\s*<a\s+href=)"  # 既にリンクが付いていない場合のみ
        )
        def _add_link(m):
            img_tag = m.group(1)
            svg_url = m.group(2)
            return f'{img_tag}\n<a href="{svg_url}" target="_blank">🔍 別ウィンドウで開く</a>'

        content = svg_img_pattern.sub(_add_link, content)

    if content != original:
        if not dry_run:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description=".mmd ファイルを SVG に変換し、Markdown リンクを書き換える"
    )
    parser.add_argument(
        "--docs-dir", default="./docs", help="docs ディレクトリのパス"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="変換・書き換えを実行せずに内容を表示"
    )
    parser.add_argument(
        "--add-external-link", action="store_true",
        help="SVG画像リンクの直後に「別ウィンドウで開く」リンクを自動挿入"
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)
    diagrams_dir = os.path.join(docs_dir, "diagrams")

    if not os.path.isdir(diagrams_dir):
        print(f"[ERROR] {diagrams_dir} が見つかりません。")
        sys.exit(1)

    mmdc_path = find_mmdc()

    # 1. .mmd ファイルを収集
    mmd_files = sorted(glob.glob(os.path.join(diagrams_dir, "*.mmd")))
    if not mmd_files:
        print("[INFO] 変換対象の .mmd ファイルがありません。")
        return

    print(f"[INFO] 変換対象: {len(mmd_files)} ファイル")
    print(f"[INFO] 出力先: {diagrams_dir} (同じディレクトリに .svg を生成)")
    if args.dry_run:
        print("[INFO] dry-run モード: 実際の変換は行いません")
    print("")

    # 2. 変換実行
    converted = 0
    failed = 0
    mmd_to_svg_map = {}

    for mmd_path in mmd_files:
        basename = os.path.splitext(os.path.basename(mmd_path))[0]
        svg_path = os.path.join(diagrams_dir, f"{basename}.svg")
        mmd_rel = os.path.relpath(mmd_path, docs_dir)
        svg_rel = os.path.relpath(svg_path, docs_dir)

        if args.dry_run:
            print(f"  [CONVERT] {mmd_rel} -> {svg_rel}")
            mmd_to_svg_map[mmd_rel] = svg_rel
            converted += 1
            continue

        ok, err = convert_mmd_to_svg(mmdc_path, mmd_path, svg_path)
        if ok:
            print(f"  [OK] {mmd_rel} -> {svg_rel}")
            mmd_to_svg_map[mmd_rel] = svg_rel
            converted += 1
        else:
            print(f"  [FAIL] {mmd_rel}: {err}")
            failed += 1

    print("")
    print(f"[INFO] 変換完了: {converted} 成功, {failed} 失敗")

    # 3. Markdown 内のリンクを書き換え
    md_files = sorted(
        glob.glob(os.path.join(docs_dir, "**", "*.md"), recursive=True)
    )

    updated = 0
    print("")
    print("[INFO] Markdown リンクを .mmd -> .svg に書き換え中...")

    for md_path in md_files:
        changed = update_markdown_links(md_path, mmd_to_svg_map, args.dry_run, args.add_external_link)
        if changed:
            rel = os.path.relpath(md_path, docs_dir)
            marker = "[DRY-RUN]" if args.dry_run else "[UPDATED]"
            print(f"  {marker} {rel}")
            updated += 1

    print("")
    if args.dry_run:
        print(f"[INFO] dry-run 完了: {converted} ファイル変換予定, {updated} ファイル書き換え予定")
    else:
        print(f"[OK] 完了: {converted} SVG 生成, {updated} Markdown 書き換え")


if __name__ == "__main__":
    main()
