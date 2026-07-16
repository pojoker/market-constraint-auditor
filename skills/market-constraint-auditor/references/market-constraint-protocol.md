# Market Constraint Protocol

This is the analytical rulebook. SKILL.md tells you what to do; this file tells
you how to think.

---

## §0 Four-Layer Diagnostic Framework — what you're actually claiming

**Read this before §1. Every other section in this file operates inside this
framework.**

When you say "the market is in regime X," you are making one of four very
different claims. Conflating them is the most common analytical error in
macro — including by professionals. This skill operates at Layer 2 and makes
disciplined inferences toward Layer 3. It does **not** have the data to speak
to Layer 1 or Layer 4.

| Layer | What it describes | What you need to see it | This skill's access |
|-------|-------------------|-------------------------|---------------------|
| **L1 Flow** | Mechanical positioning: dealer gamma, CTA, vol-target VaR, systematic re-leveraging, short covering | dealer/CTA position data, OI, fund flows | **Proxy only** (via MOVE, VIX behavior, breadth asymmetries, **BTC** as a 24/7 high-beta risk-appetite / marginal-liquidity proxy — confirmer only, see §3) |
| **L2 Pricing** | Cross-asset directional alignment — what the matrix in §2 reads | last prices + day moves across asset classes | **Direct** — this is what we see |
| **L3 Narrative** | The story the market is pricing toward (reflation, recession, funding stress, etc.) | inference from L2 + persistence over time | **Indirect** — inferred from L2 |
| **L4 Reality** | What is actually happening in the economy: PMIs, credit creation, freight, earnings, loan growth, inventories | macroeconomic data, micro data, surveys | **None** — out of scope |

### The cardinal rule

**Never use one layer's word for another's job.**

- "市场以 X 方式定价" = L2 claim. Strong, defensible.
- "X 是当前 regime" = L3 claim. Requires persistence + breadth confirmation.
- "X 正在发生" = L4 claim. **Out of scope for this skill.** Requires data this skill does not have.

L2 → L3 jump requires time + breadth. L3 → L4 jump requires real-economy data
the skill cannot access. Anyone using a Workflow A diagnosis to make economic
forecasts is over-extending the tool.

### When the same L2 pattern can come from multiple layers

Example: "Risk assets ↑ + Gold ↑ + EM ↑ + USD ↓ + Copper ↑" can be produced by:

1. **L1 mechanical:** MOVE collapses → vol-target funds release VaR → mechanical buying of high-beta across the board. No narrative agreement required.
2. **L3 narrative:** Genuine reflation/dollar-weakness consensus forming.
3. **L4 reality:** Actual reflation cycle starting (lagging confirmation).

These are **observationally identical at L2** within a single session. Distinguishing them requires:
- **Time:** does the move persist after the L1 driver (e.g., MOVE) stabilizes?
- **Breadth:** does credit (HYG/IG) confirm equity? do EM bond + EM FX + EM equity all move together, or only equity?
- **Internal consistency:** does the asset that *should* lead the named narrative actually lead it (e.g., for true reflation, cyclicals > growth; for true Fed pivot, 2Y rallies)?

If you cannot run these tests yet (single-day data), say so. Cap the diagnosis
at L2.

### How to write outputs under this framework

Every Regime Diagnosis must report **separate confidence levels for L2 and L3
(and explicitly disclaim L4).** See Schema A in §6.

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
| Sell-America / debasement (P family, v1.0.5) | ↓ | ↓ (yield ↑, bear-steepening; **2Y anchored**) | ↑ (Silver confirms) | — | — (signal-grade ↓ = conflict) | ↓ / low level |
| Multi-constraint | conflicting signals across columns; no single row matches cleanly |

### Sell-America / debasement row (v1.0.5)

