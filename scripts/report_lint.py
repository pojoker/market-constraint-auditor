#!/usr/bin/env python3
"""Machine checks for market-auditor report protocol invariants.

v2 (2026-07-11, readability ticket): 在原有机器结构检查之上，对报告日
>= 20260711 的新报告增加读者正文规则检查（结构/长度/黑话/比喻/运行日志
隔离/表达状态语言/利率归因矛盾）。旧报告仍按旧路径检查，不受新规则影响。
`--style-only` 只跑新的结构/语言检查（用于 tmp 合成样例，不读 sidecar/ledger）。
"""

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

STYLE_V2_CUTOFF = "20260711"  # 报告日（文件名前缀）>= 此值才启用 style v2

READER_SECTIONS = [
    "今日结论",
    "与上一个交易日相比",
    "核心证据",
    "当前不能确定的事",
    "下一个确认点",
    "审计附录",
]

# 6.1 程序字段与直译词（读者正文禁用；英文按词边界匹配）
INTERNAL_TERMS_EN = [
    "signal-grade", "signal", "consec", "stale", "callable",
    "aligned", "conflicted", "whipsaw", "regime_row", "regime",
    "denominator", "gap_adjacent", "vol",
]
INTERNAL_TERMS_ZH = [
    "可召唤", "判别腿", "风险腿", "美元腿", "长端腿", "机器腿",
    "冲突腿", "确认腿", "深噪", "噪音门", "厚盘", "独木",
]
METAPHOR_TERMS = [
    "换了主角", "接过定价权", "余波", "残响", "复活", "熄火",
    "瘫着", "挨打", "出场作证", "收案",
]
OPS_TERMS = [
    "补发", "无头进程", "无头 claude", "墙钟", "看门狗", "挂死",
    "例行自愈", "跑批", "launchd", "wrapper",
]
# 表达状态语言：原因未确认时禁用的确立性语言
ESTABLISHED_TERMS = ["已坐实", "坐实", "接过定价权", "主导约束已确立", "真.{0,3}定价"]
# 利率归因矛盾：声明缺分解后禁用的归因语言
ATTR_MISSING_MARKERS = [
    "来源未分解", "分解数据缺位", "无法分解", "利率分解.{0,6}缺",
    "TIPS.{0,10}缺", "rates_attribution.{0,10}(缺|不可用|null)",
]
ATTR_FORBIDDEN = [
    "实际利率(上行|回落|上升|下降|挤压|驱动)",
    "油价.{0,12}(推动|移走|驱动).{0,12}利率",
    "通胀燃料", "挤压(松开|解除)",
]


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


# ---------- style v2 helpers ----------

def reader_region(text: str) -> str:
    """文档开头到首个「## 审计附录」之前。无附录标题则整篇视为正文。"""
    m = re.search(r"^##\s*审计附录\s*$", text, re.M)
    return text[: m.start()] if m else text


