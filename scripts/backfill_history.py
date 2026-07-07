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
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SNAP_DIR = DATA / "snapshots"
TIMESERIES = DATA / "timeseries.jsonl"
EASTERN = ZoneInfo("America/New_York")

YIELD_ASSETS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}

# Must match fetch_prices.py exactly.
ASSETS = {
    "DXY": "DX-Y.NYB", "US_2Y_yield": "FRED:DGS2", "SHY": "SHY", "US_10Y_yield": "^TNX",
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


def bar_date_key(idx):
    try:
        ts = idx.to_pydatetime()
    except AttributeError:
        return str(idx).replace("-", "")[:8]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=EASTERN)
    else:
        ts = ts.astimezone(EASTERN)
    return ts.strftime("%Y%m%d")


def fetch_2yy_daily_history():
    data = yf.Ticker("2YY=F").history(period="max", interval="1d", auto_adjust=True)
    if data is None or data.empty or "Close" not in data:
        raise RuntimeError("2YY=F daily returned no usable data")
    close = data["Close"].dropna()
    rows = []
    for idx, value in close.items():
        rows.append((bar_date_key(idx), float(value)))
    dedup = {}
    for date_key, value in rows:
        dedup[date_key] = value
    rows = sorted(dedup.items())
    if not rows:
        raise RuntimeError("2YY=F daily returned no close values")
    return rows


def rebase_2y_2yy():
    backup = backup_timeseries()
    if TIMESERIES.exists() and backup is None:
        raise RuntimeError("failed to back up timeseries before rewrite")

    rows = fetch_2yy_daily_history()
    by_date = dict(rows)
    prev_by_date = {}
    prev = None
    for date_key, value in rows:
        prev_by_date[date_key] = prev
        prev = value

    records = []
    timeseries_seen = 0
    timeseries_rewritten = 0
    timeseries_removed = 0
    removed_dates = []
    samples = []
    if TIMESERIES.exists():
        for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            date_key = obj.get("date")
            assets = obj.setdefault("assets", {})
            current = assets.get("US_2Y_yield")
            if current:
                timeseries_seen += 1
                if date_key in by_date:
                    old_last = current.get("last")
                    entry = arrow_and_change(
                        "US_2Y_yield",
                        by_date[date_key],
                        prev_by_date.get(date_key),
                    )
                    entry.update({
                        "source": "yfinance:2YY=F(backfill)",
                        "as_of": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}",
                        "stale": False,
                        "session_kind": "us_close",
                    })
                    assets["US_2Y_yield"] = entry
                    timeseries_rewritten += 1
                    if len(samples) < 8:
                        samples.append({
                            "date": date_key,
                            "old": old_last,
                            "old_source": current.get("source"),
                            "new": entry.get("last"),
                            "new_source": entry.get("source"),
                        })
                else:
                    del assets["US_2Y_yield"]
                    timeseries_removed += 1
                    removed_dates.append(date_key)
            records.append(obj)
    if records:
        with open(TIMESERIES, "w", encoding="utf-8") as f:
            for obj in sorted(records, key=lambda o: o.get("date", "")):
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    snapshot_seen = 0
    snapshot_rewritten = 0
    snapshot_removed = 0
    for path in sorted(SNAP_DIR.glob("*.json")):
        date_key = path.stem
        obj = json.loads(path.read_text(encoding="utf-8"))
        assets = obj.setdefault("assets", {})
        current = assets.get("US_2Y_yield")
        if not current:
            continue
        snapshot_seen += 1
        if date_key in by_date:
            entry = arrow_and_change(
                "US_2Y_yield",
                by_date[date_key],
                prev_by_date.get(date_key),
            )
            entry.update({
                "source": "yfinance:2YY=F(backfill)",
                "as_of": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}",
                "stale": False,
                "session_kind": "us_close",
            })
            assets["US_2Y_yield"] = entry
            snapshot_rewritten += 1
        else:
            del assets["US_2Y_yield"]
            snapshot_removed += 1
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "backup": str(backup) if backup else None,
        "2yy_daily_bars": len(rows),
        "2yy_first_date": rows[0][0],
        "2yy_last_date": rows[-1][0],
        "timeseries_2y_entries_before": timeseries_seen,
        "timeseries_rewritten_days": timeseries_rewritten,
        "timeseries_removed_2y_entries": timeseries_removed,
        "timeseries_removed_dates": removed_dates,
        "snapshot_2y_entries_before": snapshot_seen,
        "snapshot_rewritten_files": snapshot_rewritten,
        "snapshot_removed_2y_entries": snapshot_removed,
        "samples": samples,
    }, ensure_ascii=False, indent=2))


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


