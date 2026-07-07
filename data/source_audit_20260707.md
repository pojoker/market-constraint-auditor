# Source Audit 20260707

- generated_at: `2026-07-06T21:45:05.057837+00:00`
- offline: `False`
- timeseries rows: `156`

## Summary

| Asset | A 分布 | B 成交 | C 移仓 | D 滞后 | E 重复 |
|---|---:|---:|---:|---:|---:|
| DXY | 🟢 | 🔴 | N/A | 🟢 | 🟡 |
| US_2Y_yield | 🟢 | 🔴 | N/A | 🟡 | 🔴 |
| US_10Y_yield | 🟢 | N/A | N/A | 🟡 | 🟡 |
| US_30Y_yield | 🟢 | N/A | N/A | 🟡 | 🟡 |
| Gold | 🟢 | 🟡 | 🔴 | 🟢 | 🔴 |
| Silver | 🟢 | 🔴 | 🔴 | 🟢 | 🔴 |
| Brent | 🟢 | 🟢 | 🟡 | 🟢 | 🔴 |
| WTI | 🟢 | 🟢 | 🔴 | 🟢 | 🔴 |
| NatGas | 🟢 | 🟢 | 🔴 | 🟢 | 🔴 |
| SP500 | 🟢 | N/A | N/A | 🟢 | 🔴 |
| Nasdaq | 🟢 | 🟢 | N/A | 🟢 | 🔴 |
| Russell2000 | 🟢 | 🟢 | N/A | 🟢 | 🔴 |
| VIX | 🟢 | N/A | N/A | 🟢 | 🔴 |
| MOVE | 🟢 | N/A | N/A | 🔴 | 🟡 |
| EM_ETF | 🟢 | 🟢 | N/A | 🟢 | 🔴 |
| HYG | 🟢 | 🟢 | N/A | 🟢 | 🔴 |
| TLT | 🟢 | 🟢 | N/A | 🟢 | 🔴 |
| Copper | 🟢 | 🟡 | 🟡 | 🟢 | 🔴 |
| USDCNY | 🟢 | N/A | N/A | 🟢 | 🟡 |
| USDJPY | 🟢 | N/A | N/A | 🟢 | 🟢 |
| BTC | 🟢 | 🟢 | N/A | 🟢 | 🟡 |
| SHY | 🟢 | 🟢 | N/A | 🟢 | 🟢 |

## Findings

### DXY B 🔴
- 证据：ticker=DX-Y.NYB, median_volume=0.0, zero_volume=100.0%
- 建议动作：换源；没有成交的价格不得进入机械信号。

### DXY E 🟡
- 证据：eligible=9, repeated=2, ratio=22.2%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

### US_2Y_yield B 🔴
- 证据：ticker=DGS2, median_volume=None, zero_volume=N/A
- 建议动作：无成交量样本，换源或禁用该价格。

### US_2Y_yield D 🟡
- 证据：sample=3, lag_distribution_sp500_sessions={1: 3}, constant_lag=True, by_design=True
- 建议动作：by design 恒滞后：保留 stale/prior_close 标注，由 SHY 承担当日前端方向。

### US_2Y_yield E 🔴
- 证据：eligible=8, repeated=8, ratio=100.0%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### US_10Y_yield D 🟡
- 证据：sample=4, lag_distribution_sp500_sessions={0: 2, 1: 2}, constant_lag=False, by_design=False
- 建议动作：下游展示 stale/as_of，避免当日同步解读。

### US_10Y_yield E 🟡
- 证据：eligible=5, repeated=2, ratio=40.0%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

### US_30Y_yield D 🟡
- 证据：sample=4, lag_distribution_sp500_sessions={0: 2, 1: 2}, constant_lag=False, by_design=False
- 建议动作：下游展示 stale/as_of，避免当日同步解读。

### US_30Y_yield E 🟡
- 证据：eligible=5, repeated=2, ratio=40.0%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

### Gold B 🟡
- 证据：ticker=GC=F, median_volume=538.0, zero_volume=0.0%
- 建议动作：成交偏弱，纳入观察；若影响阈值需换源。

### Gold C 🔴
- 证据：ticker=GC=F, polluted_days_estimate=30, candidates=30
- 建议动作：移仓污染显著，候选日 change 置 None 或改用现货/ETF。

### Gold E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### Silver B 🔴
- 证据：ticker=SI=F, median_volume=82.0, zero_volume=3.2%
- 建议动作：换源；没有成交的价格不得进入机械信号。

