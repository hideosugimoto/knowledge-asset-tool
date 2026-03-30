#!/usr/bin/env python3
"""
capture_screenshots.py - ローカル開発サーバーのスクリーンショットをキャプチャする

ユーザーガイドや画面仕様書に埋め込むスクリーンショットを Playwright で撮影する。
ローカル開発サーバーが起動している場合にのみ使用可能。

前提条件:
  pip3 install playwright
  playwright install chromium

使い方:
  python3 scripts/capture_screenshots.py \\
      --base-url http://localhost:3000 \\
      --routes routes.json \\
      --output-dir docs/screenshots

  # 画面遷移図から自動検出（--pages auto）
  python3 scripts/capture_screenshots.py \\
      --base-url http://localhost:3000 \\
      --output-dir docs/screenshots/myapp \\
      --pages auto \\
      --name myapp

  # 到達可能性チェックのみ
  python3 scripts/capture_screenshots.py \\
      --base-url http://localhost:3000 \\
      --routes routes.json \\
      --output-dir docs/screenshots \\
      --check-only

  # 認証付き
  python3 scripts/capture_screenshots.py \\
      --base-url http://localhost:3000 \\
      --routes routes.json \\
      --output-dir docs/screenshots \\
      --login-url http://localhost:3000/login \\
      --email user@example.com \\
      --password secret

注意:
  - このスクリプトは /go パイプラインでは自動実行されません。
  - 手動で明示的に実行してください。

routes.json の形式:
  [
    {"path": "/login", "name": "login", "auth_required": false},
    {"path": "/dashboard", "name": "dashboard", "auth_required": true},
    {"path": "/users/list", "name": "user-list", "auth_required": true}
  ]
"""

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# Playwright 利用可能チェック
# ---------------------------------------------------------------------------

def check_playwright_available():
    """Playwright が利用可能かどうかを確認する。

    Returns:
        tuple[bool, str]: (利用可能かどうか, メッセージ)
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, "Playwright is available."
    except ImportError:
        message = (
            "Playwright is not installed.\n"
            "Install with:\n"
            "  pip3 install playwright\n"
            "  playwright install chromium"
        )
        return False, message


# ---------------------------------------------------------------------------
# URL 到達可能性チェック
# ---------------------------------------------------------------------------

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}


def validate_base_url(url):
    """URL のスキームとホストを検証する。不正な場合は ValueError を送出。"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"許可されていないスキーム: {parsed.scheme} (http/https のみ)")
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError(f"ブロック対象のホスト: {parsed.hostname}")
    return url


def check_url_accessible(url, timeout=5):
    """指定 URL が到達可能かどうかを確認する。

    Args:
        url: チェック対象の URL
        timeout: タイムアウト秒数

    Returns:
        bool: 到達可能なら True
    """
    try:
        validate_base_url(url)
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except (urllib.error.URLError, socket.timeout, OSError, ValueError):
        return False


# ---------------------------------------------------------------------------
# ルート読み込み
# ---------------------------------------------------------------------------

