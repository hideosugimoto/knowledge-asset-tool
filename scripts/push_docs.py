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
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


# 可視性を判定できるホスト。ここに完全一致する場合のみ owner/repo を解決する。
# 部分一致にすると notgithub.com や evil.com/github.com/... が
# github.com のリポジトリの可視性で判定されてしまう（fail open）。
GITHUB_HOSTS = frozenset({"github.com"})

# プロジェクト名として許可する文字。グロブ文字（* ? [）やパス区切りを弾く。
PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# scp 形式の remote URL: [user@]host:path
SCP_LIKE_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")


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


# ---------------------------------------------------------------------------
# remote URL の解析
# ---------------------------------------------------------------------------

def parse_remote_url(url):
    """remote URL を (host, path) に分解する。解析できなければ (None, None)。

    対応形式:
        https://github.com/owner/repo(.git)
        ssh://git@github.com:22/owner/repo(.git)
        git@github.com:owner/repo(.git)
    """
    if not url:
        return None, None
    url = url.strip()

    if "://" in url:
        parsed = urlparse(url)
        # hostname はユーザ情報とポートを除いた小文字のホスト名
        return parsed.hostname, parsed.path

    match = SCP_LIKE_RE.match(url)
    if not match:
        return None, None
    return match.group("host").lower(), match.group("path")


def resolve_owner_repo(url):
    """remote URL から owner/repo を解決する。

    ホスト名が GITHUB_HOSTS と**完全一致**する場合のみ解決する。
    部分一致（`"github.com" in url`）にすると notgithub.com や
    evil.example.com/github.com/... が github.com のリポジトリとして
    判定され、可視性チェックが fail open してしまう。

    判定できない場合は None を返す（呼び出し側は中止すること）。
    """
    host, path = parse_remote_url(url)
    if host is None or host.lower() not in GITHUB_HOSTS:
        return None

    path = (path or "").strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]

    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        # GitHub の remote は必ず owner/repo の 2 要素。
        # 要素数が違うものは解析できていないとみなして中止する。
        return None
    return f"{parts[0]}/{parts[1]}"


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

def is_valid_project_name(name):
    """プロジェクト名として安全な文字列かを判定する。

    グロブ文字（* ? [）を許すと、対象を絞るための --project が
    逆に全プロジェクトの成果物へ広がってしまうため弾く。
    パス区切りや .. も同様に弾く。
    """
    return bool(name) and bool(PROJECT_NAME_RE.match(name)) and ".." not in name


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
    """指定プロジェクトの成果物パス（存在するものだけ）を返す。

    name が不正な場合は空リストを返す（呼び出し前に is_valid_project_name で
    検証すること）。
    """
    if not is_valid_project_name(name):
        return []

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
# 各ステップ
# ---------------------------------------------------------------------------

def resolve_push_context():
    """push 先の情報をまとめて解決する。

    Returns:
        (context dict, None) または (None, 終了コード)
    """
    branch = get_current_branch()
    if branch is None:
        print("[ERROR] detached HEAD 状態です。ブランチをチェックアウトしてください。")
        return None, 2

    remote, dest_ref = get_push_target(branch)
    remote_url = get_remote_url(remote)
    if remote_url is None:
        print(f"[ERROR] リモート '{remote}' が見つかりません。")
        return None, 2

    owner_repo = resolve_owner_repo(remote_url)
    if owner_repo is None:
        print(f"[ERROR] リモート URL から owner/repo を解決できませんでした: {remote_url}")
        print(f"  可視性を判定できるホスト: {', '.join(sorted(GITHUB_HOSTS))}")
        print("  判定できないホストへの push は安全のため中止します。")
        return None, 2

    return {
        "branch": branch,
        "remote": remote,
        "dest_ref": dest_ref,
        "remote_url": remote_url,
        "owner_repo": owner_repo,
    }, None


def check_visibility(context):
    """push 先が Private か判定する。0 なら続行可、非 0 なら終了コード。"""
    owner_repo = context["owner_repo"]
    visibility = get_repo_visibility(owner_repo)

    print(f"[INFO] ブランチ: {context['branch']}")
    print(f"[INFO] push 先リモート: {context['remote']} ({context['remote_url']})")
    print(f"[INFO] push 先 ref: {context['dest_ref'] or 'refs/heads/' + context['branch']}")
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
    return 0