### Silver C 🔴
- 证据：ticker=SI=F, polluted_days_estimate=69, candidates=69
- 建议动作：移仓污染显著，候选日 change 置 None 或改用现货/ETF。

### Silver E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### Brent C 🟡
- 证据：ticker=BZ=F, polluted_days_estimate=4, candidates=4
- 建议动作：候选移仓日 change 置 None 后复算 vol 分位。

### Brent E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### WTI C 🔴
- 证据：ticker=CL=F, polluted_days_estimate=6, candidates=6
- 建议动作：移仓污染显著，候选日 change 置 None 或改用现货/ETF。

### WTI E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### NatGas C 🔴
- 证据：ticker=NG=F, polluted_days_estimate=6, candidates=6
- 建议动作：移仓污染显著，候选日 change 置 None 或改用现货/ETF。

### NatGas E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### SP500 E 🔴
- 证据：eligible=9, repeated=6, ratio=66.7%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### Nasdaq E 🔴
- 证据：eligible=9, repeated=8, ratio=88.9%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### Russell2000 E 🔴
- 证据：eligible=9, repeated=8, ratio=88.9%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### VIX E 🔴
- 证据：eligible=9, repeated=5, ratio=55.6%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### MOVE D 🔴
- 证据：sample=4, lag_distribution_sp500_sessions={0: 3, 6: 1}, constant_lag=False, by_design=False
- 建议动作：禁作同日信号，改用同步替代源或明确 prior_close。

### MOVE E 🟡
- 证据：eligible=3, repeated=2, ratio=66.7%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

### EM_ETF E 🔴
- 证据：eligible=9, repeated=8, ratio=88.9%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### HYG E 🔴
- 证据：eligible=9, repeated=8, ratio=88.9%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### TLT E 🔴
- 证据：eligible=9, repeated=8, ratio=88.9%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### Copper B 🟡
- 证据：ticker=HG=F, median_volume=992.0, zero_volume=0.0%
- 建议动作：成交偏弱，纳入观察；若影响阈值需换源。

### Copper C 🟡
- 证据：ticker=HG=F, polluted_days_estimate=2, candidates=2
- 建议动作：候选移仓日 change 置 None 后复算 vol 分位。

### Copper E 🔴
- 证据：eligible=9, repeated=3, ratio=33.3%, non_sp500_rows=9
- 建议动作：修复前禁止把重复行纳入 vol 分位。

### USDCNY E 🟡
- 证据：eligible=9, repeated=2, ratio=22.2%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

### BTC E 🟡
- 证据：eligible=9, repeated=1, ratio=11.1%, non_sp500_rows=9
- 建议动作：周末/假日重复 change 从 vol 分布剔除后复算。

## Special Checks

### MOVE
```json
{
  "as_of_lag_distribution_sp500_sessions": {
    "0": 3,
    "6": 1
  },
  "longest_unchanged_run": 2,
  "zero_change_ratio": 0.0
}
```

### USDCNY
```json
{
  "zero_change_ratio": 0.175,
  "weekend_rows": [
    {
      "date": "20260607",
      "last": 6.765,
      "change": -0.13,
      "as_of": null
    },
    {
      "date": "20260614",
      "last": 6.7621,
      "change": -0.2,
      "as_of": null
    },
    {
      "date": "20260620",
      "last": 6.7647,
      "change": -0.06,
      "as_of": null
    },
    {
      "date": "20260621",
      "last": 6.7647,
      "change": -0.06,
      "as_of": null
    },
    {
      "date": "20260627",
      "last": 6.7897,
      "change": -0.0,
      "as_of": null
    },
    {
      "date": "20260628",
      "last": 6.7897,
      "change": -0.0,
      "as_of": null
    },
    {
      "date": "20260704",
      "last": 6.7702,
      "change": -0.27,
      "as_of": "2026-07-04"
    },
    {
      "date": "20260705",
      "last": 6.7702,
      "change": -0.27,
      "as_of": "2026-07-05"
    }
  ],
  "capture_semantics": "21:45 UTC 捕获晚于在岸 CNY 收盘，as_of 表示亚洲/在岸早收盘标记。"
}
```

### BTC
```json
{
  "calendar_alignment": "BTC 以 SP500 日历审计；非 SP500 交易日若有重复 change 会在 E 项暴露。",
  "non_sp500_eligible_rows": 9,
  "repeated_change_rows": 1
}
```
