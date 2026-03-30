#!/bin/bash
# GitHub Pages へのデプロイスクリプト
# Usage: bash scripts/deploy_pages.sh [--remote origin]
#
# 前提: mkdocs build 済みで site/ が存在すること
# 動作: gh-pages ブランチに site/ の内容をプッシュ

set -e

REMOTE="${1:-origin}"

# 色付きメッセージ
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. 前提チェック
if [ ! -d "site" ]; then
    error "site/ ディレクトリが見つかりません。先に 'mkdocs build' を実行してください。"
    exit 1
fi

if ! command -v mkdocs &> /dev/null; then
    error "mkdocs がインストールされていません。'pip3 install mkdocs-material' を実行してください。"
    exit 1
fi

# 2. リモートの確認
if ! git remote get-url "$REMOTE" &> /dev/null; then
    error "リモート '$REMOTE' が見つかりません。"
    exit 1
fi

REMOTE_URL=$(git remote get-url "$REMOTE")
info "デプロイ先: $REMOTE_URL"

# 3. 確認プロンプト
echo ""
warn "gh-pages ブランチに site/ の内容をプッシュします。"
read -p "続行しますか？ (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    info "キャンセルしました。"
    exit 0
fi

# 4. mkdocs gh-deploy 実行
info "GitHub Pages にデプロイ中..."
mkdocs gh-deploy --remote-name "$REMOTE" --force

info "デプロイ完了！"
info "数分後に GitHub Pages で閲覧可能になります。"
info "URL: リポジトリの Settings > Pages で確認してください。"