def _load_timeseries_rows():
    return [json.loads(l) for l in TIMESERIES.read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_timeseries_rows(rows):
    rows.sort(key=lambda r: r.get("date", ""))
    with open(TIMESERIES, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _backup_timeseries():
    backup = TIMESERIES.with_name(
        f"timeseries.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl")
    shutil.copy2(TIMESERIES, backup)
    return backup


def add_asset(name, period="9mo"):
    """向既有 timeseries/snapshots 增配单个 yfinance 价格资产的历史（不动其它资产）。"""
    ticker = ASSETS[name]
    hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
    close = hist["Close"].dropna()
    if close.empty:
        raise RuntimeError(f"{ticker}: no daily bars")
    bar_dates = [idx.strftime("%Y%m%d") for idx in close.index]
    bar_vals = [float(v) for v in close.values]
    bars = dict(zip(bar_dates, bar_vals))
    prev_map = {bar_dates[i]: (bar_vals[i - 1] if i > 0 else None) for i in range(len(bar_dates))}

    backup = _backup_timeseries()
    rows = _load_timeseries_rows()
    added, skipped = 0, 0
    for r in rows:
        d = r.get("date", "")
        if d not in bars:
            skipped += 1
            continue
        entry = arrow_and_change(name, bars[d], prev_map.get(d))
        entry.update({
            "source": f"yfinance:{ticker}(backfill)",
            "as_of": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "stale": False, "session_kind": "us_close",
        })
        r.setdefault("assets", {})[name] = entry
        added += 1
        snap = SNAP_DIR / f"{d}.json"
        if snap.exists():
            s = json.loads(snap.read_text(encoding="utf-8"))
            s.setdefault("assets", {})[name] = entry
            snap.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_timeseries_rows(rows)
    print(json.dumps({"backup": str(backup), "asset": name, "added_days": added,
                      "no_bar_days": skipped, "bar_range": [bar_dates[0], bar_dates[-1]]}, ensure_ascii=False))


def drop_entry(spec):
    """--drop-entry ASSET:YYYYMMDD — 从 timeseries 行与快照中移除单个资产条目（治理混源残值）。"""
    name, date_key = spec.split(":")
    backup = _backup_timeseries()
    rows = _load_timeseries_rows()
    hit = False
    for r in rows:
        if r.get("date") == date_key and name in r.get("assets", {}):
            del r["assets"][name]
            hit = True
    _write_timeseries_rows(rows)
    snap = SNAP_DIR / f"{date_key}.json"
    snap_hit = False
    if snap.exists():
        s = json.loads(snap.read_text(encoding="utf-8"))
        if name in s.get("assets", {}):
            del s["assets"][name]
            snap.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
            snap_hit = True
    print(json.dumps({"backup": str(backup), "dropped": spec,
                      "timeseries_hit": hit, "snapshot_hit": snap_hit}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="3mo", help="yfinance period (default 3mo)")
    ap.add_argument("--repair-2y", action="store_true", help="rewrite US_2Y_yield from FRED DGS2")
    ap.add_argument("--rebase-2y-2yy", action="store_true", help="[已废弃 2026-07-07: 2YY 日线为稀薄成交僵尸数据] rewrite US_2Y_yield from 2YY=F daily bars")
    ap.add_argument("--add-asset", default=None, help="向既有历史增配单个价格资产（如 SHY）")
    ap.add_argument("--drop-entry", default=None, help="ASSET:YYYYMMDD 移除单日单资产条目")
    args = ap.parse_args()

    if args.add_asset:
        add_asset(args.add_asset, args.period if args.period != "3mo" else "9mo")
        return

    if args.drop_entry:
        drop_entry(args.drop_entry)
        return

    if args.rebase_2y_2yy:
        rebase_2y_2yy()
        return

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
