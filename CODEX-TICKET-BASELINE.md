# 工单 — 基线净化：重复行剔除 + 移仓嫌疑标记（Backlog Round 6）

> 背景：Round 5 普查证实两项污染。①E 项：周末/假日捕获行原样复制前一交易日的
> (last, change)，vol 分位分布把同一变动重复计入 2-3 次（纳指/EM/HYG/TLT 等 88.9%
> 的非交易日行是重复行）；②C 项：能源期货月频移仓跳空混入分布。本工单在
> **compute_stats 读取层**中和 ①、标记 ②——不改写任何数据文件。

## 边界

- **只改 `scripts/compute_stats.py`**（+CHANGES.md）。data/ 全部只读——本修复是读取语义变更，不是数据迁移。
- 不 commit、不碰协议、测试用 `/Users/jowang/miniconda3/bin/python3`、无需网络（沙箱友好）。

## 改动 1：重复条目剔除（E 项修复，核心）

**判定规则（写死，逐资产粒度）**：某行中某资产的条目是"**重复条目**"，当且仅当其
`(last, change值)` 与该资产**上一个被保留条目**完全相等。（change 值取 asset_change
归一后的数；两者都相等才算——真实的平盘日 change=0 但上日 change≠0，不会误伤；
连续两天完美平盘才会误判，可接受。）

**语义**：每个资产的分析时间线 = 仅由"新 bar 条目"构成的**压缩序列**：
- `consec_same_dir` / `Nd_change` / vol 分位分布全部在压缩序列上计算——周五→周一
  在压缩序列上天然相邻，**不再触发缺口重置**（顺带修复 A′ 遗留的 SHY 周一 today_change=None 问题）。
- 真实数据故障（市场开着、别的资产有新 bar、本资产缺失/重复）仍需 `gap_adjacent=true`：
  判定 = 上一保留条目与当前条目之间存在 ≥1 个中间行，其中 **SP500 有新 bar** 而本资产没有。
  此时沿用现行为（vol_pct=None、打折）。市场关闭日（SP500 也无新 bar 的中间行）不算故障。
- 现有 degraded 行排除、source_switch 防护、legacy 容错逻辑全部保留，叠加生效。
- 输出每资产新增 `dup_days_excluded`（本次计算剔除的重复条目数）便于审计对账。

## 改动 2：移仓嫌疑标记（C 项，只标不删）

- 对期货资产（Gold/Silver/Brent/WTI/NatGas/Copper）：当日 |change| 同时满足
  ①> 压缩序列分布的 4×MAD ②绝对值 >2%，则 stat 加 `roll_suspect: true`。
- **只标记，不从分布剔除、不置 None**——尺寸上无法区分移仓跳空与真实暴动日，
  静默剔除会吞掉真实危机信号（本引擎的命门）。消费责任在协议层（协调侧接线）。

## 验收（贴 CHANGES.md「Round 6 (baseline purge)」）

1. **合成测试**：构造含 a)周末重复行 b)连续两天完美平盘 c)市场开着但单资产数据故障
   三种情形的小时间线 → 分别验证 剔除/保留/gap_adjacent 行为符合上述规则。
2. **真实回归**：`compute_stats --snapshot 20260706` 前后对比表（≥6 个代表资产的
   vol_pct/consec 新旧值 + dup_days_excluded）；**SHY 的 today_change 应从 None 变为数值**；
   US_2Y 周末重复（E 项 100%）应全数剔除。
3. `score_regimes --date 20260706` 重跑，best row 与各行 match% 新旧对照（结论变化属预期修正，如实记录）。
4. 幂等连跑一致；py_compile；data/ 零写入（sha256 前后对比 timeseries/diagnosis_log）；不 commit。
