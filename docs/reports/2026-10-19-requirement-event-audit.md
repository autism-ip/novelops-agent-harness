# 2026-10-19 原 13 项需求事件中期核对

**整体未完成。** 重新读取 Linear：18 项完整返回，原 13 项仍 In Review、5 项旧任务 Done；各项更新时间与完整描述缓存一致。保留原 Issue → 原 PR 对应关系，无新 PR、状态修改、合并或部署。

本表将原目标映射到实际事件、实现、测试和运行报告。完整验收条件保存在同名 JSON；这是中期证据地图，尚未完成逐条最终验收，不将历史执行或受控边界冒称当前源码的完整真实重跑。

| Issue / PR | 需求结果与已有事件 | 实现 / 测试 / 运行证据 | 剩余边界 |
| --- | --- | --- | --- |
| ZEN-105 / [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23) | 真实应用身份完成领域 ID CRUD；v3 可行性和有界读/冲突行为分别测量。真实应用 CRUD/批读；v3 部分为用户身份；模糊写入故障为受控传输 | `backend/app/storage.py`；`backend/tests/test_storage_provider.py`；[运行报告](2026-09-30-feishu-storage-provider.md) | 平台极限和生产 ACL 不作保证；保留单 writer；全项目覆盖率尚缺 |
| ZEN-104 / [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24) | 唯一内核按显式状态机调度、重启/审批恢复；慢 handler 期间仍能观察已提交进度。原生 lifespan 真实采集完成；真实 writer 竞争下四个 GET 完成；恢复故障有受控回归 | `backend/app/harness.py`；`backend/tests/test_harness_kernel.py`；[运行报告](2026-10-18-public-hotspots-real-feishu.md) | 旧运行原始 FeishuAPIError 原因仍未确认；[残留追踪已真实修复](2026-10-19-interrupted-trace-recovery.md)，不反推旧故障原因 |
| ZEN-106 / [#25](https://github.com/autism-ip/novelops-agent-harness/pull/25) | 生成 Artifact 可追溯，统一路由记录实际模型/usage，允许固定 fixture 比较方案。真实 DeepSeek 与飞书；当前保留 100 个 Artifact 内容哈希独立重算一致；OpenAI 为传输契约 | `backend/app/generation.py`；`backend/tests/test_evals.py`；[运行报告](2026-10-16-editor-contract-and-eval.md) | [原残留追踪已修复](2026-10-19-interrupted-trace-recovery.md)为 interrupted；未知用量未改，仍缺全 app 四项 100% |
| ZEN-33 / [#27](https://github.com/autism-ip/novelops-agent-harness/pull/27) | 公开 50 条完成入库；同一已保存批次逐条对账，既有记录不重建。真实匿名采集一次；真实应用持久化；已保存批次重放 50 reconciled、0 新增/更新，403 记录不变 | `backend/app/hotspots.py`；`backend/tests/test_hotspot_ingestion.py`；[运行报告](2026-10-19-public-hotspot-reconciliation.md) | 工具/模式/模糊网络故障为受控测试；更晚真实捕获的元数据更新尚未实测 |
| ZEN-34 / [#28](https://github.com/autism-ip/novelops-agent-harness/pull/28) | 用户筛选/详情/分页和触发采集可观察真实结果，未知结果可精确重放。真实浏览器到飞书 50 条；桌面/390px 详情与分页通过；手动/丢弃恢复另有受控端到端 | `backend/app/hotspot_controls.py`；`backend/tests/test_hotspot_controls.py`；[运行报告](2026-10-18-public-hotspots-real-feishu.md) | 十秒提交超时仍可能发生，当前按保留命令恢复；不重新写真实公开数据来重复演示丢弃 |
| ZEN-35 / [#29](https://github.com/autism-ip/novelops-agent-harness/pull/29) | 热点产生结构化机会 Artifact，风险/选择门控制推进，失败明确可查。保留的真实 DeepSeek/飞书机会和 risk/risk_review；真实 risk_gate 与 selection 已批准 | `backend/app/research.py`；`backend/tests/test_research_workflow.py`；[运行报告](2026-09-28-opportunity-research.md) | 低风险自动继续与坏输出验证有受控测试，未把它们称为重复真实质量统计 |
| ZEN-36 / [#30](https://github.com/autism-ip/novelops-agent-harness/pull/30) | 已批准机会生成至少 10 标题、选定标题生成至少 3 封面方向。当前保留真实 20 TitleCandidate、5 CoverPlan；对应两流程 completed、选择门 success | `backend/app/creative.py`；`backend/tests/test_creative_workflow.py`；[运行报告](2026-10-12-creative-batch-runtime.md) | 标题市场效果/长期模型质量不由数量或 schema 保证；去重/错误为受控测试 |
| ZEN-37 / [#31](https://github.com/autism-ip/novelops-agent-harness/pull/31) | 人类对机会/标题/封面做版本化决定，保存 ApprovalEvent 并解锁后续。真实批准和已选来源解锁现存 Book；未知响应/精确重放有真实与受控证据，边界见原报告 | `frontend/src/components/hotspots/creative-results.tsx`；`frontend/tests/creative-workbench-contract.test.tsx`；[运行报告](2026-10-15-selection-recovery.md) | 变更选择/失败存储覆盖按各报告 source；未把每种 UI 错误都当真实飞书故障 |
| ZEN-38 / [#32](https://github.com/autism-ip/novelops-agent-harness/pull/32) | 批准来源 bootstrap Book 与可追溯 canonical StoryState v1。当前真实 ready Book，保留 StoryState v1/v2 和源 refs；恢复/外部变化有受控 E2E | `backend/app/books.py`；`backend/tests/test_book_bootstrap.py`；[运行报告](2026-09-28-book-bootstrap.md) | 不创建独立记忆 Agent；当前运行仍依赖完整 Base schema 和单 writer |
| ZEN-107 / [#34](https://github.com/autism-ip/novelops-agent-harness/pull/34) | 统一顶部导航和列表/决策分栏，桌面与手机维持审批与键盘可用。历史核心热点→审批→书籍受控全链路；新增真实入库、真实 v9 批准定稿；全部路由分次桌面/手机验收 | `frontend/src/components/workflow-monitor.tsx`；`frontend/tests/workflow-status-pages.test.tsx`；[运行报告](2026-10-18-workflow-observation.md) | 不是一次当前完整回放的录像；业务树无更改的测试/报告同步不触发重复视觉微调 |
| ZEN-39 / [#35](https://github.com/autism-ip/novelops-agent-harness/pull/35) | 批准 StoryBible 提交 canonical v2；ChapterBrief 具有源版本并解锁写作。当前保留真实 1 Bible、7 版本 Brief、StoryState v1/v2，最新合格 Brief 驱动已定稿 v9 | `backend/app/story_planning.py`；`backend/tests/test_story_planning.py`；[运行报告](2026-10-18-chapter9-final-and-focused-review.md) | 旧错误 Brief 和失败运行保留；不称 schema 通过就代表编辑要求完成 |
| ZEN-40 / [#36](https://github.com/autism-ip/novelops-agent-harness/pull/36) | Writer→Verifier→Critic→按需 Rewrite→最终验证，追加版本而非覆盖。真实 9 个章节版本；最终 v9 1591 汉字、独立内容审核合格，旧 8 版本和 9 Artifact 不变 | `backend/app/chapter_loop.py`；`backend/tests/test_chapter_loop.py`；[运行报告](2026-10-18-chapter9-final-and-focused-review.md) | 1–3 是原验收首批版本范围，不擅自改成必须 3 个章节；质量不可由 schema 或 100% 覆盖保证 |
| ZEN-41 / [#37](https://github.com/autism-ip/novelops-agent-harness/pull/37) | 精确退修约束生成 RevisionTask，真实批准/定稿保留旧版本，按策略选择人审。实际 UI 退修→真实 DeepSeek→v9 合格→批准/定稿成功；routine 自动 pass 目前为受控浏览器/契约证据 | `backend/app/chapter_loop.py`；`backend/tests/test_chapter_review.py`；[运行报告](2026-10-18-chapter9-final-and-focused-review.md) | 真实模型 routine pass 事件尚缺；RevisionTask queued 表示入队进度，API/UI 另查 run_status，无需误改旧记录 |

## 本轮改变下一步的事实

- **逐条重复对账已取得真实证据**：同一已保存公开批次 50 条全部识别为已有记录，0 新增/更新；当前保留 403 条逐字段不变。没有第二次采集/模型/新流程。
- 当前保留的 100 个 Artifact 内容哈希独立重算均匹配；这是完整性证据，不替代内容质量。真实标题 20、封面 5、Book ready、StoryState 两版本、章节九版本仍在。
- **早先观察到的追踪恢复缺口（同日已修复）**：一条 2026-10-15 的 `chapter.critic` agent trace 仍为 running，关联步骤已 success、retry_count=1、关联流程已 failed。`recover` 恢复步骤而未收束旧尝试 trace；随后用受控中断复现、14 项回归和真实原生启动验证完成修复；实际只改变这一条合成 trace，其余 402 条不变。具体原始中断过程/账单仍不能反推。此发现与最终 v9 是不同流程，详见[完整报告](2026-10-19-interrupted-trace-recovery.md)。
- RevisionTask 的 queued 记录入队结果；review API 关联 run_status，UI 显示 run 状态。已有文档/实现一致，不将其判为未完成任务投影。

## 当前门槛与继续工作

完整后端 **623 项离线测试通过**（10 可选集成未执行，1 既有警告），Ruff 通过；本轮后端 Statement/Line 4111/4315（95.27%），Branch 984/1142（86.16%）。热点服务/API 以及新 trace recover 函数的语句、行、分支 100%，并非整个后端 100%。本轮不重新声称独立全 app Function 统计。

前端树未改变，沿用已验证的 343 项与 94.69/97.14/94.69/95.11% 四项覆盖率，未重复运行视觉验收。既有 11 行 coverage.py 排除未修改；整个项目不满足 100%。

继续：补齐剩余合理业务边界测试；取得真实模型 routine 自动通过事件；按原每项验收条件做最终审查。生产 ACL/SLA、长期吞吐和实际账单不由这些证据保证；用户当前交付目标是可审阅 PR，并未授权合并/部署。

本轮复用 issue-pr-delivery、现有 CLI/MCP 和生产 provider；未创建新通用技能。已确认原生只读重放进程正常退出，未留下调度器或新业务写入。

本日追踪恢复后，原生 helper 已确认正常退出，403 条既有验收记录保留；完整用量聚合不变，没有再次采集/生成/审批。既有 issue-pr-delivery Skill 追加了中断观察与业务结果分开核对的经验，校验通过。
