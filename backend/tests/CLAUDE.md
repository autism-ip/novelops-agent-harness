# tests/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: pytest 包标记。
conftest.py: 测试环境与 AsyncClient 夹具（pytest_asyncio.fixture），隔离环境变量。
test_system_endpoints.py: 系统端点行为门禁，验证响应形状、占位状态与不泄密。
test_api_key_guard.py: API key 中间件行为门禁，验证公开端点豁免与私有 API 拦截。
test_acceptance_contract.py: ZEN-28 验收门禁，验证配置失败清晰、应用可导入、布局符合计划。
test_api.py: 集成测试，验证系统端点与 API key 鉴权的 TestClient 行为。
test_feishu_client.py: FeishuClient 行为门禁，验证 token 生命周期、Bearer 注入、401 重试、token-invalid 重试与异常路径（14 用例）。
test_base_repository.py: BaseRepository 行为门禁，验证 Python↔Feishu 字段映射、CRUD + 分页操作、字段过滤与业务键查找（22 用例）。
test_table_map.py: table_map 完整性门禁，验证 16 表配置数量、映射对应关系、环境变量 fail-fast（16 用例）。
test_domain_exceptions.py: 异常层级门禁，验证 FeishuError 家族继承关系与 code 属性（6 用例）。
test_token_retry.py: token 重试门禁，验证 99991663/99991668 触发清 token + 重试一次（3 用例）。
test_config_failfast.py: 配置 fail-fast 门禁，验证缺失环境变量时 get_table_id 抛 ValueError（4 用例）。
test_step_status_recordid.py: record_id 门禁，验证 _from_feishu/get/create 均携带 record_id（3 用例）。
test_pipeline_engine.py: PipelineEngine 行为门禁，验证 create/get_runnable/complete/fail/rollback/validation 生命周期（15 用例）。
test_worker_loop.py: WorkerLoop 行为门禁，验证 claim/lease/expired/poll/execute/retry 逻辑（17 用例）。
test_step_runs.py: StepRunsRepo 行为门禁，验证 claim_step 业务键→record_id 解析与 find_by_pipeline 字段过滤（4 用例）。
test_pipeline_api.py: Pipeline API 端点门禁，验证 POST 创建、GET 查询、404 处理（5 用例）。
test_feishu_integration.py: 飞书集成门禁（需真实凭证，CI 跳过）。

架构决策
测试以 BDD 验收行为为中心：状态值必须精确、密钥不得回显、鉴权必须先于路由缺失返回。门禁允许当前实现缺失时失败；它的职责是定义合格线，而不是替实现兜底。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
