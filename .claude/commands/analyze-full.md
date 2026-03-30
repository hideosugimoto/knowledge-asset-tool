# /project:analyze-full

コードを分析して全セクションの知識資産を生成します（完全版）。
arc42 全12セクション + C4図 + MADR意思決定記録 + RAG + レベル別説明。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: 対象パス
- 第2引数: 機能名（ファイル名に使用）

```
例: /project:analyze-full ./src/auth user-authentication
```

以降、第1引数を「対象パス」、第2引数を「機能名」として参照します。

## 実行内容

以下のセクション A〜F をすべて出力してください。

### Step 0: ファクト収集（文章を書く前に必ず実行）

**ファクトキャッシュ**:
ファクト収集の前に `python3 scripts/cache_analysis.py --action check-facts --source-dir {対象パス} --name {名前}` を実行。
キャッシュが有効な場合は `.cache/facts-{名前}.yaml` から読み込んでファクト収集をスキップし、
「キャッシュ済みファクトを使用（{生成日時}、コミット {hash}）」と表示する。
キャッシュが無効（ソース変更あり）または存在しない場合は通常通りファクト収集を実行し、
完了後に `python3 scripts/cache_analysis.py --action save-facts --source-dir {対象パス} --name {名前}` でキャッシュに保存する。

`templates/thinking-frameworks.md` の選択マトリクスと `templates/business-context.md` の自動収集チェックリストを参照し、
ファクト収集と同時にシステム特性の把握・ビジネスコンテキストの収集・フレームワークの選択を1パスで実施する。

**追加収集項目**（既存の facts YAML に以下を追加）:

```yaml
  system_profile:
    scale: small|medium|large      # 画面数・テーブル数・API数から判定
    domain: "(業務系/EC系/管理系/API特化)"
    complexity: simple|moderate|complex
  business_context:
    purpose: "(1-2文でシステムの存在理由)"
    users: [{role: "...", needs: "..."}]
    confidence: low|medium|high
  selected_frameworks:  # thinking-frameworks.md のセクション3から自動選択
    - name: "MECE"
    - name: "So What? / Why So?"
```

対象パスのコードを読み、以下のカテゴリごとに発見した事実を構造化データとして整理してください。
このデータを **文章化の唯一の入力** として使用します。ファクト収集で列挙されていない事実を本文に書くことは禁止です。

**出力**: 以下の YAML 構造でファクトを整理する（最終出力ファイルには含めず、作業用中間データとして使用）

