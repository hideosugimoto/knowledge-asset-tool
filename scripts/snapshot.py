#!/usr/bin/env python3
"""snapshot.py - ドキュメントファイルのリグレッションスナップショット

生成されたドキュメントファイルのハッシュを保存し、
前回のスナップショットと比較して意図しない変更を検出する。

Usage:
    python3 scripts/snapshot.py --docs-dir ./docs --action create
    python3 scripts/snapshot.py --docs-dir ./docs --action compare --baseline baseline.json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def _hash_file(filepath: str) -> str:
    """ファイルの SHA256 ハッシュを計算する。"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_snapshot(docs_dir: str) -> dict:
    """ドキュメントディレクトリのスナップショットを作成する。

    Args:
        docs_dir: ドキュメントディレクトリのパス

    Returns:
        {"files": {"relative/path": "sha256hash", ...}, "created_at": "ISO timestamp"}
    """
    files = {}

    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, docs_dir)
            rel_path = rel_path.replace("\\", "/")
            files[rel_path] = _hash_file(full_path)

    return {
        "files": files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def compare_snapshots(old_snapshot: dict, new_snapshot: dict) -> dict:
    """2つのスナップショットを比較し、変更レポートを返す。

    Args:
        old_snapshot: ベースラインスナップショット
        new_snapshot: 新しいスナップショット

    Returns:
        {
            "added": [追加されたファイル],
            "removed": [削除されたファイル],
            "changed": [変更されたファイル],
            "has_changes": bool,
        }
    """
    old_files = old_snapshot.get("files", {})
    new_files = new_snapshot.get("files", {})

    old_keys = set(old_files.keys())
    new_keys = set(new_files.keys())

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)

    changed = sorted(
        key for key in (old_keys & new_keys)
        if old_files[key] != new_files[key]
    )

    has_changes = bool(added or removed or changed)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "has_changes": has_changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ドキュメントファイルのリグレッションスナップショット"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="ドキュメントディレクトリのパス",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["create", "compare"],
        help="実行するアクション",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="比較用ベースラインスナップショットのパス (compare 時必須)",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=".snapshots",
        help="スナップショット保存ディレクトリ (default: .snapshots)",
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)

    if args.action == "create":
        snapshot = create_snapshot(docs_dir)

        os.makedirs(args.snapshot_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        snapshot_path = os.path.join(args.snapshot_dir, f"snapshot-{timestamp}.json")

        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        print(f"[OK] Snapshot created: {snapshot_path}")
        print(f"  Files: {len(snapshot['files'])}")

    elif args.action == "compare":
        if not args.baseline:
            print("[ERROR] --baseline is required for compare action", file=sys.stderr)
            sys.exit(2)

        baseline_path = os.path.abspath(args.baseline)
        if not os.path.exists(baseline_path):
            print(f"[ERROR] Baseline not found: {baseline_path}", file=sys.stderr)
            sys.exit(2)

        with open(baseline_path, "r", encoding="utf-8") as f:
            old_snapshot = json.load(f)

        new_snapshot = create_snapshot(docs_dir)
        result = compare_snapshots(old_snapshot, new_snapshot)

        if result["has_changes"]:
            print(f"[CHANGED] Differences detected:")
            if result["added"]:
                print(f"  Added ({len(result['added'])}):")
                for p in result["added"]:
                    print(f"    + {p}")
            if result["removed"]:
                print(f"  Removed ({len(result['removed'])}):")
                for p in result["removed"]:
                    print(f"    - {p}")
            if result["changed"]:
                print(f"  Changed ({len(result['changed'])}):")
                for p in result["changed"]:
                    print(f"    ~ {p}")
            sys.exit(1)
        else:
            print("[OK] No changes detected")
            sys.exit(0)


if __name__ == "__main__":
    main()
