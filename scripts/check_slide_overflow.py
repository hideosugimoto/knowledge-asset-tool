#!/usr/bin/env python3
"""
check_slide_overflow.py - Mermaid / Marp スライドの溢れ検出

Mermaid .mmd ファイルと Marp .md ファイルを静的解析し、
PDF スライドで内容が溢れる (切れる) 可能性のある箇所を検出する。

使い方:
  python scripts/check_slide_overflow.py --docs-dir ./docs
  python scripts/check_slide_overflow.py --docs-dir ./docs --marp-dir /tmp/marp
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FLOWCHART_VERTICAL_NODES = 4
MAX_SEQUENCE_PARTICIPANTS = 5
MAX_SEQUENCE_MESSAGES = 12
MAX_ER_ENTITIES = 8
MAX_SLIDE_BULLETS = 5
MAX_SLIDE_TABLE_ROWS = 5
MAX_SLIDE_CARDS = 4
MAX_FIG_TEXT_CARDS = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    """検出された問題を表すデータクラス"""

    file: str
    line: int
    issue_type: str
    count: int
    max_allowed: int

    def __str__(self):
        return (
            f"{self.file}:{self.line}: {self.issue_type} "
            f"- count {self.count} exceeds max {self.max_allowed}"
        )


# ---------------------------------------------------------------------------
# Mermaid analysis
# ---------------------------------------------------------------------------
def _count_flowchart_vertical_depth(lines, start_line):
    """flowchart TB / direction TB ブロックの縦方向ノード深さを計算する。

    ノード間の --> 関係を追跡し、最長の縦チェーン長を返す。
    """
    graph = {}
    nodes = set()
    node_pattern = re.compile(
        r"^\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->"
        r"\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?"
    )

    for line in lines:
        m = node_pattern.match(line)
        if m:
            src, dst = m.group(1), m.group(2)
            nodes.add(src)
            nodes.add(dst)
            if src not in graph:
                graph[src] = []
            graph[src].append(dst)

    if not nodes:
        return 0

    # 各ノードから始まる最長パスを BFS/メモ化で計算
    memo = {}

    def depth(node, visiting=None):
        if visiting is None:
            visiting = set()
        if node in memo:
            return memo[node]
        if node in visiting:
            return 1  # サイクル検出 — 無限再帰を防止
        visiting.add(node)
        children = graph.get(node, [])
        if not children:
            memo[node] = 1
            visiting.discard(node)
            return 1
        max_child = max(depth(c, visiting) for c in children)
        memo[node] = 1 + max_child
        visiting.discard(node)
        return memo[node]

    # ルートノード (入辺のないノード) を探す
    has_incoming = set()
    for children in graph.values():
        for c in children:
            has_incoming.add(c)
    roots = [n for n in nodes if n not in has_incoming]
    if not roots:
        roots = list(nodes)

    return max(depth(r) for r in roots)


def _count_sequence_participants(lines):
    """sequenceDiagram の participant / actor 数を返す。"""
    participants = set()
    for line in lines:
        stripped = line.strip()
        m = re.match(r"^(participant|actor)\s+(\S+)", stripped)
        if m:
            participants.add(m.group(2))
    return len(participants)


def _count_sequence_messages(lines):
    """sequenceDiagram のメッセージ (矢印) 数を返す。"""
    count = 0
    arrow_pattern = re.compile(r"->>|-->>|-\)\)|--\)|->|-->")
    for line in lines:
        stripped = line.strip()
        # participant / actor / Note 行はスキップ
        if re.match(r"^(participant|actor|Note|end|loop|alt|else|opt|par|rect|critical|break)", stripped):
            continue
        if arrow_pattern.search(stripped):
            count += 1
    return count


def _count_er_entities(lines):
    """erDiagram のエンティティ数を返す。"""
    entities = set()

    # エンティティ定義ブロック: EntityName {
    entity_def_pattern = re.compile(r"^\s+(\w+)\s*\{")
    # リレーション: EntityA ||--o{ EntityB : "label"
    relation_pattern = re.compile(
        r"^\s+(\w+)\s+(?:\|\||\|\{|\}o|\}||\|o|o\||\{o|o\{)"
    )
    # より汎用的なリレーションパターン
    rel_generic = re.compile(
        r"^\s+(\w+)\s+\S*--\S*\s+(\w+)\s*:"
    )

    for line in lines:
        m = entity_def_pattern.match(line)
        if m:
            entities.add(m.group(1))
        m = rel_generic.match(line)
        if m:
            entities.add(m.group(1))
            entities.add(m.group(2))

    return len(entities)


def check_mermaid_file(filepath):
    """単一の .mmd ファイルを解析し、Issue のリストを返す。"""
    issues = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return issues

    if not content.strip():
        return issues

    lines = content.splitlines()

    # flowchart TB チェック
    _check_flowchart_tb(filepath, lines, issues)

    # sequenceDiagram チェック
    _check_sequence_diagram(filepath, lines, issues)

    # erDiagram チェック
    _check_er_diagram(filepath, lines, issues)

    return issues


def _check_flowchart_tb(filepath, lines, issues):
    """flowchart TB / direction TB ブロックを検出してチェック。"""
    in_flowchart_tb = False
    block_start = 0
    block_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if re.match(r"^flowchart\s+TB", stripped):
            in_flowchart_tb = True
            block_start = i + 1
            block_lines = []
            continue

        if re.match(r"^direction\s+TB", stripped):
            in_flowchart_tb = True
            block_start = i + 1
            block_lines = []
            continue

        if in_flowchart_tb:
            # 新しいダイアグラムタイプが始まったらブロック終了
            if re.match(r"^(flowchart|sequenceDiagram|erDiagram|classDiagram|stateDiagram|gantt|pie|gitGraph)", stripped):
                _emit_flowchart_issue(filepath, block_start, block_lines, issues)
                in_flowchart_tb = False
                continue
            block_lines.append(line)

    # ファイル末尾まで続いた場合
    if in_flowchart_tb:
        _emit_flowchart_issue(filepath, block_start, block_lines, issues)


def _emit_flowchart_issue(filepath, block_start, block_lines, issues):
    """flowchart TB ブロックの深さを評価し、超過なら Issue を追加。"""
    depth = _count_flowchart_vertical_depth(block_lines, block_start)
    if depth > MAX_FLOWCHART_VERTICAL_NODES:
        issues.append(
            Issue(
                file=filepath,
                line=block_start,
                issue_type="flowchart_vertical_nodes",
                count=depth,
                max_allowed=MAX_FLOWCHART_VERTICAL_NODES,
            )
        )


def _check_sequence_diagram(filepath, lines, issues):
    """sequenceDiagram ブロックを検出してチェック。"""
    in_seq = False
    block_start = 0
    block_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "sequenceDiagram":
            if in_seq:
                _emit_sequence_issues(filepath, block_start, block_lines, issues)
            in_seq = True
            block_start = i + 1
            block_lines = []
            continue

        if in_seq:
            if re.match(r"^(flowchart|erDiagram|classDiagram|stateDiagram|gantt|pie|gitGraph)", stripped):
                _emit_sequence_issues(filepath, block_start, block_lines, issues)
                in_seq = False
                continue
            block_lines.append(line)

    if in_seq:
        _emit_sequence_issues(filepath, block_start, block_lines, issues)


def _emit_sequence_issues(filepath, block_start, block_lines, issues):
    """sequenceDiagram ブロックの参加者数とメッセージ数を評価。"""
    participant_count = _count_sequence_participants(block_lines)
    if participant_count > MAX_SEQUENCE_PARTICIPANTS:
        issues.append(
            Issue(
                file=filepath,
                line=block_start,
                issue_type="sequence_participants",
                count=participant_count,
                max_allowed=MAX_SEQUENCE_PARTICIPANTS,
            )
        )

    message_count = _count_sequence_messages(block_lines)
    if message_count > MAX_SEQUENCE_MESSAGES:
        issues.append(
            Issue(
                file=filepath,
                line=block_start,
                issue_type="sequence_messages",
                count=message_count,
                max_allowed=MAX_SEQUENCE_MESSAGES,
            )
        )


def _check_er_diagram(filepath, lines, issues):
    """erDiagram ブロックを検出してチェック。"""
    in_er = False
    block_start = 0
    block_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "erDiagram":
            if in_er:
                _emit_er_issues(filepath, block_start, block_lines, issues)
            in_er = True
            block_start = i + 1
            block_lines = []
            continue

        if in_er:
            if re.match(r"^(flowchart|sequenceDiagram|classDiagram|stateDiagram|gantt|pie|gitGraph)", stripped):
                _emit_er_issues(filepath, block_start, block_lines, issues)
                in_er = False
                continue
            block_lines.append(line)

    if in_er:
        _emit_er_issues(filepath, block_start, block_lines, issues)


def _emit_er_issues(filepath, block_start, block_lines, issues):
    """erDiagram ブロックのエンティティ数を評価。"""
    entity_count = _count_er_entities(block_lines)
    if entity_count > MAX_ER_ENTITIES:
        issues.append(
            Issue(
                file=filepath,
                line=block_start,
                issue_type="er_entities",
                count=entity_count,
                max_allowed=MAX_ER_ENTITIES,
            )
        )


# ---------------------------------------------------------------------------
# Marp slide analysis
# ---------------------------------------------------------------------------
def _is_marp_file(filepath):
    """ファイルが Marp スライドかどうかを判定する。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(500)
    except (OSError, IOError):
        return False
    return "marp: true" in content


