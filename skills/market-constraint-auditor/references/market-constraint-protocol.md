# Market Constraint Protocol

This is the analytical rulebook. SKILL.md tells you what to do; this file tells
you how to think.

---

## §1 Constraint Taxonomy

The market is always pricing at least one dominant constraint. Your job is to
identify which one.

| ID | Constraint | Core dynamic |
|----|-----------|--------------|
| G  | **Growth** | Economy slowing, earnings downgrades, demand weakening |
| I  | **Inflation** | Price stickiness, input-cost pass-through, real-rate pressure |
| L  | **Liquidity** | Deleveraging, margin calls, forced selling across all asset classes |
| F  | **USD Funding** | Global dollar shortage, funding-chain stress, non-US asset liquidation |
| S  | **Geopolitical Supply** | Energy/shipping/materials disruption, insurance repricing |
| P  | **Policy** | Central bank path repricing, fiscal supply shifts, regulatory regime change |
| M  | **Multi-constraint** | ≥2 constraints active simultaneously, no single framework explains all prices |

---

## §2 Asset-Regime Fingerprint Matrix

This is the core diagnostic tool. Compare observed asset directions against these
fingerprints to identify the regime.

**Direction codes:** ↑ = up, ↓ = down, — = ambiguous/flat, ↑? = biased up but
not definitive, ↓? = biased down but not definitive

| Regime | USD | UST 10Y price | Gold | Oil/Cmdty | Risk assets | VIX |
|--------|-----|---------------|------|-----------|-------------|-----|
| Classic risk-off | ↑? | ↑ | ↑ | ↓? | ↓ | ↑ |
| Recession trade | ↓? | ↑ | ↑? | ↓ | ↓ | ↑ |
| Inflation trade | — | ↓ | ↑? | ↑ | ↓? (growth ↓, value ↑?) | ↑? |
| Liquidity crunch | ↑ | ↓ | ↓ | ↓? | ↓ | ↑↑ |
| USD funding stress | ↑↑ | — | ↓? | — | ↓ (esp. non-US) | ↑ |
| Geopolitical supply shock | — | — | ↑? | ↑↑ | ↓ (sector-specific) | ↑ |
| Policy easing trade | ↓? | ↑ | ↑? | — | ↑ (growth > value) | ↓ |
| Multi-constraint | conflicting signals across columns; no single row matches cleanly |

### How to use the matrix

1. Build the observed direction vector from user data or web search results.
2. Score each regime row by counting matches vs. mismatches.
3. The highest-scoring row is the primary diagnosis; the second-highest is the
   alternative.
4. **Critical override:** If USD ↑, gold ↓, bonds ↓, risk ↓ simultaneously →
   score Liquidity/Funding first regardless of other signals. This pattern is the
   most dangerous to misdiagnose because conventional "risk-off" playbooks fail.
5. If no row scores above 60% match, default to Multi-constraint and say so.

### Disambiguation rules

Some regimes produce similar fingerprints. Use these tiebreakers:

- **Classic risk-off vs. Recession trade:** Check oil. If oil is falling hard,
  it's leaning recession (demand destruction). If oil is flat or up, it's
  generic risk-off without a clear growth signal.
- **Liquidity crunch vs. USD funding stress:** Check gold and EM FX. If gold is
  also being liquidated, it's liquidity (sell everything). If gold holds but EM
  FX collapses, it's USD funding (dollar shortage, not universal deleveraging).
- **Inflation trade vs. Geopolitical supply shock:** Check the breadth of
  commodity moves. If oil AND base metals AND ags are all up, it's broad
  inflation. If only oil/shipping/insurance are up, it's geopolitical supply.
- **Policy easing vs. Recession trade:** Check risk assets. If equities rally on
  rate-cut expectations, it's policy easing. If equities fall despite rate-cut
  pricing, the market believes easing won't be enough — that's recession.

---

## §3 Confidence Calibration

| Level | Label | When to use |
|-------|-------|-------------|
| ★★★ | 高确定性 | ≥5 asset classes align with one regime row; no major conflicts |
| ★★☆ | 中等确定性 | 4 asset classes align; 1-2 minor conflicts explainable as noise or lag |
| ★☆☆ | 低确定性 | 2-3 asset classes align; significant conflicts; multi-constraint likely |

Rules:
- Never claim ★★★ if you have fewer than 5 data points.
- If the user only provides 2-3 assets, cap at ★☆☆ and explicitly say why.
- If you used web search to supplement, note which data points came from search
  vs. user input.

---

## §4 Failure Modes

Memorize these. Check against every output before delivering.

| # | Failure | Test |
|---|---------|------|
| F1 | Single-asset-to-macro | Did I conclude a regime from <2 asset classes? |
| F2 | News-first reasoning | Did I read news before examining prices? |
| F3 | Correlation-as-causation | Did I assume co-movement means shared driver? |
| F4 | Hindsight-as-foresight | Am I presenting a post-hoc explanation as a prediction? |
| F5 | False certainty under conflict | Am I forcing one answer when signals genuinely clash? |
| F6 | Macro platitudes | Did I use "risk appetite", "sentiment", "concern" without naming a mechanism? |
| F7 | Liquidity blindness | Did I default to "risk-off" when the pattern was actually liquidity/funding? |

