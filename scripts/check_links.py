#!/usr/bin/env python3
"""
check_links.py - Markdownファイル内のリンクを検証する

使い方:
  python scripts/check_links.py --docs-dir ./docs
  python scripts/check_links.py --docs-dir ./docs --ignore 'generated/*' '*.draft.md'
  python scripts/check_links.py --docs-dir ./docs --json
"""

import argparse
import fnmatch
import glob as glob_mod
import json as json_mod
import os
import re
import sys

# Markdownリンクのパターン: [text](url) および ![alt](url)
LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")

# 外部URLのプレフィックス
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://")


def is_external_url(url):
    """URLが外部リンクかどうかを判定する。"""
    return url.startswith(EXTERNAL_PREFIXES)


def extract_links(content):
    """Markdownコンテンツからリンクを抽出する。

    Returns:
        list of (line_number, text, url) tuples
    """
    results = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in LINK_PATTERN.finditer(line):
            text = match.group(1)
            url = match.group(2)
            results.append((line_num, text, url))
    return results


def heading_to_slug(heading_text):
    """見出しテキストをGitHub互換のスラッグに変換する。"""
    slug = heading_text.lower().strip()
    # 特殊文字を除去（英数字、ハイフン、スペース、日本語は維持）
    slug = re.sub(r"[^\w\s-]", "", slug)
    # スペースをハイフンに変換
    slug = re.sub(r"\s+", "-", slug)
    # 連続ハイフンを1つに
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def heading_exists(content, anchor):
    """コンテンツ内に指定アンカーに対応する見出しが存在するかチェックする。"""
    heading_pattern = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

    for match in heading_pattern.finditer(content):
        heading_text = match.group(1).strip()
        slug = heading_to_slug(heading_text)
        if slug == anchor.lower():
            return True
    return False


def resolve_link_target(source_file, link):
    """ソースファイルからの相対リンクを絶対パスに解決する。

    アンカー部分(#...)は除去して、ファイルパスのみ返す。
    """
    # アンカーを分離
    path = link.split("#")[0]
    if not path:
        # アンカーのみのリンク(#section) -> ソースファイル自身
        return source_file

    source_dir = os.path.dirname(source_file)
    resolved = os.path.join(source_dir, path)
    return os.path.normpath(resolved)


def find_markdown_files(directory):
    """ディレクトリ内のMarkdownファイルを再帰的に検索する。"""
    md_files = []
    for root, _dirs, files in os.walk(directory):
        for filename in sorted(files):
            if filename.endswith(".md"):
                md_files.append(os.path.join(root, filename))
    return md_files


def matches_ignore_pattern(link, patterns):
    """リンクが無視パターンにマッチするかチェックする。"""
    for pattern in patterns:
        if fnmatch.fnmatch(link, pattern):
            return True
    return False


def validate_links(directory, ignore_patterns=None):
    """ディレクトリ内の全Markdownファイルのリンクを検証する。

    Returns:
        list of error dicts: {source, line, link, reason}
    """
    if ignore_patterns is None:
        ignore_patterns = []

    errors = []
    md_files = find_markdown_files(directory)

    for filepath in md_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        links = extract_links(content)

        for line_num, _text, url in links:
            # 外部URLはスキップ
            if is_external_url(url):
                continue

            # 無視パターンにマッチする場合はスキップ
            if matches_ignore_pattern(url, ignore_patterns):
                continue

            # アンカー部分を分離
            anchor = None
            if "#" in url:
                parts = url.split("#", 1)
                anchor = parts[1] if parts[1] else None

            # ターゲットファイルを解決
            target_path = resolve_link_target(filepath, url)

            # アンカーのみリンクの場合はファイル自身をチェック
            path_part = url.split("#")[0]
            if path_part:
                # ファイルの存在チェック
                if not os.path.exists(target_path):
                    errors.append({
                        "source": filepath,
                        "line": line_num,
                        "link": url,
                        "reason": f"File not found: {target_path}",
                    })
                    continue

            # アンカーチェック
            if anchor:
                # ターゲットファイルの内容を読み込んでアンカーを検証
                target_for_anchor = target_path
                if not path_part:
                    target_for_anchor = filepath

                try:
                    with open(target_for_anchor, "r", encoding="utf-8") as f:
                        target_content = f.read()
                except (OSError, UnicodeDecodeError):
                    errors.append({
                        "source": filepath,
                        "line": line_num,
                        "link": url,
                        "reason": f"Cannot read file for anchor check: {target_for_anchor}",
                    })
                    continue

                if not heading_exists(target_content, anchor):
                    errors.append({
                        "source": filepath,
                        "line": line_num,
                        "link": url,
                        "reason": f"Anchor not found: #{anchor} in {target_for_anchor}",
                    })

    return errors


