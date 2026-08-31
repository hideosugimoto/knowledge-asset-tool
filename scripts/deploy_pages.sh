#!/bin/bash
# GitHub Pages へのデプロイスクリプト
# Usage: bash scripts/deploy_pages.sh [--remote <name>]
#
# 前提: mkdocs build 済みで site/ が存在すること
#       nav を反映する場合は先に python3 scripts/generate_nav.py を実行すること
# 動作: gh-pages ブランチに site/ の内容をプッシュする
#
# 安全装置（いずれかに引っかかったら中止する）:
#   1. push 先 remote の可視性が PRIVATE でない
#   2. gh CLI が無い / 未認証で可視性を判定できない（fail closed）
#   3. scripts/check_leakage.py が CRITICAL / HIGH を検出した

set -euo pipefail

# 色付きメッセージ
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    cat <<'USAGE'
Usage: bash scripts/deploy_pages.sh [--remote <name>]

Options:
  --remote <name>   デプロイ先の git remote 名（既定: origin）
  -h, --help        このヘルプを表示する
USAGE
}

# ---------------------------------------------------------------------------
# 引数パース
# ---------------------------------------------------------------------------
REMOTE="origin"

while [ $# -gt 0 ]; do
    case "$1" in
        --remote)
            if [ $# -lt 2 ]; then
                error "--remote にはリモート名が必要です。"
                usage
                exit 1
            fi
            REMOTE="$2"
            shift 2
            ;;
        --remote=*)
            REMOTE="${1#--remote=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "不明な引数: $1"
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# remote URL から owner/repo を解決する
# ---------------------------------------------------------------------------
resolve_owner_repo() {
    # 対応形式:
    #   https://github.com/owner/repo(.git)
    #   git@github.com:owner/repo(.git)
    #   ssh://git@github.com/owner/repo(.git)
    local url="$1"
    url="${url%.git}"
    url="${url%/}"
    case "$url" in
        *github.com:*)  echo "${url##*github.com:}" ;;
        *github.com/*)  echo "${url##*github.com/}" ;;
        *)              echo "" ;;
    esac
}

# ---------------------------------------------------------------------------
# 1. 前提チェック
# ---------------------------------------------------------------------------
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$REPO_ROOT" ]; then
    error "git リポジトリ内で実行してください。"
    exit 1
fi

if [ ! -d "site" ]; then
    error "site/ ディレクトリが見つかりません。先に 'mkdocs build' を実行してください。"
    exit 1
fi

if ! command -v mkdocs &> /dev/null; then
    error "mkdocs がインストールされていません。'pip3 install mkdocs-material' を実行してください。"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. リモートの確認
# ---------------------------------------------------------------------------
if ! git remote get-url "$REMOTE" &> /dev/null; then
    error "リモート '$REMOTE' が見つかりません。"
    error "利用可能なリモート: $(git remote | tr '\n' ' ')"
    exit 1
fi

REMOTE_URL=$(git remote get-url "$REMOTE")
info "デプロイ先リモート: $REMOTE ($REMOTE_URL)"

# ---------------------------------------------------------------------------
# 3. 可視性チェック（fail closed）
# ---------------------------------------------------------------------------
OWNER_REPO=$(resolve_owner_repo "$REMOTE_URL")
if [ -z "$OWNER_REPO" ]; then
    error "リモート URL から owner/repo を解決できませんでした: $REMOTE_URL"
    error "GitHub 以外のホストへのデプロイは可視性を判定できないため中止します。"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    error "gh (GitHub CLI) がインストールされていません。"
    error "可視性を判定できないため、安全のためデプロイを中止します。"
    error "  brew install gh && gh auth login"
    exit 1
fi

VISIBILITY=$(gh repo view "$OWNER_REPO" --json visibility -q '.visibility' 2>/dev/null || true)

if [ -z "$VISIBILITY" ]; then
    error "リポジトリ $OWNER_REPO の可視性を取得できませんでした（未認証 or 権限不足）。"
    error "可視性を判定できないため、安全のためデプロイを中止します。"
    error "  gh auth login"
    exit 1
fi

info "判定対象リポジトリ: $OWNER_REPO / 可視性: $VISIBILITY"

if [ "$VISIBILITY" != "PRIVATE" ]; then
    echo ""
    error "⛔ デプロイをブロックしました。"
    echo ""
    echo "  $OWNER_REPO は $VISIBILITY です。"
    echo "  site/ には分析対象システムの機密情報（DB構造、API仕様、"
    echo "  ビジネスロジック、画面設計等）が含まれます。"
    echo "  gh-pages へプッシュすると GitHub Pages で公開される可能性があります。"
    echo ""
    echo "  対処方法:"
    echo "    1. リポジトリを Private に変更する"
    echo "       gh repo edit $OWNER_REPO --visibility private"
    echo "    2. または site/ をローカルで直接閲覧・共有する"
    echo "       python3 -m mkdocs serve"
    echo ""
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. 情報漏洩スキャン
# ---------------------------------------------------------------------------
LEAKAGE_SCRIPT="${REPO_ROOT}/scripts/check_leakage.py"
if [ ! -f "$LEAKAGE_SCRIPT" ]; then
    error "scripts/check_leakage.py が見つかりません。安全のため中止します。"
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    error "python3 がインストールされていません。漏洩スキャンを実行できないため中止します。"
    exit 1
fi

info "情報漏洩スキャンを実行中..."
if ! python3 "$LEAKAGE_SCRIPT"; then
    echo ""
    error "⛔ 情報漏洩が検出されました。デプロイを中止します。"
    echo "  python3 scripts/check_leakage.py で詳細を確認してください。"
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. 確認プロンプト
# ---------------------------------------------------------------------------
echo ""
warn "$OWNER_REPO ($VISIBILITY) の gh-pages ブランチに site/ の内容をプッシュします。"
read -rp "続行しますか？ (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    info "キャンセルしました。"
    exit 0
fi

# ---------------------------------------------------------------------------
# 6. mkdocs gh-deploy 実行
# ---------------------------------------------------------------------------
info "GitHub Pages にデプロイ中..."
# nav 付きの設定 (mkdocs.generated.yml) があればそれを使う。
# 無い場合は mkdocs.yml で（nav は docs/ の構成から自動生成される）。
if [ -f "${REPO_ROOT}/mkdocs.generated.yml" ]; then
    info "設定ファイル: mkdocs.generated.yml"
    mkdocs gh-deploy --config-file "${REPO_ROOT}/mkdocs.generated.yml" --remote-name "$REMOTE" --force
else
    warn "mkdocs.generated.yml が無いため mkdocs.yml でデプロイします。"
    warn "nav を反映するには先に python3 scripts/generate_nav.py を実行してください。"
    mkdocs gh-deploy --remote-name "$REMOTE" --force
fi

info "デプロイ完了！"
info "数分後に GitHub Pages で閲覧可能になります。"
info "URL: リポジトリの Settings > Pages で確認してください。"
