#!/usr/bin/env python3
"""
compute_stats.py — Layer 2 of the decoupled architecture.

Reads data/timeseries.jsonl and computes, per asset, the things the LLM
currently judges by (fallible) recall:
  - N-day cumulative change (3d / 5d)
  - consecutive same-direction days (trend persistence)
  - today's |move| as a percentile of the trailing distribution
    (→ a code-grounded "noise vs signal" gate, addressing the critique that
     single-day moves get over-read)

Outputs JSON to stdout. The analysis layer (LLM) reads this alongside the
frozen snapshot so its trend / noise claims rest on computed facts.

Usage:
    python3 compute_stats.py [--window N] [--snapshot YYYYMMDD]
"""

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIMESERIES = REPO / "data" / "timeseries.jsonl"

YIELD_ASSETS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}
FUTURES_ASSETS = {"Gold", "Silver", "Brent", "WTI", "NatGas", "Copper"}


def load_series() -> list[dict]:
    if not TIMESERIES.exists():
        return []
    rows = []
    for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda o: o.get("date", ""))
    return rows


def asset_change(name: str, entry: dict):
    """Return the signed daily change in the asset's native unit (bps or %)."""
    if entry is None or "last" not in entry:
        return None
    if name in YIELD_ASSETS:
        if "change_bps" in entry:
            return entry["change_bps"]
        if "prev" in entry and "last" in entry:
            return round((entry["last"] - entry["prev"]) * 100, 1)
        return None
    if "change_bps" in entry:
        return entry["change_bps"]
    if "change_pct" in entry:
        return entry["change_pct"]
    return None


def source_family(entry: dict):
    source = entry.get("source") if isinstance(entry, dict) else None
    if not source:
        return None
    if ":" in source:
        provider, symbol = source.split(":", 1)
    else:
        provider, symbol = "", source
    symbol = symbol.split("(", 1)[0]
    if symbol.startswith("2YY"):
        symbol = "2YY"
    elif symbol.startswith("DGS2"):
        symbol = "DGS2"
    elif symbol.startswith("DGS10"):
        symbol = "DGS10"
    elif symbol.startswith("DGS30"):
        symbol = "DGS30"
    return f"{provider}:{symbol}" if provider else symbol


def source_switched(prev_entry: dict | None, entry: dict | None) -> bool:
    prev_family = source_family(prev_entry or {})
    family = source_family(entry or {})
    if not prev_family or not family:
        return False
    return prev_family != family


def is_degraded(row: dict) -> bool:
    """Legacy rows without _capture are treated as usable."""
    return bool(row.get("_capture", {}).get("degraded", False))


def median(values: list[float]):
    if not values:
        return None
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def build_points(name: str, raw_history: list[dict]):
    """Return the per-asset compressed sequence used by all downstream stats."""
    points = []
    previous_kept_entry = None
    previous_kept_key = None
    source_switch_dates = set()
    dup_days_excluded = 0

    for pos, r in enumerate(raw_history):
        if is_degraded(r):
            continue
        a = r.get("assets", {}).get(name)
        if not (a and "last" in a):
            continue

        raw_change = asset_change(name, a)
        key = (a["last"], raw_change)
        if previous_kept_key == key:
            dup_days_excluded += 1
            continue

        change = raw_change
        if source_switched(previous_kept_entry, a):
            change = None
            source_switch_dates.add(r.get("date"))
        points.append((pos, r.get("date"), a["last"], change))
        previous_kept_entry = a
        previous_kept_key = key

    return {
        "points": points,
        "source_switch_dates": source_switch_dates,
        "dup_days_excluded": dup_days_excluded,
        "kept_positions": {p[0] for p in points},
    }


def sp500_gap_between(
    sp500_new_bar_positions: set[int],
    asset_kept_positions: set[int],
    start_pos: int | None,
    end_pos: int,
) -> bool:
    """True if SP500 made a new bar while this asset did not in the interval."""
    lower = -1 if start_pos is None else start_pos
    for pos in sp500_new_bar_positions:
        if lower < pos <= end_pos and pos not in asset_kept_positions:
            return True
    return False


def is_roll_suspect(name: str, target_change, trailing_changes: list[float]) -> bool:
    if name not in FUTURES_ASSETS or target_change is None:
        return False
    if abs(target_change) <= 2:
        return False
    abs_changes = [abs(c) for c in trailing_changes if c is not None]
    med = median(abs_changes)
    if med is None:
        return False
    mad = median([abs(x - med) for x in abs_changes])
    if mad is None or mad == 0:
        return False
    return abs(target_change) > 4 * mad


