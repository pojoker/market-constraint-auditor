# 工单包① — 外行设计遗留清偿（Backlog Round 3）

> 交接说明：本文档是完整任务规格，含 4 个互不依赖的工单（#1 假日守卫 / #3 备份接线 / #5 报告 lint / #6 sector-scan 数据验证）。照规格实现，**不自行发明口径**。改完不 commit，在 `CHANGES.md` 追加「Round 3 (Backlog-1)」章节，逐项贴验收实测输出。

## 边界（硬约束）

- **只改脚本与数据文件**。禁碰：`~/.claude/skills/market-constraint-auditor/` 下的 SKILL.md / references/market-constraint-protocol.md / V1.0.3-DRAFT-NOTES.md；sector-scan 的 SKILL.md / references。
- **sector-scan 只改 repo 源**：`/Volumes/移动硬盘/sector-scan-skill/skills/sector-scan/scripts/`，**禁改安装目录** `~/.claude/skills/sector-scan/`（用户会跑 deploy.sh 同步）。
- **不 commit**（两个 repo 都不要）。
- **禁跑真实 capture / 真实全量扫描去污染数据**：测试用合成快照、`--date` 历史日、或临时目录。market-auditor 的 `data/snapshots/`、`timeseries.jsonl`、`diagnosis_log.jsonl` 一个字节都不许被测试改动（只读引用可以）。
- 测试一律用 `/Users/jowang/miniconda3/bin/python3`（market-auditor 侧）；sector-scan 脚本用系统 `python3`（其现有运行方式）。

## 环境事实

- market-auditor 项目根：`/Volumes/移动硬盘/market-constraint-auditor`（下称 `$MA`）
- sector-scan repo：`/Volumes/移动硬盘/sector-scan-skill`（下称 `$SS`），脚本在 `$SS/skills/sector-scan/scripts/`
- 每日链路 wrapper（可改）：`~/bin/market-auditor-capture.sh`（05:45）与 `~/bin/market-auditor-diagnose.sh`（06:37）
- 快照新格式每资产带 `as_of`/`source`/`session_kind`/`stale`；**旧快照（2026-07-03 之前）没有这些字段，一切读取逻辑必须容忍缺失**
- `_capture` 元数据同样存在 legacy 缺失问题（更旧的连 `_capture` 都没有）
- sector-scan 的行情源是腾讯财经（`web.ifzq.gtimg.cn/appstock/app/fqkline/get`），已知结构陷阱：个股除权日行会多出第 7 个元素（分红 dict），当前代码用 `row[:6]` 截断

---

## 工单 1：假日/半日盘守卫（partial_session）

**问题**：2026-07-03 美股假日产生"股指冻结在 07-02、商品半日盘在动"的杂交 mark（Gold +1.81% as_of 07-03 vs SP500 as_of 07-02），当时是防重复门碰巧拦住的。若某假日 mark 日期新于账本日期，自动诊断会跑在半日盘数据上。

**改法**：
1. `$MA/scripts/capture_snapshot.py`：写快照前计算——取股指锚 `SP500` 的 `as_of` 与全体带 `as_of` 资产的最大 `as_of` 比较；股指落后 ⇒ `_capture["partial_session"] = true`，否则 `false`。任一侧 `as_of` 缺失（legacy/错误日）⇒ `false` 并 log WARN。log 行加 `partial=` 字段。
2. `$MA/scripts/load_for_analysis.py`：`mark_quality()` 增加第三枚举 `partial_session`（优先级：`intraday_stale` > `partial_session` > `us_close`；即两者同现取 intraday_stale）。summary 头部照常透出。
3. `~/bin/market-auditor-diagnose.sh` 的 GATE python 块：`_capture.partial_session == true` ⇒ 输出 `SKIP partial session (<date_key>)` 退出。
4. `$MA/scripts/check_thresholds.py`：不跳过 partial mark（价格穿越仍是信息），但输出 JSON 顶层加 `mark_quality` 字段，且 ALERT 行在 partial mark 上追加后缀 `[partial-session mark]`。

**验收**：
- 合成快照 A（SP500 as_of=07-02、Gold as_of=07-03）写到**临时目录**（复制 load/compute 所需最小结构或 monkeypatch 路径）→ capture 逻辑单测得 `partial_session=true`；diagnose gate 对该合成输入输出 `SKIP partial`。
- 真实 20260702 mark → `partial_session=false`、gate 行为不变（仍是 already-diagnosed SKIP）。
- 真实 20260703 mark（半日盘那份）→ 用只读脚本验证检测函数判定为 partial（不回写文件）。

---

## 工单 3（codex 半）：备份接线

**问题**：代码+153 天数据+79 份报告只存在于一块移动硬盘。git 远端由用户另行创建（不归本工单）；本工单只做**本机镜像 + best-effort push 接线**。

**改法**：`~/bin/market-auditor-capture.sh` 追加第 5 步（在 threshold-check 之后）：
1. `mkdir -p ~/Backups/market-auditor` 后 `rsync -a --delete "$REPO/data/" ~/Backups/market-auditor/data/` 与 `rsync -a "$REPO/reports/" ~/Backups/market-auditor/reports/`（reports **不带** `--delete`，历史报告只增不删）。
2. `git -C "$REPO" push --quiet 2>/dev/null`——仅当 `git remote` 非空才尝试；无远端静默跳过。
3. **隔离性硬要求**（与既有第 4 步同标准）：备份/push 任何失败只 log `WARN backup ...`，不得改变 wrapper 退出码。

