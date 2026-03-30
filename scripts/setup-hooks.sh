#!/bin/bash
# setup-hooks.sh — .githooks/ のフックを .git/hooks/ にインストールする
#
# テンプレートからリポジトリを作成した後に一度だけ実行:
#   bash scripts/setup-hooks.sh
#
# または git の hooksPath を設定して自動適用:
#   git config core.hooksPath .githooks

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
  echo "❌ git リポジトリのルートで実行してください。"
  exit 1
fi

HOOKS_SRC="${REPO_ROOT}/.githooks"
HOOKS_DST="${REPO_ROOT}/.git/hooks"

if [ ! -d "$HOOKS_SRC" ]; then
  echo "❌ .githooks/ ディレクトリが見つかりません。"
  exit 1
fi

echo "🔧 git hooks をインストールします..."

for hook_file in "${HOOKS_SRC}"/*; do
  hook_name=$(basename "$hook_file")
  dst="${HOOKS_DST}/${hook_name}"

  if [ -f "$dst" ] && [ ! -L "$dst" ]; then
    echo "  ⚠️  ${hook_name}: 既存フックをバックアップ → ${hook_name}.bak"
    cp "$dst" "${dst}.bak"
  fi

  cp "$hook_file" "$dst"
  chmod +x "$dst"
  echo "  ✅ ${hook_name} をインストールしました"
done

echo ""
echo "✅ 完了。以下のフックがアクティブです:"
ls -1 "${HOOKS_SRC}" | sed 's/^/   - /'
echo ""
echo "💡 git config core.hooksPath .githooks を設定すると"
echo "   今後は自動で .githooks/ が使われます。"
