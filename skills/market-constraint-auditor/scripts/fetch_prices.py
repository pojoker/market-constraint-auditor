#!/usr/bin/env python3
"""
Fetch key cross-asset prices for market constraint diagnosis.
Output: JSON to stdout, errors to stderr.

Usage:
    python3 fetch_prices.py
    python3 fetch_prices.py --period 5d   # last 5 days of closes
"""

import json
import sys
import argparse
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    print(json.dumps({"error": "yfinance not installed. Run: pip install yfinance"}))
    sys.exit(1)

# Asset map: display_name -> yfinance ticker
ASSETS = {
    "DXY":         "DX-Y.NYB",   # US Dollar Index
    "US_2Y_yield": "^IRX",       # 13-week proxy; use ^TXN for 2Y (not always available)
    "US_10Y_yield":"^TNX",       # 10-Year Treasury yield (x10 = actual %)
    "US_30Y_yield":"^TYX",       # 30-Year Treasury yield
    "Gold":        "GC=F",       # Gold futures (front month)
    "Silver":      "SI=F",       # Silver futures
    "Brent":       "BZ=F",       # Brent crude futures
    "WTI":         "CL=F",       # WTI crude futures
    "NatGas":      "NG=F",       # Natural gas futures
    "SP500":       "^GSPC",      # S&P 500
    "Nasdaq":      "^IXIC",      # Nasdaq Composite
    "Russell2000": "^RUT",       # Russell 2000 (small cap / risk barometer)
    "VIX":         "^VIX",       # CBOE Volatility Index
    "MOVE":        "^MOVE",      # Treasury volatility index (not always on yf)
    "EM_ETF":      "EEM",        # Emerging Markets ETF (USD funding stress proxy)
    "HYG":         "HYG",        # High Yield Bond ETF (credit stress)
    "TLT":         "TLT",        # 20Y Treasury ETF (bonds direction)
    "Copper":      "HG=F",       # Copper futures (growth proxy)
    "USDCNY":      "CNYUSD=X",   # CNY/USD (EM/China stress)
    "USDJPY":      "JPY=X",      # USD/JPY (carry / funding)
}

def fetch_snapshot(period: str = "2d") -> dict:
    tickers = list(ASSETS.values())
    data = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    close = data["Close"] if "Close" in data else data.get("Adj Close", data)

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "assets": {},
    }

    for name, ticker in ASSETS.items():
        try:
            series = close[ticker].dropna()
            if len(series) < 1:
                result["assets"][name] = {"error": "no data"}
                continue

            latest = float(series.iloc[-1])
            prev   = float(series.iloc[-2]) if len(series) >= 2 else None

            # yfinance 1.x returns Treasury yields as actual % (e.g. 4.34 = 4.34%)
            # No adjustment needed.

            entry = {"last": round(latest, 4)}
            if prev is not None:
                change     = latest - prev
                change_pct = (change / prev) * 100 if prev != 0 else None
                entry["prev"]       = round(prev, 4)
                entry["change"]     = round(change, 4)
                entry["change_pct"] = round(change_pct, 2) if change_pct is not None else None
                # Direction arrow for quick scanning
                if abs(change_pct) < 0.05:
                    entry["dir"] = "—"
                elif change_pct > 0:
                    entry["dir"] = "↑" if change_pct < 1 else "↑↑" if change_pct < 3 else "↑↑↑"
                else:
                    entry["dir"] = "↓" if change_pct > -1 else "↓↓" if change_pct > -3 else "↓↓↓"

            result["assets"][name] = entry

        except Exception as e:
            result["assets"][name] = {"error": str(e)}

    return result


def print_summary(data: dict):
    """Print a human-readable summary table to stderr for quick inspection."""
    print(f"\n=== Market Snapshot ({data['fetched_at'][:19]} UTC) ===", file=sys.stderr)
    print(f"{'Asset':<15} {'Last':>10} {'Chg%':>8} {'Dir':>5}", file=sys.stderr)
    print("-" * 45, file=sys.stderr)
    for name, v in data["assets"].items():
        if "error" in v:
            print(f"{name:<15} {'ERROR':>10}", file=sys.stderr)
        else:
            last  = f"{v['last']:,.4f}"
            chg   = f"{v.get('change_pct', 0):+.2f}%" if v.get('change_pct') is not None else "N/A"
            arrow = v.get('dir', '')
            print(f"{name:<15} {last:>10} {chg:>8} {arrow:>5}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="2d",
                        help="yfinance period string: 1d, 2d, 5d, 1mo (default: 2d)")
    parser.add_argument("--summary", action="store_true",
                        help="Print human-readable table to stderr")
    args = parser.parse_args()

    snapshot = fetch_snapshot(args.period)

    if args.summary or not sys.stdout.isatty():
        print_summary(snapshot)

    print(json.dumps(snapshot, indent=2))
