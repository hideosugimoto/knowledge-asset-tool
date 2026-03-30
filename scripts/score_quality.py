#!/usr/bin/env python3
"""
品質スコア自動評価スクリプト

生成されたドキュメントを品質ルーブリック（templates/quality-rubric.md）の
評価軸に基づいて自動スコアリングし、改善提案を出力する。

Usage:
    python3 scripts/score_quality.py --docs-dir ./docs --name myproject
    python3 scripts/score_quality.py --docs-dir ./docs --name myproject --json
    python3 scripts/score_quality.py --docs-dir ./docs --name myproject --threshold B
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

GRADE_ORDER = {"A": 3, "B": 2, "C": 1}
GRADE_LABELS = {"A": "A", "B": "B", "C": "C"}


@dataclass
class AxisResult:
    name: str
    grade: str  # A / B / C
    detail: str
    suggestions: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return GRADE_ORDER.get(self.grade, 0)


@dataclass
class QualityReport:
    name: str
    axes: list[AxisResult] = field(default_factory=list)

    @property
    def numeric_score(self) -> int:
        """0-100 numeric score derived from axis grades."""
        if not self.axes:
            return 0
        total = sum(a.score for a in self.axes)
        max_total = len(self.axes) * 3
        return round(total / max_total * 100)

    @property
    def overall_grade(self) -> str:
        s = self.numeric_score
        if s >= 90:
            return "A"
        if s >= 80:
            return "A-"
        if s >= 70:
            return "B+"
        if s >= 60:
            return "B"
        if s >= 50:
            return "B-"
        if s >= 40:
            return "C+"
        return "C"

    @property
    def all_suggestions(self) -> list[str]:
        out: list[str] = []
        for a in self.axes:
            out.extend(a.suggestions)
        return out

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "overall_grade": self.overall_grade,
            "numeric_score": self.numeric_score,
            "axes": [
                {
                    "name": a.name,
                    "grade": a.grade,
                    "detail": a.detail,
                    "suggestions": a.suggestions,
                }
                for a in self.axes
            ],
            "suggestions": self.all_suggestions,
        }


# ---------------------------------------------------------------------------
# Helper: read all markdown files under a directory tree
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _collect_md_files(docs_dir: Path, name: str) -> list[Path]:
    """Collect all .md files that belong to the given project name."""
    files: list[Path] = []
    # architecture/{name}.md
    arch = docs_dir / "architecture" / f"{name}.md"
    if arch.exists():
        files.append(arch)
    # manual/{name}/*.md
    manual_dir = docs_dir / "manual" / name
    if manual_dir.is_dir():
        files.extend(sorted(manual_dir.rglob("*.md")))
    # explanations/{name}/*.md
    expl_dir = docs_dir / "explanations" / name
    if expl_dir.is_dir():
        files.extend(sorted(expl_dir.rglob("*.md")))
    # decisions/{name}.md
    dec = docs_dir / "decisions" / f"{name}.md"
    if dec.exists():
        files.append(dec)
    # {name}-index.md
    idx = docs_dir / f"{name}-index.md"
    if idx.exists():
        files.append(idx)
    # {name}-llms.txt (treat as text)
    llms = docs_dir / f"{name}-llms.txt"
    if llms.exists():
        files.append(llms)
    # {name}-AGENTS.md
    agents = docs_dir / f"{name}-AGENTS.md"
    if agents.exists():
        files.append(agents)
    # meta/{name}.yaml
    meta = docs_dir / "meta" / f"{name}.yaml"
    if meta.exists():
        files.append(meta)
    return files


def _all_text(docs_dir: Path, name: str) -> str:
    """Concatenate all markdown content for a project."""
    parts = []
    for f in _collect_md_files(docs_dir, name):
        parts.append(_read_text(f))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_factual_grounding(docs_dir: Path, name: str) -> AxisResult:
    """Count (file:line) source citations per section.

    Grading criteria (also documented in templates/quality-rules.md §7):
        A: 80%+ of sections contain at least one (file:line) citation
        B: 50-79% of sections contain citations
        C: <50% of sections contain citations
    """
    # マニュアル + アーキテクチャの両方を評価対象にする
    scan_dirs = []
    manual_dir = docs_dir / "manual" / name
    if manual_dir.is_dir():
        scan_dirs.append(manual_dir)
    arch_dir = docs_dir / "architecture"
    if arch_dir.is_dir():
        scan_dirs.append(arch_dir)
    if not scan_dirs:
        return AxisResult(
            name="ファクト根拠",
            grade="C",
            detail="マニュアル・アーキテクチャディレクトリが見つからない",
            suggestions=[f"docs/manual/{name}/ または docs/architecture/ にドキュメントを生成してください"],
        )

    citation_pattern = re.compile(
        r"\([^)]*:\d+\)"           # (file:line) 形式
        r"|<!-- source: [^>]+-->"  # <!-- source: file:line --> 形式
    )
    section_pattern = re.compile(r"^#{1,3}\s+", re.MULTILINE)

    total_sections = 0
    sections_with_citations = 0
    low_citation_files: list[str] = []

    all_md_files = []
    for d in scan_dirs:
        all_md_files.extend(d.rglob("*.md"))
    # architecture はプロジェクト名に完全一致するファイルのみ（例: my-app.md, my-app.rag.md）
    all_md_files = [
        f for f in all_md_files
        if f.parent.name != "architecture"
        or f.stem == name
        or f.stem == f"{name}.rag"
    ]
    for md_file in sorted(all_md_files):
        text = _read_text(md_file)
        sections = section_pattern.split(text)
        if len(sections) <= 1:
            continue
        file_sections = len(sections) - 1
        file_cited = 0
        for section in sections[1:]:
            total_sections += 1
            citations = citation_pattern.findall(section)
            if len(citations) >= 1:
                file_cited += 1
                sections_with_citations += 1
        ratio = file_cited / file_sections if file_sections > 0 else 0
        if ratio < 0.5:
            low_citation_files.append(md_file.name)

    if total_sections == 0:
        return AxisResult(
            name="ファクト根拠",
            grade="C",
            detail="セクションが見つからない",
            suggestions=["マニュアルの各セクションにソースコード引用 (file:line) を追加してください"],
        )

    ratio = sections_with_citations / total_sections
    if ratio >= 0.8:
        grade = "A"
        detail = f"全セクションの{round(ratio*100)}%にソース引用あり（{sections_with_citations}/{total_sections}セクション）"
    elif ratio >= 0.5:
        grade = "B"
        detail = f"セクションの{round(ratio*100)}%にソース引用あり（{sections_with_citations}/{total_sections}セクション）"
    else:
        grade = "C"
        detail = f"ソース引用が不足（{sections_with_citations}/{total_sections}セクション = {round(ratio*100)}%）"

    suggestions = []
    if low_citation_files:
        suggestions.append(
            f"以下のファイルでソース引用 (file:line) を追加: {', '.join(low_citation_files[:5])}"
        )
    return AxisResult(name="ファクト根拠", grade=grade, detail=detail, suggestions=suggestions)


def _score_completeness(docs_dir: Path, name: str) -> AxisResult:
    """Check if expected files exist."""
    expected_files = {
        f"architecture/{name}.md": "アーキテクチャ概要",
        f"manual/{name}/00-index.md": "マニュアル目次",
        f"manual/{name}/01-overview.md": "システム概要",
        f"manual/{name}/02-screen-flow.md": "画面フロー",
        f"manual/{name}/03-features.md": "機能一覧",
        f"manual/{name}/04-api-reference.md": "APIリファレンス",
        f"manual/{name}/05-data-model.md": "データモデル",
        f"manual/{name}/06-screen-specs.md": "画面詳細設計",
        f"manual/{name}/07-walkthrough.md": "ウォークスルー",
        f"manual/{name}/08-review.md": "レビュー",
        f"explanations/{name}/pro.md": "エンジニア向け解説",
        f"explanations/{name}/beginner.md": "初心者向け解説",
        f"explanations/{name}/sales.md": "営業向け解説",
        f"decisions/{name}.md": "設計意思決定",
        f"{name}-index.md": "プロジェクト目次",
    }

    present = []
    missing = []
    for rel_path, label in expected_files.items():
        full = docs_dir / rel_path
        if full.exists():
            present.append(label)
        else:
            missing.append(f"{label} ({rel_path})")

    total = len(expected_files)
    found = len(present)
    ratio = found / total if total > 0 else 0

    if ratio >= 0.9:
        grade = "A"
    elif ratio >= 0.7:
        grade = "B"
    else:
        grade = "C"

    detail = f"{found}/{total} ファイルが存在（{round(ratio*100)}%）"
    suggestions = []
    if missing:
        for m in missing[:5]:
            suggestions.append(f"不足: {m}")
        if len(missing) > 5:
            suggestions.append(f"他 {len(missing) - 5} 件不足")

    return AxisResult(name="網羅性", grade=grade, detail=detail, suggestions=suggestions)


def _score_diagram_coverage(docs_dir: Path, name: str) -> AxisResult:
    """Count .mmd and .svg files for the project."""
    diagrams_dir = docs_dir / "diagrams"
    mmd_count = 0
    svg_count = 0
    if diagrams_dir.is_dir():
        for f in diagrams_dir.iterdir():
            if not f.name.startswith(name):
                continue
            if f.suffix == ".mmd":
                mmd_count += 1
            elif f.suffix == ".svg":
                svg_count += 1

    # Also count inline mermaid blocks in manual
    manual_dir = docs_dir / "manual" / name
    inline_count = 0
    if manual_dir.is_dir():
        for md_file in manual_dir.rglob("*.md"):
            text = _read_text(md_file)
            inline_count += text.count("```mermaid")

    total_diagrams = mmd_count + svg_count + inline_count

    if total_diagrams >= 10:
        grade = "A"
    elif total_diagrams >= 5:
        grade = "B"
    else:
        grade = "C"

    detail = f"mmd: {mmd_count}, svg: {svg_count}, inline mermaid: {inline_count}（計 {total_diagrams} 図）"
    suggestions = []
    if total_diagrams < 5:
        suggestions.append("図の数が不足しています。アーキテクチャ図、ER図、画面フロー図などを追加してください")
    return AxisResult(name="図表充実度", grade=grade, detail=detail, suggestions=suggestions)


def _score_cross_references(docs_dir: Path, name: str) -> AxisResult:
    """Count internal links between documents."""
    all_content = _all_text(docs_dir, name)
    # Match markdown links: [text](path) where path is relative
    link_pattern = re.compile(r"\[([^\]]+)\]\((?!https?://)(?!#)([^)]+)\)")
    links = link_pattern.findall(all_content)
    count = len(links)

    if count >= 20:
        grade = "A"
    elif count >= 10:
        grade = "B"
    else:
        grade = "C"

    detail = f"内部リンク {count} 件"
    suggestions = []
    if count < 10:
        suggestions.append("ドキュメント間の相互参照リンクを追加してください（関連章への参照など）")
    return AxisResult(name="相互参照", grade=grade, detail=detail, suggestions=suggestions)


def _score_api_completeness(docs_dir: Path, name: str) -> AxisResult:
    """Parse 04-api-reference.md and count endpoint/tool rows."""
    api_file = docs_dir / "manual" / name / "04-api-reference.md"
    if not api_file.exists():
        return AxisResult(
            name="API完全性",
            grade="C",
            detail="04-api-reference.md が見つからない",
            suggestions=["APIリファレンスを生成してください"],
        )

    text = _read_text(api_file)
    # Count table rows (lines starting with |, excluding header separators)
    table_rows = [
        line for line in text.splitlines()
        if line.strip().startswith("|")
        and not re.match(r"^\|[\s\-:]+\|", line.strip())
        and "---" not in line
    ]
    # Subtract header rows (rough: each table has 1 header)
    # Count tables by counting separator rows
    separator_count = len([
        line for line in text.splitlines()
        if re.match(r"^\|[\s\-:]+\|", line.strip())
    ])
    data_rows = max(0, len(table_rows) - separator_count)

    # Also check for OpenAPI spec
    openapi_file = docs_dir / "manual" / name / "openapi.yaml"
    has_openapi = openapi_file.exists()

    if data_rows >= 20 or has_openapi:
        grade = "A"
    elif data_rows >= 5:
        grade = "B"
    else:
        grade = "C"

    detail = f"API/ツール定義 {data_rows} 行"
    if has_openapi:
        detail += "、OpenAPI仕様あり"
    suggestions = []
    if data_rows < 5:
        suggestions.append("APIエンドポイントまたはツール定義の記載が不足しています")
    return AxisResult(name="API完全性", grade=grade, detail=detail, suggestions=suggestions)


def _score_table_completeness(docs_dir: Path, name: str) -> AxisResult:
    """Parse 05-data-model.md and count table definitions."""
    dm_file = docs_dir / "manual" / name / "05-data-model.md"
    if not dm_file.exists():
        return AxisResult(
            name="テーブル完全性",
            grade="C",
            detail="05-data-model.md が見つからない",
            suggestions=["データモデルドキュメントを生成してください"],
        )

    text = _read_text(dm_file)
    # Count H3+ headings that likely represent tables
    table_headings = re.findall(r"^#{2,4}\s+.+", text, re.MULTILINE)

    # Count table rows with column definitions
    col_rows = [
        line for line in text.splitlines()
        if line.strip().startswith("|")
        and not re.match(r"^\|[\s\-:]+\|", line.strip())
    ]
    separator_count = len([
        line for line in text.splitlines()
        if re.match(r"^\|[\s\-:]+\|", line.strip())
    ])
    data_rows = max(0, len(col_rows) - separator_count)

    # Check against DB cache if available
    db_cache = None
    cache_dir = Path(docs_dir).parent / ".cache"
    if cache_dir.is_dir():
        for cache_file in cache_dir.glob(f"db-*.json"):
            try:
                db_data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(db_data, dict) and "tables" in db_data:
                    db_cache = len(db_data["tables"])
                    break
            except (json.JSONDecodeError, OSError):
                pass

    heading_count = len(table_headings)
    if heading_count >= 10:
        grade = "A"
    elif heading_count >= 5:
        grade = "B"
    else:
        grade = "C"

    detail = f"セクション見出し {heading_count} 件、テーブル定義行 {data_rows} 行"
    if db_cache is not None:
        detail += f"（DBキャッシュ: {db_cache} テーブル）"

    suggestions = []
    if db_cache is not None and heading_count < db_cache:
        suggestions.append(
            f"DBキャッシュには {db_cache} テーブルがありますが、"
            f"ドキュメントには {heading_count} セクションしかありません"
        )
    if heading_count < 5:
        suggestions.append("データモデルのテーブル定義が不足しています")
    return AxisResult(name="テーブル完全性", grade=grade, detail=detail, suggestions=suggestions)


def _score_screen_coverage(docs_dir: Path, name: str) -> AxisResult:
    """Parse 06-screen-specs.md and count screen sections."""
    screen_file = docs_dir / "manual" / name / "06-screen-specs.md"
    if not screen_file.exists():
        return AxisResult(
            name="画面網羅性",
            grade="C",
            detail="06-screen-specs.md が見つからない",
            suggestions=["画面詳細設計ドキュメントを生成してください"],
        )

    text = _read_text(screen_file)
    # Count H2/H3 headings that represent screens
    screen_sections = re.findall(r"^#{2,3}\s+.+", text, re.MULTILINE)
    count = len(screen_sections)

    if count >= 15:
        grade = "A"
    elif count >= 5:
        grade = "B"
    else:
        grade = "C"

    detail = f"画面セクション {count} 件"
    suggestions = []
    if count < 5:
        suggestions.append("画面詳細設計のセクションが不足しています。全画面を網羅してください")
    return AxisResult(name="画面網羅性", grade=grade, detail=detail, suggestions=suggestions)


def _score_speculation_markers(docs_dir: Path, name: str) -> AxisResult:
    """Count speculation markers. Fewer is better."""
    all_content = _all_text(docs_dir, name)
    markers = re.findall(r"【推測】", all_content)
    count = len(markers)

    if count == 0:
        grade = "A"
        detail = "【推測】マークなし（全てファクトベース）"
    elif count <= 5:
        grade = "B"
        detail = f"【推測】{count} 件（理想は 0 件）"
    else:
        grade = "C"
        detail = f"【推測】{count} 件（理想は 0 件）"

    suggestions = []
    if count > 0:
        suggestions.append(
            f"【推測】{count} 件の解消にはソースコードの追加分析が必要"
        )
    return AxisResult(name="推測マーク", grade=grade, detail=detail, suggestions=suggestions)


def _score_module_validity(docs_dir: Path, name: str) -> AxisResult:
    """Check module validity: disabled_modules documented, Tier counts consistent.

    Grading criteria (quality-rules.md §4a):
        A: disabled_modules section exists AND Tier counts are consistent
        B: disabled_modules section exists OR Tier-related mention found
        C: No module validity information found
    """
    all_content = _all_text(docs_dir, name)

    # Check for disabled_modules / 無効化モジュール documentation
    has_disabled_section = bool(
        re.search(r"(disabled.modules|無効化モジュール|無効モジュール)", all_content, re.IGNORECASE)
    )

    # Check for active/inactive module mentions
    has_active_check = bool(
        re.search(r"(active:\s*(true|false)|presence\s*=\s*[01]|INSTALLED_APPS)", all_content)
    )

    # Check Tier classification exists (each tier must appear at least once)
    has_tiers = all(
        re.search(rf"Tier\s*{t}", all_content) for t in [1, 2, 3]
    )

    # Check facts cache for module data
    cache_dir = Path(docs_dir).parent / ".cache"
    facts_file = cache_dir / f"facts-{name}.yaml"
    has_facts_modules = False
    if facts_file.exists():
        try:
            facts_text = _read_text(facts_file)
            has_facts_modules = "disabled_modules:" in facts_text or "active:" in facts_text
        except (OSError, UnicodeDecodeError):
            pass

    checks_passed = sum([has_disabled_section, has_active_check or has_facts_modules, has_tiers])

    if checks_passed >= 3:
        grade = "A"
        detail = "モジュール有効性検証済み（無効モジュール記載あり・Tier分類整合）"
    elif checks_passed >= 1:
        grade = "B"
        detail = f"モジュール有効性チェック {checks_passed}/3 項目該当"
    else:
        grade = "C"
        detail = "モジュール有効性の検証情報なし"

    suggestions = []
    if not has_disabled_section:
        suggestions.append(
            "無効化モジュール一覧（disabled_modules）を技術的負債セクションに記載してください"
        )
    if not has_active_check and not has_facts_modules:
        suggestions.append(
            "ファクト収集で各モジュールの active 判定を実施してください（quality-rules.md §4a）"
        )
    if not has_tiers:
        suggestions.append(
            "Tier分類（Tier 1/2/3）を実施し、active: true のモジュールのみ分類してください"
        )
    return AxisResult(name="モジュール有効性", grade=grade, detail=detail, suggestions=suggestions)


def _score_formal_quality(docs_dir: Path, name: str) -> AxisResult:
    """Check formal quality: cover page, revision history, status header."""
    manual_dir = docs_dir / "manual" / name
    if not manual_dir.is_dir():
        return AxisResult(
            name="形式品質",
            grade="C",
            detail="マニュアルディレクトリが見つからない",
            suggestions=[f"docs/manual/{name}/ にマニュアルを生成してください"],
        )

    # Check index/cover page for cover page elements
    index_file = manual_dir / "00-index.md"
    has_cover_page = False
    has_revision_history = False

    if index_file.exists():
        # Read first 50 lines for cover page elements
        text = _read_text(index_file)
        lines = text.splitlines()[:50]
        first_50 = "\n".join(lines)
        cover_markers = ["文書番号", "バージョン", "承認者"]
        cover_found = sum(1 for m in cover_markers if m in first_50)
        has_cover_page = cover_found >= 3

    # Check all files for revision history and status
    has_status = False
    for md_file in sorted(manual_dir.glob("*.md")):
        text = _read_text(md_file)
        if re.search(r"^#{1,3}\s*.*改訂履歴", text, re.MULTILINE):
            has_revision_history = True
        if re.search(r"ステータス:", text):
            has_status = True

    checks_passed = sum([has_cover_page, has_revision_history, has_status])

    if checks_passed >= 3:
        grade = "A"
        detail = "表紙・改訂履歴・ステータス表示が全て存在"
    elif checks_passed >= 2:
        grade = "B"
        detail = f"形式要素 {checks_passed}/3 存在"
    else:
        grade = "C"
        detail = f"形式要素 {checks_passed}/3 存在"

    suggestions = []
    if not has_cover_page:
        suggestions.append("表紙（文書番号・バージョン・承認者）を00-index.mdの先頭に追加してください")
    if not has_revision_history:
        suggestions.append("改訂履歴セクションを追加してください")
    if not has_status:
        suggestions.append("各文書のヘッダーに「ステータス:」を追加してください")

    return AxisResult(name="形式品質", grade=grade, detail=detail, suggestions=suggestions)


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _format_table_report(report: QualityReport) -> str:
    """Format the report as a human-readable table."""
    lines = [
        f"=== 品質スコアレポート: {report.name} ===",
        "",
        f"  総合スコア: {report.overall_grade} ({report.numeric_score}/100)",
        "",
        "  軸別スコア:",
    ]

    # Calculate column widths
    name_width = max(len(a.name) for a in report.axes) + 2
    detail_width = max(len(a.detail) for a in report.axes) + 2

    # Ensure minimum widths
    name_width = max(name_width, 14)
    detail_width = max(detail_width, 30)

    border_top = f"  +{'-' * name_width}+-------+{'-' * detail_width}+"
    header = f"  |{'品質軸'.ljust(name_width - 4)}    |{'スコア'.ljust(3)}  |{'詳細'.ljust(detail_width - 2)}  |"
    separator = f"  +{'-' * name_width}+-------+{'-' * detail_width}+"

    lines.append(border_top)
    lines.append(header)
    lines.append(separator)

    for axis in report.axes:
        padded_name = axis.name.ljust(name_width - len(axis.name) + len(axis.name))
        # Calculate padding accounting for multi-byte characters
        name_display_width = _display_width(axis.name)
        name_pad = name_width - name_display_width
        detail_display_width = _display_width(axis.detail)
        detail_pad = detail_width - detail_display_width

        line = (
            f"  |{axis.name}{' ' * name_pad}"
            f"|  {axis.grade}    "
            f"|{axis.detail}{' ' * detail_pad}|"
        )
        lines.append(line)

    lines.append(border_top)

    suggestions = report.all_suggestions
    if suggestions:
        lines.append("")
        lines.append("  改善提案:")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"    {i}. {s}")

    return "\n".join(lines)


def _display_width(s: str) -> int:
    """Estimate display width accounting for CJK characters."""
    width = 0
    for ch in s:
        if ord(ch) > 0x2E80:
            width += 2
        else:
            width += 1
    return width


# ---------------------------------------------------------------------------
# Threshold check
# ---------------------------------------------------------------------------

_THRESHOLD_MAP = {
    "A": 90,
    "A-": 80,
    "B+": 70,
    "B": 60,
    "B-": 50,
    "C+": 40,
    "C": 0,
}


def _check_threshold(report: QualityReport, threshold: str) -> bool:
    """Return True if report meets or exceeds threshold."""
    min_score = _THRESHOLD_MAP.get(threshold)
    if min_score is None:
        print(f"警告: 不明な閾値 '{threshold}'。有効な値: {', '.join(_THRESHOLD_MAP.keys())}", file=sys.stderr)
        return True
    return report.numeric_score >= min_score


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def score_project(docs_dir: Path, name: str) -> QualityReport:
    """Run all scoring checks and return a QualityReport."""
    report = QualityReport(name=name)
    report.axes = [
        _score_factual_grounding(docs_dir, name),
        _score_completeness(docs_dir, name),
        _score_diagram_coverage(docs_dir, name),
        _score_cross_references(docs_dir, name),
        _score_api_completeness(docs_dir, name),
        _score_table_completeness(docs_dir, name),
        _score_screen_coverage(docs_dir, name),
        _score_speculation_markers(docs_dir, name),
        _score_module_validity(docs_dir, name),
        _score_formal_quality(docs_dir, name),
    ]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="品質スコア自動評価 - 生成ドキュメントをルーブリックに基づきスコアリング"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="ドキュメントのルートディレクトリ（例: ./docs）",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="プロジェクト名（例: my-app）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="JSON形式で出力",
    )
    parser.add_argument(
        "--threshold",
        type=str,
        default=None,
        help="最低グレード閾値（例: B）。下回ると exit code 1",
    )

    args = parser.parse_args()
    docs_dir = Path(args.docs_dir).resolve()
    name = args.name

    if not docs_dir.is_dir():
        print(f"エラー: ディレクトリが見つかりません: {docs_dir}", file=sys.stderr)
        sys.exit(2)

    report = score_project(docs_dir, name)

    if args.json_output:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_table_report(report))

    if args.threshold:
        if not _check_threshold(report, args.threshold):
            grade = report.overall_grade
            print(
                f"\n  NG: 総合スコア {grade} が閾値 {args.threshold} を下回っています",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
