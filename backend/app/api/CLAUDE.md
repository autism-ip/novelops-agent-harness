# app/api/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 空包标记。
deps.py: FastAPI 依赖注入辅助函数（get_settings）。
middleware.py: APIKeyMiddleware，基于 app.state.settings 鉴权，公开路径走白名单。
routes/: 路由注册表与端点实现。

架构决策
中间件从 app.state.settings 读取密钥，不依赖模块级单例。公开端点（/api/system/health, /api/system/status）通过 PUBLIC_PATHS 白名单豁免鉴权。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
