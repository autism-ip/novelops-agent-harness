# tests/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: pytest 包标记。
conftest.py: 测试环境与 AsyncClient 夹具（pytest_asyncio.fixture），隔离环境变量。
test_system_endpoints.py: 系统端点行为门禁，验证响应形状、占位状态与不泄密。
test_api_key_guard.py: API key 中间件行为门禁，验证公开端点豁免与私有 API 拦截。
test_acceptance_contract.py: ZEN-28 验收门禁，验证配置失败清晰、应用可导入、布局符合计划。
test_api.py: 集成测试，验证系统端点与 API key 鉴权的 TestClient 行为。
test_feishu_client.py: FeishuClient 行为门禁，验证 token 生命周期、Bearer 注入、401 重试与异常路径（13 用例）。
test_base_repository.py: BaseRepository 行为门禁，验证 Python↔Feishu 字段映射与 CRUD + 分页操作（15 用例）。
test_table_map.py: table_map 完整性门禁，验证 16 表配置数量、映射对应关系、环境变量覆盖（16 用例）。

架构决策
测试以 BDD 验收行为为中心：状态值必须精确、密钥不得回显、鉴权必须先于路由缺失返回。门禁允许当前实现缺失时失败；它的职责是定义合格线，而不是替实现兜底。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
