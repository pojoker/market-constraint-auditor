# 工单 7 — 期货幽灵 bar：检测 + Wind 仲裁 + 次日自愈 + 影子探测 + 悬案工具强化（Round 7）

> 背景：2026-07-06（周一）21:45 UTC 捕获踩中 CME 维护时段（17-18 ET），Yahoo 把
> 07-03 的旧 bar 盖上"07-06"的章原样发回（Gold last/change 与 07-03 一字不差）。
> Wind 官方结算价已定罪：当日金实跌（4187.3→4167.5）。Round 6 的去重机制事后
> 正确隔离了它，但代价是次日全部 6 期货 vol 分位失明一天（20260707 mark 实况）。
> 本工单把"盲隔离"升级为"当场审判 + 次日自愈"，并附带跨日悬案工具强化。

## 边界（违反任何一条 = 全单拒收）

- **只动这些文件**：`scripts/capture_snapshot.py`、`scripts/wind_arbiter.py`（新）、
  `scripts/shadow_probe.py`（新）、`scripts/threads_tool.py`（强化现有最小版）
  + `CHANGES.md`（追加「Round 7 (ghost bar + wind arbitration)」验收记录）。
- **不碰协议三件套**（SKILL.md / market-constraint-protocol.md / DRAFT-NOTES）。
- **不 commit**。
- 测试一律用 `/Users/jowang/miniconda3/bin/python3`。
- **沙箱无网**：Wind 桥与 yfinance 全部 mock（monkeypatch subprocess / 注入假数据），
  实网验证归验收方。
- **data/ 测试期只读**：`timeseries.jsonl`、`diagnosis_log.jsonl`、`open_threads.jsonl`
  的 sha256 测试前后必须一致（合成数据放 tmp 目录）。不跑真实 capture。

## 改动 1 — 幽灵签名检测（capture_snapshot.py）

判定规则（写死）：某期货资产（Gold/Silver/Copper/Brent/WTI/NatGas）的新条目是
"幽灵嫌疑"，当且仅当：① 当日 SP500 有新 bar（as_of 前进 = 真交易日）；② 该资产
新条目的 `(last, change)` 与时间序列该资产**上一行**完全相等。命中 → 该资产条目
加 `"ghost_suspect": true`（snapshot 与 timeseries 行同步）。**只标记，不改值**
——真实的完美平盘日（change=0 但 last 前进）不会命中，两值同时冻结才算。

## 改动 2 — Wind 官方结算仲裁（scripts/wind_arbiter.py，新）

被 capture_snapshot 在发现 ghost_suspect 后 best-effort 调用（桥失败/超时 30s
→ 不阻塞捕获）。职责：查官方口径"当日到底动没动"。

- 调用方式（已实测可用，照抄）：
  ```
  /Users/jowang/.nvm/versions/node/v22.22.3/bin/node \
    ~/.agents/skills/wind-mcp-skill/scripts/cli.mjs \
    call economic_data natural_language_get_edb_data \
    '{"executionMode":"fetch","question":"<EDB代码>","beginDate":"<5天前>","endDate":"<今日>"}'
  ```
  **cwd 必须设为 `~/.agents/skills/wind-mcp-skill`**；node 用上面的绝对路径
  （launchd 环境 PATH 无 node，有前科）。返回 envelope 结构：外层 JSON 的
  `content[0].text` 是 JSON 字符串，内层 `data.data[i]` 含 `meta.code` 与
  `date[]`/`value[]` 两个平行数组；失败 envelope 有 `error.code`（SERVER_5XX/
  NETWORK_ERROR/RATE_LIMIT_QPS 可重试一次，间隔 3s）。
- EDB 代码表（全部已于 2026-07-08 实测验证，见 data/SOURCES.md 仲裁源一节）：
  Gold `S0180945`｜Silver `S0180964`｜Copper `S0180946`｜WTI `S0180938`｜
  Brent `S0031525`｜NatGas `S0069682`（⚠️此条口径是"收盘价(连续)"非结算价）。
- 裁决逻辑：取官方序列最近两个值。官方 |变动| > 0.05% 而我方 bar 冻结
  → `"ghost_verdict":"confirmed"`；官方也几乎没动（≤0.05%）→ `"acquitted"`；
  桥不可用/该日无数据 → `"unavailable"`。写进该资产条目，并附
  `"official_ref": {"code":…, "prev":…, "last":…, "source":"wind-edb"}`。
- **严禁把 Wind 数值写回 last/change**——结算窗口（金属 13:30 ET/能源 14:30 ET）
  ≠ 本系统 Globex 收盘窗口（17:00 ET），只判方向真伪，不替换价格。

## 改动 3 — 次日自愈回填（capture_snapshot.py）

每次捕获本就下载 5 天窗口。对 6 期货：若时间序列**昨行**（最近一个先前行）的
`last` 与今日下载窗口中同日期 bar 的 close 相差 > 0.01% → 用下载值改写昨行
（last 与 change 一致重算），加 `"retro_corrected": true`，原值存
`"pre_correction": {"last":…, "change":…}`，并向 `data/corrections.log` 追加
一行（UTC 时间戳、资产、日期、旧值→新值）。约束：只回看最近 1 个交易日；
只动期货 6 资产；已 `retro_corrected` 的行不再二次改写（幂等）；快照文件同步。

## 改动 4 — 影子探测（scripts/shadow_probe.py，新）

独立脚本，无参数：对 8 资产（6 期货 + DXY + USDJPY）用 yfinance 重拉当日 bar，
与最新 snapshot 中该资产 `(last, change)` 对比，差异 > 0.01% 记 `CHANGED` 否则
`SAME`，向 `data/shadow_probe.log` 追加一行 JSON：`{ts, date, verdicts:{资产:…}}`。
用途：回答"05:45 的 bar 在 06:37 时是否已被上游修正"（一周后人工评估，决定
要不要加 06:20 复核步）。接线进 wrapper 归验收方，不在本单。

## 改动 5 — threads_tool.py 强化

现有最小版（--list / --expire-check）之上补齐：
- `--add --question … --resolve-condition … --expires YYYYMMDD`（id 自动生成
  `YYYYMMDD-slug`，slug 取 question 前几个词的拼音/英文摘要或随机后缀）；
- `--resolve <id> --resolution "…"`（置 resolved + resolved_on=今日）；
- 全操作前 schema 校验：必填字段齐全、日期格式 YYYYMMDD、status ∈
  {open,resolved,expired}；坏行明确报错退出码 2，不静默跳过；
- `--list` 保持现有输出形态（人读表格 + `--- json ---` 机读段）。

## 验收（贴 CHANGES.md，逐项附实测输出）

1. **幽灵检测合成测试**：a) 交易日+双值冻结 → ghost_suspect=true；b) 完美平盘
   （change=0 但 last 前进）→ 不标；c) 非交易日（SP500 无新 bar）→ 不标。
2. **仲裁 mock 三态**：官方有变动→confirmed；官方同冻→acquitted；桥超时/异常
   →unavailable 且捕获流程不中断。
3. **自愈合成测试**：昨行错值+今日窗口正确值 → 回填+pre_correction+corrections.log
   一行；连跑两次第二次零改写（幂等）。
4. **shadow_probe**：mock yfinance 跑通，输出行格式符合规格。
5. **threads_tool**：add/resolve/expire 全链路 + 坏 schema 拒绝（退出码 2）。
6. `py_compile` 全部触及文件；data/ 三文件 sha256 前后一致；不 commit。
