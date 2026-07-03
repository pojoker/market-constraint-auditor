# 外包 Plan — market-constraint-auditor 优化（codex 执行）

> 交接说明：本文档是完整任务规格。按任务 A→B→C→D 顺序执行；所有"分析口径"已写死为数据规格，**照规格实现，不自行发明口径**。改完不 commit，写 `CHANGES.md` 等待 review。

## Context（为什么做）

`market-constraint-auditor` 是一个三层解耦管线（捕获→统计→分析），设计良好，但存在三类问题：

1. **数据正确性 bug（最严重，静默腐蚀分析）**：`fetch_prices.py` 把 `US_2Y_yield` 映射到 `^IRX`（13周/3个月短债），不是 2 年。而"前端 2Y 锚定 / 前端沉默 = 锚点迁移"是本 skill 反复出现的承重推理（07-03、06-12、06-25 报告都靠它区分"财政期限溢价"和"联储路径重定价"）——它读的其实是错的工具。
2. **捕获可靠性**：`data/capture.log` 显示 `06-16=2/21`、`06-23=2/21`、`06-24=17/21`（后者直接逼出 06-25 的 Schema D）。单源 yfinance、无重试、无备源、残缺日照写进 timeseries 污染下游 consec/vol 基线。
3. **闭环缺失**：诊断设了 ex-ante 证伪线但没人自动核对；矩阵评分/whipsaw 全靠 LLM 心算；诊断从不回测自己准不准。

目标产出：把上述"机制"部分全部脚本化、确定性化，并**接进每日自动链路**；LLM 只在确定性打分之上做裁决。

## 关键边界（务必遵守）

- **只改脚本与数据文件**（`scripts/*.py`、`~/bin/market-auditor-capture.sh`、新建 `.py`/`.json`）。
- **禁止修改分析协议文字**：`~/.claude/skills/market-constraint-auditor/SKILL.md`、`.../references/market-constraint-protocol.md`、`.../V1.0.3-DRAFT-NOTES.md` 一律不动。协议口径由发包方在 review 阶段改。
- **不要 commit**。改完留在工作区，写一份 `CHANGES.md`（改动摘要 + 每项验收实测输出 + 2Y 源选择/滞后说明 + 回填差异摘要）。

## 运行环境事实（必须按这个测）

- 捕获实际用 **miniconda python**：`/Users/jowang/miniconda3/bin/python3`。所有脚本用它测。
- 已装：`yfinance 1.2.0`、`requests 2.33.1`、`pandas 2.2.3`、`Markdown`。**未装** `fredapi`/`pandas-datareader` → **不得引入新依赖**；FRED 走 `requests` 拉 `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>`（无需 API key）。
- **FRED 时点现实**：每日捕获在 05:45 北京时 = 美东下午，FRED 当日 DGS2 **尚未发布** → FRED 只用于**历史回填与交叉校验**，不做当日主源。
- **源码双份漂移**（重要）：
  - `capture_snapshot.py` / `compute_stats.py` / `load_for_analysis.py` 只在 `/Volumes/移动硬盘/market-constraint-auditor/scripts/` 有运行副本（git 未跟踪）→ 直接改这里。
  - `fetch_prices.py` **运行副本**在 `~/.claude/skills/market-constraint-auditor/scripts/`（capture_snapshot.py 写死引用）；**git 跟踪副本**在 `/Volumes/移动硬盘/market-constraint-auditor/skills/market-constraint-auditor/scripts/`。→ **两份都改、逐字一致**。
- 旧快照（2026-05 及更早一批）**没有 `_capture` 字段** → 所有读 `_capture` 的逻辑必须容忍缺失（按"非退化 legacy"处理），不得崩。
- 测试前确认 `/Volumes/移动硬盘/` 已挂载（wrapper 对未挂载会干净跳过）。

---

## 任务 A：数据层修复 — 最高优先

### A1. 真 2Y + 历史回填（防序列断裂）
**文件**：`fetch_prices.py`（两份）、`scripts/backfill_history.py`。

