# 将来拡張の設計メモ（v2以降）

## ⚠️ APIキーについて

このツールはv1・v2ともにAPIキーを使いません。
Claude Codeのサブスクのみで動作する設計を維持します。

## v2：claude-memory-kit 統合

docs/meta/*.yaml を claude-memory-kit の Skill として自動登録する。
次のClaudeCodeセッションで生成したドキュメントを自動参照できるようになる。

実装TODO：
- [ ] scripts/register_to_memory_kit.py の作成
- [ ] analyze コマンドに --register オプション追加

## v2：ローカルRAG検索

docs/ 配下をベクターDBに投入し、自然言語で検索できるようにする。
`ask-my-codebase "この処理どうなってたっけ"` で即答できる。

技術候補：
- ChromaDB（ローカル）
- SQLite + FTS5（軽量・依存なし）

## v2：MCPツール定義への自動変換

docs/meta/*.yaml から MCP ツール定義を自動生成する。
AIエージェントがコードベースの機能を直接「ツール」として呼べるようになる。