def _split_slides(content):
    """Marp スライドを --- で分割し、各スライドの (開始行番号, テキスト) を返す。

    最初の YAML frontmatter (--- で囲まれた部分) はスキップする。
    """
    lines = content.splitlines(keepends=True)
    slides = []
    current_lines = []
    current_start = 1
    in_frontmatter = False
    frontmatter_ended = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue

        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
                frontmatter_ended = True
                current_start = i + 1
            continue

        if stripped == "---":
            if current_lines:
                slides.append((current_start, "".join(current_lines)))
            current_lines = []
            current_start = i + 1
        else:
            current_lines.append(line)

    if current_lines:
        slides.append((current_start, "".join(current_lines)))

    return slides


def _count_bullets(text):
    """テキスト内の箇条書き行数を返す (- または * で始まる行)。"""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s", stripped):
            count += 1
    return count


def _count_table_data_rows(text):
    """テキスト内のテーブルデータ行数を返す (ヘッダーとセパレータを除く)。"""
    table_lines = []
    in_table = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
            in_table = True
        elif in_table:
            in_table = False

    if len(table_lines) < 2:
        return 0

    # ヘッダー行とセパレータ行を除外
    data_rows = 0
    for tl in table_lines:
        # セパレータ: |---|---|
        if re.match(r"^\|[\s\-:|]+\|$", tl):
            continue
        data_rows += 1

    # ヘッダー行を 1 行分引く (最初のデータ行がヘッダー)
    return max(0, data_rows - 1)


