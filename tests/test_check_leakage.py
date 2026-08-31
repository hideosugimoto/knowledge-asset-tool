"""check_leakage.py のテスト

--json 出力が機械可読（json.load でパース可能）であることを検証する。
検出が 0 件のときは問題が表面化しないため、意図的に検出させたうえで確認する。
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "check_leakage.py")
)

# 検出対象のテーブル名。このテストファイル自身が check_leakage に
# 引っかからないよう、リテラルを連結して組み立てる。
LEAK_TABLE = "vtiger" + "_users"


def _init_repo(tmp_path):
    """検査対象の一時 git リポジトリを作る。"""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _run(tmp_path, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


class TestJsonOutput:
    """--json 出力"""

    def test_json_is_parseable_when_clean(self, tmp_path):
        """検出 0 件でも stdout は JSON として読める"""
        repo = _init_repo(tmp_path)
        (repo / "sample.md").write_text("# sample\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.md"], cwd=repo, check=True)

        result = _run(repo, "--json")

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["blocked"] is False
        assert data["summary"]["total"] == 0
        assert data["findings"] == []

    def test_json_is_parseable_when_findings_exist(self, tmp_path):
        """検出ありでも stdout は JSON のみ（サマリ行が混ざらない）"""
        repo = _init_repo(tmp_path)
        (repo / "sample.md").write_text(
            f"SELECT * FROM {LEAK_TABLE};\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "sample.md"], cwd=repo, check=True)

        result = _run(repo, "--json")

        # 検出ありなのでブロック（rc=1）
        assert result.returncode == 1

        # ここが本来のバグ: サマリ行が stdout に追記されて Extra data で失敗していた
        data = json.loads(result.stdout)

        assert data["blocked"] is True
        assert data["summary"]["HIGH"] >= 1
        assert any(f["file"] == "sample.md" for f in data["findings"])

        # 人間向けサマリは stderr に出る
        assert "NG:" in result.stderr

    def test_text_output_keeps_summary_on_stdout(self, tmp_path):
        """通常出力ではサマリ行を stdout に出す（従来どおり）"""
        repo = _init_repo(tmp_path)
        (repo / "sample.md").write_text(
            f"SELECT * FROM {LEAK_TABLE};\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "sample.md"], cwd=repo, check=True)

        result = _run(repo)

        assert result.returncode == 1
        assert "NG:" in result.stdout


class TestExitCode:
    """終了コード"""

    def test_clean_repo_returns_zero(self, tmp_path):
        repo = _init_repo(tmp_path)
        (repo / "sample.md").write_text("# sample\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.md"], cwd=repo, check=True)

        assert _run(repo).returncode == 0
