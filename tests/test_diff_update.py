"""diff_update.py tests -- TDD: written before implementation."""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from diff_update import (
    MAPPING_RULES,
    get_changed_files,
    map_source_to_docs,
    aggregate_updates,
    build_update_plan,
    main,
)


# ---------------------------------------------------------------------------
# get_changed_files
# ---------------------------------------------------------------------------
class TestGetChangedFiles:
    """git diff --name-only の呼び出しとパース"""

    def _patch_isdir(self, monkeypatch):
        monkeypatch.setattr(os.path, "isdir", lambda p: True)

    def test_returns_list_of_changed_files(self, monkeypatch):
        self._patch_isdir(monkeypatch)
        fake_output = "app/Http/Controllers/API/BillingController.php\napp/Models/User.php\n"

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=fake_output)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = get_changed_files("/fake/source", "HEAD~1")
        assert result == [
            "app/Http/Controllers/API/BillingController.php",
            "app/Models/User.php",
        ]

    def test_returns_empty_list_when_no_changes(self, monkeypatch):
        self._patch_isdir(monkeypatch)
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = get_changed_files("/fake/source", "HEAD~1")
        assert result == []

    def test_uses_custom_base_ref(self, monkeypatch):
        self._patch_isdir(monkeypatch)
        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        get_changed_files("/fake/source", "main")
        assert "main" in captured_cmds[0]

    def test_strips_whitespace_from_filenames(self, monkeypatch):
        self._patch_isdir(monkeypatch)
        fake_output = "  file.php  \n  other.php  \n"

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=fake_output)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = get_changed_files("/fake/source", "HEAD~1")
        assert result == ["file.php", "other.php"]

    def test_raises_on_git_failure(self, monkeypatch):
        self._patch_isdir(monkeypatch)
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fatal: bad ref")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="git diff failed"):
            get_changed_files("/fake/source", "HEAD~1")


# ---------------------------------------------------------------------------
# map_source_to_docs
# ---------------------------------------------------------------------------
class TestMapSourceToDocs:
    """個別ソースファイル → 影響ドキュメントのマッピング"""

    def test_controller_maps_to_feature_and_api(self):
        docs = map_source_to_docs("app/Http/Controllers/API/BillingController.php")
        assert "features/billing.md" in docs
        assert "04-api-reference.md" in docs

    def test_model_maps_to_data_model(self):
        docs = map_source_to_docs("app/Models/User.php")
        assert "05-data-model.md" in docs

    def test_vue_page_maps_to_screen_specs_and_flow(self):
        docs = map_source_to_docs("pages/dashboard/index.vue")
        assert "06-screen-specs.md" in docs
        assert "02-screen-flow.md" in docs

    def test_store_maps_to_feature(self):
        docs = map_source_to_docs("store/billing.js")
        assert "features/billing.md" in docs

    def test_route_maps_to_api_and_flow(self):
        docs = map_source_to_docs("routes/api.php")
        assert "04-api-reference.md" in docs
        assert "02-screen-flow.md" in docs

    def test_config_maps_to_overview(self):
        docs = map_source_to_docs("config/app.php")
        assert "01-overview.md" in docs

    def test_json_config_maps_to_overview(self):
        docs = map_source_to_docs("package.json")
        assert "01-overview.md" in docs

    def test_unrelated_file_returns_empty(self):
        docs = map_source_to_docs("README.md")
        assert docs == []

    def test_unrelated_nested_file_returns_empty(self):
        docs = map_source_to_docs("docs/something.md")
        assert docs == []

    def test_controller_feature_name_extraction(self):
        """Controller名からfeature名が正しく抽出されること"""
        docs = map_source_to_docs(
            "app/Http/Controllers/API/DashUserSettingsController.php"
        )
        assert "features/dash-user-settings.md" in docs

    def test_store_feature_name_extraction(self):
        """Store名からfeature名が正しく抽出されること"""
        docs = map_source_to_docs("store/userSettings.js")
        assert "features/user-settings.md" in docs