Added after this fingerprint recurred without a home (2026-05-07 "P 质变升级",
2026-07-03 P diagnosis) and kept forcing low-confidence patchwork inside the
Policy row. Core read: **the store-of-value properties of the dollar AND long
Treasuries are being discounted simultaneously, with precious metals as the
receiving asset** — fiscal supply / term-premium repricing, not a Fed-path trade.

Fingerprint (asset-class level; ex-ante grouping lives in `data/regime_matrix.json`):
- **USD ↓** — ≥2 of DXY / USDJPY / USDCNY at signal grade
- **Long end sold** — 10Y/30Y yields ↑ (TLT ↓), bear-steepening
- **2Y anchored** — front end silent is *required*, not merely tolerated: a
  signal-grade 2Y move in **either** direction breaks the row (down → relabel
  policy-easing; up → whole-curve selloff, different constraint)
- **Precious ↑** — gold leads, silver confirms
- **Risk assets not required to rally** — neutral is consistent; but a
  signal-grade equity/EM **decline counts as a conflict** (growth-divergence
  guard: USD weak + stocks falling is not benign debasement)
- **Vol ↓ or low** — this row alone may satisfy its vol leg via low absolute
  levels (VIX ≤ 18, MOVE ≤ 75) when daily vol moves are noise; the low-level
  channel does not count toward the ≥4 signal-class threshold

Disambiguation:
- **vs. Policy easing:** easing → long end *rallies* and 2Y *leads lower*;
  debasement → long end *sells off* and 2Y stays anchored.
- **vs. USD funding stress:** funding → USD **up**; debasement → USD **down**.

Confidence: single-day max **★★☆**; ★★★ requires ≥2 consecutive sessions
(same discipline as the whipsaw rule — day-1 of a USD reversal is
observationally identical to positioning mean-reversion).

### How to use the matrix

1. Build the observed direction vector from the frozen mark's computed stats.
2. **Row scoring, the override check, the ≥4-asset-class threshold, and whipsaw
   caps are computed mechanically by `scripts/score_regimes.py`** against the
   machine-readable transcription of this matrix (`data/regime_matrix.json`).
   The analyst adjudicates on top of that output and does not re-count by hand
   (SKILL.md rule 15).
3. The highest-scoring row is the primary diagnosis; the second-highest is the
   alternative.
4. **Critical override:** If USD ↑, gold ↓, bonds ↓, risk ↓ simultaneously →
   score Liquidity/Funding first regardless of other signals. This pattern is the
   most dangerous to misdiagnose because conventional "risk-off" playbooks fail.
5. If no row scores above 60% match (or fewer than 4 asset classes are
   signal-aligned — `schema_d_suggested`), default to Multi-constraint or
   Schema D and say so.

### Disambiguation rules

Some regimes produce similar fingerprints. Use these tiebreakers:

- **Classic risk-off vs. Recession trade:** Check oil. If oil is falling hard,
  it's leaning recession (demand destruction). If oil is flat or up, it's
  generic risk-off without a clear growth signal.
- **Liquidity crunch vs. USD funding stress:** Check gold and EM FX. If gold is
  also being liquidated, it's liquidity (sell everything). If gold holds but EM
  FX collapses, it's USD funding (dollar shortage, not universal deleveraging).
  **BTC as confirmer (not driver):** a signal-grade BTC drawdown *in confluence
  with* MOVE↑ / HYG↓ / EM↓ strengthens the L (liquidity) read — BTC is the
  highest-beta, most leverage-sensitive risk asset, so it tends to break first
  when funding tightens. But BTC moving *alone* (funding proxies quiet) is
  crypto-idiosyncratic (ETF flows, regulation, liquidations) → not a macro
  liquidity signal. BTC does **not** get its own matrix row and never drives the
  call by itself; it adds breadth/confirmation only. See §3 BTC subsection.
- **Inflation trade vs. Geopolitical supply shock:** Check the breadth of
  commodity moves. If oil AND base metals AND ags are all up, it's broad
  inflation. If only oil/shipping/insurance are up, it's geopolitical supply.
