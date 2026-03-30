#!/usr/bin/env python3
"""
validate.py - 生成された知識資産のバリデーション

使い方:
  python scripts/validate.py --name user-authentication
  python scripts/validate.py --name user-authentication --output-dir /path/to/docs
"""

import argparse
import os
import re
import sys

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

VALID_MERMAID_TYPES = [
    "flowchart",
    "sequenceDiagram",
    "erDiagram",
    "stateDiagram",
    "C4Context",
    "C4Container",
    "C4Component",
    "C4Deployment",
    "classDiagram",
    "gantt",
    "pie",
    "gitgraph",
]

REQUIRED_OPENAPI_FIELDS = ["openapi", "info", "paths"]

REQUIRED_RAG_SECTIONS = [
    "SYSTEM_OVERVIEW",
    "COMPONENTS",
    "FLOW",
    "DEPENDENCY",
    "ERROR_HANDLING",
    "BUSINESS_RULES",
    "CONSTRAINTS",
    "KEYWORDS",
]


def validate_name(name):
    """名前にパストラバーサルや不正な文字が含まれていないかチェックする。"""
    if ".." in name or name.startswith("/") or name.startswith("\\"):
        raise ValueError(f"Invalid name (path traversal detected): '{name}'")
    if os.sep in name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid name (path traversal detected): '{name}'")
    return name


def check_file_exists(path, label):
    """ファイルの存在チェック。"""
    if os.path.exists(path):
        print(f"  [OK] {label}")
        return True
    else:
        print(f"  [FAIL] {label} ... 見つかりません")
        return False


def check_rag_sections(path, label):
    """RAGドキュメントの必須セクションをチェック。"""
    if not os.path.exists(path):
        print(f"  [FAIL] {label} ... 見つかりません")
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"  [FAIL] {label} ... 読み込みエラー: {e}")
        return False

    found = []
    missing = []
    for section in REQUIRED_RAG_SECTIONS:
        if re.search(rf"##\s*{re.escape(section)}", content):
            found.append(section)
        else:
            missing.append(section)

    total = len(REQUIRED_RAG_SECTIONS)
    found_count = len(found)

    if missing:
        print(f"  [WARN] {label} ... 必須セクション: {found_count}/{total}")
        for m in missing:
            print(f"      欠落: {m}")
        return False
    else:
        print(f"  [OK] {label}（必須セクション: {found_count}/{total}）")
        return True


def check_yaml(path, label):
    """YAMLファイルのパースチェック。"""
    if not os.path.exists(path):
        print(f"  [FAIL] {label} ... 見つかりません")
        return False

    if not HAS_YAML:
        print(f"  [WARN] {label} ... pyyaml 未インストールのためスキップ")
        print("      pip install pyyaml でインストールしてください")
        return True

    try:
        with open(path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)
        print(f"  [OK] {label}")
        return True
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        location = f"line {mark.line + 1}" if mark else "unknown location"
        print(f"  [FAIL] {label} ... YAML parse error at {location}")
        return False


def check_decisions(path, label):
    """意思決定ログの未確認項目をチェック。"""
    if not os.path.exists(path):
        print(f"  [FAIL] {label} ... 見つかりません")
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"  [FAIL] {label} ... 読み込みエラー: {e}")
        return False

    unverified = len(re.findall(r"未確認", content))
    if unverified > 0:
        print(f"  [WARN] {label} ... 未確認の意思決定が {unverified}件あります")
        return True
    else:
        print(f"  [OK] {label}（全件確認済み）")
        return True


def check_openapi(filepath):
    """OpenAPI YAML の必須フィールドを検証する。

    Args:
        filepath: OpenAPI YAML ファイルのパス

    Returns:
        エラーメッセージのリスト（空リスト = 問題なし）
    """
    if not os.path.exists(filepath):
        return [f"File not found: {filepath}"]

    if not HAS_YAML:
        return ["pyyaml is not installed; cannot validate OpenAPI"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]
    except (OSError, UnicodeDecodeError) as e:
        return [f"File read error: {e}"]

    if not isinstance(data, dict):
        return ["OpenAPI document must be a YAML mapping"]

    errors = []
    for field in REQUIRED_OPENAPI_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    return errors


def check_mermaid_syntax(filepath):
    """Mermaid .mmd ファイルが有効な図タイプで始まるか検証する。

    Args:
        filepath: .mmd ファイルのパス

    Returns:
        エラーメッセージのリスト（空リスト = 問題なし）
    """
    if not os.path.exists(filepath):
        return [f"File not found: {filepath}"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"File read error: {e}"]

    stripped = content.strip()
    if not stripped:
        return ["File is empty"]

    first_line = stripped.split("\n")[0].strip()
    first_word = first_line.split()[0] if first_line.split() else ""

    # Handle types like "stateDiagram-v2" by checking prefix
    matched = False
    for diagram_type in VALID_MERMAID_TYPES:
        if first_word == diagram_type or first_word.startswith(diagram_type + "-"):
            matched = True
            break

    if not matched:
        return [
            f"Invalid diagram type: '{first_word}'. "
            f"Expected one of: {', '.join(VALID_MERMAID_TYPES)}"
        ]

    return []


