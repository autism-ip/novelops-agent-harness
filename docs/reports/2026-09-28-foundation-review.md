# 基础 PR Review 修复分析报告

日期：2026-09-28（Asia/Shanghai）。本报告记录一次推进结果；整个项目目标仍在执行中。

## 目标与实际交付

核对 Linear v0.2 项目、现有 Issue/PR 和 Review，修复基础设施缺陷，并同步 main 新增的 CI 门禁。保持一个 Issue 对应一个 PR，没有新增重复 PR，也没有合并任何 PR。

| Issue | PR / 代码提交 | 本轮结果 |
|---|---|---|
| ZEN-105 / #21 | [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23), `84354bdb` | 同步 main `4706cf68`，保留质量门禁；仍为 Draft |
| ZEN-104 / #20 | [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24), `c6cc2618` | 修复 5 条 Review；6 个新回归用例 |
| ZEN-106 / #22 | [#25](https://github.com/autism-ip/novelops-agent-harness/pull/25), `e96bff72` | 修复 5 条 Review；19 个新回归用例，补充损坏 Artifact API 验证 |

依赖关系：#23 → #24 → #25。#24、#25 的目标分支仍是直接依赖分支，不能跳过 #23 的验收限制。

## Review、设计决策与主要模块

所有以下发现均经当前代码确认有效，修复已推送，相应 10 条线程已标记 resolved。未用“outdated”状态替代修复判断，也没有拒绝有效反馈。

| PR / Review comment ID | 问题 | 实现与验证 |
|---|---|---|
| #24 / 4115457137 | 远端记录顺序导致不确定调度 | `harness.py` 按稳定业务标识排序；反转存储返回顺序后仍以同样顺序执行 |
| #24 / 4115457140 | 失败父流程留下 pending/awaiting 兄弟步骤 | 取消非终态兄弟步骤，拒绝终态父流程的新审批；恢复时修复历史不一致 |
| #24 / 4115457143 | 公开状态查询全表扫描并占用 writer | 内存计数器随持久化成功更新、启动从 Feishu 重建；重复状态读取零远端调用 |
| #24 / 4115457145 | 返回值不可序列化触发重启后重复副作用 | 在执行保护边界内序列化，失败进入 blocked 且不增加重试；重启后调用次数仍为 1 |
| #24 / 4115457147 | handler 被移除后浪费执行重试 | dispatch 检测缺失 handler，阻塞等待配置协调；retry_count 保持 0 |
| #25 / 4115487986 | 非正常结束的 JSON 被接受 | `generation.py` 仅接受显式 stop；保留 length 截断分类；两种 provider 均验证过滤/工具调用/未知/空/缺失原因 |
| #25 / 4115487988 | 配置相同的逻辑 route 可错误重放 | 重放同时比较逻辑 route 和配置 hash；不额外调用模型 |
| #25 / 4115487995 | 外部修改内容仍沿用原 hash | `ArtifactStore.get` 校验 schema、稳定 ID、内容 hash；API 返回脱敏 409，不返回损坏内容 |
| #25 / 4115487997 | 环境变量样例缺少两张表 | `.env.example` 补充 Artifacts、Traces 表 ID 占位符 |
| #25 / 4115487999 | tracing 假设输出一定为字典 | 列表、字符串、空列表、false、0 保持原值；安全提取 output_refs；无效输出 trace 正确标记失败 |

内存计数器不是第二业务数据库；恢复时以 Feishu 为准。保持单进程、单 scheduler、单 writer 的部署约束。合并冲突保留两侧忽略规则；另发现并修复自动合并产生的重复 TOML 表定义和新增 lint 门禁发现的未使用变量/导入。

主要文件：`backend/app/harness.py`、`backend/app/generation.py`、`backend/app/api/routes/observability.py`、`backend/.env.example`、对应测试和 `backend/pyproject.toml`。

## 已验证事实

### 本地验证

使用 Python 3.13.12，隔离工具环境安装仓库固定的 Ruff 0.16.9、build 1.6.1、pytest-cov 7.1.0。

| 分支范围 | 离线测试 | 全 app 覆盖率 | Ruff |
|---|---:|---:|---|
| #23 | 179 passed | 88.42% | 通过 |
| #24 | 198 passed | 90.14% | 通过 |
| #25 | 238 passed | 91.20% | 通过 |

9 项 integration 测试依照现有 CI 的 `-m "not integration"` 被排除；未删除、修改标记或降低断言。保持既有 87.81558726673984% 覆盖率门槛。#25 generation 为 96.31%、kernel 为 94.57%、observability 为 100%。新增用例先观察到失败，再验证修复后通过。原有成功模型响应 fixture 增加显式 stop 字段以符合收紧后的真实契约。

