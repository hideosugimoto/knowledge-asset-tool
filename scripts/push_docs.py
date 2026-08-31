#!/usr/bin/env python3
"""
push_docs.py - Private リポジトリの場合のみ docs/ を git add してプッシュする

情報漏洩防止のため、Public リポジトリへの docs/ プッシュをブロックする。

可視性の判定は「実際に push する remote」に対して行う。
gh のリモート解決と git push の宛先がずれると、private な origin を根拠に
public な remote へ push してしまうため。

使い方:
  python3 scripts/push_docs.py                      # docs/ 全体を add + commit + push
  python3 scripts/push_docs.py --project my-app     # 指定プロジェクトの成果物のみ
  python3 scripts/push_docs.py --check-only         # Private 判定のみ（add/push しない）
  python3 scripts/push_docs.py --include-site       # site/ も含める
  python3 scripts/push_docs.py --yes                # 確認プロンプトを省略
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# git ヘルパ
# ---------------------------------------------------------------------------

def _git(*args, check=False):
    """git コマンドを実行して CompletedProcess を返す。"""
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=check
    )


def get_repo_root():
    """リポジトリルートを返す（git 管理外なら None）。"""
    result = _git("rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def get_current_branch():
    """現在のブランチ名を返す（detached HEAD なら None）。"""
    result = _git("rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return None if branch == "HEAD" else branch


def get_push_target(branch):
    """push 先の (remote 名, 宛先 ref) を決定する。

    plain `git push` と同じ宛先になるように、
    branch.<name>.remote → remote.pushDefault → origin の順で解決する。

    Returns:
        (remote_name, dest_ref or None)
    """
    remote = None
    if branch:
        result = _git("config", "--get", f"branch.{branch}.remote")
        if result.returncode == 0 and result.stdout.strip():
            remote = result.stdout.strip()

    if remote is None:
        result = _git("config", "--get", "remote.pushDefault")
        if result.returncode == 0 and result.stdout.strip():
            remote = result.stdout.strip()

    if remote is None:
        remote = "origin"

    dest_ref = None
    if branch:
        result = _git("config", "--get", f"branch.{branch}.merge")
        if result.returncode == 0 and result.stdout.strip():
            dest_ref = result.stdout.strip()

    return remote, dest_ref


def get_remote_url(remote):
    """remote の push 用 URL を返す（存在しなければ None）。"""
    result = _git("remote", "get-url", "--push", remote)
    if result.returncode != 0:
        result = _git("remote", "get-url", remote)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def resolve_owner_repo(url):
    """remote URL から owner/repo を解決する。

    対応形式:
        https://github.com/owner/repo(.git)
        git@github.com:owner/repo(.git)
        ssh://git@github.com/owner/repo(.git)

    GitHub 以外のホストは None を返す（可視性を判定できないため）。
    """
    if not url:
        return None
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[: -len(".git")]

    for sep in ("github.com:", "github.com/"):
        if sep in url:
            candidate = url.split(sep, 1)[1].strip("/")
            parts = candidate.split("/")
            if len(parts) >= 2 and parts[0] and parts[1]:
                return f"{parts[0]}/{parts[1]}"
    return None


# ---------------------------------------------------------------------------
# GitHub CLI
# ---------------------------------------------------------------------------

def get_repo_visibility(owner_repo):
    """gh CLI で指定リポジトリの可視性を取得する。

    Returns:
        "PRIVATE", "PUBLIC", "INTERNAL", or None (判定不能)
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", owner_repo, "--json", "visibility"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout).get("visibility")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# プロジェクト単位の対象パス解決
# ---------------------------------------------------------------------------

def discover_projects(repo_root):
    """docs/ 直下の {name}-index.md からプロジェクト名一覧を返す。"""
    docs = repo_root / "docs"
    if not docs.is_dir():
        return []
    names = []
    for path in sorted(docs.glob("*-index.md")):
        name = path.name[: -len("-index.md")]
        if name:
            names.append(name)
    return names


