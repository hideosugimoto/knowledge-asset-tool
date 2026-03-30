# /project:analyze

コードを分析して知識資産（arc42アーキテクチャドキュメント + C4図 + 設計レビュー）を生成します。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: 対象パス
- 第2引数: 機能名（ファイル名に使用）
- 第3引数（任意）: 目的

```
例: /project:analyze ./src/auth user-authentication 新メンバー引き継ぎ
```

以降、第1引数を「対象パス」、第2引数を「機能名」として参照します。

## 実行内容

あなたは優秀なソフトウェアアーキテクトです。
対象パスのコードを分析し、**arc42テンプレート**に従ってアーキテクチャドキュメントを生成してください。
図は**C4 Model**の記法に準拠し、Mermaidで記述してください。

---

### Step 0: ファクト収集（文章を書く前に必ず実行）

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

1. 図はすべてMermaid記法 + C4の抽象レベル（Context / Container / Component）を意識する
2. 複雑な処理は必ず分解して説明する
3. **DB分析結果がある場合（`.cache/db-*.json` が存在する場合）:**
   - DBスキーマ情報を読み込み、コード分析と照合すること
   - マスタテーブルの有効/無効フラグを確認し、無効化されたデータに依存する機能は【DB無効】と注記
   - テーブルの表示名・ラベルがDBに格納されている場合、コード上の変数名ではなくDB上の表示名を優先して記載
   - 設定テーブル・機能フラグの値を確認し、無効化されている機能は【機能OFF】と注記
   - コード上に参照があるがDBに存在しないテーブル/カラム、またはその逆の不整合を§11に記載

---

### arc42 アーキテクチャドキュメント（標準版）

標準版では arc42 の12セクションのうち、コードから導出可能な主要セクションを出力します。

#### §1. はじめに（Introduction and Goals）
- システムの目的（1文）
- 主要な機能要件（箇条書き3-5個）
- 主要な品質目標（性能・可用性・保守性等）
- 主要ステークホルダー（開発者・運用者・エンドユーザー等の関心事）

#### §2. 制約（Constraints）
- 技術的制約（言語・フレームワーク・バージョン）
- 組織的制約（チーム構成・デプロイ方針等）【推測】
- 規約（命名規則・コーディング規約）

#### §3. コンテキストと範囲（Context and Scope）

**C4 Level 1: System Context Diagram**
```mermaid
C4Context
    title System Context Diagram
```
（システムと外部アクター・外部システムの関係を示す）

#### §4. 解決戦略（Solution Strategy）
- 採用しているアーキテクチャパターン（MVC, レイヤード, マイクロサービス等）
- 主要な技術選定とその理由【推測】
- 品質目標を達成するためのアプローチ

#### §5. ビルディングブロック（Building Block View）

**C4 Level 2: Container Diagram**
```mermaid
C4Container
    title Container Diagram
```
（アプリケーション・データベース・外部サービス等の構成）

**コンポーネント一覧**

| コンポーネント名 | 種別 | 責務 | 主要ファイル |
|----------------|------|------|-------------|

#### §6. ランタイム（Runtime View）

主要なユースケースの処理フローをシーケンス図で示す。

**正常系**
```mermaid
sequenceDiagram
```

**異常系**
```mermaid
sequenceDiagram
```

#### §8. 横断的関心事（Crosscutting Concepts）
- 認証・認可の仕組み
- エラーハンドリングパターン
- ログ戦略
- データバリデーション方針
- セキュリティ対策

#### §11. リスクと技術的負債（Risks and Technical Debt）

| リスク/負債 | 該当箇所 | 深刻度（高/中/低） | 改善案 | 工数感 |
|-----------|---------|------------------|--------|--------|

---

### セルフレビュー（出力前に必ず実行）

`templates/quality-rules.md` §5 のセルフレビューチェックリストを実行すること。

---

### 出力形式

以下の形式で出力してください。「{機能名}」は第2引数の値に置き換えてください。

```
--- FILE: docs/architecture/{機能名}.md ---
（arc42 主要セクション §1,§2,§3,§4,§5,§6,§8,§11 の人間向けドキュメント）

--- FILE: docs/diagrams/{機能名}-context.mmd ---
（§3 C4 System Context Diagram — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-container.mmd ---
（§5 C4 Container Diagram — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-sequence.mmd ---
（§6 正常系シーケンス図 — 1ファイル1図）

--- FILE: docs/diagrams/{機能名}-sequence-error.mmd ---
（§6 異常系シーケンス図 — 1ファイル1図）

--- FILE: docs/decisions/{機能名}.md ---
（§11 リスクと技術的負債 + 改善案）
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

- スライド資料を作成するには: `/project:analyze-slide {対象パス} {機能名}`
- 完全マニュアルを生成するには: `/project:manual {対象パス} {機能名}`
