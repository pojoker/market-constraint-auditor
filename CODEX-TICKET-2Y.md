# 工单 2（换源）— US_2Y 全序列切换到 2YY=F（Backlog Round 4）

> 背景：`2YY=F` 日线 bar 在捕获时点（21:45 UTC）尚未落（期货日 22:00 UTC 切换后才出）→ 2Y 天天 fallback 到 FRED（滞后 1-4 天）→ 前端判别腿失明（07-07 弃权报告的直接成因之一）。探测确认：**小时线在捕获时点可得当日值**。用户已裁决：全序列切换 2YY=F（期货隐含收益率口径），FRED 降应急回退。
> **核心红线：两种口径（2YY≈3.89 vs DGS2≈4.14，差~25bp）绝不能在无防护的情况下混进同一条 change 序列。**

## 边界（同前几轮）

- 只改脚本与数据文件；不 commit；不碰协议三文件；`data/diagnosis_log.jsonl` 不许动；测试禁跑真实 capture。
- **本工单唯一被允许的数据改写**：timeseries + snapshots 中 `US_2Y_yield` 字段的回填（改前必须备份 timeseries，沿用 `.backup-<ts>` 命名）。
- 双副本 `fetch_prices.py` 改完逐字一致。
- 测试用 `/Users/jowang/miniconda3/bin/python3`。

## 改动

### 1. fetch_prices.py（两份）
- `US_2Y_yield` 主源改为 **2YY=F 小时线最后 bar**：`yf.Ticker("2YY=F").history(period="2d", interval="1h")` 取最后一根的 Close；`as_of` = 该 bar 的美东日期；`source="yfinance:2YY=F(1h)"`；`prev` 用 2YY **日线**的前一交易日 Close（同口径），change_bps 据此算。
- 回退链：小时线失败 → 2YY 日线最后 bar（as_of 滞后则标 stale/prior_close）→ FRED DGS2（标 stale + prior_close，应急）。
- 删除/绕过原来针对 2Y 的"yfinance as_of 落后 → FRED"强制回退比较（新主源本身就是为了当日性）。
- 10Y/30Y 逻辑不动。

### 2. backfill_history.py 新 flag `--rebase-2y-2yy`
- 用 2YY=F 日线历史把 timeseries + snapshots 里 `US_2Y_yield` **整段重写**（覆盖现有 DGS2 回填值）：last=当日 2YY Close、change_bps=相邻 2YY 日差、`source="yfinance:2YY=F(backfill)"`、as_of=bar 日期。
- 2YY 缺 bar 的日子（假日等）：该日 `US_2Y_yield` 条目**整个移除**（下游 compute_stats 的缺口桥接会处理），不许留 DGS2 旧值造成混源。
- 备份先行；CHANGES 记录改写天数、移除天数、新旧值抽样（≥4 天）。

### 3. compute_stats.py 跨源防护
- 对所有资产：若当日 entry 的 source 系列族（取 source 字符串中冒号前+票据名归一，如 `2YY` 族 vs `DGS2` 族）与**前一有效日**不同 → `today_change` 置 None、stat 加 `source_switch: true`（等同 gap 处理：不进 vol 分布、consec 桥接语义按现有缺口规则）。legacy 无 source 字段的天视为同族（不触发）。

### 4. 不需要动的
score_regimes / check_thresholds / retro / wrapper——全部只消费 stats，无感。

## 验收（贴 CHANGES.md「Round 4 (2Y rebase)」）

1. `fetch_prices.py` 实跑：`US_2Y` source=`2YY=F(1h)`、as_of 与 SP500 的 reference as_of 同日、change_bps 为同口径日差。
2. 回填后：`timeseries` 中 US_2Y 全部为 2YY 族（grep source 无 DGS2 残留，除非该日被移除）；抽 4 天新旧对比（预期 4.0x→3.8x 量级）。
3. `compute_stats.py --snapshot 20260706`：US_2Y 的 consec/vol 在纯 2YY 序列上计算，无跨口径幽灵跳变；构造合成"DGS2→2YY 切换日" → `today_change=None` + `source_switch=true`。
4. 双副本 diff 为空；py_compile 全过；diagnosis_log 无 diff；未 commit。
