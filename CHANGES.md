# CHANGES — 2026-07-03 market-constraint-auditor

## Summary

- Replaced the false `US_2Y_yield = ^IRX` mapping with `2YY=F` in both fetch script copies, with FRED `DGS2` fallback when the yfinance 2Y bar is stale or missing.
- Added yfinance retry, per-asset `source/as_of/stale/session_kind`, `--simulate-missing`, FRED fallback for Treasury yield assets, and BTC calendar alignment.
- Added capture completeness metadata: `MIN_ASSETS_OK = 18`, `degraded`, `missing`, and fetch-copy drift warning.
- Updated stats/loading so degraded days are excluded from trend/vol baselines, legacy rows without `_capture` remain usable, and stats expose `stale`, `gap_adjacent`, and session quality.
- Added deterministic matrix/threshold/retro tooling and data files:
  - `data/regime_matrix.json`
  - `data/thresholds.schema.json`
  - `data/diagnosis_log.jsonl`
  - `reports/20260703--约束诊断-P.thresholds.json`
  - `scripts/score_regimes.py`
  - `scripts/check_thresholds.py`
  - `scripts/retro.py`
- Wired `check_thresholds.py` into `~/bin/market-auditor-capture.sh` as best-effort post-capture work. Wrapper exit code remains the capture exit code.

## 2Y Source Choice

- Primary source is `yfinance:2YY=F`, per plan.
- Live test showed `2YY=F` returned a stale 2026-07-01 bar while the rest of the capture had 2026-07-02 bars. The fetcher therefore fell back to FRED `DGS2` and marked:
  - `source: FRED:DGS2`
  - `as_of: 2026-07-01`
  - `stale: true`
  - `fallback_reason: yfinance stale as_of=2026-07-01, reference_as_of=2026-07-02`
- FRED `DGS2` is intentionally allowed to lag; it is used as historical/validation fallback, not as a same-session live source.

## Historical Backfill

Command:

```bash
/Users/jowang/miniconda3/bin/python3 scripts/backfill_history.py --repair-2y
```

Output summary:

```json
{
  "backup": "/Volumes/移动硬盘/market-constraint-auditor/data/timeseries.backup-20260703-085517.jsonl",
  "timeseries_changed_days": 148,
  "snapshot_changed_files": 154,
  "samples": [
    {"date": "20251208", "old": 3.618, "new": 3.57},
    {"date": "20251209", "old": 3.632, "new": 3.61},
    {"date": "20251210", "old": 3.593, "new": 3.54},
    {"date": "20251211", "old": 3.568, "new": 3.52}
  ]
}
```

## Verification

### Fetch

Command:

```bash
/Users/jowang/miniconda3/bin/python3 ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py --summary
```

Observed:

```text
US_2Y_yield  4.1700  +3.00bp  ↑  FRED:DGS2
ok 21 total 21
```

### Simulated Missing Capture

Command:

```bash
FETCH_SIMULATE_MISSING=DXY,USDCNY,Gold,Silver /Users/jowang/miniconda3/bin/python3 scripts/capture_snapshot.py
```

Observed:

```text
WARN 20260703: 17/21 assets, degraded=True, missing=['DXY', 'Gold', 'Silver', 'USDCNY']
```

A normal capture was run after this test and restored the 20260703 snapshot to:

```text
OK 20260703: 21/21 assets, degraded=False, missing=[]
```

### Stats + Summary

Command:

```bash
/Users/jowang/miniconda3/bin/python3 scripts/compute_stats.py --snapshot 20260702
/Users/jowang/miniconda3/bin/python3 scripts/load_for_analysis.py --date 20260702 --summary
```

Observed key lines:

```text
US_2Y_yield last=4.17 today_change=+3.00bps 3d_change=+7.00bps move_vol_pct=46 stale=true
mark_quality: us_close
```

### Regime Score

Command:

```bash
/Users/jowang/miniconda3/bin/python3 scripts/score_regimes.py --date 20260702
```

Observed:

```text
best_regime=sell_america_debasement
match_pct=100.0
aligned=['usd_fx', 'rates_long', 'precious', 'vol']
liquidity_override=false
schema_d_suggested=false
whipsaw_cap=null
```

### Thresholds

Command:

```bash
/Users/jowang/miniconda3/bin/python3 scripts/check_thresholds.py --sidecar reports/20260703--约束诊断-P.thresholds.json --date 20260703
```