def load_routes(file_path):
    """routes.json を読み込む。

    Args:
        file_path: JSON ファイルパス

    Returns:
        list[dict]: ルート定義のリスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: JSON パースに失敗した場合、またはトップレベルがリストでない場合
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}")

    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON list in {file_path}, got {type(data).__name__}"
        )

    return data


# ---------------------------------------------------------------------------
# スクリーンショットパス生成
# ---------------------------------------------------------------------------

def generate_screenshot_path(output_dir, name):
    """スクリーンショットの保存パスを生成する（パストラバーサル防止付き）。

    Args:
        output_dir: 出力ディレクトリ
        name: スクリーンショット名（拡張子なし）

    Returns:
        str: フルパス（{output_dir}/{safe_name}.png）

    Raises:
        ValueError: name にパストラバーサルが含まれる場合
    """
    safe_name = os.path.basename(name)
    if not safe_name or safe_name.startswith('.'):
        raise ValueError(f"不正なスクリーンショット名: '{name}'")
    full_path = os.path.normpath(os.path.join(output_dir, f"{safe_name}.png"))
    if not full_path.startswith(os.path.normpath(output_dir)):
        raise ValueError(f"パストラバーサル検出: '{name}'")
    return full_path


# ---------------------------------------------------------------------------
# ルートフィルタリング
# ---------------------------------------------------------------------------

def filter_routes(routes, has_credentials):
    """認証情報の有無に応じてルートをフィルタリングする。

    Args:
        routes: ルート定義のリスト
        has_credentials: 認証情報が提供されているかどうか

    Returns:
        list[dict]: フィルタリング済みルートのリスト
    """
    if has_credentials:
        return list(routes)

    return [r for r in routes if not r.get("auth_required", False)]


def filter_disabled_module_routes(routes, name, docs_dir="./docs"):
    """disabled_modules に属するルートを除外する。

    .cache/facts-{name}.yaml の disabled_modules からモジュール名を取得し、
    ルート名やパスに含まれるものを除外する。

    Args:
        routes: ルート定義のリスト
        name: プロジェクト名
        docs_dir: ドキュメントディレクトリ（.cache の親）

    Returns:
        list[dict]: disabled modules のルートを除外したリスト
    """
    if not name:
        return list(routes)

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(docs_dir)), ".cache")
    facts_path = os.path.join(cache_dir, f"facts-{name}.yaml")
    if not os.path.isfile(facts_path):
        return list(routes)

    try:
        import yaml
        with open(facts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {facts_path}: {e}")
        return list(routes)

    if not isinstance(data, dict):
        return list(routes)

    facts = data.get("facts", data)
    disabled = facts.get("disabled_modules", [])
    if not disabled:
        return list(routes)

    disabled_names = {
        m.get("name", "").lower()
        for m in disabled
        if isinstance(m, dict) and m.get("name")
    }

    filtered = []
    for route in routes:
        route_name = route.get("name", "").lower()
        route_path_segments = set(route.get("path", "").lower().strip("/").split("/"))
        if any(
            d == route_name or d in route_path_segments
            for d in disabled_names
        ):
            continue
        filtered.append(route)

    if len(filtered) < len(routes):
        excluded = len(routes) - len(filtered)
        print(f"[INFO] disabled_modules により {excluded} ルートを除外")

    return filtered


# ---------------------------------------------------------------------------
# 出力ディレクトリ作成
# ---------------------------------------------------------------------------

def ensure_output_dir(output_dir):
    """出力ディレクトリを作成する（存在しない場合）。

    Args:
        output_dir: 作成するディレクトリパス
    """
    os.makedirs(output_dir, exist_ok=True)


# ---------------------------------------------------------------------------
# レポート生成
# ---------------------------------------------------------------------------

def build_report(results):
    """キャプチャ結果からレポートを生成する。

    Args:
        results: キャプチャ結果のリスト。各要素は
                 {"name": str, "success": bool, "size": int}

    Returns:
        dict: {"captured": int, "failed": int, "total_size": int}
    """
    captured = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    total_size = sum(r["size"] for r in results if r["success"])

    return {
        "captured": captured,
        "failed": failed,
        "total_size": total_size,
    }


# ---------------------------------------------------------------------------
# --pages auto: 画面遷移図からルートを自動検出
# ---------------------------------------------------------------------------

def extract_routes_from_screen_flow(screen_flow_path):
    """02-screen-flow.md からページパスを抽出してルート定義を生成する。

    Mermaid graph 内のノード定義からパスを抽出する。
    例: `login["/login<br>ログイン画面"]` -> {"path": "/login", "name": "login"}
        `dashboard["/dashboard/summary"]` -> {"path": "/dashboard/summary", "name": "dashboard-summary"}

    Args:
        screen_flow_path: 02-screen-flow.md のファイルパス

    Returns:
        list[dict]: ルート定義のリスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
    """
    with open(screen_flow_path, "r", encoding="utf-8") as f:
        content = f.read()

    routes = []
    seen_paths = set()

    # Mermaid ノード定義からパスを抽出
    # パターン例:
    #   nodeId["パス名"] or nodeId["/path<br>説明"]
    #   nodeId["/path"] or nodeId("/path")
    path_patterns = [
        # ["パス<br>説明"] or ["/path<br>description"]
        r'\w+\["(/[^"<\]]*)',
        # ["/path"] 完全一致
        r'\w+\["(/[^"]+)"?\]',
        # ("/path") 丸括弧形式
        r'\w+\("(/[^"<\)]*)',
        # Markdown リンクやインラインコードからもパスを拾う
        r'`(/[a-zA-Z0-9/_-]+)`',
    ]

    for pattern in path_patterns:
        for match in re.finditer(pattern, content):
            path = match.group(1).strip()
            # パスの基本バリデーション
            if not path or path in seen_paths:
                continue
            if not path.startswith("/"):
                continue
            # Mermaid 制御構文や CSS は除外
            if any(kw in path for kw in ["style ", "class ", "click ", ":::"]):
                continue
            seen_paths.add(path)
            # パスから名前を生成（先頭スラッシュ除去、/ を - に変換）
            name = path.strip("/").replace("/", "-") or "root"
            routes.append({
                "path": path,
                "name": name,
                "auth_required": False,
            })

    return routes


# ---------------------------------------------------------------------------
# CLI 引数パーサー
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    """コマンドライン引数をパースする。

    Args:
        argv: 引数リスト（None の場合は sys.argv[1:]）

    Returns:
        argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Capture screenshots of a running web application using Playwright.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Requirements:\n"
            "  pip3 install playwright\n"
            "  playwright install chromium\n"
            "\n"
            "This script should ONLY be run when explicitly invoked.\n"
            "It is NOT auto-run in the /go pipeline."
        ),
    )
    parser.add_argument(
        "--base-url",
        "--url",
        required=True,
        help="Base URL of the running web application (e.g., http://localhost:3000)",
    )
    parser.add_argument(
        "--routes",
        required=False,
        default=None,
        help="Path to routes.json file (not required when --pages auto is used)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to save screenshots",
    )
    parser.add_argument(
        "--pages",
        choices=["auto"],
        default=None,
        help="Page discovery mode: 'auto' reads 02-screen-flow.md to extract page paths",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Project name (required for --pages auto, maps to docs/manual/{name}/02-screen-flow.md)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help="Only check if the base URL is accessible, don't capture",
    )
    parser.add_argument(
        "--login-url",
        default=None,
        help="Login page URL for authentication",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Email for authentication",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for authentication",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# スクリーンショット撮影（Playwright）
# ---------------------------------------------------------------------------

def _detect_username_field(page):
    """ログインフォームのユーザー名/メールフィールドを自動検出する。

    フレームワークごとに異なるフィールド名に対応するため、
    複数のセレクタを優先順に試行する。

    Args:
        page: Playwright Page オブジェクト

    Returns:
        Locator: 検出されたフィールドの Locator（見つからない場合は None）
    """
    # 優先順にセレクタを試行（一般的なフレームワークのパターンを網羅）
    selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="username"]',
        'input[name="user"]',
        'input[name="login"]',
        'input[name="login_id"]',
        'input[name="user_id"]',
        'input[name="account"]',
        'input[id="email"]',
        'input[id="username"]',
        'input[id="login"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
        # テキスト入力フィールドのフォールバック（パスワード以外の最初の入力）
        'input[type="text"]',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0 and locator.first.is_visible():
            return locator.first
    return None


