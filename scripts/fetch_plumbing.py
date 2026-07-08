#!/usr/bin/env python3
"""
fetch_plumbing.py — quantity plumbing layer for L/F context.

Fetches NYFed + FRED plumbing series and upserts one JSONL row per data day.
Network calls are best-effort: partial source failures are recorded per key and
the process still succeeds when at least one value is available.
"""

import argparse
import csv
import io
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "data" / "plumbing.jsonl"
UA = {"User-Agent": "Mozilla/5.0"}

SOFR_LAST_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/5.json"
SOFR_SEARCH_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
ONRRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"
# SRF 走通用 results 端点（验收修正 2026-07-09：/rp/repo/propositions 返回 400，
# 实测正确路径为 /rp/results/search.json + operationTypes=Repo）
SRF_URL = "https://markets.newyorkfed.org/api/rp/results/search.json"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

SERIES_ORDER = ["SOFR", "ONRRP", "SRF", "IORB", "TGA", "WALCL"]
FRED_SPECS = {
    "IORB": {"id": "IORB", "unit": "%", "scale": 1.0},
    "TGA": {"id": "WTREGEN", "unit": "$bn", "scale": 0.001},
    "WALCL": {"id": "WALCL", "unit": "$mn", "scale": 1.0},
}
NYFED_SPECS = {
    "SOFR": {"unit": "%", "source": "nyfed-api"},
    "ONRRP": {"unit": "$bn", "source": "nyfed-api"},
    "SRF": {"unit": "$bn", "source": "nyfed-api"},
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ymd(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def compact_date(d: date | None = None) -> str:
    return (d or utc_now().date()).strftime("%Y%m%d")


def request_text(url: str) -> str:
    last_error = None
    for attempt in range(3):
        try:
            res = requests.get(url, headers=UA, timeout=20)
            res.raise_for_status()
            return res.text
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(str(last_error))


def request_json(url: str) -> dict:
    return json.loads(request_text(url))


def query_url(base: str, params: dict[str, str]) -> str:
    return f"{base}?{urlencode(params)}"


def parse_float(raw) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text or text == ".":
        return None
    return float(text)


def normalize_bn(raw) -> float | None:
    """NYFed rp API 的 totalAmtAccepted 恒为美元原值 → 统一 /1e9 换算 $bn。
    验收修正 2026-07-09：原实现按数量级猜单位（≥1e9 除 1e9、≥1e4 除 1e3），
    当日接纳额 < $1bn 时会错三个数量级——而 ONRRP 缓冲池现仅 $1-4.5bn，
    跌破 $1bn 完全可能。av < 1e6 视为测试注入的已换算 $bn 值原样返回。"""
    value = parse_float(raw)
    if value is None:
        return None
    av = abs(value)
    if av >= 1_000_000:
        return value / 1_000_000_000
    return value


def entry(value, as_of: str | None, unit: str, source: str, error: str | None = None) -> dict:
    out = {"value": value, "as_of": as_of, "unit": unit, "source": source}
    if error:
        out["error"] = error
    return out


def error_entry(unit: str, source: str, error: str) -> dict:
    return entry(None, None, unit, source, error[:180])


def parse_sofr(payload: dict) -> dict[str, float]:
    rows = payload.get("refRates") or payload.get("refRatesValues") or []
    out = {}
    for row in rows:
        d = row.get("effectiveDate") or row.get("date")
        v = row.get("percentRate") if "percentRate" in row else row.get("rate")
        val = parse_float(v)
        if d and val is not None:
            out[str(d)[:10]] = val
    return out


def rp_operations(payload: dict) -> list[dict]:
    repo = payload.get("repo") if isinstance(payload, dict) else None
    if isinstance(repo, dict):
        ops = repo.get("operations")
        if isinstance(ops, list):
            return ops
    ops = payload.get("operations") if isinstance(payload, dict) else None
    return ops if isinstance(ops, list) else []


def parse_rp(payload: dict) -> dict[str, float]:
    """同一日可能有多次操作（SRF 每日早/午两场）——按日求和而非覆盖
    （验收修正 2026-07-09）。"""
    out: dict[str, float] = {}
    for row in rp_operations(payload):
        d = row.get("operationDate") or row.get("date")
        val = normalize_bn(row.get("totalAmtAccepted"))
        if d and val is not None:
            key = str(d)[:10]
            out[key] = round(out.get(key, 0.0) + val, 6)
    return out


def parse_fred_csv(text: str, scale: float) -> dict[str, float]:
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        d = row.get("observation_date") or row.get("DATE") or row.get("date")
        value_col = next((k for k in row if k and k.upper() not in {"DATE", "OBSERVATION_DATE"}), None)
        val = parse_float(row.get(value_col) if value_col else None)
        if d and val is not None:
            out[str(d)[:10]] = val * scale
    return out


def latest_map_value(values: dict[str, float]) -> tuple[str | None, float | None]:
    if not values:
        return None, None
    d = sorted(values)[-1]
    return d, values[d]


def fetch_current_maps() -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    maps: dict[str, dict[str, float]] = {}
    errors: dict[str, str] = {}
    start_10 = ymd(utc_now().date() - timedelta(days=10))
    start_30 = ymd(utc_now().date() - timedelta(days=30))
    fetches = [
        ("SOFR", lambda: parse_sofr(request_json(SOFR_LAST_URL))),
        ("ONRRP", lambda: parse_rp(request_json(query_url(ONRRP_URL, {"startDate": start_10})))),
        ("SRF", lambda: parse_rp(request_json(query_url(SRF_URL, {"startDate": start_10, "operationTypes": "Repo"})))),
    ]
    for key, fn in fetches:
        try:
            maps[key] = fn()
        except Exception as exc:
            maps[key] = {}
            errors[key] = str(exc)
    for key, spec in FRED_SPECS.items():
        try:
            url = query_url(FRED_URL, {"id": spec["id"], "cosd": start_30})
            maps[key] = parse_fred_csv(request_text(url), spec["scale"])
        except Exception as exc:
            maps[key] = {}
            errors[key] = str(exc)
    return maps, errors


def fetch_backfill_maps(days: int) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    maps: dict[str, dict[str, float]] = {}
    errors: dict[str, str] = {}
    start = ymd(utc_now().date() - timedelta(days=days))
    fetches = [
        ("SOFR", lambda: parse_sofr(request_json(query_url(SOFR_SEARCH_URL, {"startDate": start})))),
        ("ONRRP", lambda: parse_rp(request_json(query_url(ONRRP_URL, {"startDate": start})))),
        ("SRF", lambda: parse_rp(request_json(query_url(SRF_URL, {"startDate": start, "operationTypes": "Repo"})))),
    ]
    for key, fn in fetches:
        try:
            maps[key] = fn()
        except Exception as exc:
            maps[key] = {}
            errors[key] = str(exc)
    for key, spec in FRED_SPECS.items():
        try:
            url = query_url(FRED_URL, {"id": spec["id"], "cosd": start})
            maps[key] = parse_fred_csv(request_text(url), spec["scale"])
        except Exception as exc:
            maps[key] = {}
            errors[key] = str(exc)
    return maps, errors


def series_from_latest(maps: dict[str, dict[str, float]], errors: dict[str, str]) -> dict:
    out = {}
    for key in SERIES_ORDER:
        if key in FRED_SPECS:
            spec = FRED_SPECS[key]
            source = f"fred:{spec['id']}"
            unit = spec["unit"]
        else:
            spec = NYFED_SPECS[key]
            source = spec["source"]
            unit = spec["unit"]
        d, value = latest_map_value(maps.get(key, {}))
        if value is None:
            out[key] = error_entry(unit, source, errors.get(key, "no value"))
        else:
            out[key] = entry(round(value, 4), d, unit, source)
    return out


def series_for_date(
    target: str,
    maps: dict[str, dict[str, float]],
    errors: dict[str, str],
) -> dict:
    out = {}
    for key in SERIES_ORDER:
        if key in FRED_SPECS:
            spec = FRED_SPECS[key]
            source = f"fred:{spec['id']}"
            unit = spec["unit"]
        else:
            spec = NYFED_SPECS[key]
            source = spec["source"]
            unit = spec["unit"]
        values = maps.get(key, {})
        if target in values:
            out[key] = entry(round(values[target], 4), target, unit, source)
        elif key in errors:
            out[key] = error_entry(unit, source, errors[key])
        else:
            out[key] = entry(None, None, unit, source)
    return out


def latest_on_or_before(values: dict[str, float], target: str) -> tuple[str | None, float | None]:
    candidates = [d for d in values if d <= target]
    if not candidates:
        return None, None
    d = sorted(candidates)[-1]
    return d, values[d]


def derive(series: dict) -> dict:
    sofr = series.get("SOFR", {})
    iorb = series.get("IORB", {})
    spread = {"value": None, "unit": "bp"}
    if sofr.get("value") is not None and iorb.get("value") is not None and sofr.get("as_of") == iorb.get("as_of"):
        spread["value"] = round((float(sofr["value"]) - float(iorb["value"])) * 100, 1)
        spread["as_of"] = sofr.get("as_of")
    else:
        spread["as_of"] = None
        spread["components_as_of"] = {"SOFR": sofr.get("as_of"), "IORB": iorb.get("as_of")}

    walcl = series.get("WALCL", {})
    tga = series.get("TGA", {})
    onrrp = series.get("ONRRP", {})
    net = {
        "value": None,
        "unit": "$bn",
        "components_as_of": {
            "WALCL": walcl.get("as_of"),
            "TGA": tga.get("as_of"),
            "ONRRP": onrrp.get("as_of"),
        },
    }
    if walcl.get("value") is not None and tga.get("value") is not None and onrrp.get("value") is not None:
        net["value"] = round(float(walcl["value"]) / 1000 - float(tga["value"]) - float(onrrp["value"]), 1)
    return {"sofr_iorb_spread_bp": spread, "net_liquidity_bn": net}


def derive_for_date(target: str, maps: dict[str, dict[str, float]]) -> dict:
    series = series_for_date(target, maps, {})
    for key in ("WALCL", "TGA", "ONRRP"):
        d, v = latest_on_or_before(maps.get(key, {}), target)
        if v is not None:
            series[key]["value"] = round(v, 4)
            series[key]["as_of"] = d
    return derive(series)


def current_row(maps: dict[str, dict[str, float]], errors: dict[str, str]) -> dict:
    series = series_from_latest(maps, errors)
    return {
        "date": compact_date(),
        "fetched_at": utc_now().isoformat(),
        "series": series,
        "derived": derive(series),
    }


def backfill_rows(maps: dict[str, dict[str, float]], errors: dict[str, str]) -> list[dict]:
    dates = sorted({d for values in maps.values() for d in values})
    fetched_at = utc_now().isoformat()
    rows = []
    for d in dates:
        rows.append(
            {
                "date": d.replace("-", ""),
                "fetched_at": fetched_at,
                "series": series_for_date(d, maps, errors),
                "derived": derive_for_date(d, maps),
            }
        )
    return rows


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def same_payload(a: dict | None, b: dict) -> bool:
    if a is None:
        return False
    aa = dict(a)
    bb = dict(b)
    aa.pop("fetched_at", None)
    bb.pop("fetched_at", None)
    return aa == bb


def upsert_rows(path: Path, new_rows: list[dict]) -> tuple[int, int]:
    old_rows = load_jsonl(path)
    by_date = {row.get("date"): row for row in old_rows if row.get("date")}
    changed = 0
    for row in new_rows:
        key = row.get("date")
        if same_payload(by_date.get(key), row):
            continue
        else:
            changed += 1
            by_date[key] = row
    rows = [by_date[k] for k in sorted(by_date)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows), changed


def any_success(maps: dict[str, dict[str, float]]) -> bool:
    return any(values for values in maps.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, help="backfill N calendar days")
    ap.add_argument("--output", default=str(DEFAULT_OUT), help=argparse.SUPPRESS)
    args = ap.parse_args()

    out = Path(args.output)
    if args.backfill:
        maps, errors = fetch_backfill_maps(args.backfill)
        rows = backfill_rows(maps, errors)
    else:
        maps, errors = fetch_current_maps()
        rows = [current_row(maps, errors)]
    total, changed = upsert_rows(out, rows)
    summary = {
        "output": str(out),
        "rows_written": len(rows),
        "total_rows": total,
        "changed_rows": changed,
        "errors": errors,
        "success_values": sum(len(v) for v in maps.values()),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if any_success(maps) else 1


if __name__ == "__main__":
    sys.exit(main())
