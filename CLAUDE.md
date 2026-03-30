# knowledge-asset-tool

コードから知識資産（ドキュメント、スライド、API仕様等）を自動生成するツール。

## セキュリティルール（最優先・違反禁止）

### 🔒 docs/ と site/ のプッシュ禁止

**以下の操作は、リポジトリが Private であることを確認するまで絶対に実行しないこと:**

1. `git add -f docs/` — 禁止
2. `git add -f site/` — 禁止
3. `.gitignore` から `docs/` や `site/` の行を削除・コメントアウト — 禁止
4. `git push --no-verify` — 禁止

**docs/ と site/ には分析対象システムの機密情報が含まれる:**
- データベース構造（テーブル名、カラム名、ER図）
- API仕様（全エンドポイント、認証方式、OpenAPI定義）
- ビジネスロジック（計算式、承認ワークフロー）
- 画面設計（フォーム仕様、テーブル定義）
- DB突合レポート（本番データの統計情報）

### docs/ をプッシュしたい場合

必ず `python scripts/push_docs.py --check-only` を先に実行し、Private であることを確認してから操作すること。

```bash
# 1. まず確認（これは安全）
python scripts/push_docs.py --check-only

# 2. Private の場合のみ実行（スクリプトが Public をブロックする）
python scripts/push_docs.py
```

直接 `git add -f docs/` を実行しないこと。必ず `push_docs.py` 経由で操作する。

### 🔍 プッシュ前の情報漏洩スキャン（必須）

**`git push` の前に必ず `python3 scripts/check_leakage.py` を実行すること。**
pre-push hook が自動実行するが、AI が `git push` する際も事前に手動実行して結果を確認する。

```bash
# プッシュ前に必ず実行
python3 scripts/check_leakage.py

# CRITICAL または HIGH が検出された場合はプッシュ禁止
# 該当箇所を汎用的な例（my-app, user@example.com 等）に差し替えてから再コミット
```

スキャン対象:
- 分析対象プロジェクト名（.cache/ と docs/ から自動検出）
- mkdocs.yml の nav 構造
- DB テーブル名（vtiger_*, wp_* 等）
- 実プロジェクト固有の URL パス・フィールド名

### .gitignore の変更禁止

`.gitignore` の以下の行を削除・変更してはならない:
```
docs/
site/
.cache/
```

## プロジェクト構造

```
scripts/          — ツールスクリプト群
templates/        — ドキュメントテンプレート
.claude/commands/ — Claude Code スラッシュコマンド
docs/             — 生成ドキュメント（.gitignore対象）
site/             — MkDocs ビルド出力（.gitignore対象）
.cache/           — DB分析キャッシュ（.gitignore対象）
```

## コマンド一覧

| コマンド | 用途 |
|---------|------|
| `/go` | **おすすめ。** 全成果物の一括生成ウィザード（質問→OK→全自動） |
| `/project:analyze` | コード分析（標準: 構造・詳細・レビュー） |
| `/project:analyze-full` | コード分析（完全版: arc42全12セクション + レベル別説明 + RAG + MADR） |
| `/project:analyze-rag` | RAG用ドキュメント + YAMLメタ情報のみ |
| `/project:analyze-share` | 共有用（レベル別説明 + ストーリー形式） |
| `/project:analyze-slide` | スライド生成（エンジニア/営業/初心者、HTML/PDF/PPTX） |
| `/project:manual` | 完全マニュアル（全画面・全機能・全API・OpenAPI・画面詳細設計） |
| `/project:manual-slide` | マニュアルからSlidedocs形式スライド生成 |
| `/project:user-guide` | エンドユーザー操作ガイド（技術用語なし・ステップバイステップ） |
| `/project:quick-ref` | A4 1枚クイックリファレンス（印刷用早見表） |
| `/project:generate-ai-docs` | AI向けドキュメント（llms.txt + AGENTS.md） |
| `/project:generate-site` | MkDocs Material 検索付きWebサイト生成 |
| `/project:customize` | テンプレート・設定のカスタマイズ |

`/go` は上記コマンドを内部で呼び出すウィザード。個別コマンドはエキスパート向け。

## コーディング規約

- Python スクリプトは `scripts/` に配置
- テンプレートは `templates/` に配置
- 生成物は `docs/` に出力（git管理対象外）