def _detect_submit_button(page):
    """ログインフォームの送信ボタンを自動検出する。

    Args:
        page: Playwright Page オブジェクト

    Returns:
        Locator: 検出されたボタンの Locator（見つからない場合は None）
    """
    selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("ログイン")',
        'button:has-text("Login")',
        'button:has-text("Sign in")',
        'button:has-text("サインイン")',
        'a:has-text("ログイン")',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0 and locator.first.is_visible():
            return locator.first
    return None


def _perform_login(page, login_url, email, password):
    """ログイン処理を行う。

    ログインフォームのフィールドを自動検出し、フレームワークごとに
    異なる入力フィールド名（email, username, login_id 等）に対応する。

    Args:
        page: Playwright Page オブジェクト
        login_url: ログインページの URL
        email: メールアドレスまたはユーザー名
        password: パスワード

    Raises:
        RuntimeError: ログインフォームのフィールドが検出できない場合
    """
    page.goto(login_url, wait_until="networkidle")

    # ユーザー名/メールフィールドの自動検出
    username_field = _detect_username_field(page)
    if username_field is None:
        raise RuntimeError(
            f"ログインフォームのユーザー名フィールドが検出できません: {login_url}"
        )
    username_field.fill(email)

    # パスワードフィールド（type="password" は共通）
    password_locator = page.locator('input[type="password"]')
    if password_locator.count() == 0:
        raise RuntimeError(
            f"ログインフォームのパスワードフィールドが検出できません: {login_url}"
        )
    password_locator.first.fill(password)

    # 送信ボタンの自動検出
    submit_button = _detect_submit_button(page)
    if submit_button is None:
        raise RuntimeError(
            f"ログインフォームの送信ボタンが検出できません: {login_url}"
        )
    submit_button.click()

    page.wait_for_load_state("networkidle")