def project_paths(repo_root, name):
    """指定プロジェクトの成果物パス（存在するものだけ）を返す。"""
    docs = repo_root / "docs"
    candidates = [
        docs / f"{name}-index.md",
        docs / f"{name}-llms.txt",
        docs / f"{name}-AGENTS.md",
        docs / "architecture" / f"{name}.md",
        docs / "architecture" / f"{name}.rag.md",
        docs / "decisions" / f"{name}.md",
        docs / "manual" / name,
        docs / "explanations" / name,
        docs / "slides" / name,
    ]
    # スライドはファイル名接頭辞で置かれることもある
    slides = docs / "slides"
    if slides.is_dir():
        candidates.extend(sorted(slides.glob(f"{name}-*")))

    seen = []
    for path in candidates:
        if path.exists():
            rel = str(path.relative_to(repo_root))
            if rel not in seen:
                seen.append(rel)
    return seen


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Private リポジトリの場合のみ docs/ をプッシュする"
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Private 判定のみ行い、add/push はしない",
    )
    parser.add_argument(
        "--include-site", action="store_true",
        help="site/ ディレクトリも含める",
    )
    parser.add_argument(
        "--project", default=None,
        help="対象プロジェクト名（docs/{name}-index.md の {name}）。"
             "指定するとそのプロジェクトの成果物だけを add する",
    )
    parser.add_argument(
        "--message", "-m", default=None,
        help="コミットメッセージ（省略時は自動生成）",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="対象確認のプロンプトを省略する",
    )
    args = parser.parse_args(argv)

    repo_root = get_repo_root()
    if repo_root is None:
        print("[ERROR] git リポジトリ内で実行してください。")
        return 2

    # --- push 先の特定 --------------------------------------------------- #
    branch = get_current_branch()
    if branch is None:
        print("[ERROR] detached HEAD 状態です。ブランチをチェックアウトしてください。")
        return 2

    remote, dest_ref = get_push_target(branch)
    remote_url = get_remote_url(remote)
    if remote_url is None:
        print(f"[ERROR] リモート '{remote}' が見つかりません。")
        return 2

    owner_repo = resolve_owner_repo(remote_url)
    if owner_repo is None:
        print(f"[ERROR] リモート URL から owner/repo を解決できませんでした: {remote_url}")
        print("  GitHub 以外のホストは可視性を判定できないため中止します。")
        return 2

    visibility = get_repo_visibility(owner_repo)

    dest_label = dest_ref or f"refs/heads/{branch}"
    print(f"[INFO] ブランチ: {branch}")
    print(f"[INFO] push 先リモート: {remote} ({remote_url})")
    print(f"[INFO] push 先 ref: {dest_label}")
    print(f"[INFO] 可視性の判定対象: {owner_repo}  ← push 先と同一のリポジトリ")

    if visibility is None:
        print("[ERROR] リポジトリの可視性を取得できませんでした。")
        print("  以下を確認してください:")
        print("  1. gh (GitHub CLI) がインストールされているか: brew install gh")
        print("  2. gh auth login で認証済みか")
        print(f"  3. {owner_repo} を参照する権限があるか")
        return 2

    print(f"[INFO] 可視性: {visibility}")

    if visibility != "PRIVATE":
        print("")
        print("=" * 60)
        print("  ⛔ docs/ のプッシュをブロックしました")
        print("")
        print(f"  push 先 {owner_repo} は {visibility} です。")
        print("  生成ドキュメントには機密情報（DB構造、API仕様、")
        print("  ビジネスロジック等）が含まれる可能性があります。")
        print("")
        print("  対処方法:")
        print("    1. リポジトリを Private に変更する")
        print(f"       gh repo edit {owner_repo} --visibility private")
        print("    2. または docs/ は .gitignore のまま")
        print("       ローカルの site/ を直接共有する")
        print("=" * 60)
        return 1

    print("[OK] Private リポジトリです。docs/ のプッシュを許可します。")

    if args.check_only:
        return 0

    # --- add 対象の決定 --------------------------------------------------- #
    if args.project:
        targets = project_paths(repo_root, args.project)
        if not targets:
            print(f"[ERROR] プロジェクト '{args.project}' の成果物が見つかりません。")
            known = discover_projects(repo_root)
            if known:
                print(f"  検出済みプロジェクト: {', '.join(known)}")
            return 1
    else:
        targets = ["docs/"]

    if args.include_site:
        targets.append("site/")

    print("")
    print("[INFO] add 対象:")
    for target in targets:
        print(f"  - {target}")

    if not args.project and not args.yes:
        # docs/ 全体は複数プロジェクトの成果物が同居しうるため、内訳を見せて確認する
        projects = discover_projects(repo_root)
        if projects:
            print("")
            print(f"[WARN] docs/ 配下には {len(projects)} 件のプロジェクトの成果物があります:")
            for name in projects:
                print(f"  - {name}")
            print("  特定のプロジェクトだけを push するには --project <name> を使ってください。")
        print("")
        try:
            answer = input("上記すべてを push します。続行しますか？ (y/N): ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "y":
            print("[INFO] キャンセルしました。")
            return 0

    # --- git add ---------------------------------------------------------- #
    for target in targets:
        print(f"[INFO] git add -f {target}")
        result = _git("add", "-f", target)
        if result.returncode != 0:
            print(f"[ERROR] git add -f {target} に失敗: {result.stderr}")
            return 1

    # --- commit ----------------------------------------------------------- #
    if args.project:
        default_message = f"docs: update generated documentation ({args.project})"
    else:
        default_message = "docs: update generated documentation"
    message = args.message or default_message

    print(f"[INFO] git commit -m '{message}'")
    result = _git("commit", "-m", message)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            print("[INFO] 変更なし。コミットをスキップします。")
        else:
            print(f"[ERROR] git commit に失敗: {result.stderr}")
            return 1

    # --- push ------------------------------------------------------------- #
    if dest_ref:
        push_args = ["push", remote, f"HEAD:{dest_ref}"]
    else:
        push_args = ["push", remote, "HEAD"]
    print(f"[INFO] git {' '.join(push_args)}")
    result = _git(*push_args)
    if result.returncode != 0:
        print(f"[ERROR] git push に失敗: {result.stderr}")
        return 1

    print("")
    print("[OK] docs/ のプッシュが完了しました。")
    print(f"  GitHub上で閲覧: https://github.com/{owner_repo}/tree/{branch}/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