- 主源改为 **yfinance `2YY=F`**（CBOE 2Y 收益率期货，可给同日值）；实测确认可用性与收盘对齐，记录在 `CHANGES.md`。若实测不可用，与发包方确认后再定替代，不得静默换成滞后源。
- 对新主源取不到的日子，fallback FRED `DGS2`（会滞后一天）：该资产在快照里标 `stale: true` + `as_of`。
- **必须回填**：扩展/使用 `backfill_history.py`，用 FRED `DGS2` 把 `data/timeseries.jsonl` 与 `data/snapshots/*.json` 中 `US_2Y_yield` 的**全部历史值**重写为真 2Y（^IRX 旧值全部替换），重算受影响的 change/change_pct。回填前先备份 timeseries（沿用现有 `.backup-<ts>` 命名习惯）。`CHANGES.md` 附回填摘要（改写天数、抽样新旧值对比）。
- 10Y/30Y 维持 `^TNX`/`^TYX` 不动（避免引入 FRED 滞后），仅在 A2 fallback 链里挂 FRED `DGS10`/`DGS30`。

### A2. 多源 + 重试 + 完整度门 + 退化日排除
**文件**：`fetch_prices.py`、`capture_snapshot.py`、`compute_stats.py`。

- **fetch_prices.py**：
  - `yf.download` 整批调用加重试（最多 3 次、指数退避）；重试后仍缺的资产做逐资产 fallback（收益率→FRED 前值+stale 标记；其余源缺就缺，如实标 error）。
  - 每资产记录 `source` 与 `as_of`。
  - 新增 **`--simulate-missing A,B,C`**（或 `FETCH_SIMULATE_MISSING` 环境变量）：强制指定资产返回 error，用于确定性测试退化路径。
- **capture_snapshot.py**：
  - 常量 `MIN_ASSETS_OK = 18`。重试后 `assets_ok < 18` → 仍写快照，但 `_capture` 加 `degraded: true` + `missing: [...]`，log 打 `WARN`；完整日 `degraded: false`。保持幂等。
  - **副本漂移探测**：每次运行时 hash 比对两份 `fetch_prices.py`，不一致 → log `WARN: fetch_prices copies diverged`（不阻断）。
- **compute_stats.py**：
  - consec/vol 基线**排除 `degraded: true` 的整天**（`_capture` 缺失的 legacy 天视为非退化）。
  - **缺口桥接（不是重置）**：某资产在日 t 缺失（或 t 被排除）时，consec 用 t−1→t+1 作一步方向桥接（单日数据故障 ≠ 趋势反转）；但桥接产生的 2 日变动**不进 vol 分位分布**，且当日 stat 加 `gap_adjacent: true` 供分析层打折。缺口 >1 天才重置。

**验收 A**：
- `fetch_prices.py` 输出的 `US_2Y_yield` 为真 2Y；与 FRED DGS2 抽 2 个历史日交叉核对一致。
- 回填后 `compute_stats.py --snapshot 20260702` 的 `US_2Y_yield` consec/vol 在真 2Y 序列上计算、切换日无假跳变。
- `--simulate-missing` 制造残缺 → 快照 `degraded:true`+`missing`；compute_stats 确认该日不进基线、consec 桥接生效、`gap_adjacent` 出现。
- `load_for_analysis.py --summary` 表格形状不变，能透出 stale/degraded/gap 信息。

---

## 任务 B：确定性工具层 — 新脚本

三个新脚本共享结构化数据文件，先建数据再实现。

### B0. 机器可读矩阵 + 资产分组 + sidecar schema + 诊断账本（规格已定死，照填）

**新建 `data/regime_matrix.json`**，包含四部分：

1. **资产→资产类映射（ex-ante，写死）**：
   ```
   usd_fx:      [DXY, USDJPY, USDCNY]
   rates_front: [US_2Y_yield]
   rates_long:  [US_10Y_yield, US_30Y_yield, TLT]
   precious:    [Gold, Silver]
   energy:      [Brent, WTI, NatGas]
   industrial:  [Copper]
   equities_us: [SP500, Nasdaq, Russell2000]
   em:          [EM_ETF]
   credit:      [HYG]
   vol:         [VIX, MOVE]
   btc:         [BTC]   # confirmer-only，永不计入 ≥4 类阈值（协议 F13）
   ```
   类级方向判定：类内 ≥1 成员过噪音门且同向、且无成员 signal 级反向 → 类=signal 对齐；有 signal 级反向成员 → 类=conflicted；全噪音 → 类=noise。
