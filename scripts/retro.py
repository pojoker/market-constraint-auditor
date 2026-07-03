#!/usr/bin/env python3
"""Retrospective sidecar/diagnosis summary."""

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
LOG = REPO / "data" / "diagnosis_log.jsonl"
CHECK = REPO / "scripts" / "check_thresholds.py"
SCORE = REPO / "scripts" / "score_regimes.py"


def load_log():
    rows = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def timeseries_dates():
    path = REPO / "data" / "timeseries.jsonl"
    dates = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                dates.append(json.loads(line)["date"])
            except Exception:
                pass
    return sorted(dates)


def check_sidecar(sidecar, date):
    res = subprocess.run(
        ["/Users/jowang/miniconda3/bin/python3", str(CHECK), "--sidecar", str(sidecar), "--date", date],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return res.returncode != 0


def best_regime(date):
    res = subprocess.run(
        ["/Users/jowang/miniconda3/bin/python3", str(SCORE), "--date", date],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if res.returncode != 0:
        return None
    data = json.loads(res.stdout)
    best = data.get("best_regime")
    row = data.get("rows", {}).get(best, {})
    return best, row.get("match_pct", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=5)
    args = ap.parse_args()
    log_rows = load_log()
    dates = timeseries_dates()
    sidecars = {p.stem.replace(".thresholds", "")[:8]: p for p in REPORTS.glob("*.thresholds.json")}
    results = []
    counts = {}
    schema_d = sum(1 for r in log_rows if r.get("schema") == "D")
    for row in log_rows:
        date = row.get("date")
        sidecar = sidecars.get(date)
        if not sidecar:
            results.append({"date": date, "status": "no-sidecar", "regime": row.get("regime")})
            continue
        future = [d for d in dates if d > date][: args.window]
        falsified = any(check_sidecar(sidecar, d) for d in future)
        confirmed_days = 0
        target_row = row.get("regime_row")
        for d in future:
            best = best_regime(d)
            if best and best[0] == target_row and best[1] > 60:
                confirmed_days += 1
        status = "falsified" if falsified else "confirmed" if confirmed_days >= 3 else "unresolved"
        key = row.get("regime") or "null"
        counts.setdefault(key, {"confirmed": 0, "falsified": 0, "unresolved": 0})
        counts[key][status] += 1
        results.append({
            "date": date,
            "status": status,
            "regime": row.get("regime"),
            "regime_row": target_row,
            "future_days": future,
        })
    print(json.dumps({
        "schema_d_share": round(schema_d / len(log_rows), 3) if log_rows else None,
        "counts": counts,
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