def determine_targets(repo_root, args):
    """add 対象のパス一覧を決める。エラー時は None。"""
    if args.project:
        if not is_valid_project_name(args.project):
            print(f"[ERROR] プロジェクト名が不正です: {args.project!r}")
            print("  使用できるのは英数字と . _ - のみです（先頭は英数字）。")
            return None
        targets = project_paths(repo_root, args.project)
        if not targets:
            print(f"[ERROR] プロジェクト '{args.project}' の成果物が見つかりません。")
            known = discover_projects(repo_root)
            if known:
                print(f"  検出済みプロジェクト: {', '.join(known)}")
            return None
    else:
        targets = ["docs/"]

    if args.include_site:
        targets.append("site/")
    return targets


def confirm_targets(repo_root, targets, args):
    """add 対象を表示し、必要なら確認を取る。続行するなら True。"""
    print("")
    print("[INFO] add 対象:")
    for target in targets:
        print(f"  - {target}")

    if args.project or args.yes:
        return True

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
        return False
    return True


def stage_targets(targets):
    """対象を git add する。成功なら True。"""
    for target in targets:
        print(f"[INFO] git add -f {target}")
        result = _git("add", "-f", target)
        if result.returncode != 0:
            print(f"[ERROR] git add -f {target} に失敗: {result.stderr}")
            return False
    return True


def has_staged_changes(targets):
    """対象パスに staged な変更があるか判定する。

    Returns:
        True / False / None（判定失敗）
    """
    # git diff --quiet: 差分なし=0, 差分あり=1, エラー=2以上
    result = _git("diff", "--cached", "--quiet", "--", *targets)
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    print(f"[ERROR] git diff --cached に失敗: {result.stderr}")
    return None


def commit_targets(targets, message):
    """対象パスに限定してコミットする。成功なら True。

    パススペックを付けないと、事前に staged だった無関係な変更まで
    巻き込んでコミットしてしまうため、必ず対象を限定する。

    「変更なし」の判定は git のメッセージ文字列ではなく
    git diff --cached の終了コードで行う（メッセージはロケール依存のため）。
    """
    staged = has_staged_changes(targets)
    if staged is None:
        return False
    if staged is False:
        print("[INFO] 変更なし。コミットをスキップします。")
        return True

    print(f"[INFO] git commit -m '{message}' -- {' '.join(targets)}")
    result = _git("commit", "-m", message, "--", *targets)
    if result.returncode != 0:
        print(f"[ERROR] git commit に失敗: {result.stderr or result.stdout}")
        return False
    return True


def push_branch(context):
    """push 先を明示して push する。成功なら True。"""
    dest_ref = context["dest_ref"]
    remote = context["remote"]
    push_args = ["push", remote, f"HEAD:{dest_ref}"] if dest_ref else ["push", remote, "HEAD"]
    print(f"[INFO] git {' '.join(push_args)}")
    result = _git(*push_args)
    if result.returncode != 0:
        print(f"[ERROR] git push に失敗: {result.stderr}")
        return False
    return True


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args(argv=None):
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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    repo_root = get_repo_root()
    if repo_root is None:
        print("[ERROR] git リポジトリ内で実行してください。")
        return 2

    context, error_code = resolve_push_context()
    if context is None:
        return error_code

    visibility_code = check_visibility(context)
    if visibility_code != 0:
        return visibility_code

    if args.check_only:
        return 0

    targets = determine_targets(repo_root, args)
    if targets is None:
        return 1

    if not confirm_targets(repo_root, targets, args):
        return 0

    if not stage_targets(targets):
        return 1

    suffix = f" ({args.project})" if args.project else ""
    message = args.message or f"docs: update generated documentation{suffix}"
    if not commit_targets(targets, message):
        return 1

    if not push_branch(context):
        return 1

    print("")
    print("[OK] docs/ のプッシュが完了しました。")
    print(f"  GitHub上で閲覧: "
          f"https://github.com/{context['owner_repo']}/tree/{context['branch']}/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
