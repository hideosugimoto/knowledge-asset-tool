# knowledge-asset-tool

[English](./README_EN.md)

コードから「理解しやすく再利用可能な知識資産」を自動生成するツール。
**APIキー不要。Claude Codeのサブスクリプションのみで動作します。**

## このツールが解決する問題

エンジニアがドキュメントを書かない理由は3つ：

- **コストが高い** → AIが自動生成するのでコストゼロ
- **すぐ腐る** → コードから直接生成するので常に最新
- **誰も読まない** → RAG・スライド・レベル別説明で「使われる」形式に

## クイックスタート

### Step 1: テンプレートからリポジトリを作成

> **⚠️ セキュリティ警告: 必ず Private リポジトリとして作成してください。**
> 生成ドキュメントには分析対象のDB構造・API仕様・ビジネスロジック等が含まれます。
> Public リポジトリにプッシュすると情報漏洩になります。
> （万が一 Public に docs/ をプッシュした場合は GitHub Actions が自動削除します）

**方法A: コマンドライン（推奨・確実にPrivateになります）**

```bash
gh repo create my-knowledge-assets \
  --template hideosugimoto/knowledge-asset-tool \
  --private \
  --clone
cd my-knowledge-assets
```

**方法B: GitHub UI**

右上の **"Use this template"** → **"Create a new repository"** をクリック。

> **⛔ 「Private」を必ず選択してください。Public を選ぶと情報漏洩リスクがあります。**

### Step 2: ローカルにクローン（方法Bのみ）

```bash
git clone https://github.com/{あなたのユーザー名}/my-knowledge-assets.git
cd my-knowledge-assets
```

### Step 3: 依存ツールのインストール

```bash
npm install -g @marp-team/marp-cli
npm install -g @mermaid-js/mermaid-cli
pip install pyyaml
```

### Step 4: Claude Code を起動して実行

```bash
claude
```

```
/go
```

質問に答えて「OK」→ あとは待つだけ。以下が全自動で実行されます：
- コード分析・ドキュメント生成
- Mermaid図 → SVG変換
- MkDocsサイトビルド
- 目次・ポータル生成

### Step 5: 生成物を確認

```bash
# MkDocsサイトで確認（検索・ナビゲーション付き）
mkdocs serve
# → http://localhost:8000

# または直接スライドを開く
open docs/slides/機能名-エンジニア.html
```

### Step 6: Private リポジトリの場合のみ — GitHub公開

```bash
# リポジトリがPrivateか確認（Publicならブロックされます）
python scripts/push_docs.py --check-only

# Privateの場合のみ docs/ をプッシュ
python scripts/push_docs.py
```

---

## コマンド一覧

| コマンド | 出力内容 | 用途 |
|----------|---------|------|
| `/go` | 対話式ウィザード | **おすすめ。質問に答えるだけで全自動実行** |
| `/project:analyze` | 構造・詳細・レビュー | コードレビュー・設計確認 |
| `/project:analyze-full` | 全セクション | 完全ドキュメント化 |
| `/project:analyze-rag` | RAG・YAML | 知識ベース蓄積 |
| `/project:analyze-share` | レベル別・ストーリー | チーム共有・説明資料 |
| `/project:analyze-slide` | スライド資料 | HTML・PDF・PPTX生成（20-30枚全機能網羅） |
| `/project:manual` | 完全マニュアル | 全画面・全機能・全API・OpenAPI・画面遷移図 |
| `/project:manual-slide` | Slidedocs | マニュアルから読む用スライド作成 |
| `/project:user-guide` | 操作ガイド | エンドユーザー向け。技術用語なし・全画面ステップバイステップ |
| `/project:quick-ref` | クイックリファレンス | A4 1枚の早見表。印刷してデスクに貼れる |
| `/project:generate-ai-docs` | AI向けドキュメント | llms.txt + AGENTS.md 生成 |
| `/project:generate-site` | ドキュメントサイト | MkDocs Material で検索付きWebサイト生成 |

### /go の出力モード

| モード | 内容 |
|--------|------|
| a) 標準 | 構造・詳細・設計レビュー |
| b) 完全版 | 全セクション（プロ/営業/初心者向け説明、RAG、意思決定ログ含む） |
| c) RAG用 | 最小出力（RAGドキュメント + YAMLメタ情報のみ） |
| d) 共有用 | レベル別説明 + ストーリー形式ドキュメント |
| e) スライド | 20-30枚の全機能網羅スライド（HTML/PDF/PPTX） |
| f) 完全マニュアル | 全画面・全機能・全API・OpenAPI・画面詳細設計 |
| g) Slidedocs | マニュアルから読む用スライド（Duarte Slidedocs形式） |
| h) AI向け | llms.txt + AGENTS.md |
| j) サイト | MkDocs Material で検索付きドキュメントサイト |
| k) 操作ガイド | エンドユーザー向け。技術用語なし・全画面ステップバイステップ手順書 |
| l) クイックリファレンス | A4 1枚の早見表。印刷してデスクに貼れる |
| i) 全部 | 全成果物を一括生成 |

