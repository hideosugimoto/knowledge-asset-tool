#!/usr/bin/env python3
"""docs/ ディレクトリを走査して mkdocs.yml の nav セクションを自動生成する。

使い方:
    python scripts/generate_nav.py          # mkdocs.yml を上書き更新
    python scripts/generate_nav.py --dry-run  # 生成結果を stdout に表示(ファイル変更なし)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MKDOCS_YML = ROOT / "mkdocs.yml"

# --- タイトル抽出 ---------------------------------------------------------- #

# マニュアル番号ファイルの既知マッピング
MANUAL_TITLES: dict[str, str] = {
    "00-index.md": "マニュアル目次",
    "01-overview.md": "システム概要",
    "02-screen-flow.md": "画面遷移図",
    "03-features.md": "機能カタログ",
    "04-api-reference.md": "APIリファレンス",
    "05-data-model.md": "データモデル",
    "06-screen-specs.md": "画面詳細設計",
    "07-walkthrough.md": "ウォークスルー",
    "08-review.md": "設計評価",
    "09-user-guide.md": "操作ガイド",
    "10-quick-reference.md": "クイックリファレンス",
    "db-reconciliation.md": "コード⇔DB突合レポート",
}

EXPLANATION_TITLES: dict[str, str] = {
    "pro.md": "エンジニア向け",
    "sales.md": "営業向け",
    "beginner.md": "初心者向け",
}


def _title_from_md(path: Path) -> str:
    """Markdown ファイルの先頭 # 見出しからタイトルを取得する。"""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line.lstrip("# ").strip()
    except (OSError, UnicodeDecodeError):
        pass
    # フォールバック: ファイル名をタイトル化
    return path.stem.replace("-", " ").replace("_", " ").title()


def _feature_title(path: Path) -> str:
    """features/ 配下の .md からタイトルを取得し「機能: ...」形式にする。"""
    title = _title_from_md(path)
    return f"機能: {title}"


# --- プロジェクト検出 ------------------------------------------------------- #


def discover_projects() -> list[str]:
    """docs/ 直下の {name}-index.md からプロジェクト名一覧を返す。"""
    projects: list[str] = []
    for p in sorted(DOCS.glob("*-index.md")):
        name = p.name.removesuffix("-index.md")
        if name:
            projects.append(name)
    return projects


# --- nav 構築 -------------------------------------------------------------- #


def _rel(path: Path) -> str:
    """docs/ からの相対パスを返す。"""
    return str(path.relative_to(DOCS))


def _if_exists(path: Path) -> str | None:
    return _rel(path) if path.exists() else None


def build_project_nav(name: str) -> list:
    """1 プロジェクト分の nav ツリーを構築する。"""
    nav: list = []

    # 目次
    idx = DOCS / f"{name}-index.md"
    if idx.exists():
        nav.append({"目次": _rel(idx)})

    # Architecture
    arch_items: list = []
    arc42 = DOCS / "architecture" / f"{name}.md"
    if arc42.exists():
        arch_items.append({"arc42 ドキュメント": _rel(arc42)})
    rag = DOCS / "architecture" / f"{name}.rag.md"
    if rag.exists():
        arch_items.append({"RAG用": _rel(rag)})
    if arch_items:
        nav.append({"Architecture": arch_items})

    # Manual
    manual_dir = DOCS / "manual" / name
    if manual_dir.is_dir():
        manual_items: list = []

        # 番号付きファイル (00-*.md ~ 08-*.md)
        pre_feature_files = sorted(
            f for f in manual_dir.glob("[0-9][0-9]-*.md")
            if f.name in MANUAL_TITLES and int(f.name[:2]) <= 3
        )
        for f in pre_feature_files:
            manual_items.append({MANUAL_TITLES[f.name]: _rel(f)})

        # features/
        features_dir = manual_dir / "features"
        if features_dir.is_dir():
            for feat in sorted(features_dir.glob("*.md")):
                manual_items.append({_feature_title(feat): _rel(feat)})

        # 番号付きファイル (04-*.md ~ 08-*.md)
        post_feature_files = sorted(
            f for f in manual_dir.glob("[0-9][0-9]-*.md")
            if f.name in MANUAL_TITLES and 4 <= int(f.name[:2]) <= 8
        )
        for f in post_feature_files:
            manual_items.append({MANUAL_TITLES[f.name]: _rel(f)})

        if manual_items:
            nav.append({"Manual": manual_items})

        # User Guide (09-, 10-)
        ug_items: list = []
        ug_files = sorted(
            f for f in manual_dir.glob("[0-9][0-9]-*.md")
            if f.name in MANUAL_TITLES and int(f.name[:2]) >= 9
        )
        for f in ug_files:
            ug_items.append({MANUAL_TITLES[f.name]: _rel(f)})
        if ug_items:
            nav.append({"User Guide": ug_items})

    # Explanations
    exp_dir = DOCS / "explanations" / name
    if exp_dir.is_dir():
        exp_items: list = []
        for fname, title in EXPLANATION_TITLES.items():
            p = exp_dir / fname
            if p.exists():
                exp_items.append({title: _rel(p)})
        if exp_items:
            nav.append({"Explanations": exp_items})

    # 意思決定記録
    dec = DOCS / "decisions" / f"{name}.md"
    if dec.exists():
        nav.append({"意思決定記録": _rel(dec)})

    # AI Docs (プロジェクト単位)
    ai_items: list = []
    llms = DOCS / f"{name}-llms.txt"
    if llms.exists():
        ai_items.append({"llms.txt": _rel(llms)})
    agents = DOCS / f"{name}-AGENTS.md"
    if agents.exists():
        ai_items.append({"AGENTS.md": _rel(agents)})
    if ai_items:
        nav.append({"AI Docs": ai_items})

    return nav


