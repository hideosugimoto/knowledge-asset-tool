<!-- このテンプレートは docs/ 直下に {NAME}-index.md として配置される前提 -->
<!-- 相対リンクは docs/ をルートとして解決される -->
# {NAME} ドキュメント

> 生成日: {DATE} | 対象: {TARGET_PATH} | ツール: knowledge-asset-tool

---

## 読む人別 クイックリンク

| あなたは... | まず読むべき資料 |
|------------|----------------|
| エンジニア（設計を知りたい） | [arc42 アーキテクチャ](architecture/{NAME}.md) → [API リファレンス](manual/{NAME}/04-api-reference.md) |
| エンジニア（初めて触る） | [初心者向け解説](explanations/{NAME}/beginner.md) → [完全マニュアル](manual/{NAME}/00-index.md) |
| 営業・ビジネス | [営業向け説明](explanations/{NAME}/sales.md) or [営業スライド](slides/{NAME}-営業.html) |
| エンドユーザー（操作方法） | [操作ガイド](manual/{NAME}/09-user-guide.md) → [早見表](manual/{NAME}/10-quick-reference.md) |
| AI エージェント | [{NAME}-llms.txt]({NAME}-llms.txt) / [{NAME}-AGENTS.md]({NAME}-AGENTS.md) |

---

## 1. アーキテクチャ文書

| 資料 | 内容 | ファイル |
|------|------|---------|
| arc42 全12セクション | システム全体の設計ドキュメント | [architecture/{NAME}.md](architecture/{NAME}.md) |
| RAG 用ドキュメント | AI 検索に最適化されたチャンク | [architecture/{NAME}.rag.md](architecture/{NAME}.rag.md) |
| 意思決定記録（MADR） | 設計判断と根拠 | [decisions/{NAME}.md](decisions/{NAME}.md) |
| YAML メタ情報 | 機械可読なコンポーネント一覧 | [meta/{NAME}.yaml](meta/{NAME}.yaml) |

---

## 2. 完全マニュアル

| 章 | 内容 | ファイル |
|----|------|---------|
| 目次 | 全章へのリンク | [00-index.md](manual/{NAME}/00-index.md) |
| 第1章 | システム概要・技術スタック | [01-overview.md](manual/{NAME}/01-overview.md) |
| 第2章 | 画面遷移図・画面一覧 | [02-screen-flow.md](manual/{NAME}/02-screen-flow.md) |
| 第3章 | 機能カタログ | [03-features.md](manual/{NAME}/03-features.md) |
| 第4章 | API リファレンス | [04-api-reference.md](manual/{NAME}/04-api-reference.md) |
| 第5章 | データモデル | [05-data-model.md](manual/{NAME}/05-data-model.md) |
| 第6章 | 画面詳細設計 | [06-screen-specs.md](manual/{NAME}/06-screen-specs.md) |
| 第7章 | ユースケース別ウォークスルー | [07-walkthrough.md](manual/{NAME}/07-walkthrough.md) |
| 第8章 | 設計評価・改善案 | [08-review.md](manual/{NAME}/08-review.md) |
| OpenAPI | Swagger/OpenAPI 3.0 定義 | [openapi.yaml](manual/{NAME}/openapi.yaml) |

### 第3章 機能カタログ（個別ファイル）

{FEATURES_TABLE}

---

## 3. 操作ガイド（エンドユーザー向け）

| 資料 | 内容 | ファイル |
|------|------|---------|
| 操作ガイド | 技術用語なし・ステップバイステップ手順書 | [09-user-guide.md](manual/{NAME}/09-user-guide.md) |
| クイックリファレンス | A4 1枚の早見表（印刷用） | [10-quick-reference.md](manual/{NAME}/10-quick-reference.md) |

---

## 4. レベル別説明

| 対象読者 | 内容 | ファイル |
|---------|------|---------|
| エンジニア | 技術詳細・設計意図・コード例付き | [pro.md](explanations/{NAME}/pro.md) |
| 営業・ビジネス | ビジネス価値・定量効果・導入ステップ | [sales.md](explanations/{NAME}/sales.md) |
| 初心者エンジニア | やさしい解説・用語注釈・学習順序 | [beginner.md](explanations/{NAME}/beginner.md) |

---

## 5. スライド資料

### コード分析ベース

| 対象読者 | HTML | PDF | PPTX |
|---------|------|-----|------|
| エンジニア | [HTML](slides/{NAME}-エンジニア.html) | [PDF](slides/{NAME}-エンジニア.pdf) | [PPTX](slides/{NAME}-エンジニア.pptx) |
| 営業 | [HTML](slides/{NAME}-営業.html) | [PDF](slides/{NAME}-営業.pdf) | [PPTX](slides/{NAME}-営業.pptx) |
| 初心者 | [HTML](slides/{NAME}-初心者.html) | [PDF](slides/{NAME}-初心者.pdf) | [PPTX](slides/{NAME}-初心者.pptx) |

### マニュアルベース（Slidedocs 形式）

| 対象読者 | HTML | PDF | PPTX |
|---------|------|-----|------|
| エンジニア | [HTML](slides/{NAME}-manual-エンジニア.html) | [PDF](slides/{NAME}-manual-エンジニア.pdf) | [PPTX](slides/{NAME}-manual-エンジニア.pptx) |
| 営業 | [HTML](slides/{NAME}-manual-営業.html) | [PDF](slides/{NAME}-manual-営業.pdf) | [PPTX](slides/{NAME}-manual-営業.pptx) |
| 初心者 | [HTML](slides/{NAME}-manual-初心者.html) | [PDF](slides/{NAME}-manual-初心者.pdf) | [PPTX](slides/{NAME}-manual-初心者.pptx) |

---

## 6. AI 向けドキュメント

| 資料 | 用途 | ファイル |
|------|------|---------|
| llms.txt | AI がプロジェクトを発見・理解するためのインデックス | [{NAME}-llms.txt]({NAME}-llms.txt) |
| AGENTS.md | AI エージェント向け作業指示書 | [{NAME}-AGENTS.md]({NAME}-AGENTS.md) |

---

## 7. ダイアグラム（Mermaid → SVG）

{DIAGRAMS_TABLE}

---

## 共有方法

### フォルダごと共有（推奨）

`site/` フォルダをそのままコピーするだけで、検索付きドキュメントサイトとして閲覧できます。

```
site/ をコピー → index.html をブラウザで開く
```

- 全文検索（日本語対応）
- ダークモード切替
- Mermaid 図の自動レンダリング
- ナビゲーション・目次の自動生成

### ローカルプレビュー

```bash
mkdocs serve
# → http://localhost:8000
```
