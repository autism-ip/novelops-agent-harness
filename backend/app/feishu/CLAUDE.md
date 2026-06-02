# app/feishu/
> L2 | 父级: ../../CLAUDE.md

成员清单
__init__.py: 包入口，重导出 FeishuClient、FeishuError 异常族（FeishuAuthError/FeishuNotFoundError/FeishuAPIError）、TABLE_NAMES、FIELD_MAPS、TableMapConfig。
client.py: 同步飞书 HTTP 客户端，自动管理 tenant_access_token 获取/刷新，401 自动重试，token-invalid（99991663/99991668）清缓存重试，业务码非 0 抛类型化异常（FeishuNotFoundError/FeishuAPIError）。
table_map.py: 16 张 Bitable 表的名称映射（TABLE_NAMES）、字段映射（FIELD_MAPS）、运行时配置类（TableMapConfig），get_table_id 缺失环境变量时 raise ValueError。
repositories/: 16 个具体 repository + 工厂，继承 BaseRepository 并添加领域查询方法。详见 repositories/CLAUDE.md。

架构决策
client.py 使用同步 httpx 而非 lark-oapi SDK——减少依赖层级，直接控制认证与重试语义。异常层级：FeishuError → FeishuAuthError / FeishuNotFoundError / FeishuAPIError，允许调用方精确捕获。table_map.py 的 get_table_id 采用 fail-fast 策略，拒绝在缺失配置时静默回退。repositories/ 包含完整的 CRUD 基类与 16 个领域 Repo，工厂函数 create_repositories 一次性组装全部实例。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
