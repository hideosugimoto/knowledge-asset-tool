#!/usr/bin/env python3
"""cache_analysis.py - コード探索結果のキャッシュ機構

同一 /go セッション内で複数コマンドが再スキャンなしに結果を再利用できるよう、
解析結果を JSON キャッシュファイルに保存・復元する。

Usage:
    python3 scripts/cache_analysis.py --source-dir /path --action save|load|check|clear
    python3 scripts/cache_analysis.py --source-dir /path --action save --cache-dir .cache
    python3 scripts/cache_analysis.py --source-dir /path --action save-facts --name myapp
    python3 scripts/cache_analysis.py --source-dir /path --action load-facts --name myapp
    python3 scripts/cache_analysis.py --source-dir /path --action check-facts --name myapp
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml  # PyYAML — used only for facts caching


def _get_git_commit_hash(source_dir: str) -> str:
    """ソースディレクトリの最新 git commit ハッシュを取得する。

    git リポジトリでない場合やエラー時は空文字を返す。
    """
    try:
        result = subprocess.run(
            ["git", "-C", source_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _compute_cache_key(source_dir: str) -> str:
    """ソースディレクトリのパスと git commit ハッシュからキャッシュキーを計算する。

    Returns:
        SHA256 ハッシュ文字列
    """
    abs_path = os.path.abspath(source_dir)
    git_hash = _get_git_commit_hash(source_dir)
    raw = f"{abs_path}:{git_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_file_path(source_dir: str, cache_base: str) -> str:
    """キャッシュファイルのパスを返す。"""
    key = _compute_cache_key(source_dir)
    return os.path.join(cache_base, f"analysis-{key}.json")


def save_cache(source_dir: str, data: dict, cache_base: str = ".cache") -> str:
    """解析結果をキャッシュに保存する。

    Args:
        source_dir: ソースディレクトリのパス
        data: 保存するデータ (file_list, project_type, directory_structure, key_files_summary)
        cache_base: キャッシュディレクトリのベースパス

    Returns:
        キャッシュファイルのパス
    """
    os.makedirs(cache_base, exist_ok=True)

    cache_path = _cache_file_path(source_dir, cache_base)
    envelope = {
        "source_dir": os.path.abspath(source_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

    return cache_path


def load_cache(source_dir: str, cache_base: str = ".cache") -> dict | None:
    """キャッシュから解析結果を読み込む。

    Args:
        source_dir: ソースディレクトリのパス
        cache_base: キャッシュディレクトリのベースパス

    Returns:
        キャッシュデータの dict。存在しない場合は None。
    """
    cache_path = _cache_file_path(source_dir, cache_base)

    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            envelope = json.load(f)
        return envelope.get("data")
    except (json.JSONDecodeError, OSError):
        return None


def is_cache_valid(
    source_dir: str,
    max_age_seconds: int = 3600,
    cache_base: str = ".cache",
) -> bool:
    """キャッシュが存在し、有効期限内かどうかをチェックする。

    Args:
        source_dir: ソースディレクトリのパス
        max_age_seconds: キャッシュの最大有効秒数 (デフォルト: 3600)
        cache_base: キャッシュディレクトリのベースパス

    Returns:
        キャッシュが有効なら True、それ以外は False
    """
    cache_path = _cache_file_path(source_dir, cache_base)

    if not os.path.exists(cache_path):
        return False

    try:
        file_mtime = os.path.getmtime(cache_path)
        age = time.time() - file_mtime
        return age <= max_age_seconds
    except OSError:
        return False


def clear_cache(cache_base: str = ".cache") -> int:
    """キャッシュディレクトリ内の全キャッシュファイルを削除する。

    Args:
        cache_base: キャッシュディレクトリのベースパス

    Returns:
        削除したファイル数
    """
    if not os.path.isdir(cache_base):
        return 0

    removed = 0
    for fname in os.listdir(cache_base):
        is_analysis = fname.startswith("analysis-") and fname.endswith(".json")
        is_facts = fname.startswith("facts-") and fname.endswith(".yaml")
        if is_analysis or is_facts:
            fpath = os.path.join(cache_base, fname)
            try:
                os.remove(fpath)
                removed += 1
            except OSError:
                pass

    return removed


def _facts_cache_path(name: str, cache_base: str) -> str:
    """ファクトキャッシュファイルのパスを返す。"""
    return os.path.join(cache_base, f"facts-{name}.yaml")


def _count_source_files(source_dir: str) -> int:
    """ソースディレクトリ内のファイル数をカウントする。"""
    count = 0
    skip_dirs = {
        "node_modules", "vendor", ".git", "dist", "build",
        "__pycache__", ".next", ".nuxt", ".cache",
    }
    for _dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        count += len(filenames)
    return count


def save_facts(
    source_dir: str,
    name: str,
    facts_yaml: str,
    output_dir: str = ".cache",
) -> str:
    """Save fact collection results with source directory hash and git commit.

    Args:
        source_dir: ソースディレクトリのパス
        name: プロジェクト/機能名
        facts_yaml: ファクト収集結果の YAML 文字列
        output_dir: キャッシュ出力ディレクトリ

    Returns:
        保存先ファイルパス
    """
    os.makedirs(output_dir, exist_ok=True)
    cache_path = _facts_cache_path(name, output_dir)

    # YAML 文字列をパースしてファクトデータを取得
    try:
        facts_data = yaml.safe_load(facts_yaml)
    except yaml.YAMLError:
        facts_data = {"_raw": facts_yaml}

    envelope = {
        "_meta": {
            "name": name,
            "source_dir": os.path.abspath(source_dir),
            "git_commit": _get_git_commit_hash(source_dir),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": _count_source_files(source_dir),
            "facts_version": 1,
        },
        "facts": facts_data.get("facts", facts_data) if isinstance(facts_data, dict) else facts_data,
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        yaml.dump(
            envelope,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    return cache_path


def load_facts(
    source_dir: str,
    name: str,
    output_dir: str = ".cache",
    max_age: int = 3600,
) -> dict | None:
    """Load cached facts if still valid (source hasn't changed).

    Args:
        source_dir: ソースディレクトリのパス
        name: プロジェクト/機能名
        output_dir: キャッシュディレクトリ
        max_age: キャッシュの最大有効秒数 (デフォルト: 3600)

    Returns:
        キャッシュデータの dict（_meta + facts）。無効または存在しない場合は None。
    """
    cache_path = _facts_cache_path(name, output_dir)

    if not os.path.exists(cache_path):
        return None

    # 有効期限チェック
    try:
        file_mtime = os.path.getmtime(cache_path)
        age = time.time() - file_mtime
        if age > max_age:
            return None
    except OSError:
        return None

    # git commit が一致するかチェック
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            envelope = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None

    if not isinstance(envelope, dict) or "_meta" not in envelope:
        return None

    cached_commit = envelope["_meta"].get("git_commit", "")
    current_commit = _get_git_commit_hash(source_dir)

    # git commit が変わっていたらキャッシュ無効
    if cached_commit and current_commit and cached_commit != current_commit:
        return None

    return envelope


def facts_changed(
    source_dir: str,
    name: str,
    output_dir: str = ".cache",
) -> list[str]:
    """Check if source has changed since facts were cached.

    Args:
        source_dir: ソースディレクトリのパス
        name: プロジェクト/機能名
        output_dir: キャッシュディレクトリ

    Returns:
        変更されたファイルのリスト。キャッシュが存在しない場合は ["(no cache)"]。
    """
    cache_path = _facts_cache_path(name, output_dir)

    if not os.path.exists(cache_path):
        return ["(no cache)"]

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            envelope = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return ["(unreadable cache)"]

    if not isinstance(envelope, dict) or "_meta" not in envelope:
        return ["(invalid cache)"]

    cached_commit = envelope["_meta"].get("git_commit", "")
    current_commit = _get_git_commit_hash(source_dir)

    if not cached_commit or not current_commit:
        return ["(no git info)"]

    if cached_commit == current_commit:
        return []

    # git diff で変更ファイルを取得
    try:
        result = subprocess.run(
            ["git", "-C", source_dir, "diff", "--name-only", cached_commit, current_commit],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
    except (OSError, subprocess.TimeoutExpired):
        pass

    return [f"(commit changed: {cached_commit[:8]} -> {current_commit[:8]})"]


def _gather_analysis_data(source_dir: str) -> dict:
    """ソースディレクトリの簡易解析を行いキャッシュ用データを生成する。"""
    file_list = []
    directory_structure = {}

    for dirpath, dirnames, filenames in os.walk(source_dir):
        # 除外ディレクトリ
        dirnames[:] = [
            d for d in dirnames
            if d not in {
                "node_modules", "vendor", ".git", "dist", "build",
                "__pycache__", ".next", ".nuxt", ".cache",
            }
        ]
        rel_dir = os.path.relpath(dirpath, source_dir)
        if rel_dir == ".":
            rel_dir = ""

        dir_files = []
        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            rel_path = rel_path.replace("\\", "/")
            file_list.append(rel_path)
            dir_files.append(fname)

        if dir_files:
            key = rel_dir if rel_dir else "."
            directory_structure[key] = dir_files

    # プロジェクトタイプの簡易検出
    project_type = "generic"
    pkg_path = os.path.join(source_dir, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "express" in deps:
                project_type = "express"
            elif "next" in deps:
                project_type = "nextjs"
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "file_list": file_list,
        "project_type": project_type,
        "directory_structure": directory_structure,
        "key_files_summary": {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="コード探索結果のキャッシュ管理"
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="ソースディレクトリのパス",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "save", "load", "check", "clear",
            "save-facts", "load-facts", "check-facts",
        ],
        help="実行するアクション",
    )
    parser.add_argument(
        "--name",
        default="",
        help="ファクトキャッシュ名（save-facts/load-facts/check-facts で使用）",
    )
    parser.add_argument(
        "--facts-yaml",
        default="",
        help="保存するファクト YAML 文字列（save-facts で使用。省略時は stdin から読む）",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="キャッシュディレクトリ (default: .cache)",
    )
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source_dir)
    cache_base = args.cache_dir

    if args.action == "save":
        data = _gather_analysis_data(source_dir)
        path = save_cache(source_dir, data, cache_base=cache_base)
        print(f"[OK] Cache saved: {path}")

    elif args.action == "load":
        result = load_cache(source_dir, cache_base=cache_base)
        if result is None:
            print("[INFO] No cache found")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.action == "check":
        valid = is_cache_valid(source_dir, cache_base=cache_base)
        if valid:
            print("[OK] Cache is valid")
        else:
            print("[INFO] Cache is invalid or missing")

    elif args.action == "clear":
        count = clear_cache(cache_base=cache_base)
        print(f"[OK] Cleared {count} cache file(s)")

    elif args.action == "save-facts":
        if not args.name:
            print("[ERROR] --name is required for save-facts", file=sys.stderr)
            sys.exit(1)
        facts_input = args.facts_yaml if args.facts_yaml else sys.stdin.read()
        path = save_facts(
            source_dir, args.name, facts_input, output_dir=cache_base
        )
        print(f"[OK] Facts saved: {path}")

    elif args.action == "load-facts":
        if not args.name:
            print("[ERROR] --name is required for load-facts", file=sys.stderr)
            sys.exit(1)
        result = load_facts(
            source_dir, args.name, output_dir=cache_base
        )
        if result is None:
            print("[INFO] No valid facts cache found")
            sys.exit(1)
        else:
            meta = result.get("_meta", {})
            print(
                f"[OK] Facts loaded (generated: {meta.get('generated_at', '?')}, "
                f"commit: {meta.get('git_commit', '?')[:8]})"
            )
            print(
                yaml.dump(
                    result,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            )

    elif args.action == "check-facts":
        if not args.name:
            print("[ERROR] --name is required for check-facts", file=sys.stderr)
            sys.exit(1)
        changed = facts_changed(
            source_dir, args.name, output_dir=cache_base
        )
        if not changed:
            # キャッシュ有効 — メタデータも表示
            cached = load_facts(
                source_dir, args.name, output_dir=cache_base
            )
            if cached:
                meta = cached.get("_meta", {})
                print(
                    f"[OK] Facts cache is valid "
                    f"(generated: {meta.get('generated_at', '?')}, "
                    f"commit: {meta.get('git_commit', '?')[:8]})"
                )
            else:
                print("[INFO] Facts cache is invalid or expired")
                sys.exit(1)
        else:
            print(f"[INFO] Facts cache is invalid — changed: {', '.join(changed)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