Before outputting, run through F1-F7 as a checklist. If any fails, fix the
output.

---

## §5 Output Schemas

All outputs are in Chinese by default. Section headers are fixed; content under
each header adapts to the specific situation.

### Schema A: Regime Diagnosis

```
## 主判断

- **主导约束：** [从§1选一个]
- **市场阶段：** [从§2矩阵行名选一个]
- **确定性：** [★☆☆ / ★★☆ / ★★★]
- **备选解释：** [第二匹配的约束+阶段，一句话说明为什么它是备选而非主判断]

## 证据链

| 资产 | 方向 | 支持主判断 / 冲突 / 中性 | 备注 |
|------|------|--------------------------|------|
| ...  | ...  | ...                      | ...  |

冲突信号判断：[噪音 / 阶段切换早期信号 / 多因子叠加]

## 机制

[2-4句话解释核心传导链。不准用"情绪""担忧"等空词。]

新闻角色：[触发器 / 放大器 / 事后叙事]

## 证伪条件

- 如果 [具体资产] 出现 [具体方向]，当前判断大概率错误
- 最大风险来源：[一句话]

## 观察清单

| 变量 | 上行含义 | 下行含义 | 阶段切换阈值 |
|------|----------|----------|-------------|
| ...  | ...      | ...      | ...         |

**一句话总结：** [当前盘面的最精炼描述]
```

### Schema B: Thesis Audit

```
## 观点审计

- **原命题：** [用一句话复述被审计观点的核心主张]
- **最薄弱跳跃：** [指出最大的逻辑漏洞]
- **相关性↔因果混淆：** [有/无，具体说明]
- **事后归因：** [有/无，具体说明]
- **单资产推全局：** [有/无，具体说明]
- **结论：** 保留 / 修正 / 否定
- **修正建议（如适用）：** [怎样改才能站住脚]
```

After the audit, append a condensed Schema A to show what the price evidence
actually supports.

### Schema C: Watchlist

```
## 观察清单

| 变量 | 上行含义 | 下行含义 | 阶段切换阈值 |
|------|----------|----------|-------------|
| ...  | ...      | ...      | ...         |

**当前最该盯的一件事：** [从清单中选权重最高的一个]
```

---

## §6 Worked Examples

### Example 1: Clear liquidity crunch

**Input:**
- USD (DXY): +1.2%
- UST 10Y: yield +15bps (price down)
- Gold: -2.1%
- Brent: -3.5%
- S&P 500: -3.8%
- VIX: 32 (+40%)
- News: Geopolitical tensions escalating; multiple headlines say "risk-off"

**Correct diagnosis:**

主导约束：流动性约束 (L)
市场阶段：流动性踩踏
确定性：★★★

Key reasoning: This is NOT classic risk-off despite news framing it that way.
In genuine risk-off, bonds and gold rally as safe havens. Here, everything is
being sold — including traditional hedges — while USD strengthens. This is the
fingerprint of forced liquidation / margin-call driven selling. The geopolitical
news may have been the trigger, but the mechanism is deleveraging, not
risk-preference rotation.

Evidence table: All 6 assets match the Liquidity crunch row perfectly.

Falsification: If gold and UST prices start recovering while equities remain
weak → regime is transitioning from liquidity crunch to classic risk-off. Watch
for the gold-equity divergence as the signal.

### Example 2: Ambiguous / multi-constraint

**Input:**
- USD (DXY): +0.3%
- UST 10Y: yield +5bps (price slightly down)
- Gold: +0.8%
- Brent: +2.4%
- S&P 500: -1.2%
- VIX: 21 (+8%)
- News: Mixed — some inflation data, some growth concerns, geopolitical noise

**Correct diagnosis:**

主导约束：多重约束叠加 (M)，通胀约束 (I) 略占主导
市场阶段：多因子混合阶段，偏向通胀交易
确定性：★☆☆

Key reasoning: Oil up + bonds down + gold up is consistent with inflation trade.
But USD is up (inflation trade is usually USD-ambiguous) and VIX is only mildly
elevated. Equities are down but not crashing. No single regime row scores >60%.

The honest answer is: the market hasn't made up its mind. Inflation constraint
is the leading candidate, but not dominant enough to call with confidence.

Falsification: If oil reverses down while bonds rally → growth constraint taking
over. If gold reverses down while USD accelerates → funding stress entering.

### Example 3: Thesis audit — flawed reasoning

**Input thesis:** "黄金突破2400说明全球进入全面避险，美股必跌美债必涨。"

**Correct audit:**

原命题：黄金突破关键价位 = 全面避险启动 = 美股下跌 + 美债上涨
最薄弱跳跃：黄金上涨有多种驱动（央行买盘、实际利率下行、美元走弱、通胀对冲），
不能直接等于"全面避险"。这是 F1（单资产推全局）。
相关性↔因果混淆：有。黄金与避险的相关性存在，但因果链不成立——2023-2024央行
购金潮推动的黄金牛市与风险偏好基本无关。
事后归因：有。"突破2400"是价格已经发生的事实，用已发生的价格来"预测"其他资产
的走向，是典型的F4。
结论：否定。

修正建议：要判断是否进入全面避险，需要同时观察美债、VIX、信用利差、美元、
原油的方向组合，不能仅凭黄金一个资产下结论。