def capture_screenshots(base_url, routes, output_dir, login_url=None,
                        email=None, password=None):
    """全ルートのスクリーンショットを撮影する。

    Args:
        base_url: ベース URL
        routes: ルート定義のリスト
        output_dir: 出力ディレクトリ
        login_url: ログイン URL（認証が必要な場合）
        email: メールアドレス（認証が必要な場合）
        password: パスワード（認証が必要な場合）

    Returns:
        list[dict]: 各ルートの結果リスト
    """
    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        # 認証が必要な場合はログイン
        if login_url and email and password:
            try:
                _perform_login(page, login_url, email, password)
                print(f"  [OK] Logged in via {login_url}")
            except Exception as e:
                print(f"  [FAIL] Login failed: {e}")

        for route in routes:
            name = route["name"]
            path = route["path"]
            url = f"{base_url.rstrip('/')}{path}"
            screenshot_path = generate_screenshot_path(output_dir, name)

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.screenshot(path=screenshot_path, full_page=True)
                file_size = os.path.getsize(screenshot_path)
                results.append({
                    "name": name,
                    "success": True,
                    "size": file_size,
                })
                print(f"  [OK] {name} -> {screenshot_path} ({file_size:,} bytes)")
            except Exception as e:
                results.append({
                    "name": name,
                    "success": False,
                    "size": 0,
                })
                print(f"  [FAIL] {name}: {e}")

        browser.close()

    return results


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Playwright チェック
    available, message = check_playwright_available()
    if not available:
        print(message)
        sys.exit(1)

    # URL 到達可能性チェック
    print(f"Checking {args.base_url} ...")
    if not check_url_accessible(args.base_url):
        print(f"Error: {args.base_url} is not reachable.")
        print("Make sure the development server is running.")
        sys.exit(1)

    print(f"  [OK] {args.base_url} is accessible.")

    if args.check_only:
        print("Check-only mode: exiting.")
        sys.exit(0)

    # ルート読み込み（--pages auto または --routes から）
    if args.pages == "auto":
        if not args.name:
            print("Error: --name is required when using --pages auto")
            sys.exit(1)
        screen_flow_path = os.path.join(
            "docs", "manual", args.name, "02-screen-flow.md"
        )
        if not os.path.isfile(screen_flow_path):
            print(f"Error: Screen flow file not found: {screen_flow_path}")
            sys.exit(1)
        try:
            routes = extract_routes_from_screen_flow(screen_flow_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error extracting routes from screen flow: {e}")
            sys.exit(1)
        if not routes:
            print(f"Warning: No page paths found in {screen_flow_path}")
            sys.exit(0)
        print(f"  Auto-detected {len(routes)} page(s) from {screen_flow_path}")
    elif args.routes:
        try:
            routes = load_routes(args.routes)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading routes: {e}")
            sys.exit(1)
    else:
        print("Error: Either --routes or --pages auto must be specified.")
        sys.exit(1)

    # 認証情報の有無を判定
    has_credentials = all([args.login_url, args.email, args.password])

    # ルートフィルタリング
    target_routes = filter_routes(routes, has_credentials)
    target_routes = filter_disabled_module_routes(target_routes, args.name)

    if not target_routes:
        print("No routes to capture (auth routes skipped - no credentials).")
        sys.exit(0)

    skipped = len(routes) - len(target_routes)
    if skipped > 0:
        print(f"  Skipping {skipped} auth-required route(s) (no credentials).")

    # 出力ディレクトリ作成
    ensure_output_dir(args.output_dir)

    # スクリーンショット撮影
    print(f"Capturing {len(target_routes)} screenshot(s) ...")
    results = capture_screenshots(
        base_url=args.base_url,
        routes=target_routes,
        output_dir=args.output_dir,
        login_url=args.login_url,
        email=args.email,
        password=args.password,
    )

    # レポート
    report = build_report(results)
    print(f"\nReport:")
    print(f"  Captured: {report['captured']}")
    print(f"  Failed:   {report['failed']}")
    print(f"  Total:    {report['total_size']:,} bytes")

    if report["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
