# ZEN-40 / ZEN-41：章节最终校验来源与选择完整性

日期：2026-10-19。交付仍使用原 [PR36](https://github.com/autism-ip/novelops-agent-harness/pull/36) 与 [PR37](https://github.com/autism-ip/novelops-agent-harness/pull/37)。**整体目标未完成，未合并 main、部署或标 Done。**

## 原始需求与实际验证事件

原要求：ChapterVersion 指向精确 StoryContextSnapshot 与源 Artifact 版本；确定性失败阻止无效推进/定稿，旧版本不被覆盖。此次验证事件为受控 HTTP 边界上的损坏来源拒绝与原数据恢复：真实项目 client/repositories/storage/ModelRouter/ArtifactStore/chapter service/kernel 执行，Feishu 与模型响应受控。未把该测试当成真实 DeepSeek routine 自动通过事件。

## 发现与实现

先复现 12 个领域来源缺口：泛用 Artifact 哈希自洽但书籍、章节、State、brief/snapshot、来源版本、run 或引用顺序已变化时，最终校验可能继续；缺失位置引用产生 IndexError。另复现 2 个布尔值被当作整数身份接受的情况（State 版本控制样本原本已被拒绝），以及 1 个基础分支最终阶段未再次拒绝 reject 选择的情况。原始失败日志保留，断言未弱化。

在位置引用读取及 review 投影修改前，核对四项有序引用、验证 Artifact 引用、书籍/章节/State/源版本/产物版本/brief/snapshot 的精确值与类型，以及 run/chapter 身份。矛盾抛出 AmbiguousWrite，留待对账。基础分支额外拒绝 reject；后续分支保持已配置的高价值人审原始候选保留语义。泛用 Artifact 哈希检查继续生效。

修复：[22b9cc5](https://github.com/autism-ip/novelops-agent-harness/commit/22b9cc5e3769965b0baa5f1fe97463db5c8c02eb)；补充证据/重放测试：[fcf05ae](https://github.com/autism-ip/novelops-agent-harness/commit/fcf05ae8b7b2bb56b8f534becdbd0ce070de0f80)。完整最终源码 SHA 在配套 JSON 的 gates 中。

## 行为回归与工程结果

31 项新测试：16 项哈希自洽的领域来源故障、3 项 manifest 损坏、7 项选择/投影冲突、5 项策略/验证证据/精确重放。故障检测只有读取，不调用新模型、不改变既有 ChapterVersion；恢复原始证据后继续同一 run，选择与版本数量准确，模型调用数不增加。重写禁用时 pass 正常推进；最终验证重放只读；Critic pass/revise/reject 与选择冲突及修改后的验证证据不能晋升。

| 范围 | 后端离线测试 | Statement / Line | Branch | final_verify 函数 |
|---|---:|---:|---:|---|
| PR36 | 638 | 3930/4130 (95.16%) | 904/1046 (86.42%) | 44/44 语句，20/20 分支，100% |
| PR37 | 694 | 4165/4347 (95.81%) | 1012/1150 (88.00%) | 47/47 语句，20/20 分支，100% |

每分支完整命令 `python -m pytest -m 'not integration' --cov=app --cov-branch --cov-report=json --cov-report=term -q`；10 项可选集成不纳入该离线命令，1 条既有 Starlette/httpx 警告，Ruff 全过。全 app 命名可执行函数入口：PR36 387/396，PR37 402/407；定义与未进入函数清单在 JSON，不能与整站四项覆盖率混同。generation 模块仍为 313/313 语句、80/80 分支100%。11 行既有默认排除未变；无配置、ignore、质量门槛或断言降级。

前端树未改，未重复本地前端测试，沿用同树 343 项以及 Statement/Line/Function/Branch 94.69/97.14/94.69/95.11%。GitHub 新 head 的 CI 与 Review 在发布后独立核对；前一批 13 个原 PR 的精确远端引用、依赖链和最新有效 CI 已验证全绿，全部 Review 来源无新增反馈、0 未解决线程。

## 证据边界、风险与剩余工作

本轮没有外部写入、公开采集或付费模型调用，已知保留证据仍 408 条，先前付费产物保留。真实单次模型来源/精确重放证据见 [模型报告](2026-10-19-model-provenance-and-replay.md)，公开50条及逐条去重、真实 v9 批准定稿证据继续保留。

领域检查发现不一致持久化元数据，不是对完整可信图被恶意重写的安全证明。真实 routine 章节自动通过仍缺，原13项/61条最终逐条件核验与全项目四项100%仍未达成；未证明生产 SLA、原始故障根因或模型账单。当前代码未引入新的数据迁移或依赖。

## Skill 复用

复用 issue-pr-delivery 的精确来源、失败关闭、已有投影恢复和不重复付费产物规范，以及既有 TDD/完整性工作流。此问题不需要新增工具抽象或通用 Skill。后续继续按原 issue/PR 单元推进，不能因函数100%或 CI 绿色宣布整体完成。
