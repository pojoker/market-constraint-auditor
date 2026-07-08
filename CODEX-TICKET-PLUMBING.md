# 工单 8 — 管道数量层（plumbing）接入：净流动性 + 融资压力判别官（Round 8）

> 背景：本系统的 L/F 诊断全靠价格倒推（L2），没有"量"的维度。2026-07-08 与
> dollarliquidity.com 对照后确认结构性盲区：净流动性（Fed 资产负债表−TGA−逆回购）、
> SOFR-IORB 融资利差、SRF 使用量——这些是 L/F 的**直读判别官**（20260708 报告的
> L/F 悬案若有 SOFR-IORB 当天即可裁决）。数据源体检已完成（见 data/SOURCES.md
> 即将登记 + CHANGES.md Round 8）：SOFR/ONRRP 走 NYFed 官方 API（实测直证），
> IORB/WTREGEN/WALCL 走 FRED fredgraph.csv（生产夜窗已证；**白天从本网络超时**，
> 故拉取必须跑在 05:45 夜窗）。角色定位：**量不进价格矩阵**——不参与 match% 计数，
> 只作判别官/语境（协议侧接线 v1.0.9 归验收方）。

## 边界（违反任何一条 = 全单拒收）

- **只动这些文件**：`scripts/fetch_plumbing.py`（新）、`scripts/load_for_analysis.py`
  （仅加 plumbing 输出块）+ `CHANGES.md`（追加「Round 8 (plumbing)」验收记录）。
- 不碰协议三件套（SKILL.md / market-constraint-protocol.md / DRAFT-NOTES）。
- 不 git commit。测试用 `/Users/jowang/miniconda3/bin/python3`。
- **沙箱无网**：NYFed / FRED 请求全部 mock；实网验证归验收方（夜窗）。
- **data/ 现有文件只读**：timeseries.jsonl / diagnosis_log.jsonl / open_threads.jsonl
  sha256 测试前后一致；测试产物一律写 tmp（含合成的 plumbing 文件）。

## 改动 1 — scripts/fetch_plumbing.py（新）

每日拉 6 序列，upsert 进 `data/plumbing.jsonl`（每数据日一行，重跑覆盖同日行）。

**源与序列（全部已体检，照抄）：**

| 键 | 源 | 端点/ID | 语义 | 单位 | 更新 |
|---|---|---|---|---|---|
| `SOFR` | NYFed API | `https://markets.newyorkfed.org/api/rates/secured/sofr/last/5.json` → `refRates[].effectiveDate/percentRate` | 担保隔夜融资利率 | % | t+1 晨 |
| `ONRRP` | NYFed API | `https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate=<10天前>` → `repo.operations[].operationDate/totalAmtAccepted`（换算 $bn）| 隔夜逆回购用量（缓冲池）| $bn | 当日 13:15 ET |
| `SRF` | NYFed API | 同上 rp 端点族，正回购方向：`/api/rp/repo/propositions/search.json?startDate=…` 同字段 | 常备回购便利使用量（银行敲窗=融资告急）| $bn | 当日 |
| `IORB` | FRED | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=IORB&cosd=<30天前>` | 准备金利率（政策阶梯）| % | 日频 |
| `TGA` | FRED | 同上 `id=WTREGEN` | 财政部一般账户 | $bn | 周三周频 |
| `WALCL` | FRED | 同上 `id=WALCL` | 美联储总资产 | $mn | 周三周频 |

**要求：**
- requests，timeout 20s，每源重试 2 次（间隔 2^i s），UA header `Mozilla/5.0`。
- **全程 best-effort**：单源失败 → 该键 `{"value": null, "error": "<简述>"}`，其余照常，
  进程 rc=0（有任何成功值）/ rc=1（全灭）。
- 每键结构：`{"value": …, "as_of": "YYYY-MM-DD", "unit": …, "source": "nyfed-api"|"fred:<ID>"}`。
- **派生字段 `derived`**：
  - `sofr_iorb_spread_bp`：仅当 SOFR 与 IORB 存在**同一 as_of 日**的值才计算
    （(SOFR−IORB)×100，保留 1 位）；对不齐 → null + 注明两侧 as_of。
  - `net_liquidity_bn`：WALCL/1000 − TGA − ONRRP，各取最近可用值；结果附
    `components_as_of` 三元组——**混频近似，as_of 必须全披露**。
- 行结构：`{"date": "YYYYMMDD"(当日UTC), "fetched_at": iso, "series": {…}, "derived": {…}}`。
- `--backfill N`（如 `--backfill 730`）：FRED 三序列拉全历史窗（cosd=N天前）+
  NYFed SOFR 用 `/api/rates/secured/sofr/search.json?startDate=…`、ONRRP/SRF 用
  search 端点同参——逐**数据日**构行回填（值缺的键置 null），幂等 upsert。
  沙箱只写逻辑+mock 测试，实跑归验收方。

## 改动 2 — scripts/load_for_analysis.py

输出顶层加 `"plumbing"` 块：取 `data/plumbing.jsonl` 最新行，附每键 as_of 与
`lag_days`（相对 mark 数据日）；文件不存在/空 → `"plumbing": null`。
不改动现有任何字段与行为（现有消费者零感知）。

## 验收（贴 CHANGES.md「Round 8 (plumbing)」，逐项实测输出）

1. mock 三源正常 → plumbing.jsonl 行 schema 逐键正确（value/as_of/unit/source）。
2. mock 单源故障（NYFed 通、FRED 挂）→ 对应键 null+error，其余正常，rc=0；全灭 rc=1。
3. 派生合成测试：SOFR/IORB 同日对齐 → spread 正确；错日 → null+双 as_of 披露；
   净流动性混频计算 + components_as_of 三元组。
4. `--backfill` mock：构造 30 天假历史 → 行数正确、重跑幂等（第二次零变更）。
5. load_for_analysis：有 plumbing 文件 / 无文件两态输出正确，现有字段回归不变
   （对同一快照新旧输出 diff 仅新增 plumbing 键）。
6. py_compile；data/ 三受保护文件 sha256 前后一致；不 commit。

**验收方后续（不在本单）**：夜窗实网三日对账（IORB/TGA vs FRED，SOFR/ONRRP vs
NYFed，WALCL vs Wind G1100075）→ SOURCES.md 登记；capture wrapper 接线（步骤 3.5
调 fetch_plumbing）；`--backfill 730` 实跑；协议侧 v1.0.9（L/F 判别接线）。
