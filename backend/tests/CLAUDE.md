# tests/
> L2 | 父级: ../CLAUDE.md

成员清单
test_harness_projection.py: 投影读取契约；无投影器不加载未使用步骤，有投影器保留当前类型、最新状态、取消兄弟步骤与投影失败后的无副作用重放恢复。
test_legacy_pipeline_resources.py: 32项兼容管线API真实路由/映射/引擎门禁；dotenv、显式配置与进程配置隔离，请求客户端成功/失败均关闭，鉴权与v0.2创建禁用先于出站IO，部分创建回滚使用实际record_id且清理失败不假报成功；只控制外部HTTP。
test_legacy_worker_transport.py: 20项实际旧Worker/Engine/映射仓库HTTP合同；租约、依赖、重试耗尽、失败零写入和ID隔离，明确不代表v0.2调度或分布式安全。
test_application_boundary_contracts.py: 15项应用配置/鉴权隔离、启动缺表关闭、公开状态故障恢复和独立旧health消费合同；不将未挂载router当作生产探活。
test_story_states_query_contract.py: 3项StoryStatesRepo实际book_id投影查询合同；不同书籍及字面恶意ID只返回精确记录，表隔离/无写入；不代表canonical状态生成或真实Base验收。
__init__.py: pytest 包标记。
function_entry_coverage.py: 可显式加载的全 app 函数入口报告插件；含未导入模块、嵌套函数、lambda 和 Protocol 声明，不替代语句/分支覆盖率；输出 coverage-functions.json。
conftest.py: 测试环境与 AsyncClient 夹具（pytest_asyncio.fixture），隔离环境变量，TYPE_CHECKING 导入 Settings。
test_system_endpoints.py: 系统端点行为门禁，验证响应形状、占位状态与不泄密。
test_api_key_guard.py: API key 中间件行为门禁，验证公开端点豁免与私有 API 拦截。
test_acceptance_contract.py: ZEN-28 验收门禁，验证配置失败清晰、应用可导入、布局符合计划。
test_api.py: 集成测试，验证系统端点与 API key 鉴权的 TestClient 行为。
test_feishu_client.py: FeishuClient 行为门禁，验证 token 生命周期、Bearer 注入、401 重试、token-invalid 重试与异常路径（含有界 GET 内部错误重试与写入不重放用例）。
test_base_repository.py: BaseRepository 行为门禁，验证 Python↔Feishu 字段映射、CRUD + 分页操作、字段过滤、业务键查找及异常写入回显。
test_storage_batch_read.py: 业务 ID 批量读取的 47 项行为门禁，覆盖原生只读 POST、富文本/数字映射、50 条件分批、缺失/重复身份、分页循环及失败不返回部分结果。
test_storage_batch_live.py: 显式固定测试 Base 的可选真实批量查询门禁；只创建本次合成记录，独立客户端确认清理。
test_table_map.py: table_map 完整性门禁，验证 16 表配置数量、映射对应关系、环境变量 fail-fast（16 用例）。
test_domain_exceptions.py: 异常层级门禁，验证 FeishuError 家族继承关系与 code 属性（6 用例）。
test_token_retry.py: token 重试门禁，验证 99991663/99991668 触发清 token + 重试一次（3 用例）。
test_config_failfast.py: 配置 fail-fast 门禁，验证缺失环境变量时 get_table_id 抛 ValueError（4 用例）。
test_step_status_recordid.py: record_id 门禁，验证 _from_feishu/get/create 均携带 record_id（3 用例）。
test_pipeline_engine.py: PipelineEngine 行为门禁，验证 create/get_runnable/complete/fail/rollback/validation 生命周期及父流程 record_id 契约。
test_worker_loop.py: WorkerLoop 行为门禁，验证 claim/lease/expired/poll/execute/retry 及父流程 record_id 契约。
test_repository_queries.py: 全部 16 张表的工厂装配和领域查询行为门禁，验证真实映射、表隔离与过滤条件。
test_step_runs.py: StepRunsRepo 行为门禁，验证 claim_step 业务键→record_id 解析与 find_by_pipeline 字段过滤（4 用例）。
test_pipeline_api.py: Pipeline API 端点门禁，验证 POST 创建、GET 安全业务键查询、重复 ID 冲突和 404 处理。
test_feishu_integration.py: 飞书集成门禁（需真实凭证，CI 跳过）。
test_hotspot_ingestion.py: ZEN-33 子进程→adapter→调度器→Feishu transport→API 验收，覆盖批次重放、去重、超时与关闭采集后读取；不等于真实平台验收。
test_hotspot_controls.py: ZEN-34 人工添加/丢弃鉴权、幂等与冲突、写入超时和重启恢复验收。
test_research_workflow.py: ZEN-35 schema/风险分流、模型失败、版本审批、投影恢复、批次重放及 API 验收；四阶段批量读取预算、部分产物和跨请求丢弃新鲜性。
test_research_kernel_contract.py: 动态审批、退修理由、永久失败与终态投影恢复契约。
test_creative_workflow.py: ZEN-36 十至二十标题/三至五封面、模型输出验证、精确选择、版本及失败契约；批量只读查询、候选顺序、跨请求篡改/缺失拒绝契约；部分投影失败后同一选择重放补齐且不重复审批事件或模型调用；完整已选视图仍拒绝未选、错误种类和丢弃来源。
test_book_bootstrap.py: ZEN-38 单书/状态幂等和初始化恢复；上下文读取预算、精确来源、远程丢弃后拒绝和纯读取零生成。
ui_fixture_app.py: 仅本机浏览器验收服务；复用真实 API/Harness 与合成 HTTP 存储，提供受鉴权保护的响应丢失/上游失败注入；不进入生产包。
test_story_history_contract.py: ZEN-39 产品历史 API 的鉴权空历史零生成，以及故事升级后新旧 Bible/Brief 来源、顺序、资格和不可变快照的 HTTP 验收。
test_story_planning.py: ZEN-39 API 与 Harness 门禁，覆盖人工审批、状态版本、不可变快照、brief 资格、历史读取数量上限、禁止回退旧提纲和中断恢复。
test_chapter_loop.py: ZEN-40 章节生成、结构化 Critic、条件改写、硬规则/成本门禁、重试与最终锁定验收；人工约束在Critic和自动Rewrite中的完整性（每类1项/20项）、旧版本不可变与调用次数验收。
test_review_prerequisites.py: 审稿台前置能力缺失时先鉴权、明确503且零外部读取/写入；Bible、Brief及正文生成请求与URL目标不一致时422且零模型调用。
test_chapter_review_integrity.py: ZEN-41 审稿失败关闭契约；空白操作者、远程版本来源损坏、不可重放修订意图和精确终锁重放，经真实 API/仓储验证安全错误、零写入、零新增模型调用及恢复后原产物一致。
test_editorial_projection_commands.py: 44项审稿命令与退修恢复合同；整章投影歧义、跨书业务ID碰撞、恢复后的精确重放、退修身份篡改与真实HTTP远端已提交/读回不可用恢复；另3项构造配置明确不作为完整启动验收，均保持原模型预算；首次列表暂旧时仍须后续新鲜检查，拒绝旧版本且零写入。
test_chapter_review.py: ZEN-41 选择性关卡、精确 HTTP 审阅/退修、RevisionTask 恢复、历史与终锁、响应读取数量和跨刷新完整性门禁；包含空备注被远程省略后的批准/拒绝零写入重放及冲突保护，以及生产装配缺少 RevisionTasks 表配置时启动失败、已配置时按实际表 ID 查询的回归。

