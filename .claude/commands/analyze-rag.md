# /project:analyze-rag

RAG・知識ベース蓄積に特化した最小出力を生成します。
チャンク最適化 + YAML frontmatter メタデータ付き。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: 対象パス
- 第2引数: 機能名（ファイル名に使用）

```
例: /project:analyze-rag ./src/auth user-authentication
```

以降、第1引数を「対象パス」、第2引数を「機能名」として参照します。

## 実行内容

RAG 検索に最適化されたドキュメントと YAML メタ情報を出力してください。
CI/CDやバッチ処理での自動蓄積を想定した最小・高速な出力です。

### Step 0: ファクト収集（文章を書く前に必ず実行）

`templates/thinking-frameworks.md` と `templates/business-context.md` を参照し、ファクト収集と同時にビジネスコンテキストを把握する。

**追加収集項目**:
```yaml
  business_context:
    purpose: "(1-2文でシステムの存在理由)"
    users: [{role: "...", needs: "..."}]
  selected_frameworks: [MECE, "So What? / Why So?"]
```

対象パスのコードを読み、発見した事実を構造化データとして整理してください。
ファクト収集で列挙されていない事実を本文に書くことは禁止です。

````yaml
facts:
  routes:       # ルーティング定義
    - method: (HTTP メソッド)
      path: (パス)
      controller: (コントローラー#メソッド)
      source: "(ファイル:行番号)"
  controllers:  # コントローラー
    - name: (クラス名)
      file: (ファイルパス)
      source: "(ファイル:行番号)"
  models:       # モデル
    - name: (クラス名)
      table: (テーブル名)
      source: "(ファイル:行番号)"
  screens:      # 画面
    - name: (画面名)
      path: (URL パス)
      component: (コンポーネントファイル)
      source: "(ファイル:行番号)"
````

**ルール**: 各エントリの `source`（ファイル:行番号）は必須。推測は `confirmed: false` を付与。
**モジュール有効性チェック（必須）**: `quality-rules.md` §4a に従い各モジュールの active を判定する。コードの存在だけでモジュールを列挙しない。

### Step 0b: ストーリーライン設計

各セクション（SYSTEM_OVERVIEW, COMPONENTS, FLOW等）の結論を1文ずつ先に定義してから本文を書き始める。

### Step 0c: disabled_modules の配置

disabled_modules（active: false）は CONSTRAINTS セクション内に「無効化モジュール一覧」として記載する。
RAG チャンクは独立して検索されるため、SYSTEM_OVERVIEW セクションにも disabled_modules の概要を含めてよい。

### RAG ドキュメントのルール

`templates/quality-rules.md` の全ルールに従うこと。ソース引用は `(file:line)` 形式（本文に表示）。
以下は RAG 固有の追加ルール：

1. **YAML frontmatter** を先頭に含める
2. 各セクションが**自己完結**すること（「上述の通り」「前述の」等のクロスリファレンス禁止）
3. **階層見出し**（H2 > H3）をチャンク境界として使う
4. 1セクション **256-512トークン** を目安にする（長すぎるセクションは分割）
5. **箇条書き中心・短文・冗長禁止**
6. **DB分析結果がある場合（`.cache/db-*.json` が存在する場合）:**
   - COMPONENTS セクションにDB上のテーブル情報（種別・有効/無効状態）を含める
   - BUSINESS_RULES セクションに機能フラグの現在値・マスタデータの有効/無効状態を反映
   - KEYWORDS セクションにDB上のラベル/表示名も含める（コード上の変数名との対応付き）
   - DB_STATUS セクションを追加し、コード⇔DB間の不整合・無効化されたデータ/機能を記載

### frontmatter 形式

```yaml
---
title: {機能名} - RAG Knowledge Base
category: architecture
keywords: [キーワード1, キーワード2, ...]
language: ja
last_updated: （今日の日付）
confidence: medium
source_path: （対象パス）
---
```

### 必須セクション

```
## SYSTEM_OVERVIEW
（システムの目的・解決する問題・技術スタック。自己完結。）

## COMPONENTS
（全コンポーネント名・種別・責務・ファイルパス。自己完結。）

## FLOW
（リクエストの流れ。エントリポイント→終端を箇条書き。自己完結。）

## DEPENDENCY
（外部依存: ライブラリ・外部サービス・インフラ。バージョン付き。自己完結。）

## ERROR_HANDLING
（エラー種別・HTTPステータス・ユーザーへの通知方法。自己完結。）

## BUSINESS_RULES
（ビジネスルール・計算ロジック・条件分岐。自己完結。）

## CONSTRAINTS
（技術的制約・EOL情報・命名規則・既知のTypo。自己完結。）

## KEYWORDS
（検索用キーワード。日本語・英語の両方を含める。自己完結。）
```

### セルフレビュー（出力前に必ず実行）

`templates/quality-rules.md` §5 のセルフレビューチェックリストを実行すること。

### 出力形式

以下の形式で出力してください。「{機能名}」は第2引数の値に置き換えてください。

```
--- FILE: docs/architecture/{機能名}.rag.md ---
（YAML frontmatter + 8セクションの RAG ドキュメント）

--- FILE: docs/meta/{機能名}.yaml ---
（YAML メタ情報）
```

出力後、以下を案内してください（{機能名}は実際の値に置き換え）：
```
分析完了！次のコマンドでファイルに保存できます：
python scripts/save_output.py \
  --name {機能名} \
  --output-dir ./docs

生成内容の実在性を検証するには：
python scripts/verify_docs.py \
  --docs-dir ./docs \
  --source-dir {対象パス} \
  --name {機能名}
```
