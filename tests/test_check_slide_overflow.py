"""check_slide_overflow.py のテスト"""

import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from check_slide_overflow import (
    Issue,
    check_marp_slides,
    check_mermaid_file,
    scan_directory,
)


# ---------------------------------------------------------------------------
# Mermaid: flowchart TB vertical node count
# ---------------------------------------------------------------------------
class TestMermaidFlowchartVerticalNodes:
    """flowchart TB / direction TB の縦方向ノード数チェック"""

    def test_3_vertical_nodes_no_warning(self, tmp_path):
        mmd = tmp_path / "ok.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A[Start] --> B[Process]
                B --> C[End]
        """))
        issues = check_mermaid_file(str(mmd))
        vertical_issues = [i for i in issues if i.issue_type == "flowchart_vertical_nodes"]
        assert vertical_issues == []

    def test_6_vertical_nodes_warning(self, tmp_path):
        mmd = tmp_path / "deep.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A[Step1] --> B[Step2]
                B --> C[Step3]
                C --> D[Step4]
                D --> E[Step5]
                E --> F[Step6]
        """))
        issues = check_mermaid_file(str(mmd))
        vertical_issues = [i for i in issues if i.issue_type == "flowchart_vertical_nodes"]
        assert len(vertical_issues) == 1
        assert vertical_issues[0].count == 6
        assert vertical_issues[0].max_allowed == 4

    def test_4_vertical_nodes_no_warning(self, tmp_path):
        mmd = tmp_path / "boundary.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A --> B
                B --> C
                C --> D
        """))
        issues = check_mermaid_file(str(mmd))
        vertical_issues = [i for i in issues if i.issue_type == "flowchart_vertical_nodes"]
        assert vertical_issues == []

    def test_5_vertical_nodes_warning(self, tmp_path):
        mmd = tmp_path / "over.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A --> B
                B --> C
                C --> D
                D --> E
        """))
        issues = check_mermaid_file(str(mmd))
        vertical_issues = [i for i in issues if i.issue_type == "flowchart_vertical_nodes"]
        assert len(vertical_issues) == 1
        assert vertical_issues[0].count == 5

    def test_direction_tb_in_subgraph(self, tmp_path):
        mmd = tmp_path / "subgraph.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart LR
                subgraph sub1
                    direction TB
                    A --> B
                    B --> C
                    C --> D
                    D --> E
                    E --> F
                end
        """))
        issues = check_mermaid_file(str(mmd))
        vertical_issues = [i for i in issues if i.issue_type == "flowchart_vertical_nodes"]
        assert len(vertical_issues) >= 1


# ---------------------------------------------------------------------------
# Mermaid: sequenceDiagram participant count
# ---------------------------------------------------------------------------
class TestMermaidSequenceParticipants:
    """sequenceDiagram の participant / actor 数チェック"""

    def test_4_participants_no_warning(self, tmp_path):
        mmd = tmp_path / "ok.mmd"
        mmd.write_text(textwrap.dedent("""\
            sequenceDiagram
                participant A
                participant B
                participant C
                participant D
                A->>B: msg
        """))
        issues = check_mermaid_file(str(mmd))
        participant_issues = [i for i in issues if i.issue_type == "sequence_participants"]
        assert participant_issues == []

    def test_7_participants_warning(self, tmp_path):
        mmd = tmp_path / "many.mmd"
        mmd.write_text(textwrap.dedent("""\
            sequenceDiagram
                participant A
                participant B
                participant C
                participant D
                participant E
                participant F
                participant G
                A->>B: msg
        """))
        issues = check_mermaid_file(str(mmd))
        participant_issues = [i for i in issues if i.issue_type == "sequence_participants"]
        assert len(participant_issues) == 1
        assert participant_issues[0].count == 7
        assert participant_issues[0].max_allowed == 5

    def test_5_participants_no_warning(self, tmp_path):
        mmd = tmp_path / "boundary.mmd"
        mmd.write_text(textwrap.dedent("""\
            sequenceDiagram
                participant A
                participant B
                participant C
                participant D
                participant E
                A->>B: msg
        """))
        issues = check_mermaid_file(str(mmd))
        participant_issues = [i for i in issues if i.issue_type == "sequence_participants"]
        assert participant_issues == []

    def test_actor_keyword_counted(self, tmp_path):
        mmd = tmp_path / "actors.mmd"
        mmd.write_text(textwrap.dedent("""\
            sequenceDiagram
                actor User
                participant Browser
                participant API
                participant DB
                participant Cache
                participant Queue
                User->>Browser: click
        """))
        issues = check_mermaid_file(str(mmd))
        participant_issues = [i for i in issues if i.issue_type == "sequence_participants"]
        assert len(participant_issues) == 1
        assert participant_issues[0].count == 6


# ---------------------------------------------------------------------------
# Mermaid: sequenceDiagram message count
# ---------------------------------------------------------------------------
class TestMermaidSequenceMessages:
    """sequenceDiagram のメッセージ数チェック"""

    def test_10_messages_no_warning(self, tmp_path):
        mmd = tmp_path / "ok.mmd"
        lines = ["sequenceDiagram", "    participant A", "    participant B"]
        for i in range(10):
            lines.append(f"    A->>B: msg{i}")
        mmd.write_text("\n".join(lines) + "\n")
        issues = check_mermaid_file(str(mmd))
        msg_issues = [i for i in issues if i.issue_type == "sequence_messages"]
        assert msg_issues == []

    def test_15_messages_warning(self, tmp_path):
        mmd = tmp_path / "many.mmd"
        lines = ["sequenceDiagram", "    participant A", "    participant B"]
        for i in range(15):
            lines.append(f"    A->>B: msg{i}")
        mmd.write_text("\n".join(lines) + "\n")
        issues = check_mermaid_file(str(mmd))
        msg_issues = [i for i in issues if i.issue_type == "sequence_messages"]
        assert len(msg_issues) == 1
        assert msg_issues[0].count == 15
        assert msg_issues[0].max_allowed == 12

    def test_12_messages_no_warning(self, tmp_path):
        mmd = tmp_path / "boundary.mmd"
        lines = ["sequenceDiagram", "    participant A", "    participant B"]
        for i in range(12):
            lines.append(f"    A->>B: msg{i}")
        mmd.write_text("\n".join(lines) + "\n")
        issues = check_mermaid_file(str(mmd))
        msg_issues = [i for i in issues if i.issue_type == "sequence_messages"]
        assert msg_issues == []

    def test_return_arrows_counted(self, tmp_path):
        mmd = tmp_path / "returns.mmd"
        lines = ["sequenceDiagram", "    participant A", "    participant B"]
        for i in range(7):
            lines.append(f"    A->>B: request{i}")
            lines.append(f"    B-->>A: response{i}")
        mmd.write_text("\n".join(lines) + "\n")
        issues = check_mermaid_file(str(mmd))
        msg_issues = [i for i in issues if i.issue_type == "sequence_messages"]
        assert len(msg_issues) == 1
        assert msg_issues[0].count == 14


# ---------------------------------------------------------------------------
# Mermaid: erDiagram entity count
# ---------------------------------------------------------------------------
class TestMermaidErEntities:
    """erDiagram のエンティティ数チェック"""

    def test_6_entities_no_warning(self, tmp_path):
        mmd = tmp_path / "ok.mmd"
        entities = []
        for i in range(6):
            entities.append(f"    Entity{i} {{\n        int id PK\n    }}")
        mmd.write_text("erDiagram\n" + "\n".join(entities) + "\n")
        issues = check_mermaid_file(str(mmd))
        er_issues = [i for i in issues if i.issue_type == "er_entities"]
        assert er_issues == []

    def test_10_entities_warning(self, tmp_path):
        mmd = tmp_path / "many.mmd"
        entities = []
        for i in range(10):
            entities.append(f"    Entity{i} {{\n        int id PK\n    }}")
        mmd.write_text("erDiagram\n" + "\n".join(entities) + "\n")
        issues = check_mermaid_file(str(mmd))
        er_issues = [i for i in issues if i.issue_type == "er_entities"]
        assert len(er_issues) == 1
        assert er_issues[0].count == 10
        assert er_issues[0].max_allowed == 8

    def test_8_entities_no_warning(self, tmp_path):
        mmd = tmp_path / "boundary.mmd"
        entities = []
        for i in range(8):
            entities.append(f"    Entity{i} {{\n        int id PK\n    }}")
        mmd.write_text("erDiagram\n" + "\n".join(entities) + "\n")
        issues = check_mermaid_file(str(mmd))
        er_issues = [i for i in issues if i.issue_type == "er_entities"]
        assert er_issues == []

    def test_relationship_only_entities_counted(self, tmp_path):
        """エンティティ定義ブロックがなくてもリレーションから検出"""
        mmd = tmp_path / "rels.mmd"
        lines = ["erDiagram"]
        for i in range(10):
            lines.append(f"    Entity{i} ||--o{{ Entity{i + 1} : has")
        mmd.write_text("\n".join(lines) + "\n")
        issues = check_mermaid_file(str(mmd))
        er_issues = [i for i in issues if i.issue_type == "er_entities"]
        assert len(er_issues) == 1
        assert er_issues[0].count > 8


# ---------------------------------------------------------------------------
# Marp slide: bullet points
# ---------------------------------------------------------------------------
class TestMarpBullets:
    """Marp スライドの箇条書き数チェック"""

    def test_4_bullets_no_warning(self, tmp_path):
        md = tmp_path / "ok.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide 1
            - bullet 1
            - bullet 2
            - bullet 3
            - bullet 4
        """))
        issues = check_marp_slides(str(md))
        bullet_issues = [i for i in issues if i.issue_type == "slide_bullets"]
        assert bullet_issues == []

    def test_7_bullets_warning(self, tmp_path):
        md = tmp_path / "many.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide 1
            - bullet 1
            - bullet 2
            - bullet 3
            - bullet 4
            - bullet 5
            - bullet 6
            - bullet 7
        """))
        issues = check_marp_slides(str(md))
        bullet_issues = [i for i in issues if i.issue_type == "slide_bullets"]
        assert len(bullet_issues) == 1
        assert bullet_issues[0].count == 7
        assert bullet_issues[0].max_allowed == 5

    def test_5_bullets_no_warning(self, tmp_path):
        md = tmp_path / "boundary.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide 1
            - bullet 1
            - bullet 2
            - bullet 3
            - bullet 4
            - bullet 5
        """))
        issues = check_marp_slides(str(md))
        bullet_issues = [i for i in issues if i.issue_type == "slide_bullets"]
        assert bullet_issues == []

    def test_bullets_per_slide_independent(self, tmp_path):
        """スライドごとに独立してカウント"""
        md = tmp_path / "multi.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide 1
            - a
            - b
            - c
            ---
            # Slide 2
            - d
            - e
            - f
            - g
            - h
            - i
        """))
        issues = check_marp_slides(str(md))
        bullet_issues = [i for i in issues if i.issue_type == "slide_bullets"]
        assert len(bullet_issues) == 1
        assert bullet_issues[0].count == 6


# ---------------------------------------------------------------------------
# Marp slide: table rows
# ---------------------------------------------------------------------------
class TestMarpTableRows:
    """Marp スライドのテーブル行数チェック"""

    def test_4_rows_no_warning(self, tmp_path):
        md = tmp_path / "ok.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide 1
            | Col1 | Col2 |
            |------|------|
            | a    | b    |
            | c    | d    |
            | e    | f    |
            | g    | h    |
        """))
        issues = check_marp_slides(str(md))
        table_issues = [i for i in issues if i.issue_type == "slide_table_rows"]
        assert table_issues == []

    def test_6_rows_warning(self, tmp_path):
        md = tmp_path / "many.md"
        rows = "\n".join([f"| val{i} | val{i} |" for i in range(6)])
        md.write_text(textwrap.dedent(f"""\
            ---
            marp: true
            ---
            # Slide 1
            | Col1 | Col2 |
            |------|------|
            {rows}
        """))
        issues = check_marp_slides(str(md))
        table_issues = [i for i in issues if i.issue_type == "slide_table_rows"]
        assert len(table_issues) == 1
        assert table_issues[0].count == 6
        assert table_issues[0].max_allowed == 5

    def test_5_rows_no_warning(self, tmp_path):
        md = tmp_path / "boundary.md"
        rows = "\n".join([f"| val{i} | val{i} |" for i in range(5)])
        md.write_text(textwrap.dedent(f"""\
            ---
            marp: true
            ---
            # Slide 1
            | Col1 | Col2 |
            |------|------|
            {rows}
        """))
        issues = check_marp_slides(str(md))
        table_issues = [i for i in issues if i.issue_type == "slide_table_rows"]
        assert table_issues == []


