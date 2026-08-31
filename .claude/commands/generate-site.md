# /project:generate-site

生成済みドキュメントから MkDocs Material テーマの静的サイトを構築します。
検索・ナビゲーション・ダークモード付きの見やすいドキュメントサイトを生成します。

**⚠️ 複数プロジェクト対応**: 既存の mkdocs.yml がある場合は新プロジェクトの nav を追記する。既存プロジェクトの nav を削除しない。

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: docs ディレクトリのパス（デフォルト: ./docs）
- 第2引数: システム名

```
例: /project:generate-site ./docs my-app
```

## 実行手順

### Step 1: MkDocs のインストール確認

まず `mkdocs --version` を実行してください。
コマンドが見つからない場合は以下でインストールしてください：

```bash
pip install mkdocs-material
```

### Step 2: nav を自動生成

nav は `scripts/generate_nav.py` で docs/ ディレクトリを走査して自動生成する。
手動で nav をハードコードしないこと。

```bash
python3 scripts/generate_nav.py
```

**出力先は `mkdocs.generated.yml`（.gitignore 対象）で、`mkdocs.yml` は変更されない。**
nav には分析対象のプロジェクト名・機能名・ファイルパスが並ぶため、
追跡ファイルである `mkdocs.yml` には書き込まない。
`mkdocs.generated.yml` は `INHERIT: mkdocs.yml` で静的設定を取り込む。

このスクリプトは以下を行う：
- docs/ 直下の `{name}-index.md` からプロジェクト一覧を検出
- 各プロジェクトの Architecture / Manual / features / User Guide / Explanations / Decisions / AI Docs を走査
- 実在するファイルのみ nav に含める
- 機能タイトルは Markdown ファイルの `# 見出し` から自動取得
- `mkdocs.generated.yml` を生成（`mkdocs.yml` は読み取りもしない）

`--dry-run` オプションで変更せずに結果を確認できる：
```bash
python3 scripts/generate_nav.py --dry-run
```

mkdocs.yml 自体が存在しない場合は、先にテンプレートから新規作成してからスクリプトを実行する。

### Step 3: index.md を確認

`docs/index.md` は go.md の Step 5-B で管理されるポータルファイルである。
**generate-site.md では index.md を生成・変更しない。** go.md 側に任せる。

index.md が存在しない場合のみ、go.md Step 5-B のテンプレートに従って新規作成する。

### Step 4: サイトをビルド・プレビュー

```bash
mkdocs serve -f mkdocs.generated.yml
```

ブラウザで `http://localhost:8000` を開くと検索付きドキュメントサイトが表示されます。

静的サイトとしてビルドする場合：
```bash
mkdocs build -f mkdocs.generated.yml
```

`-f mkdocs.generated.yml` を省くと nav が反映されず、docs/ のファイル構成から
自動生成された nav でビルドされる（ビルド自体は成功する）。

`site/` ディレクトリに HTML が生成されます。`file://` でも直接開けます（`use_directory_urls: false` のため）。

### Step 5: 完了報告

```
ドキュメントサイト生成完了！

  設定ファイル: mkdocs.yml（静的） + mkdocs.generated.yml（nav・gitignore対象）
  プレビュー: mkdocs serve -f mkdocs.generated.yml → http://localhost:8000
  ビルド: mkdocs build -f mkdocs.generated.yml → site/

  機能:
  - 全文検索（日本語対応）
  - ダークモード切替
  - Mermaid図の自動レンダリング
  - プロジェクト別タブナビゲーション
  - file:// でも直接開ける（use_directory_urls: false）
  - 目次の自動生成
```
