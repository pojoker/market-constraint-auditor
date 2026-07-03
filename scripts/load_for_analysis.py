#!/usr/bin/env python3
"""
load_for_analysis.py — Layer 3 entry point.

The analysis (LLM) reads THIS instead of fetching live. It returns the latest
FROZEN snapshot merged with computed trend/vol stats, so the diagnosis rests on
a reproducible data mark + code-grounded trend facts (not live re-fetch, not
human recall of multi-day moves).

Usage:
    python3 load_for_analysis.py            # latest frozen snapshot + stats
    python3 load_for_analysis.py --date YYYYMMDD   # a specific past day
    python3 load_for_analysis.py --summary  # human table to stderr too

If no snapshot exists yet, tells the caller to run capture_snapshot.py first.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SNAP_DIR = REPO / "data" / "snapshots"
COMPUTE = REPO / "scripts" / "compute_stats.py"


def latest_snapshot_date() -> str | None:
    if not SNAP_DIR.exists():
        return None
    snaps = sorted(SNAP_DIR.glob("*.json"))
    return snaps[-1].stem if snaps else None


def load_snapshot(date_key: str) -> dict:
    path = SNAP_DIR / f"{date_key}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_stats(date_key: str, window: int) -> dict:
    res = subprocess.run(
        ["/Users/jowang/miniconda3/bin/python3", str(COMPUTE), "--window", str(window), "--snapshot", date_key],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if res.returncode != 0:
        return {"error": res.stderr[:300]}
    return json.loads(res.stdout)


def mark_quality(snapshot: dict) -> str:
    assets = snapshot.get("assets", {})
    kinds = [
        v.get("session_kind")
        for v in assets.values()
        if isinstance(v, dict) and "last" in v
    ]
    if any(k == "intraday_stale" for k in kinds):
        return "intraday_stale"
    return "us_close"


def stale_assets(snapshot: dict) -> list[str]:
    return [
        name for name, value in snapshot.get("assets", {}).items()
        if isinstance(value, dict) and value.get("stale") is True
    ]


def print_summary(merged: dict):
    snap = merged["snapshot"]
    stats = merged["stats"]
    print(f"\n=== 分析就绪数据 ({merged['date']}) ===", file=sys.stderr)
    print(f"数据时间: {snap.get('fetched_at','?')[:19]} UTC", file=sys.stderr)
    cap = snap.get("_capture", {})
    print(
        f"捕获: {cap.get('assets_ok','?')}/{cap.get('assets_total','?')} 资产 | "
        f"degraded: {cap.get('degraded', False)} | mark_quality: {merged.get('mark_quality')} | "
        f"较前一日有变动: {cap.get('data_changed_vs_prev','?')} | "
        f"trend_ready: {stats.get('trend_ready')} | vol_gate_ready: {stats.get('vol_gate_ready')}",
        file=sys.stderr,
    )
    wlabel = f"{stats.get('window','?')}日"
    print(f"{'资产':<14}{'最新':>11}{'当日':>9}{wlabel:>9}{'连续同向':>9}{'波动分位':>9}{'标记':>8}", file=sys.stderr)
    print("-" * 72, file=sys.stderr)
    for name, s in stats.get("assets", {}).items():
        unit = s.get("unit", "")
        chg = s.get("today_change")
        chg_s = f"{chg:+.2f}" if chg is not None else "—"
        wkey = f"{stats.get('window')}d_change" if unit == "bps" else f"{stats.get('window')}d_change_pct"
        wv = s.get(wkey)
        wv_s = f"{wv:+.2f}" if wv is not None else "—"
        consec = s.get("consec_same_dir", 0)
        volp = s.get("move_vol_pct")
        volp_s = f"{volp}%" if volp is not None else "—"
        flags = []
        if s.get("stale"):
            flags.append("stale")
        if s.get("gap_adjacent"):
            flags.append("gap")
        flags_s = ",".join(flags) if flags else "—"
        print(
            f"{name:<14}{s.get('last',0):>11.2f}{chg_s:>9}{wv_s:>9}{consec:>9}{volp_s:>9}{flags_s:>8}",
            file=sys.stderr,
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="target date YYYYMMDD (default: latest)")
    ap.add_argument("--window", type=int, default=3, help="trend window (default 3)")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    date_key = args.date or latest_snapshot_date()
    if not date_key:
        print(
            json.dumps(
                {
                    "error": "no frozen snapshot found",
                    "hint": "run: python3 scripts/capture_snapshot.py (or wait for the daily routine)",
                }
            )
        )
        sys.exit(1)

    snapshot = load_snapshot(date_key)
    stats = load_stats(date_key, args.window)
    merged = {
        "date": date_key,
        "snapshot": snapshot,
        "stats": stats,
        "mark_quality": mark_quality(snapshot),
        "stale_assets": stale_assets(snapshot),
    }

    if args.summary or not sys.stdout.isatty():
        print_summary(merged)
    print(json.dumps(merged, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