def check_diagram_reverse_links(directory):
    """SVGファイルが対応するMarkdownからリンクされているかを逆引きチェックする。

    Returns:
        list of warning dicts: {svg, expected_md, reason}
    """
    diagrams_dir = os.path.join(directory, "diagrams")
    if not os.path.isdir(diagrams_dir):
        return []

    # SVGファイル名パターン → 期待されるMarkdownファイルの対応ルール
    DIAGRAM_LINK_RULES = [
        # (SVGファイル名の正規表現, 期待されるMarkdownパスのテンプレート)
        (r"^(.+)-screen-flow\.svg$", ["manual/{name}/02-screen-flow.md"]),
        (r"^(.+)-architecture\.svg$", ["manual/{name}/01-overview.md"]),
        (r"^(.+)-data-flow\.svg$", ["manual/{name}/05-data-model.md"]),
        (r"^(.+)-er-\w+\.svg$", ["manual/{name}/05-data-model.md"]),
        (r"^(.+)-feat-\w+\.svg$", ["manual/{name}/features/*.md", "manual/{name}/03-features.md"]),
        (r"^(.+)-seq-\w+\.svg$", ["manual/{name}/07-walkthrough.md"]),
        (r"^(.+)-context\.svg$", ["architecture/{name}.md"]),
        (r"^(.+)-container\.svg$", ["architecture/{name}.md"]),
        (r"^(.+)-component\.svg$", ["architecture/{name}.md"]),
        (r"^(.+)-deployment\.svg$", ["architecture/{name}.md"]),
    ]

    warnings = []
    svg_files = [f for f in os.listdir(diagrams_dir) if f.endswith(".svg")]

    for svg_file in sorted(svg_files):
        for pattern, md_templates in DIAGRAM_LINK_RULES:
            match = re.match(pattern, svg_file)
            if not match:
                continue

            name = match.group(1)
            svg_basename = svg_file

            # 期待されるMarkdownファイルを展開
            expected_mds = []
            for tmpl in md_templates:
                md_path_pattern = tmpl.replace("{name}", name)
                if "*" in md_path_pattern:
                    # ワイルドカード展開
                    full_pattern = os.path.join(directory, md_path_pattern)
                    expected_mds.extend(glob_mod.glob(full_pattern))
                else:
                    full_path = os.path.join(directory, md_path_pattern)
                    if os.path.exists(full_path):
                        expected_mds.append(full_path)

            if not expected_mds:
                # 対応するMarkdownファイル自体が存在しない → スキップ
                break

            # いずれかのMarkdownファイルにSVGへのリンクが含まれているかチェック
            found = False
            for md_path in expected_mds:
                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if svg_basename in content:
                        found = True
                        break
                except (OSError, UnicodeDecodeError):
                    continue

            if not found:
                expected_names = [os.path.relpath(p, directory) for p in expected_mds]
                warnings.append({
                    "svg": f"diagrams/{svg_file}",
                    "expected_md": expected_names,
                    "reason": f"SVG '{svg_file}' は生成済みだが、{', '.join(expected_names)} からリンクされていない",
                })
            break  # 最初にマッチしたルールのみ適用

    return warnings


def format_errors(errors):
    """エラーリストを人間が読める形式にフォーマットする。"""
    lines = []
    for error in errors:
        source = error["source"]
        line_num = error["line"]
        link = error["link"]
        reason = error["reason"]
        lines.append(f"  {source}:{line_num} -> [{link}] {reason}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Markdownファイル内のリンクを検証する"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="検証対象のドキュメントディレクトリ",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="無視するリンクパターン（fnmatch形式）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="結果をJSON形式で標準出力に出力する",
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)

    if not os.path.isdir(docs_dir):
        print(f"[ERROR] ディレクトリが見つかりません: {docs_dir}")
        sys.exit(2)

    print(f"[INFO] リンク検証: {docs_dir}")
    if args.ignore:
        print(f"[INFO] 無視パターン: {args.ignore}")

    errors = validate_links(docs_dir, ignore_patterns=args.ignore)

    # 図リンク逆引きチェック
    diagram_warnings = check_diagram_reverse_links(docs_dir)

    if args.json:
        result = {
            "errors": errors,
            "diagram_warnings": diagram_warnings,
        }
        print(json_mod.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1 if errors else 0)

    if diagram_warnings:
        print(f"\n[WARNING] {len(diagram_warnings)}件の図リンク漏れが見つかりました:\n")
        for w in diagram_warnings:
            print(f"  {w['svg']} -> {w['reason']}")

    if errors:
        print(f"\n[FAIL] {len(errors)}件のリンク切れが見つかりました:\n")
        print(format_errors(errors))
        sys.exit(1)
    elif diagram_warnings:
        print(f"\n[WARNING] リンク切れはありませんが、{len(diagram_warnings)}件の図リンク漏れがあります")
        sys.exit(0)
    else:
        print("\n[OK] リンク切れはありません")
        sys.exit(0)


if __name__ == "__main__":
    main()
