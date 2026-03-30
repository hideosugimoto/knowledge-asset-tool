#!/usr/bin/env python3
"""
check_freshness.py - ドキュメントの鮮度チェック

ソースコードの最終更新日とドキュメントの生成日を比較し、
古くなっている可能性のあるドキュメントを警告します。

使い方:
  python scripts/check_freshness.py --source-dir ./src --docs-dir ./docs
  python scripts/check_freshness.py --source-dir ./src --docs-dir ./docs --threshold 7
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta


def get_git_last_modified(path):
    """git log からファイルまたはディレクトリの最終更新日を取得する。"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            date_str = result.stdout.strip()
            return datetime.fromisoformat(date_str)
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return None


def get_doc_generated_date(doc_path):
    """ドキュメントのヘッダーまたは frontmatter から生成日を取得する。"""
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read(2000)
    except (OSError, UnicodeDecodeError):
        return None

    patterns = [
        r"last_updated:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?",
        r"生成日:\s*(\d{4}-\d{2}-\d{2})",
        r"Generated:\s*(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            except ValueError:
                continue

    stat = os.stat(doc_path)
    return datetime.fromtimestamp(stat.st_mtime)


def main():
    parser = argparse.ArgumentParser(description="ドキュメントの鮮度チェック")
    parser.add_argument(
        "--source-dir", required=True, help="ソースコードのディレクトリ"
    )
    parser.add_argument(
        "--docs-dir", default="./docs", help="ドキュメントのディレクトリ"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=7,
        help="警告を出す日数の閾値（デフォルト: 7日）",
    )
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source_dir)
    docs_dir = os.path.abspath(args.docs_dir)
    threshold = timedelta(days=args.threshold)

    if not os.path.isdir(source_dir):
        print(f"[ERROR] ソースディレクトリが見つかりません: {source_dir}")
        sys.exit(1)

    if not os.path.isdir(docs_dir):
        print(f"[ERROR] ドキュメントディレクトリが見つかりません: {docs_dir}")
        sys.exit(1)

    source_last_modified = get_git_last_modified(source_dir)
    if not source_last_modified:
        stat = os.stat(source_dir)
        source_last_modified = datetime.fromtimestamp(stat.st_mtime)

    print(f"[INFO] ソースコード最終更新: {source_last_modified.strftime('%Y-%m-%d')}")
    print(f"[INFO] 閾値: {args.threshold}日")
    print("")

    stale = []
    fresh = []
    unknown = []

    for root, dirs, files in os.walk(docs_dir):
        for fname in sorted(files):
            if not fname.endswith((".md", ".yaml", ".yml")):
                continue

            doc_path = os.path.join(root, fname)
            rel_path = os.path.relpath(doc_path, docs_dir)
            doc_date = get_doc_generated_date(doc_path)

            if not doc_date:
                unknown.append(rel_path)
                continue

            age = source_last_modified - doc_date
            if age > threshold:
                stale.append((rel_path, doc_date, age.days))
            else:
                fresh.append((rel_path, doc_date))

    if fresh:
        print(f"[OK] 最新のドキュメント: {len(fresh)} ファイル")

    if stale:
        print("")
        print(f"[WARN] 古くなっている可能性: {len(stale)} ファイル")
        print("")
        for rel, date, days in sorted(stale, key=lambda x: -x[2]):
            print(f"  {rel}")
            print(f"    生成日: {date.strftime('%Y-%m-%d')} ({days}日前にソース更新あり)")
        print("")
        print("再生成を検討してください:")
        print("  /project:go でドキュメントを再生成")

    if unknown:
        print("")
        print(f"[INFO] 生成日が不明: {len(unknown)} ファイル")
        for rel in unknown:
            print(f"  {rel}")

    if not stale:
        print("")
        print("[OK] 全ドキュメントが最新です。")


if __name__ == "__main__":
    main()