test_chapter_projection_boundaries.py: 章节投影歧义的HTTP拒绝与恢复合同；外部重复版本不得绕过定稿完整性检查，保留旧版本和模型调用次数，不作为真实模型语义验收。
test_chapter_command_boundaries.py: 初始/退修命令、占用版本精确重放、运行中重复触发和不可执行Critic退修的行为合同；构造配置失败单独标注，均不替代真实模型语义验收。

架构决策
测试以 BDD 验收行为为中心：状态值必须精确、密钥不得回显、鉴权必须先于路由缺失返回。门禁允许当前实现缺失时失败；它的职责是定义合格线，而不是替实现兜底。CI 显式排除 integration，保留全部离线断言，要求 app 语句覆盖率至少当前基线 87.82%，上传 coverage XML 与 JUnit 报告；Ruff 同时检查测试代码。不得为过门禁降低覆盖率下限、删除或弱化断言、增加应用代码排除项。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

规划编辑指令 HTTP 回归：初始Bible、重大变更、Brief均覆盖未鉴权401、伪造内部字段422且零run/调用、原样feedback映射、不可变来源及人工设定门；模型语义服从另由真实验收核实。

test_eval_cli_contract.py: 实际 CLI/router/provider 的 16 项行为用例；仅控制出站 HTTP，验证参数、fixture 边界、失败分类、约束检测、资源关闭、用量隔离与报告不泄露凭据/正文。

规划合同冻结回归覆盖 Bible/Brief：排队后提示词版本变化须 blocked，零模型调用、冻结定义不变、无新增生成产物与规范变更，精确请求重放不创建新任务。

test_model_instructions.py: 两家 provider 的显式用户指令、空指令、来源不变、请求/输入哈希、渲染选择器重放冲突及非法字段零调用的8项边界门禁。

test_consumption_api.py: 机会 approved 与标题/封面 selected 的 HTTP 消费边界；鉴权、缺失/未选拒绝、精确产物、跨请求丢弃/篡改拒绝，重复只读不调用模型。5项用例使用实际API/kernel/存储适配器及受控HTTP，不包含服务lifespan或真实模型质量。

三种鉴权编辑输入HTTP用例同时核验最后user消息逐字等于原始反馈；来源中的同名文本仍仅在完整来源JSON内。

test_runtime_dotenv_tables.py: 五项启动配置行为门禁；文件/进程优先级、完整表注册、配置实例隔离、显式空配置不回退环境和旧接口兼容；合成凭据、无远程API调用。

章节输入回归新增三种初始角色场景，保留1/20项编辑约束回归；核验最后消息、完整五字段提纲、原始编辑约束和模型建议的不同权限，叙事引用不提升为指令。

章节度量回归验证初始 Critic、自动 Rewrite 及人工退修三阶段实际 HTTP 消息：混合汉字/标点/emoji 的准确范围计数、原稿/当前稿绑定、来源伪造计数不提升、初始 Writer 无虚构计数、Critic/Rewrite 合同升级不静默执行旧排队任务。
test_harness_kernel.py: 慢外部handler执行期间列表/详情仍可读取真实running状态；并发新命令仍等待单一writer，保留既有重启、版本审批和模糊写入行为门禁。

test_harness_boundaries.py: 审批身份、严格版本、重复操作者与外部审批证据损坏的行为门禁；真实API/Kernel/存储映射，验证拒绝后无写入、恢复原证据和精确重放。

test_kernel_lifecycle_boundaries.py: 15项内核生命周期边界；运行中注册限制、重复启动、非法定义/转换、404、非审批步骤拒绝、取消保留已完成结果和完成任务重启不重跑。