Observed:

```text
rc=0
DXY=NEAR, USDCNY=NEAR, US_2Y_yield=NEAR, TLT=SAFE, Gold=NEAR/SAFE, SP500=SAFE, MOVE/HYG=SAFE
```

Temporary trigger test:

```text
ALERT DXY move_vol_pct: temporary trigger test
rc=1
```

### Retro

Command:

```bash
/Users/jowang/miniconda3/bin/python3 scripts/retro.py
```

Observed:

```json
{
  "schema_d_share": 0.5,
  "results": [
    {"date": "20260612", "status": "no-sidecar", "regime": "P"},
    {"date": "20260620", "status": "no-sidecar", "regime": null},
    {"date": "20260625", "status": "no-sidecar", "regime": null},
    {"date": "20260703", "status": "unresolved", "regime": "P", "future_days": []}
  ]
}
```

### Wrapper

Command:

```bash
bash ~/bin/market-auditor-capture.sh
```

Observed:

```text
wrapper_rc=0
END threshold-check exit=0
```

### Copy Drift

Command:

```bash
diff -u skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
```

Observed:

```text
diff_rc=0
```

### Syntax

Command:

```bash
/Users/jowang/miniconda3/bin/python3 -m py_compile scripts/*.py skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
```

Observed: passed.

## Notes

- I did not modify `SKILL.md`, `references/market-constraint-protocol.md`, or `V1.0.3-DRAFT-NOTES.md`.
- I did not commit.
- Pre-existing workspace changes were left untouched, including `.DS_Store`, deleted root-level 20260406 files, and `convert_md.py`.

## Round 2 Fixes

### F1 + F8 + F9: Threshold Date, Directional NEAR, and 20260703 Cleanup

- `check_thresholds.py` now defaults to latest frozen snapshot instead of `report_date`.
- NEAR checks for numeric/cross rules now require matching direction.
- Removed the test-contaminated `data/snapshots/20260703.json` and only the `date=20260703` row from `data/timeseries.jsonl`.

Verification:

```text
rows_after 152 latest 20260702 has_20260703 False
loaded_date 20260702
```

No-arg threshold check:

```text
date=20260702
DXY SAFE value=83 dir=down
USDCNY SAFE value=-4
US_2Y_yield SAFE value=46 dir=up
TLT SAFE value=0 dir=down
Gold SAFE value=68 dir=up
SP500 SAFE value=0 dir=flat
MOVE/HYG SAFE value=29 dir=down
rc=0
```

### F2 + F3: sell_america Guards and Vol Low-Level Channel

- `score_regimes.py` now applies `guards`.
- `em` signal-level down is a conflict for `sell_america_debasement`.
- `rates_front` signal in any direction is a conflict for `sell_america_debasement`.
- Vol class no longer has a global low-level shortcut. VIX/MOVE use move-based signal direction like other classes.
- `vol_low_level` is now a separate boolean. Only rows with `accept_low_level_vol: true` can use it; for `sell_america_debasement`, low-level vol aligns but does not count toward the 4 signal-class callable threshold.

Real 20260702 score:

```text
best sell_america_debasement schemaD True cap None vol_low True
sell 60.0 ['usd_fx', 'rates_long', 'precious', 'vol'] ['em'] False 3 ['vol']
vol_state {'state': 'noise', 'dir': None, 'members': []}
```

This is an expected conclusion change versus the first pass: the deterministic scorer is stricter than the human 07-03 ★★☆ call because the EM signal-down guard forces Schema D suggestion.

Synthetic vol test:

```text
{'state': 'signal', 'dir': '↑', 'members': [{'asset': 'VIX', 'dir': '↑', 'move_vol_pct': 90}]}
```

### F4: Treasury Yield Unit Normalization

`compute_stats.py` now normalizes all yield assets to bp at read time. If a legacy row lacks `change_bps`, it derives bp from `last - prev`.

Verification:

```text
10Y 11.3 99
30Y 12.1 100
```

Old first-pass values were 10Y `today_change=2.58`, `move_vol_pct=55`; 30Y `today_change=2.49`, `move_vol_pct=58`. The new values correctly reflect +11.3bp and +12.1bp.

### F5 + F6: regime_row Whipsaw and Retro Confirmation

