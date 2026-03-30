#!/usr/bin/env python3
"""
translate_diagrams.py - .mmd ファイルのノードラベルを日本語に翻訳する

対象パスの languages/ja_jp/ ディレクトリから翻訳文言を取得し、
.mmd 内のノードラベルを日本語名に置換する。

使い方:
  python scripts/translate_diagrams.py --docs-dir ./docs --source-dir /path/to/project --name system-name
  python scripts/translate_diagrams.py --docs-dir ./docs --source-dir /path/to/project --name system-name --in-place
"""

import argparse
import glob
import json
import os
import re
import sys


def find_language_files(source_dir):
    """languages/ja_jp/ ディレクトリから翻訳ファイルを検索する。

    対応フォーマット:
    - PHP: $languageStrings['KEY'] = 'VALUE';
    - JSON: {"KEY": "VALUE"}
    - Vue i18n (JS): 'KEY': 'VALUE' or "KEY": "VALUE"
    """
    translations = {}
    lang_dirs = [
        os.path.join(source_dir, "languages", "ja_jp"),
        os.path.join(source_dir, "lang", "ja"),
        os.path.join(source_dir, "locales", "ja"),
        os.path.join(source_dir, "i18n", "ja"),
        os.path.join(source_dir, "resources", "lang", "ja"),
    ]

    for lang_dir in lang_dirs:
        if not os.path.isdir(lang_dir):
            continue

        # PHP files
        for php_file in glob.glob(os.path.join(lang_dir, "**", "*.php"), recursive=True):
            translations.update(parse_php_lang_file(php_file))

        # JSON files
        for json_file in glob.glob(os.path.join(lang_dir, "**", "*.json"), recursive=True):
            translations.update(parse_json_lang_file(json_file))

        # JS files (Vue i18n)
        for js_file in glob.glob(os.path.join(lang_dir, "**", "*.js"), recursive=True):
            translations.update(parse_js_lang_file(js_file))

    return translations


def parse_php_lang_file(filepath):
    """PHP言語ファイルから翻訳を抽出する。

    $languageStrings['KEY'] = 'VALUE'; パターン
    """
    translations = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # $languageStrings['SINGLE_Module'] = '日本語名';
        pattern = re.compile(
            r"\$languageStrings\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*['\"]([^'\"]+)['\"]",
        )
        for match in pattern.finditer(content):
            key = match.group(1)
            value = match.group(2)
            translations[key] = value

        # 'key' => '日本語名', パターン（Laravel等）
        pattern2 = re.compile(
            r"['\"]([^'\"]+)['\"]\s*=>\s*['\"]([^'\"]+)['\"]",
        )
        for match in pattern2.finditer(content):
            key = match.group(1)
            value = match.group(2)
            translations[key] = value

    except (OSError, UnicodeDecodeError):
        pass
    return translations


