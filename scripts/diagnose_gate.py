#!/usr/bin/env python3
"""Daily diagnosis gate, factored for wrapper use and isolated tests."""

import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def gate(repo: Path, now: datetime | None = None) -> str:
    snaps = sorted(glob.glob(str(repo / "data/snapshots/*.json")))
    if not snaps:
        return "SKIP no snapshots"
    latest = Path(snaps[-1])
    snapshot = json.loads(latest.read_text(encoding="utf-8"))
    cap = snapshot.get("_capture", {})
    now = now or datetime.now(timezone.utc)
    try:
        age_h = (now - datetime.fromisoformat(cap.get("captured_at", ""))).total_seconds() / 3600
    except Exception:
        age_h = 999
    date_key = latest.stem
    if age_h > 26:
        return f"SKIP stale capture ({age_h:.0f}h old, {date_key})"
    if cap.get("partial_session") is True:
        return f"SKIP partial session ({date_key})"
    if not cap.get("data_changed_vs_prev", False):
        return f"SKIP market closed (data unchanged, {date_key})"
    ledger = repo / "data/diagnosis_log.jsonl"
    ledger_max = ""
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                date = json.loads(line).get("date", "")
            except Exception:
                continue
            ledger_max = max(ledger_max, date or "")
    if ledger_max >= date_key:
        return f"SKIP already diagnosed (ledger {ledger_max} >= mark {date_key})"
    return f"GO {date_key}"


def main() -> int:
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(gate(repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
