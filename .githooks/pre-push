#!/bin/bash
set -euo pipefail

# pre-push guard
# knowledge-asset-tool に docs/ が混入していないかチェックする

REPO_ROOT=$(git rev-parse --show-toplevel)

if [ -t 1 ]; then
  RED=$(tput setaf 1)
  YELLOW=$(tput setaf 3)
  GREEN=$(tput setaf 2)
  NC=$(tput sgr0)
else
  RED=""
  YELLOW=""
  GREEN=""
  NC=""
fi

printf "%s\n" "🔍 プッシュ前チェックを実行中..."

# 1. docs/ 配下のファイルがリポジトリに含まれていないか確認
DOCS_IN_GIT=$(git ls-files docs/ 2>/dev/null | grep -v '^docs/stylesheets/' || true)

if [ -n "$DOCS_IN_GIT" ]; then
  # docs/ が含まれている → Private リポジトリなら許可、それ以外はブロック
  VISIBILITY=""
  if command -v gh &>/dev/null; then
    VISIBILITY=$(gh repo view --json visibility -q '.visibility' 2>/dev/null || echo "")
  fi

  if [ "$VISIBILITY" = "PRIVATE" ]; then
    printf "%s%s%s\n" "$GREEN" "✅ Private リポジトリです。docs/ のプッシュを許可します。" "$NC"
  else
    printf "\n"
    printf "%s%s%s\n" "$RED" "⛔ docs/ のプッシュをブロックしました！" "$NC"
    printf "\n"
    if [ -z "$VISIBILITY" ]; then
      printf "%s\n" "リポジトリの可視性を確認できませんでした（gh CLI 未インストール or 未認証）。"
      printf "%s\n" "安全のため、可視性が確認できない場合もブロックします。"
    else
      printf "%s\n" "リポジトリの可視性: ${VISIBILITY}"
    fi
    printf "\n"
    printf "%s\n" "該当ファイル："
    echo "$DOCS_IN_GIT" | head -10 | sed 's/^/  /'
    TOTAL=$(echo "$DOCS_IN_GIT" | wc -l | tr -d ' ')
    if [ "$TOTAL" -gt 10 ]; then
      printf "  ... 他 %s ファイル\n" "$((TOTAL - 10))"
    fi
    printf "\n"
    printf "%s%s%s\n" "$YELLOW" "生成ドキュメントには機密情報（DB構造、API仕様、ビジネスロジック等）が" "$NC"
    printf "%s%s%s\n" "$YELLOW" "含まれる可能性があります。Public リポジトリへのプッシュは許可されません。" "$NC"
    printf "\n"
    printf "%s\n" "対処方法："
    printf "%s\n" "  (A) リポジトリを Private に変更する:"
    printf "%s\n" "      gh repo edit --visibility private"
    printf "%s\n" "  (B) docs/ をリポジトリから除去する:"
    printf "%s\n" "      git rm -r --cached docs/"
    printf "%s\n" "      git commit -m 'remove docs from tracking'"
    printf "\n"
    exit 1
  fi
fi

# 2. .gitignore に docs/ が含まれているか確認
if ! grep -q "^docs/" "${REPO_ROOT}/.gitignore" 2>/dev/null; then
  printf "\n"
  printf "%s%s%s\n" "$YELLOW" "⚠️  警告：.gitignore に docs/ が含まれていません。" "$NC"
  printf "%s\n" "   以下を .gitignore に追加することを強く推奨します："
  printf "%s\n" "   docs/"
  printf "\n"
  # 警告のみ・プッシュは止めない
fi

# 3. push対象のコミットに資産ファイルが含まれていないか確認
# pre-push hook は stdin で <local_ref> <local_sha> <remote_ref> <remote_sha> を受け取る
while IFS=' ' read -r _local_ref local_sha _remote_ref remote_sha; do
  # 資産ファイルのパターン: .rag.md と docs/ 配下の .yaml のみ
  # .github/*.yml, docker-compose.yaml 等の誤検知を防ぐ
  ASSET_PATTERN='\.(rag\.md)$|^docs/.*\.yaml$'

  if [ "$remote_sha" = "0000000000000000000000000000000000000000" ]; then
    # 新規ブランチ: ブランチ分岐点からチェック
    RANGE_START=$(git merge-base HEAD main 2>/dev/null || git rev-list --max-parents=0 HEAD | head -n1)
    SUSPICIOUS=$(git diff --name-only "${RANGE_START}..${local_sha}" 2>/dev/null | grep -E "$ASSET_PATTERN" | grep -v templates/ | grep -v tests/fixtures/ || true)
  else
    SUSPICIOUS=$(git diff --name-only "${remote_sha}..${local_sha}" 2>/dev/null | grep -E "$ASSET_PATTERN" | grep -v templates/ | grep -v tests/fixtures/ || true)
  fi

  if [ -n "$SUSPICIOUS" ]; then
    printf "\n"
    printf "%s%s%s\n" "$YELLOW" "⚠️  注意：資産ファイルの可能性があるファイルが含まれています：" "$NC"
    echo "$SUSPICIOUS" | sed 's/^/  /'
    printf "\n"
    read -rp "本当にプッシュしますか？ [y/N]: " confirm < /dev/tty
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
      printf "%s\n" "プッシュを中止しました。"
      exit 1
    fi
  fi
done

# 4. 情報漏洩スキャン（分析対象プロジェクトのデータ混入チェック）
LEAKAGE_SCRIPT="${REPO_ROOT}/scripts/check_leakage.py"
if [ -f "$LEAKAGE_SCRIPT" ] && command -v python3 &>/dev/null; then
  printf "%s\n" "🔍 情報漏洩スキャンを実行中..."
  if ! python3 "$LEAKAGE_SCRIPT"; then
    printf "\n"
    printf "%s%s%s\n" "$RED" "⛔ 情報漏洩が検出されました！プッシュをブロックします。" "$NC"
    printf "%s\n" ""
    printf "%s\n" "対処方法："
    printf "%s\n" "  1. python3 scripts/check_leakage.py で詳細を確認"
    printf "%s\n" "  2. 該当箇所を汎用的な例に差し替え"
    printf "%s\n" "  3. 再コミット後にプッシュ"
    printf "\n"
    exit 1
  fi
else
  printf "%s%s%s\n" "$YELLOW" "⚠️  check_leakage.py が見つからない、または python3 が未インストールです。" "$NC"
  printf "%s\n" "   漏洩スキャンをスキップします。"
fi

printf "%s%s%s\n" "$GREEN" "✅ チェック完了。プッシュを続行します。" "$NC"
exit 0
