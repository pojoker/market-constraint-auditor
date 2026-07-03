#!/bin/bash
# 部署 market-constraint-auditor skill：repo（唯一真相）→ 用户级安装目录
# 用法：bash deploy.sh [--dry-run]
# 注：外置卷 noowners 挂载，直接 ./deploy.sh 会 permission denied——用 bash 调起即可，无需 sudo。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/skills/market-constraint-auditor/"
DST="$HOME/.claude/skills/market-constraint-auditor/"

DRY=""
[ "${1:-}" = "--dry-run" ] && DRY="--dry-run"

echo "📦 market-constraint-auditor 部署：$SRC → $DST ${DRY:+(dry-run)}"

# --delete 保证安装目录与 repo 完全一致（防止部署漂移，如 2026-06-07 的 BTC 增补只改了安装目录）
rsync -av --delete $DRY \
  --exclude '__pycache__/' \
  --exclude '.DS_Store' \
  "$SRC" "$DST"

echo "✅ 部署完成。校验差异（应只剩排除项）："
diff -rq "$SRC" "$DST" \
  --exclude __pycache__ --exclude .DS_Store \
  && echo "   无差异" || true