- **Policy easing vs. Recession trade:** Check risk assets. If equities rally on
  rate-cut expectations, it's policy easing. If equities fall despite rate-cut
  pricing, the market believes easing won't be enough — that's recession.

### Caveat: the matrix is a historical induction, not a complete enumeration

The fingerprints in §2 are inductive summaries of past regimes. New compositions
of the global economy (AI capex cycles, fiscal-dominance environments, reserve
diversification flows, external USD supply dynamics) can produce real regimes
whose fingerprints **don't appear in this matrix**. When an asset that "should"
move under a candidate regime stays silent, ask in this order:

1. **Has the regime's anchor migrated?** e.g., if Fed reaction function has
   decoupled from the trade, UST 2Y can stay flat while everything else moves.
   Front-end silence in such a world is consistent, not contradictory.
2. **Is the regime composition new?** AI-capex-driven reflation looks different
   from old-economy industrial reflation: growth > value, megacap > small cap,
   credit lukewarm. Don't reflexively label this "duration squeeze" or "not
   real reflation"; it may be real reflation with a different sectoral signature.
3. **Only after (1) and (2):** is the regime not real?

Using yesterday's necessary conditions as today's filters is meta-F4 (see §4).
The matrix decays; check whether it has before invalidating signals.

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
- **L2 confidence ≠ L3 confidence.** Five aligned asset classes give you ★★★ on
  pricing alignment (L2). They do **not** give you ★★★ on regime/narrative (L3)
  unless persistence and breadth tests are also passed. Report the two
  separately in Schema A.

### Volatility-percentile noise gate (v1.0.4)

When the data comes from the frozen-snapshot path (SKILL.md step 1b), each asset
carries `move_vol_pct` (today's |move| as a percentile of its trailing
distribution) and `consec_same_dir` (signed run-length of same-direction days).
Use them to separate signal from noise **with statistics, not narrative
instinct** — this is the structural fix for the most common authoring error
(over-reading a single trivial daily move into a regime story):

- **`move_vol_pct` < 50** → the move is below its own median; treat as NOISE.
  It may be cited as "within range" but must NOT anchor a regime argument or a
  confidence change. (Example failure: a +0.13% DXY day at the 7th percentile is
  not "dollar strength resuming.")
- **`move_vol_pct` ≥ 80** → an unusually large move; this IS signal worth a
  mechanism, even if a single day.
- **Multi-day trend claims** ("second leg", "stalling", "X days of") require
  `consec_same_dir` ≥ 2 (or ≤ −2) **or** a material `Nd_change`. Never assert a
  trend from direction arrows alone — arrows are single-day and memoryless.
- When stats are unavailable (live-fetch fallback, step 1c), you have no
  percentile context: explicitly downgrade all trend/noise language and say the
  judgment is provisional.

This gate operates at the evidence layer, upstream of confidence — it removes
noise-based evidence before L2/L3 scoring, rather than discounting it after.

### Confidence whipsaw protection (v1.0.3)

Confidence may **not** jump ≥2 levels in opposite direction within 24 hours.

Examples of forbidden moves:
- Yesterday ★★☆ regime X → today ★★★ regime ¬X. Forbidden by construction.
- Yesterday ★★★ regime X → today ★★★ regime ¬X. Forbidden.

Allowed moves on a same-direction reversal:
- Yesterday ★★☆ regime X → today ★★☆ regime ¬X (single-level downgrade matched by single-level new direction). Allowed.
- Reaching ★★★ on the new direction requires **≥2 consecutive sessions** of confirmation.

**Justification:** A 1-day reversal immediately followed by max-confidence call on the opposite direction is observationally indistinguishable from noise + over-fitting. The cross-asset alignment may look clean today, but you cannot tell whether it's a real regime flip or a single-day mean reversion until the move persists. The cost of cap-at-★★☆ on day-1 of reversal is small (mild understatement); the cost of ★★★ on day-1 of a noise-driven reversal is large (max-confidence whipsaw call destroys the diagnostic record).