````yaml
facts:
  routes:       # 全ルーティング定義
    - method: (HTTP メソッド)
      path: (パス)
      controller: (コントローラー#メソッド)
      source: "(ファイル:行番号)"
  controllers:  # 全コントローラー
    - name: (クラス名)
      file: (ファイルパス)
      methods: [...]
      source: "(ファイル:行番号)"
  models:       # 全モデル
    - name: (クラス名)
      table: (テーブル名)
      file: (ファイルパス)
      source: "(ファイル:行番号)"
  tables:       # 全テーブル（マイグレーション or DB分析から）
    - name: (テーブル名)
      type: (master/transaction/relation/system)
      columns: [{name: ..., type: ...}]
      source: "(ファイル:行番号)"
  screens:      # 全画面
    - name: (画面名)
      path: (URL パス)
      component: (コンポーネントファイル)
      elements: {buttons: [...], forms: [...], tables: [...]}
      source: "(ファイル:行番号)"
  stores:       # 状態管理
    - name: (Store名)
      file: (ファイルパス)
      actions: [...]
      source: "(ファイル:行番号)"
  middleware:   # ミドルウェア
    - name: (名前)
      file: (ファイルパス)
      source: "(ファイル:行番号)"
  services:     # サービス層
    - name: (クラス名)
      file: (ファイルパス)
      methods: [...]
      source: "(ファイル:行番号)"
````

**ルール**:
1. 各エントリの `source` は必須。ファイルパスと行番号を `file:line` 形式で記録
2. コードを実際に読んで確認した事実のみ記録。推測は `confirmed: false` を付与
3. ファクト収集完了後、件数を確認: routes件数 = API一覧件数、screens件数 = 画面一覧件数
4. ファクト収集が完了してから、以降のセクション（共通ルール以降）の文章化に進む
5. **モジュール有効性チェック（必須）**: `quality-rules.md` §4a に従い各モジュールの active を判定する。コードの存在だけでモジュールを列挙しない

---

### Step 0b: ストーリーライン設計

`templates/storyline-design.md` を参照し、ファクト収集の結果を基にドキュメント全体のストーリーラインを設計する。

1. **メインメッセージ**: このドキュメント全体で読者に伝えたい結論を1-2文で定義
2. **各セクションのサブメッセージ**: 章/セクションごとの結論を1文ずつ定義
3. **ピラミッド構造**: 結論先行 → 根拠（ファクトから） → 詳細

テンプレート埋めに入る前にストーリーラインを確定させること。メッセージが定まらないまま書き始めない。

---

### Step 0c: 重要度マッピング

`templates/priority-analysis.md` を参照し、Step 0 のファクトとビジネスコンテキストに基づいて全機能を Tier 1（コア）/ Tier 2（重要）/ Tier 3（補助）に分類する。
Tier 1 は全機能の 20-30% を目安とする。Tier 1 の機能はビジネスルール詳細・エッジケース・パフォーマンス考慮点まで深掘りし、Tier 3 は概要+API一覧のサマリーに留める。
Tier分類の対象は active: true のモジュールのみ。disabled_modules は §11 に無効化モジュール一覧として記載する（`quality-rules.md` §4a 参照）。

---

### ⚠️ 共通ルール（最優先）

`templates/quality-rules.md` の全ルールに従うこと。ソース引用は `(file:line)` 形式（本文に表示）。
以下は本コマンド固有の追加ルール：

1. 図はすべてMermaid記法 + C4 記法で記述する
2. 複雑な処理は必ず分解して説明する
3. **DB分析結果がある場合（`.cache/db-*.json` が存在する場合）:**
   - DBスキーマ情報を読み込み、コード分析と照合すること
   - マスタテーブルの有効/無効フラグを確認し、無効化されたデータに依存する機能は【DB無効】と注記
   - テーブルの表示名・ラベルがDBに格納されている場合、コード上の変数名ではなくDB上の表示名を優先して記載
   - 設定テーブル・機能フラグの値を確認し、無効化されている機能は【機能OFF】と注記
   - コード上に参照があるがDBに存在しないテーブル/カラム、またはその逆の不整合を§11に記載
   - §12 用語集にDB上のラベル/表示名とコード上の変数名の対応を含める

---

### A. arc42 アーキテクチャドキュメント（全12セクション）

#### §1. はじめに（Introduction and Goals）
- システムの目的（1文）
- 主要な機能要件（箇条書き）
- 品質目標（性能・可用性・保守性・セキュリティ等）
- ステークホルダー一覧

| ステークホルダー | 関心事 | 期待 |
|---------------|--------|------|

#### §2. 制約（Constraints）

| 種別 | 制約 | 背景 |
|------|------|------|

種別: 技術的 / 組織的 / 規約

#### §3. コンテキストと範囲（Context and Scope）

**ビジネスコンテキスト**（ユーザー・外部システムとの関係）
```mermaid
C4Context
    title System Context Diagram
```

**技術コンテキスト**（通信プロトコル・インフラ）

| 通信相手 | プロトコル | 形式 | 用途 |
|---------|----------|------|------|

#### §4. 解決戦略（Solution Strategy）

| 品質目標 | アプローチ | 採用技術 |
|---------|----------|---------|

#### §5. ビルディングブロック（Building Block View）

**C4 Level 2: Container Diagram**
```mermaid
C4Container
    title Container Diagram
```

**C4 Level 3: Component Diagram**（主要コンテナの内部構造）
```mermaid
C4Component
    title Component Diagram
```

**コンポーネント一覧**

| コンポーネント名 | 種別 | 責務 | 主要ファイル |
|----------------|------|------|-------------|

#### §6. ランタイム（Runtime View）

主要ユースケース3-5個のシーケンス図。
```mermaid
sequenceDiagram
```

#### §7. デプロイ（Deployment View）

本番環境・開発環境の構成。【推測】と明記してよい。
```mermaid
C4Deployment
    title Deployment Diagram
```

| 環境 | インフラ | 用途 |
|------|---------|------|

#### §8. 横断的関心事（Crosscutting Concepts）

以下の各項目について、コードでの実装状況を記述：
- **認証・認可**: 方式、トークン管理、ロール設計
- **エラーハンドリング**: パターン、例外処理、ユーザーへの通知
- **ログ**: ログレベル、出力先、構造化ログの有無
- **バリデーション**: 入力検証の方針、フレームワーク機能の活用状況
- **セキュリティ**:
  - CSRF保護の実装状況
  - XSS対策の実装状況
  - SQLインジェクション対策の実装状況
  - **ロール×機能アクセスマトリクス**: 全ロール × 全機能 × 全操作（CRUD + 特殊操作）の許可/拒否を網羅的なマトリクス表で出力する。ロール定義ファイル（config/access-roles.php, middleware等）を読み、全組み合わせを列挙すること。

  | 機能 | 操作 | admin | board | general_mgr | center_mgr | staff | sale | head_office | director | deputy_dir | accountant |
  |------|------|-------|-------|-------------|------------|-------|------|-------------|----------|------------|------------|
  | スタッフ管理 | 一覧 | ○ | ○ | ○ | ... |
  | スタッフ管理 | 作成 | ○ | × | × | ... |

  ○=許可 ×=拒否 △=条件付き（条件を注記）
- **永続化**: ORM, キャッシュ, セッション管理
- **非同期処理**: キュー, バッチ, スケジューラ

#### §9. 設計判断（Architecture Decisions）

→ セクション D（MADR形式）で詳細に記述。ここではサマリーのみ。

#### §10. 品質要件（Quality Requirements）

**品質ツリー**

| 品質属性 | 具体的なシナリオ | 優先度 |
|---------|----------------|--------|

例: 性能 → 「ダッシュボード画面が3秒以内に表示される」

#### §11. リスクと技術的負債（Risks and Technical Debt）

| # | リスク/負債 | 該当箇所 | 深刻度 | 改善案 | 工数 |
|---|-----------|---------|--------|--------|------|

#### §12. 用語集（Glossary）

| 用語 | 定義 |
|------|------|

---

### B. 人間向けドキュメント（ストーリー形式）

1. 背景：なぜこの機能が必要か
2. 処理の流れ：ユーザー視点で何が起きるか
3. 設計意図：なぜこの構造になっているか
4. 読み解くポイント：最初に押さえるべきこと

---

### C. レベル別説明

**⚠️ 全ドキュメントの先頭にヘッダー情報を含める:**
```
> 生成日: {今日の日付} | 対象: {対象パス} | ステータス: DRAFT | ツール: knowledge-asset-tool
```

**C-1. プロ向け（エンジニア）**
- 技術詳細・設計意図・実装のポイント・用語制限なし
- 末尾に「関連ドキュメント」セクションを追加し、マニュアル・API リファレンス等へのリンクを記載

**C-2. 営業・ビジネス向け**
- 何ができるか・導入メリット・ビジネス価値・技術用語は最小限
- **定量効果の記述ルール（必須）:**
  - DB実データから算出可能な数値のみ定量表現に使用する
    （例: レコード件数、テーブル行数、モジュール数、ロール数）
  - 工数削減・コスト削減等の効果は「**効果（推定）**」と明記し、算出の前提条件を併記する
    （例: 「効果（推定）: 月XX時間の工数削減 ※前提: 1件あたりYY分の手作業がZZ件/月」）
  - 前提条件が不明な場合は定量表現を使わず、定性表現に留める
    （例: 「手作業による入力工数を大幅に削減」）
  - 「年間N件→0件」のように改善後をゼロと断言しない（ゼロは証明できない。「大幅に削減」に留める）
- 末尾に必ず**「次のアクション」セクション**を含める:
  - 導入ステップ（概算期間付き）
  - デモ・問い合わせ先の案内
  - よくある質問への回答

**C-3. 初心者エンジニア向け**
- わかりやすい説明・専門用語には必ず注釈・「なぜ」を重視
- **代表的なコード例を1-2個含める**（例: API呼び出し、Vuex action、Controller メソッド等の実コード抜粋）
- 末尾に必ず**「次のステップ」セクション**を含める:
  - 次に読むべきドキュメントへのリンク（マニュアル、アーキテクチャ文書等）
  - 最初に試すべき操作（「ログインしてサマリー画面を確認する」等）
  - おすすめの学習順序

**⚠️ C-1〜C-3 の相対リンクパス規則（最重要）:**
レベル別説明は `docs/explanations/{機能名}/` に配置される。他ドキュメントへの相対パスは **2階層上** から辿る必要がある：
- `docs/architecture/{機能名}.md` → `../../architecture/{機能名}.md`
- `docs/manual/{機能名}/00-index.md` → `../../manual/{機能名}/00-index.md`
- `docs/decisions/{機能名}.md` → `../../decisions/{機能名}.md`

`../` （1階層上）では `docs/explanations/` 止まりでリンク切れになる。必ず `../../` を使うこと。

---

### D. 意思決定記録（MADR 4.0 形式）

各設計判断を以下のMADR形式で記述してください。

```markdown
# ADR-{番号}: {タイトル}

## Status
Proposed（推測ベース・要人間確認）

## Context and Problem Statement
（どんな状況で、何が問題だったか）

## Decision Drivers
- （判断に影響した要因を箇条書き）

## Considered Options
1. {採用された選択肢}
2. {代替案1}
3. {代替案2}

## Decision Outcome
Chosen option: "{採用された選択肢}", because {理由}【推測】

### Consequences
- Good, because {良い結果}
- Bad, because {悪い結果・トレードオフ}

## Pros and Cons of the Options

### {選択肢1}
- Good, because ...
- Bad, because ...

### {選択肢2}
- Good, because ...
- Bad, because ...
```

---

### E. RAG用ドキュメント（チャンク最適化済み）

以下のルールに従って RAG 検索に最適化されたドキュメントを生成：

1. **YAML frontmatter** を先頭に含める（タイトル・カテゴリ・キーワード・更新日）
2. 各セクションが**自己完結**すること（「上述の通り」「前述の」等の参照は禁止）
3. **階層見出し**（H2 > H3）をチャンク境界として使う
4. 1セクション **256-512トークン** を目安にする
5. 同じ概念に**複数の表現を使わない**（用語統一）

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

```
## SYSTEM_OVERVIEW
## COMPONENTS
## FLOW
## DEPENDENCY
## ERROR_HANDLING
## BUSINESS_RULES
## CONSTRAINTS
## KEYWORDS
```

---

### F. YAMLメタ情報

**⚠️ components にはAの§5で定義した全コンポーネントを漏れなく・個別に含めること。**
「MasterControllers」等の集約名は禁止。Controller 1つにつき1エントリ。Repository、Store も同様。
**⚠️ decisions にはDの全意思決定を漏れなく含めること（IDを飛ばさない）。**

```yaml
id: {機能名}
version: 1.0.0
last_updated: （今日の日付）
confidence: medium
arc42_version: "9.0"
components:
  - name: （コンポーネント名）
    type: （Controller / Repository / Model / Trait / Middleware / Store / Service）
    file: （ファイルパス）
flow: []
decisions:
  - id: （番号 — Dの全件）
    summary: （設計判断の要約）
    status: proposed
keywords: []
document_management:  # 検収成果物モード有効時のみ出力
  doc_id_prefix: "{prefix}"
  documents:
    - id: "{prefix}-DD-001"
      title: "詳細設計書"
      file: "manual/{name}/00-index.md"
      version: "1.0"
      status: "DRAFT"
    - id: "{prefix}-AD-001"
      title: "アーキテクチャ設計書"
      file: "architecture/{name}.md"
      version: "1.0"
      status: "DRAFT"
extensions:
  claude_memory_kit: null
  mcp_tool: null
  local_rag: null
```

---

### セルフレビュー（出力前に必ず実行）

`templates/quality-rules.md` §5 のセルフレビューチェックリストを実行すること。
品質評価には `templates/quality-rubric.md` のルーブリック（6軸×3段階）も参照可能。
以下は本コマンド固有の追加チェック：

1. **件数一致（追加）**: D の意思決定件数と F の decisions 件数の一致
2. **文書横断の数値整合**: ロール数、テーブル数、API数、画面数が全セクション（§1, §5, §12用語集, C-1〜C-3, D意思決定記録, Fメタ情報）で一致しているか
3. **ソースコード由来のtypo**: コード上の識別子をそのまま記載する場合、初出時に「（原文ママ）」を付記する

---

### 出力形式

以下の形式で出力してください。「{機能名}」は第2引数の値に置き換えてください。

```
--- FILE: docs/architecture/{機能名}.md ---
（A: arc42全セクション + B: 人間向けドキュメント）
（検収成果物モードの場合、先頭に templates/cover-page.md の内容を挿入する。
  DOC_ID は {prefix}-AD-001 形式で自動採番。VERSION は 1.0。
  STATUS は DRAFT。改訂履歴の初版エントリを自動挿入。）

--- FILE: docs/architecture/{機能名}.rag.md ---
（E: RAG用ドキュメント — YAML frontmatter付き）

--- FILE: docs/diagrams/{機能名}-context.mmd ---
（A §3: C4 System Context Diagram — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-container.mmd ---
（A §5: C4 Container Diagram — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-component.mmd ---
（A §5: C4 Component Diagram — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-sequence.mmd ---
（A §6: 正常系シーケンス図 — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-deployment.mmd ---
（A §7: デプロイ図 — 1ファイル1図）

--- FILE: docs/explanations/{機能名}/pro.md ---
（C-1: エンジニア向け）

--- FILE: docs/explanations/{機能名}/sales.md ---
（C-2: 営業向け）

--- FILE: docs/explanations/{機能名}/beginner.md ---
（C-3: 初心者向け）

--- FILE: docs/decisions/{機能名}.md ---
（D: MADR 4.0 形式の意思決定記録全件）

--- FILE: docs/meta/{機能名}.yaml ---
（F: YAMLメタ情報）
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

### 次のステップ

- MkDocs サイトを生成するには: `/project:generate-site`
- スライド資料を作成するには: `/project:analyze-slide {対象パス} {機能名}`
