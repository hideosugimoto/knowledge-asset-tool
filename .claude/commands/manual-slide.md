# /project:manual-slide

生成済みのマニュアルから **Slidedocs形式** のスライド資料を作成します。
コードの再分析は不要。マニュアルの内容をそのままスライド化します。

**Slidedocs とは**: Nancy Duarte が提唱した「読まれるスライド」形式。
通常のプレゼンスライド（1メッセージ/枚）と異なり、情報密度が高く、
非同期で読まれることを前提にした資料。引き継ぎ・レビュー・研修に最適。

**Slidedocs の原則**:
- 各スライドは単独で読んでも意味が通る（自己完結）
- テキスト量はプレゼン用より多くてよい（ただし簡潔に）
- 図・表・カードを多用して情報を構造化する
- 目次スライドで全体構成を示す
- スライド番号と章番号を一致させる

## 引数

$ARGUMENTS をスペース区切りで以下のように解釈してください：
- 第1引数: マニュアルのディレクトリパス（docs/manual/{システム名}）
- 第2引数: システム名（ファイル名に使用）
- 第3引数（任意）: 対象読者（エンジニア / 営業 / 初心者、省略時: エンジニア）
- 第4引数（任意）: 形式（html / pdf / pptx、省略時: html）

```
例: /project:manual-slide docs/manual/my-app my-app エンジニア html
例: /project:manual-slide docs/manual/my-app my-app 営業 pptx
```

以降、第1引数を「マニュアルパス」、第2引数を「システム名」、第3引数を「対象読者」、第4引数を「形式」として参照します。

## 実行手順

### Step 1: ツールの確認

まず `marp --version` を実行してください。
コマンドが見つからない場合は `npm install -g @marp-team/marp-cli` でインストールしてください。

次に `mmdc --version` を実行してください。
コマンドが見つからない場合は `npm install -g @mermaid-js/mermaid-cli` でインストールしてください。

### Step 2: マニュアルの読み込みと品質確認

マニュアルパス配下の全ファイルを読み込んでください。
読み込み後、以下を確認：
- 03-features.md の Tier 分類に disabled_modules（active: false）が混入していないか
- 混入していた場合はスライド化時に除外し、「技術的負債」スライドに移動する

ファイル一覧：
- 00-index.md
- 01-overview.md
- 02-screen-flow.md
- 03-features.md
- 04-api-reference.md
- 05-data-model.md
- 06-screen-specs.md
- 07-walkthrough.md
- 08-review.md

### Step 3: 対象読者に合わせたスライド構成を決定

マニュアルの内容を対象読者に合わせて再構成してください。

**エンジニア向け（25〜35枚）**

第1部：全体像（5枚）
1. タイトル（システム名・一言説明・技術スタック）
2. アーキテクチャ概要図（01-overview.md から）
3. 技術スタック詳細（01-overview.md から）
4. ディレクトリ構成と責務分担（01-overview.md から）
5. 全画面遷移図（02-screen-flow.md から）

第2部：機能カタログ（10〜15枚、03-features.md の全機能を1機能1スライドで）
- 各機能のコンポーネント構成・API・ビジネスルールを含める

第3部：画面詳細（5〜8枚、06-screen-specs.md から主要画面を抜粋）
- 主要画面のレイアウト・操作一覧・フォーム仕様
- 全画面は入れきれないので、最も複雑な5〜8画面を選択

第4部：データモデル（3〜4枚、05-data-model.md から）
- テーブル一覧の概要
- ER図（ドメインごと）
- データフロー

第5部：設計評価（3〜5枚、08-review.md から）
- 良い点・問題点・改善案・セキュリティ評価

**営業向け（12〜18枚）**

**⚠️ 最低4枚のSVG図を含めること。**

第1部：概要（3枚）
1. タイトル（ビジネス価値を一言で）
2. 機能マップ（03-features.md の全機能を図で — SVG必須）
3. 導入メリット（Before/After 図 — SVG必須）

第2部：機能紹介（6〜10枚、03-features.md から主要機能ごとに1スライド）
- 技術用語なし。「何ができるか」「誰が使うか」のみ
- 画面遷移図の簡略版（SVG必須）

