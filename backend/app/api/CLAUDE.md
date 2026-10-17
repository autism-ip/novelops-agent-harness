# app/api/
> L2 | 父级: ../CLAUDE.md

成员清单
__init__.py: 空包标记。
deps.py: FastAPI 依赖注入辅助函数（get_settings）。
middleware.py: APIKeyMiddleware，基于 app.state.settings 鉴权，公开路径走白名单。
routes/: 路由注册表与端点实现。

routes/ 成员
research.py: ZEN-35 研究 context、批量触发、历史与精确步骤/产物审批接口。
creative.py: ZEN-36 标题候选与封面规划 context、历史、选择及 selected 消费接口。
books.py: ZEN-38 Book bootstrap context、创建/恢复、列表和 canonical StoryState 读取接口。
story_planning.py: ZEN-39 StoryBible 与 ChapterBrief 的版本上下文、提交、历史、人工审批及消费资格接口。
chapter_loop.py: ZEN-40 章节生成上下文、精确来源命令、版本历史和最终锁定接口。
workflows.py: 通用 Harness 工作流查询与创建入口，拒绝绕过领域校验创建 Book 与规划工作流。
__init__.py: api_router 注册中心，挂载 system_router 和 pipelines_router。
system.py: GET /system/health（探活）、GET /system/status（版本+运行态）、GET /system/config（配置快照）。
pipelines.py: POST /pipelines（创建流水线）、GET /pipelines/{id}（流水线状态+步骤）、GET /pipelines/{id}/steps（步骤列表）。依赖 PipelineEngine + FeishuBitable repos。

架构决策
中间件从 app.state.settings 读取密钥，不依赖模块级单例。公开端点（/api/system/health, /api/system/status）通过 PUBLIC_PATHS 白名单豁免鉴权。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