def parse_json_lang_file(filepath):
    """JSON言語ファイルから翻訳を抽出する。"""
    translations = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        def _flatten(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _flatten(v, f"{prefix}{k}." if prefix else f"{k}.")
            elif isinstance(obj, str):
                key = prefix.rstrip(".")
                translations[key] = obj

        _flatten(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return translations


def parse_js_lang_file(filepath):
    """JS言語ファイル（Vue i18n等）から翻訳を抽出する。"""
    translations = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = re.compile(
            r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        )
        for match in pattern.finditer(content):
            key = match.group(1)
            value = match.group(2)
            translations[key] = value
    except (OSError, UnicodeDecodeError):
        pass
    return translations


def build_label_map(translations):
    """翻訳辞書からモジュール名→日本語名のマッピングを構築する。

    SINGLE_ModuleName → 日本語名 を優先、なければ ModuleName → 日本語名
    """
    label_map = {}

    for key, value in translations.items():
        # SINGLE_ プレフィックス付きを優先
        if key.startswith("SINGLE_"):
            module_name = key[7:]  # "SINGLE_" を除去
            label_map[module_name] = value
        elif key not in label_map:
            label_map[key] = value

    return label_map


# Mermaid 予約語（ノード名として扱わない）
MERMAID_RESERVED = frozenset({
    "subgraph", "end", "direction", "classDef", "class", "style", "click",
    "note", "participant", "actor", "activate", "deactivate", "loop", "alt",
    "else", "opt", "par", "critical", "break", "rect", "TB", "TD", "BT",
    "RL", "LR", "graph", "flowchart", "sequenceDiagram", "stateDiagram",
    "stateDiagram-v2", "erDiagram", "gantt", "pie", "gitGraph", "journey",
    "left", "right", "of", "over", "as", "state",
})

# ノード名サフィックスの定訳マップ
SUFFIX_TRANSLATIONS = {
    "_Detail": " 詳細",
    "_Details": " 詳細",
    "_List": " 一覧",
    "_ListView": " 一覧",
    "_Edit": " 編集",
    "_EditView": " 編集",
    "_Create": " 新規作成",
    "_CreateView": " 新規作成",
    "_Related": " 関連",
    "_RelatedList": " 関連一覧",
    "_Index": " トップ",
    "_Summary": " サマリー",
    "_Config": " 設定",
    "_Settings": " 設定",
    "_Search": " 検索",
    "_Import": " インポート",
    "_Export": " エクスポート",
}


def _extract_bare_nodes(content):
    """Mermaid コンテンツからラベルなしのノード名を抽出する。

    Returns:
        set: ラベルなしで使われているノード名の集合
    """
    bare_nodes = set()

    for line in content.splitlines():
        stripped = line.strip()
        # コメント行をスキップ
        if stripped.startswith("%%"):
            continue
        # ダイアグラム種別宣言行をスキップ
        if re.match(
            r"^(graph|flowchart|sequenceDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph|journey)\b",
            stripped,
        ):
            continue
        # direction 行をスキップ
        if re.match(r"^direction\s+", stripped):
            continue

        # 矢印パターン: A --> B / A --> B: ラベル / A --- B 等
        # 全矢印種別: -->, --->, -.->,-...->, ==>, --, ---, ~~
        arrow_pattern = re.compile(
            r'(\S+)\s+(?:-->|---->|-.->|-\.\.\.->|==>|---|----|\~\~>|--)\s+(\S+)',
        )
        for m in arrow_pattern.finditer(stripped):
            for node_str in [m.group(1), m.group(2)]:
                # エッジラベル ": ..." を除去
                node_clean = re.sub(r':.*$', '', node_str).strip()
                # 既にラベル付き ["..."] ("...") をスキップ
                if re.search(r'[\[\("]', node_clean):
                    continue
                # [*] 等の特殊ノードをスキップ
                if node_clean in ("[*]", "(*)", "[*"):
                    continue
                if node_clean and node_clean not in MERMAID_RESERVED:
                    bare_nodes.add(node_clean)

        # participant A / actor A パターン（sequenceDiagram）
        participant_m = re.match(r"^(?:participant|actor)\s+(\w+)", stripped)
        if participant_m:
            node_name = participant_m.group(1)
            if node_name not in MERMAID_RESERVED:
                bare_nodes.add(node_name)

        # state "..." as A の A 部分（stateDiagram）
        state_as_m = re.match(r'^state\s+"[^"]*"\s+as\s+(\w+)', stripped)
        if state_as_m:
            node_name = state_as_m.group(1)
            if node_name not in MERMAID_RESERVED:
                bare_nodes.add(node_name)

        # [*] --> A パターン（stateDiagram の開始ノード）
        star_m = re.match(r'^\[\*\]\s+-->\s+(\w+)', stripped)
        if star_m:
            node_name = star_m.group(1)
            if node_name not in MERMAID_RESERVED:
                bare_nodes.add(node_name)

    return bare_nodes


def _resolve_node_label(node_name, label_map):
    """ノード名に対する日本語ラベルを解決する。

    優先順:
    1. 完全一致: label_map に直接存在
    2. サフィックス分離: {Module}_{ViewType} を分離し、
       Module部分を翻訳 + ViewType部分を定訳
    3. マッチなし: None を返す

    Args:
        node_name: ノード名（例: "ClinicalTrial_Detail"）
        label_map: 英語名→日本語名の辞書

    Returns:
        str or None: 日本語ラベル（マッチなしは None）
    """
    # 1. 完全一致
    if node_name in label_map:
        return label_map[node_name]

    # 2. サフィックス分離（長いサフィックスを優先）
    for suffix, ja_suffix in sorted(
        SUFFIX_TRANSLATIONS.items(), key=lambda x: -len(x[0])
    ):
        if node_name.endswith(suffix):
            module_part = node_name[: -len(suffix)]
            if module_part in label_map:
                return label_map[module_part] + ja_suffix

    return None


def _translate_bare_nodes(content, label_map):
    """ラベルなしノード名を NodeName["日本語ラベル"] 形式に変換する。

    既存パターン1-3の後に実行し、既にラベル付きのノードは二重変換しない。

    Returns:
        (str, int): 変換後のコンテンツと変換数
    """
    bare_nodes = _extract_bare_nodes(content)
    if not bare_nodes:
        return content, 0

    # 翻訳可能なノードのマッピングを構築
    node_translations = {}
    for node_name in bare_nodes:
        ja_label = _resolve_node_label(node_name, label_map)
        if ja_label is not None:
            node_translations[node_name] = ja_label

    if not node_translations:
        return content, 0

    # ノード名の長い順にソート（部分一致の誤置換を防ぐ）
    sorted_nodes = sorted(node_translations.keys(), key=len, reverse=True)

    translated = content
    changes = 0

    for node_name in sorted_nodes:
        ja_label = node_translations[node_name]

        # ノード名が単独で出現する箇所を置換
        # 前後の文脈: 行頭、空白、矢印の後、| の後
        # 後続: 空白、矢印、行末、: （エッジラベル）
        # 既にラベル付き ["..."] ("...") {" の直前は除外
        pattern = re.compile(
            rf'(?<!["\w\]\)])'           # 前方: ラベル閉じや単語の途中でない
            rf'({re.escape(node_name)})'  # ノード名をキャプチャ
            rf'(?![\w"\[\(])'            # 後方: ラベル開始や単語の続きでない
        )

        def _replace_node(m):
            return f'{m.group(1)}["{ja_label}"]'

        new_content = []
        for line in translated.splitlines(True):
            stripped = line.lstrip()
            # コメント行はスキップ
            if stripped.startswith("%%"):
                new_content.append(line)
                continue
            # ダイアグラム種別宣言行はスキップ
            if re.match(
                r"^(graph|flowchart|sequenceDiagram|stateDiagram|erDiagram)\b",
                stripped,
            ):
                new_content.append(line)
                continue
            # 既にこのノードにラベルが付いている行はスキップ
            if f'{node_name}["' in line or f"{node_name}(\"" in line:
                new_content.append(line)
                continue

            new_line = pattern.sub(_replace_node, line)
            new_content.append(new_line)

        result = "".join(new_content)
        if result != translated:
            changes += 1
            translated = result

    return translated, changes


def translate_mmd_content(content, label_map):
    """Mermaid .mmd コンテンツのノードラベルを日本語に翻訳する。

    翻訳対象パターン:
    - パターン1: NodeName["Label"] → NodeName["日本語ラベル"]
    - パターン2: NodeName("Label") → NodeName("日本語ラベル")
    - パターン3: NodeName["Label<br/>SubLabel"] → NodeName["日本語<br/>サブラベル"]
    - パターン3b: stateDiagram の state "Label" as NodeName → state "日本語" as NodeName
    - パターン4: ラベルなしノード名 → NodeName["日本語ラベル"]（パターン1-3の後に実行）
    """
    translated = content
    changes = 0

    # --- パターン1-3: 既存のラベル付きノードの翻訳 ---
    for eng_name, ja_name in label_map.items():
        # ["Label"] or ("Label") パターン
        pattern1 = re.compile(
            rf'(\["|\(")\s*{re.escape(eng_name)}\s*("\]|"\))',
        )
        # <br/> 付きパターン
        pattern2 = re.compile(
            rf'{re.escape(eng_name)}<br/>',
        )
        # state "Label" パターン
        pattern3 = re.compile(
            rf'state\s+"{re.escape(eng_name)}"',
        )

        new_content = pattern1.sub(
            lambda m: f'{m.group(1)}{ja_name}{m.group(2)}',
            translated,
        )
        if new_content != translated:
            changes += 1
            translated = new_content

        new_content = pattern2.sub(f"{ja_name}<br/>", translated)
        if new_content != translated:
            changes += 1
            translated = new_content

        new_content = pattern3.sub(f'state "{ja_name}"', translated)
        if new_content != translated:
            changes += 1
            translated = new_content

    # --- パターン4: ラベルなしノード名の検出と変換 ---
    translated, bare_changes = _translate_bare_nodes(translated, label_map)
    changes += bare_changes

    return translated, changes


def main():
    parser = argparse.ArgumentParser(
        description=".mmd ファイルのノードラベルを日本語に翻訳する"
    )
    parser.add_argument(
        "--docs-dir", default="./docs", help="docs ディレクトリのパス"
    )
    parser.add_argument(
        "--source-dir", required=True, help="対象プロジェクトのソースディレクトリ"
    )
    parser.add_argument(
        "--name", required=True, help="システム名（ファイル名プレフィックス）"
    )
    parser.add_argument(
        "--in-place", action="store_true",
        help="原本を直接書き換える（デフォルトは -ja.mmd として別ファイル出力）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="翻訳を実行せずに結果を表示"
    )
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)
    source_dir = os.path.abspath(args.source_dir)
    diagrams_dir = os.path.join(docs_dir, "diagrams")

    if not os.path.isdir(diagrams_dir):
        print(f"[ERROR] {diagrams_dir} が見つかりません。")
        sys.exit(1)

    # 1. 翻訳ファイルを検索・パース
    print(f"[INFO] 翻訳ファイル検索: {source_dir}")
    translations = find_language_files(source_dir)

    if not translations:
        print("[INFO] 翻訳ファイルが見つかりません。処理をスキップします。")
        sys.exit(0)

    print(f"[INFO] 翻訳エントリ: {len(translations)}件")

    label_map = build_label_map(translations)
    print(f"[INFO] ラベルマップ: {len(label_map)}件")

    # 2. 対象 .mmd ファイルを収集
    mmd_pattern = os.path.join(diagrams_dir, f"{args.name}-*.mmd")
    mmd_files = sorted(glob.glob(mmd_pattern))

    if not mmd_files:
        print(f"[INFO] {args.name}-*.mmd に一致するファイルがありません。")
        sys.exit(0)

    print(f"[INFO] 対象: {len(mmd_files)} ファイル")
    print("")

    # 3. 翻訳実行
    translated_count = 0
    for mmd_path in mmd_files:
        basename = os.path.basename(mmd_path)
        with open(mmd_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content, changes = translate_mmd_content(content, label_map)

        if changes > 0:
            if args.in_place:
                output_path = mmd_path
            else:
                name_part = os.path.splitext(basename)[0]
                output_path = os.path.join(diagrams_dir, f"{name_part}-ja.mmd")

            rel = os.path.relpath(output_path, docs_dir)
            if args.dry_run:
                print(f"  [DRY-RUN] {basename} -> {rel} ({changes}箇所翻訳)")
            else:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"  [OK] {basename} -> {rel} ({changes}箇所翻訳)")
            translated_count += 1
        else:
            print(f"  [SKIP] {basename} (翻訳対象なし)")

    print("")
    if args.dry_run:
        print(f"[INFO] dry-run 完了: {translated_count}/{len(mmd_files)} ファイル翻訳予定")
    else:
        print(f"[OK] 完了: {translated_count}/{len(mmd_files)} ファイル翻訳")


if __name__ == "__main__":
    main()