**This rule overrides the matrix-match-count basis for ★★★ in §3 above.** Even if 5+ assets align with the new direction on day-1 of reversal, max confidence allowed is ★★☆.

**What counts as "¬X" — regime_row semantics (v1.0.5):** reversal comparison is
by **matrix row key** (`regime_row`, recorded per diagnosis in
`data/diagnosis_log.jsonl`), not by constraint code. Rows with opposite
fingerprints inside the same constraint family — `policy_easing_trade`
(long end rallies, 2Y leads lower) vs. `sell_america_debasement` (long end
sells off, 2Y anchored) both carry code P — **are reversals of each other** and
trigger the cap like any other flip. The cap is enforced mechanically by
`scripts/score_regimes.py` (reads the ledger's most recent entry within 3
sessions); the analyst may tighten it further but never loosen it silently.

### MOVE as flow-regime indicator (Layer 1 proxy)

MOVE is the bond-volatility analog of VIX. Its single-day moves carry
mechanical implications that are independent of any macro narrative:

| MOVE behavior | What it means at Layer 1 |
|---------------|--------------------------|
| Sharp drop (≥ -5% / day) | Vol-target / risk-parity / CTA funds release VaR budget → **mechanical re-leveraging into beta** (equities, EM, commodities, recently-shorted names) |
| Sharp jump (≥ +10% / day) | Bond convexity hedging cascades, dealer balance sheet stress, mechanical de-risking |
| Sustained low (< 75) | Vol-target funds operate at full leverage; supports broad risk asset bid |
| Sustained high (> 110) | Vol-target funds operate at reduced leverage; chronic headwind for risk |

**Operating rule:** When MOVE drops sharply *on the same day* that risk assets
rally broadly across high-beta names (EM, Copper, Silver, Nasdaq, junk credit,
recently-oversold sectors), **weight the L1 mechanical explanation before the
L3 narrative explanation.** The same L2 pattern is produced by either, and you
cannot distinguish them within one session.

Test for distinguishing: does the rally hold *after* MOVE stabilizes (no longer
falling)? If yes, real flow/narrative is sustaining it. If the rally stalls
when MOVE flattens, it was vol-budget mechanics — not regime.

This is the most important update to add to your reading: MOVE is no longer
just a "bond market trust" indicator. It is the cleanest L1 proxy you have.

**Data-freshness precondition (v1.0.6, source-audit finding):** the ^MOVE
series on Yahoo lags erratically — measured lag distribution {same-day: 3,
6-sessions: 1}. "Same day" in this rule means the asset's `as_of` equals the
mark's data date, verified, not assumed. A lagged MOVE reading may still be
cited as prior-session context but cannot trigger the same-day L1 rule, and a
MOVE-quiet day with stale as_of is *unknown*, not *calm*. The same applies to
^TNX/^TYX (t-1 on ~half of capture days) — TLT is the always-same-day long-end
instrument. Per-source details: `data/SOURCES.md`.

### BTC as a liquidity / risk-appetite proxy (24/7, high-beta)

BTC is included as a **marginal-liquidity / risk-appetite proxy** (L1 flow / L2
pricing). Its appeal — no cash-flow anchor, maximum leverage sensitivity, 24/7 —
is also its hazard: it is reflexive and fat-tailed, so a raw daily % move looks
alarming next to DXY or HYG and invites over-reading. Three disciplines keep it
useful without being spooked:

1. **Read it through the percentile gate, not the raw %.** `move_vol_pct`
   normalizes today's move against BTC's *own* trailing distribution, so BTC's
   high baseline volatility is already neutralized — you compare percentile
   ranks, never raw percentages. **Use a higher signal bar for BTC: treat only
   `move_vol_pct ≥ 65` as signal-grade** (vs the ≥50 default for other assets),
   because BTC's fat tails mean even percentile-normalized daily moves are noisy.
   Below 65 → cite as "within range," never anchor a read on it.
