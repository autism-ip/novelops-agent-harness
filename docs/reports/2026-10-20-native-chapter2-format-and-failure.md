# ZEN-39/40/41：真实第二章规划与失败边界验收

日期：2026-10-20。归属原[PR35](https://github.com/autism-ip/novelops-agent-harness/pull/35)，继承至PR36、37。**实际章节目标未达成，生产代码未改。**

## 目标与实际结果

当前canonical StoryState v2、已定稿第一章v9和完整写作方向，应生成合格第二章，并由结构化Critic与策略决定是否自动通过。本轮原生后端使用已通过818项测试的 `c270db45d241e457cc6ba19f07dd3c134381d0af`，app树 `88b2cf4d2300fedeb016e38c45b232f4346e789c`。

- 新规划v2独立验收通过，五字段句数2/1/1/2/1；原付费v1与其格式失败审查保留。完整954字符方向、v9正文和来源在实际Writer/Critic外发中均精确核对，证明此前方向传播修复已实际生效。
- Writer正文996汉字、1181codepoints，来源/投影/原响应一致，但独立内容审查拒绝：支付后仍知道“话里有个邮差”；结尾新记录缺归还期限。另有“多了两个字：限今日午前”的数量不符、格栅空间位置不清。长度合格不代表内容合格。
- Critic HTTP200、finish=stop，却返回无效JSON：`Extra data`，第1行第1521列，constraints被放到已关闭的顶层对象之后。其原文虽写pass，后端严格校验为SchemaFailure；没有生成有效CriticReport。Critic步骤failed，Rewrite/final_verify未运行，review gate为cancelled，草稿保留为candidate；**routine自动通过为False**。
- 原生观察进程退出0、scheduler停止，表示观察/收尾完成；业务工作流仍failed。未修补模型JSON、手改正文、代批或终锁。

## 付费输出、保留与精确重放

已授权[测试Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph)中，417→426（规划新增9，旧417不变）→443（章节新增17，旧426不变）→444（诊断新增1，旧443不变）。原第一章v9、旧Artifact、canonical v2保持原样。9个新增Artifact内容哈希独立重算一致。规划/章节API命令重放均0新增模型、0写入。

无效付费Critic响应保留为 `AR-205d981f2e957fe26c5c9f07a5db472b` / `RejectedModelResponseEvidence`，内容含实际HTTP信封、原始无效assistant文本、响应/请求指纹和失败trace。步骤ID与实际Critic StepRun交叉核对；没有伪造成功model_trace_id绑定，也没有把诊断当作业务CriticReport。诊断精确重放不新建、不改写。

本轮新增3次真实模型（规划、Writer、Critic），连同此前v1规划共4次，0自动重试，原授权已用完。四次共32979输入/2907输出token；配置估算0.0133821，不是账单。Writer/Critic本轮19366输入/2201输出token，失败Critic的已知usage也被记录。

## 门槛、观察器失败与复用

原PR35/36/37准确源码完整门槛689/762/818项及Ruff通过，10项可选集成未纳入离线命令、1条既有警告。本轮未改app/tests/前端/配置，复用同树结果；原生完整流程只在PR37组合源码执行。全后端Statement/Line4282/4418（96.92%）、Branch1080/1186（91.06%），独立命名入口403/408；前端同树343项和94.69/97.14/94.69/95.11%。**全项目四项100%仍未达到**，门槛、ignore、业务断言未降低。

诊断观察器首次在写入前主动停止以纠正traceID/StepRunID混用，0写入；第二次把既有投影的只读ensure误判为新增而停止，0写入；两次都核验旧443不变。第三次复用已验证守卫，既有ensure强制allow_create=False并与基线完全相等，仅白名单诊断Artifact可新建，成功后旧443不变。原日志保留，不把观察器问题当产品缺陷。

既有issue-pr-delivery Skill按skill-creator窄幅补充两条：复用只读ensure保护器；跨阶段共享模型额度，以及失败响应/实际StepRun/trace/有效业务产物的区分。quick_validate通过；实际单Artifact保留、零模型、重放、旧记录一致和并发预算保护支持这些规则。

## 剩余验收与后续动作

原13项、61条Linear验收、51条GitHub原有附加检查及完整Scope/用户约束继续核对，未完成最终审计。计划v2格式已解决，第二章正文质量及真实routine事件仍未达成；剩余覆盖率继续。

已准备后续新规划v3的具体预览及修订方向；追加最多4次（全局总上限8）是**待用户授权的提案**，当前额度仍4且已用完，未发送新请求。新结果应追加版本并保留所有失败证据；未合并main、部署或标Done。发布后的准确head CI/review另核。
