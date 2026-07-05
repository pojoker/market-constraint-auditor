#!/usr/bin/env python3
"""Check report falsifier sidecars against computed stats."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
LOAD = REPO / "scripts" / "load_for_analysis.py"


def latest_sidecar():
    files = sorted(REPORTS.glob("*.thresholds.json"))
    return files[-1] if files else None


def load_analysis(date):
    cmd = ["/Users/jowang/miniconda3/bin/python3", str(LOAD)]
    if date:
        cmd += ["--date", date]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    return json.loads(res.stdout)


def asset_dir(stat):
    chg = stat.get("today_change")
    if chg is None:
        return None
    return "up" if chg > 0 else "down" if chg < 0 else "flat"


def metric_value(stat, rule):
    metric = rule["metric"]
    if metric == "level":
        return stat.get("last")
    if metric == "nd_change":
        window = rule.get("window", 1)
        return stat.get(f"{window}d_change") or stat.get(f"{window}d_change_pct")
    return stat.get(metric)


def direction_ok(stat, rule):
    wanted = rule.get("dir")
    if wanted in (None, "any"):
        return True
    return asset_dir(stat) == wanted


def evaluate(rule, stats):
    stat = stats.get(rule["asset"])
    if not stat:
        return {"state": "SAFE", "value": None, "reason": "asset missing"}
    if rule["op"] == "flip_sign":
        val = stat.get(rule["metric"])
        wanted = rule.get("dir")
        sign_flipped = (wanted == "positive" and val and val > 0) or (wanted == "negative" and val and val < 0)
        triggered = sign_flipped and not stat.get("noise_flag", False)
        near = val in (-1, 0, 1)
        return {"state": "TRIGGERED" if triggered else "NEAR" if near or sign_flipped else "SAFE", "value": val}
    val = metric_value(stat, rule)
    if val is None:
        return {"state": "SAFE", "value": None}
    target = rule.get("value")
    op = rule["op"]
    triggered = False
    near = False
    if op == ">=":
        triggered = val >= target and direction_ok(stat, rule)
        near = direction_ok(stat, rule) and (
            val >= target * 0.8 or (rule["metric"] == "move_vol_pct" and target - val <= 10)
        )
    elif op == "<=":
        triggered = val <= target and direction_ok(stat, rule)
        near = direction_ok(stat, rule) and val <= target * 1.2
    elif op == "cross":
        triggered = direction_ok(stat, rule) and ((rule.get("dir") == "up" and val >= target) or (rule.get("dir") == "down" and val <= target))
        near = direction_ok(stat, rule) and (abs(val - target) <= abs(target) * 0.2 if target else False)
    state = "TRIGGERED" if triggered else "NEAR" if near else "SAFE"
    return {"state": state, "value": val, "dir": asset_dir(stat)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar", default=None)
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    sidecar = Path(args.sidecar) if args.sidecar else latest_sidecar()
    if not sidecar:
        print("No thresholds sidecar found.")
        return 0
    spec = json.loads(sidecar.read_text(encoding="utf-8"))
    date = args.date
    analysis = load_analysis(date)
    stats = analysis["stats"]["assets"]
    mark_quality = analysis.get("mark_quality")
    triggered = []
    out = {
        "sidecar": str(sidecar),
        "report_date": spec.get("report_date"),
        "regime": spec.get("regime"),
        "regime_row": spec.get("regime_row"),
        "date": analysis.get("date"),
        "mark_quality": mark_quality,
        "checks": [],
    }
    for rule in spec.get("falsifiers", []):
        result = evaluate(rule, stats)
        paired = rule.get("paired_with")
        if paired and result["state"] == "TRIGGERED":
            pair_result = evaluate(paired, stats)
            if pair_result["state"] != "TRIGGERED":
                result["state"] = "NEAR"
            result["paired_result"] = pair_result
        row = {"rule": rule, **result}
        out["checks"].append(row)
        if result["state"] == "TRIGGERED":
            triggered.append(row)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    for row in triggered:
        suffix = " [partial-session mark]" if mark_quality == "partial_session" else ""
        print(f"ALERT {row['rule']['asset']} {row['rule']['metric']}: {row['rule']['means']}{suffix}", file=sys.stderr)
    return 1 if triggered else 0


if __name__ == "__main__":
    sys.exit(main())