2. **Read the liquidity stance off the trend, not the tick.** Liquidity regimes
   are slow; a single red BTC candle is not a liquidity event. Require
   `consec_same_dir ≥ 2` (or ≤ −2) or a material `Nd_change` before any
   BTC-based persistence claim. (Example: a −4.5% day at vol 91 with consec −10
   *is* a sustained drawdown worth weighing; an isolated −4.5% at vol 40 is not.)
3. **Confluence-only — BTC never counts alone.** BTC contributes to the **L
   (liquidity)** / **F (USD funding)** read *only* when it agrees with ≥1–2 of
   the established funding proxies (MOVE, HYG, DXY, EM_ETF). BTC moving while
   those stay quiet = crypto-idiosyncratic (ETF flows, regulation, exchange
   liquidations) → log as noise, do not promote to a macro liquidity signal.

**Scope guard:** BTC is a *confirmer*, not a constraint. It has no row in the §2
matrix, does **not** count toward the "≥4 asset classes aligned" threshold that
gates a regime call, and never drives a diagnosis by itself. It adds breadth to
a liquidity/risk read that the other proxies already support. (This is Critical
Rule 2 — no single-asset conclusions — applied to BTC; see F13.)

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
| F8 | Layer conflation | Did I use L4 language ("X 正在发生") for an L2 observation, or claim L3 confidence from a single day's L2 alignment? See §0. |
| F9 | Necessary-condition lock-in (meta-F4) | Did I invalidate today's signal using yesterday's necessary conditions? When a previously-anchoring asset goes silent, did I first ask "anchor migrated?" before "regime not real"? See §2 caveat. |
| F10 | Flow-blindness | Did MOVE drop ≥ -5% on the same day risk assets ripped, while I attributed the move to narrative/regime without explicitly weighing vol-budget release? See §3 MOVE section. |
| F11 | Phase-language without ex-ante anchor | Did I introduce state-change terms ("阶段切换", "承接测试", "裁决窗口", "质变升级") without referencing (a) a phase defined in this protocol or (b) a numerical threshold pre-defined in a prior session's falsification list? If so, replace with descriptive language ("price has crossed X" / "asset has moved beyond Y%") rather than coining new state names. |
| F12 | Hand-wave trigger | Did I claim a trigger / catalyst / 触发器 without naming the specific news event or asset move? Statements like "无论具体事件是什么", "某种催化剂", "未指明的冲击" are forbidden. If you cannot name the source, rewrite as "price has moved X, cause unknown" — do not assert the existence of a trigger you cannot identify. |
| F13 | BTC-solo as liquidity | Did I read a BTC move as a liquidity/risk signal without confluence? A BTC move counts only if `move_vol_pct ≥ 65` AND ≥1–2 funding proxies (MOVE/HYG/DXY/EM) agree. BTC alone = crypto-idiosyncratic noise; it has no §2 row and does not count toward the ≥4-asset regime threshold. See §3 BTC subsection. |

Before outputting, run through F1-F13 as a checklist. If any fails, fix the
output.

The most pernicious of these is F8. The word "regime" naturally flows between
layers and a reader cannot distinguish without explicit tagging. **Default to
L2 language; promote to L3 only with persistence; never promote to L4.**

**F11 and F12 share a common root**: both are forms of "narrating beyond the
evidence." F11 invents states the market has not declared; F12 asserts
causation without naming the source. When in doubt on either, prefer
descriptive language over coined terminology.

---

## §5 Output Schemas

All outputs are in Chinese by default. Section headers are fixed; content under
each header adapts to the specific situation.

### Schema A: Regime Diagnosis（v1.1.0：读者正文 + 审计附录两层结构）

