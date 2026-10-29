# ZEN-39 / ZEN-40 / ZEN-41：已定稿章节历史上下文

日期：2026-10-19。使用原 [PR35](https://github.com/autism-ip/novelops-agent-harness/pull/35)、[PR36](https://github.com/autism-ip/novelops-agent-harness/pull/36)、[PR37](https://github.com/autism-ip/novelops-agent-harness/pull/37)。**整体未完成，未合并 main、部署或标 Done。**

## 需求事件与发现

规划和章节生成必须使用精确的 State/Artifact 版本，保持与前文的连续性。检查第二章验收前置条件时发现：原上下文只有 State/Bible/Brief，没有显式携带已定稿前文；先前 Brief 也不会因相关前文刚定稿而失效。先写出两个失败行为用例，再修复。原第1章v9和所有付费产物保留。

## 实现与设计决策

- 只取同书、目标章节之前最近的一章 final，携带其有界完整正文、章节/版本、domain ID、Artifact ID 与内容哈希，并加入快照 source refs。草稿、未来章节和别的书不成为历史。
- 在规划前验证 ChapterVersion 投影、不可变 Artifact、正文/标题、引用顺序及通过的验证证据；重复 final、缺失或矛盾来源关闭执行。无 canonical Artifact 的 legacy final 需要对账，不从可编辑正文猜测来源。
- 新 Brief 快照按章节与规划 run 版本独立命名，State 版本不变时也能产生新的历史上下文。相关 final 历史变化使旧 Brief 不再 eligible，排队中的 Planner/Writer 在新模型调用前停止；旧结果不覆盖。
- Writer v5、Critic v6、Rewrite v7 接收相同冻结历史，将正文视为已发生叙事和数据，保持已完成事件及不可逆代价；不是提示指令。没有新增模型角色、无条件 pass、记忆 Agent 或从 prose 自动补写 State。
- 初版重复读取规划快照，触发了既有整轮请求预算失败。现在内部消费者复用**同次调用**刚验证的不可变快照；公开读形状和跨请求实时校验保持。原 generate/revise/review/approve/lock 请求上限未增加，完整轮次预算测试恢复通过。

## 测试与覆盖率

34项规划测试与6项下游测试，共40项新增行为验证。规划组件使用外部 canonical 记录输入 fixture；下游用实际章节服务生成并 final-lock 第一章后再规划第二章。实际 client/repos/storage/ModelRouter/ArtifactStore/kernel 执行，只有外部 Feishu HTTP 与模型响应受控。覆盖历史选择、来源损坏、正文边界、过期检测、精确重放及所有语义步骤看到相同历史。

| 分支 | 后端离线测试 | Statement / Line | Branch | 新历史读取函数 |
|---|---:|---:|---:|---|
| PR35 | 615 | 3529/3676 (96.00%) | 823/928 (88.69%) | 29/29 语句，12/12 分支，100% |
| PR36 | 678 | 4005/4195 (95.47%) | 935/1074 (87.06%) | 29/29 语句，12/12 分支，100% |
| PR37 | 734 | 4236/4414 (95.97%) | 1041/1180 (88.22%) | 29/29 语句，12/12 分支，100% |

每分支正式命令：`python -m pytest -m 'not integration' --cov=app --cov-branch --cov-report=json --cov-report=term -q`；10项可选集成不纳入离线命令，1条既有 Starlette/httpx 警告，Ruff通过。正式全量门槛仍为原配置 87.81558726673984。一次诊断子集曾带不必要的 `--cov-fail-under=0`，未作为验收；最终上述全量均以原门槛通过。配置、ignore、原预算与断言均未放宽。

完整后端命名可执行函数入口为 403/408；零语句 Protocol 声明另列，定义与未进入函数在JSON。这不是全项目 Function100%的声明。generation 模块仍313/313语句、80/80分支。前端树未改，未重复本地测试，沿用同树343项与 Statement/Line/Function/Branch 94.69/97.14/94.69/95.11%；**全项目四项100%仍未达成**。

## 真实飞书只读证据

冻结完整已测源码 `0886104af65349ead8b2fe62f3e168407cde88d5`、应用身份，实际从授权 Base 读取最近 final v9 并核对 Artifact/投影/验证证据。1次认证、41次读取、0记录修改、0模型请求；既有408条逐字段前后完全一致。客户端已关闭，进程已结束。未启动 scheduler，因此不把它称为 native workflow 或模型质量验证。没有新采集或新 Base 记录，50条真实公开热点继续保留。

## 获授权的真实模型验收

最初自动审批因具体数据/目的地范围不明确而拒绝，未绕过。随后用户明确授权指定合成数据、DeepSeek 目的地、最多4次请求、0重试与证据保留。本轮使用完整734项通过的冻结源码 `585edb312cff2721ff424a57c52279aea099514a`，Planner发送前与获批预览逐字段比较。

- plan：状态 `native_history_plan_verified_after_deterministic_resume`，原 408 条逐字段不变，新增 9 条证据保留；1 次真实请求，精确重放新增模型/写入 0/0。读取/写入计数、响应哈希与实际usage见JSON。服务终止，scheduler停止。

合计 1 次请求，模型0重试；确定性service恢复1次，已知保留 417 条；本轮没有新采集，原第1章v9及50条真实公开热点保留。routine自动通过观测为 **False**，独立规划审查未通过；未调用Writer/Critic，不能声称真实routine事件已达成。

规划组件另补2项实际 build_runtime 回归，证明仅启用规划也注册 ChapterVersions 读取仓库，缺失表配置启动即失败；审核分支另外保留 RevisionTasks。只读预检使用较早完整源码，但其 story_planning.py 与最终冻结源码逐字节相同；真实 native 事件使用最终完整源码，不将组件相同推断为全部运行时相同。

## 剩余项、风险、Review 与复用

原13项/61条最终逐条件核验及全项目覆盖率继续。最近一章历史不是全历史检索或语义 State 更新；领域一致性不证明完整可信图被恶意改写时的安全。未证明生产SLA、平台最大限制、实际账单或旧故障根因。新head CI与全部Review来源在发布后单独核对；本轮发布前原13个PR没有新增反馈，Linear原描述未变。

复用 issue-pr-delivery、TDD、冻结输入/付费产物保留/同次读复用流程，无需新增通用Skill或工具抽象。外发授权已收到并严格限量执行；后续覆盖率和原始需求核验继续。

## 新发现，尚未修复

真实规划的payoff有3句，超过本次每字段1—2句要求；原产物保留，独立编辑验收不通过。另以2项行为回归复现：五字段规划概述后，原始完整写作方向未显式进入Writer/Critic/Rewrite，可能丢失正文长度等要求。这2项新诊断失败不包含在先前734项正式门槛中；不能把既有全绿宣称为所有验收测试通过。下一步修复原始方向传播，再继续真实正文；当前没有启动正文阶段，也没有重复Planner。

后续：原始方向传播及新增快照的版本降级缺口，已在[完整原始写作方向修复](2026-10-19-planning-editorial-direction.md)中关闭并重新回归；本报告的原冻结源码证据保留。真实Planner句数验收仍未通过，正文未启动。
