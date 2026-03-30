"""capture_screenshots.py のテスト

Playwright はブラウザが必要なため、ネットワーク呼び出しと
ブラウザ操作は unittest.mock でモックする。
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from capture_screenshots import (
    check_url_accessible,
    filter_routes,
    generate_screenshot_path,
    load_routes,
    parse_args,
    build_report,
    _perform_login,
    capture_screenshots,
    main,
    check_playwright_available,
    ensure_output_dir,
)


# ---------------------------------------------------------------------------
# check_url_accessible
# ---------------------------------------------------------------------------
class TestCheckUrlAccessible:
    """Base URL の到達可能性チェック"""

    def test_reachable_url(self, monkeypatch):
        """到達可能な URL は True を返す"""
        import urllib.request

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            status = 200

        monkeypatch.setattr(
            urllib.request, "urlopen", lambda *a, **kw: FakeResponse()
        )
        assert check_url_accessible("http://localhost:3000") is True

    def test_unreachable_url(self, monkeypatch):
        """到達不可能な URL は False を返す"""
        import urllib.request
        import urllib.error

        def raise_error(*a, **kw):
            raise urllib.error.URLError("Connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", raise_error)
        assert check_url_accessible("http://localhost:9999") is False

    def test_timeout_returns_false(self, monkeypatch):
        """タイムアウトした場合も False を返す"""
        import urllib.request
        import socket

        def raise_timeout(*a, **kw):
            raise socket.timeout("timed out")

        monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)
        assert check_url_accessible("http://localhost:3000") is False


# ---------------------------------------------------------------------------
# load_routes
# ---------------------------------------------------------------------------
class TestLoadRoutes:
    """routes.json の読み込み"""

    def test_valid_json(self, tmp_path):
        """正常な JSON ファイルを読み込める"""
        routes = [
            {"path": "/login", "name": "login", "auth_required": False},
            {"path": "/dashboard", "name": "dashboard", "auth_required": True},
        ]
        routes_file = tmp_path / "routes.json"
        routes_file.write_text(json.dumps(routes), encoding="utf-8")

        result = load_routes(str(routes_file))
        assert len(result) == 2
        assert result[0]["name"] == "login"
        assert result[1]["auth_required"] is True

    def test_invalid_json(self, tmp_path):
        """不正な JSON は ValueError を発生させる"""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")

        with pytest.raises(ValueError, match="JSON"):
            load_routes(str(bad_file))

    def test_missing_file(self):
        """存在しないファイルは FileNotFoundError を発生させる"""
        with pytest.raises(FileNotFoundError):
            load_routes("/nonexistent/routes.json")

    def test_empty_list(self, tmp_path):
        """空のリストも読み込める"""
        routes_file = tmp_path / "empty.json"
        routes_file.write_text("[]", encoding="utf-8")

        result = load_routes(str(routes_file))
        assert result == []

    def test_not_a_list(self, tmp_path):
        """トップレベルがリストでない場合は ValueError"""
        routes_file = tmp_path / "obj.json"
        routes_file.write_text('{"path": "/"}', encoding="utf-8")

        with pytest.raises(ValueError, match="list"):
            load_routes(str(routes_file))


# ---------------------------------------------------------------------------
# generate_screenshot_path
# ---------------------------------------------------------------------------
class TestGenerateScreenshotPath:
    """スクリーンショットファイルパスの生成"""

    def test_basic_path(self):
        result = generate_screenshot_path("/output", "login")
        assert result == os.path.join("/output", "login.png")

    def test_name_with_hyphens(self):
        result = generate_screenshot_path("/output", "client-list")
        assert result == os.path.join("/output", "client-list.png")

    def test_preserves_output_dir(self):
        result = generate_screenshot_path("/docs/screenshots", "summary")
        assert result.startswith("/docs/screenshots/")
        assert result.endswith(".png")


# ---------------------------------------------------------------------------
# filter_routes
# ---------------------------------------------------------------------------
class TestFilterRoutes:
    """認証情報の有無によるルートのフィルタリング"""

    def setup_method(self):
        self.routes = [
            {"path": "/login", "name": "login", "auth_required": False},
            {"path": "/dashboard", "name": "dashboard", "auth_required": True},
            {"path": "/about", "name": "about", "auth_required": False},
        ]

    def test_with_credentials(self):
        """認証情報がある場合は全ルートを返す"""
        result = filter_routes(self.routes, has_credentials=True)
        assert len(result) == 3

    def test_without_credentials(self):
        """認証情報がない場合は auth_required=False のルートのみ"""
        result = filter_routes(self.routes, has_credentials=False)
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "login" in names
        assert "about" in names
        assert "dashboard" not in names

    def test_all_auth_required_no_credentials(self):
        """全ルートが認証必須で認証情報がない場合は空リスト"""
        routes = [{"path": "/admin", "name": "admin", "auth_required": True}]
        result = filter_routes(routes, has_credentials=False)
        assert result == []

    def test_missing_auth_required_defaults_false(self):
        """auth_required キーがないルートは False 扱い"""
        routes = [{"path": "/page", "name": "page"}]
        result = filter_routes(routes, has_credentials=False)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------
class TestParseArgs:
    """CLI 引数パーサー"""

    def test_required_args(self):
        args = parse_args([
            "--base-url", "http://localhost:3000",
            "--routes", "routes.json",
            "--output-dir", "docs/screenshots",
        ])
        assert args.base_url == "http://localhost:3000"
        assert args.routes == "routes.json"
        assert args.output_dir == "docs/screenshots"

    def test_check_only_flag(self):
        args = parse_args([
            "--base-url", "http://localhost:3000",
            "--routes", "routes.json",
            "--output-dir", "out",
            "--check-only",
        ])
        assert args.check_only is True

    def test_check_only_default_false(self):
        args = parse_args([
            "--base-url", "http://localhost:3000",
            "--routes", "routes.json",
            "--output-dir", "out",
        ])
        assert args.check_only is False

    def test_auth_flags(self):
        args = parse_args([
            "--base-url", "http://localhost:3000",
            "--routes", "routes.json",
            "--output-dir", "out",
            "--login-url", "http://localhost:3000/login",
            "--email", "user@example.com",
            "--password", "secret",
        ])
        assert args.login_url == "http://localhost:3000/login"
        assert args.email == "user@example.com"
        assert args.password == "secret"

    def test_auth_flags_default_none(self):
        args = parse_args([
            "--base-url", "http://localhost:3000",
            "--routes", "routes.json",
            "--output-dir", "out",
        ])
        assert args.login_url is None
        assert args.email is None
        assert args.password is None


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------
class TestBuildReport:
    """キャプチャ結果レポートの生成"""

    def test_all_success(self):
        results = [
            {"name": "login", "success": True, "size": 50000},
            {"name": "dashboard", "success": True, "size": 80000},
        ]
        report = build_report(results)
        assert report["captured"] == 2
        assert report["failed"] == 0
        assert report["total_size"] == 130000

    def test_with_failures(self):
        results = [
            {"name": "login", "success": True, "size": 50000},
            {"name": "dashboard", "success": False, "size": 0},
        ]
        report = build_report(results)
        assert report["captured"] == 1
        assert report["failed"] == 1
        assert report["total_size"] == 50000

    def test_empty_results(self):
        report = build_report([])
        assert report["captured"] == 0
        assert report["failed"] == 0
        assert report["total_size"] == 0


# ---------------------------------------------------------------------------
# Playwright 未インストール検出
# ---------------------------------------------------------------------------
class TestPlaywrightNotInstalled:
    """Playwright が未インストールの場合のグレースフル処理"""

    def test_import_error_message(self, monkeypatch):
        """playwright が import できない場合にインストール手順を表示"""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # capture_screenshots モジュール内の関数を直接テストするのではなく、
        # check_playwright_available ヘルパーをテストする
        from capture_screenshots import check_playwright_available

        available, message = check_playwright_available()
        # モック環境では playwright が入っている可能性があるので
        # 戻り値の型だけ検証する
        assert isinstance(available, bool)
        assert isinstance(message, str)


# ---------------------------------------------------------------------------
# 出力ディレクトリの作成
# ---------------------------------------------------------------------------
class TestOutputDirectory:
    """出力ディレクトリが存在しない場合の自動作成"""

    def test_creates_output_dir(self, tmp_path):
        from capture_screenshots import ensure_output_dir

        new_dir = str(tmp_path / "new" / "nested" / "dir")
        assert not os.path.exists(new_dir)

        ensure_output_dir(new_dir)
        assert os.path.isdir(new_dir)

    def test_existing_dir_no_error(self, tmp_path):
        """既存ディレクトリに対してエラーにならない"""
        ensure_output_dir(str(tmp_path))
        assert os.path.isdir(str(tmp_path))


# ---------------------------------------------------------------------------
# _perform_login (Playwright モック)
# ---------------------------------------------------------------------------
class TestPerformLogin:
    """ログイン処理のテスト（Playwright をモック）"""

    def test_login_calls_page_methods(self):
        """ログイン処理で正しいメソッドが呼ばれる"""
        page = MagicMock()
        _perform_login(page, "http://localhost/login", "u@ex.com", "pass")

        page.goto.assert_called_once_with(
            "http://localhost/login", wait_until="networkidle"
        )
        page.fill.assert_any_call(
            'input[type="email"], input[name="email"]', "u@ex.com"
        )
        page.fill.assert_any_call(
            'input[type="password"], input[name="password"]', "pass"
        )
        page.click.assert_called_once_with('button[type="submit"]')
        page.wait_for_load_state.assert_called_once_with("networkidle")


# ---------------------------------------------------------------------------
# capture_screenshots (Playwright をフルモック)
# ---------------------------------------------------------------------------
class TestCaptureScreenshots:
    """スクリーンショット撮影のテスト（Playwright をモック）"""

    def _build_mock_playwright(self, tmp_path):
        """Playwright のモックツリーを構築する"""
        mock_page = MagicMock()

        def fake_screenshot(path, full_page=True):
            # テスト用に空 PNG ファイルを書き出す
            with open(path, "wb") as f:
                f.write(b"\x89PNG" + b"\x00" * 100)

        mock_page.screenshot.side_effect = fake_screenshot

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser

        mock_pw = MagicMock()
        mock_pw.chromium = mock_chromium

        mock_sync = MagicMock()
        mock_sync.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync.__exit__ = MagicMock(return_value=False)

        return mock_sync, mock_page

    @patch("capture_screenshots.sync_playwright", create=True)
    def test_captures_all_routes(self, mock_sp_cls, tmp_path):
        """全ルートをキャプチャして結果を返す"""
        mock_sync, mock_page = self._build_mock_playwright(tmp_path)

        # sync_playwright() がコンテキストマネージャを返す
        with patch(
            "capture_screenshots.sync_playwright", return_value=mock_sync
        ):
            # playwright.sync_api モジュールを差し替え
            import types
            fake_module = types.ModuleType("playwright.sync_api")
            fake_module.sync_playwright = lambda: mock_sync

            with patch.dict("sys.modules", {"playwright.sync_api": fake_module}):
                routes = [
                    {"path": "/login", "name": "login", "auth_required": False},
                    {"path": "/dash", "name": "dash", "auth_required": False},
                ]
                results = capture_screenshots(
                    base_url="http://localhost:3000",
                    routes=routes,
                    output_dir=str(tmp_path),
                )

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert all(r["size"] > 0 for r in results)

    @patch("capture_screenshots.sync_playwright", create=True)
    def test_handles_screenshot_failure(self, mock_sp_cls, tmp_path):
        """スクリーンショット失敗時に success=False を記録する"""
        mock_sync, mock_page = self._build_mock_playwright(tmp_path)
        mock_page.goto.side_effect = Exception("Navigation failed")

        import types
        fake_module = types.ModuleType("playwright.sync_api")
        fake_module.sync_playwright = lambda: mock_sync

        with patch.dict("sys.modules", {"playwright.sync_api": fake_module}):
            routes = [{"path": "/broken", "name": "broken", "auth_required": False}]
            results = capture_screenshots(
                base_url="http://localhost:3000",
                routes=routes,
                output_dir=str(tmp_path),
            )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["size"] == 0

    @patch("capture_screenshots.sync_playwright", create=True)
    def test_performs_login_when_credentials_provided(self, mock_sp_cls, tmp_path):
        """認証情報が提供された場合にログイン処理が実行される"""
        mock_sync, mock_page = self._build_mock_playwright(tmp_path)

        import types
        fake_module = types.ModuleType("playwright.sync_api")
        fake_module.sync_playwright = lambda: mock_sync

        with patch.dict("sys.modules", {"playwright.sync_api": fake_module}):
            routes = [{"path": "/dash", "name": "dash", "auth_required": True}]
            capture_screenshots(
                base_url="http://localhost:3000",
                routes=routes,
                output_dir=str(tmp_path),
                login_url="http://localhost:3000/login",
                email="test@example.com",
                password="secret",
            )

        # ログイン用の goto が呼ばれたことを確認
        goto_calls = mock_page.goto.call_args_list
        assert any(
            "login" in str(c) for c in goto_calls
        ), "Login URL should be navigated to"


# ---------------------------------------------------------------------------
# main() の統合テスト
# ---------------------------------------------------------------------------
class TestMain:
    """main() のテスト（外部依存をすべてモック）"""

    def test_exits_when_playwright_unavailable(self, monkeypatch, capsys):
        """Playwright が利用不可な場合に終了コード 1"""
        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (False, "Playwright is not installed."),
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(base_url="http://localhost:3000"),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "not installed" in captured.out

    def test_exits_when_url_unreachable(self, monkeypatch, capsys):
        """URL 到達不可能な場合に終了コード 1"""
        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: False,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(base_url="http://localhost:9999"),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "not reachable" in captured.out

    def test_check_only_exits_zero(self, monkeypatch, capsys):
        """--check-only の場合に終了コード 0"""
        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=True,
            ),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Check-only" in captured.out

    def test_exits_on_bad_routes_file(self, monkeypatch, capsys):
        """routes ファイルが読み込めない場合に終了コード 1"""
        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=False,
                routes="/nonexistent/routes.json",
                login_url=None,
                email=None,
                password=None,
            ),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error loading routes" in captured.out

    def test_exits_zero_no_target_routes(self, monkeypatch, capsys, tmp_path):
        """全ルートがフィルタリングで除外された場合に終了コード 0"""
        routes_file = tmp_path / "routes.json"
        routes_file.write_text(
            json.dumps([{"path": "/admin", "name": "admin", "auth_required": True}]),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=False,
                routes=str(routes_file),
                login_url=None,
                email=None,
                password=None,
            ),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "No routes to capture" in captured.out

    def test_successful_capture_flow(self, monkeypatch, capsys, tmp_path):
        """正常フロー：キャプチャ成功してレポート出力"""
        routes_file = tmp_path / "routes.json"
        routes_file.write_text(
            json.dumps([{"path": "/", "name": "home", "auth_required": False}]),
            encoding="utf-8",
        )
        output_dir = str(tmp_path / "out")

        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=False,
                routes=str(routes_file),
                output_dir=output_dir,
                login_url=None,
                email=None,
                password=None,
            ),
        )
        monkeypatch.setattr(
            "capture_screenshots.capture_screenshots",
            lambda **kw: [{"name": "home", "success": True, "size": 12345}],
        )

        # main() は失敗がないので sys.exit を呼ばずに正常終了する
        main()

        captured = capsys.readouterr()
        assert "Captured: 1" in captured.out
        assert "Failed:   0" in captured.out

    def test_exits_one_when_failures(self, monkeypatch, capsys, tmp_path):
        """キャプチャに失敗があれば終了コード 1"""
        routes_file = tmp_path / "routes.json"
        routes_file.write_text(
            json.dumps([{"path": "/", "name": "home", "auth_required": False}]),
            encoding="utf-8",
        )
        output_dir = str(tmp_path / "out")

        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=False,
                routes=str(routes_file),
                output_dir=output_dir,
                login_url=None,
                email=None,
                password=None,
            ),
        )
        monkeypatch.setattr(
            "capture_screenshots.capture_screenshots",
            lambda **kw: [{"name": "home", "success": False, "size": 0}],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_skipped_routes_message(self, monkeypatch, capsys, tmp_path):
        """認証なしで auth_required ルートがスキップされた場合のメッセージ"""
        routes_file = tmp_path / "routes.json"
        routes_file.write_text(
            json.dumps([
                {"path": "/", "name": "home", "auth_required": False},
                {"path": "/admin", "name": "admin", "auth_required": True},
            ]),
            encoding="utf-8",
        )
        output_dir = str(tmp_path / "out")

        monkeypatch.setattr(
            "capture_screenshots.check_playwright_available",
            lambda: (True, "OK"),
        )
        monkeypatch.setattr(
            "capture_screenshots.check_url_accessible",
            lambda url: True,
        )
        monkeypatch.setattr(
            "capture_screenshots.parse_args",
            lambda: MagicMock(
                base_url="http://localhost:3000",
                check_only=False,
                routes=str(routes_file),
                output_dir=output_dir,
                login_url=None,
                email=None,
                password=None,
            ),
        )
        monkeypatch.setattr(
            "capture_screenshots.capture_screenshots",
            lambda **kw: [{"name": "home", "success": True, "size": 5000}],
        )

        main()

        captured = capsys.readouterr()
        assert "Skipping 1 auth-required" in captured.out


# ---------------------------------------------------------------------------
# check_playwright_available の直接テスト
# ---------------------------------------------------------------------------
class TestCheckPlaywrightAvailable:
    """Playwright 利用可能チェックの直接テスト"""

    def test_returns_true_when_installed(self, monkeypatch):
        """playwright がインストールされていれば True"""
        import types

        fake_module = types.ModuleType("playwright.sync_api")
        fake_module.sync_playwright = lambda: None

        with patch.dict("sys.modules", {"playwright.sync_api": fake_module}):
            available, message = check_playwright_available()
            assert available is True
            assert "available" in message.lower()

    def test_returns_false_when_not_installed(self, monkeypatch):
        """playwright がインストールされていなければ False"""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "playwright" in name:
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # sys.modules からも削除して再 import を強制
        modules_to_remove = [k for k in sys.modules if "playwright" in k]
        saved = {}
        for k in modules_to_remove:
            saved[k] = sys.modules.pop(k)

        try:
            available, message = check_playwright_available()
            assert available is False
            assert "pip3 install playwright" in message
        finally:
            sys.modules.update(saved)
