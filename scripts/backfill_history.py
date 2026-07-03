#!/usr/bin/env python3
"""
backfill_history.py — one-shot history loader.

Pulls daily bars from yfinance for the same 20 assets and reconstructs
historical snapshots into data/timeseries.jsonl (and data/snapshots/), so the
Layer-2 trend / volatility stats become useful immediately instead of after a
week of live captures.

- Reconstructs the exact same per-asset structure as fetch_prices.py
  (last / prev / change / change_pct|change_bps / dir).
- Keys each day by its trading-bar date (YYYYMMDD), matching the live capture's
  UTC-date keying (live capture runs shortly after US close, same UTC day).
- Does NOT overwrite a snapshot file that already exists (preserves any mark the
  live routine already wrote); always rebuilds the timeseries from scratch.

Usage:
    python3 backfill_history.py [--period 3mo]
"""

import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

import requests
import yfinance as yf

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SNAP_DIR = DATA / "snapshots"
TIMESERIES = DATA / "timeseries.jsonl"

YIELD_ASSETS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}

# Must match fetch_prices.py exactly.
ASSETS = {
    "DXY": "DX-Y.NYB", "US_2Y_yield": "2YY=F", "US_10Y_yield": "^TNX",
    "US_30Y_yield": "^TYX", "Gold": "GC=F", "Silver": "SI=F", "Brent": "BZ=F",
    "WTI": "CL=F", "NatGas": "NG=F", "SP500": "^GSPC", "Nasdaq": "^IXIC",
    "Russell2000": "^RUT", "VIX": "^VIX", "MOVE": "^MOVE", "EM_ETF": "EEM",
    "HYG": "HYG", "TLT": "TLT", "Copper": "HG=F", "USDCNY": "USDCNY=X",
    "USDJPY": "JPY=X", "BTC": "BTC-USD",
}

# 24/7 assets (crypto): excluded from the trading-calendar union so their
# weekend bars don't create weekend-only rows. They're sampled on US trading
# days only, so prev = prior US trading day (Fri→Mon), matching fetch_prices.py.
CALENDAR_ALIGN_TO_EQUITY = {"BTC"}