## 生成されるファイル構成

```
docs/
├── architecture/
│   ├── {名前}.md              # arc42 アーキテクチャ文書
│   └── {名前}.rag.md          # RAG用ドキュメント
├── diagrams/
│   ├── {名前}-*.mmd           # Mermaid図（ソース）
│   └── {名前}-*.svg           # SVG変換済み図
├── explanations/
│   └── {名前}/
│       ├── pro.md             # エンジニア向け
│       ├── sales.md           # 営業向け
│       └── beginner.md        # 初心者向け
├── decisions/
│   └── {名前}.md              # 意思決定記録（MADR 4.0）
├── manual/
│   └── {名前}/
│       ├── 00-index.md             # 目次
│       ├── 01-overview.md          # システム概要
│       ├── 02-screen-flow.md       # 画面遷移図
│       ├── 03-features.md          # 機能カタログ（全機能）
│       ├── features/               # 機能別詳細（1機能1ファイル）
│       ├── 04-api-reference.md     # APIリファレンス（全API）
│       ├── 05-data-model.md        # データモデル・ER図・データディクショナリ
│       ├── 06-screen-specs.md      # 画面詳細設計（全画面）
│       ├── 07-walkthrough.md       # ユースケース別ウォークスルー
│       ├── 08-review.md            # 設計評価・改善案
│       ├── 09-user-guide.md        # エンドユーザー操作ガイド
│       ├── 10-quick-reference.md   # A4 1枚クイックリファレンス
│       ├── db-reconciliation.md    # コード⇔DB突合レポート（DB分析時のみ）
│       └── openapi.yaml            # OpenAPI 3.x 定義
├── meta/
│   └── {名前}.yaml            # メタ情報（機械可読）
├── slides/
│   ├── {名前}-エンジニア.html  # コード分析ベーススライド
│   ├── {名前}-営業.html
│   ├── {名前}-初心者.html
│   ├── {名前}-manual-エンジニア.html  # マニュアルベーススライド
│   ├── {名前}-manual-営業.html
│   └── {名前}-manual-初心者.html
├── {名前}-llms.txt            # AI向けインデックス
├── {名前}-AGENTS.md           # AIエージェント向け作業指示書
├── {名前}-index.md            # プロジェクト固有の目次
└── index.md                   # 全プロジェクトのポータル
```

## セキュリティ: 4層の情報漏洩防止

生成ドキュメントには分析対象の機密情報が含まれます。テンプレートから作成されたリポジトリに以下の防御が **自動で適用** されます。

```
第1層: .gitignore       — git add . で docs/ が混入しない（ユーザー操作不要）
第2層: AI指示ファイル   — AIツールに git add -f docs/ を禁止（自動読み込み）
第3層: GitHub Actions   — Public に docs/ がプッシュされたら即自動削除 + Issue通知
第4層: push_docs.py     — Private確認付きの唯一の正規プッシュ手段
```

| 防御層 | 対象 | 仕組み | テンプレート自動適用 |
|--------|------|--------|:------------------:|
| `.gitignore` | 人間 + AI全般 | `git add .` で docs/, site/ をブロック | はい |
| AI指示ファイル | Claude Code, Copilot, Cursor, Windsurf, Codex | `git add -f docs/` と `.gitignore` 改変を禁止 | はい |
| GitHub Actions | 全て（最終防衛線） | Public + docs/ 検出 → 自動削除コミット + Issue作成 | はい |
| `push_docs.py` | 正規の公開手段 | `gh repo view` で Private 判定後にのみ push | はい |

### AI指示ファイル

以下のファイルがテンプレートに含まれ、各AIツールが自動で読み込みます：

| ファイル | 対象ツール |
|---------|----------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Claude Code, Codex, 共通標準 |
| `.cursorrules` | Cursor |
| `.windsurfrules` | Windsurf |
| `.github/copilot-instructions.md` | GitHub Copilot |

## 品質保証パイプライン

全コマンドに組み込まれた多層の品質保証により、正確で実用的なドキュメントを生成します。

### 分析プロセス

```
Step 0:  ファクト収集 + ビジネスコンテキスト + フレームワーク選択（1パス）
Step 0b: ストーリーライン設計（ピラミッドプリンシプル）
Step 0c: 重要度マッピング（Tier 1/2/3）
→ 本文執筆（思考フレームワーク適用）
→ セルフレビュー（9項目チェック）
→ 品質チェックスクリプト（リンク整合性・用語一貫性・図リンク逆引き・スライド溢れ）
→ verify_docs.py（機械的検証）
```

### 品質保証の仕組み