报告不只是模型调试产物，而是给中文母语、非交易员背景读者的每日诊断。读者正文
回答四件事：今天的价格组合最像什么？这是价格事实还是原因推断？什么支持、什么
未知？下一个交易日什么观察会改变判断？机械打分、字段名、数据异常、运行状态
**完整保留但全部进「审计附录」**，不得抢占正文。

#### 表达状态（写作状态，不是新的评分行，不写入 regime_matrix.json）

| 状态 | 条件 | 正文必须怎么写 | 正文禁止怎么写 |
|------|------|----------------|----------------|
| `D_ABSTAIN` | 命中 Schema D 规则 | 「今天不判断主导原因」+ 纯价格事实 + 何时重评 | 机制、交易建议、「主导约束是 X」 |
| `A_PRICING_ONLY` | L2 ≥ ★★☆ 但 L3 = ★☆☆；或存在观测等价的备选原因 | 「最佳匹配的价格模式是 X，**原因未确认**」 | 「X 接过定价权」「X 已坐实」「真 X 定价」等确立性语言 |
| `A_NARRATIVE_SUPPORTED` | L3 ≥ ★★☆（持续性/广度具备，备选原因已有区分证据） | 允许「当前更支持 X 作为主要解释」，仍须给出证伪 | 任何 L4 断言或无来源因果 |

头部「主导约束」字段保留（归档习惯），但 `A_PRICING_ONLY` 时必须写成：
`**主导约束：** 原因未确认（L2 最佳匹配：X — 行名）`。
文件名、ledger 的 regime/regime_row、thresholds sidecar 继续按机器判断写入，
不因读者措辞改变。

#### 输出结构（标题文字固定，lint 依赖，顺序不得调换）

```
## 今日结论

- **最佳匹配的价格模式：** ...
- **原因判断：** 已获得支持 / 未确认 / 两种解释暂不可分
- **确定性：** 价格层 ... / 原因层 ...

[2–4 个短句说清价格事实、最佳匹配与主要不确定性。]

## 与上一个交易日相比

- [最多 3 条，只写真正改变判断的增量]

## 核心证据

| 观察 | 当日事实 | 对判断的影响 |
|---|---|---|
| ... | ... | 支持 / 反对 / 暂无区分力 |

[最多 5 行，只放承重证据。]

## 当前不能确定的事

- [1–3 条，明确是数据缺失、原因无法区分，还是现实层无数据]

## 下一个确认点

- [最多 3 条：具体变量 + 方向/阈值 + 改变什么判断]

## 审计附录

### 数据口径与运行状态
[fetched_at、数据日、滞后/断档/降级、运行故障（补发/进程/看门狗等只许出现在这里）]

### 机械打分与人工判断
[best row、match%、aligned/conflicted、Schema 建议、偏离理由；机器字段名首现须带中文语义]

### 完整证据表
[全量资产、波动分位、连续方向、as_of、支持/冲突/不作证据]

### 原因候选与区分证据
[对各候选原因分别说明：已有什么证据、缺什么、是否可区分]

### 证伪条件
[与 thresholds sidecar 逐条对齐]

### 待确认问题
[对应 open_threads，用「待确认/已回答/顺延/过期」，不用「悬案/立案/收案」]

### 术语说明
[只放本日实际用到的 3–6 项]
```

#### 正文长度硬限制

- 「审计附录」之前的读者正文 ≤ **1500 个中文字符**；
- 「核心证据」最多 5 行；「与上一个交易日相比」「下一个确认点」各最多 3 条；
- 审计附录不设硬限制，但不得整段重复正文。

#### 因果表达门（v1.1.0，适用于读者正文与附录的分析文字）

价格同时波动只能证明「组合形状与某矩阵行一致」，不能单独证明因果。只有下列
任一证据存在时，「原因判断」才允许明确因果语言：

