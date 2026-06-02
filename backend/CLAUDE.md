# backend/
> L2 | 父级: ../CLAUDE.md

成员清单
pyproject.toml: Python 项目元数据与依赖门禁，定义 FastAPI/pytest/httpx 运行边界。
.env.example: 本地环境变量样例，只放占位符，不承载真实密钥。
app/: FastAPI 应用实现 — 工厂函数、配置、中间件、路由。
tests/: 行为级 pytest 门禁，验证 ZEN-28 验收契约而非仅验证进程可启动。
app/api/: FastAPI 路由层——中间件守卫（deps.py）、端点注册（routes/__init__.py）、健康探活（routes/health.py）、管线端点（routes/pipelines.py）。
app/feishu/: 飞书 Bitable 集成层——HTTP 客户端（client.py）、16 表配置（table_map.py）、16 个具体 Repository + 工厂（repositories/）。
app/pipeline/: 流水线引擎——数据模型（models.py）、编排器（engine.py）、lease-based worker 执行循环（worker.py）。

架构决策
`app.main:create_app(settings)` 是唯一入口；模块级 `app` 通过 `__getattr__` 延迟创建。`Settings` 字段全小写，pydantic-settings 自动映射大写环境变量。密钥只进入 Settings 与 app.state，禁止出现在响应体。`/api/system/health` 与 `/api/system/status` 公开可探活，`/api/system/config` 需鉴权，其余 `/api/*` 先过 `x-api-key`。

依赖边界
`tests/` 是语义边界：它描述未来实现必须满足的外部行为。实现代码不得通过改弱测试来过关，只能让真实行为匹配测试。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
