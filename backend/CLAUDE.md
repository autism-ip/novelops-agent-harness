# backend/
> L2 | 父级: ../CLAUDE.md

成员清单
app/harness.py: 单调度器和单写者状态机；投影先读取当前流程类型，仅存在投影器时才加载最新步骤，不缓存业务状态。
README.md: 后端包说明与本地验证命令，包含当前覆盖率基线和运行限制。
pyproject.toml: Python 项目元数据与依赖门禁；固定 Ruff/coverage/build 工具，配置 lint、87.82% 当前覆盖率基线下限和 app 包发现。
.env.example: 本地环境变量样例，只放占位符，不承载真实密钥。
app/: FastAPI 应用实现 — 工厂函数、配置、中间件、路由。
tests/: 行为级 pytest 门禁，验证 ZEN-28 验收契约而非仅验证进程可启动。
app/api/: FastAPI 路由层——中间件守卫（deps.py）、端点注册（routes/__init__.py）、健康探活（routes/health.py）、管线端点（routes/pipelines.py）。
app/generation.py: 版本化 Artifact 与模型/遥测基础；批量产物读取复用单条读取的身份、稳定版本 ID 与内容哈希校验，每次调用重新读取。
app/feishu/: 飞书 Bitable 集成层——HTTP 客户端（client.py）、16 表配置（table_map.py）、16 个具体 Repository + 工厂（repositories/）。
app/pipeline/: 流水线引擎——数据模型（models.py）、编排器（engine.py）、lease-based worker 执行循环（worker.py）。
app/tools/: 外部工具集成层——OpenCLIRunner 子进程执行（runner.py）、OpenCLIResult 结果封装（含 data 字段）、DouyinHotspotRecord 数据契约（schemas.py）、错误层级（errors.py）、DouyinAdapterResult 归一化结果。
app/tools/adapters/: 工具适配器子包——抖音热点适配器（douyin_hotspots.py），DouyinHotspotAdapter 封装命令组装与字段归一化，支持多字段别名容错。
app/hotspots.py: ZEN-33 确定性抓取快照、去重、保留业务 ID/状态、按新采集时间更新与重启对账；不调用 LLM。
app/hotspot_controls.py: ZEN-34 人工添加与丢弃命令；通过持久化工作流执行，稳定身份和状态冲突保护。
app/research.py: ZEN-35 版本化 ResearchAgent、保守风险策略、精确版本审批与可恢复飞书分析投影；同一次读取按业务 ID 批量验证两种产物与审批事件，保留未生成产物和步骤顺序，每次重新核验热点当前性。
app/creative.py: ZEN-36 标题候选与封面方向生成、逐项 Artifacts、版本选择与飞书投影；候选按业务 ID 批量重新读取，保留顺序与完整性校验，缺失时不返回部分集合，选择步骤复用本次同一组 ID；完整已选视图与选项由同一次新鲜读取返回，保留种类、终态、当前性和精确选择校验。
app/books.py: ZEN-38 精确来源建书与 canonical StoryState，ready 重放兼容后续状态版本；同次单写者操作复用完整已审批/已选视图，不重复解析相同链路，每次重新核验来源。
app/story_planning.py: ZEN-39 StoryBible 人工审批与确定性状态补丁、不可变 StoryContextSnapshot、版本化 ChapterBrief；资格检查仅展开最新版本，历史列表保留完整读取。
app/chapter_loop.py: ZEN-40 精确源章节快照、Writer→机器校验→Critic→按需 Rewrite→最终校验与版本锁定；人工三类约束完整传入Critic并在后续Rewrite中保持顶层优先，Critic建议独立保留；首次定稿和锁定重放均核验整章版本投影与产物一致性，歧义拒绝写入。 首次定稿还须重取选定正文的Critic、Verifier与绑定草稿，重新核对确定性检查及精确来源；所需不可变产物批量读取，不覆盖旧版本。
app/api/routes/story_planning.py: ZEN-39 精确版本上下文、触发、历史、审批和 eligible brief 接口。
app/api/routes/chapter_loop.py: ZEN-40 章节生成 context、触发、运行/版本历史及 final-lock 接口。
app/api/routes/research.py: 鉴权批量分析、历史、审批/拒绝/退修与 approved 消费契约。
app/api/routes/creative.py: ZEN-36 标题和封面的版本 context、触发、历史、选择与 selected 消费契约。
app/api/routes/hotspots.py: 鉴权抓取触发及热点列表/详情接口；命令只由后端配置。

架构决策
`app.main:create_app(settings)` 是唯一入口；模块级 `app` 通过 `__getattr__` 延迟创建。`Settings` 字段全小写，pydantic-settings 自动映射大写环境变量。密钥只进入 Settings 与 app.state，禁止出现在响应体。`/api/system/health` 与 `/api/system/status` 公开可探活，`/api/system/config` 需鉴权，其余 `/api/*` 先过 `x-api-key`。

依赖边界
`tests/` 是语义边界：它描述未来实现必须满足的外部行为。实现代码不得通过改弱测试来过关，只能让真实行为匹配测试。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

规划模型输入将鉴权请求的 feedback 映射为独立 editor_instruction；StoryBible 同时携带 initial/major 范围，仍由精确版本人工审批生效。提纲以规范快照规则为上位约束，修复旧提纲冲突。API 的 feedback 字段保持原契约，客户端不能伪造内部输入字段，来源中的同名文本只是数据。

app/evals.py: 离线对比及有界真实 provider 评估 CLI；非空数组 fixture 验证先于客户端创建，输出失败类别与用量未知状态，不把传输测试当作真实模型质量证据。

chapter-planner-v3 区分给作者的规划说明与下游章节正文风格，遵从编辑指定的视角、句数和原句标点；真实语义仍须独立验收。

SemanticRuntime 可由内部调用方显式选择已验证的顶层字符串指令字段，作为来源 JSON 后的最后 user 消息；输入哈希同时绑定字段选择，缺省路径消息/哈希保持，嵌套来源不能被提升为指令。

StoryBible v3 / ChapterPlanner v4 显式选择 editor_instruction 为来源JSON后的最后user消息；系统规范仍居上位，输入哈希绑定选择器，公共API不新增内部字段。

Settings统一读取.env、.env.local及进程覆盖后的Base和表ID；runtime向TableMapConfig显式传递已解析配置，禁止运行时混用别的进程环境。旧TableMapConfig无映射调用仍保留环境接口，显式映射防御性复制且缺失值保持fail-fast。

Writer v4 / Critic v4 / Rewrite v5 使用最后user消息中的显式章纲与原始编辑约束，模型建议独立且从属；实际动作、时间转换和完成结果不得由意图代替，Critic须对照实际文本提供依据。仅输入渲染变更，API和输出schema保持。

Critic v5 / Rewrite v6 的内部最终指令附带由实际正文计算的 prose_metrics：Unicode 码点数与 U+4E00..U+9FFF 汉字数（不含标题）；明确计数范围，不把 token 数当字数，不解析或信任叙事中的伪造计数。原始约束、公共 API 和输出 schema 保持，排队旧合同变更即阻塞。
工作流列表/详情读取不等待整个handler的writer锁；返回飞书中已持久化的进度观察值，不承诺跨表原子快照。全部机器修改、调度选择和审批仍串行于同一writer。