第3部：システム活用（3〜5枚）
- 業務フロー全体図（07-walkthrough.md から — SVG必須）
- よくある質問と答え
- まとめ

**初心者向け（15〜22枚）**

第1部：はじめに（3枚）
1. タイトル（わかりやすい言葉で）
2. 何をするシステムか（01-overview.md から）
3. 登場人物と権限（04-api-reference.md のロール情報から）

第2部：画面ツアー（8〜12枚、06-screen-specs.md から全画面を1画面1スライドで）
- 各画面の役割をやさしく説明
- 画面レイアウト図を含める
- 専門用語には注釈をつける

第3部：仕組みの基本（3〜4枚）
- データの流れ（05-data-model.md から、簡略化）
- 代表的な操作の裏側（07-walkthrough.md から1〜2本）

第4部：まとめ（2〜3枚）
- 全体の画面遷移図（簡略版）
- 用語解説テーブル
- 次に学ぶべきこと

### Step 4: Mermaid 図を SVG に変換

マニュアル内の Mermaid 図および新たに作成した図を `.mmd` ファイルとして書き出し、SVG に変換してください。

```bash
mmdc -i /tmp/{システム名}-mslide-N.mmd -o /tmp/{システム名}-mslide-N.svg -t neutral -b transparent
```

### Step 5: Marp用Markdownファイルを生成

テーマCSSは `templates/slides/theme.css` を参照してください。
`/tmp/{システム名}-manual-{対象読者}.md` を生成してください。

**スライド作成の必須ルール**

1. テキストのみのスライドは禁止。全スライドにビジュアル要素を含める
2. 図を含むスライドは `.fig-text` レイアウト（左に図・右に説明）を活用
3. 1スライドの上限: 箇条書き5項目 / テーブル5行 / コード10行
4. マニュアルの内容と矛盾しないこと（マニュアルが Single Source of Truth）
5. セクション区切りには `<!-- _class: section-divider -->` を使う

**⚠️ スライド内画像の切れ防止ルール（最重要）**
- **縦方向のノード数は最大4つ**（flowchart TB / direction TB のステップ数）。5つ以上ある場合はステップを統合して4つ以下にする
- SVG が縦に長くなる図は、ステップを統合するか `flowchart LR`（横方向）に変更する
- `.fig-text` レイアウト内の SVG + 右カラムの要素を合計5つ以内に抑える（カード3枚 or テーブル4行が上限）
- 生成後に必ず PDF 出力して全ページの下端が切れていないか確認する。切れている場合はノード数を減らして再生成する

### Step 6: 変換実行

まず出力ディレクトリを作成：
```bash
mkdir -p docs/slides
```

形式に応じて以下のコマンドを実行：

HTML（デフォルト）:
```bash
marp /tmp/{システム名}-manual-{対象読者}.md --html -o docs/slides/{システム名}-manual-{対象読者}.html
```

PDF:
```bash
marp /tmp/{システム名}-manual-{対象読者}.md --html --pdf -o docs/slides/{システム名}-manual-{対象読者}.pdf
```

PPTX:
```bash
marp /tmp/{システム名}-manual-{対象読者}.md --html --pptx -o docs/slides/{システム名}-manual-{対象読者}.pptx
```

### Step 7: 中間ファイルのクリーンアップ

```bash
rm /tmp/{システム名}-mslide-*.mmd /tmp/{システム名}-mslide-*.svg
```

### Step 8: 完了報告

```
マニュアルベーススライド生成完了
   ソース：{マニュアルパス}
   ファイル：docs/slides/{システム名}-manual-{対象読者}.（拡張子）
   枚数：N枚
   対象読者：{対象読者}
   Mermaid図：N個（SVG変換済み）

他の形式に変換したい場合：
  HTML: marp /tmp/{システム名}-manual-{対象読者}.md --html -o docs/slides/{システム名}-manual-{対象読者}.html
  PDF:  marp /tmp/{システム名}-manual-{対象読者}.md --html --pdf -o docs/slides/{システム名}-manual-{対象読者}.pdf
  PPTX: marp /tmp/{システム名}-manual-{対象読者}.md --html --pptx -o docs/slides/{システム名}-manual-{対象読者}.pptx
```