- `data/diagnosis_log.jsonl` now includes `regime_row`.
- `score_regimes.py` whipsaw checks row key changes, so opposite P-family rows can cap each other.
- `retro.py` now confirms only when the future best row matches the report's own `regime_row` and match% > 60.
- Threshold schema and the 20260703 sidecar now include `regime_row`.

Temporary whipsaw injection test:

```text
cap ★★☆ reason previous high-confidence regime_row policy_easing_trade on 20260701
restored_cap None reason None
```

Retro rerun:

```json
{
  "schema_d_share": 0.5,
  "results": [
    {"date": "20260612", "status": "no-sidecar", "regime": "P"},
    {"date": "20260620", "status": "no-sidecar", "regime": null},
    {"date": "20260625", "status": "no-sidecar", "regime": null},
    {
      "date": "20260703",
      "status": "unresolved",
      "regime": "P",
      "regime_row": "sell_america_debasement",
      "future_days": []
    }
  ]
}
```

### F7: prior_close Does Not Pollute mark_quality

- FRED yield fallback now marks `session_kind: prior_close` instead of `intraday_stale`.
- `mark_quality()` still returns `intraday_stale` when any true intraday-stale asset is present.
- `load_for_analysis.py` now adds top-level `stale_assets`.

Inline test:

```text
prior_close_only us_close
intraday_present intraday_stale
```

### Round 2 Final Checks

```text
/Users/jowang/miniconda3/bin/python3 -m py_compile scripts/*.py skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
passed

diff -u skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
diff_rc=0
```

Protocol files check:

```text
git diff -- skills/market-constraint-auditor/SKILL.md skills/market-constraint-auditor/references/market-constraint-protocol.md skills/market-constraint-auditor/V1.0.3-DRAFT-NOTES.md --stat
no output
```

No capture was run in Round 2. No commit was made.

---

# Round 2 Fixes — 2026-07-03（按 CODEX-FIXES-20260703.md；验收输出由 reviewer 实测补录）

| # | 修复 | 验收实测 |
|---|------|---------|
| F1 | check_thresholds 默认改用最新快照（report_date 仅元数据） | 无参运行 → `date: 20260702`，rc=0 ✅ |
| F2 | scorer 实现 guards（signal_down_conflict / anchor_or_not_leading） | 20260702: sell_america match%=60.0、em∈conflicted、callable=false、schema_d_suggested=true ✅（预期的结论变化，机械门比人工严格属设计意图） |
| F3 | vol 类改 move-based；低位兜底改为 sell_america 行级 accept_low_level_vol，不计 signal 类数 | 20260702: vol state=noise、vol_low_level=true、low_level_aligned=['vol']、signal_class_count=3 ✅；合成 VIX 16.5 +30%(vol90) → vol=signal ↑ 且对 sell_america 记 conflicted ✅ |
| F4 | asset_change 对收益率读时归一 (last−prev)×100 | 20260702: 10Y today_change=11.3bp vol_pct 55→**99**；30Y 12.1bp vol_pct **100** ✅（07-03 报告的长端腿实际强于当时口径） |
| F5 | diagnosis_log 增 regime_row；whipsaw 比行键 | 注入 20260701 policy_easing ★★★ → cap=★★☆ reason 正确；删除后恢复 null ✅ |
| F6 | retro confirmed 检查 best 行==报告行 | 20260703 按 sell_america_debasement 判定 unresolved ✅ |
| F7 | FRED fallback session_kind=prior_close；mark_quality 不被污染；新增 stale_assets | 内联测试: prior_close→us_close、intraday_stale→intraday_stale、legacy→us_close、stale_assets 正确 ✅ |
| F8 | NEAR 判定加方向检查 | 20260702: DXY vol83 dir=down → SAFE（不再误报 NEAR），全表 SAFE ✅ |
| F9 | 清理 00:56 UTC 盘中杂交快照 | snapshots/20260703.json 已删、timeseries 回到 152 行、latest=20260702 ✅ |

守卫补充合成验证：2Y signal 级上行/下行均使 rates_front∈conflicted（match% 60→33.3）✅；股指 signal 级上涨不记 conflict ✅。
双副本 diff 为空 ✅；py_compile 全过 ✅；协议三文件未动、未 commit ✅。

---

# Round 3 (Backlog-1) — 2026-07-05

