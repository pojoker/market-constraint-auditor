#!/usr/bin/env python3
"""跨日悬案账本（open threads）最小工具。

悬案 = 前几日诊断留给今天的未决问题（工作记忆）。无头会话没有对话记忆，
这个账本就是记忆。协议侧接线见 SKILL.md v1.0.8 步骤 2/6。

最小版（2026-07-08，保障协议当天可用）：--list / --expire-check。
待强化（Round 7 工单）：--add / --resolve / 全量 schema 校验。
"""

import json
import sys
from datetime import date
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data" / "open_threads.jsonl"
REQUIRED = ["id", "opened", "question", "resolve_condition", "expires", "status"]


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
            print(f"ERROR line {i}: bad json ({e})", file=sys.stderr)
            sys.exit(2)
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            print(f"ERROR line {i}: missing {missing}", file=sys.stderr)
            sys.exit(2)
        rows.append(row)
    return rows


def save(rows: list[dict]) -> None:
    LEDGER.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def cmd_list() -> int:
    rows = load()
    today = date.today().strftime("%Y%m%d")
    active = [r for r in rows if r["status"] == "open"]
    if not active:
        print("（无活跃悬案）")
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
    today = date.today().strftime("%Y%m%d")
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


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--list"
    if cmd == "--list":
        return cmd_list()
    if cmd == "--expire-check":
        return cmd_expire_check()
    print(f"unknown command: {cmd}（最小版仅支持 --list / --expire-check）", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
