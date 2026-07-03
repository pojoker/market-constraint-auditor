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