**验收**：手动跑 wrapper（--注意：这会触发一次真实 capture——**改为单独把第 5 步抽成可独测的函数/子脚本**，用 `bash -c` 直接调它验证），确认 `~/Backups/market-auditor/` 结构完整、与源 diff 一致；断网/无远端时 push 静默、rc 不变。

---

## 工单 5：报告 lint（协议的机器护栏）

**问题**：v1.0.5 协议规定每份 Schema A 必须带 `.thresholds.json` sidecar、A/D 都要追加 diagnosis_log、正文须引用机械打分——但执行者是 LLM，没有机器核查这些规定等于不存在。

**改法**：新建 `$MA/scripts/report_lint.py`：
- 输入：`--report <md路径>`，缺省取 `$MA/reports/` 里 mtime 最新的 `.md`。
- 从文件名解析 schema 类型（含 `约束诊断` = Schema A；`不诊断` = Schema D）。
- **Schema A 检查**：①同名 `.thresholds.json` 存在且能通过 `data/thresholds.schema.json` 的字段校验（必填字段齐全、op/metric 枚举合法）；②`data/diagnosis_log.jsonl` 存在该报告日条目，且其 `regime_row` 与 sidecar 顶层 `regime_row` 一致；③正文含机械打分引用（正则找 `match%` 或 `match_pct` 或 `分层确定性` 表头，至少命中一处数字化引用）；④正文含证伪条件段（`## 证伪条件` 或 `证伪` 标题）。
- **Schema D 检查**：仅 ①账本有当日条目 schema="D"；②正文**不含**机制段/观察清单标题（Schema D 禁带，协议 §5）。
- 输出：逐项 PASS/FAIL 表，任一 FAIL ⇒ exit 1 并打印 `LINT-FAIL <项目>` 行。
- **接线**：`~/bin/market-auditor-diagnose.sh` 在 claude -p 正常退出（且非 DRY/非 SKIP）后跑 lint；FAIL ⇒ osascript 通知 + 追加 `$MA/data/alerts.log`；wrapper rc 保持 = claude rc。

**验收**：
- 对现存 `20260703--约束诊断-P.md` 跑 lint → 全 PASS（它有 sidecar/账本/打分引用/证伪段）。
- 复制该报告到临时目录、删掉 sidecar → FAIL①；抹掉正文 match% 数字 → FAIL③。exit code 验证。
- 对 `20260625--不诊断-*.md` 跑 → 账本有 D 条目 ⇒ PASS（若正文含禁带段则如实 FAIL，贴出结果）。

---

## 工单 6：sector-scan 数据验证移植（同病同治）

**问题**：sector-scan 管真金白银的 ETF 决策，但腾讯数据零校验：分红行 bug 是撞见的不是查出来的；无 as_of；样本量门只写在 SKILL.md prose 里。

**改法**（全部只动 `$SS/skills/sector-scan/scripts/`）：
1. `scan_all_etfs.py` 的 `fetch_data()`：
   - 结构校验：非法行（宽度<6、日期/价格字段类型异常）→ `logging`/stderr 打 `WARN fetch_data <symbol> malformed row ...`（含行内容截断样本），**不再被裸 except 静默吞成 None**；可修复的（如 >6 列）照旧截断修复。
   - 返回的 DataFrame 附带 `as_of`（最后一根完整 K 线日期）——以函数属性、全局 dict 或返回值扩展实现，**不得改变现有调用方签名兼容性**（保持 `fetch_data(symbol)` 仍可直接当 df 用；建议 `df.attrs['as_of']`）。
   - 主循环里对每标的记录 as_of，扫描完成后若存在 as_of 落后于众数日期的标的 → 报告头部数据源警示行加名单。
2. 样本量门代码化：`scan_all_etfs.py` 主流程里 `成功标的数 < 40` ⇒ stdout 打醒目 `🚨 样本量不足(<40)，数据源异常，结论不可用`，且报告 markdown 头部写同样警示（现在只在 SKILL.md 里要求 LLM 自觉判断）。
3. 新建 `validate_source.py`：抽 3 只 ETF（sh510300 / sh512880 / sz159915）× 各 3 个历史交易日（取 30/60/90 天前最近交易日），腾讯收盘价 vs 第二源交叉核对。第二源候选按序试：新浪 `hq.sinajs.cn` 历史接口、东财 `push2his.eastmoney.com` klines、AKShare；哪个可用用哪个，脚本里注明选择。输出 9 格对账表（差异>0.1% 标 ❌），任一 ❌ ⇒ exit 1。
4. **不碰**：12 公式、门控、TIERS、回测封顶逻辑——一行都不动。

**验收**：
- `validate_source.py` 跑通，9 格对账贴 CHANGES.md（允许因除权因子差异有 ≤0.1% 容差，超差需注明原因）。
- 人为构造异常行（单测里 mock 腾讯返回加一行 3 列的垃圾）→ WARN 日志 + 该行被剔除或修复，函数不返回 None（除非全部行非法）。
- 现有 `analyze('sh510300')` 路径回归正常（df.attrs 不破坏原逻辑）。
- **不跑全量扫描**；单标的回归即可。

---

## 端到端复验清单（贴 CHANGES.md「Round 3 (Backlog-1)」）

1. 工单1：合成 partial 快照 → gate SKIP partial；20260702 → 行为不变。
2. 工单3：备份子步骤独测 → `~/Backups/market-auditor/` 与源一致；无远端 push 静默。
3. 工单5：现存 A 报告全 PASS；两种故障注入各 FAIL + exit 1。
4. 工单6：9 格对账表；异常行 WARN 测试；单标的回归。
5. `py_compile` 全部改动脚本；确认未 commit、未碰协议文件、未改 sector-scan 安装目录、market-auditor 数据文件无 diff。
