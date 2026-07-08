#!/usr/bin/env python3
"""Wind EDB arbiter for suspected futures ghost bars."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


NODE = "/Users/jowang/.nvm/versions/node/v22.22.3/bin/node"
WIND_SKILL_DIR = Path.home() / ".agents/skills/wind-mcp-skill"
WIND_CLI = WIND_SKILL_DIR / "scripts/cli.mjs"
RETRYABLE = {"SERVER_5XX", "NETWORK_ERROR", "RATE_LIMIT_QPS"}
MOVE_THRESHOLD = 0.0005
EDB_CODES = {
    "Gold": "S0180945",
    "Silver": "S0180964",
    "Copper": "S0180946",
    "WTI": "S0180938",
    "Brent": "S0031525",
    "NatGas": "S0069682",
}


def query_dates(today: datetime | None = None) -> tuple[str, str]:
    today = today or datetime.now(timezone.utc)
    begin = today - timedelta(days=5)
    return begin.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def wind_command(code: str, begin: str, end: str) -> list[str]:
    payload = json.dumps(
        {
            "executionMode": "fetch",
            "question": code,
            "beginDate": begin,
            "endDate": end,
        },
        ensure_ascii=False,
    )
    return [
        NODE,
        str(WIND_CLI),
        "call",
        "economic_data",
        "natural_language_get_edb_data",
        payload,
    ]


def run_wind(code: str, begin: str, end: str) -> dict[str, Any]:
    res = subprocess.run(
        wind_command(code, begin, end),
        cwd=str(WIND_SKILL_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"wind cli exit {res.returncode}: {res.stderr[:300]}")
    return json.loads(res.stdout)


def envelope_error(envelope: dict[str, Any]) -> str | None:
    err = envelope.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        return str(code) if code else "UNKNOWN"
    return None


def fetch_envelope(code: str, begin: str, end: str) -> dict[str, Any]:
    envelope = run_wind(code, begin, end)
    err = envelope_error(envelope)
    if err in RETRYABLE:
        time.sleep(3)
        envelope = run_wind(code, begin, end)
    return envelope


def parse_official_pair(envelope: dict[str, Any], code: str) -> tuple[float, float] | None:
    if envelope_error(envelope):
        return None
    content = envelope.get("content")
    if not isinstance(content, list) or not content:
        return None
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not text:
        return None
    inner = json.loads(text)
    series = inner.get("data", {}).get("data", [])
    for item in series:
        meta = item.get("meta", {}) if isinstance(item, dict) else {}
        if meta.get("code") and meta.get("code") != code:
            continue
        dates = item.get("date", [])
        values = item.get("value", [])
        pairs = []
        for d, v in zip(dates, values):
            if d is None or v is None:
                continue
            try:
                pairs.append((str(d), float(v)))
            except (TypeError, ValueError):
                continue
        if len(pairs) >= 2:
            pairs.sort(key=lambda x: x[0])
            return pairs[-2][1], pairs[-1][1]
    return None


def verdict_from_pair(prev: float, last: float) -> str:
    base = abs(prev)
    move = abs(last - prev) / base if base else (0.0 if last == prev else float("inf"))
    return "confirmed" if move > MOVE_THRESHOLD else "acquitted"


def unavailable(code: str, error: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"code": code, "prev": None, "last": None, "source": "wind-edb"}
    if error:
        ref["error"] = error
    return {"ghost_verdict": "unavailable", "official_ref": ref}


def arbitrate_asset(asset: str, bar: dict[str, Any] | None = None) -> dict[str, Any]:
    code = EDB_CODES.get(asset)
    if not code:
        return unavailable("", f"no EDB code for {asset}")
    begin, end = query_dates()
    try:
        envelope = fetch_envelope(code, begin, end)
        pair = parse_official_pair(envelope, code)
        if pair is None:
            return unavailable(code, envelope_error(envelope) or "no official pair")
        prev, last = pair
        return {
            "ghost_verdict": verdict_from_pair(prev, last),
            "official_ref": {"code": code, "prev": prev, "last": last, "source": "wind-edb"},
        }
    except Exception as exc:
        return unavailable(code, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Arbitrate one suspected futures ghost bar.")
    parser.add_argument("asset", choices=sorted(EDB_CODES))
    args = parser.parse_args()
    print(json.dumps(arbitrate_asset(args.asset, {}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
