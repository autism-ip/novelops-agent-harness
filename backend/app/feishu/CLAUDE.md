# app/feishu/
> L2 | 父级: ../../CLAUDE.md

成员清单
__init__.py: 包入口，重导出 FeishuClient、FeishuAuthError、TABLE_NAMES、FIELD_MAPS、TableMapConfig。
client.py: 同步飞书 HTTP 客户端，自动管理 tenant_access_token 获取/刷新，401 自动重试，业务码非 0 抛 FeishuAuthError。
table_map.py: 16 张 Bitable 表的名称映射（TABLE_NAMES）、字段映射（FIELD_MAPS）、运行时配置类（TableMapConfig）。
repositories/: 16 个具体 repository + 工厂，继承 BaseRepository 并添加领域查询方法。详见 repositories/CLAUDE.md。

架构决策
client.py 使用同步 httpx 而非 lark-oapi SDK——减少依赖层级，直接控制认证与重试语义。table_map.py 支持环境变量覆盖表 ID，适配多环境部署。repositories/ 包含完整的 CRUD 基类与 16 个领域 Repo，工厂函数 create_repositories 一次性组装全部实例。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
