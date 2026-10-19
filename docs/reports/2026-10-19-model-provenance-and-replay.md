# 2026-10-19 模型产物溯源与精确重放 — 原 ZEN-106 / PR #25

**本次溯源与重放事件已验证，整项目仍未完成。** [原 PR #25](https://github.com/autism-ip/novelops-agent-harness/pull/25) 保留原 Issue 和依赖关系。没有新建重复 PR、将 PR 合并至 main、部署或修改 Done。

## 从需求到行为

| 需求 | 发现与修复 | 验证 |
| --- | --- | --- |
| 每个生成产物绑定实际模型与本次调用 | 原实现重新扫描历史；缺行时回退配置别名，旧历史会选到旧模型并改写旧追踪。改用本次成功返回的 GenerationResult（输出、确认的 trace ID、返回模型） | 两项历史缺失/陈旧回归先红，修复后不扫描历史、不改写旧追踪；真实调用的 ID/模型/hash/输入源关系核对通过 |
| 产物保存后的链接写入可恢复 | 原实现保存 Artifact 后，追踪引用写失败；重放只返回产物，漏掉修复。新直接模型产物保存 model_trace_id，并按明确 ID 检查 run/step/输入、模型、prompt/route/workflow 版本、输出 hash 和现有链接 | 第三项回归先红；原命令修复引用、模型仍 1 次；缺失或冲突追踪停在 reconciliation，不重新生成 |
| 已存在的数据和对外 API 保持可读 | generate 仍返回经过 schema 验证的输出；新增 generate_recorded 供共享运行时使用。旧 payload 未带追踪 ID 时保持原读形状，不猜测回填 | 100 个真实旧 Artifact 逐一与原始 JSON 比对相同；全部 403 条原记录逐字段不变 |
| 有界失败和资源边界明确 | 连接错误、非文本输出、缺配置、空 ID、提交回显冲突、借用 client 的关闭语义；保持每调用一个 call ID 和 0–2 次重试/原 backoff | 新增共 40 项需求回归。显式有限 attempt 计数取代永远不可达的循环隐式落点，不修改有效重试预算，也不使用无效配置刷分支 |

新字段在已有 payload_json 内，不新增表或 Base 列。新产物里的 model_trace_id 属于不可变元数据；正常已关联重放不修改追踪时间。派生产物沿版本化 source_refs 追溯。旧记录没有被迁移或回填；旧 strict Artifact schema 明确读取新输出时不认识新增字段，需使用更新后的后端。此次真实产物只在已授权测试 Base 中，未发布生产。

## 真实集成事件

先检查 CLI/MCP：gh/lark-cli 可用，没有 DeepSeek CLI 或适用飞书/DeepSeek MCP。使用现有生产 ModelRouter、SemanticRuntime、Feishu provider 和实际应用身份。固定完整源码 **76deb6a46ed83977203fa66a8b5d6d1de105e5e3**，app 树 **3706af27cdd90cbe7a160765ead20a0f519c7cf6**；已通过完整 663 项离线回归和 Ruff。与 #25 相同的路由、链接、重放方法源码 SHA 在同名 JSON 中，后续分支保留其原 creator 参数。

原生 FastAPI lifespan → 单一内核 → 一次真实 DeepSeek JSON 调用 → Artifact 与 model trace 持久化 → 受保护 API 查询 → 精确命令与产物重放。输入仅是合成控制对象，不包含旧书籍正文或公开热点。约束：最多 1 个模型请求、128 输出 token、路由与内核重试均 0，禁止改写任何原记录、再次采集或新增其他任务。

| 实测项 | 结果 |
| --- | --- |
| 模型 | deepseek-flash；HTTP 200、stop，147 输入 / 8 输出 token，0 重试 |
| 配置价格估算 | USD 0.0000537；不是提供商账单，也不是项目总成本 |
| 新输出 | 实际响应 JSON 与真实读回 Artifact 内容完全一致；内容 SHA-256 `7085a6b0c6dde093a8a5b74339023ad9ad6a6f1989af75c18c6e96860313bbeb` |
| 溯源 | Artifact.model_trace_id 指向本次 model trace；模型/输入/route/prompt/workflow/输出 hash 一致，model 与 agent 两条 trace 均 success |
| 状态 | Workflow completed，Step success、output_version=1、retry_count=0 |
| 原命令重放 | 两次相同 POST 均 201、同一 workflow；直接语义重放产物完全相同；新增模型/写入均 0 |
| 生成期间历史扫描 | 0；按明确 trace ID 核验、关联 |
| 保留范围 | 新增 1 流程 + 1 步骤 + 1 Artifact + 2 Trace，共 5 条；原 403 条不变，已知验收记录共保留 408 条 |
| SDK 请求 | 1 次认证、213 次读取、13 次仅针对新 5 条记录的创建/状态更新；公开采集 0 |
| 生命周期 | 原生调度器实际启动；helper 正常退出 0，调度器已停止；总计 248.716 秒包含全部预检、恢复与前后完整核验，不是模型耗时或 SLA |

写前记录了确定性业务 ID 与动态 Trace ID。退出后的新记录快照再与实际提供商响应独立解析、重算 hash、核对引用、状态和用量。原始提供商响应与完整数据只留在私有证据；GitHub 不发布凭据、旧正文或公开热点原文。后续预检需在此前 403 条检查点上合入这 5 条已保留新记录，不能把旧检查点当当前完整状态。

这个合成控制验证模型元数据/存储链路，不代表章节语义质量，也不替代仍待完成的真实章节策略自动通过。

## 测试、评测与覆盖率

| 原 PR | 后端离线通过 |
| --- | --- |
| #25 | 432 |
| #27 | 480 |
| #28 | 489 |
| #29 | 529 |
| #30 | 557 |
| #31 | 557 |
| #32 | 565 |
| #34 | 565 |
| #35 | 581 |
| #36 | 607 |
| #37 | 663 |

各分支 Ruff 通过，10 项可选凭据测试未执行，1 条既有 Starlette/httpx 警告；此次另有上述真实集成。前端源码树未改，沿用同树 343 项及既有四项覆盖率，不声称本地重跑。

| 范围 | Statement / Line | Branch | Function |
| --- | --- | --- | --- |
| 模型基础模块 | 313/313，100% | 80/80，100% | 26 个实际实现函数均完整覆盖 |
| #25 全后端 | 1974/2050，96.29% | 462/506，91.30% | 全 app 独立统计未重算 |
| 完整 #37 后端 | 4147/4342，95.51% | 1000/1148，87.11% | 全 app 独立统计未重算 |

模块原有 3 行默认排除仅涉及类型 Protocol 声明与相邻空行，未新增 ignore 或调用空协议方法刷覆盖。全 app 原有 11 行默认排除、配置、质量门槛和旧断言均未改动。整个项目不满足四项 100%。

固定评测 CLI 在旧源码 6098dcba 与新源码运行相同 fixture 哈希 `f4a307cfe485a3871b7fb16c5b598e57dcab07f6d715be19c48a62e69fb07792`。除实测 latency_ms 外，完整两方案结果、schema/约束 findings、usage、价格、重试和输出均一致。它是受控 fixture 评测，没有真实 OpenAI/DeepSeek 请求，不作为写作质量比较结论。常规命令：`python -m pytest -m "not integration" --cov=app --cov-branch`、`ruff check --no-cache .`、`python -m app.evals --output ...`。

## 审阅边界与继续工作

合并研究分支时出现 creator 签名/字段冲突，已逐块保留 creator 和新 model_trace_id 后逐分支重跑。完整冻结源码不反推祖先具有书籍/章节全部功能。精确发布 head 的远端引用、CI 与全部 review 在推送后另核对。

继续原 13 个 Issue、61 条验收的最终逐条件检查、全项目适用四项 100% 和真实章节 routine 自动通过。此次不新增 Agent 角色、模型 pass 或第二数据库，不改重试/人审策略，不推断旧中断原因或提供商实际账单。复用既有 issue-pr-delivery 的精确命令与部分投影恢复流程；稳定确认 ID 与重放链接可复用，无需另建通用 Skill。
