# 工单 4（收敛版）— 快照/时间序列键 = 数据日：键位生成规则修复（Round 10）

> 背景：键位病一周三咬——①07-08 gate 误杀（已用 diagnosed_marks 数据日空间绕开）；
> ②07-11 Mac 睡眠致捕获延至 10:24（UTC 已过午夜），07-10 收盘被错挂 20260711 键，
> 险些被当晚正常捕获同键覆盖蒸发（已人工手术）；③报告/账本长期要脑内 +1 换算。
> **实证结论**：正常运行时"捕获 UTC 日 == 数据日"恒成立（21:45 UTC 捕获当日收盘），
> 历史键已全部等于数据日（含两次手术修正）——**无需数据迁移**，只需修键位生成规则：
> 晚发捕获自动按数据日挂键。

## 边界（违反任何一条 = 全单拒收）

- **只动 `scripts/capture_snapshot.py`** + `CHANGES.md`（追加「Round 10 (date-key rule)」）。
- 不碰协议三件套；不 git commit；测试用 `/Users/jowang/miniconda3/bin/python3`；
  无需网络（合成快照测试）；data/ 只读（timeseries.jsonl / diagnosis_log.jsonl /
  open_threads.jsonl / diagnosed_marks.txt sha256 前后一致；合成数据写 tmp）。

## 改动 — trading_date() 键位规则（写死）

现行：`date_key = fetched_at 的 UTC 日期`。改为：

1. **数据日 D = 股指锚（SP500）的 `as_of`**（YYYY-MM-DD → YYYYMMDD）。
2. **若 `data_changed_vs_prev == True`（有新收盘）→ `date_key = D`。**
   - 准点运行（21:45 UTC）：D == 捕获 UTC 日，行为与现行完全一致；
   - 晚发运行（跨过 UTC 午夜，如 07-11 02:24 捕获 07-10 收盘）：自动挂 D，
     不再错挂捕获日。
3. **若 `data_changed_vs_prev == False`（周末/假日，锚未前进）→ 维持现行
   `date_key = 捕获 UTC 日`**——闭市日的重复行按捕获日记档，是 Round 6 压缩
   序列去重逻辑的既有输入语义，不得改变。
4. SP500 缺失/as_of 不可解析 → 回退现行规则（捕获 UTC 日）+ 日志 WARN。
5. 注意判定顺序：现行代码里 `has_data_changed()` 在 date_key 之后才算——需要
   重排为「先取锚 as_of 与变更判定，再定键」，且 `has_data_changed` 的"prev 行"
   查找必须基于数据日键位后的语义仍正确（prev = date < D 的最近行）。

## 附带一次性校验（只读，输出到 stdout/CHANGES，不改数据）

扫描现有 timeseries 全部行，输出对账表：每行 `date` vs `SP500.as_of`（compact），
分三类计数——一致 / 闭市重复行（as_of 落后且与前行同值）/ 异常（其他不一致）。
预期异常 = 0（历史已含两次人工手术）；若非 0，如实列出留给验收方裁决，**不得自行改写**。

## 验收（贴 CHANGES.md，逐项实测输出）

1. **准点合成**：fetched_at 21:45 UTC 当日、锚 as_of 同日、changed=True →
   date_key 与现行规则一致（回归零差异）。
2. **晚发合成**（本周实案重演）：fetched_at 02:24 UTC D+1、锚 as_of=D、
   changed=True → date_key=D；且再模拟当晚准点捕获（锚 as_of=D+1）→
   date_key=D+1，**两行共存无覆盖**。
3. **周末合成**：锚 as_of 落后、changed=False → date_key=捕获日（现行为准），
   Round 6 去重语义回归（构造周五+周六 dup 行 → compute_stats 剔除行为不变）。
4. **锚缺失合成**：SP500 缺位 → 回退捕获日 + WARN 落日志。
5. 一次性校验表（现有 160 行全扫）：三类计数 + 异常明细（预期 0）。
6. py_compile；data/ 四文件 sha256 前后一致；不 commit。
