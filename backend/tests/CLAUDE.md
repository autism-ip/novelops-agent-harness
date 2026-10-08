# tests/
> L2 | 父级: ../CLAUDE.md

成员清单
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
test_research_workflow.py: ZEN-35 schema/风险分流、模型失败、版本审批、投影恢复、批次重放及 API 验收。
test_research_kernel_contract.py: 动态审批、退修理由、永久失败与终态投影恢复契约。
test_creative_workflow.py: ZEN-36 十标题/三封面、模型输出验证、精确选择、版本及失败契约。
ui_fixture_app.py: 仅本机浏览器验收服务；复用真实 API/Harness 与合成 HTTP 存储，提供受鉴权保护的响应丢失/上游失败注入；不进入生产包。
test_story_planning.py: ZEN-39 API 与 Harness 门禁，覆盖人工审批、状态版本、不可变快照、brief 资格、历史读取数量上限、禁止回退旧提纲和中断恢复。
test_chapter_loop.py: ZEN-40 章节生成、结构化 Critic、条件改写、硬规则/成本门禁、重试与最终锁定验收。
test_chapter_review.py: ZEN-41 选择性关卡、精确 HTTP 审阅/退修、RevisionTask 恢复、历史与终锁、响应读取数量和跨刷新完整性门禁；包含空备注被远程省略后的批准/拒绝零写入重放及冲突保护。


架构决策
测试以 BDD 验收行为为中心：状态值必须精确、密钥不得回显、鉴权必须先于路由缺失返回。门禁允许当前实现缺失时失败；它的职责是定义合格线，而不是替实现兜底。CI 显式排除 integration，保留全部离线断言，要求 app 语句覆盖率至少当前基线 87.82%，上传 coverage XML 与 JUnit 报告；Ruff 同时检查测试代码。不得为过门禁降低覆盖率下限、删除或弱化断言、增加应用代码排除项。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
