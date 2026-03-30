#!/usr/bin/env python3
"""
split_diagram.py - 超過 Mermaid ダイアグラムを閾値内に自動分割

check_slide_overflow.py で検出される超過ダイアグラムを、
閾値を満たす複数のサブダイアグラムに自動分割する。

使い方:
  # 単一ファイルモード
  python scripts/split_diagram.py --input docs/diagrams/name-er-master.mmd --max-entities 8

  # バッチモード（指定名のすべての超過ダイアグラムを分割）
  python scripts/split_diagram.py --docs-dir ./docs --name system-name --auto

  # ドライラン（書き込みなしで結果をプレビュー）
  python scripts/split_diagram.py --docs-dir ./docs --name system-name --auto --dry-run
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Default thresholds (same as check_slide_overflow.py)
# ---------------------------------------------------------------------------
DEFAULT_MAX_FLOWCHART_VERTICAL_NODES = 4
DEFAULT_MAX_SEQUENCE_PARTICIPANTS = 5
DEFAULT_MAX_SEQUENCE_MESSAGES = 12
DEFAULT_MAX_ER_ENTITIES = 8


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class SplitResult:
    """分割結果を表すデータクラス"""

    source_file: str
    diagram_type: str
    original_count: int
    threshold: int
    parts: list = field(default_factory=list)  # list of (filename, content)


# ---------------------------------------------------------------------------
# Diagram type detection
# ---------------------------------------------------------------------------
def detect_diagram_type(content):
    """Mermaid コンテンツからダイアグラムタイプを検出する。"""
    first_line = content.strip().splitlines()[0].strip() if content.strip() else ""

    if first_line.startswith("erDiagram"):
        return "erDiagram"
    if first_line.startswith("sequenceDiagram"):
        return "sequenceDiagram"
    if re.match(r"^(flowchart|graph)\s+(TB|TD|BT|LR|RL)", first_line):
        return "flowchart"
    if first_line.startswith("stateDiagram"):
        return "stateDiagram"

    return None


# ---------------------------------------------------------------------------
# ER Diagram splitting
# ---------------------------------------------------------------------------
def _parse_er_entities_and_relations(lines):
    """ER ダイアグラムからエンティティと関係を解析する。

    Returns:
        entities: dict[name, list[str]] - エンティティ名 → 属性行のリスト
        relations: list[tuple[str, str, str]] - (entity1, entity2, relation_line)
    """
    entities = {}
    relations = []

    entity_def_pattern = re.compile(r"^\s+(\w+)\s*\{")
    rel_generic = re.compile(r"^\s+(\w+)\s+\S*--\S*\s+(\w+)\s*:")
    closing_brace = re.compile(r"^\s+\}")

    current_entity = None
    current_attrs = []

    for line in lines:
        if current_entity is not None:
            if closing_brace.match(line):
                entities[current_entity] = list(current_attrs)
                current_entity = None
                current_attrs = []
            else:
                current_attrs.append(line)
            continue

        m = entity_def_pattern.match(line)
        if m:
            current_entity = m.group(1)
            current_attrs = []
            continue

        m = rel_generic.match(line)
        if m:
            e1, e2 = m.group(1), m.group(2)
            entities.setdefault(e1, [])
            entities.setdefault(e2, [])
            relations.append((e1, e2, line))

    # ファイル末尾でエンティティが閉じなかった場合
    if current_entity is not None:
        entities[current_entity] = list(current_attrs)

    return entities, relations


def _build_adjacency(entities, relations):
    """エンティティ間の隣接リストを構築する。"""
    adj = {e: set() for e in entities}
    for e1, e2, _ in relations:
        adj.setdefault(e1, set()).add(e2)
        adj.setdefault(e2, set()).add(e1)
    return adj


def _cluster_entities(entities, relations, max_per_cluster):
    """関連するエンティティをクラスタにグループ化する。

    隣接するエンティティを優先的に同じクラスタに配置し、
    各クラスタの上限を max_per_cluster に制限する。
    """
    adj = _build_adjacency(entities, relations)
    remaining = set(entities.keys())
    clusters = []

    # 関係数が多いエンティティから開始（ハブノード優先）
    sorted_entities = sorted(
        remaining,
        key=lambda e: len(adj.get(e, set())),
        reverse=True,
    )

    while remaining:
        cluster = []
        # 残りの中で最も関係が多いエンティティを種とする
        seed = None
        for e in sorted_entities:
            if e in remaining:
                seed = e
                break
        if seed is None:
            break

        cluster.append(seed)
        remaining.discard(seed)

        # BFS で近隣エンティティをクラスタに追加
        queue = list(adj.get(seed, set()))
        while queue and len(cluster) < max_per_cluster:
            candidate = queue.pop(0)
            if candidate in remaining:
                cluster.append(candidate)
                remaining.discard(candidate)
                # 候補の隣接ノードもキューに追加
                for neighbor in adj.get(candidate, set()):
                    if neighbor in remaining and neighbor not in queue:
                        queue.append(neighbor)

        clusters.append(cluster)

    return clusters


def _render_er_part(cluster_entities, all_entities, relations, part_num, total_parts):
    """ER ダイアグラムの1パートを Mermaid 形式で描画する。"""
    lines = ["erDiagram"]
    cluster_set = set(cluster_entities)

    # このクラスタに関連するリレーションを出力
    for e1, e2, rel_line in relations:
        if e1 in cluster_set and e2 in cluster_set:
            lines.append(rel_line)

    # 空行で区切り
    lines.append("")

    # エンティティ定義を出力
    for entity_name in cluster_entities:
        attrs = all_entities.get(entity_name, [])
        if attrs:
            lines.append(f"    {entity_name} {{")
            for attr in attrs:
                lines.append(attr)
            lines.append("    }")
        else:
            # 属性定義がないエンティティはリレーションのみで表現済み
            pass

    # 継続ノートを追加
    if total_parts > 1:
        lines.append("")
        lines.append(
            f"    %% Part {part_num}/{total_parts}"
            f" - 他のパートも参照してください"
        )

    return "\n".join(lines) + "\n"


def split_er_diagram(content, max_entities):
    """ER ダイアグラムを max_entities 以下のサブダイアグラムに分割する。"""
    lines = content.splitlines()
    # 最初の行 (erDiagram) をスキップ
    body_lines = lines[1:] if lines and lines[0].strip() == "erDiagram" else lines

    entities, relations = _parse_er_entities_and_relations(body_lines)

    if len(entities) <= max_entities:
        return None  # 分割不要

    clusters = _cluster_entities(entities, relations, max_entities)
    total = len(clusters)

    parts = []
    for i, cluster in enumerate(clusters, 1):
        part_content = _render_er_part(
            cluster, entities, relations, i, total
        )
        parts.append(part_content)

    return SplitResult(
        source_file="",
        diagram_type="erDiagram",
        original_count=len(entities),
        threshold=max_entities,
        parts=[(f"part{i}", content) for i, content in enumerate(parts, 1)],
    )


# ---------------------------------------------------------------------------
# Sequence Diagram splitting
# ---------------------------------------------------------------------------
def _parse_sequence_elements(lines):
    """シーケンスダイアグラムのパーティシパントとメッセージを解析する。

    Returns:
        participants: list[str] - participant/actor 定義行
        messages: list[str] - メッセージ行
        notes: list[str] - Note 行
        blocks: list[tuple[int, int, str]] - (start, end, type) ブロック構造
    """
    participants = []
    messages = []
    other_lines = []
    arrow_pattern = re.compile(r"->>|-->>|-\)\)|--\)|->|-->")

    for line in lines:
        stripped = line.strip()
        if re.match(r"^(participant|actor)\s+", stripped):
            participants.append(line)
        elif re.match(
            r"^(Note|end|loop|alt|else|opt|par|rect|critical|break)",
            stripped,
        ):
            other_lines.append(line)
        elif arrow_pattern.search(stripped):
            messages.append(line)
        else:
            other_lines.append(line)

    return participants, messages, other_lines


def _extract_participants_from_messages(messages):
    """メッセージ行から使用されているパーティシパント名を抽出する。"""
    participants_used = set()
    arrow_pattern = re.compile(r"(->>|-->>|-\)\)|--\)|->|-->)")
    for line in messages:
        stripped = line.strip()
        parts = arrow_pattern.split(stripped, maxsplit=1)
        if len(parts) >= 3:
            sender = parts[0].strip()
            receiver_part = parts[2].strip()
            # receiver: "Name: message" のパターン
            receiver = receiver_part.split(":")[0].strip()
            participants_used.add(sender)
            participants_used.add(receiver)
    return participants_used


def _filter_participants_for_messages(participant_lines, messages):
    """メッセージ群で使用されるパーティシパント定義行のみを返す。"""
    used = _extract_participants_from_messages(messages)
    result = []
    for line in participant_lines:
        stripped = line.strip()
        m = re.match(r"^(participant|actor)\s+(\S+)", stripped)
        if m:
            name = m.group(2)
            if name in used:
                result.append(line)
    return result


def split_sequence_diagram(content, max_messages, max_participants):
    """シーケンスダイアグラムをメッセージ数とパーティシパント数の制限内に分割する。"""
    lines = content.splitlines()
    body_lines = (
        lines[1:] if lines and lines[0].strip() == "sequenceDiagram" else lines
    )

    participants, messages, other_lines = _parse_sequence_elements(body_lines)

    total_messages = len(messages)
    if total_messages <= max_messages:
        return None  # 分割不要

    # Note 行を位置情報付きで保持（メッセージの直前の Note はそのメッセージと一緒に移動）
    # 簡略化: メッセージを max_messages 件ずつのチャンクに分割
    chunks = []
    for i in range(0, total_messages, max_messages):
        chunk = messages[i : i + max_messages]
        chunks.append(chunk)

    total = len(chunks)
    parts = []
    for i, chunk in enumerate(chunks, 1):
        part_lines = ["sequenceDiagram"]

        # このチャンクで使われるパーティシパントのみ含める
        filtered_participants = _filter_participants_for_messages(
            participants, chunk
        )
        if filtered_participants:
            part_lines.extend(filtered_participants)
            part_lines.append("")

        # 継続ノートを追加（先頭パート以外）
        if i > 1:
            part_lines.append(
                f"    Note over {_get_first_participant_name(filtered_participants)}"
                f": (Part {i}/{total} - 前パートからの続き)"
            )
            part_lines.append("")

        part_lines.extend(chunk)

        # 末尾ノート
        if i < total:
            part_lines.append("")
            part_lines.append(
                f"    Note over {_get_first_participant_name(filtered_participants)}"
                f": (Part {i+1} に続く)"
            )

        part_lines.append(
            f"    %% Part {i}/{total}"
        )

        parts.append("\n".join(part_lines) + "\n")

    return SplitResult(
        source_file="",
        diagram_type="sequenceDiagram",
        original_count=total_messages,
        threshold=max_messages,
        parts=[(f"part{i}", content) for i, content in enumerate(parts, 1)],
    )


def _get_first_participant_name(participant_lines):
    """パーティシパント行リストから最初の名前を取得する。"""
    for line in participant_lines:
        m = re.match(r"^\s*(participant|actor)\s+(\S+)", line.strip())
        if m:
            return m.group(2)
    return "Unknown"


# ---------------------------------------------------------------------------
# Flowchart splitting
# ---------------------------------------------------------------------------
def _parse_flowchart_structure(lines):
    """フローチャートのノード、エッジ、サブグラフを解析する。

    Returns:
        direction: str - "TB", "LR", etc.
        subgraphs: list[dict] - サブグラフ情報
        edges: list[str] - エッジ行
        node_defs: list[str] - ノード定義行
    """
    subgraphs = []
    edges = []
    node_defs = []
    current_subgraph = None
    current_lines = []

    node_pattern = re.compile(
        r"^\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->"
        r"\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?"
    )
    subgraph_start = re.compile(r"^\s*subgraph\s+(\w+)(?:\[(.+?)\])?")
    subgraph_end = re.compile(r"^\s*end\s*$")

    for line in lines:
        stripped = line.strip()

        m = subgraph_start.match(stripped)
        if m:
            if current_subgraph is not None:
                subgraphs.append(
                    {"name": current_subgraph, "lines": list(current_lines)}
                )
            current_subgraph = m.group(1)
            current_lines = [line]
            continue

        if subgraph_end.match(stripped) and current_subgraph is not None:
            current_lines.append(line)
            subgraphs.append(
                {"name": current_subgraph, "lines": list(current_lines)}
            )
            current_subgraph = None
            current_lines = []
            continue

        if current_subgraph is not None:
            current_lines.append(line)
            continue

        if node_pattern.match(stripped):
            edges.append(line)
        elif stripped and not stripped.startswith("%%"):
            node_defs.append(line)

    if current_subgraph is not None:
        subgraphs.append(
            {"name": current_subgraph, "lines": list(current_lines)}
        )

    return subgraphs, edges, node_defs


def _count_flowchart_depth(content):
    """フローチャートの縦方向深さを計算する。"""
    lines = content.splitlines()
    graph = {}
    nodes = set()
    node_pattern = re.compile(
        r"^\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->"
        r"\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?"
    )

    for line in lines:
        m = node_pattern.match(line.strip())
        if m:
            src, dst = m.group(1), m.group(2)
            nodes.add(src)
            nodes.add(dst)
            graph.setdefault(src, []).append(dst)

    if not nodes:
        return 0

    memo = {}

    def depth(node, visiting=None):
        if visiting is None:
            visiting = set()
        if node in memo:
            return memo[node]
        if node in visiting:
            return 1
        visiting = {*visiting, node}
        children = graph.get(node, [])
        if not children:
            memo[node] = 1
            return 1
        max_child = max(depth(c, visiting) for c in children)
        memo[node] = 1 + max_child
        return memo[node]

    has_incoming = set()
    for children in graph.values():
        for c in children:
            has_incoming.add(c)
    roots = [n for n in nodes if n not in has_incoming] or list(nodes)

    return max(depth(r) for r in roots)


def split_flowchart(content, max_nodes):
    """フローチャートをサブグラフ単位で分割する。"""
    lines = content.splitlines()
    first_line = lines[0].strip() if lines else ""

    # ダイアグラム方向を抽出
    direction_match = re.match(r"^(flowchart|graph)\s+(TB|TD|BT|LR|RL)", first_line)
    if not direction_match:
        return None
    diagram_keyword = direction_match.group(1)
    direction = direction_match.group(2)

    body_lines = lines[1:]
    subgraphs, edges, node_defs = _parse_flowchart_structure(body_lines)

    # サブグラフがあればサブグラフ単位で分割
    if subgraphs:
        depth = _count_flowchart_depth(content)
        if depth <= max_nodes:
            return None

        # サブグラフごとに1パート + サブグラフ間のエッジを含む概要パート
        parts = []

        # 概要パート: サブグラフ名のみのノードとサブグラフ間エッジ
        overview_lines = [f"{diagram_keyword} {direction}"]
        for sg in subgraphs:
            overview_lines.append(f"    {sg['name']}[{sg['name']}]")
        # サブグラフ間エッジのみ抽出
        subgraph_nodes = set()
        for sg in subgraphs:
            for line in sg["lines"]:
                node_m = re.match(
                    r"^\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?", line.strip()
                )
                if node_m:
                    subgraph_nodes.add(node_m.group(1))
        for edge_line in edges:
            overview_lines.append(edge_line)

        overview_lines.append(
            f"    %% 概要図 - 詳細は各パートを参照"
        )
        parts.append(("\n".join(overview_lines) + "\n", "overview"))

        # 各サブグラフを個別パートとして出力
        for i, sg in enumerate(subgraphs, 1):
            sg_lines = [f"{diagram_keyword} {direction}"]
            sg_lines.extend(sg["lines"])
            # サブグラフに関連するエッジを追加
            sg_line_content = "\n".join(sg["lines"])
            for edge_line in edges:
                edge_stripped = edge_line.strip()
                node_m = re.match(
                    r"^\s*(\w+)(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->"
                    r"\s*(\w+)",
                    edge_stripped,
                )
                if node_m:
                    src, dst = node_m.group(1), node_m.group(2)
                    if src in sg_line_content or dst in sg_line_content:
                        sg_lines.append(edge_line)

            sg_lines.append(
                f"    %% Part {i}/{len(subgraphs)}"
            )
            parts.append(("\n".join(sg_lines) + "\n", f"part{i}"))

        total = len(parts)
        return SplitResult(
            source_file="",
            diagram_type="flowchart",
            original_count=depth,
            threshold=max_nodes,
            parts=[
                (suffix, content) for content, suffix in parts
            ],
        )

    # サブグラフがない場合、エッジの縦チェーンを分割
    depth = _count_flowchart_depth(content)
    if depth <= max_nodes:
        return None

    # エッジを順番に max_nodes 件ずつチャンク分割
    all_body = body_lines
    chunk_size = max(1, max_nodes - 1)  # エッジ数 = ノード数 - 1
    edge_lines_only = [
        line
        for line in all_body
        if re.match(
            r"^\s*\w+(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->",
            line.strip(),
        )
    ]
    non_edge_lines = [
        line
        for line in all_body
        if not re.match(
            r"^\s*\w+(?:\[.*?\]|\(.*?\)|\{.*?\})?\s*-->",
            line.strip(),
        )
        and line.strip()
    ]

    chunks = []
    for i in range(0, len(edge_lines_only), chunk_size):
        chunks.append(edge_lines_only[i : i + chunk_size])

    if len(chunks) <= 1:
        return None

    total = len(chunks)
    parts = []
    for i, chunk in enumerate(chunks, 1):
        part_lines = [f"{diagram_keyword} {direction}"]
        part_lines.extend(chunk)
        part_lines.append(f"    %% Part {i}/{total}")
        parts.append(("\n".join(part_lines) + "\n", f"part{i}"))

    return SplitResult(
        source_file="",
        diagram_type="flowchart",
        original_count=depth,
        threshold=max_nodes,
        parts=[(suffix, content) for content, suffix in parts],
    )


# ---------------------------------------------------------------------------
# State Diagram splitting
# ---------------------------------------------------------------------------
def _parse_state_groups(lines):
    """stateDiagram のステートグループを解析する。

    Returns:
        groups: list[dict] - {"name": str, "lines": list[str]}
        transitions: list[str] - グループ外の遷移行
        other: list[str] - その他の行
    """
    groups = []
    transitions = []
    other = []
    current_group = None
    current_lines = []
    depth = 0

    state_group_pattern = re.compile(r"^\s*state\s+(\S+)\s*\{")
    transition_pattern = re.compile(r"^\s*\S+\s*-->\s*\S+")

    for line in lines:
        stripped = line.strip()

        if current_group is not None:
            current_lines.append(line)
            depth += stripped.count("{") - stripped.count("}")
            if depth <= 0:
                groups.append(
                    {"name": current_group, "lines": list(current_lines)}
                )
                current_group = None
                current_lines = []
                depth = 0
            continue

        m = state_group_pattern.match(stripped)
        if m:
            current_group = m.group(1)
            current_lines = [line]
            depth = 1
            continue

        if transition_pattern.match(stripped):
            transitions.append(line)
        elif stripped and not stripped.startswith("%%"):
            other.append(line)

    if current_group is not None:
        groups.append({"name": current_group, "lines": list(current_lines)})

    return groups, transitions, other


def _count_states(content):
    """stateDiagram 内のユニークなステート数を数える。"""
    states = set()
    transition_pattern = re.compile(r"^\s*(\S+)\s*-->\s*(\S+)")
    for line in content.splitlines():
        m = transition_pattern.match(line.strip())
        if m:
            s1, s2 = m.group(1), m.group(2)
            if s1 != "[*]":
                states.add(s1)
            if s2 != "[*]":
                states.add(s2)
    return len(states)


def split_state_diagram(content, max_nodes):
    """stateDiagram をステートグループ単位で分割する。"""
    lines = content.splitlines()
    first_line = lines[0].strip() if lines else ""

    if not first_line.startswith("stateDiagram"):
        return None

    state_count = _count_states(content)
    if state_count <= max_nodes:
        return None

    body_lines = lines[1:]
    groups, transitions, other = _parse_state_groups(body_lines)

    if not groups:
        # グループがない場合、遷移を max_nodes 件ずつ分割
        all_transitions = transitions
        chunk_size = max(1, max_nodes)
        chunks = [
            all_transitions[i : i + chunk_size]
            for i in range(0, len(all_transitions), chunk_size)
        ]
        if len(chunks) <= 1:
            return None

        total = len(chunks)
        parts = []
        for i, chunk in enumerate(chunks, 1):
            part_lines = [first_line]
            part_lines.extend(other)
            part_lines.extend(chunk)
            part_lines.append(f"    %% Part {i}/{total}")
            parts.append(("\n".join(part_lines) + "\n", f"part{i}"))

        return SplitResult(
            source_file="",
            diagram_type="stateDiagram",
            original_count=state_count,
            threshold=max_nodes,
            parts=[(suffix, content) for content, suffix in parts],
        )

    # グループ単位で分割
    total = len(groups)
    parts = []
    for i, group in enumerate(groups, 1):
        part_lines = [first_line]
        # [*] からこのグループへの遷移を含める
        for t_line in transitions:
            stripped = t_line.strip()
            if group["name"] in stripped or "[*]" in stripped:
                part_lines.append(t_line)
        part_lines.extend(group["lines"])
        # グループ間遷移のうちこのグループに関連するものを含める
        for t_line in transitions:
            if group["name"] in t_line and t_line not in part_lines:
                part_lines.append(t_line)
        part_lines.append(f"    %% Part {i}/{total}")
        parts.append(("\n".join(part_lines) + "\n", f"part{i}"))

    return SplitResult(
        source_file="",
        diagram_type="stateDiagram",
        original_count=state_count,
        threshold=max_nodes,
        parts=[(suffix, content) for content, suffix in parts],
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def analyze_and_split(filepath, max_entities, max_messages, max_participants, max_nodes):
    """単一ファイルを分析し、必要なら分割結果を返す。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError) as e:
        print(f"ERROR: ファイルを読み取れません: {filepath} ({e})", file=sys.stderr)
        return None

    if not content.strip():
        return None

    diagram_type = detect_diagram_type(content)
    if diagram_type is None:
        return None

    result = None

    if diagram_type == "erDiagram":
        result = split_er_diagram(content, max_entities)
    elif diagram_type == "sequenceDiagram":
        result = split_sequence_diagram(content, max_messages, max_participants)
    elif diagram_type == "flowchart":
        result = split_flowchart(content, max_nodes)
    elif diagram_type == "stateDiagram":
        result = split_state_diagram(content, max_nodes)

    if result is not None:
        result.source_file = filepath

    return result