def check_index_links(index_path, docs_dir):
    """index.md 内のリンクが実在するファイルを指しているか検証する。

    Args:
        index_path: index.md ファイルのパス
        docs_dir: ドキュメントのベースディレクトリ

    Returns:
        壊れたリンクのエラーメッセージリスト（空リスト = 問題なし）
    """
    if not os.path.exists(index_path):
        return [f"Index file not found: {index_path}"]

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"File read error: {e}"]

    # Extract markdown links: [text](path)
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    broken = []

    for match in link_pattern.finditer(content):
        link_target = match.group(2)

        # Skip external URLs and anchors
        if link_target.startswith(("http://", "https://", "#", "mailto:")):
            continue

        # Remove fragment identifiers
        target_path = link_target.split("#")[0]
        if not target_path:
            continue

        full_path = os.path.join(docs_dir, target_path)
        if not os.path.exists(full_path):
            broken.append(f"Broken link: '{link_target}' (file not found: {full_path})")

    return broken


def check_module_validity(docs_dir, name):
    """Validate that disabled_modules in facts cache are not in feature listings."""
    cache_dir = os.path.join(os.path.dirname(docs_dir), ".cache")
    facts_path = os.path.join(cache_dir, f"facts-{name}.yaml")
    if not os.path.isfile(facts_path):
        return True  # No facts cache; skip

    try:
        import yaml
        with open(facts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"  [WARN] ファクトキャッシュ読み込み失敗: {e}")
        return True

    if not isinstance(data, dict):
        return True

    facts = data.get("facts", data)
    disabled = facts.get("disabled_modules", [])
    if not disabled:
        print(f"  [OK] モジュール有効性: disabled_modules なし（または未記録）")
        return True

    disabled_names = [
        m.get("name", "").lower()
        for m in disabled
        if isinstance(m, dict)
    ]

    # Check features file for disabled module names
    features_path = os.path.join(docs_dir, "manual", name, "03-features.md")
    if not os.path.isfile(features_path):
        print(f"  [OK] モジュール有効性: 03-features.md なし（チェックスキップ）")
        return True

    try:
        with open(features_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except (OSError, UnicodeDecodeError):
        return True

    violations = [
        d for d in disabled_names
        if d and re.search(rf"\b{re.escape(d)}\b", content)
    ]
    if violations:
        for v in violations:
            print(f"  [FAIL] モジュール有効性: disabled module '{v}' が 03-features.md に含まれている")
        return False

    print(f"  [OK] モジュール有効性: disabled_modules ({len(disabled_names)}件) が機能一覧に混入していない")
    return True


def main():
    parser = argparse.ArgumentParser(description="知識資産のバリデーション")
    parser.add_argument("--name", required=True, help="機能名")
    parser.add_argument(
        "--output-dir", default="./docs", help="資産のベースディレクトリ"
    )
    args = parser.parse_args()

    try:
        name = validate_name(args.name)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(2)

    base = os.path.abspath(args.output_dir)

    print(f"[INFO] バリデーション: {name}")
    print(f"[INFO] 対象: {base}")
    print("")

    results = []

    arch_path = os.path.join(base, "architecture", f"{name}.md")
    results.append(check_file_exists(arch_path, f"architecture/{name}.md"))

    rag_path = os.path.join(base, "architecture", f"{name}.rag.md")
    results.append(check_rag_sections(rag_path, f"architecture/{name}.rag.md"))

    diag_path = os.path.join(base, "diagrams", f"{name}.mmd")
    results.append(check_file_exists(diag_path, f"diagrams/{name}.mmd"))

    dec_path = os.path.join(base, "decisions", f"{name}.md")
    results.append(check_decisions(dec_path, f"decisions/{name}.md"))

    meta_path = os.path.join(base, "meta", f"{name}.yaml")
    results.append(check_yaml(meta_path, f"meta/{name}.yaml"))

    # OpenAPI バリデーション
    openapi_path = os.path.join(base, "manual", name, "openapi.yaml")
    if os.path.exists(openapi_path):
        openapi_errors = check_openapi(openapi_path)
        if openapi_errors:
            for e in openapi_errors:
                print(f"  [FAIL] openapi.yaml: {e}")
            results.append(False)
        else:
            print(f"  [OK] openapi.yaml: 構造チェック通過")
            results.append(True)

    # Mermaid 構文チェック（diagrams/ 内の全 .mmd ファイル）
    diagrams_dir = os.path.join(base, "diagrams")
    if os.path.isdir(diagrams_dir):
        for mmd_file in sorted(os.listdir(diagrams_dir)):
            if mmd_file.endswith(".mmd") and mmd_file.startswith(name):
                mmd_path = os.path.join(diagrams_dir, mmd_file)
                mmd_errors = check_mermaid_syntax(mmd_path)
                if mmd_errors:
                    for e in mmd_errors:
                        print(f"  [FAIL] {mmd_file}: {e}")
                    results.append(False)
                else:
                    results.append(True)

    # モジュール有効性チェック
    results.append(check_module_validity(base, name))

    # index.md リンクチェック
    index_path = os.path.join(base, "index.md")
    if os.path.exists(index_path):
        link_errors = check_index_links(index_path, base)
        if link_errors:
            for e in link_errors:
                print(f"  [FAIL] index.md: {e}")
            results.append(False)
        else:
            print(f"  [OK] index.md: 全リンク有効")
            results.append(True)

    print("")
    errors = results.count(False)
    if errors == 0:
        print("[OK] バリデーション完了（問題なし）")
    else:
        print(f"[WARN] バリデーション完了（{errors}件の問題あり）")
        sys.exit(1)


if __name__ == "__main__":
    main()