# ---------------------------------------------------------------------------
# aggregate_updates
# ---------------------------------------------------------------------------
class TestAggregateUpdates:
    """複数ファイル変更の集約"""

    def test_multiple_files_aggregated(self):
        changed = [
            "app/Http/Controllers/API/BillingController.php",
            "app/Models/User.php",
        ]
        result = aggregate_updates(changed)
        # doc -> list of source_files の辞書
        assert "05-data-model.md" in result
        assert "features/billing.md" in result
        assert "app/Models/User.php" in result["05-data-model.md"]

    def test_same_doc_from_multiple_sources(self):
        """異なるソースが同じドキュメントに影響する場合、ソースが集約される"""
        changed = [
            "app/Http/Controllers/API/BillingController.php",
            "routes/api.php",
        ]
        result = aggregate_updates(changed)
        sources = result["04-api-reference.md"]
        assert "app/Http/Controllers/API/BillingController.php" in sources
        assert "routes/api.php" in sources

    def test_empty_changes_returns_empty(self):
        result = aggregate_updates([])
        assert result == {}

    def test_unrelated_files_only_returns_empty(self):
        result = aggregate_updates(["README.md", ".gitignore"])
        assert result == {}


# ---------------------------------------------------------------------------
# build_update_plan
# ---------------------------------------------------------------------------
class TestBuildUpdatePlan:
    """最終的なJSON出力構造の構築"""

    def test_output_structure(self):
        changed = ["app/Http/Controllers/API/BillingController.php"]
        plan = build_update_plan(changed)
        assert "needs_update" in plan
        assert isinstance(plan["needs_update"], list)
        assert len(plan["needs_update"]) > 0

        entry = plan["needs_update"][0]
        assert "doc" in entry
        assert "reason" in entry
        assert "source_files" in entry

    def test_reason_includes_source_filename(self):
        changed = ["app/Models/Invoice.php"]
        plan = build_update_plan(changed)
        reasons = [item["reason"] for item in plan["needs_update"]]
        assert any("Invoice.php" in r for r in reasons)

    def test_source_files_is_list(self):
        changed = ["config/app.php"]
        plan = build_update_plan(changed)
        for item in plan["needs_update"]:
            assert isinstance(item["source_files"], list)

    def test_no_changes_produces_empty_list(self):
        plan = build_update_plan([])
        assert plan == {"needs_update": []}

    def test_output_is_json_serializable(self):
        changed = [
            "app/Http/Controllers/API/BillingController.php",
            "app/Models/User.php",
            "pages/dashboard/index.vue",
        ]
        plan = build_update_plan(changed)
        serialized = json.dumps(plan)
        parsed = json.loads(serialized)
        assert parsed == plan


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------
class TestCLI:
    """コマンドラインインターフェース"""

    def _patch_isdir(self, monkeypatch):
        monkeypatch.setattr(os.path, "isdir", lambda p: True)

    def test_dry_run_outputs_json_to_stdout(self, monkeypatch, capsys):
        self._patch_isdir(monkeypatch)
        fake_output = "app/Models/User.php\n"

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=fake_output)

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "diff_update.py",
                "--source-dir",
                "/fake",
                "--docs-dir",
                "./docs",
                "--base",
                "HEAD~1",
                "--dry-run",
            ],
        )
        exit_code = main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "needs_update" in output
        assert exit_code == 0

    def test_default_base_is_head_tilde_1(self, monkeypatch, capsys):
        self._patch_isdir(monkeypatch)
        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diff_update.py", "--source-dir", "/fake", "--docs-dir", "./docs"],
        )
        main()
        assert any("HEAD~1" in c for c in captured_cmds[0])

    def test_custom_base_flag(self, monkeypatch, capsys):
        self._patch_isdir(monkeypatch)
        captured_cmds = []

        def fake_run(cmd, **kwargs):
            captured_cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "diff_update.py",
                "--source-dir",
                "/fake",
                "--docs-dir",
                "./docs",
                "--base",
                "main",
            ],
        )
        main()
        assert any("main" in c for c in captured_cmds[0])

    def test_no_changes_outputs_empty_plan(self, monkeypatch, capsys):
        self._patch_isdir(monkeypatch)
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diff_update.py", "--source-dir", "/fake", "--docs-dir", "./docs"],
        )
        main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == {"needs_update": []}

    def test_exit_code_nonzero_on_git_error(self, monkeypatch, capsys):
        self._patch_isdir(monkeypatch)
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diff_update.py", "--source-dir", "/fake", "--docs-dir", "./docs"],
        )
        exit_code = main()
        assert exit_code == 1


# ---------------------------------------------------------------------------
# MAPPING_RULES 構造検証
# ---------------------------------------------------------------------------
class TestMappingRules:
    """MAPPING_RULES定数の構造が正しいこと"""

    def test_all_rules_have_required_keys(self):
        for rule in MAPPING_RULES:
            assert "source_pattern" in rule
            assert "docs" in rule
            assert isinstance(rule["docs"], list)

    def test_at_least_seven_rules(self):
        assert len(MAPPING_RULES) >= 7
