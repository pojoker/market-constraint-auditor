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
MIN_ASSETS_OK = 18

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


def trading_date(snapshot: dict) -> str:
    """Derive YYYYMMDD key from fetched_at (UTC). The US close captured at
    ~05:30 Beijing belongs to the *previous* US calendar day, but for our
    daily-series purposes we key by the capture's UTC date, which is stable."""
    ts = snapshot.get("fetched_at", datetime.now(timezone.utc).isoformat())
    return datetime.fromisoformat(ts).strftime("%Y%m%d")


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
    lines = []
    if TIMESERIES.exists():
        for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("date") != date_key:  # keep all other days
                lines.append(obj)
    lines.append(record)
    lines.sort(key=lambda o: o.get("date", ""))
    with open(TIMESERIES, "w", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return len(lines)


def has_data_changed(snapshot: dict, date_key: str) -> bool:
    """Compare new snapshot's asset 'last' values against the most recent
    *different-day* timeseries entry. Returns False if essentially identical
    (market closed / no new bar) — lets the analysis layer know to abstain."""
    if not TIMESERIES.exists():
        return True
    prev = None
    for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("date") and obj["date"] < date_key:
            prev = obj
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

    date_key = trading_date(snapshot)
    changed = has_data_changed(snapshot, date_key)
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
    }

    snap_path = write_snapshot(snapshot, date_key)
    n = upsert_timeseries(snapshot, date_key)
    prefix = "WARN" if snapshot["_capture"]["degraded"] else "OK"
    log(
        f"{prefix} {date_key}: {len(ok)}/{len(assets)} assets, "
        f"degraded={snapshot['_capture']['degraded']}, missing={missing}, "
        f"changed={changed}, partial={partial_session}, timeseries={n} days → {snap_path.name}"
    )


if __name__ == "__main__":
    main()