def _count_card_divs(text):
    """テキスト内の <div class="card"> の数を返す。"""
    return len(re.findall(r'<div\s+class="card"', text))


def _count_fig_text_right_cards(text):
    """fig-text レイアウト内の right カラムにあるカード数を返す。"""
    # fig-text ブロック内の right div を探す
    fig_text_pattern = re.compile(
        r'<div\s+class="fig-text">(.*?)</div>\s*</div>',
        re.DOTALL,
    )
    # より単純なアプローチ: fig-text の中の right の中の card を数える
    counts = []
    in_fig_text = False
    in_right = False
    card_count = 0
    fig_text_depth = 0
    right_depth = 0

    for line in text.splitlines():
        if '<div class="fig-text">' in line:
            in_fig_text = True
            fig_text_depth = 1
            card_count = 0
            continue

        if in_fig_text:
            if '<div class="right">' in line:
                in_right = True
                right_depth = 1
                continue

            if in_right:
                if '<div class="card"' in line:
                    card_count += 1

                # right ブロックの終了を検出
                open_divs = len(re.findall(r"<div", line))
                close_divs = len(re.findall(r"</div>", line))
                right_depth += open_divs - close_divs
                if right_depth <= 0:
                    in_right = False
                    continue

            # fig-text ブロック全体の終了
            if not in_right:
                open_divs = len(re.findall(r"<div", line))
                close_divs = len(re.findall(r"</div>", line))
                fig_text_depth += open_divs - close_divs
                if fig_text_depth <= 0:
                    counts.append(card_count)
                    in_fig_text = False

    # ファイル末尾でブロックが閉じなかった場合
    if in_fig_text and card_count > 0:
        counts.append(card_count)

    return max(counts) if counts else 0


