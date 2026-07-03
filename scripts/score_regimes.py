#!/usr/bin/env python3
"""Deterministic regime matrix scoring."""

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MATRIX = REPO / "data" / "regime_matrix.json"
LOG = REPO / "data" / "diagnosis_log.jsonl"
LOAD = REPO / "scripts" / "load_for_analysis.py"
YIELDS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}


def load_analysis(date=None):
    cmd = ["/Users/jowang/miniconda3/bin/python3", str(LOAD)]
    if date:
        cmd += ["--date", date]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    return json.loads(res.stdout)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def recent_log(before_date):
    if not LOG.exists():
        return None
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("date") and row["date"] < before_date:
            rows.append(row)
    return rows[-1] if rows else None


def confidence_rank(stars):
    return {"★☆☆": 1, "★★☆": 2, "★★★": 3}.get(stars or "", 0)


def signal_dir(asset, stat, gate):
    pct = stat.get("move_vol_pct")
    if pct is None or pct < gate:
        return None
    chg = stat.get("today_change")
    if chg is None or chg == 0:
        return None
    up = chg > 0
    if asset in YIELDS:
        up = not up
    return "↑" if up else "↓"


def class_state(class_name, assets, stats, gates):
    dirs = []
    members = []
    for asset in assets:
        stat = stats.get(asset)
        if not stat:
            continue
        gate = gates.get("BTC_move_vol_pct") if asset == "BTC" else gates.get("default_move_vol_pct", 50)
        d = signal_dir(asset, stat, gate)
        if d:
            dirs.append(d)
            members.append({"asset": asset, "dir": d, "move_vol_pct": stat.get("move_vol_pct")})
    if not dirs:
        return {"state": "noise", "dir": None, "members": members}
    if "↑" in dirs and "↓" in dirs:
        return {"state": "conflicted", "dir": None, "members": members}
    return {"state": "signal", "dir": dirs[0], "members": members}


def expected_base(direction):
    return "↑" if direction.startswith("↑") else "↓" if direction.startswith("↓") else None


def weight(direction):
    return 0.5 if "?" in direction else 1.0


def liquidity_override(states):
    return {
        "value": (
            states.get("usd_fx", {}).get("dir") == "↑"
            and states.get("precious", {}).get("dir") == "↓"
            and states.get("rates_long", {}).get("dir") == "↓"
            and states.get("equities_us", {}).get("dir") == "↓"
        ),
        "checks": {
            "usd_up": states.get("usd_fx", {}).get("dir") == "↑",
            "gold_down": states.get("precious", {}).get("dir") == "↓",
            "bonds_down": states.get("rates_long", {}).get("dir") == "↓",
            "risk_down": states.get("equities_us", {}).get("dir") == "↓",
        },
    }


def vol_low_level(stats):
    vix = stats.get("VIX", {}).get("last")
    move = stats.get("MOVE", {}).get("last")
    return vix is not None and move is not None and vix <= 18 and move <= 75


def row_key_for_log(row, matrix):
    if row.get("regime_row"):
        return row.get("regime_row")
    code = row.get("regime")
    matches = [
        key for key, spec in matrix["regimes"].items()
        if spec.get("code") == code
    ]
    return matches[0] if len(matches) == 1 else code


def score(analysis):
    matrix = load_json(MATRIX)
    stats = analysis["stats"]["assets"]
    states = {
        cls: class_state(cls, assets, stats, matrix["noise_gate"])
        for cls, assets in matrix["asset_classes"].items()
    }
    low_vol = vol_low_level(stats)
    rows = {}
    for regime, spec in matrix["regimes"].items():
        dirs = spec.get("directions", {})
        guards = spec.get("guards", {})
        denom = 0.0
        score_val = 0.0
        aligned = []
        conflicted = []
        noise = []
        low_level_aligned = []
        for cls, exp in dirs.items():
            exp_dir = expected_base(exp)
            if not exp_dir:
                continue
            state = states.get(cls, {"state": "noise"})
            if state["state"] == "noise":
                if cls == "vol" and spec.get("accept_low_level_vol") and low_vol and exp_dir == "↓":
                    w = weight(exp)
                    denom += w
                    score_val += w
                    aligned.append(cls)
                    low_level_aligned.append(cls)
                else:
                    noise.append(cls)
                continue
            w = weight(exp)
            denom += w
            if state["state"] == "conflicted":
                score_val -= w
                conflicted.append(cls)
            elif state.get("dir") == exp_dir:
                score_val += w
                aligned.append(cls)
            else:
                score_val -= w
                conflicted.append(cls)
        for cls, rule in guards.items():
            if rule == "signal_down_conflict":
                state = states.get(cls, {"state": "noise"})
                if state.get("state") == "signal" and state.get("dir") == "↓":
                    denom += 1.0
                    score_val -= 1.0
                    if cls not in conflicted:
                        conflicted.append(cls)
            elif rule == "anchor_or_not_leading":
                state = states.get(cls, {"state": "noise"})
                if state.get("state") == "signal":
                    denom += 1.0
                    score_val -= 1.0
                    if cls not in conflicted:
                        conflicted.append(cls)
        match_pct = round((score_val / denom) * 100, 1) if denom else 0
        signal_classes = [
            c for c in aligned
            if c != "btc" and c not in low_level_aligned
            and states.get(c, {}).get("state") == "signal"
        ]
        rows[regime] = {
            "match_pct": match_pct,
            "score": round(score_val, 2),
            "denominator": round(denom, 2),
            "aligned": aligned,
            "conflicted": conflicted,
            "noise": noise,
            "low_level_aligned": low_level_aligned,
            "signal_class_count": len(signal_classes),
            "callable": match_pct > 60 and len(signal_classes) >= 4,
            "single_day_max_confidence": spec.get("single_day_max_confidence"),
        }
    best = max(
        rows.items(),
        key=lambda kv: (
            kv[1]["callable"],
            kv[1]["signal_class_count"],
            kv[1]["denominator"],
            kv[1]["match_pct"],
            kv[1]["score"],
        ),
    )
    prev = recent_log(analysis["date"])
    cap = None
    if prev and prev.get("regime"):
        prev_row = row_key_for_log(prev, matrix)
        current_row = best[0]
        changed = prev_row != current_row
        if "regime_row" not in prev:
            changed = prev.get("regime") != matrix["regimes"].get(best[0], {}).get("code")
    else:
        changed = False
    if changed:
        if confidence_rank(prev.get("l2")) >= 2:
            cap = "★★☆"
    return {
        "date": analysis["date"],
        "mark_quality": analysis.get("mark_quality"),
        "class_states": states,
        "vol_low_level": low_vol,
        "rows": rows,
        "best_regime": best[0],
        "liquidity_override": liquidity_override(states),
        "whipsaw_cap": cap,
        "cap_reason": f"previous high-confidence regime_row {row_key_for_log(prev, matrix)} on {prev.get('date')}" if cap and prev else None,
        "schema_d_suggested": not rows[best[0]]["callable"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    print(json.dumps(score(load_analysis(args.date)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