def fred_series(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    rows = []
    for row in csv.DictReader(io.StringIO(res.text)):
        val = row.get(series_id)
        if not val or val == ".":
            continue
        try:
            rows.append((row["observation_date"].replace("-", ""), float(val)))
        except (KeyError, ValueError):
            continue
    return rows


def fred_value_on_or_before(rows, date_key):
    last = None
    prev = None
    for d, v in rows:
        if d > date_key:
            break
        prev = last
        last = (d, v)
    if not last:
        return None, None
    return last, prev


def arrow_and_change(name, last, prev):
    """Replicate fetch_prices.py's change/dir logic exactly."""
    entry = {"last": round(last, 4)}
    if prev is None:
        return entry
    change = last - prev
    entry["prev"] = round(prev, 4)
    entry["change"] = round(change, 4)
    if name in YIELD_ASSETS:
        bps = change * 100
        entry["change_bps"] = round(bps, 1)
        entry["unit"] = "bps"
        if abs(bps) < 0.5:
            entry["dir"] = "—"
        elif bps > 0:
            entry["dir"] = "↑" if bps < 5 else "↑↑" if bps < 15 else "↑↑↑"
        else:
            entry["dir"] = "↓" if bps > -5 else "↓↓" if bps > -15 else "↓↓↓"
    else:
        change_pct = (change / prev) * 100 if prev != 0 else None
        entry["change_pct"] = round(change_pct, 2) if change_pct is not None else None
        entry["unit"] = "%"
        if change_pct is None or abs(change_pct) < 0.05:
            entry["dir"] = "—"
        elif change_pct > 0:
            entry["dir"] = "↑" if change_pct < 1 else "↑↑" if change_pct < 3 else "↑↑↑"
        else:
            entry["dir"] = "↓" if change_pct > -1 else "↓↓" if change_pct > -3 else "↓↓↓"
    return entry


def backup_timeseries():
    if not TIMESERIES.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TIMESERIES.with_name(f"timeseries.backup-{ts}.jsonl")
    shutil.copy2(TIMESERIES, backup)
    return backup


def repair_2y_from_fred():
    rows = fred_series("DGS2")
    if not rows:
        raise RuntimeError("FRED DGS2 returned no usable rows")

    backup = backup_timeseries()
    changed = []
    samples = []

    records = []
    if TIMESERIES.exists():
        for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            date_key = obj.get("date")
            current = obj.get("assets", {}).get("US_2Y_yield", {})
            latest, prev = fred_value_on_or_before(rows, date_key)
            if date_key and latest and current:
                old_last = current.get("last")
                entry = arrow_and_change("US_2Y_yield", latest[1], prev[1] if prev else None)
                entry.update({
                    "source": "FRED:DGS2",
                    "as_of": f"{latest[0][:4]}-{latest[0][4:6]}-{latest[0][6:]}",
                    "stale": latest[0] != date_key,
                    "session_kind": "us_close",
                })
                obj.setdefault("assets", {})["US_2Y_yield"] = entry
                if old_last != entry.get("last"):
                    changed.append(date_key)
                    if len(samples) < 8:
                        samples.append({"date": date_key, "old": old_last, "new": entry.get("last")})
            records.append(obj)
    if records:
        with open(TIMESERIES, "w", encoding="utf-8") as f:
            for obj in sorted(records, key=lambda o: o.get("date", "")):
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    snap_changed = 0
    for path in sorted(SNAP_DIR.glob("*.json")):
        date_key = path.stem
        latest, prev = fred_value_on_or_before(rows, date_key)
        if not latest:
            continue
        obj = json.loads(path.read_text(encoding="utf-8"))
        if "US_2Y_yield" not in obj.get("assets", {}):
            continue
        old_last = obj["assets"]["US_2Y_yield"].get("last")
        entry = arrow_and_change("US_2Y_yield", latest[1], prev[1] if prev else None)
        entry.update({
            "source": "FRED:DGS2",
            "as_of": f"{latest[0][:4]}-{latest[0][4:6]}-{latest[0][6:]}",
            "stale": latest[0] != date_key,
            "session_kind": "us_close",
        })
        obj["assets"]["US_2Y_yield"] = entry
        if old_last != entry.get("last"):
            snap_changed += 1
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "backup": str(backup) if backup else None,
        "timeseries_changed_days": len(changed),
        "snapshot_changed_files": snap_changed,
        "samples": samples,
    }, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="3mo", help="yfinance period (default 3mo)")
    ap.add_argument("--repair-2y", action="store_true", help="rewrite US_2Y_yield from FRED DGS2")
    args = ap.parse_args()

    if args.repair_2y:
        repair_2y_from_fred()
        return

    print(f"Downloading {len(ASSETS)} assets, period={args.period} ...")
    data = yf.download(
        list(ASSETS.values()), period=args.period, interval="1d",
        auto_adjust=True, progress=False, threads=True,
    )
    close = data["Close"] if "Close" in data else data.get("Adj Close", data)

    # Build per-asset clean series of (date, value)
    series = {}
    for name, ticker in ASSETS.items():
        try:
            s = close[ticker].dropna()
            series[name] = [(idx.strftime("%Y%m%d"), float(v)) for idx, v in s.items()]
        except Exception as e:
            print(f"  ! {name}: {e}")
            series[name] = []

    # Trading-calendar = union of dates from non-24/7 assets only, so a 24/7
    # asset (BTC) never injects a weekend-only row. BTC is then sampled on these
    # dates, giving it a prior-US-trading-day reference (Fri→Mon).
    all_dates = sorted({
        d for name, s in series.items()
        if name not in CALENDAR_ALIGN_TO_EQUITY
        for d, _ in s
    })
    if len(all_dates) < 2:
        print("Not enough history.")
        return

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    snaps_written = 0
    for i, date_key in enumerate(all_dates):
        if i == 0:
            continue  # need a prev day for change
        prev_date = all_dates[i - 1]
        assets_out = {}
        for name in ASSETS:
            sm = dict(series[name])
            last = sm.get(date_key)
            prev = sm.get(prev_date)
            if last is None:
                continue
            assets_out[name] = arrow_and_change(name, last, prev)
        if not assets_out:
            continue
        snapshot = {
            "fetched_at": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}T21:00:00+00:00",
            "period": args.period,
            "assets": assets_out,
            "_capture": {"source": "backfill", "assets_ok": len(assets_out)},
        }
        records.append({"date": date_key, **snapshot})
        # Write snapshot file only if it doesn't already exist (preserve live marks)
        snap_path = SNAP_DIR / f"{date_key}.json"
        if not snap_path.exists():
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            snaps_written += 1

    # Merge with any existing timeseries entries that backfill didn't cover,
    # then rewrite sorted & de-duplicated (backfill wins for covered dates,
    # but a live same-day entry already on disk as a snapshot file is kept too).
    existing = {}
    if TIMESERIES.exists():
        for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                existing[o["date"]] = o
            except Exception:
                continue
    for r in records:
        existing.setdefault(r["date"], r)  # don't clobber a live entry if present
    merged = sorted(existing.values(), key=lambda o: o["date"])
    with open(TIMESERIES, "w", encoding="utf-8") as f:
        for o in merged:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"Backfill done: {len(records)} trading days reconstructed, "
          f"{snaps_written} snapshot files written, timeseries now {len(merged)} days "
          f"({merged[0]['date']} → {merged[-1]['date']}).")


if __name__ == "__main__":
    main()
