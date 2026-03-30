#!/usr/bin/env python3
"""
save_output.py - Claude Code の出力をファイルに書き出すスクリプト

APIは一切使わない。Claudeの出力テキストを --- FILE: パス --- で分割して保存する。

使い方:
  python scripts/save_output.py --name user-authentication --output-dir ./docs
  python scripts/save_output.py --name user-authentication --output-dir ./docs --dry-run
  python scripts/save_output.py --name user-authentication --output-dir ./docs --force
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

MAX_INPUT_SIZE = 10 * 1024 * 1024  # 10 MB
PREVIEW_LENGTH = 200
SUBPROCESS_TIMEOUT = 5


def get_clipboard_content():
    """クリップボードからテキストを取得する。失敗時はNoneを返す。"""
    if shutil.which("pbpaste"):
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                check=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
    elif shutil.which("xclip"):
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                check=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
    return None


def get_input_text():
    """クリップボードまたはstdinからテキストを取得する。"""
    if not sys.stdin.isatty():
        text = sys.stdin.read(MAX_INPUT_SIZE)
        if text.strip():
            return text

    clipboard = get_clipboard_content()
    if clipboard and clipboard.strip():
        print("[INFO] クリップボードからテキストを取得しました。")
        return clipboard

    print("[ERROR] テキストが見つかりません。")
    print("   クリップボードにコピーするか、パイプで渡してください。")
    print("   例: pbpaste | python scripts/save_output.py --name feature")
    sys.exit(1)


def parse_files(text):
    """--- FILE: パス --- 形式でテキストを分割する。"""
    pattern = r"---\s*FILE:\s*(.+?)\s*---"
    parts = re.split(pattern, text)

    if len(parts) < 3:
        return []

    return [
        {
            "path": parts[i].strip(),
            "content": parts[i + 1].strip() + "\n" if i + 1 < len(parts) else "",
        }
        for i in range(1, len(parts), 2)
    ]


def resolve_path(file_path, output_dir):
    """ファイルパスを output_dir を基準に安全に解決する。

    パストラバーサルと絶対パスの指定をブロックする。
    """
    cleaned = re.sub(r"^docs/", "", file_path)
    full = os.path.normpath(os.path.join(output_dir, cleaned))
    normalized_output = os.path.normpath(output_dir)

    if not (
        full == normalized_output or full.startswith(normalized_output + os.sep)
    ):
        raise ValueError(
            f"Path outside output directory: '{file_path}' -> '{full}'"
        )

    return full


def confirm(message):
    """ユーザーに確認を求める。"""
    try:
        response = input(f"{message} [y/N]: ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def count_unverified_decisions(content):
    """未確認の意思決定の数をカウントする。"""
    return len(re.findall(r"未確認", content))


def setup_output_dir(output_dir, dry_run, force):
    """出力先ディレクトリの存在確認と作成。"""
    if os.path.exists(output_dir):
        return

    if dry_run:
        print(f"[INFO] 出力先（未作成）: {output_dir}")
    elif force or not sys.stdin.isatty():
        os.makedirs(output_dir, exist_ok=True)
        print(f"[INFO] 出力先を作成しました: {output_dir}")
    else:
        if not confirm(f"[INFO] {output_dir} が存在しません。作成しますか？"):
            print("中止しました。")
            sys.exit(0)
        os.makedirs(output_dir, exist_ok=True)


def write_files(files, output_dir, dry_run, force):
    """ファイルを書き出し、結果を返す。"""
    written = 0
    skipped = 0
    warnings = []

    for file_info in files:
        try:
            full_path = resolve_path(file_info["path"], output_dir)
        except ValueError as e:
            print(f"  [SKIP] {file_info['path']}（{e}）")
            skipped += 1
            continue

        rel_path = os.path.relpath(full_path, output_dir)
        exists = os.path.exists(full_path)
        status = "上書き" if exists else "新規"

        if dry_run:
            marker = "[EXISTS]" if exists else "[NEW]"
            print(f"  {marker} {rel_path}（{status}）")
            content_preview = file_info["content"][:100].replace("\n", "\\n")
            print(f"     先頭: {content_preview}...")
            written += 1
            continue

        if exists and not force:
            if not confirm(f"  [WARN] {rel_path} は既に存在します。上書きしますか？"):
                print(f"  [SKIP] {rel_path}（スキップ）")
                skipped += 1
                continue

        parent = os.path.dirname(full_path)
        os.makedirs(parent, exist_ok=True)

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(file_info["content"])
            print(f"  [OK] {rel_path}（{status}）")
            written += 1
        except OSError as e:
            print(f"  [ERROR] {rel_path}（{e}）")
            sys.exit(1)

        if "decisions" in rel_path:
            count = count_unverified_decisions(file_info["content"])
            if count > 0:
                warnings.append(
                    f"[WARN] {rel_path} に未確認の意思決定が {count}件あります。確認してください。"
                )

    return written, skipped, warnings


def print_summary(written, skipped, warnings, dry_run):
    """結果サマリーを表示する。"""
    print("")
    if dry_run:
        print(f"[INFO] 確認完了！{written}ファイルが書き出し対象です。")
        print("   --dry-run を外して実行すると実際に書き出します。")
    else:
        print(f"[OK] 完了！{written}ファイルを書き出しました。")
        if skipped > 0:
            print(f"   （{skipped}ファイルをスキップ）")

    for warning in warnings:
        print(warning)


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code の出力をファイルに書き出す"
    )
    parser.add_argument("--name", default="", help="機能名（ログ表示用、任意）")
    parser.add_argument(
        "--output-dir", default="./docs", help="出力先ベースディレクトリ"
    )
    parser.add_argument(
        "--force", action="store_true", help="既存ファイルを確認なしに上書き"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="ファイルを実際に書かずに内容を表示"
    )
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output_dir)
    setup_output_dir(output_dir, args.dry_run, args.force)

    text = get_input_text()
    files = parse_files(text)

    if not files:
        print("[ERROR] --- FILE: パス --- 形式のセクションが見つかりません。")
        print("")
        print("受け取ったテキストの先頭:")
        print(text[:PREVIEW_LENGTH])
        sys.exit(1)

    print(f"[INFO] 出力先: {output_dir}")
    if args.name:
        print(f"[INFO] 機能名: {args.name}")
    print(f"[INFO] {'確認中...' if args.dry_run else '書き出し中...'}")
    print("")

    written, skipped, warnings = write_files(
        files, output_dir, args.dry_run, args.force
    )
    print_summary(written, skipped, warnings, args.dry_run)


if __name__ == "__main__":
    main()
