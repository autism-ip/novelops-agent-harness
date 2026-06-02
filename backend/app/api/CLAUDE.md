# app/api/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 空包标记。
deps.py: FastAPI 依赖注入辅助函数（get_settings）。
middleware.py: APIKeyMiddleware，基于 app.state.settings 鉴权，公开路径走白名单。
routes/: 路由注册表与端点实现。

routes/ 成员
__init__.py: api_router 注册中心，挂载 system_router 和 pipelines_router。
system.py: GET /system/health（探活）、GET /system/status（版本+运行态）、GET /system/config（配置快照）。
pipelines.py: POST /pipelines（创建流水线）、GET /pipelines/{id}（流水线状态+步骤）、GET /pipelines/{id}/steps（步骤列表）。依赖 PipelineEngine + FeishuBitable repos。

架构决策
中间件从 app.state.settings 读取密钥，不依赖模块级单例。公开端点（/api/system/health, /api/system/status）通过 PUBLIC_PATHS 白名单豁免鉴权。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