2. **协议 §2 七行指纹逐字转录**（方向码 `↑/↓/—/↑?/↓?` 按类给出）+ `single_day_max_confidence`（按 `V1.0.3-DRAFT-NOTES.md` §2「修改 A」表：L/F/S 指纹全中可单日 ★★★；P/I/G 单日禁 ★★★；M 无意义）。
3. **新增第 8 行 `sell_america_debasement`**（指纹已定死）：
   ```
   usd_fx: ↓（≥2 成员 signal 级下行）
   rates_long: yield↑（熊陡 → TLT/price ↓）
   rates_front: —（锚定/不领先）
   precious: ↑（Silver 佐证）
   equities_us / em: —，但 signal 级 ↓ 记为 conflict（增长背离守卫，防止股跌+美元弱被打成债务化）
   vol: ↓ 或低位
   判别 vs Policy-easing：宽松→长端 rally(收益率↓)+2Y 领跌；债务化→长端 sell(收益率↑)+2Y 锚定
   判别 vs USD-funding：funding→USD ↑↑；债务化→USD ↓
   single_day_max_confidence: ★★☆（★★★ 需 ≥2 sessions）
   ```
4. **噪音门参数**：默认 signal bar = `move_vol_pct ≥ 50`，BTC 专用 `≥ 65`。

**新建 `data/thresholds.schema.json`**，falsifier 字段：
```
{ asset, metric: move_vol_pct|consec_same_dir|level|nd_change,
  op: '>='|'<='|'flip_sign'|'cross', value, dir,
  window: 交易日数(默认1), consecutive: 需连续满足的日数(默认1), means }
```
三态判定：**TRIGGERED**（条件满足）/ **NEAR**（数值型达阈值 ≥80%，分位型差 ≤10 点，flip 型 consec 处于 ±1）/ **SAFE**。
并**手写样例** `reports/20260703--约束诊断-P.thresholds.json`（从该报告证伪条件转录：DXY vol≥50 up；USDCNY consec flip→positive；US_2Y vol≥50 down 等）。

**新建 `data/diagnosis_log.jsonl`**（诊断状态账本，whipsaw/retro 的依据；Schema D 天也有记录）。每行：`{date, schema: "A"|"D", regime|null, l2, l3, report_file}`。初始回填四条：
```
{date:"20260612", schema:"A", regime:"P", l2:"★★★", l3:"★☆☆"}
{date:"20260620", schema:"D", regime:null}
{date:"20260625", schema:"D", regime:null}
{date:"20260703", schema:"A", regime:"P", l2:"★★☆", l3:"★☆☆"}
```

### B1. `scripts/score_regimes.py`
- 输入：`load_for_analysis.py` 的合并输出 + `regime_matrix.json` + `diagnosis_log.jsonl` 最近一条。
- **评分语义（写死）**：对每行，只在该行指定了非 `—` 方向的类上计分：类 signal 对齐 = +1；类 conflicted（signal 级反向）= −1；类全噪音 = 不进分母；`↑?/↓?` 半权。`match% = 得分/分母`。行可 call 条件：`match% > 60%` **且** signal 对齐类数 ≥ 4（BTC 永不计入）。
- 输出 JSON：各行 match% + 命中/冲突/噪音类清单；**强制 liquidity-override 布尔**（USD↑+金↓+债↓+风险↓ 四条逐项）；**whipsaw 上限**：diagnosis_log 最近一条在 ≤3 sessions 内且 regime 不同且其信心 ≥★★☆ → 今日 cap ★★☆（附 `cap_reason`）；★★★ 需与上一 session 同 regime 连续；**`schema_d_suggested` 布尔**（无行 >60% 或 signal 类 <4 → true）。
- 纯计算、不写叙事。

### B2. `scripts/check_thresholds.py`
- 输入：最近一份 `reports/*.thresholds.json` + 最新快照 stats。
- 按 schema 三态逐条输出；**任一 TRIGGERED → exit code 非 0** 并打印 `ALERT` 行（供 wrapper 通知）。支持 `--date` 指定历史 mark。

