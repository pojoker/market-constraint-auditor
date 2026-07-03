# 修复清单 — CODEX-PLAN-20260703 验收返工（第 2 轮）

> 第 1 轮验收结论：约 80% 合格，架构与数据回填质量高。但存在 2 个功能性缺陷（F1/F2）+ 3 个静默偏差（F3/F4/F5+F6）+ 2 个小修（F7/F8）+ 1 个测试残留清理（F9）。**全部修完才能 commit。**
> 本轮同样：**只改脚本与数据文件，不动协议三文件（SKILL.md / market-constraint-protocol.md / V1.0.3-DRAFT-NOTES.md），不 commit**。修完在 `CHANGES.md` 追加「Round 2 Fixes」章节，逐项贴验收实测输出。

## 环境提醒（同第 1 轮）

- 测试一律用 `/Users/jowang/miniconda3/bin/python3`。
- `fetch_prices.py` 双副本（`~/.claude/skills/market-constraint-auditor/scripts/` 运行副本 + `skills/market-constraint-auditor/scripts/` git 副本）：本轮 F7 会碰它，改完必须保持逐字一致（`diff` 为空）。
- **本轮禁止运行 `capture_snapshot.py`**（避免再次向冻结数据写入盘中杂交 mark，见 F9 教训）。所有测试用 `--date 20260702` 或合成数据。

---

## 🔴 F1. check_thresholds 默认评估日期钉死在 report_date（每日闭环失效）

**现状**：`check_thresholds.py` 中 `date = args.date or spec.get("report_date")`。wrapper 每日无参调用 → 永远评估 20260703 那个 mark，数据日期从不前进；闭环报警等于没接。

**修复**：默认 `date = args.date`（即 None → `load_analysis(None)` 加载**最新快照**）。`spec["report_date"]` 只放进输出 JSON 作元数据，不再决定评估日期。

**验收**：`check_thresholds.py` 无参运行 → 输出的 `date` == timeseries 最新日期（F9 清理后应为 `20260702`）。

## 🔴 F2. sell_america 的 guards 是死代码（增长背离守卫从未执行）

**现状**：`score_regimes.py` 的评分循环只读 `spec["directions"]`，`regime_matrix.json` 里 sell_america 的 `guards` 块从未被读取。今天 EM 是 signal 级下行，本应记 conflict，实际未计入。

**修复**：在 `score()` 中对每行应用 `spec.get("guards", {})`，语义写死如下：
- `"signal_down_conflict"`（用于 `equities_us` / `em`）：该类 state == signal 且 dir == "↓" → 计入 conflict（权重 1.0：加入分母、扣分、加入 conflicted 列表）。signal ↑ → 中性（不计入分母）。noise → 不计入。
- `"anchor_or_not_leading"`（用于 `rates_front`）：该类 state == signal（**任一方向**，价格约定）→ 计入 conflict（权重 1.0）。noise → 不计入（noise 正是"锚定"的满足态，不加分）。
- 文本型 guard（`vs_policy_easing` / `vs_usd_funding`）仅是文档，跳过不解析。

**验收**：`score_regimes.py --date 20260702` → sell_america 行：`em` 出现在 conflicted、`match_pct == 60.0`（(4−1)/5）、`callable == false`、`schema_d_suggested == true`。**这是预期的结论变化**（机械门比 07-03 人工 ★★☆ 更严格，属设计意图——scorer 是给 LLM 的输入而非最终裁决），在 CHANGES.md 里明确记录这一预期差异。best_regime 仍应为 sell_america（最高 match%）。

## 🟠 F3. vol 类的绝对水平短路污染所有 regime 行

**现状**：`class_state()` 对 `"vol"` 特判：VIX≤18 且 MOVE≤75 → 直接返回 signal "↓"，**先于**动量判定。后果：VIX 12→16.5（+37%、vol 分位 90）的 risk-off 早期日仍被判 "↓"，对 risk-off 行记 conflict——方向完全错误。今天恰好方向对，掩盖了 bug。