def cjk_count(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def find_terms(region: str, zh_terms: list[str], en_terms: list[str] | None = None) -> list[str]:
    hits = []
    for t in zh_terms:
        if re.search(t, region):
            hits.append(t)
    for t in en_terms or []:
        # 英文词边界匹配；排除代码围栏内没必要——新报告正文本就不应引用黑话
        if re.search(rf"(?<![A-Za-z_]){re.escape(t)}(?![A-Za-z_])", region):
            hits.append(t)
    return hits


def style_v2_a(text: str, results: list) -> None:
    region = reader_region(text)

    # reader_sections：六个固定一级标题齐全且顺序正确
    positions = []
    missing = []
    for sec in READER_SECTIONS:
        m = re.search(rf"^##\s*{sec}\s*$", text, re.M)
        if m:
            positions.append((sec, m.start()))
        else:
            missing.append(sec)
    ordered = positions == sorted(positions, key=lambda x: x[1]) and not missing
    add_result(results, "reader_sections", ordered,
               "6 sections present & ordered" if ordered
               else f"missing={missing or '-'}; order={[s for s, _ in positions]}")

    # reader_length：附录前中文字符 ≤ 1500
    n = cjk_count(region)
    add_result(results, "reader_length", n <= 1500, f"reader CJK chars = {n} (limit 1500)")

    # reader_internal_terms
    hits = find_terms(region, INTERNAL_TERMS_ZH, INTERNAL_TERMS_EN)
    add_result(results, "reader_internal_terms", not hits,
               "clean" if not hits else f"hit: {hits}")

    # reader_metaphors
    hits = find_terms(region, METAPHOR_TERMS)
    add_result(results, "reader_metaphors", not hits,
               "clean" if not hits else f"hit: {hits}")

    # reader_ops_isolation
    hits = find_terms(region, [], OPS_TERMS) + find_terms(region, [t for t in OPS_TERMS if re.search(r"[一-鿿]", t)])
    hits = sorted(set(hits))
    add_result(results, "reader_ops_isolation", not hits,
               "clean" if not hits else f"ops words in reader body: {hits}")

    # pricing_only_language：正文声明原因未确认/暂不可分时的语言约束
    unconfirmed = re.search(r"未确认|暂不可分", region)
    if unconfirmed:
        has_pattern = re.search(r"最佳匹配的价格模式", region)
        bad = [t for t in ESTABLISHED_TERMS if re.search(t, region)]
        ok = bool(has_pattern) and not bad
        detail = "pricing-only language ok" if ok else \
            f"pattern={'ok' if has_pattern else 'missing 最佳匹配的价格模式'}; established-hits={bad or '-'}"
    else:
        # 叙事已获支持态：不做额外语言限制（因果门由协议约束）
        ok, detail = True, "no unconfirmed marker (narrative-supported path)"
    add_result(results, "pricing_only_language", ok, detail)

    # rates_attribution_guard：全篇（含附录）声明分解缺位后禁止归因语言
    missing_attr = any(re.search(p, text) for p in ATTR_MISSING_MARKERS)
    if missing_attr:
        bad = []
        for p in ATTR_FORBIDDEN:
            m = re.search(p, text)
            if m:
                bad.append(m.group(0))
        add_result(results, "rates_attribution_guard", not bad,
                   "no attribution claims while decomposition missing" if not bad
                   else f"attribution missing but text claims: {bad}")
    else:
        add_result(results, "rates_attribution_guard", True, "decomposition not declared missing")


def style_v2_d(text: str, results: list) -> None:
    # Schema D：技术说明段之前为读者区域
    m = re.search(r"^#{2,3}\s*技术说明", text, re.M)
    region = text[: m.start()] if m else text
    hits = find_terms(region, INTERNAL_TERMS_ZH, INTERNAL_TERMS_EN)
    add_result(results, "schema_d_plain_language", not hits,
               "clean" if not hits else f"hit: {hits}")


# ---------- main lint ----------

def lint(report: Path, style_only: bool = False) -> int:
    text = report.read_text(encoding="utf-8")
    stype = schema_type(report)
    date = report_date(report)
    results: list[tuple[str, bool, str]] = []

    add_result(results, "schema_type", stype in {"A", "D"}, stype or "unknown filename schema")
    add_result(results, "report_date", date is not None, date or "missing YYYYMMDD prefix")

    if not style_only:
        if stype == "A":
            ok_sidecar, detail, spec = validate_sidecar(sidecar_path(report))
            add_result(results, "schema_a_sidecar", ok_sidecar, detail)
            if date:
                ok_ledger, ledger_detail = check_ledger_a(date, spec)
                add_result(results, "schema_a_ledger", ok_ledger, ledger_detail)
            mechanical = re.search(r"(match%|match_pct|匹配率|分层确定性(?![_A-Za-z])).*?(\d+(?:\.\d+)?)", text, re.S)
            add_result(results, "schema_a_mechanical_score", mechanical is not None,
                       "numeric mechanical score reference found" if mechanical
                       else "missing match%/match_pct/匹配率 numeric reference")
            falsifier = re.search(r"^#{1,6}\s*.*证伪", text, re.M)
            add_result(results, "schema_a_falsifier_section", falsifier is not None,
                       "证伪 section found" if falsifier else "missing 证伪 section")

        if stype == "D":
            if date:
                ok_ledger, ledger_detail = check_ledger_d(date)
                add_result(results, "schema_d_ledger", ok_ledger, ledger_detail)
            forbidden = re.search(r"^#{1,6}\s*(机制|观察清单)\b", text, re.M)
            add_result(results, "schema_d_no_forbidden_sections", forbidden is None,
                       "no 机制/观察清单 heading" if forbidden is None
                       else f"forbidden heading: {forbidden.group(0)}")

    # style v2：报告日 >= cutoff 才启用（旧报告不回溯）
    if date and date >= STYLE_V2_CUTOFF:
        if stype == "A":
            style_v2_a(text, results)
        elif stype == "D":
            style_v2_d(text, results)

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
    ap.add_argument("--style-only", action="store_true",
                    help="only run structure/language checks (skip sidecar/ledger); for tmp synthetic samples")
    args = ap.parse_args()
    report = Path(args.report) if args.report else latest_report()
    if not report:
        print("LINT-FAIL report: no report found")
        return 1
    return lint(report, style_only=args.style_only)


if __name__ == "__main__":
    sys.exit(main())
