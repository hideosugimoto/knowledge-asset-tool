#!/usr/bin/env python3
"""
check_leakage.py - git 管理ファイルの情報漏洩チェック

分析対象プロジェクトのデータ（DB構造、API仕様、ビジネスロジック等）が
テンプレート・スクリプト・コマンドファイルに混入していないかスキャンする。

Usage:
    python3 scripts/check_leakage.py                    # git tracked 全ファイル
    python3 scripts/check_leakage.py --staged           # staged ファイルのみ
    python3 scripts/check_leakage.py --diff HEAD~1      # 直近コミットの差分
    python3 scripts/check_leakage.py --json              # JSON 出力

--json 指定時、stdout には JSON オブジェクトのみを出力する（json.load でパース可能）:

    {
      "mode": "all tracked",
      "scanned_files": 109,
      "patterns": 16,
      "summary": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "total": 0},
      "blocked": false,
      "findings": [...]
    }

人間向けのサマリ行は stderr に出す。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# 検出パターン定義
# ---------------------------------------------------------------------------

@dataclass
class LeakPattern:
    name: str
    pattern: re.Pattern
    severity: str  # CRITICAL / HIGH / MEDIUM
    description: str
    allow_in: list[str] = field(default_factory=list)  # 除外パス glob


# .cache/facts-*.yaml からプロジェクト名を動的取得
def _discover_project_names(repo_root: str) -> set[str]:
    """ローカルの .cache/facts-*.yaml からプロジェクト名を収集する。"""
    names = set()
    cache_dir = Path(repo_root) / ".cache"
    if cache_dir.is_dir():
        for f in cache_dir.glob("facts-*.yaml"):
            name = f.stem.replace("facts-", "")
            if name and len(name) > 2:
                names.add(name)
    # docs/ 配下のディレクトリ名も収集
    docs_dir = Path(repo_root) / "docs"
    if docs_dir.is_dir():
        for subdir in ["architecture", "manual", "explanations"]:
            d = docs_dir / subdir
            if d.is_dir():
                for child in d.iterdir():
                    if child.is_dir() and child.name not in ("stylesheets",):
                        names.add(child.name)
                    elif child.is_file() and child.suffix == ".md":
                        stem = child.stem
                        if stem not in ("index",) and len(stem) > 2:
                            names.add(stem)
    return names


def _build_patterns(repo_root: str) -> list[LeakPattern]:
    """検出パターンリストを構築する。"""
    patterns = []

    # 1. 動的: ローカルで分析したプロジェクト名
    project_names = _discover_project_names(repo_root)
    for name in sorted(project_names):
        # my-app, sample-app 等の汎用名は除外
        if name in ("my-app", "sample-app", "example", "test", "demo"):
            continue
        patterns.append(LeakPattern(
            name=f"project-name:{name}",
            pattern=re.compile(re.escape(name), re.IGNORECASE),
            severity="CRITICAL",
            description=f"分析対象プロジェクト名 '{name}' がファイルに含まれています",
            allow_in=["docs/", "site/", ".cache/", ".gitignore"],
        ))

    # 2. 静的: mkdocs.yml に実プロジェクトの nav が残っていないか
    patterns.append(LeakPattern(
        name="mkdocs-nav-leak",
        pattern=re.compile(
            r'^\s+-\s+"(機能|Feature|Manual|Architecture|Explanations|User Guide|検収|AI Docs)'
            r'.*?:\s+\S+/',
            re.MULTILINE,
        ),
        severity="CRITICAL",
        description="mkdocs.yml に分析プロジェクトの nav 構造が含まれています",
        allow_in=[],
    ))

    # 3. DB テーブル/カラムのパターン（facts cache 由来）
    patterns.append(LeakPattern(
        name="db-schema-leak",
        pattern=re.compile(
            r'\b(vtiger_\w+|wp_\w{3,}options|vtiger_tab)\b'
        ),
        severity="HIGH",
        description="分析対象の DB テーブル名が含まれています（vtiger/WordPress 固有テーブル）",
        allow_in=[
            "templates/quality-rules.md",
            "templates/fact-schema.yaml",
            "templates/business-context.md",
            "scripts/check_leakage.py",
        ],
    ))

    # 4. 実在 URL パス（/infor/, /admin/staff/ 等の特徴的パス）
    # 汎用的な /api/, /login/, /dashboard/ は除外
    patterns.append(LeakPattern(
        name="specific-url-path",
        pattern=re.compile(r'/infor/'),
        severity="HIGH",
        description="分析対象の実 URL パスが含まれています",
        allow_in=["scripts/check_leakage.py"],
    ))

    # 5. 実プロジェクト固有のフィールド名
    patterns.append(LeakPattern(
        name="specific-field-name",
        pattern=re.compile(r'\bstaff_cd\b'),
        severity="MEDIUM",
        description="分析対象の実フィールド名が含まれています",
        allow_in=["scripts/check_leakage.py"],
    ))

    return patterns


# ---------------------------------------------------------------------------
# スキャン実行
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    file_path: str
    line_number: int
    pattern_name: str
    severity: str
    matched_text: str
    description: str


def _should_skip_file(path: str) -> bool:
    """スキャン対象外のファイルを判定する。"""
    skip_prefixes = ("docs/", "site/", ".cache/", ".git/")
    skip_suffixes = (".png", ".jpg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf")
    for prefix in skip_prefixes:
        if path.startswith(prefix):
            return True
    for suffix in skip_suffixes:
        if path.endswith(suffix):
            return True
    return False


def _is_allowed(pattern: LeakPattern, file_path: str) -> bool:
    """パターンの allow_in に含まれるパスかチェックする。"""
    for allowed in pattern.allow_in:
        if file_path.startswith(allowed) or file_path == allowed:
            return True
    return False


def scan_file(file_path: str, full_path: str, patterns: list[LeakPattern]) -> list[Finding]:
    """1ファイルをスキャンして検出結果を返す。"""
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    findings = []
    for line_num, line in enumerate(lines, 1):
        for pat in patterns:
            if _is_allowed(pat, file_path):
                continue
            match = pat.pattern.search(line)
            if match:
                findings.append(Finding(
                    file_path=file_path,
                    line_number=line_num,
                    pattern_name=pat.name,
                    severity=pat.severity,
                    matched_text=match.group(0)[:50],
                    description=pat.description,
                ))
    return findings


def scan_files(file_list: list[str], repo_root: str, patterns: list[LeakPattern]) -> list[Finding]:
    """複数ファイルをスキャンする。"""
    all_findings = []
    for rel_path in file_list:
        if _should_skip_file(rel_path):
            continue
        full_path = os.path.join(repo_root, rel_path)
        if os.path.isfile(full_path):
            all_findings.extend(scan_file(rel_path, full_path, patterns))
    return all_findings


# ---------------------------------------------------------------------------
# ファイルリスト取得
# ---------------------------------------------------------------------------

def get_tracked_files(repo_root: str) -> list[str]:
    """git ls-files で追跡ファイル一覧を取得。"""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, cwd=repo_root,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_staged_files(repo_root: str) -> list[str]:
    """git diff --cached で staged ファイル一覧を取得。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=repo_root,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_diff_files(repo_root: str, ref: str) -> list[str]:
    """git diff で差分ファイル一覧を取得。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", ref],
        capture_output=True, text=True, cwd=repo_root,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------

def format_findings(findings: list[Finding]) -> str:
    """検出結果を人間可読な形式で出力する。"""
    if not findings:
        return "  漏洩パターンは検出されませんでした"

    lines = []
    by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)

    for sev in ["CRITICAL", "HIGH", "MEDIUM"]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        lines.append(f"\n  [{sev}] {len(items)} 件:")
        for f in items:
            lines.append(f"    {f.file_path}:{f.line_number} — {f.matched_text}")
            lines.append(f"      {f.description}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="git 管理ファイルの情報漏洩チェック"
    )
    parser.add_argument(
        "--staged", action="store_true",
        help="staged ファイルのみチェック",
    )
    parser.add_argument(
        "--diff", type=str, default=None,
        help="指定 ref との差分ファイルをチェック（例: HEAD~1）",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="JSON 形式で出力",
    )
    return parser.parse_args(argv)


def _collect_files(repo_root: str, args) -> tuple[list[str], str]:
    """スキャン対象のファイル一覧とモード名を返す。"""
    if args.staged:
        return get_staged_files(repo_root), "staged"
    if args.diff:
        return get_diff_files(repo_root, args.diff), f"diff {args.diff}"
    return get_tracked_files(repo_root), "all tracked"


def _count_by_severity(findings: list[Finding]) -> dict:
    """深刻度別の件数と blocked 判定を返す。"""
    counts = {
        sev: sum(1 for f in findings if f.severity == sev)
        for sev in ("CRITICAL", "HIGH", "MEDIUM")
    }
    counts["total"] = len(findings)
    return counts


def build_json_payload(findings: list[Finding], counts: dict, mode: str,
                       scanned_files: int, patterns: int, blocked: bool) -> dict:
    """--json 出力用の機械可読なオブジェクトを組み立てる。"""
    return {
        "mode": mode,
        "scanned_files": scanned_files,
        "patterns": patterns,
        "summary": counts,
        "blocked": blocked,
        "findings": [
            {
                "file": f.file_path,
                "line": f.line_number,
                "severity": f.severity,
                "pattern": f.pattern_name,
                "matched": f.matched_text,
                "description": f.description,
            }
            for f in findings
        ],
    }


def main(argv=None) -> int:
    args = _parse_args(argv)

    repo_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    ).stdout.strip()

    if not repo_root:
        print("[ERROR] git リポジトリ内で実行してください", file=sys.stderr)
        return 2

    patterns = _build_patterns(repo_root)
    files, mode = _collect_files(repo_root, args)
    findings = scan_files(files, repo_root, patterns)

    counts = _count_by_severity(findings)
    blocked = counts["CRITICAL"] > 0 or counts["HIGH"] > 0
    summary_line = (
        f"NG: CRITICAL={counts['CRITICAL']}, HIGH={counts['HIGH']} — プッシュをブロックします"
    )

    if args.json_output:
        # stdout は JSON のみ。サマリを混ぜると json.load が Extra data で失敗する。
        payload = build_json_payload(
            findings, counts, mode, len(files), len(patterns), blocked
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if blocked:
            print(summary_line, file=sys.stderr)
    else:
        print(f"[INFO] 漏洩チェック ({mode}): {len(files)} ファイル, {len(patterns)} パターン")
        print(format_findings(findings))
        if blocked:
            print(f"\n  {summary_line}")

    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
