# /project:analyze-share

チーム共有・説明資料向けの出力を生成します。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: 対象パス
- 第2引数: 機能名（ファイル名に使用）

```
例: /project:analyze-share ./src/auth user-authentication
```

以降、第1引数を「対象パス」、第2引数を「機能名」として参照します。

## 実行内容

①共通構造・④レベル別説明・⑤人間向けドキュメントのみ出力してください。
非エンジニアへの共有や勉強会資料を想定した読みやすい出力です。

**⚠️ C-2（営業・ビジネス向け）の定量効果の記述ルール（必須）:**
- DB実データから算出可能な数値のみ定量表現に使用する（例: レコード件数、テーブル行数、モジュール数、ロール数）
- 工数削減・コスト削減等の効果は「**効果（推定）**」と明記し、算出の前提条件を併記する
  （例: 「効果（推定）: 月XX時間の工数削減 ※前提: 1件あたりYY分の手作業がZZ件/月」）
- 前提条件が不明な場合は定量表現を使わず、定性表現に留める（例: 「手作業による入力工数を大幅に削減」）
- 「年間N件→0件」のように改善後をゼロと断言しない（ゼロは証明できない。「大幅に削減」に留める）

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

`templates/storyline-design.md` を参照し、読者に伝えたいメインメッセージを1文で定義してから書き始める。

### Step 0c: 重要度マッピング

`templates/priority-analysis.md` を参照し、Step 0 のファクトとビジネスコンテキストに基づいて全機能を Tier 1（コア）/ Tier 2（重要）/ Tier 3（補助）に分類する。
Tier 1 は全機能の 20-30% を目安とする。Tier 1 の機能はビジネスルール詳細・エッジケース・パフォーマンス考慮点まで深掘りし、Tier 3 は概要+API一覧のサマリーに留める。
Tier分類の対象は active: true のモジュールのみ。disabled_modules は architecture 文書の末尾に「無効化モジュール一覧」として記載する（`quality-rules.md` §4a 参照）。

---

### ⚠️ 品質ルール（最優先）

`templates/quality-rules.md` の全ルールに従うこと。ソース引用は `<!-- source: file:line -->` 形式（HTMLコメント、不可視）。

### セルフレビュー（出力前に必ず実行）

`templates/quality-rules.md` §5 のセルフレビューチェックリストを実行すること。

### 出力形式

以下の形式で出力してください。「{機能名}」は第2引数の値に置き換えてください。

```
--- FILE: docs/architecture/{機能名}.md ---
（⑤の内容）

--- FILE: docs/explanations/{機能名}/pro.md ---
（④Aの内容）

--- FILE: docs/explanations/{機能名}/sales.md ---
（④Bの内容）

--- FILE: docs/explanations/{機能名}/beginner.md ---
（④Cの内容）
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