**修复**：
1. `class_state()` 里 vol 类走与其它类相同的 move-based 判定（VIX/MOVE 都是普通 change_pct 资产，无反转）。删除水平短路。
2. 另计算独立布尔 `vol_low_level = (VIX ≤ 18 and MOVE ≤ 75)`，放进输出（`class_states` 旁或顶层）。
3. `regime_matrix.json` 的 sell_america 行加 `"accept_low_level_vol": true`；评分时**仅对带此 flag 的行**：若 vol 类为 noise 且 `vol_low_level` 为真 → vol 按 aligned 计入 match%（权重照 directions 给的 1.0），**但不计入 "≥4 signal 类" 的 callable 计数**（它不是 signal 级动量）。
4. 其它行的 vol 在 noise 时一律不计入分母（与所有类一致）。

**验收**：
- 合成测试（参考第 1 轮验收用的注入法，import compute/score 相关函数或构造 stats dict）：VIX move_vol_pct=90、change +30%、level 16 → vol 类 = signal "↑"（不是 "↓"）。
- `score_regimes.py --date 20260702` 真实数据：vol 类 state == "noise"（VIX vol30/MOVE vol29）、`vol_low_level == true`、sell_america 的 aligned 含 vol（经 low-level 通道）、match% 仍为 60.0、signal 类计数 = 3。

## 🟠 F4. 10Y/30Y 单位混合（17-18 天 change_pct 混进 bps 分布）

**现状**：timeseries 里 US_10Y/30Y 有 121 天 `change_bps`（中位 |move| 2.60）+ 17-18 天旧 live 抓取的 `change_pct`（中位 0.54），`asset_change()` 直接混用 → vol 分位失真。实测：07-02 的 10Y 真实动作是 +11.3bp，旧算法给了 55 分位；归一后应为高分位 signal 级。

**修复**：`compute_stats.py` 的 `asset_change()` 对 `YIELD_ASSETS` 读时归一（不改数据文件）：
```python
if name in YIELD_ASSETS:  # 需要把 asset name 传进来，或改为按 entry 内容判断
    if "change_bps" in entry: return entry["change_bps"]
    if "prev" in entry and "last" in entry: return round((entry["last"] - entry["prev"]) * 100, 1)
    return None
```
非收益率资产逻辑不变。注意 `asset_change` 现签名只收 entry，需要加 name 参数并更新两处调用点。

**验收**：`compute_stats.py --snapshot 20260702` → `US_10Y_yield.today_change == 11.3`（不再是 2.58）、`move_vol_pct` 显著上移（预期 ≥85，贴实测值即可）；`US_30Y_yield` 同理（真实动作 +12.1bp）。在 CHANGES.md 记录新旧分位对比。

## 🟠 F5 + 🟡 F6. whipsaw 用 constraint code 比较，"P" 家族反转逃逸；retro 的 confirmed 不检查行匹配

**现状**：
- `score_regimes.py` whipsaw 比较 `prev["regime"] != matrix[best]["code"]`——policy_easing_trade 与 sell_america_debasement 同 code "P" 但指纹相反（长端 rally vs selloff），昨日宽松 ★★★ → 今日债务化不会被 cap。
- `retro.py` 的 confirmed 判据是 `best[1] > 60`，**任何行** >60 都算确认，没检查 best 行是否等于该报告自己的行。

**修复**：
1. `data/diagnosis_log.jsonl` 每行增加 `"regime_row"` 字段（矩阵行键）。现有 4 条回填为：
   - 20260612 → `"regime_row": "policy_easing_trade"`
   - 20260620 / 20260625 → `"regime_row": null`
   - 20260703 → `"regime_row": "sell_america_debasement"`
2. `score_regimes.py` whipsaw 改为比较 `prev["regime_row"] != best_row_key`（prev 无该字段时回退比较 code，兼容旧数据）。
3. `retro.py` confirmed 改为：`best 行键 == 该报告的 regime_row` 且 match% > 60，≥3/5 天。
4. `data/thresholds.schema.json` 与样例 sidecar `reports/20260703--约束诊断-P.thresholds.json` 增加顶层 `"regime_row"` 字段（样例填 `"sell_america_debasement"`）。