def write_split_files(result, dry_run=False):
    """分割結果をファイルに書き出す。

    元ファイルが name.mmd の場合:
      - name-part1.mmd, name-part2.mmd, ... を生成
    """
    source = Path(result.source_file)
    stem = source.stem
    suffix = source.suffix
    parent = source.parent

    written_files = []
    for part_suffix, content in result.parts:
        out_name = f"{stem}-{part_suffix}{suffix}"
        out_path = parent / out_name

        if dry_run:
            print(f"  [DRY RUN] 書き込み予定: {out_path}")
            print(f"            ({len(content.splitlines())} 行)")
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  書き込み: {out_path}")

        written_files.append(str(out_path))

    return written_files


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------
def find_oversized_diagrams(docs_dir, name, max_entities, max_messages, max_nodes):
    """指定名のすべての .mmd ファイルを検査し、超過しているものを返す。"""
    diagrams_dir = os.path.join(docs_dir, "diagrams")
    if not os.path.isdir(diagrams_dir):
        print(f"WARNING: diagrams ディレクトリが見つかりません: {diagrams_dir}", file=sys.stderr)
        return []

    oversized = []
    for fname in sorted(os.listdir(diagrams_dir)):
        if not fname.endswith(".mmd"):
            continue
        if not fname.startswith(name):
            continue
        # 既に分割済みのファイル (-partN.mmd) はスキップ
        if re.search(r"-part\d+\.mmd$", fname):
            continue
        if re.search(r"-overview\.mmd$", fname):
            continue

        fpath = os.path.join(diagrams_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        diagram_type = detect_diagram_type(content)
        needs_split = False

        if diagram_type == "erDiagram":
            from scripts.check_slide_overflow import _count_er_entities

            lines = content.splitlines()[1:]
            if _count_er_entities(lines) > max_entities:
                needs_split = True
        elif diagram_type == "sequenceDiagram":
            from scripts.check_slide_overflow import (
                _count_sequence_messages,
                _count_sequence_participants,
            )

            lines = content.splitlines()[1:]
            if (
                _count_sequence_messages(lines) > max_messages
                or _count_sequence_participants(lines) > max_entities
            ):
                needs_split = True
        elif diagram_type == "flowchart":
            if _count_flowchart_depth(content) > max_nodes:
                needs_split = True
        elif diagram_type == "stateDiagram":
            if _count_states(content) > max_nodes:
                needs_split = True

        if needs_split:
            oversized.append(fpath)

    return oversized


def find_oversized_standalone(docs_dir, name, max_entities, max_messages, max_nodes):
    """check_slide_overflow のインポートに頼らないスタンドアロン版。"""
    diagrams_dir = os.path.join(docs_dir, "diagrams")
    if not os.path.isdir(diagrams_dir):
        print(f"WARNING: diagrams ディレクトリが見つかりません: {diagrams_dir}", file=sys.stderr)
        return []

    oversized = []
    for fname in sorted(os.listdir(diagrams_dir)):
        if not fname.endswith(".mmd"):
            continue
        if not fname.startswith(name):
            continue
        if re.search(r"-part\d+\.mmd$", fname):
            continue
        if re.search(r"-overview\.mmd$", fname):
            continue

        fpath = os.path.join(diagrams_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        diagram_type = detect_diagram_type(content)
        needs_split = False

        if diagram_type == "erDiagram":
            lines = content.splitlines()
            body = lines[1:] if lines and lines[0].strip() == "erDiagram" else lines
            entities, _ = _parse_er_entities_and_relations(body)
            if len(entities) > max_entities:
                needs_split = True
        elif diagram_type == "sequenceDiagram":
            lines = content.splitlines()
            body = (
                lines[1:]
                if lines and lines[0].strip() == "sequenceDiagram"
                else lines
            )
            participants, messages, _ = _parse_sequence_elements(body)
            if len(messages) > max_messages or len(participants) > max_entities:
                needs_split = True
        elif diagram_type == "flowchart":
            if _count_flowchart_depth(content) > max_nodes:
                needs_split = True
        elif diagram_type == "stateDiagram":
            if _count_states(content) > max_nodes:
                needs_split = True

        if needs_split:
            oversized.append(fpath)

    return oversized


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="超過 Mermaid ダイアグラムを閾値内に自動分割"
    )

    # 単一ファイルモード
    parser.add_argument(
        "--input",
        default=None,
        help="分割対象の .mmd ファイルパス（単一ファイルモード）",
    )

    # バッチモード
    parser.add_argument(
        "--docs-dir",
        default=None,
        help="ドキュメントディレクトリ（バッチモード）",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="プロジェクト名プレフィックス（バッチモードで必須）",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="超過ダイアグラムを自動検出して分割（バッチモード）",
    )

    # 閾値オーバーライド
    parser.add_argument(
        "--max-entities",
        type=int,
        default=DEFAULT_MAX_ER_ENTITIES,
        help=f"ER ダイアグラムの最大エンティティ数 (default: {DEFAULT_MAX_ER_ENTITIES})",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=DEFAULT_MAX_SEQUENCE_MESSAGES,
        help=f"シーケンスダイアグラムの最大メッセージ数 (default: {DEFAULT_MAX_SEQUENCE_MESSAGES})",
    )
    parser.add_argument(
        "--max-participants",
        type=int,
        default=DEFAULT_MAX_SEQUENCE_PARTICIPANTS,
        help=f"シーケンスダイアグラムの最大パーティシパント数 (default: {DEFAULT_MAX_SEQUENCE_PARTICIPANTS})",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=DEFAULT_MAX_FLOWCHART_VERTICAL_NODES,
        help=f"フローチャート/ステートの最大縦ノード数 (default: {DEFAULT_MAX_FLOWCHART_VERTICAL_NODES})",
    )

    # オプション
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="書き込みせずにプレビューのみ表示",
    )

    args = parser.parse_args()

    # バリデーション
    if args.input and args.auto:
        print("ERROR: --input と --auto は同時に指定できません", file=sys.stderr)
        sys.exit(2)

    if not args.input and not args.auto:
        print("ERROR: --input または --auto のいずれかを指定してください", file=sys.stderr)
        sys.exit(2)

    if args.auto and (not args.docs_dir or not args.name):
        print("ERROR: --auto モードでは --docs-dir と --name が必須です", file=sys.stderr)
        sys.exit(2)

    # 単一ファイルモード
    if args.input:
        if not os.path.isfile(args.input):
            print(f"ERROR: ファイルが見つかりません: {args.input}", file=sys.stderr)
            sys.exit(2)

        print(f"分析中: {args.input}")
        result = analyze_and_split(
            args.input,
            args.max_entities,
            args.max_messages,
            args.max_participants,
            args.max_nodes,
        )

        if result is None:
            print("分割不要: 閾値内です")
            sys.exit(0)

        print(
            f"分割: {result.diagram_type} "
            f"({result.original_count} → {len(result.parts)} パート, "
            f"閾値: {result.threshold})"
        )
        write_split_files(result, dry_run=args.dry_run)
        sys.exit(0)

    # バッチモード
    print(f"バッチモード: {args.docs_dir} / {args.name}")
    oversized = find_oversized_standalone(
        args.docs_dir,
        args.name,
        args.max_entities,
        args.max_messages,
        args.max_nodes,
    )

    if not oversized:
        print("分割が必要なダイアグラムはありません")
        sys.exit(0)

    print(f"{len(oversized)} 件の超過ダイアグラムを検出\n")

    total_parts = 0
    for fpath in oversized:
        print(f"分析中: {os.path.basename(fpath)}")
        result = analyze_and_split(
            fpath,
            args.max_entities,
            args.max_messages,
            args.max_participants,
            args.max_nodes,
        )

        if result is None:
            print("  スキップ（分割不要）")
            continue

        print(
            f"  分割: {result.diagram_type} "
            f"({result.original_count} → {len(result.parts)} パート, "
            f"閾値: {result.threshold})"
        )
        write_split_files(result, dry_run=args.dry_run)
        total_parts += len(result.parts)
        print()

    action = "書き込み予定" if args.dry_run else "生成"
    print(f"\n完了: {total_parts} ファイル{action}")
    sys.exit(0)


if __name__ == "__main__":
    main()