### B3. `scripts/retro.py`
- 遍历 `reports/*.thresholds.json` + `diagnosis_log.jsonl`（无 sidecar 的老报告标 `no-sidecar` 跳过）。
- **判据（写死，参数可配）**：报告后 **N=5** 个交易日内任一 falsifier TRIGGERED → `falsified`；后 5 日中 ≥3 日该 regime 行仍为 best-match 且 >60% → `confirmed`；其余 `unresolved`。
- 汇总：Schema D 占比、各 regime confirmed/falsified 计数。

**验收 B**：
- `score_regimes.py` 跑 20260702：预期 `sell_america_debasement` 为最高分行、override=false、无 whipsaw cap（上一条 A 记录是 0612，>3 sessions）。
- `check_thresholds.py` 对 07-03 sidecar → 全 SAFE/NEAR；再改样例数值制造一次 TRIGGERED → exit≠0。
- `retro.py` 处理现有账本不崩、老报告优雅跳过。

---

## 任务 C：Session 新鲜度守卫

- **fetch_prices.py**：每资产补 `session_kind`（`us_close` / `intraday_stale`）：最新 bar 非完整 US 收盘 bar 时标后者。
- **load_for_analysis.py**：按 `fetched_at` 时点 + 各资产 `session_kind` 汇总出顶层 `mark_quality: us_close | intraday_stale`，只警示**不阻断**。

**验收 C**：US-close 快照 → `us_close`；盘中时点手动 fetch → `intraday_stale`。

---

## 任务 D：闭环接线（把 check_thresholds 接进每日链路）

**文件**：`~/bin/market-auditor-capture.sh`（launchd plist 不动）。

- 捕获成功后新增第 4 步：跑 `check_thresholds.py`；exit≠0 时 `osascript -e 'display notification ...'` 弹 macOS 通知 + 追加 `data/alerts.log`。
- **隔离性硬要求**：核对/通知任何失败都不得改变 wrapper 的退出码语义（capture 的 rc 仍是 wrapper 的 rc）；核对步骤整体 best-effort。

**验收 D**：手动 `bash ~/bin/market-auditor-capture.sh` → 捕获正常 + 核对跑过 + 无误报；用改数样例制造 TRIGGERED → 收到通知 + alerts.log 有记录 + wrapper rc 仍为 0。

---

## 端到端验证（跑完贴输出到 CHANGES.md）

1. `fetch_prices.py`（运行副本）：2Y 真实、21 资产照常、`--simulate-missing` 生效。
2. `capture_snapshot.py`：正常日 `degraded:false`；模拟残缺 `degraded:true`+`missing`；副本漂移 WARN 可触发。
3. 回填后 `compute_stats.py --snapshot 20260702` + `load_for_analysis.py --summary`：形状不变、退化日排除、consec 桥接、2Y 无断裂。
4. `score_regimes.py` / `check_thresholds.py` / `retro.py` 按验收 B 各贴一份实测输出。
5. wrapper 全链手动跑一遍（验收 D）。
6. 两份 `fetch_prices.py` `diff` 为空。

## 交付物清单

- 改：`fetch_prices.py`×2、`capture_snapshot.py`、`compute_stats.py`、`load_for_analysis.py`、`backfill_history.py`、`~/bin/market-auditor-capture.sh`
- 新：`data/regime_matrix.json`、`data/thresholds.schema.json`、`data/diagnosis_log.jsonl`、`reports/20260703--约束诊断-P.thresholds.json`、`scripts/score_regimes.py`、`scripts/check_thresholds.py`、`scripts/retro.py`
- 数据：`timeseries.jsonl` + 历史快照的 `US_2Y_yield` 回填（含备份）
- `CHANGES.md`
- **不 commit、不动协议三文件**

## 后续（不在本次外包范围，review 通过后由发包方做）

1. **协议侧**：SKILL.md 把 live-fetch(1c) 降级为"仅捕获输入、诊断禁用"；诊断 Workflow 强制产出 thresholds sidecar + 追加 diagnosis_log；preflight 增加 degraded/stale/mark_quality 处理；protocol.md §2 增补 sell-america 行 prose 与判别规则、§3 说明 whipsaw/评分由 score_regimes 机械执行。
2. **每日自动诊断**：`/schedule` 建每日 routine（US 收盘冻结后自动跑 Workflow A，无信号日照常出 Schema D）。
3. 报告口径修订：历史报告中"2Y"实为 3M 的事实，在下一份诊断中作一次性披露。
