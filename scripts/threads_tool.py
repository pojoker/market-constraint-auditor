#!/usr/bin/env python3
"""跨日悬案账本（open threads）工具。

悬案 = 前几日诊断留给今天的未决问题（工作记忆）。无头会话没有对话记忆，
这个账本就是记忆。协议侧接线见 SKILL.md v1.0.8 步骤 2/6。

支持：--list / --expire-check / --add / --resolve。
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data" / "open_threads.jsonl"
REQUIRED = ["id", "opened", "question", "resolve_condition", "expires", "status"]
STATUSES = {"open", "resolved", "expired"}


def today_key() -> str:
    return date.today().strftime("%Y%m%d")


def valid_yyyymmdd(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
        return False
    try:
        date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")
    except ValueError:
        return False
    return True


def schema_error(message: str) -> None:
    print(f"ERROR {message}", file=sys.stderr)
    sys.exit(2)


def validate_row(row: dict, line_no: int | None = None) -> None:
    where = f" line {line_no}:" if line_no is not None else ":"
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        schema_error(f"{where} missing {missing}")
    for key in ("id", "question", "resolve_condition"):
        if not isinstance(row.get(key), str) or not row.get(key).strip():
            schema_error(f"{where} {key} must be non-empty string")
    for key in ("opened", "expires"):
        if not valid_yyyymmdd(row.get(key)):
            schema_error(f"{where} {key} must be YYYYMMDD")
    if row.get("status") not in STATUSES:
        schema_error(f"{where} status must be one of {sorted(STATUSES)}")
    if row.get("status") in {"resolved", "expired"} and row.get("resolved_on") is not None:
        if not valid_yyyymmdd(row.get("resolved_on")):
            schema_error(f"{where} resolved_on must be YYYYMMDD")


def load() -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            schema_error(f"line {i}: bad json ({e})")
        validate_row(row, i)
        rows.append(row)
    return rows


def save(rows: list[dict]) -> None:
    for row in rows:
        validate_row(row)
    LEDGER.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def cmd_list() -> int:
    rows = load()
    today = today_key()
    active = [r for r in rows if r["status"] == "open"]
    if not active:
        print("（无活跃悬案）")
        print("--- json ---")
        print("[]")
        return 0
    for r in active:
        overdue = " ⚠️已过期" if r["expires"] < today else ""
        print(f"[{r['id']}]{overdue}")
        print(f"  问题: {r['question']}")
        print(f"  了结条件: {r['resolve_condition']}")
        print(f"  有效期至: {r['expires']}")
    print("--- json ---")
    print(json.dumps(active, ensure_ascii=False))
    return 0


def cmd_expire_check() -> int:
    rows = load()
    today = today_key()
    n = 0
    for r in rows:
        if r["status"] == "open" and r["expires"] < today:
            r["status"] = "expired"
            r["resolved_on"] = today
            n += 1
    if n:
        save(rows)
    print(f"expired: {n}")
    return 0


def slugify(question: str, existing: set[str]) -> str:
    words = re.findall(r"[A-Za-z0-9]+", question.lower())
    slug = "-".join(words[:6]).strip("-") if words else ""
    if not slug:
        slug = f"thread-{abs(hash(question)) % 100000:05d}"
    slug = slug[:48].strip("-") or "thread"
    base = f"{today_key()}-{slug}"
    candidate = base
    i = 2
    while candidate in existing:
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def cmd_add(question: str, resolve_condition: str, expires: str) -> int:
    if not question or not resolve_condition or not expires:
        schema_error(": --add requires --question, --resolve-condition, --expires")
    if not valid_yyyymmdd(expires):
        schema_error(": expires must be YYYYMMDD")
    rows = load()
    row = {
        "id": slugify(question, {r["id"] for r in rows}),
        "opened": today_key(),
        "question": question,
        "resolve_condition": resolve_condition,
        "expires": expires,
        "status": "open",
    }
    validate_row(row)
    rows.append(row)
    save(rows)
    print(f"added: {row['id']}")
    print(json.dumps(row, ensure_ascii=False))
    return 0


def cmd_resolve(thread_id: str, resolution: str) -> int:
    if not thread_id or not resolution:
        schema_error(": --resolve requires id and --resolution")
    rows = load()
    for row in rows:
        if row["id"] == thread_id:
            row["status"] = "resolved"
            row["resolved_on"] = today_key()
            row["resolution"] = resolution
            save(rows)
            print(f"resolved: {thread_id}")
            return 0
    print(f"not found: {thread_id}", file=sys.stderr)
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage open cross-day diagnostic threads.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true")
    group.add_argument("--expire-check", action="store_true")
    group.add_argument("--add", action="store_true")
    group.add_argument("--resolve")
    parser.add_argument("--question")
    parser.add_argument("--resolve-condition")
    parser.add_argument("--expires")
    parser.add_argument("--resolution")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    if args.list or not any((args.expire_check, args.add, args.resolve)):
        return cmd_list()
    if args.expire_check:
        return cmd_expire_check()
    if args.add:
        return cmd_add(args.question, args.resolve_condition, args.expires)
    if args.resolve:
        return cmd_resolve(args.resolve, args.resolution)
    return cmd_list()


if __name__ == "__main__":
    sys.exit(main())
