#!/usr/bin/env python3
"""
Mechanical data-source audit for market-constraint-auditor.

This script is read-only for existing data files. It writes only:
  - data/source_audit_<YYYYMMDD>.md
  - data/source_audit_<YYYYMMDD>.json

Exit code is always 0: this is an informational health check, not a gate.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
TIMESERIES = DATA / "timeseries.jsonl"

YIELD_ASSETS = {"US_2Y_yield", "US_10Y_yield", "US_30Y_yield"}
VOLUME_NA_TICKERS = {"^GSPC", "^VIX", "^MOVE", "^TNX", "^TYX"}
FUTURES_ASSETS = {"Gold", "Silver", "Brent", "WTI", "NatGas", "Copper"}
FUTURES_TICKERS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Brent": "BZ=F",
    "WTI": "CL=F",
    "NatGas": "NG=F",
    "Copper": "HG=F",
}
TICKERS = {
    "DXY": "DX-Y.NYB",
    "US_2Y_yield": "DGS2",
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
    "SHY": "SHY",
}

GREEN = "green"
YELLOW = "yellow"
RED = "red"
NA = "n/a"
SKIPPED = "skipped(offline)"
STATUS_ICON = {
    GREEN: "🟢",
    YELLOW: "🟡",
    RED: "🔴",
    NA: "N/A",
    SKIPPED: "skipped(offline)",
}


@dataclass
class AssetAudit:
    asset: str
    A: dict[str, Any]
    B: dict[str, Any]
    C: dict[str, Any]
    D: dict[str, Any]
    E: dict[str, Any]
    F: dict[str, Any] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit local market data sources.")
    parser.add_argument("--offline", action="store_true", help="Skip yfinance checks B/C.")
    parser.add_argument("--json-only", action="store_true", help="Write JSON only; skip Markdown.")
    parser.add_argument("--date", default=None, help="Report date key, default today YYYYMMDD.")
    return parser.parse_args()


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not TIMESERIES.exists():
        return rows
    for line in TIMESERIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda r: r.get("date", ""))
    return rows


def all_assets(rows: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        assets = row.get("assets", {})
        if isinstance(assets, dict):
            names.update(k for k, v in assets.items() if isinstance(v, dict) and "last" in v)
    preferred = [a for a in TICKERS if a in names]
    return preferred + sorted(names - set(preferred))


def parse_ymd(value: str | None) -> date | None:
    if not value:
        return None
    try:
        if len(value) == 8 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d").date()
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def asset_change(asset: str, entry: dict[str, Any]) -> float | None:
    if asset in YIELD_ASSETS:
        if "change_bps" in entry:
            return num(entry.get("change_bps"))
        last = num(entry.get("last"))
        prev = num(entry.get("prev"))
        return round((last - prev) * 100, 6) if last is not None and prev is not None else None
    if "change_pct" in entry:
        return num(entry.get("change_pct"))
    if "change_bps" in entry:
        return num(entry.get("change_bps"))
    if "change" in entry:
        return num(entry.get("change"))
    last = num(entry.get("last"))
    prev = num(entry.get("prev"))
    if last is not None and prev not in (None, 0):
        return round((last - prev) / prev * 100, 6)
    return None


def status_from_ratio(value: float, yellow: float, red: float) -> str:
    if value > red:
        return RED
    if value > yellow:
        return YELLOW
    return GREEN


def audit_A(rows: list[dict[str, Any]], asset: str) -> dict[str, Any]:
    points: list[tuple[str, float, float | None]] = []
    for row in rows:
        entry = row.get("assets", {}).get(asset)
        if not isinstance(entry, dict):
            continue
        last = num(entry.get("last"))
        if last is None:
            continue
        points.append((row.get("date", ""), last, asset_change(asset, entry)))
    window = points[-120:]
    changes = [c for _, _, c in window if c is not None]
    zero_count = sum(1 for c in changes if c == 0)
    zero_ratio = zero_count / len(changes) if changes else 0.0
    unique_last = len({last for _, last, _ in window})
    median_abs_change = statistics.median(abs(c) for c in changes) if changes else None
    longest = 0
    current = 0
    prev_last: float | None = None
    for _, last, _ in window:
        if prev_last is not None and last == prev_last:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        prev_last = last
    status = status_from_ratio(zero_ratio, 0.20, 0.40)
    return {
        "status": status,
        "sample_days": len(window),
        "change_days": len(changes),
        "zero_change_days": zero_count,
        "zero_change_ratio": round(zero_ratio, 4),
        "unique_last_values": unique_last,
        "median_abs_change": median_abs_change,
        "longest_unchanged_run": longest,
        "recommendation": recommendation("A", status),
    }


def import_yfinance():
    import yfinance as yf  # type: ignore

    return yf


def audit_B(rows: list[dict[str, Any]], asset: str, offline: bool) -> dict[str, Any]:
    ticker = ticker_for(asset, rows)
    if offline:
        return {"status": SKIPPED, "reason": "offline mode: yfinance Volume check skipped"}
    if not ticker:
        return {"status": NA, "reason": "no ticker mapping"}
    if ticker in VOLUME_NA_TICKERS or ticker.endswith("=X"):
        return {"status": NA, "ticker": ticker, "reason": "index/FX has no reliable Volume"}
    try:
        yf = import_yfinance()
        hist = yf.download(ticker, period="3mo", progress=False, auto_adjust=False)
        volume = hist["Volume"]
        # yfinance 新版对单 ticker 也返回 MultiIndex 列 → 压平成 Series（同 flatten_download_close）
        if hasattr(volume, "columns"):
            volume = volume[ticker] if ticker in volume.columns else volume.iloc[:, 0]
        volume = volume.dropna()
    except Exception as exc:  # pragma: no cover - network dependent
        return {"status": YELLOW, "ticker": ticker, "error": str(exc), "recommendation": "实网成交量拉取失败，协调侧重跑。"}
    vals = [float(v) for v in volume.tolist()]
    if not vals:
        return {"status": RED, "ticker": ticker, "median_volume": None, "zero_volume_ratio": None, "recommendation": "无成交量样本，换源或禁用该价格。"}
    median_volume = statistics.median(vals)
    zero_ratio = sum(1 for v in vals if v == 0) / len(vals)
    if median_volume < 100:
        status = RED
    elif median_volume < 1000:
        status = YELLOW
    else:
        status = GREEN
    return {
        "status": status,
        "ticker": ticker,
        "sample_days": len(vals),
        "median_volume": median_volume,
        "zero_volume_ratio": round(zero_ratio, 4),
        "recommendation": recommendation("B", status),
    }


def ticker_for(asset: str, rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        entry = row.get("assets", {}).get(asset)
        if isinstance(entry, dict):
            source = entry.get("source")
            if isinstance(source, str) and source.startswith("yfinance:"):
                return source.split(":", 1)[1].split("(", 1)[0]
    return TICKERS.get(asset)


def flatten_download_close(hist: Any, ticker: str) -> list[tuple[str, float]]:
    close = hist["Close"]
    if hasattr(close, "columns"):
        series = close[ticker] if ticker in close.columns else close.iloc[:, 0]
    else:
        series = close
    rows = []
    for idx, value in series.dropna().items():
        rows.append((str(idx)[:10], float(value)))
    return rows


def pct_changes(close_rows: list[tuple[str, float]]) -> dict[str, float]:
    out: dict[str, float] = {}
    prev: float | None = None
    for day, close in close_rows:
        if prev not in (None, 0):
            out[day] = (close - prev) / prev * 100
        prev = close
    return out


def audit_C(asset: str, offline: bool) -> dict[str, Any]:
    if asset not in FUTURES_ASSETS:
        return {"status": NA, "reason": "not a six-asset front-month futures series"}
    if offline:
        return {"status": SKIPPED, "reason": "offline mode: yfinance futures/ETF cross-check skipped"}
    ticker = FUTURES_TICKERS[asset]
    try:
        yf = import_yfinance()
        if asset in {"Gold", "Silver"}:
            etf = "GLD" if asset == "Gold" else "SLV"
            hist = yf.download([ticker, etf], period="6mo", progress=False, auto_adjust=False)
            fut_ret = pct_changes(flatten_download_close(hist, ticker))
            etf_ret = pct_changes(flatten_download_close(hist, etf))
            days = []
            for day in sorted(set(fut_ret) & set(etf_ret)):
                diff = abs(fut_ret[day] - etf_ret[day])
                if diff > 0.8:
                    days.append({"date": day, "future_change_pct": round(fut_ret[day], 4), "etf_change_pct": round(etf_ret[day], 4), "diff_pct": round(diff, 4)})
            status = RED if len(days) >= 5 else (YELLOW if days else GREEN)
            return {
                "status": status,
                "ticker": ticker,
                "cross_check": etf,
                "polluted_days_estimate": len(days),
                "candidate_days": days,
                "recommendation": recommendation("C", status),
            }
        hist = yf.download(ticker, period="6mo", progress=False, auto_adjust=False)
        returns = pct_changes(flatten_download_close(hist, ticker))
    except Exception as exc:  # pragma: no cover - network dependent
        return {"status": YELLOW, "ticker": ticker, "error": str(exc), "recommendation": "实网移仓探测失败，协调侧重跑。"}
    vals = list(returns.values())
    if len(vals) < 10:
        return {"status": YELLOW, "ticker": ticker, "reason": "insufficient return samples", "polluted_days_estimate": None}
    med = statistics.median(vals)
    deviations = [abs(v - med) for v in vals]
    mad = statistics.median(deviations)
    threshold = 4 * mad
    days = [
        {"date": day, "change_pct": round(ret, 4), "threshold_pct": round(threshold, 4)}
        for day, ret in sorted(returns.items())
        if threshold > 0 and abs(ret - med) > threshold
    ]
    status = RED if len(days) >= 5 else (YELLOW if days else GREEN)
    return {
        "status": status,
        "ticker": ticker,
        "mad_pct": round(mad, 6),
        "polluted_days_estimate": len(days),
        "candidate_days": days,
        "note": "需人工核对是否换月日",
        "recommendation": recommendation("C", status),
    }


def sp500_as_of_calendar(rows: list[dict[str, Any]]) -> dict[date, int]:
    days: list[date] = []
    for row in rows:
        sp = row.get("assets", {}).get("SP500")
        sp_as_of = parse_ymd(sp.get("as_of") if isinstance(sp, dict) else None)
        if sp_as_of is not None:
            days.append(sp_as_of)
    unique_days = sorted(set(days))
    return {day: idx for idx, day in enumerate(unique_days)}


def trading_lag(sp_as_of: date, asset_as_of: date, calendar: dict[date, int]) -> int:
    sp_idx = calendar.get(sp_as_of)
    asset_idx = calendar.get(asset_as_of)
    if sp_idx is not None and asset_idx is not None:
        return sp_idx - asset_idx
    return (sp_as_of - asset_as_of).days


def audit_D(rows: list[dict[str, Any]], asset: str, calendar: dict[date, int]) -> dict[str, Any]:
    lags: list[int] = []
    samples: list[dict[str, Any]] = []
    for row in rows:
        row_day = parse_ymd(row.get("date"))
        if row_day is None or row_day < date(2026, 7, 3):
            continue
        assets = row.get("assets", {})
        sp_as_of = parse_ymd(assets.get("SP500", {}).get("as_of") if isinstance(assets.get("SP500"), dict) else None)
        entry = assets.get(asset)
        asset_as_of = parse_ymd(entry.get("as_of") if isinstance(entry, dict) else None)
        if sp_as_of is None or asset_as_of is None:
            continue
        lag = trading_lag(sp_as_of, asset_as_of, calendar)
        lags.append(lag)
        samples.append({"date": row.get("date"), "asset_as_of": asset_as_of.isoformat(), "sp500_as_of": sp_as_of.isoformat(), "lag_days": lag})
    if not lags:
        return {"status": NA, "reason": "no new-format as_of samples since 2026-07-03"}
    counts = dict(sorted(Counter(lags).items()))
    constant_lag = len(counts) == 1
    max_lag = max(lags)
    status = RED if max_lag >= 3 else (YELLOW if max_lag >= 1 else GREEN)
    by_design = asset == "US_2Y_yield" and constant_lag and max_lag >= 1
    if by_design:
        status = YELLOW
    return {
        "status": status,
        "sample_days": len(lags),
        "lag_distribution_sp500_sessions": counts,
        "constant_lag": constant_lag,
        "by_design": by_design,
        "samples": samples,
        "recommendation": "by design 恒滞后：保留 stale/prior_close 标注，由 SHY 承担当日前端方向。" if by_design else recommendation("D", status),
    }


def sp500_trading_row(row: dict[str, Any]) -> bool:
    row_day = parse_ymd(row.get("date"))
    if row_day is None:
        return False
    sp = row.get("assets", {}).get("SP500")
    sp_as_of = parse_ymd(sp.get("as_of") if isinstance(sp, dict) else None)
    if sp_as_of is not None:
        return sp_as_of == row_day
    return row_day.weekday() < 5


def audit_E_all(rows: list[dict[str, Any]], assets: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    latest_trading: dict[str, dict[str, Any]] | None = None
    eligible: defaultdict[str, int] = defaultdict(int)
    repeated: defaultdict[str, int] = defaultdict(int)
    examples: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    non_trading_dates: list[str] = []
    for row in rows:
        if sp500_trading_row(row):
            latest_trading = row.get("assets", {})
            continue
        non_trading_dates.append(row.get("date", ""))
        if latest_trading is None:
            continue
        for asset in assets:
            entry = row.get("assets", {}).get(asset)
            prev_entry = latest_trading.get(asset)
            if not isinstance(entry, dict) or not isinstance(prev_entry, dict):
                continue
            c = asset_change(asset, entry)
            pc = asset_change(asset, prev_entry)
            if c is None or pc is None:
                continue
            eligible[asset] += 1
            if c == pc:
                repeated[asset] += 1
                if len(examples[asset]) < 5:
                    examples[asset].append({"date": row.get("date"), "change": c, "previous_trading_change": pc})
    for asset in assets:
        n = eligible[asset]
        r = repeated[asset]
        ratio = r / n if n else 0.0
        status = RED if ratio > 0.20 and r >= 3 else (YELLOW if ratio > 0 and r > 0 else GREEN)
        out[asset] = {
            "status": status,
            "non_sp500_trading_rows_total": len(non_trading_dates),
            "eligible_rows": n,
            "repeated_change_rows": r,
            "repeated_change_ratio": round(ratio, 4),
            "examples": examples[asset],
            "recommendation": recommendation("E", status),
        }
    return out


def audit_F(rows: list[dict[str, Any]], asset: str, A: dict[str, Any], D: dict[str, Any], E: dict[str, Any]) -> dict[str, Any] | None:
    if asset not in {"USDCNY", "MOVE", "BTC"}:
        return None
    if asset == "USDCNY":
        weekend_rows = []
        for row in rows:
            row_day = parse_ymd(row.get("date"))
            entry = row.get("assets", {}).get("USDCNY")
            if row_day is not None and row_day.weekday() >= 5 and isinstance(entry, dict):
                weekend_rows.append({"date": row.get("date"), "last": entry.get("last"), "change": asset_change(asset, entry), "as_of": entry.get("as_of")})
        return {
            "zero_change_ratio": A["zero_change_ratio"],
            "weekend_rows": weekend_rows,
            "capture_semantics": "21:45 UTC 捕获晚于在岸 CNY 收盘，as_of 表示亚洲/在岸早收盘标记。",
        }
    if asset == "MOVE":
        return {
            "as_of_lag_distribution_sp500_sessions": D.get("lag_distribution_sp500_sessions"),
            "longest_unchanged_run": A.get("longest_unchanged_run"),
            "zero_change_ratio": A.get("zero_change_ratio"),
        }
    weekend_leak = E.get("eligible_rows", 0)
    return {
        "calendar_alignment": "BTC 以 SP500 日历审计；非 SP500 交易日若有重复 change 会在 E 项暴露。",
        "non_sp500_eligible_rows": weekend_leak,
        "repeated_change_rows": E.get("repeated_change_rows", 0),
    }


def recommendation(check: str, status: str) -> str:
    if status == GREEN:
        return "保持现源，季度复核。"
    if status == YELLOW:
        return {
            "A": "仅方向使用或降低权重，补做语义/成交复核。",
            "B": "成交偏弱，纳入观察；若影响阈值需换源。",
            "C": "候选移仓日 change 置 None 后复算 vol 分位。",
            "D": "下游展示 stale/as_of，避免当日同步解读。",
            "E": "周末/假日重复 change 从 vol 分布剔除后复算。",
        }.get(check, "人工复核。")
    if status == RED:
        return {
            "A": "停止用于分位/强度判断，换源或仅保留人工备注。",
            "B": "换源；没有成交的价格不得进入机械信号。",
            "C": "移仓污染显著，候选日 change 置 None 或改用现货/ETF。",
            "D": "禁作同日信号，改用同步替代源或明确 prior_close。",
            "E": "修复前禁止把重复行纳入 vol 分位。",
        }.get(check, "停止机械使用并人工复核。")
    return "未执行或不适用。"


def build_report(rows: list[dict[str, Any]], audits: list[AssetAudit], generated_at: str, offline: bool) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "offline": offline,
        "source_files": {"timeseries": str(TIMESERIES)},
        "rows": len(rows),
        "assets": {
            a.asset: {
                "A": a.A,
                "B": a.B,
                "C": a.C,
                "D": a.D,
                "E": a.E,
                **({"F": a.F} if a.F is not None else {}),
            }
            for a in audits
        },
    }


def fmt_status(item: dict[str, Any]) -> str:
    return STATUS_ICON.get(item.get("status"), str(item.get("status", "")))


def pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Source Audit {path.stem.rsplit('_', 1)[-1]}")
    lines.append("")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- offline: `{report['offline']}`")
    lines.append(f"- timeseries rows: `{report['rows']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Asset | A 分布 | B 成交 | C 移仓 | D 滞后 | E 重复 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for asset, checks in report["assets"].items():
        lines.append(
            f"| {asset} | {fmt_status(checks['A'])} | {fmt_status(checks['B'])} | {fmt_status(checks['C'])} | {fmt_status(checks['D'])} | {fmt_status(checks['E'])} |"
        )
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    any_finding = False
    for asset, checks in report["assets"].items():
        for check_name in ["A", "B", "C", "D", "E"]:
            check = checks[check_name]
            status = check.get("status")
            if status not in {YELLOW, RED, SKIPPED}:
                continue
            any_finding = True
            lines.append(f"### {asset} {check_name} {fmt_status(check)}")
            lines.append(evidence_line(check_name, check))
            lines.append(f"- 建议动作：{check.get('recommendation', check.get('reason', '人工复核。'))}")
            lines.append("")
    if not any_finding:
        lines.append("No yellow/red/skipped findings.")
        lines.append("")
    lines.append("## Special Checks")
    lines.append("")
    for asset, checks in report["assets"].items():
        if "F" not in checks:
            continue
        lines.append(f"### {asset}")
        lines.append("```json")
        lines.append(json.dumps(checks["F"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def evidence_line(check_name: str, check: dict[str, Any]) -> str:
    if check.get("status") == SKIPPED:
        return f"- 证据：{check.get('reason')}"
    if check_name == "A":
        return (
            f"- 证据：sample={check.get('sample_days')}, zero={pct(check.get('zero_change_ratio'))}, "
            f"unique_last={check.get('unique_last_values')}, median_abs_change={check.get('median_abs_change')}, "
            f"longest_unchanged={check.get('longest_unchanged_run')}"
        )
    if check_name == "B":
        return (
            f"- 证据：ticker={check.get('ticker')}, median_volume={check.get('median_volume')}, "
            f"zero_volume={pct(check.get('zero_volume_ratio'))}"
        )
    if check_name == "C":
        return (
            f"- 证据：ticker={check.get('ticker')}, polluted_days_estimate={check.get('polluted_days_estimate')}, "
            f"candidates={len(check.get('candidate_days', []))}"
        )
    if check_name == "D":
        return (
            f"- 证据：sample={check.get('sample_days')}, lag_distribution_sp500_sessions={check.get('lag_distribution_sp500_sessions')}, "
            f"constant_lag={check.get('constant_lag')}, by_design={check.get('by_design')}"
        )
    return (
        f"- 证据：eligible={check.get('eligible_rows')}, repeated={check.get('repeated_change_rows')}, "
        f"ratio={pct(check.get('repeated_change_ratio'))}, non_sp500_rows={check.get('non_sp500_trading_rows_total')}"
    )


def print_key_lines(report: dict[str, Any]) -> None:
    print("CHECK SUMMARY")
    for asset, checks in report["assets"].items():
        print(
            f"{asset}: A={checks['A']['status']} B={checks['B']['status']} C={checks['C']['status']} D={checks['D']['status']} E={checks['E']['status']}"
        )


def main() -> int:
    args = parse_args()
    rows = load_rows()
    assets = all_assets(rows)
    e_all = audit_E_all(rows, assets)
    sp_calendar = sp500_as_of_calendar(rows)
    audits: list[AssetAudit] = []
    c_cache: dict[str, dict[str, Any]] = {}
    for asset in assets:
        A = audit_A(rows, asset)
        B = audit_B(rows, asset, args.offline)
        if asset not in c_cache:
            c_cache[asset] = audit_C(asset, args.offline)
        C = c_cache[asset]
        D = audit_D(rows, asset, sp_calendar)
        E = e_all[asset]
        F = audit_F(rows, asset, A, D, E)
        audits.append(AssetAudit(asset=asset, A=A, B=B, C=C, D=D, E=E, F=F))

    report_date = args.date or datetime.now().strftime("%Y%m%d")
    generated_at = rows[-1].get("fetched_at") if rows else datetime.now().astimezone().isoformat(timespec="seconds")
    report = build_report(rows, audits, generated_at, args.offline)
    json_path = DATA / f"source_audit_{report_date}.json"
    md_path = DATA / f"source_audit_{report_date}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if not args.json_only:
        write_markdown(report, md_path)
    print_key_lines(report)
    print(f"JSON: {json_path}")
    if not args.json_only:
        print(f"MD: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
