# 2026-10-17 原生启动、正文度量与审稿边界

**整项目仍未完成，目标保持 active。** 全部 13 个 issue 及原有独立 PR、真实需求事件、Review 和全部适用覆盖率 100% 仍在范围内。本报告接续 [显式编辑消息报告](2026-10-16-explicit-editor-messages.md)，更正其中“配置缺陷未修复”和“正文链运行中”的旧状态。

## 已交付代码与原 PR

| Issue / PR | 本轮实现与验证 |
| --- | --- |
| ZEN-104 / [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24) | 统一 Settings 与表映射配置来源；5 项配置回归，所属分支 303 项测试通过，并逐分支验证和同步全部后续 PR。 |
| ZEN-40 / [#36](https://github.com/autism-ip/novelops-agent-harness/pull/36) | 完整原始约束与实际事件/时间证据合同；再加入由实际正文计算的码点、汉字数及明确范围。Critic v5 / Rewrite v6 保持公共 API 与输出 schema。所属分支 531 项测试通过。 |
| ZEN-41 / [#37](https://github.com/autism-ip/novelops-agent-harness/pull/37) | 22 项审核完整性测试与 11 项前置依赖/URL 目标绑定测试；损坏、过期、未配置或重复冲突时明确拒绝，验证零写入/零新增模型调用。同步全部章节修复。 |

表配置显式映射防御性复制，缺失值不混用环境回退；未传映射的旧接口保持兼容。测试覆盖配置文件优先级、进程覆盖、19 张注册表字段和多实例隔离。用户主工作区及密钥文件未修改。

## 真实需求事件及保留失败

使用已授权的[合成飞书 Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph)和真实 DeepSeek deepseek-flash，关闭 thinking、零供应商重试。预检与每次原生探针使用同一不可变源码；13 张启用表无缺失字段。

1. 前一轮章节 v6：已完成归还、低语和失忆，但铜钥匙条目在夜间提前出现，尸体位置语句冲突，正文 2386 汉字。独立审阅失败，未批准/锁稿。
2. 原生 v7：正常文件配置启动成功，不注入 FEISHU 表进程变量，启动前零模型调用；实际 create_app lifespan 启动单调度器，通过 API 发起退修，无直接 kernel.tick。启动恢复约 166.95 秒，命令约 151.99 秒，完整探针约 747.89 秒。
3. v7 的归还、主动支付、遗忘、七年设定、次日黎明与尸体安葬措辞已改善；但正文实测 2113 汉字，超过明确 1800 上限，Critic 仍误称“约1500字”并 pass。原生运行停在 awaiting_approval；独立后置断言失败。两次真实模型调用，保留 300 条合成记录且快照无失败；进程终止后写锁可获取，未批准或锁稿。
4. 为该问题加入确定性正文计数，范围为 U+4E00..U+9FFF，不含标题、标点、空白和 emoji；同时提供总码点数。计数取自实际当前/上一版 Artifact，叙事中的同名文字不能覆盖。不是全语言词数，也不是 token 数。
5. 对同一 2113 汉字稿的第一次度量诊断识别到超限，但原响应漏了数组结束符，finish_reason=stop；严格 schema 拒绝，原响应与请求哈希保留。没有修补 JSON 或放宽断言。
6. 一次明确记录的相同请求复核（哈希不变）产生 schema 合法的 revise 和压缩建议，但把编辑要求中引用的旧尸体错误句当成当前正文。独立结论仅为 partial；共两次诊断调用，零飞书/业务写入，不能作为业务完成证明。

7. 后续原生 v8 捕获状态：**running**，源码 `0fb29c10412fa26be4fed3c8445490ed0feb60c9`，已观察模型调用 1。保留原要求，补充已测 2113 字与压缩目标；硬范围仍为 1400–1800。未据进行中状态声称审批或锁定完成。

## 测试、覆盖率与边界

- 完整后端：**587 passed, 10 deselected, 1 warning in 164.58s (0:02:44)**；Ruff 通过。10 项需要真实凭据的可选集成测试未混入离线套件；真实探针单列。
- 后端 Statement/Line：**4087/4303 = 94.98%**；Branch：**966/1132 = 85.34%**；原始函数入口 **410/422 = 97.16%**，lambda 11/11。
- 全前端：24 文件、239 项测试通过；Statement 92.67%、Line 95.08%、Function 91.4%、Branch 93.02%。本轮未修改前端 UI；已有桌面/手机截图是历史证据，不冒充本轮新浏览器验收。
- **全部适用覆盖率 100% 尚未达到。** 未新增排除、降低门槛、删除有效测试或弱化断言。原始函数报告仍包含 7 个 Protocol 声明和 5 个实际未进入函数；完整名单见 JSON，未调用空声明刷覆盖率。
- 度量测试先出现 6 项缺少指标的失败；修复过程中局部变量引用与测试输入末尾空白规范化的设置差异分别修正。保留精确计数、完整约束和不可变历史断言。
- 两个新增队列合同回归证明 Critic/Rewrite 合同变更时旧任务阻塞，零模型调用、零新生成产物，冻结请求与精确重放不变。

## 交付清单、审阅与剩余工作

| Issue | PR | 捕获 head | 基分支 |
| --- | --- | --- | --- |
| ZEN-105 | [#23](https://github.com/autism-ip/novelops-agent-harness/pull/23) | `6f29fba50144` | `main` |
| ZEN-104 | [#24](https://github.com/autism-ip/novelops-agent-harness/pull/24) | `f555fd922d01` | `codex/zen-105-storage-provider` |
| ZEN-106 | [#25](https://github.com/autism-ip/novelops-agent-harness/pull/25) | `ef7a51ccb01a` | `codex/zen-104-harness-kernel` |
| ZEN-33 | [#27](https://github.com/autism-ip/novelops-agent-harness/pull/27) | `554cf6dfb7ca` | `codex/zen-106-model-artifacts` |
| ZEN-34 | [#28](https://github.com/autism-ip/novelops-agent-harness/pull/28) | `381b8b78e46d` | `codex/zen-33-hotspot-ingestion` |
| ZEN-35 | [#29](https://github.com/autism-ip/novelops-agent-harness/pull/29) | `2a6d1b9fb21e` | `codex/zen-34-hotspots-page` |
| ZEN-36 | [#30](https://github.com/autism-ip/novelops-agent-harness/pull/30) | `114d00fcada2` | `codex/zen-35-opportunity-research` |
| ZEN-37 | [#31](https://github.com/autism-ip/novelops-agent-harness/pull/31) | `6876e88f4153` | `codex/zen-36-title-cover` |
| ZEN-38 | [#32](https://github.com/autism-ip/novelops-agent-harness/pull/32) | `75f71e2a4228` | `codex/zen-37-approval-ui` |
| ZEN-107 | [#34](https://github.com/autism-ip/novelops-agent-harness/pull/34) | `87860c90468e` | `codex/zen-38-book-bootstrap` |
| ZEN-39 | [#35](https://github.com/autism-ip/novelops-agent-harness/pull/35) | `aa0892bfda1f` | `codex/zen-107-ios-design` |
| ZEN-40 | [#36](https://github.com/autism-ip/novelops-agent-harness/pull/36) | `4ddcd7ad7b17` | `codex/zen-39-story-planning` |
| ZEN-41 | [#37](https://github.com/autism-ip/novelops-agent-harness/pull/37) | `954f015cea14` | `codex/zen-40-chapter-loop` |

合并顺序沿现有直接依赖：23 → 24 → 25 → 27 → 28 → 29 → 30 → 31 → 32 → 34 → 35 → 36 → 37。没有新建重复 PR，也未合并 GitHub PR 或部署。当前捕获的全部 inline thread 均已解决，无新增 review/comment；每个捕获 head 的检查明细见 JSON。新代码/报告提交后的 CI 必须再次按实际 head 核验，不能引用旧绿色作当前证明。

尚需：v8 独立审阅与合格后的真实选择性审批/final-lock、常规自动通过事件、逐 issue 最终需求审计、Critic 引用旧示例的证据可靠性、启动/读写延迟预算、全部适用覆盖率 100% 与最终 review/安全合并检查。启动耗时是单次观察，未用它宣称普遍性能收益。模型成本按配置价格估算，不是供应商账单。

复用 issue-pr-delivery、TDD、security-review；既有完整约束、不可变源码、独立审阅和有界诊断规则继续适用。本轮不为单个计数字段新造 Skill。详细 JSON 区分原生事实、诊断观察和未完成事件；合成数据保留/链接共享沿用用户明确授权，不发布任何密钥或测试 API nonce。