执行命令（backend 目录）：

```sh
python -m ruff check app tests --no-cache
python -m pytest tests -q -m 'not integration' --cov=app --cov-report=term -p no:cacheprovider
python -m build --no-isolation --outdir /private/tmp/novelops-review-dist
python -m app.evals --output /private/tmp/novelops-review-evals.json
```

#25 sdist、wheel、离线 eval 全部成功，wheel 包含 eval fixture。存在本地 Starlette/httpx 弃用提示，不影响此次测试；未隐藏提示。未执行付费模型调用。

### 远端 CI

核对的是以下实际代码提交关联的 PR workflow，全部 conclusion=success：

- #23 `84354bdb`：[run 36339412841](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36339412841)
- #24 `c6cc2618`：[run 36339477088](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36339477088)
- #25 `e96bff72`：[run 36339668535](https://github.com/autism-ip/novelops-agent-harness/actions/runs/36339668535)

main 新增的 workflow lint、backend lint、Python 3.12 行为/覆盖率/包构建与安装 smoke、前端 lint/types/build、聚合门禁均保留。报告文档提交将具有另一个 head；上述结果明确只证明列出的代码提交。

## 工程判断

Review 中的具体缺陷已有直接回归证据，代码可以继续支持后续业务 Issue 开发。由于根依赖 #23 尚未完成实际 v3 运行路径及可行性验收，当前不能宣称整个 PR 栈已安全可合并或三个 Issue 已满足完整 Definition of Done。Linear 状态没有被改成 Done。

## 尚未验证、限制与风险

- #23 尚有 HTTP PATCH、删除、应用身份 Base v3 访问、容量/限流/冲突边界及 v1/v3 schema 兼容性缺口。当前生产 provider 仍使用 legacy Bitable 路径；CLI 用户身份成功不能证明后端应用身份可部署。
- 先前授权测试 Base 的证据继续保留；本轮未新增真实数据或执行破坏性 Base 操作。
- 9 项依赖真实环境的 integration 检查未运行；无真实模型质量、账单或生产 E2E 证据。离线 eval 的合成输出不是质量收益证明。
- 外部人工直接修改 runtime 状态后，公开缓存计数可能暂时陈旧；恢复会重建。计数不参与调度决策。
- 状态成功写入前发生进程退出/存储超时的通用副作用恢复仍依赖 handler 按稳定业务 ID 对账。不能把此次无效输出修复理解为跨系统 exactly-once 保证。
- Artifact hash 用于检测不一致，不是防恶意篡改签名。具备存储写权限的人若同时修改内容和 hash，超出此完整性校验边界。
- 未改变鉴权边界，错误响应没有泄漏原始损坏 payload；没有新凭据进入提交。不存在“CI 通过所以没有风险”的推论。

## Skill 沉淀与验证

已检查现有 `tdd-workflow`、`verification-loop` 和 `skill-creator`。前两者不覆盖跨 Linear/GitHub 的依赖 PR 同步与 Review 证据闭环，故新增个人 Skill `issue-pr-delivery`，安装于 `~/.codex/skills/issue-pr-delivery`。

适用：跨 Linear/GitHub 持续交付、依赖 PR、Review 修复和报告。复用方式：后续任务调用 `$issue-pr-delivery`。它只固化工具发现、issue/PR 映射、依赖传播、按提交核对 CI 和报告边界，不替代业务技能，不授予额外发布/合并权限。

验证：临时目录和安装后均通过官方 `quick_validate.py`；人工检查“main 新增门禁”“outdated Review 未修复”“CLI 成功但后端凭据缺失”三个实际场景的处理指引。没有修改现有 Skill、工具配置或安装 hooks；没有宣称完成独立 agent 前向评测。

## 后续可执行工作与技术债务

1. 继续 ZEN-33 / GitHub #6：复用现有 Douyin adapter 完成去重、持久化和可观察的抓取工作流；之后按依赖推进 ZEN-34–41，共 9 个业务 Issue。
2. 补齐 ZEN-105 的官方 Base v3 API/应用身份验证与 provider 实现，在同一个 #23 交付。
3. 后续业务 handler 必须证明副作用重放安全、Artifact 版本 provenance 和失败可见性，不能只复用基础测试结果。
4. 单调度器当前仍会扫描运行表；当实际记录量增长时，根据观测评估过滤/索引和归档策略。本次修复去除了公开 status 流量对扫描的放大。
5. 新模型角色或额外 pass 必须增加真实 eval 对比后再以质量/成本收益解释；当前人工修订率仍未知。

总目标保持进行中。本报告是基础 Review 修复阶段的证据，不是项目完成声明。