# ---------------------------------------------------------------------------
# Marp slide: cards (.card divs)
# ---------------------------------------------------------------------------
class TestMarpCards:
    """Marp スライドの .card div 数チェック"""

    def test_3_cards_no_warning(self, tmp_path):
        md = tmp_path / "ok.md"
        cards = "\n".join(['<div class="card">Card</div>' for _ in range(3)])
        md.write_text(f"---\nmarp: true\n---\n# Slide\n{cards}\n")
        issues = check_marp_slides(str(md))
        card_issues = [i for i in issues if i.issue_type == "slide_cards"]
        assert card_issues == []

    def test_5_cards_warning(self, tmp_path):
        md = tmp_path / "many.md"
        cards = "\n".join(['<div class="card">Card</div>' for _ in range(5)])
        md.write_text(f"---\nmarp: true\n---\n# Slide\n{cards}\n")
        issues = check_marp_slides(str(md))
        card_issues = [i for i in issues if i.issue_type == "slide_cards"]
        assert len(card_issues) == 1
        assert card_issues[0].count == 5
        assert card_issues[0].max_allowed == 4

    def test_4_cards_no_warning(self, tmp_path):
        md = tmp_path / "boundary.md"
        cards = "\n".join(['<div class="card">Card</div>' for _ in range(4)])
        md.write_text(f"---\nmarp: true\n---\n# Slide\n{cards}\n")
        issues = check_marp_slides(str(md))
        card_issues = [i for i in issues if i.issue_type == "slide_cards"]
        assert card_issues == []