| 仕組み | 内容 |
|--------|------|
| **ファクト収集** | コードから事実をYAMLで構造化抽出。ファクトにない情報の記載を禁止 |
| **ソース引用** | 全記述に `(file:line)` で出典を明記。検証可能性を担保 |
| **思考フレームワーク** | MECE・So What?・4+1 View・ATAM等をシステム特性で自動選択 |
| **ストーリーライン設計** | テンプレート埋めではなく結論先行のピラミッド構造で設計 |
| **重要度マッピング** | コア機能は深掘り、補助機能はサマリーのメリハリ |
| **セルフレビュー** | ファクト突合・件数一致・引用検証・論理的深み・ビジネス接続を検証 |
| **品質チェックスクリプト** | リンク切れ検出、用語一貫性、図リンク逆引き、スライド溢れ検出 |
| **自動検証スクリプト** | ファイルパス・テーブル名・エンドポイントの実在性を機械チェック |

### 自動検証

```bash
# 生成ドキュメントの記述がソースコードと一致するか検証
python scripts/verify_docs.py \
  --docs-dir ./docs \
  --source-dir /path/to/target/project \
  --name feature-name
```

検証内容:
- **(A)** ファイルパス引用の実在チェック（ファイル存在 + 行番号範囲）
- **(B)** テーブル名の突合（DB分析 / マイグレーション / モデル定義と照合）
- **(C)** APIエンドポイントの突合（ルーティング定義と照合）

### テンプレートファイル

| ファイル | 用途 |
|---------|------|
| `templates/thinking-frameworks.md` | 分析思考フレームワーク（選択マトリクス付き） |
| `templates/business-context.md` | ビジネスコンテキスト収集ガイド |
| `templates/quality-rubric.md` | 品質ルーブリック（6軸×3段階） |
| `templates/storyline-design.md` | ストーリーライン設計ガイド |
| `templates/priority-analysis.md` | 重要度ベース分析ガイド（Tier 1/2/3） |
| `templates/fact-schema.yaml` | ファクト収集スキーマ定義 |

## 適用している国際標準・ベストプラクティス

| 成果物 | 適用標準 | 出典 |
|--------|---------|------|
| アーキテクチャ文書 | **arc42** テンプレート v9 | [arc42.org](https://arc42.org/) |
| アーキテクチャ図 | **C4 Model** | [c4model.com](https://c4model.com/) |
| API リファレンス | **OpenAPI 3.x** | [openapis.org](https://spec.openapis.org/) |
| 意思決定記録 | **MADR 4.0** | [adr.github.io/madr](https://adr.github.io/madr/) |
| データモデル | **Crow's Foot** + データディクショナリ | 業界標準 |
| スライド（読む用） | **Duarte Slidedocs** | [duarte.com](https://www.duarte.com/resources/books/slidedocs/) |
| RAG ドキュメント | チャンク最適化 + YAML frontmatter | 業界ベストプラクティス |
| AI 向け概要 | **llms.txt** 仕様 | [llmstxt.org](https://llmstxt.org/) |
| AI エージェント指示 | **AGENTS.md** 標準 | [agents.md](https://agents.md/) |

## DB連携分析

コードだけでなくデータベースの状態も加味した正確なドキュメントを生成できます。

`/go` ウィザードがプロジェクトの `.env`・Prisma・Spring設定等からDB接続設定を自動検出し、ユーザーに確認した上で分析に組み込みます。

### 対応する分析方法

| 方法 | 説明 | DB接続 |
|------|------|--------|
| ライブDB接続 | ユーザー指定のコマンドでSQLを実行 | 必要 |
| SQLダンプ | `.sql` ファイルからスキーマを解析 | 不要 |
| マイグレーション | マイグレーションファイルからテーブル構造を推定 | 不要 |

### DB分析で改善される点

- **マスタデータの有効/無効状態**: `is_active=0` のデータを参照する機能に【DB無効】と注記
- **機能フラグ**: DBの設定テーブルで無効化されている機能に【機能OFF】と注記
- **表示名・ラベル**: DBに格納された日本語ラベルをドキュメントに反映
- **コード⇔DB突合**: テーブル/カラムの不整合をリスクとして報告

### 単体利用

```bash
# ライブDB接続
python3 scripts/scan_database.py --sql-command "mysql -u root -N mydb"
python3 scripts/scan_database.py --sql-command "docker exec -i db mysql -u root mydb"
python3 scripts/scan_database.py --sql-command "psql -U postgres -t mydb" --db-type postgresql

# SQLダンプを解析
python3 scripts/scan_database.py --dump-file schema.sql --output db-manifest.json

# プロジェクトからDB設定を自動検出
python3 scripts/scan_database.py --source-dir /path/to/project
```

## ツール更新の自動通知

`.github/workflows/sync-template.yml` により、毎週月曜に元リポジトリの更新を自動チェック。
更新があれば PR が作成されます。**docs/ は絶対に上書きされません。**

## 将来の拡張（v2予定）

- claude-memory-kit 統合（セッション間で自動参照）
- ローカルRAG検索（ask-my-codebase コマンド）
- MCPツール定義への自動変換

詳細は [EXTENSION.md](./EXTENSION.md) を参照してください。
