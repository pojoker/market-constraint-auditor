#!/usr/bin/env python3
"""
Fetch key cross-asset prices for market constraint diagnosis.
Output: JSON to stdout, errors to stderr.
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

try:
    import yfinance as yf
except ImportError:
    print(json.dumps({"error": "yfinance not installed. Run: pip install yfinance"}))
    sys.exit(1)


ASSETS = {
    "DXY": "DX-Y.NYB",
    "US_2Y_yield": "2YY=F",
    "US_10Y_yield": "^TNX",
    "US_30Y_yield": "^TYX",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Brent": "BZ=F",
    "WTI": "CL=F",
    "NatGas": "NG=F",
    "SP500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Russell2000": "^RUT",
    "VIX": "^VIX",
    "MOVE": "^MOVE",
    "EM_ETF": "EEM",
    "HYG": "HYG",
    "TLT": "TLT",
    "Copper": "HG=F",
    "USDCNY": "USDCNY=X",
    "USDJPY": "JPY=X",
    "BTC": "BTC-USD",
}

YIELD_ASSETS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}
FRED_SERIES = {
    "US_2Y_yield": "DGS2",
    "US_10Y_yield": "DGS10",
    "US_30Y_yield": "DGS30",
}
CALENDAR_ALIGN_TO_EQUITY = {"BTC"}
EQUITY_ANCHOR_TICKER = "^GSPC"


def download_with_retries(tickers, period, attempts=3):
    last_exc = None
    for i in range(attempts):
        try:
            return yf.download(
                tickers,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as exc:
            last_exc = exc
            if i < attempts - 1:
                time.sleep(2**i)
    raise RuntimeError(f"yf.download failed after {attempts} attempts: {last_exc}")


def close_frame(data):
    return data["Close"] if "Close" in data else data.get("Adj Close", data)


def fred_series(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    res = requests.get(url, timeout=20)
    res.raise_for_status()
    rows = []
    for row in csv.DictReader(io.StringIO(res.text)):
        val = row.get(series_id)
        if not val or val == ".":
            continue
        try:
            rows.append((row["observation_date"], float(val)))
        except (KeyError, ValueError):
            continue
    return rows


def latest_fred_pair(asset):
    rows = fred_series(FRED_SERIES[asset])
    if not rows:
        raise RuntimeError(f"FRED {FRED_SERIES[asset]} no data")
    latest = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    return latest, prev


def session_kind_for_index(idx, fetched_at):
    try:
        last_dt = idx[-1].to_pydatetime()
    except Exception:
        return "us_close"
    if last_dt.tzinfo is not None:
        last_dt = last_dt.astimezone(timezone.utc).replace(tzinfo=None)
    now = fetched_at.replace(tzinfo=None)
    if last_dt.date() == now.date() and now.hour < 21:
        return "intraday_stale"
    return "us_close"


def build_entry(name, last, prev, source, as_of=None, stale=False, session_kind="us_close"):
    entry = {
        "last": round(last, 4),
        "source": source,
        "as_of": as_of,
        "stale": bool(stale),
        "session_kind": session_kind,
    }
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
        pct = (change / prev) * 100 if prev else None
        entry["change_pct"] = round(pct, 2) if pct is not None else None
        entry["unit"] = "%"
        if pct is None or abs(pct) < 0.05:
            entry["dir"] = "—"
        elif pct > 0:
            entry["dir"] = "↑" if pct < 1 else "↑↑" if pct < 3 else "↑↑↑"
        else:
            entry["dir"] = "↓" if pct > -1 else "↓↓" if pct > -3 else "↓↓↓"
    return entry


def series_for(close, name, ticker):
    if name in CALENDAR_ALIGN_TO_EQUITY and EQUITY_ANCHOR_TICKER in close:
        return close[ticker].where(close[EQUITY_ANCHOR_TICKER].notna()).dropna()
    return close[ticker].dropna()


def fallback_yield(asset):
    (as_of, last), prev_pair = latest_fred_pair(asset)
    prev = prev_pair[1] if prev_pair else None
    return build_entry(
        asset,
        last,
        prev,
        source=f"FRED:{FRED_SERIES[asset]}",
        as_of=as_of,
        stale=True,
        session_kind="prior_close",
    )


def parse_simulated_missing(arg):
    values = set()
    for raw in [arg, os.environ.get("FETCH_SIMULATE_MISSING", "")]:
        if not raw:
            continue
        values.update(x.strip() for x in raw.split(",") if x.strip())
    return values


def fetch_snapshot(period="5d", simulate_missing=None):
    simulate_missing = simulate_missing or set()
    fetched_at = datetime.now(timezone.utc)
    result = {
        "fetched_at": fetched_at.isoformat(),
        "period": period,
        "assets": {},
    }

    try:
        data = download_with_retries(list(ASSETS.values()), period)
        close = close_frame(data)
    except Exception as exc:
        close = None
        result["_fetch_error"] = str(exc)

    reference_as_of = None
    if close is not None:
        refs = []
        for ref_asset in ("DXY", "SP500", "US_10Y_yield", "US_30Y_yield"):
            try:
                s = series_for(close, ref_asset, ASSETS[ref_asset])
                if len(s) >= 1:
                    refs.append(s.index[-1].strftime("%Y-%m-%d"))
            except Exception:
                pass
        reference_as_of = max(refs) if refs else None

    for name, ticker in ASSETS.items():
        if name in simulate_missing:
            result["assets"][name] = {"error": "simulated missing", "source": "simulate"}
            continue
        try:
            if close is None:
                raise RuntimeError(result.get("_fetch_error", "download failed"))
            series = series_for(close, name, ticker)
            if len(series) < 1:
                raise RuntimeError("no data")
            latest = float(series.iloc[-1])
            prev = float(series.iloc[-2]) if len(series) >= 2 else None
            as_of = series.index[-1].strftime("%Y-%m-%d")
            if name in FRED_SERIES and reference_as_of and as_of < reference_as_of:
                result["assets"][name] = fallback_yield(name)
                result["assets"][name]["fallback_reason"] = f"yfinance stale as_of={as_of}, reference_as_of={reference_as_of}"
                continue
            result["assets"][name] = build_entry(
                name,
                latest,
                prev,
                source=f"yfinance:{ticker}",
                as_of=as_of,
                stale=False,
                session_kind=session_kind_for_index(series.index, fetched_at),
            )
        except Exception as exc:
            if name in FRED_SERIES:
                try:
                    result["assets"][name] = fallback_yield(name)
                    continue
                except Exception as fred_exc:
                    result["assets"][name] = {
                        "error": f"{exc}; FRED fallback failed: {fred_exc}",
                        "source": f"yfinance:{ticker}",
                    }
            else:
                result["assets"][name] = {"error": str(exc), "source": f"yfinance:{ticker}"}

    return result


def print_summary(data):
    print(f"\n=== Market Snapshot ({data['fetched_at'][:19]} UTC) ===", file=sys.stderr)
    print(f"{'Asset':<15} {'Last':>10} {'Chg':>8} {'Dir':>5} {'Source':>16}", file=sys.stderr)
    print("-" * 62, file=sys.stderr)
    for name, v in data["assets"].items():
        if "error" in v:
            print(f"{name:<15} {'ERROR':>10} {'':>8} {'':>5} {v.get('source',''):>16}", file=sys.stderr)
            continue
        chg = v.get("change_bps") if name in YIELD_ASSETS else v.get("change_pct")
        suffix = "bp" if name in YIELD_ASSETS else "%"
        chg_s = f"{chg:+.2f}{suffix}" if chg is not None else "N/A"
        print(
            f"{name:<15} {v['last']:>10,.4f} {chg_s:>8} {v.get('dir',''):>5} {v.get('source',''):>16}",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="5d")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--simulate-missing", default="")
    args = parser.parse_args()

    snapshot = fetch_snapshot(args.period, parse_simulated_missing(args.simulate_missing))
    if args.summary or not sys.stdout.isatty():
        print_summary(snapshot)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