# ---------------------------------------------------------------------------
# Marp slide: .fig-text with > 3 cards in right column
# ---------------------------------------------------------------------------
class TestMarpFigTextCards:
    """fig-text レイアウトの右カラムカード数チェック"""

    def test_2_cards_in_fig_text_no_warning(self, tmp_path):
        md = tmp_path / "ok.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide
            <div class="fig-text">
            <div class="right">
            <div class="card">A</div>
            <div class="card">B</div>
            </div>
            </div>
        """))
        issues = check_marp_slides(str(md))
        ft_issues = [i for i in issues if i.issue_type == "fig_text_cards"]
        assert ft_issues == []

    def test_4_cards_in_fig_text_warning(self, tmp_path):
        md = tmp_path / "many.md"
        cards = "\n".join(['<div class="card">C</div>' for _ in range(4)])
        md.write_text(textwrap.dedent(f"""\
            ---
            marp: true
            ---
            # Slide
            <div class="fig-text">
            <div class="right">
            {cards}
            </div>
            </div>
        """))
        issues = check_marp_slides(str(md))
        ft_issues = [i for i in issues if i.issue_type == "fig_text_cards"]
        assert len(ft_issues) == 1
        assert ft_issues[0].count == 4
        assert ft_issues[0].max_allowed == 3


# ---------------------------------------------------------------------------
# Empty files
# ---------------------------------------------------------------------------
class TestEmptyFiles:
    """空ファイルでエラーにならないこと"""

    def test_empty_mmd_no_error(self, tmp_path):
        mmd = tmp_path / "empty.mmd"
        mmd.write_text("")
        issues = check_mermaid_file(str(mmd))
        assert issues == []

    def test_empty_marp_no_error(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("")
        issues = check_marp_slides(str(md))
        assert issues == []


# ---------------------------------------------------------------------------
# Non-mermaid / non-marp files skipped in scan
# ---------------------------------------------------------------------------
class TestScanDirectory:
    """scan_directory は対象外ファイルをスキップ"""

    def test_non_mmd_files_skipped(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        issues = scan_directory(str(tmp_path))
        assert issues == []

    def test_mmd_files_scanned(self, tmp_path):
        mmd = tmp_path / "deep.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A --> B
                B --> C
                C --> D
                D --> E
                E --> F
        """))
        issues = scan_directory(str(tmp_path))
        assert len(issues) > 0

    def test_marp_md_scanned(self, tmp_path):
        md = tmp_path / "slide.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide
            - a
            - b
            - c
            - d
            - e
            - f
        """))
        issues = scan_directory(str(tmp_path))
        assert len(issues) > 0

    def test_non_marp_md_skipped(self, tmp_path):
        md = tmp_path / "readme.md"
        md.write_text("# README\n- a\n- b\n- c\n- d\n- e\n- f\n- g\n")
        issues = scan_directory(str(tmp_path))
        assert issues == []

    def test_scan_with_marp_dir(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        marp = tmp_path / "marp"
        marp.mkdir()
        mmd = docs / "test.mmd"
        mmd.write_text(textwrap.dedent("""\
            flowchart TB
                A --> B
                B --> C
                C --> D
                D --> E
                E --> F
        """))
        md = marp / "slide.md"
        md.write_text(textwrap.dedent("""\
            ---
            marp: true
            ---
            # Slide
            - a
            - b
            - c
            - d
            - e
            - f
        """))
        issues = scan_directory(str(docs), marp_dir=str(marp))
        mmd_issues = [i for i in issues if i.file.endswith(".mmd")]
        marp_issues = [i for i in issues if i.file.endswith(".md")]
        assert len(mmd_issues) > 0
        assert len(marp_issues) > 0


# ---------------------------------------------------------------------------
# Issue dataclass
# ---------------------------------------------------------------------------
class TestIssueDataclass:
    """Issue の構造チェック"""

    def test_issue_fields(self):
        issue = Issue(
            file="test.mmd",
            line=1,
            issue_type="flowchart_vertical_nodes",
            count=6,
            max_allowed=4,
        )
        assert issue.file == "test.mmd"
        assert issue.line == 1
        assert issue.issue_type == "flowchart_vertical_nodes"
        assert issue.count == 6
        assert issue.max_allowed == 4

    def test_issue_str(self):
        issue = Issue(
            file="test.mmd",
            line=5,
            issue_type="sequence_participants",
            count=7,
            max_allowed=5,
        )
        s = str(issue)
        assert "test.mmd" in s
        assert "7" in s
        assert "5" in s
