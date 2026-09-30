# ZEN-36 — 标题候选与封面规划交付报告

## 目标与交付单元

- Linear：[ZEN-36](https://linear.app/zenhungyep/issue/ZEN-36/implement-title-and-cover-planning-workflow)
- GitHub：[Issue #9](https://github.com/autism-ip/novelops-agent-harness/issues/9)
- 分支：`codex/zen-36-title-cover`；直接依赖 [PR #29](https://github.com/autism-ip/novelops-agent-harness/pull/29)；本 issue 由独立 PR 交付。
- 产品目标：从已批准的机会版本生成至少 10 个标题候选，选择标题后生成至少 3 个封面方向，结果可见且可准确选择。

## 实际实现

1. `CreativeService` 两段工作流复用共享 Kernel、ModelRouter、SemanticRuntime、ArtifactStore 和审批事件；无新增长期 Agent 状态。
2. 标题集合与候选逐项保存不可变 Artifact；封面集合与方向逐项保存 Artifact。每个产物关联来源、模型、prompt、hash、工作流/步骤和版本。
3. 确定性 schema 和重复/风险检查在模型集合落库前执行；失败经过有界模型重试后终止，不能产生可选候选。
4. 选择事件包含精确的 `step_id`、输出版本、候选 Artifact ID；旧版、被拒绝或上游机会过期的结果不能由 selected 契约供 #11 消费。
5. Feishu TitleCandidates 与 CoverPlans 投影，接口提供版本 context、触发、历史、选择、退修和 selected 读取。
6. 热点详情展示标题比较、分数、风险说明与封面方向/提示词；可直接选择。页面保留未知结果的原请求重试载荷。

## 设计判断与风险

- 下游只接收已批准机会；封面只接收已选中的标题，且两层源版本必须保持当前。
- 显式版本使重放幂等，修改同版输入冲突；模型路由或 prompt 更改时待执行版本阻止继续。
- 人工选择只写一个候选 ID。未选项保留在历史中，可审阅但不能冒充 selected。
- 规则仅筛查明显重复、联系方式和少量敏感词。它不能证明标题市场表现、版权/商标安全或封面内容完全合规。
- 飞书投影非跨表事务；以 Artifacts、步骤、审批事件和 intent journal 恢复。生产级 Base v3/应用凭据与容量验证仍依赖 #23。
- UI 覆盖选择；完整编辑审批工作台仍属于 ZEN-37/#10。图片生成不在本 issue 范围。

## 验证

| 检查 | 证据 |
| --- | --- |
| 后端行为 | 十标题、三封面、重复/数量不足/敏感标题拒绝、失败不落库、版本与旧选择失效、退修输入、API 鉴权、命名空间防占用通过 |
| 全量本地回归 | 322 passed、9 live/integration deselected；应用覆盖率 92.89%，高于仓库硬性门槛；创作工作流、生产接线及评审回归通过 |
| 浏览器产品路径 | 生产 Next + 真实 FastAPI/Kernel + 合成模型/飞书 HTTP：批准机会 → 页面展示 10 标题 → 选择第 1 个 → 页面展示 3 封面方向 → 选择第 2 个；页面 pending 已清空 |
| 静态与构建 | Ruff、ESLint 零警告、TypeScript、Next 生产构建均通过 |
| 实际模型、Base v3 | 未验证；不能把合成夹具算作真实质量/部署验收 |

CI 与 Review 状态以 PR 最新 SHA 为准；测试 Base 和合成夹具不能替代真实模型质量或生产容量验收。

评审修复：移除重复的飞书表 ID 环境变量；未选候选使用 schema 支持的 `rejected`，精确选择仍由 ApprovalEvent 的 `choice_id` 表达；封面模型输入引用包含机会 Artifact；通用工作流拒绝研究与创作的未来版本命名空间；拒绝和退修不得附带候选 ID。

## 可复用性与下一步

复用并检验 `issue-pr-delivery` 流程、TDD 与 `ego-browser`。标题和封面的版本与精确选择已经抽象在现有 Kernel/Artifact 契约中，无需新增类似技能。下一步为 PR 审阅、真实模型评测、前置 #23 存储验收，以及 ZEN-37 编辑审批 UI 和 #11 选定版本消费。