按 `CODEX-BACKLOG-1.md` 执行。当前沙箱只允许写入 market-auditor repo；`~/bin` 与 `/Volumes/移动硬盘/sector-scan-skill` 均不可写，因此 wrapper 接线与 sector-scan 落盘未完成，见下方复验清单。

## 工单结果

| 工单 | 结果 | 说明 |
|---|---|---|
| #1 假日/半日盘守卫 | 部分完成 | `capture_snapshot.py` 写入 `_capture.partial_session`；`load_for_analysis.py` 透出 `mark_quality=partial_session`；`check_thresholds.py` 顶层输出 `mark_quality` 且 partial alert 加后缀；新增 `diagnose_gate.py` 可输出 `SKIP partial session (...)`。`~/bin/market-auditor-diagnose.sh` 因沙箱不可写未接线。 |
| #3 备份接线 | 部分完成 | 新增 `scripts/backup_step.sh`，实现 `data/` mirror with `--delete`、`reports/` mirror without `--delete`、有 remote 时 best-effort push，失败 rc 保持 0。`~/bin/market-auditor-capture.sh` 因沙箱不可写未接线。 |
| #5 report_lint.py | 完成（wrapper 未接线） | 新增 `scripts/report_lint.py`，Schema A/D 检查、PASS/FAIL 表、`LINT-FAIL`、exit 1 均实现。`~/bin/market-auditor-diagnose.sh` lint 后置接线因沙箱不可写未完成。 |
| #6 sector-scan 数据验证移植 | 未完成 | 目标目录 `/Volumes/移动硬盘/sector-scan-skill/skills/sector-scan/scripts/` 不在当前可写根内，写权限探针返回 `operation not permitted`。未修改 sector-scan 源，也未修改安装目录。 |

## 端到端复验清单

1. 工单 #1 partial gate：

```text
SKIP partial session (20260703)
SKIP already diagnosed (ledger 20260703 >= mark 20260702)
```

只读检测真实快照：

```text
20260702 (False, 'as_of missing for SP500 or all assets')
20260703 (True, None)
```

2. 工单 #3 备份子步骤独测（临时 BACKUP_DIR + fake git，未触发真实 capture）：

```text
backup_rc=0
data_diff_rc=0
reports_diff_rc=0
mkdir: /root: Operation not permitted
forbidden_backup_rc=0
```

3. 工单 #5 lint：

```text
REPORT-LINT reports/20260703--约束诊断-P.md
| schema_a_sidecar | PASS | sidecar schema ok |
| schema_a_ledger | PASS | ledger regime_row matches sell_america_debasement |
| schema_a_mechanical_score | PASS | numeric mechanical score reference found |
| schema_a_falsifier_section | PASS | 证伪 section found |

missing_sidecar_rc=1
LINT-FAIL schema_a_sidecar: missing sidecar

no_score_rc=1
LINT-FAIL schema_a_mechanical_score: missing match%/match_pct/分层确定性 numeric reference

REPORT-LINT reports/20260625--不诊断-商品独跌跨资产冲突.md
| schema_d_ledger | PASS | ledger has Schema D entry for 20260625 |
| schema_d_no_forbidden_sections | PASS | no 机制/观察清单 heading |
```

4. 工单 #6 复验：

```text
zsh:2: operation not permitted: skills/sector-scan/scripts/.codex_write_probe
not_writable
```

因此 9 格对账、异常行 WARN 测试、单标的回归未执行；未跑全量扫描。

5. 编译与边界自检：

```text
/Users/jowang/miniconda3/bin/python3 -m py_compile scripts/capture_snapshot.py scripts/load_for_analysis.py scripts/check_thresholds.py scripts/report_lint.py scripts/diagnose_gate.py
bash -n scripts/backup_step.sh
compile_ok
```

真实数据文件哈希（执行前后相同）：

```text
860a6946b47f1d79c30dc5cc2db6cfe86b0b902783b978d2128f1dafef3f4d9d  data/timeseries.jsonl
95abcdc5859a7f3593cb878faf3b991fd7ca8a8f19ee45f60ce2a52ead9a1cbf  data/diagnosis_log.jsonl
9193d24ef49759fab2914c3b0acd0885302dc0812691c6022950e953fb251e30  data/snapshots/20260702.json
c21a7bed3228b0b083e74317f1a7aedb9e50898cd78d9db2a5d719f2fbe465ef  data/snapshots/20260703.json
```