def compute(rows: list[dict], window: int, target_date: str | None):
    if not rows:
        return {"error": "no timeseries data"}

    # Pick the target snapshot (default: latest)
    if target_date:
        idx = next((i for i, r in enumerate(rows) if r.get("date") == target_date), None)
        if idx is None:
            return {"error": f"date {target_date} not in timeseries"}
    else:
        idx = len(rows) - 1

    target = rows[idx]
    raw_history = rows[: idx + 1]  # up to and including target
    history = [r for r in raw_history if not is_degraded(r)]
    assets = target.get("assets", {})
    target_pos = idx
    compressed_by_asset = {
        name: build_points(name, raw_history) for name in assets if "last" in assets[name]
    }
    sp500_new_bar_positions = compressed_by_asset.get("SP500", {}).get("kept_positions", set())

    out = {
        "target_date": target.get("date"),
        "fetched_at": target.get("fetched_at"),
        "history_days": len(history),
        "window": window,
        "assets": {},
    }

    for name, entry in assets.items():
        if "last" not in entry:
            continue
        last = entry["last"]
        unit = "bps" if name in YIELD_ASSETS else "%"

        # Collect usable history. Degraded days are excluded from baselines.
        compressed = compressed_by_asset.get(name) or build_points(name, raw_history)
        points = compressed["points"]
        source_switch_dates = compressed["source_switch_dates"]
        dup_days_excluded = compressed["dup_days_excluded"]
        asset_kept_positions = compressed["kept_positions"]
        lasts = [p[2] for p in points]
        changes = [p[3] for p in points if p[3] is not None]

        target_point_index = next((i for i, p in enumerate(points) if p[1] == target.get("date")), None)
        source_switch = target.get("date") in source_switch_dates
        target_change = points[target_point_index][3] if target_point_index is not None else None
        gap_adjacent = False
        if target_point_index is not None and target_point_index > 0:
            gap_adjacent = sp500_gap_between(
                sp500_new_bar_positions,
                asset_kept_positions,
                points[target_point_index - 1][0],
                points[target_point_index][0],
            )
        elif target_point_index is None:
            previous_pos = None
            for pos, _date, _last, _change in points:
                if pos < target_pos:
                    previous_pos = pos
                else:
                    break
            gap_adjacent = sp500_gap_between(
                sp500_new_bar_positions,
                asset_kept_positions,
                previous_pos,
                target_pos,
            )
        if source_switch:
            gap_adjacent = True

        stat = {
            "last": last,
            "today_change": target_change,
            "unit": unit,
            "gap_adjacent": gap_adjacent,
            "source_switch": source_switch,
            "stale": bool(entry.get("stale", False)),
            "source": entry.get("source"),
            "as_of": entry.get("as_of"),
            "session_kind": entry.get("session_kind"),
            "dup_days_excluded": dup_days_excluded,
        }

        # N-day cumulative change (level diff over window)
        if target_point_index is not None:
            current_lasts = lasts[: target_point_index + 1]
        else:
            current_lasts = lasts
        if len(current_lasts) > window:
            base = current_lasts[-(window + 1)]
            if name in YIELD_ASSETS:
                stat[f"{window}d_change"] = round((last - base) * 100, 1)  # bps
            else:
                stat[f"{window}d_change_pct"] = (
                    round((last - base) / base * 100, 2) if base else None
                )
        else:
            stat[f"{window}d_change"] = None  # insufficient history

        # Consecutive same-direction days
        consec = 0
        direction = None
        if target_point_index is not None:
            point_window = points[: target_point_index + 1]
        else:
            point_window = points
        consec_changes = []
        for _pos, _date, _last, c in point_window:
            if c is None:
                consec_changes = []
                continue
            consec_changes.append(c)

        for c in reversed(consec_changes):
            d = 1 if c > 0 else (-1 if c < 0 else 0)
            if d == 0:
                break
            if direction is None:
                direction = d
                consec = 1
            elif d == direction:
                consec += 1
            else:
                break
        stat["consec_same_dir"] = consec * (direction or 0)  # signed

        # Volatility percentile: |today| vs trailing |changes|
        vol_changes = changes[:-1] if target_point_index == len(points) - 1 else changes
        abs_changes = [abs(c) for c in vol_changes]
        today_abs = abs(target_change) if target_change is not None and not gap_adjacent else None
        if len(abs_changes) >= 5 and today_abs is not None:
            below = sum(1 for x in abs_changes if x < today_abs)
            pct = round(below / len(abs_changes) * 100)
            stat["move_vol_pct"] = pct  # 0-100; high = unusually large move
            stat["noise_flag"] = pct < 50  # below median |move| = likely noise
        else:
            stat["move_vol_pct"] = None
            stat["noise_flag"] = None  # insufficient history to judge

        if is_roll_suspect(name, target_change, vol_changes):
            stat["roll_suspect"] = True

        out["assets"][name] = stat

    # Top-level convenience: how much usable history do we have for trend calls?
    out["history_days_raw"] = len(raw_history)
    out["history_days"] = len(history)
    out["excluded_degraded_days"] = [
        r.get("date") for r in raw_history if is_degraded(r)
    ]
    out["target_degraded"] = is_degraded(target)
    out["trend_ready"] = len(history) > window
    out["vol_gate_ready"] = len(history) >= 6
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=3, help="N-day trend window (default 3)")
    ap.add_argument("--snapshot", default=None, help="target date YYYYMMDD (default: latest)")
    args = ap.parse_args()

    rows = load_series()
    result = compute(rows, args.window, args.snapshot)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
