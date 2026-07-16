#!/usr/bin/env python3
"""
capture_snapshot.py — Layer 1 of the decoupled architecture.

Runs the skill's fetch_prices.py, freezes the result to disk:
  - data/snapshots/YYYYMMDD.json   (one frozen daily mark)
  - data/timeseries.jsonl          (rolling append, one line per trading day)

No LLM. Pure data capture. Designed to run from launchd daily after US close.

Re-running the same day overwrites that day's snapshot and timeseries entry
(idempotent), so a manual re-run never duplicates a day.
"""

import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SNAP_DIR = DATA / "snapshots"
TIMESERIES = DATA / "timeseries.jsonl"
LOG = DATA / "capture.log"
CORRECTIONS_LOG = DATA / "corrections.log"
MIN_ASSETS_OK = 18
FUTURES_ASSETS = {"Gold", "Silver", "Copper", "Brent", "WTI", "NatGas"}
FUTURES_TICKERS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Brent": "BZ=F",
    "WTI": "CL=F",
    "NatGas": "NG=F",
}
RETRO_THRESHOLD = 0.0001

# Canonical fetch script = the active skill copy (kept in sync with backfill).
# Previously pointed at a frozen 1.0.1 plugin-cache copy, which drifted from the
# active asset list; repointed here so there is a single source of truth.
FETCH_SCRIPT = (
    Path.home()
    / ".claude/skills/market-constraint-auditor"
    / "scripts/fetch_prices.py"
)
TRACKED_FETCH_SCRIPT = (
    REPO / "skills/market-constraint-auditor/scripts/fetch_prices.py"
)


def log(msg: str):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_fetch_copy_drift():
    active = hash_file(FETCH_SCRIPT)
    tracked = hash_file(TRACKED_FETCH_SCRIPT)
    if active and tracked and active != tracked:
        log("WARN: fetch_prices copies diverged")


