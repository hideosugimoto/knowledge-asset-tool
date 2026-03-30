#!/usr/bin/env python3
"""
freshness_badge.py - ドキュメント鮮度バッジ生成

ファクトキャッシュとgitログから鮮度を判定し、
Markdownバッジ行を出力する。

使い方:
  python scripts/freshness_badge.py --source-dir /path --name system-name --docs-dir ./docs
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

# 鮮度判定の閾値（日数）
FRESHNESS_THRESHOLD_DAYS = 7


def get_facts_generation_date(cache_dir, name):
    """ファクトキャッシュから生成日を取得する。"""
    facts_path = os.path.join(cache_dir, f"facts-{name}.yaml")
    if not os.path.isfile(facts_path):
        return None

    try:
        with open(facts_path, "r", encoding="utf-8") as f:
            content = f.read(2000)
    except (OSError, UnicodeDecodeError):
        return None

    patterns = [
        r"generated_at:\s*[\"']?(\d{4}-\d{2}-\d{2}(?:T[\d:]+)?)[\"']?",
        r"date:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            date_str = match.group(1)[:10]
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

    stat = os.stat(facts_path)
    return datetime.fromtimestamp(stat.st_mtime).date()


def get_git_last_commit_date(source_dir):
    """ソースディレクトリの最終コミット日を取得する。"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", source_dir],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            date_str = result.stdout.strip()[:10]
            return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return None


def generate_badge(generation_date, source_date):
    """鮮度バッジのMarkdown行を生成する。"""
    if generation_date is None:
        return "> 📊 鮮度: ❓ 不明（ファクトキャッシュが見つかりません）"

    gen_str = generation_date.isoformat()
    src_str = source_date.isoformat() if source_date else "不明"

    if source_date is None or generation_date >= source_date:
        return (
            f"> 📊 鮮度: ✅ 最新"
            f"（生成日: {gen_str}, ソース最終更新: {src_str}）"
        )

    delta_days = (source_date - generation_date).days
    if delta_days <= FRESHNESS_THRESHOLD_DAYS:
        return (
            f"> 📊 鮮度: ✅ 最新"
            f"（生成日: {gen_str}, ソース最終更新: {src_str}）"
        )

    return (
        f"> 📊 鮮度: ⚠️ 要更新"
        f"（生成日: {gen_str}, ソース最終更新: {src_str}"
        f" — {delta_days}日経過）"
    )


def insert_badge_into_index(docs_dir, name, badge_line):
    """docs/{name}-index.md にバッジを挿入（既存バッジがあれば置換）。"""
    index_path = os.path.join(docs_dir, f"{name}-index.md")
    if not os.path.isfile(index_path):
        print(f"[WARN] 目次ファイルが見つかりません: {index_path}", file=sys.stderr)
        return False

    with open(index_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    badge_marker = "> 📊 鮮度:"
    new_lines = []
    replaced = False
    for line in lines:
        if badge_marker in line:
            new_lines.append(badge_line + "\n")
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        # 最初の見出し（# ...）の直後に挿入
        inserted = False
        result = []
        for line in lines:
            result.append(line)
            if not inserted and line.startswith("# "):
                result.append("\n")
                result.append(badge_line + "\n")
                inserted = True
        if not inserted:
            result.insert(0, badge_line + "\n\n")
        new_lines = result

    with open(index_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return True


def main():
    parser = argparse.ArgumentParser(description="ドキュメント鮮度バッジ生成")
    parser.add_argument(
        "--source-dir", required=True, help="ソースコードのディレクトリ"
    )
    parser.add_argument(
        "--name", required=True, help="プロジェクト/システム名"
    )
    parser.add_argument(
        "--docs-dir", default="./docs", help="ドキュメントのディレクトリ"
    )
    parser.add_argument(
        "--insert",
        action="store_true",
        help="バッジを目次ファイルに挿入する（指定しない場合は標準出力のみ）",
    )
    args = parser.parse_args()

    cache_dir = os.path.join(os.path.dirname(args.docs_dir), ".cache")
    if not os.path.isdir(cache_dir):
        cache_dir = ".cache"

    generation_date = get_facts_generation_date(cache_dir, args.name)
    source_date = get_git_last_commit_date(os.path.abspath(args.source_dir))
    badge_line = generate_badge(generation_date, source_date)

    print(badge_line)

    if args.insert:
        ok = insert_badge_into_index(args.docs_dir, args.name, badge_line)
        if ok:
            print(f"[OK] バッジを {args.docs_dir}/{args.name}-index.md に挿入しました。")


if __name__ == "__main__":
    main()