写权限边界：

```text
zsh:2: operation not permitted: /Users/jowang/bin/.codex_write_probe
not_writable
zsh:2: operation not permitted: skills/sector-scan/scripts/.codex_write_probe
not_writable
```

Git status 摘要：market-auditor 存在本次脚本改动，也存在开工前已有的 `.DS_Store`、删除文件、`data/diagnosis_log.jsonl`、`skills/market-constraint-auditor/SKILL.md` 等脏状态；sector-scan status 与开工前一致，未产生新改动。未 commit。

## Round 4 (2Y rebase)

Scope implemented in workspace copy:
- `skills/market-constraint-auditor/scripts/fetch_prices.py`: `US_2Y_yield` now tries `2YY=F` hourly (`period=2d`, `interval=1h`) first, computes `prev` from prior `2YY=F` daily close, then falls back to `2YY=F` daily, then emergency FRED `DGS2`.
- `scripts/backfill_history.py`: added `--rebase-2y-2yy`; it backs up `data/timeseries.jsonl` before attempting to fetch `2YY=F` daily history, and rewrites/removes only `US_2Y_yield` fields when data is available.
- `scripts/compute_stats.py`: added source-family switching guard; source switches set `today_change=null`, `source_switch=true`, and break consecutive-direction / volatility use of the cross-source jump.

### Acceptance 1 — fetch_prices real run

Command:

```text
/Users/jowang/miniconda3/bin/python3 skills/market-constraint-auditor/scripts/fetch_prices.py
```

Actual result: blocked by DNS/network, so the required `source=yfinance:2YY=F(1h)` live proof could not be produced in this environment. No DGS2 value was used to fake the 2YY hourly result.

```text
US_2Y_yield {"error": "HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=DGS2 (Caused by NameResolutionError(... Failed to resolve 'fred.stlouisfed.org' ...)); FRED fallback failed: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=DGS2 (Caused by NameResolutionError(... Failed to resolve 'fred.stlouisfed.org' ...))", "source": "yfinance:2YY=F"}
SP500 {"as_of": null, "last": null, "session_kind": null, "source": "yfinance:^GSPC", "stale": null}
stderr included:
Failed to get ticker '2YY=F' reason: Failed to perform, curl: (6) Could not resolve host: guce.yahoo.com.
Failed to get ticker '^GSPC' reason: Failed to perform, curl: (6) Could not resolve host: guce.yahoo.com.
```

### Acceptance 2 — rebase and DGS2 residual check

Command:

```text
/Users/jowang/miniconda3/bin/python3 scripts/backfill_history.py --rebase-2y-2yy
```

Actual result: the command created a backup first, then stopped before rewriting because `2YY=F` daily history could not be fetched. Therefore timeseries was intentionally not rewritten, and DGS2 residuals remain.

```text
exit=1
Failed to get ticker '2YY=F' reason: Failed to perform, curl: (6) Could not resolve host: guce.yahoo.com.
curl_cffi.requests.exceptions.DNSError: Failed to perform, curl: (6) Could not resolve host: guce.yahoo.com.
```

Backup and unchanged-data evidence:

```text
/Volumes/移动硬盘/market-constraint-auditor/data/timeseries.backup-20260707-130258.jsonl
backup_exists=yes
cmp_latest_intentional_backup=0

total_rows 156
US_2Y_entries 152
US_2Y_missing_dates 4 ['20260119', '20260216', '20260403', '20260525']
source_counts {"FRED:DGS2": 151, "yfinance:2YY=F": 1}
DGS2_residual_entries 151

grep -n '"source": "FRED:DGS2"' data/timeseries.jsonl | wc -l
151
```

### Acceptance 3 — compute_stats source-switch guard

Real current data, `20260706`, now detects the existing `20260705 2YY -> 20260706 DGS2` switch and suppresses the mixed-source daily move:

```text
/Users/jowang/miniconda3/bin/python3 scripts/compute_stats.py --snapshot 20260706

{"as_of": "2026-07-02", "consec_same_dir": 0, "gap_adjacent": true, "last": 4.14, "move_vol_pct": null, "noise_flag": null, "source": "FRED:DGS2", "source_switch": true, "stale": true, "today_change": null}
```

Synthetic `DGS2 -> 2YY` switch test:

```text
20260703 {"consec_same_dir": 0, "gap_adjacent": true, "last": 3.89, "move_vol_pct": null, "noise_flag": null, "source": "yfinance:2YY=F(backfill)", "source_switch": true, "today_change": null}
20260706 {"consec_same_dir": 1, "gap_adjacent": false, "last": 3.91, "move_vol_pct": null, "noise_flag": null, "source": "yfinance:2YY=F(backfill)", "source_switch": false, "today_change": 2.0}
```

### Acceptance 4 — duplicate fetch copy, compile, boundaries

Compile:

```text
/Users/jowang/miniconda3/bin/python3 -m py_compile scripts/backfill_history.py scripts/compute_stats.py skills/market-constraint-auditor/scripts/fetch_prices.py
```

Dual-copy sync is blocked by the workspace boundary: the runtime copy is outside the writable project root.

```text
cp skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
cp: /Users/jowang/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py: Operation not permitted

diff -u skills/market-constraint-auditor/scripts/fetch_prices.py ~/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
--- skills/market-constraint-auditor/scripts/fetch_prices.py
+++ /Users/jowang/.claude/skills/market-constraint-auditor/scripts/fetch_prices.py
@@
+# runtime copy lacks the new 2YY=F(1h) helper block and dispatch
```

Boundary checks:

```text
HEAD 9ac655d
git diff --name-only -- 'skills/**/SKILL.md' '*protocol*' '*DRAFT-NOTES*'
# no output

sha256sum data/diagnosis_log.jsonl
bff4b0f31c3f774e41c562b9013538abd8bc8043d2429c9ec54d58ded93ceae8  data/diagnosis_log.jsonl
```

Current status still includes pre-existing dirty files plus this round's workspace edits; no commit was made.

## Round 4 附录 — A′ 转向（2026-07-07，reviewer 执行）

Round 4 交付的 2YY 重写在验收中被否决并回滚：**yfinance 2YY=F 日线为稀薄成交僵尸数据**
（142 天仅 27 天变动，会使噪音门分布退化）。codex 代码本身零缺陷；探测遗漏（只验当日性
未验历史分布）责任在验收方。经用户裁决改行 **A′ 方案**：

- `US_2Y_yield` 固定 FRED DGS2（恒 t+1、stale/prior_close 标记），fetch 中 2YY 全部摘除
- 新增资产 **SHY**（1-3Y 美债 ETF）承担前端当日方向，`rates_front: [US_2Y_yield, SHY]`
  ——与 rates_long 的 TLT 同构；backfill_history 新增 `--add-asset`（SHY 142 天入库）
  与 `--drop-entry`（清除 20260705 的 2YY 稀薄成交幻影，2Y 序列回归 151 天纯 DGS2）
- 保留 Round 4 的 compute_stats 跨源防护（实战验证有效）；`--rebase-2y-2yy` 标注废弃
- 数据回滚路径：timeseries ← codex pre-rebase 备份；snapshots ← ~/Backups 晨镜像；
  20260705/06 快照由 timeseries 行重建（镜像因 backup 步骤 launchd 执行外置盘脚本被
  provenance 拒绝而滞后一天——该步骤已内联进 ~/bin wrapper 修复）
- 实测：fetch 22 资产（US_2Y=FRED、SHY 当日 as_of）；score_regimes rates_front 类
  正常；双副本一致；SKILL.md 注记 v1.0.6

---

# Round 5 (source audit) — 2026-07-07

- 新增 `scripts/audit_sources.py`（codex 实现 + reviewer 修复联网路径 yfinance MultiIndex bug）与首次全量审计报告 `data/source_audit_20260707.{md,json}`（离线部分 codex 跑、B/C 联网部分 reviewer 补跑）。
- 新增 `data/SOURCES.md` 语义台账（reviewer 编写）：22 资产 + sector-scan 四源的"身份证"+ 接入军规五条 + 首次普查结论与解读纪律。
- 边界：timeseries/diagnosis_log sha256 跑前后一致（dbb3efc9/bff4b0f3），无 commit（由协调侧统一提交），协议未动。
- 核心发现：E 项周末重复变动污染（全资产性 🔴）、能源移仓跳空（月频 🔴）、MOVE 滞后不稳定（🔴 {0:3,6:1}）、10Y/30Y 半数 t+1（🟡）；B 项对期货的 Volume 读数不可靠（解读纪律已写入台账）。
