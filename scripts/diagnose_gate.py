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
    # Dedup on the DATA date, not the ledger's `date`. The snapshot filename
    # stem == equity-anchor as_of == data date (verified invariant). The ledger
    # `date`, however, is the Beijing run-date = data date + 1, so comparing the
    # two collides on consecutive trading days (Mon-close diagnosed on Tue morning
    # is labeled Tue; Tue's own capture is also 20260707 -> false "already
    # diagnosed"). diagnosed_marks.txt records the data date of every completed
    # diagnosis, so both sides live in data-date space. The wrapper appends to it
    # only after a successful run (rc==0), so a crashed diagnosis is retried.
    diagnosed = repo / "data/diagnosed_marks.txt"
    diag_max = ""
    if diagnosed.exists():
        for line in diagnosed.read_text(encoding="utf-8").splitlines():
            d = line.strip()
            if len(d) == 8 and d.isdigit():
                diag_max = max(diag_max, d)
    if diag_max >= date_key:
        return f"SKIP already diagnosed (marks {diag_max} >= mark {date_key})"
    return f"GO {date_key}"


def main() -> int:
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(gate(repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