def fetch() -> dict:
    """Run fetch_prices.py, return parsed JSON snapshot (stdout = pure JSON)."""
    res = subprocess.run(
        ["/Users/jowang/miniconda3/bin/python3", str(FETCH_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(f"fetch_prices.py exit {res.returncode}: {res.stderr[:500]}")
    return json.loads(res.stdout)


def load_timeseries(path: Path = TIMESERIES) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda o: o.get("date", ""))
    return rows


def write_timeseries_rows(rows: list[dict], path: Path = TIMESERIES) -> int:
    rows = sorted(rows, key=lambda o: o.get("date", ""))
    with open(path, "w", encoding="utf-8") as f:
        for obj in rows:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return len(rows)


def previous_row(rows: list[dict], date_key: str) -> dict | None:
    prev = None
    for row in rows:
        if row.get("date") and row["date"] < date_key:
            prev = row
    return prev


def same_number(a, b) -> bool:
    return a is not None and b is not None and a == b


def sp500_as_of_advanced(snapshot: dict, prev: dict | None) -> bool:
    if prev is None:
        return False
    new_as_of = snapshot.get("assets", {}).get("SP500", {}).get("as_of")
    old_as_of = prev.get("assets", {}).get("SP500", {}).get("as_of")
    return bool(new_as_of and old_as_of and new_as_of > old_as_of)


def mark_ghost_suspects(snapshot: dict, date_key: str, rows: list[dict]) -> list[str]:
    """Flag futures whose last/change exactly freeze while SP500 made a new bar."""
    prev = previous_row(rows, date_key)
    if not sp500_as_of_advanced(snapshot, prev):
        return []
    assets = snapshot.get("assets", {})
    old_assets = prev.get("assets", {}) if prev else {}
    suspects = []
    for name in FUTURES_ASSETS:
        new = assets.get(name)
        old = old_assets.get(name)
        if not isinstance(new, dict) or not isinstance(old, dict):
            continue
        if same_number(new.get("last"), old.get("last")) and same_number(new.get("change"), old.get("change")):
            new["ghost_suspect"] = True
            suspects.append(name)
    return suspects


def arbitrate_ghost_suspects(snapshot: dict, suspects: list[str]) -> None:
    if not suspects:
        return
    try:
        from wind_arbiter import arbitrate_asset
    except Exception as exc:
        for name in suspects:
            snapshot["assets"][name]["ghost_verdict"] = "unavailable"
            snapshot["assets"][name]["official_ref"] = {"source": "wind-edb", "error": str(exc)}
        return
    for name in suspects:
        entry = snapshot.get("assets", {}).get(name, {})
        try:
            result = arbitrate_asset(name, entry)
        except Exception as exc:
            result = {"ghost_verdict": "unavailable", "official_ref": {"source": "wind-edb", "error": str(exc)}}
        entry.update(result)


def pct_diff(old: float, new: float) -> float:
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return abs(new - old) / abs(old)


def change_dir(change: float, pct: float | None) -> str:
    if pct is None or abs(pct) < 0.05:
        return "—"
    if pct > 0:
        return "↑" if pct < 1 else "↑↑" if pct < 3 else "↑↑↑"
    return "↓" if pct > -1 else "↓↓" if pct > -3 else "↓↓↓"


def recompute_price_entry(entry: dict, last: float, prev_last: float | None) -> None:
    entry["last"] = round(float(last), 4)
    if prev_last is None:
        return
    change = float(last) - float(prev_last)
    pct = (change / float(prev_last)) * 100 if prev_last else None
    entry["prev"] = round(float(prev_last), 4)
    entry["change"] = round(change, 4)
    entry["change_pct"] = round(pct, 2) if pct is not None else None
    entry["unit"] = "%"
    entry["dir"] = change_dir(change, pct)


def normalize_window_bars(raw) -> dict[str, dict[str, float]]:
    """Return {asset: {YYYY-MM-DD: close}} from injected/fetched window shapes."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for asset, bars in raw.items():
        asset_bars: dict[str, float] = {}
        if isinstance(bars, dict):
            items = bars.items()
        elif isinstance(bars, list):
            items = []
            for row in bars:
                if isinstance(row, dict):
                    d = row.get("date") or row.get("Date") or row.get("as_of")
                    v = row.get("close") if "close" in row else row.get("Close")
                    items.append((d, v))
        else:
            items = []
        for d, v in items:
            if d is None or v is None:
                continue
            try:
                asset_bars[str(d)[:10]] = float(v)
            except (TypeError, ValueError):
                continue
        if asset_bars:
            out[asset] = asset_bars
    return out


def import_yfinance():
    import yfinance as yf  # type: ignore

    return yf


def download_futures_window() -> dict[str, dict[str, float]]:
    yf = import_yfinance()
    raw = yf.download(
        list(FUTURES_TICKERS.values()),
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    close = raw["Close"] if "Close" in raw else raw.get("Adj Close", raw)
    out: dict[str, dict[str, float]] = {}
    for asset, ticker in FUTURES_TICKERS.items():
        try:
            series = close[ticker].dropna()
        except Exception:
            continue
        out[asset] = {idx.strftime("%Y-%m-%d"): float(value) for idx, value in series.items()}
    return out


def futures_window_from_snapshot(snapshot: dict) -> dict[str, dict[str, float]]:
    for key in ("download_window", "_download_window", "history", "_history", "bars", "_bars"):
        window = normalize_window_bars(snapshot.get(key))
        if window:
            return window
    return download_futures_window()


def apply_retro_corrections(
    rows: list[dict],
    snapshot: dict,
    date_key: str,
    futures_window: dict[str, dict[str, float]],
    corrections_log: Path = CORRECTIONS_LOG,
    snap_dir: Path = SNAP_DIR,
) -> int:
    """Correct only the most recent prior trading-day futures entries."""
    if not rows:
        return 0
    prior_idx = None
    for i, row in enumerate(rows):
        if row.get("date") and row["date"] < date_key:
            prior_idx = i
    if prior_idx is None:
        return 0
    yesterday = rows[prior_idx]
    yesterday_date = yesterday.get("date", "")
    yesterday_iso = f"{yesterday_date[:4]}-{yesterday_date[4:6]}-{yesterday_date[6:8]}"
    prev_for_change = rows[prior_idx - 1] if prior_idx > 0 else None
    corrections = []
    for asset in FUTURES_ASSETS:
        entry = yesterday.get("assets", {}).get(asset)
        close = futures_window.get(asset, {}).get(yesterday_iso)
        if not isinstance(entry, dict) or close is None or entry.get("retro_corrected"):
            continue
        old_last = entry.get("last")
        if old_last is None or pct_diff(float(old_last), float(close)) <= RETRO_THRESHOLD:
            continue
        old_change = entry.get("change")
        entry["pre_correction"] = {"last": old_last, "change": old_change}
        prev_last = None
        if prev_for_change:
            prev_entry = prev_for_change.get("assets", {}).get(asset, {})
            prev_last = prev_entry.get("last")
        recompute_price_entry(entry, float(close), float(prev_last) if prev_last is not None else None)
        entry["retro_corrected"] = True
        corrections.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "asset": asset,
                "date": yesterday_date,
                "old_last": old_last,
                "new_last": entry["last"],
                "old_change": old_change,
                "new_change": entry.get("change"),
            }
        )
        snap_path = snap_dir / f"{yesterday_date}.json"
        if snap_path.exists():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            snap_entry = snap.get("assets", {}).get(asset)
            if isinstance(snap_entry, dict) and not snap_entry.get("retro_corrected"):
                snap_entry.clear()
                snap_entry.update(entry)
                snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    if corrections:
        corrections_log.parent.mkdir(parents=True, exist_ok=True)
        with corrections_log.open("a", encoding="utf-8") as f:
            for item in corrections:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(corrections)


def trading_date(snapshot: dict) -> str:
    """Derive YYYYMMDD key from fetched_at (UTC). The US close captured at
    ~05:30 Beijing belongs to the *previous* US calendar day, but for our
    daily-series purposes we key by the capture's UTC date, which is stable."""
    ts = snapshot.get("fetched_at", datetime.now(timezone.utc).isoformat())
    return datetime.fromisoformat(ts).strftime("%Y%m%d")


def anchor_data_date(snapshot: dict) -> str | None:
    """数据日 = 股指锚（SP500）的 as_of，YYYYMMDD；缺失/不可解析返回 None。"""
    as_of = snapshot.get("assets", {}).get("SP500", {}).get("as_of")
    if isinstance(as_of, str) and len(as_of) >= 10:
        compact = as_of[:10].replace("-", "")
        if compact.isdigit() and len(compact) == 8:
            return compact
    return None


def resolve_date_key(snapshot: dict, changed: bool) -> str:
    """键位规则（Round 10，2026-07-11）——一周三次键位事故后收敛：

    - 有新收盘（changed=True）→ 键 = 数据日（SP500 as_of）。准点运行
      （21:45 UTC）时与捕获 UTC 日恒等（行为零变化）；晚发运行（跨 UTC
      午夜，如 07-11 02:24 捕获 07-10 收盘）自动挂对数据日，不再错挂
      捕获日、也不会被当晚正常捕获同键覆盖。
    - 闭市日（changed=False，锚未前进）→ 维持捕获 UTC 日——重复行按
      捕获日记档是 Round 6 压缩序列去重逻辑的既有输入语义，不得改变。
    - SP500 缺失/as_of 不可解析 → 回退捕获 UTC 日 + WARN。
    """
    fetch_key = trading_date(snapshot)
    if not changed:
        return fetch_key
    data_key = anchor_data_date(snapshot)
    if data_key is None:
        log(f"WARN {fetch_key}: SP500 as_of unavailable; falling back to fetch-date key")
        return fetch_key
    return data_key


def detect_partial_session(snapshot: dict) -> tuple[bool, str | None]:
    """Return whether the mark mixes stale US equities with newer assets."""
    assets = snapshot.get("assets", {})
    sp500 = assets.get("SP500")
    if not isinstance(sp500, dict):
        return False, "SP500 asset missing"
    sp_as_of = sp500.get("as_of")
    dated_assets = [
        (name, value.get("as_of"))
        for name, value in assets.items()
        if isinstance(value, dict) and value.get("as_of")
    ]
    if not sp_as_of or not dated_assets:
        return False, "as_of missing for SP500 or all assets"
    max_as_of = max(as_of for _, as_of in dated_assets)
    return sp_as_of < max_as_of, None


def write_snapshot(snapshot: dict, date_key: str):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{date_key}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def upsert_timeseries(snapshot: dict, date_key: str):
    """Append one line per trading day; replace if the day already exists."""
    record = {"date": date_key, **snapshot}
    lines = [obj for obj in load_timeseries() if obj.get("date") != date_key]
    lines.append(record)
    lines.sort(key=lambda o: o.get("date", ""))
    return write_timeseries_rows(lines)


def has_data_changed(snapshot: dict, date_key: str) -> bool:
    """Compare new snapshot's asset 'last' values against the most recent
    *different-day* timeseries entry. Returns False if essentially identical
    (market closed / no new bar) — lets the analysis layer know to abstain."""
    if not TIMESERIES.exists():
        return True
    prev = previous_row(load_timeseries(), date_key)
    if prev is None:
        return True
    new_assets = snapshot.get("assets", {})
    old_assets = prev.get("assets", {})
    for k, v in new_assets.items():
        if "last" not in v:
            continue
        ov = old_assets.get(k, {}).get("last")
        if ov is None or v["last"] != ov:
            return True
    return False


def main():
    check_fetch_copy_drift()
    try:
        snapshot = fetch()
    except Exception as e:
        log(f"FETCH FAILED: {e}")
        sys.exit(1)

    # Guard: if every asset errored, don't persist garbage.
    assets = snapshot.get("assets", {})
    ok = [k for k, v in assets.items() if "last" in v]
    missing = [k for k, v in assets.items() if "last" not in v]
    if not ok:
        log(f"ABORT: no asset returned data ({len(assets)} assets, all errored)")
        sys.exit(1)

    # Round 10：先判"有无新收盘"，再据此裁决键位（数据日 vs 捕获日）。
    # has_data_changed 的 prev 查找用 fetch-date 键与数据日键结果恒同
    # （prev = date < key 的最近行，两种键都大于任何既有行日期）。
    fetch_key = trading_date(snapshot)
    changed = has_data_changed(snapshot, fetch_key)
    date_key = resolve_date_key(snapshot, changed)
    rows = load_timeseries()
    suspects = mark_ghost_suspects(snapshot, date_key, rows)
    arbitrate_ghost_suspects(snapshot, suspects)
    try:
        futures_window = futures_window_from_snapshot(snapshot)
        retro_n = apply_retro_corrections(rows, snapshot, date_key, futures_window)
        if retro_n:
            write_timeseries_rows(rows)
    except Exception as exc:
        retro_n = 0
        log(f"WARN {date_key}: retro correction skipped ({exc})")
    partial_session, partial_warn = detect_partial_session(snapshot)
    if partial_warn:
        log(f"WARN {date_key}: partial_session=false ({partial_warn})")
    snapshot["_capture"] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "assets_ok": len(ok),
        "assets_total": len(assets),
        "missing": missing,
        "degraded": len(ok) < MIN_ASSETS_OK,
        "data_changed_vs_prev": changed,
        "partial_session": partial_session,
        "ghost_suspects": suspects,
        "retro_corrections": retro_n,
    }

    snap_path = write_snapshot(snapshot, date_key)
    n = upsert_timeseries(snapshot, date_key)
    prefix = "WARN" if snapshot["_capture"]["degraded"] else "OK"
    log(
        f"{prefix} {date_key}: {len(ok)}/{len(assets)} assets, "
        f"degraded={snapshot['_capture']['degraded']}, missing={missing}, "
        f"changed={changed}, partial={partial_session}, ghosts={suspects}, "
        f"retro={retro_n}, timeseries={n} days → {snap_path.name}"
    )


if __name__ == "__main__":
    main()
