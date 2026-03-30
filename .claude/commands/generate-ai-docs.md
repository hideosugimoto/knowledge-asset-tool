# /project:generate-ai-docs

AI エージェント向けのプロジェクトドキュメントを生成します。
llms.txt（AI向けプロジェクト発見用）と AGENTS.md（クロスツールAI指示書）を出力します。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: 対象パス
- 第2引数: プロジェクト名

```
例: /project:generate-ai-docs ./src my-project
例: /project:generate-ai-docs /Users/.../my-project my-app
```

以降、第1引数を「対象パス」、第2引数を「プロジェクト名」として参照します。

## 実行内容

対象パスのコードを分析し、以下の2つのファイルを生成してください。

---

### 1. llms.txt（llms.txt 仕様準拠）

**仕様**: https://llmstxt.org/
Jeremy Howard（Answer.AI）が提唱した、AIがプロジェクトを発見・理解するための標準形式。

**形式ルール**:
- H1: プロジェクト名（1つだけ）
- blockquote: プロジェクトの簡潔な説明（1-2文）
- H2 セクションでドキュメントへのリンクを分類
- 「## Optional」セクションにコンテキストに余裕がある場合に読むべきリソースを配置
- リンク形式: `- [タイトル](パス): 説明`

```markdown
# {プロジェクト名}

> {プロジェクトの1-2文の説明}

## Architecture
- [Architecture Document](docs/architecture/{名前}.md): arc42形式のアーキテクチャドキュメント
- [System Context](docs/diagrams/{名前}-context.mmd): C4 System Context Diagram
- [Container Diagram](docs/diagrams/{名前}-container.mmd): C4 Container Diagram

## API
- [API Reference](docs/manual/{名前}/04-api-reference.md): 全APIエンドポイント一覧
- [OpenAPI Spec](docs/manual/{名前}/openapi.yaml): OpenAPI 3.x 定義

## Data Model
- [Data Model](docs/manual/{名前}/05-data-model.md): テーブル一覧・ER図・データディクショナリ

## Features
- [Feature Catalog](docs/manual/{名前}/03-features.md): 全機能の詳細仕様
- [Screen Specs](docs/manual/{名前}/06-screen-specs.md): 画面詳細設計

## Decisions
- [ADR](docs/decisions/{名前}.md): MADR形式の設計意思決定記録

## Optional
- [RAG Document](docs/architecture/{名前}.rag.md): RAG検索用ドキュメント
- [Walkthrough](docs/manual/{名前}/07-walkthrough.md): ユースケース別ウォークスルー
- [Design Review](docs/manual/{名前}/08-review.md): 設計評価・改善案
- [Engineer Explanation](docs/explanations/{名前}/pro.md): エンジニア向け説明
- [Sales Explanation](docs/explanations/{名前}/sales.md): 営業向け説明
- [Beginner Explanation](docs/explanations/{名前}/beginner.md): 初心者向け説明
```

**⚠️ リンク先のファイルが実際に存在するか確認し、存在するもののみ列挙すること。**
存在しないファイルへのリンクは含めない。

**モジュール有効性チェック**: `.cache/facts-{名前}.yaml` が存在する場合、disabled_modules に含まれるモジュールの機能は Features セクションに列挙しない。llms.txt は AI が読むため、無効モジュールを含めると誤解を招く（`quality-rules.md` §4a 参照）。

---

### 2. AGENTS.md（AGENTS.md 標準準拠）

**仕様**: https://agents.md/
OpenAI Codex が提唱し、現在はオープン標準。
Claude Code, Codex, Copilot, Cursor, Windsurf 等のAIツールが共通で読み込む。

**形式ルール**:
- 標準的な Markdown
- プロジェクトのルートに配置
- 階層的に配置可能（サブディレクトリに置くとそのディレクトリ固有のルールになる）

以下のセクションを含めてください：

```markdown
# {プロジェクト名}

## Overview
（システムの目的と概要を2-3行で）

## Tech Stack
（言語・フレームワーク・バージョン。箇条書き。）

## Project Structure
（主要ディレクトリとその役割。ツリー形式。）

## Build & Run
（ローカル環境でのビルド・起動手順。コマンド付き。）

## Test
（テストの実行方法。テストフレームワーク名。）

## Code Style
（命名規則・コーディング規約・フォーマッター設定。）

## Architecture
（アーキテクチャパターン・レイヤー構成・主要コンポーネント。簡潔に。）

## Key Conventions
（このプロジェクト固有の慣習・ルール。AIが知っておくべきこと。）

## Known Issues
（既知の問題・Typo固定・workaround。）

## Documentation
（生成済みドキュメントへのパス。）
```

**⚠️ AGENTS.md は200行以内を目標にする。** 冗長な説明は避け、AIが作業に必要な最小限の情報を記載する。

---

## 出力形式

**⚠️ ファイル名にプロジェクト名を含める。** 複数プロジェクトの成果物が同じ docs/ に共存するため、
`llms.txt` や `AGENTS.md` を直接使うと前回のプロジェクトのファイルが上書きされる。

以下の形式で出力してください。

```
--- FILE: {プロジェクト名}-llms.txt ---
（llms.txt 仕様準拠のプロジェクト概要 + ドキュメントリンク）

--- FILE: {プロジェクト名}-AGENTS.md ---
（AGENTS.md 標準準拠のAIエージェント向け指示書）
```

出力後、以下を案内してください：
```
AI向けドキュメント生成完了！

  {プロジェクト名}-llms.txt  — AIがプロジェクトを発見・理解するためのインデックス
  {プロジェクト名}-AGENTS.md — AIエージェント向け作業指示書

  llms.txt はプロジェクトルートまたはWebサーバーのルートに配置してください。
  AGENTS.md はプロジェクトルートに配置してください。

  ※ /project:go 経由の場合はファイル保存が自動実行されます。
  単独実行の場合は手動で保存してください。
```
