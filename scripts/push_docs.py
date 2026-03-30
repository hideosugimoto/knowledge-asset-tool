#!/usr/bin/env python3
"""
push_docs.py - Private リポジトリの場合のみ docs/ を git add してプッシュする

情報漏洩防止のため、Public リポジトリへの docs/ プッシュをブロックする。

使い方:
  python scripts/push_docs.py                    # docs/ を add + commit + push
  python scripts/push_docs.py --check-only       # Private 判定のみ（add/push しない）
  python scripts/push_docs.py --include-site      # site/ も含める
"""

import argparse
import json
import subprocess
import sys


def get_repo_visibility():
    """GitHub CLI でリポジトリの可視性を取得する。

    Returns:
        "PRIVATE", "PUBLIC", "INTERNAL", or None (エラー時)
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "visibility"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            # gh が未インストール or 未認証の場合
            return None
        data = json.loads(result.stdout)
        return data.get("visibility", None)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def get_repo_name():
    """リポジトリ名を取得する。"""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "(不明)"


def main():
    parser = argparse.ArgumentParser(
        description="Private リポジトリの場合のみ docs/ をプッシュする"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Private 判定のみ行い、add/push はしない",
    )
    parser.add_argument(
        "--include-site",
        action="store_true",
        help="site/ ディレクトリも含める",
    )
    parser.add_argument(
        "--message", "-m",
        default=None,
        help="コミットメッセージ（省略時は自動生成）",
    )
    args = parser.parse_args()

    repo_name = get_repo_name()
    visibility = get_repo_visibility()

    if visibility is None:
        print("[ERROR] リポジトリの可視性を取得できませんでした。")
        print("  以下を確認してください:")
        print("  1. gh (GitHub CLI) がインストールされているか: brew install gh")
        print("  2. gh auth login で認証済みか")
        print("  3. git リポジトリのルートで実行しているか")
        sys.exit(2)

    print(f"[INFO] リポジトリ: {repo_name}")
    print(f"[INFO] 可視性: {visibility}")

    if visibility != "PRIVATE":
        print("")
        print("=" * 60)
        print("  ⛔ docs/ のプッシュをブロックしました")
        print("")
        print(f"  リポジトリ {repo_name} は {visibility} です。")
        print("  生成ドキュメントには機密情報（DB構造、API仕様、")
        print("  ビジネスロジック等）が含まれる可能性があります。")
        print("")
        print("  対処方法:")
        print("    1. リポジトリを Private に変更する")
        print("       gh repo edit --visibility private")
        print("    2. または docs/ は .gitignore のまま")
        print("       ローカルの site/ を直接共有する")
        print("=" * 60)
        sys.exit(1)

    print("[OK] Private リポジトリです。docs/ のプッシュを許可します。")

    if args.check_only:
        sys.exit(0)

    # docs/ を git add
    add_targets = ["docs/"]
    if args.include_site:
        add_targets.append("site/")

    for target in add_targets:
        print(f"[INFO] git add -f {target}")
        result = subprocess.run(
            ["git", "add", "-f", target],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[ERROR] git add -f {target} に失敗: {result.stderr}")
            sys.exit(1)

    # コミット
    message = args.message or "docs: update generated documentation"
    print(f"[INFO] git commit -m '{message}'")
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            print("[INFO] 変更なし。コミットをスキップします。")
        else:
            print(f"[ERROR] git commit に失敗: {result.stderr}")
            sys.exit(1)

    # プッシュ
    print("[INFO] git push")
    result = subprocess.run(
        ["git", "push"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[ERROR] git push に失敗: {result.stderr}")
        sys.exit(1)

    print("")
    print("[OK] docs/ のプッシュが完了しました。")
    print(f"  GitHub上で閲覧: https://github.com/{repo_name}/tree/main/docs")


if __name__ == "__main__":
    main()