**验收**：
- 临时向 diagnosis_log 追加一条 `{date:"20260701", schema:"A", regime:"P", regime_row:"policy_easing_trade", l2:"★★★", ...}` → `score_regimes.py --date 20260702` 输出 `whipsaw_cap == "★★☆"` 且 cap_reason 指向它；**测完删除临时行**，恢复后再跑确认 cap 回到 null。
- `retro.py` 重跑：20260703 条目按 sell_america 行判定，输出贴 CHANGES.md。

## 🟡 F7. mark_quality 被单资产 FRED fallback 污染（慢性误报）

**现状**：`fetch_prices.py` 的 `fallback_yield()` 把 session_kind 硬编码为 `"intraday_stale"`；`load_for_analysis.mark_quality()` 是 any() 语义 → 2Y 走 FRED 的每一天（可能是常态），整个 US 收盘 mark 都被标 `intraday_stale`。

**修复**：
1. `fallback_yield()` 的 session_kind 改为新枚举 `"prior_close"`（数据是真收盘、只是滞后一天）。
2. `mark_quality()`：仅当存在 session_kind == `"intraday_stale"` 的资产时返回 `intraday_stale`；`prior_close` 不污染整体。
3. `load_for_analysis` 输出顶层增加 `"stale_assets": [...]`（所有 `stale == true` 的资产名），summary 表照旧显示 stale 标记。
4. **双副本同步**（此项动 fetch_prices.py）。

**验收**：python 内联构造含 `prior_close` 资产的 snapshot dict 调 `mark_quality()` → 返回 `us_close`；含 `intraday_stale` 资产 → 返回 `intraday_stale`。贴测试代码与输出。

## 🟡 F8. NEAR 判定不看方向（反向大动作被标"接近证伪"）

**现状**：`check_thresholds.evaluate()` 中 `>=` / `<=` / `cross` 的 `near` 不含方向检查 → 07-02 的 DXY vol 83 但方向**向下**（利好当前判断）仍被标 NEAR。

**修复**：`near` 判定同样要求 `direction_ok(stat, rule)`（`dir` 为 None/"any" 时不受影响）。`flip_sign` 分支的 near（consec ∈ {−1,0,1}）保持不变。

**验收**：`check_thresholds.py --date 20260702`（配合 F1 修复后用显式 --date）→ DXY 应为 `SAFE`（vol 83 但 dir=down ≠ up）；预期全表 SAFE、rc=0。贴全表输出。

## 🧹 F9. 清理第 1 轮测试残留的盘中杂交快照

**现状**：第 1 轮测试在 00:56 UTC 跑了真实 capture，产生 `data/snapshots/20260703.json` + timeseries 的 20260703 行——这是**盘中杂交 mark**（DXY 带隔夜期货噪音、USDCNY consec 被翻成 +1），今天任何"latest"分析都在读它。

**修复**：删除 `data/snapshots/20260703.json`，并从 `data/timeseries.jsonl` 移除 `"date":"20260703"` 那一行（明天 21:45 UTC 的正规 launchd 捕获会以真实收盘重建它）。**不要**动其它任何行。

**验收**：`load_for_analysis.py --summary` 无参 → `分析就绪数据 (20260702)`；timeseries 行数回到 152。

---

## 完成后的端到端复验（贴 CHANGES.md「Round 2 Fixes」）

1. `check_thresholds.py` 无参 → date=20260702、全 SAFE、rc=0（F1+F8+F9）。
2. `score_regimes.py --date 20260702` → sell_america: match 60.0 / em conflicted / callable=false / schema_d_suggested=true / vol 经 low-level 通道 aligned / whipsaw_cap=null（F2+F3+F5）。
3. `compute_stats.py --snapshot 20260702` → 10Y today_change=11.3、vol 分位新值（F4）。
4. whipsaw 临时注入测试输出（F5）+ retro 重跑输出（F6）。
5. mark_quality 内联测试输出（F7）。
6. 两份 `fetch_prices.py` `diff` 为空。
7. 确认未运行 capture、未 commit、协议三文件 mtime 未变。
