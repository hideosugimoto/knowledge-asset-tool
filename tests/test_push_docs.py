"""push_docs.py のテスト

重点は remote URL のホスト判定。ホスト名を部分一致で見ていると
notgithub.com のような別ホストが github.com のリポジトリの可視性で
判定され、可視性チェックが fail open する。
同じ判定ロジックが scripts/deploy_pages.sh と .githooks/pre-push にも
複製されているため、3 実装が一致することも検証する。
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from push_docs import (  # noqa: E402
    is_valid_project_name,
    parse_remote_url,
    project_paths,
    resolve_owner_repo,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (URL, 期待する owner/repo または None)
URL_CASES = [
    # 正常系
    ("https://github.com/owner/repo.git", "owner/repo"),
    ("https://github.com/owner/repo", "owner/repo"),
    ("http://github.com/owner/repo", "owner/repo"),
    ("git@github.com:owner/repo.git", "owner/repo"),
    ("git@github.com:owner/repo", "owner/repo"),
    ("ssh://git@github.com/owner/repo.git", "owner/repo"),
    ("https://github.com/owner/repo/", "owner/repo"),
    ("https://GitHub.com/owner/repo.git", "owner/repo"),
    # ホストが github.com ではない → 判定不能
    ("https://notgithub.com/attacker/repo.git", None),
    ("https://evil.example.com/github.com/attacker/repo", None),
    ("git@my-github.com:attacker/repo.git", None),
    ("https://github.com.attacker.net/x/y", None),
    ("https://gitlab.com/owner/repo.git", None),
    ("https://github.company.com/owner/repo.git", None),
    # 形が owner/repo でない → 判定不能
    ("https://github.com/owner", None),
    ("https://github.com/owner/repo/extra", None),
    ("https://github.com/", None),
    ("/local/path/repo", None),
    ("", None),
]


class TestResolveOwnerRepo:
    """Python 実装のホスト判定"""

    @pytest.mark.parametrize("url,expected", URL_CASES)
    def test_resolves(self, url, expected):
        assert resolve_owner_repo(url) == expected

    def test_lookalike_host_does_not_resolve(self):
        """github.com を部分文字列として含むホストは解決しない

        これを許すと gh repo view が github.com 側のリポジトリを見にいき、
        別ホストへの push が「PRIVATE だから OK」と誤判定される。
        """
        for url in (
            "https://notgithub.com/acme/docs.git",
            "https://evil.example.com/github.com/acme/docs",
            "git@fake-github.com:acme/docs.git",
        ):
            assert resolve_owner_repo(url) is None

    def test_parse_remote_url_strips_user_and_port(self):
        host, path = parse_remote_url("ssh://git@github.com:22/owner/repo.git")
        assert host == "github.com"
        assert path == "/owner/repo.git"


class TestBashImplementationsAgree:
    """bash 側の複製実装が Python 実装と一致すること"""

    SCRIPTS = ["scripts/deploy_pages.sh", ".githooks/pre-push"]

    @staticmethod
    def _run_bash_resolver(script_path, url):
        """スクリプトから resolve_owner_repo を抜き出して実行する。"""
        full = os.path.join(REPO_ROOT, script_path)
        extract = subprocess.run(
            ["awk", "/^resolve_owner_repo\\(\\) \\{/,/^\\}/", full],
            capture_output=True, text=True, check=True,
        )
        assert extract.stdout.strip(), f"{script_path} に関数が見つからない"
        program = extract.stdout + '\nresolve_owner_repo "$1"\n'
        result = subprocess.run(
            ["bash", "-c", program, "bash", url],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    @pytest.mark.parametrize("script", SCRIPTS)
    @pytest.mark.parametrize("url,expected", URL_CASES)
    def test_matches_python(self, script, url, expected):
        got = self._run_bash_resolver(script, url)
        assert got == (expected or "")


class TestProjectNameValidation:
    """--project の入力検証"""

    @pytest.mark.parametrize("name", ["my-app", "app_1", "a.b.c", "App2"])
    def test_valid_names(self, name):
        assert is_valid_project_name(name) is True

    @pytest.mark.parametrize(
        "name",
        ["*", "?", "a*", "[ab]", "../etc", "a/b", "", "-leading", ".hidden", "a b"],
    )
    def test_invalid_names(self, name):
        assert is_valid_project_name(name) is False

    def test_glob_does_not_widen_targets(self, tmp_path):
        """グロブ文字を渡しても対象が広がらない

        以前は docs/slides/*-* にマッチして全プロジェクトの
        スライドを巻き込んでいた。
        """
        docs = tmp_path / "docs"
        slides = docs / "slides"
        slides.mkdir(parents=True)
        (docs / "alpha-index.md").write_text("# alpha", encoding="utf-8")
        (docs / "beta-index.md").write_text("# beta", encoding="utf-8")
        (slides / "alpha-engineer.html").write_text("a", encoding="utf-8")
        (slides / "beta-engineer.html").write_text("b", encoding="utf-8")

        assert project_paths(tmp_path, "alpha") == [
            "docs/alpha-index.md",
            "docs/slides/alpha-engineer.html",
        ]
        assert project_paths(tmp_path, "*") == []
        assert project_paths(tmp_path, "../../tmp") == []


class TestCommitTargets:
    """コミットが対象パスに限定されること"""

    @staticmethod
    def _init_repo(tmp_path):
        run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True,
                                        capture_output=True, text=True)
        run("git", "init", "-q", "-b", "main")
        run("git", "config", "user.email", "t@example.com")
        run("git", "config", "user.name", "t")
        (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
        run("git", "add", "base.txt")
        run("git", "commit", "-qm", "init")
        return run

    def test_does_not_include_unrelated_staged_files(self, tmp_path, monkeypatch):
        """事前に staged だった無関係な変更を巻き込まない"""
        run = self._init_repo(tmp_path)
        (tmp_path / "unrelated.txt").write_text("x\n", encoding="utf-8")
        run("git", "add", "unrelated.txt")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# a\n", encoding="utf-8")
        run("git", "add", "-f", "docs/a.md")

        monkeypatch.chdir(tmp_path)
        from push_docs import commit_targets
        assert commit_targets(["docs/"], "docs: update") is True

        committed = subprocess.run(
            ["git", "show", "--name-only", "--format="],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        ).stdout.split()
        assert committed == ["docs/a.md"]

        still_staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        ).stdout.split()
        assert still_staged == ["unrelated.txt"]

    def test_skips_when_nothing_staged(self, tmp_path, monkeypatch):
        """対象に staged な変更が無ければコミットせず True を返す

        判定は git のメッセージ文字列ではなく終了コードで行うため、
        ロケールに依存しない。
        """
        self._init_repo(tmp_path)
        (tmp_path / "docs").mkdir()

        monkeypatch.chdir(tmp_path)
        from push_docs import commit_targets, has_staged_changes
        assert has_staged_changes(["docs/"]) is False
        assert commit_targets(["docs/"], "docs: update") is True

        count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert count == "1"
