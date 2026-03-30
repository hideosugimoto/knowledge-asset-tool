#!/usr/bin/env python3
"""
check_consistency.py - ドキュメント間の用語一貫性チェック

使い方:
  python scripts/check_consistency.py --docs-dir ./docs
  python scripts/check_consistency.py --docs-dir ./docs --patterns custom.json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Built-in inconsistency patterns (loaded from external JSON)
# ---------------------------------------------------------------------------
_DEFAULT_RULES_PATH = os.path.join(os.path.dirname(__file__), "consistency_rules.json")


def _load_builtin_patterns() -> list[dict]:
    """Load built-in patterns from consistency_rules.json, falling back to empty list."""
    try:
        with open(_DEFAULT_RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


KNOWN_INCONSISTENCIES = _load_builtin_patterns()


# ---------------------------------------------------------------------------
# Data class for findings
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    """一件の検出結果を表す。"""

    file_path: str
    line_number: int
    found: str
    expected: str
    context: str
    level: str = "error"


# ---------------------------------------------------------------------------
# Helper: strip fenced code blocks
# ---------------------------------------------------------------------------
def strip_code_blocks(text: str) -> str:
    """マークダウンのフェンスドコードブロック(``` ... ```)を除去する。

    未閉じのコードブロックも除去対象とする。
    """
    return re.sub(r"```[^\n]*\n.*?(?:```|$)", "", text, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Core: check a single file
# ---------------------------------------------------------------------------
def check_file(file_path: str, patterns: list[dict]) -> list[Finding]:
    """単一ファイルをパターンリストに照合し、検出結果を返す。"""
    with open(file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # コードブロックを除去したテキストで行マッピングを作成
    cleaned = strip_code_blocks(raw_content)
    cleaned_lines = cleaned.splitlines()

    # 元テキストの各行 → 行番号マッピング（1-based）
    raw_lines = raw_content.splitlines()

    # cleaned_lines の各行が raw_lines の何行目に対応するか求める
    # strip_code_blocks は行を削除するだけなので、cleaned の行は raw のサブセット
    line_mapping = _build_line_mapping(raw_lines, cleaned_lines)

    findings: list[Finding] = []

    for cleaned_idx, line in enumerate(cleaned_lines):
        original_line_number = line_mapping[cleaned_idx]
        for pattern in patterns:
            wrong = pattern["wrong"]
            if wrong in line:
                level = "info" if pattern.get("in_code") else "error"
                findings.append(Finding(
                    file_path=file_path,
                    line_number=original_line_number,
                    found=wrong,
                    expected=pattern["correct"],
                    context=pattern.get("context", ""),
                    level=level,
                ))

    return findings


def _build_line_mapping(
    raw_lines: list[str], cleaned_lines: list[str]
) -> list[int]:
    """cleaned_lines の各インデックスを raw_lines の行番号(1-based)にマッピングする。"""
    mapping: list[int] = []
    raw_idx = 0

    for cleaned_line in cleaned_lines:
        while raw_idx < len(raw_lines):
            if raw_lines[raw_idx] == cleaned_line:
                mapping.append(raw_idx + 1)  # 1-based
                raw_idx += 1
                break
            raw_idx += 1
        else:
            # フォールバック: マッピングできない場合は 0
            mapping.append(0)

    return mapping


# ---------------------------------------------------------------------------
# Load custom patterns
# ---------------------------------------------------------------------------
def load_custom_patterns(path: str) -> list[dict]:
    """JSON ファイルからカスタムパターンを読み込む。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] パターンファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] パターンファイルのJSON解析に失敗: {e}", file=sys.stderr)
        sys.exit(1)

    return data


# ---------------------------------------------------------------------------
# Scan directory
# ---------------------------------------------------------------------------
def scan_directory(docs_dir: str, patterns: list[dict]) -> list[Finding]:
    """ディレクトリ配下の .md ファイルを再帰スキャンし、検出結果を集約する。"""
    all_findings: list[Finding] = []

    for root, _dirs, files in os.walk(docs_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            all_findings.extend(check_file(fpath, patterns))

    return all_findings


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """メインエントリポイント。終了コードを返す。"""
    parser = argparse.ArgumentParser(
        description="ドキュメント間の用語一貫性チェック"
    )
    parser.add_argument(
        "--docs-dir", required=True, help="スキャン対象ディレクトリ"
    )
    parser.add_argument(
        "--patterns", default=None, help="カスタムパターン JSON ファイル"
    )
    args = parser.parse_args(argv)

    patterns = list(KNOWN_INCONSISTENCIES)
    if args.patterns:
        custom = load_custom_patterns(args.patterns)
        patterns.extend(custom)

    findings = scan_directory(args.docs_dir, patterns)

    errors = [f for f in findings if f.level == "error"]
    infos = [f for f in findings if f.level == "info"]

    # 結果出力
    for f in findings:
        tag = "ERROR" if f.level == "error" else "INFO"
        print(
            f"  [{tag}] {f.file_path}:{f.line_number}  "
            f"'{f.found}' -> '{f.expected}' ({f.context})"
        )

    if errors:
        print(f"\n[FAIL] {len(errors)} 件のエラー、{len(infos)} 件の情報")
        return 1

    if infos:
        print(f"\n[OK] エラーなし（{len(infos)} 件の情報）")

    if not findings:
        print("[OK] 用語の不整合は検出されませんでした")

    return 0


if __name__ == "__main__":
    sys.exit(main())