def build_full_nav() -> list:
    """mkdocs.yml 用の完全な nav ツリーを構築する。"""
    nav: list = [{"Home": "index.md"}]

    for project in discover_projects():
        project_nav = build_project_nav(project)
        if project_nav:
            nav.append({project: project_nav})

    return nav


# --- YAML 出力 ------------------------------------------------------------- #


def _indent(level: int) -> str:
    return "  " * level


def _render_nav_item(item, level: int = 1) -> list[str]:
    """nav アイテムを YAML 文字列行のリストとして返す。"""
    lines: list[str] = []
    if isinstance(item, dict):
        for key, value in item.items():
            if isinstance(value, str):
                lines.append(f'{_indent(level)}- "{key}": {value}')
            elif isinstance(value, list):
                lines.append(f'{_indent(level)}- "{key}":')
                for child in value:
                    lines.extend(_render_nav_item(child, level + 1))
    elif isinstance(item, str):
        lines.append(f"{_indent(level)}- {item}")
    return lines


def render_nav_yaml(nav: list) -> str:
    """nav リストを YAML テキストとして返す。"""
    lines = ["nav:"]
    for item in nav:
        lines.extend(_render_nav_item(item))
    return "\n".join(lines) + "\n"


# --- mkdocs.yml 更新 ------------------------------------------------------- #

NAV_PATTERN = re.compile(r"^nav:\s*\n(?:(?:[ \t]+-.*|[ \t]*\n))*", re.MULTILINE)


def update_mkdocs_yml(nav_yaml: str, *, dry_run: bool = False) -> str:
    """mkdocs.yml の nav セクションを差し替える。"""
    content = MKDOCS_YML.read_text(encoding="utf-8")

    match = NAV_PATTERN.search(content)
    if match:
        new_content = content[: match.start()] + nav_yaml + content[match.end() :]
    else:
        # nav セクションが無ければ末尾に追加
        new_content = content.rstrip("\n") + "\n\n" + nav_yaml

    if not dry_run:
        MKDOCS_YML.write_text(new_content, encoding="utf-8")

    return new_content


# --- main ------------------------------------------------------------------ #


def main() -> None:
    parser = argparse.ArgumentParser(description="mkdocs.yml の nav を自動生成する")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを変更せず stdout に出力する",
    )
    args = parser.parse_args()

    nav = build_full_nav()
    nav_yaml = render_nav_yaml(nav)

    if args.dry_run:
        print(nav_yaml)
    else:
        update_mkdocs_yml(nav_yaml)
        print("mkdocs.yml の nav セクションを更新しました。")


if __name__ == "__main__":
    main()