1. 已指名的具体新闻/政策/事件，且时序与价格反应相符；
2. 协议已定义的 L1 机械阈值被**当日新鲜数据**命中，且补充证据同向；
3. 资金市场官方数据给出直接证据（如 SRF 非零、SOFR−IORB 持续为正）；
4. 利率分解数据明确指向实际利率或通胀补偿；
5. 用户提供了可验证的因果证据。

不满足时只允许：「与 X 价格模式一致」「最接近 X」「同时出现」「两种解释在
当日数据上不可分」「原因未确认」。

**利率归因硬门**：`rates_attribution` 缺位/滞后/不可用时——只能写「名义利率
上升/下降，来源未分解」；禁止写「实际利率上行/回落」「油价推动了利率变动」
「通胀燃料被移走」「实际利率挤压松开」等等价拟人化因果。附录可原样展示数据
字段，但不得用它们支持数据没有给出的归因。

**MOVE 表达边界**：MOVE 命中协议阈值时可写「程序化资金减仓/加仓的可能性上升」；
不得仅凭 MOVE 断言「某类基金已被迫买卖某资产」——本系统没有持仓与成交流数据。
「MOVE 是机械减仓链条的驱动源」类表述必须改为「MOVE 上升与程序化减仓风险一致，
但本系统不直接观察基金持仓」。

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

### Schema D: Abstention (不诊断声明) — v1.0.3

Schema D is a **first-class output form**, not a downgraded Schema A. It exists to give the analyst a concrete way to refuse causal narrative when conditions don't support one. The cost of using Schema D should be zero; the burden of proof is on Schema A.

**Use Schema D instead of Schema A when ANY of these holds:**

1. **L2 confidence < ★★☆** — assets do not even align cleanly at the pricing layer
2. **Confidence-whipsaw context** — within the last 3 sessions there was a regime reversal of ≥2 confidence levels in opposite direction (see §3 whipsaw rule). Stay in Schema D until ≥2 consecutive sessions of same-direction confirmation accumulate
3. **Patchwork escalation** — diagnosing the asset vector requires ≥4 separate narrative elements or new explanatory hypotheses (protocol-defined exceptions like F10 do not count toward this threshold; "new" means not in the prior session's framework)
4. **F11 or F12 unfixable** — diagnosis cannot be written without phase-language hand-waving or unnamed-trigger attribution

**Format（v1.1.0 中文化：分析逻辑不变，只改表达）:**

```
## 不诊断声明 (Schema D)

- **观测窗口：** [实际可用观测] vs [所需最低，按 §3 regime 默认值]
- **为什么今天不判断原因：** L2 / L3 哪几层无法做判断（用中文说清，不用字段名）
- **触发条件：** [从上面 4 条里挑被命中的，引用具体证据]
- **盘面纯描述：** [纯方向矢量，无因果框架，无 regime 标签]

| 资产 | 当日变动 | 备注（仅事实：显著波动 / 波动过小 / 数据滞后） |
|------|------|-----------------------|
| ...  | ...  | ...                    |

- **何时重评：** [ex-ante 的可观测阈值——什么观察会让不判断状态结束]

### 技术说明（可选，置于末尾）
[机械打分等机器字段如必须披露，集中放这一短段，不得穿插进读者说明。]
```

正文用「显著波动/波动过小/数据滞后」，不用 `signal/vol/stale` 等字段名；
运行事故（补发、进程故障等）只写对判断的影响（如「部分商品数据暂不可用，
今日不对商品方向作结论」），过程细节不进正文。

**Schema D 必须比 Schema A 短**——拒绝叙事就是它的意义。**禁止包含**：
- 机制段（不解释传导）
- 证伪条件（已经在 abstain 状态，无需为不存在的判断设证伪）
- 观察清单（拒绝把"想看什么"打包成 actionable signals）
- "一句话总结"叙事

只有：方向矢量 + 拒绝理由 + 何时重评。

**Schema D 不是失败模式，是正确响应**。一周里有 2-3 天输出 Schema D 是健康的——市场大部分时间不在清晰 regime 里。

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
