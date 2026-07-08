#!/usr/bin/env python3
"""Probe whether upstream daily bars changed after the frozen capture."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SNAP_DIR = DATA / "snapshots"
LOG = DATA / "shadow_probe.log"
ASSETS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Brent": "BZ=F",
    "WTI": "CL=F",
    "NatGas": "NG=F",
    "DXY": "DX-Y.NYB",
    "USDJPY": "JPY=X",
}
THRESHOLD = 0.0001


def latest_snapshot_path() -> Path:
    files = sorted(SNAP_DIR.glob("*.json"))
    if not files:
        raise RuntimeError("no snapshots found")
    return files[-1]


def import_yfinance():
    import yfinance as yf  # type: ignore

    return yf


def pct_diff(old: float, new: float) -> float:
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return abs(new - old) / abs(old)


def pair_for_date(hist: Any, ticker: str, iso_date: str) -> tuple[float | None, float | None]:
    """Return (close_at_date, prev_close) for the bar whose DATE matches the
    snapshot's data date — never the window's latest bar. Rationale: this probe
    runs at 06:37 Beijing (22:37 UTC), 37 min after CME opens the NEXT trade
    date; taking the latest bar would compare the frozen mark against tomorrow's
    thin live session and spuriously report CHANGED for all futures
    (acceptance fix, 2026-07-08)."""
    close = hist["Close"] if "Close" in hist else hist.get("Adj Close", hist)
    try:
        series = close[ticker].dropna()
    except Exception:
        series = close.dropna()
    last = prev = None
    prev_candidate = None
    for idx, value in series.items():
        d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        if d == iso_date:
            last = float(value)
            prev = prev_candidate
            break
        prev_candidate = float(value)
    return last, prev


def probe(snapshot: dict[str, Any], iso_date: str) -> tuple[dict[str, str], dict[str, float]]:
    """Returns (verdicts, revision pct per CHANGED asset). Magnitudes matter:
    2026-07-08 acceptance run showed Yahoo rewrites futures daily closes to the
    official settlement after the fact (Brent/WTI matched Wind settle exactly,
    revisions up to 2.4%) — CHANGED alone would hide the size of the drift."""
    yf = import_yfinance()
    verdicts: dict[str, str] = {}
    diffs_pct: dict[str, float] = {}
    for asset, ticker in ASSETS.items():
        frozen = snapshot.get("assets", {}).get(asset, {})
        if not isinstance(frozen, dict) or frozen.get("last") is None:
            verdicts[asset] = "ERROR"
            continue
        try:
            hist = yf.download(ticker, period="5d", interval="1d", auto_adjust=True, progress=False)
            last, prev = pair_for_date(hist, ticker, iso_date)
            if last is None:
                verdicts[asset] = "NO_BAR"  # upstream no longer serves a bar for that date
                continue
            frozen_last = float(frozen.get("last"))
            frozen_change = float(frozen.get("change", 0.0))
            live_change = (last - prev) if prev is not None else frozen_change
            changed = pct_diff(frozen_last, last) > THRESHOLD or pct_diff(frozen_change, live_change) > THRESHOLD
            verdicts[asset] = "CHANGED" if changed else "SAME"
            if changed:
                diffs_pct[asset] = round((last - frozen_last) / frozen_last * 100, 3) if frozen_last else 0.0
        except Exception:
            verdicts[asset] = "ERROR"
    return verdicts, diffs_pct


def main() -> int:
    path = latest_snapshot_path()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    date_key = path.stem
    iso_date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    verdicts, diffs_pct = probe(snapshot, iso_date)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date": date_key,
        "verdicts": verdicts,
        "revision_pct": diffs_pct,
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
