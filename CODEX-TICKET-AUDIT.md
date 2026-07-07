# 工单 — 数据源机械审计器 audit_sources.py（Backlog Round 5）

> 背景：三周三个数据源事故同根源（^IRX 语义错 / bps-%混合 / 2YY 流动性僵尸）。本工单交付**可复跑的机械体检器**，与人工语义台账（data/SOURCES.md，协调侧另行编写）配对，构成完整数据源审计。

## 边界

- **只新建 `scripts/audit_sources.py` + 允许改 `CHANGES.md`**；对 data/ 全部**只读**（timeseries/snapshots/账本一个字节不许写）；不 commit；不碰协议文件。
- 测试用 `/Users/jowang/miniconda3/bin/python3`；yfinance/requests 可用、网络可用。
- 审计报告输出到 `data/source_audit_<YYYYMMDD>.md`（这是唯一允许的新写入物）+ 同名 `.json`。

## 检查项（每资产逐项，输出 绿/黄/红）

**A. 僵尸/分布健康**（timeseries 近 120 个有效日）
- 零变动天占比（>40% 红、>20% 黄）；唯一 last 值个数；|change| 中位数；最长连续不变天数。
- 2YY 教训的代码化：这些指标当初能一眼判死 2YY。

**B. 成交量门**（yfinance 实时拉，period=3mo）
- 对期货/ETF 类 ticker 取 Volume 列：中位日成交量、零成交天占比。
- 中位量 <100 红、<1000 黄（指数类 ^GSPC/^VIX/^MOVE/^TNX/^TYX 与 FX =X 无量，标 N/A）。

**C. 期货移仓跳空探测**（GC/SI/BZ/CL/NG/HG 六个 =F 资产）
- 金属交叉核对：GC=F vs GLD、SI=F vs SLV 的日变动差 >0.8% 的天数清单（GLD/SLV 为实物 ETF≈现货，前月期货与其背离日 ≈ 移仓伪影候选）。
- 能源/铜（无干净现货 ETF）：列出 |日变动| 超过自身 4×MAD 的离群日清单，标注"需人工核对是否换月日"。
- 输出各资产受污染天数估计——这直接决定 vol 分位的可信度。

**D. as_of 滞后统计**（新格式快照，2026-07-03 起）
- 每资产 as_of 与 SP500 as_of 的滞后天数分布；恒滞后者列出（预期：US_2Y=t+1 by design）。

**E. 周末/假日重复变动污染**（重要，疑似全资产性问题）
- 找出 timeseries 中日期非 SP500 交易日的行（周末/假日捕获行）；统计这些行里各价格资产携带的 change 与前一交易日 change **完全相同**的比例。
- 若确认：说明 vol 分位分布把周五的变动重复计入了 2-3 次——量化污染程度（每资产受影响样本数/占比），**只量化不修**（修复方案协调侧裁决）。

**F. 专项**
- `USDCNY=X`：零变动天占比、周末 bar 行为、在 21:45 UTC 捕获时的 as_of 语义（onshore 收盘早于捕获 5 小时+）。
- `^MOVE`：as_of 滞后（该指数日更且发布晚，Yahoo 常见 t+1）+ 连续相同收盘天数。
- `BTC-USD`：确认 calendar-align 后无周末 bar 泄漏进序列。

## 输出格式

`data/source_audit_<date>.md`：
1. 顶部汇总表：资产 × {A分布/B成交/C移仓/D滞后/E重复} 五列 绿🟢黄🟡红🔴。
2. 每个 🔴/🟡 一段：证据数字 + 一句"建议动作"（如"移仓日 change 置 None"、"换源"、"仅方向使用"）。
3. 同名 .json 供后续脚本消费。
- 脚本 exit code 恒 0（体检是信息不是门禁）；`--json-only` flag 支持。

## 验收（贴 CHANGES.md「Round 5 (source audit)」）

1. 实跑一次全量审计，报告落盘；汇总表贴 CHANGES。
2. 已知结论回归自检：US_2Y(DGS2) 的 D 项应显示恒 t+1（by design 标注）；SHY 的 B 项应为绿；若 E 项确认重复污染，给出各资产受影响占比表。
3. 幂等：连跑两次结果一致；data/ 除审计报告外零改动（跑前后对 timeseries + diagnosis_log 做 sha256 对比并贴出）。
4. py_compile；不 commit。
