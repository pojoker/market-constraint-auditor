#!/bin/bash
# Best-effort local mirror and optional git push for market-auditor.

REPO="${1:-/Volumes/移动硬盘/market-constraint-auditor}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/Backups/market-auditor}"
LOG="${LOG:-$HOME/Library/Logs/market-auditor-capture.log}"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
warn() { echo "[$(ts)] WARN backup $*" >> "$LOG"; }

mkdir -p "$BACKUP_DIR" || {
    warn "mkdir failed"
    exit 0
}

rsync -a --delete "$REPO/data/" "$BACKUP_DIR/data/" >> "$LOG" 2>&1 || warn "data rsync failed"
rsync -a "$REPO/reports/" "$BACKUP_DIR/reports/" >> "$LOG" 2>&1 || warn "reports rsync failed"

if git -C "$REPO" remote >/dev/null 2>&1 && [[ -n "$(git -C "$REPO" remote)" ]]; then
    git -C "$REPO" push --quiet 2>/dev/null || warn "git push failed"
fi

exit 0
