#!/usr/bin/env python3
"""Machine checks for market-auditor report protocol invariants."""

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
SCHEMA = REPO / "data" / "thresholds.schema.json"
LEDGER = REPO / "data" / "diagnosis_log.jsonl"

ALLOWED_METRICS = {"move_vol_pct", "consec_same_dir", "level", "nd_change"}
ALLOWED_OPS = {">=", "<=", "flip_sign", "cross"}


def latest_report() -> Path | None:
    reports = list(REPORTS.glob("*.md"))
    return max(reports, key=lambda p: p.stat().st_mtime) if reports else None


def schema_type(path: Path) -> str | None:
    name = path.name
    if "约束诊断" in name:
        return "A"
    if "不诊断" in name:
        return "D"
    return None


def report_date(path: Path) -> str | None:
    m = re.match(r"(\d{8})--", path.name)
    return m.group(1) if m else None


def sidecar_path(report: Path) -> Path:
    return report.with_name(f"{report.stem}.thresholds.json")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sidecar(path: Path) -> tuple[bool, str, dict | None]:
    if not path.exists():
        return False, "missing sidecar", None
    try:
        spec = load_json(path)
        schema = load_json(SCHEMA)
    except Exception as exc:
        return False, f"invalid json ({type(exc).__name__}: {exc})", None
    for key in schema.get("required", []):
        if key not in spec:
            return False, f"missing required field {key}", spec
    falsifiers = spec.get("falsifiers")
    if not isinstance(falsifiers, list):
        return False, "falsifiers is not an array", spec
    for i, rule in enumerate(falsifiers, 1):
        if not isinstance(rule, dict):
            return False, f"falsifier {i} is not an object", spec
        for key in ("asset", "metric", "op", "means"):
            if key not in rule:
                return False, f"falsifier {i} missing {key}", spec
        if rule.get("metric") not in ALLOWED_METRICS:
            return False, f"falsifier {i} invalid metric {rule.get('metric')}", spec
        if rule.get("op") not in ALLOWED_OPS:
            return False, f"falsifier {i} invalid op {rule.get('op')}", spec
    return True, "sidecar schema ok", spec


def ledger_rows(date: str) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("date") == date:
            rows.append(row)
    return rows


def check_ledger_a(date: str, sidecar: dict | None) -> tuple[bool, str]:
    rows = ledger_rows(date)
    if not rows:
        return False, f"no diagnosis_log entry for {date}"
    if sidecar is None:
        return False, "sidecar unavailable for regime_row comparison"
    expected = sidecar.get("regime_row")
    for row in rows:
        if row.get("schema") == "A" and row.get("regime_row") == expected:
            return True, f"ledger regime_row matches {expected}"
    return False, f"no A ledger row with regime_row={expected}"


def check_ledger_d(date: str) -> tuple[bool, str]:
    rows = ledger_rows(date)
    if any(row.get("schema") == "D" for row in rows):
        return True, f"ledger has Schema D entry for {date}"
    return False, f"no Schema D ledger entry for {date}"


def passfail(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def add_result(results: list[tuple[str, bool, str]], name: str, ok: bool, detail: str):
    results.append((name, ok, detail))


def lint(report: Path) -> int:
    text = report.read_text(encoding="utf-8")
    stype = schema_type(report)
    date = report_date(report)
    results: list[tuple[str, bool, str]] = []

    add_result(results, "schema_type", stype in {"A", "D"}, stype or "unknown filename schema")
    add_result(results, "report_date", date is not None, date or "missing YYYYMMDD prefix")

    if stype == "A":
        ok_sidecar, detail, spec = validate_sidecar(sidecar_path(report))
        add_result(results, "schema_a_sidecar", ok_sidecar, detail)
        if date:
            ok_ledger, ledger_detail = check_ledger_a(date, spec)
            add_result(results, "schema_a_ledger", ok_ledger, ledger_detail)
        mechanical = re.search(r"(match%|match_pct|分层确定性(?![_A-Za-z])).*?(\d+(?:\.\d+)?)", text, re.S)
        add_result(results, "schema_a_mechanical_score", mechanical is not None, "numeric mechanical score reference found" if mechanical else "missing match%/match_pct/分层确定性 numeric reference")
        falsifier = re.search(r"^##\s*证伪条件\b|^#{1,6}\s*.*证伪", text, re.M)
        add_result(results, "schema_a_falsifier_section", falsifier is not None, "证伪 section found" if falsifier else "missing 证伪 section")

    if stype == "D":
        if date:
            ok_ledger, ledger_detail = check_ledger_d(date)
            add_result(results, "schema_d_ledger", ok_ledger, ledger_detail)
        forbidden = re.search(r"^#{1,6}\s*(机制|观察清单)\b", text, re.M)
        add_result(results, "schema_d_no_forbidden_sections", forbidden is None, "no 机制/观察清单 heading" if forbidden is None else f"forbidden heading: {forbidden.group(0)}")

    failed = False
    print(f"REPORT-LINT {report}")
    print("| item | status | detail |")
    print("|---|---|---|")
    for name, ok, detail in results:
        print(f"| {name} | {passfail(ok)} | {detail} |")
        if not ok:
            failed = True
            print(f"LINT-FAIL {name}: {detail}")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None, help="report markdown path; defaults to latest reports/*.md by mtime")
    args = ap.parse_args()
    report = Path(args.report) if args.report else latest_report()
    if not report:
        print("LINT-FAIL report: no report found")
        return 1
    return lint(report)


if __name__ == "__main__":
    sys.exit(main())