def check_marp_slides(filepath):
    """単一の Marp .md ファイルを解析し、Issue のリストを返す。"""
    issues = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return issues

    if not content.strip():
        return issues

    if "marp: true" not in content:
        return issues

    slides = _split_slides(content)

    for slide_start, slide_text in slides:
        # 箇条書きチェック
        bullet_count = _count_bullets(slide_text)
        if bullet_count > MAX_SLIDE_BULLETS:
            issues.append(
                Issue(
                    file=filepath,
                    line=slide_start,
                    issue_type="slide_bullets",
                    count=bullet_count,
                    max_allowed=MAX_SLIDE_BULLETS,
                )
            )

        # テーブル行チェック
        table_row_count = _count_table_data_rows(slide_text)
        if table_row_count > MAX_SLIDE_TABLE_ROWS:
            issues.append(
                Issue(
                    file=filepath,
                    line=slide_start,
                    issue_type="slide_table_rows",
                    count=table_row_count,
                    max_allowed=MAX_SLIDE_TABLE_ROWS,
                )
            )

        # カードチェック
        card_count = _count_card_divs(slide_text)
        if card_count > MAX_SLIDE_CARDS:
            issues.append(
                Issue(
                    file=filepath,
                    line=slide_start,
                    issue_type="slide_cards",
                    count=card_count,
                    max_allowed=MAX_SLIDE_CARDS,
                )
            )

        # fig-text 右カラムカードチェック
        fig_card_count = _count_fig_text_right_cards(slide_text)
        if fig_card_count > MAX_FIG_TEXT_CARDS:
            issues.append(
                Issue(
                    file=filepath,
                    line=slide_start,
                    issue_type="fig_text_cards",
                    count=fig_card_count,
                    max_allowed=MAX_FIG_TEXT_CARDS,
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------
def scan_directory(docs_dir, marp_dir=None):
    """指定ディレクトリを走査し、全 Issue を返す。

    Args:
        docs_dir: .mmd ファイルと Marp .md ファイルを含むディレクトリ
        marp_dir: Marp .md ファイル専用の追加ディレクトリ (任意)
    """
    issues = []

    # .mmd ファイルスキャン
    for root, _dirs, files in os.walk(docs_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            if fname.endswith(".mmd"):
                issues.extend(check_mermaid_file(fpath))
            elif fname.endswith(".md"):
                if _is_marp_file(fpath):
                    issues.extend(check_marp_slides(fpath))

    # 追加 Marp ディレクトリ
    if marp_dir and os.path.isdir(marp_dir):
        for root, _dirs, files in os.walk(marp_dir):
            for fname in files:
                if fname.endswith(".md"):
                    fpath = os.path.join(root, fname)
                    if _is_marp_file(fpath):
                        issues.extend(check_marp_slides(fpath))

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Mermaid / Marp スライドの溢れ検出"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help=".mmd / Marp .md ファイルを含むディレクトリ",
    )
    parser.add_argument(
        "--marp-dir",
        default=None,
        help="Marp .md ファイル専用の追加ディレクトリ",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.docs_dir):
        print(f"ERROR: ディレクトリが見つかりません: {args.docs_dir}", file=sys.stderr)
        sys.exit(2)

    issues = scan_directory(args.docs_dir, marp_dir=args.marp_dir)

    if issues:
        print(f"\n=== スライド溢れチェック: {len(issues)} 件の問題を検出 ===\n")
        for issue in issues:
            print(f"  WARNING: {issue}")
        print()
        sys.exit(1)
    else:
        print("スライド溢れチェック: 問題なし")
        sys.exit(0)


if __name__ == "__main__":
    main()
