#!/usr/bin/env python3
"""
log_generation.py - 生成履歴ログへのエントリ追記

生成完了時に .cache/generation-log.json へエントリを追加する。

使い方:
  python scripts/log_generation.py \
    --name system-name \
    --mode i \
    --source-dir /path/to/source \
    --file-count 108 \
    --duration-estimate "30-45分"
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime


LOG_FILE = os.path.join(".cache", "generation-log.json")


def get_git_commit(source_dir):
    """ソースディレクトリの最新コミットハッシュを取得する。"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", source_dir],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return "unknown"


def load_log(log_path):
    """既存のログファイルを読み込む。存在しなければ空のエントリリストを返す。"""
    if os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "entries" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"entries": []}


def save_log(log_path, data):
    """ログファイルを書き出す。"""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="生成履歴ログへのエントリ追記")
    parser.add_argument("--name", required=True, help="プロジェクト/システム名")
    parser.add_argument("--mode", required=True, help="出力モード（例: i, b, f）")
    parser.add_argument("--source-dir", required=True, help="ソースコードのディレクトリ")
    parser.add_argument("--file-count", type=int, default=0, help="生成されたファイル数")
    parser.add_argument("--duration-estimate", default="", help="推定所要時間")
    parser.add_argument("--log-file", default=LOG_FILE, help="ログファイルのパス")
    args = parser.parse_args()

    git_commit = get_git_commit(os.path.abspath(args.source_dir))

    entry = {
        "name": args.name,
        "mode": args.mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit,
        "source_dir": os.path.abspath(args.source_dir),
        "file_count": args.file_count,
        "duration_estimate": args.duration_estimate,
    }

    data = load_log(args.log_file)
    data["entries"].append(entry)
    save_log(args.log_file, data)

    print(f"[OK] 生成履歴を記録しました: {args.log_file}")
    print(f"     name={args.name}, mode={args.mode}, commit={git_commit}")


if __name__ == "__main__":
    main()
