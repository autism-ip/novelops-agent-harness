@AGENTS.md

# frontend/
> L2 | 父级: /Users/zen/Desktop/project/novelops-agent-harness/CLAUDE.md

## 技术栈
Next.js 16.3.6 + React 19 + Tailwind CSS 4 + shadcn/ui + TypeScript

## 验证门禁
Node 24（`.nvmrc`）。`npm ci` 安装锁定依赖；`npm run check` 依次执行零警告 ESLint、`next typegen && tsc --noEmit` 和生产构建。`npm run lint:fix` 用于自动修复 lint。CI/CD 接入说明见 `../docs/ci-cd.md`。

`npm test` 在 Vitest 中执行原有行为断言和组件测试；`npm run test:coverage` 使用 V8 对所有 `src/**/*.{ts,tsx}`（含未导入文件）报告语句、行、函数和分支覆盖率。CI 必须通过现有门禁。`/hotspots` 使用已有会话代理，浏览器不配置后端密钥。代理仅接受字母、数字、下划线和连字符组成的路径段，以防 URL 归一化改变后端目标路径。登录签名配置缺失时返回 503；密码错误显示明确提示。新增组件位于 `src/components/hotspots/`；`docs/hotspot-product-page.md` 记录人工操作与浏览器验收步骤。

`src/components/hotspots/editor-identity.ts` 在会话内保存编辑者署名；研究、标题和封面决策共用它。`docs/approval-ui.md` 记录审批版本、退修和冲突行为。
`src/components/books/story-planning.tsx` 提供 StoryBible 审批与版本化章节 brief 工作台；从读取上下文起锁定操作并显示准备进度，防止重复生成；检查历史后的清除失败保留精确请求并显示存储恢复指引；`planning-state.ts` 校验待重放的精确命令。视觉规范以仓库根目录 `DESIGN.md` 为准，包含响应式圆角卡片与短时动效。
`src/components/books/chapter-generation.tsx` 提供 ZEN-40 章节生成、Critic 摘要、全版本历史与来源/模型细节；读取上下文起锁定操作并显示准备进度；检查历史后的本地清除失败保留精确命令和存储恢复指引；`chapter-state.ts` 校验待重放章节命令的 Book/章节/源版本身份。

`src/components/books/book-bootstrap.tsx` 从批准来源创建书籍；检查 Books 后的本地清除失败显示原因和恢复指引，并保留原请求，恢复存储后可再次清除。
`src/components/books/chapter-review-desk.tsx` 提供 ZEN-41 Book 内章节审阅台：正文与历史、所读版本 Artifact ID、Critic/Verifier、批准/拒绝/退修/终锁、选择性人工关卡和折叠的来源/模型细节；切换 Book/章节时由 `chapter-generation.tsx` 的 key 重置本地审阅表单；`review-state.ts` 校验待重放命令的精确版本身份。实测飞书审稿读取和批准/终锁均超过十秒；审稿 GET 与精确版本 POST 使用 120 秒有界限时，覆盖完整响应正文。保存中显示等待状态，超时保留原命令供重放；检查历史后的本地清除失败显示错误并保留命令，恢复存储后可再次清除；代理声明 120 秒执行预算，部署平台实际限时仍需验收。其他浏览器请求保留默认十秒。

`src/app/books/[bookId]/chapters/[chapterNo]/review/page.tsx` 提供独立章节审稿入口，校验 Book 路径与 1–10000 的规范章节号；`focused-chapter-review.tsx` 只挂载同一真实审稿组件，不加载全书/Bible/Brief 历史或启动生成。章节生成区提供可发现链接，独立页保留返回书籍、手动刷新及精确审批/重放语义。`tests/focused-chapter-review.test.tsx` 使用真实 hook、ApiClient 和审稿台验证读取预算、关卡静默及版本绑定。

## 目录结构
```
src/
  app/           - App Router 页面与布局
    api/
      auth/login/route.ts  - POST /api/auth/login 签发 session cookie
      [...path]/route.ts   - catch-all 代理，验证 session 后注入 x-api-key
    globals.css  - NovelOps 珍珠白、石板色和钴蓝色视觉变量 + Tailwind v4 @theme
    layout.tsx   - 根布局，Geist 字体
    page.tsx     - 首页
  api/
    client.ts    - ApiClient 工厂 + 默认无 key 浏览器实例
  components/
    ui/          - shadcn/ui 组件（button, card, badge, table）
  lib/
    session.ts   - HMAC-SHA256 signToken / verifyToken
    utils.ts     - cn() 工具函数（clsx + tailwind-merge）
components.json  - shadcn CLI 配置（style: default, baseColor: neutral, cssVariables: true）
```

## shadcn/ui 主题
- Style: Default
- Base color: Neutral（oklch 色彩空间）
- CSS variables: 启用（:root + .dark 双主题）
- 支持 dark mode class 策略

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

## 创作请求原子性
工作台 `submit` 接受已准备请求或异步请求工厂：从读取上下文到持久化、POST、清理均持有同一锁，并显示 Preparing/Saving 状态。标题/封面历史未加载或读取失败时禁止生成；失败的上下文不产生保存意图或 POST。未知 POST 结果保留确切来源与版本，重载后重试不再读取上下文。实际工作台和 ApiClient 的 HTTP 边界回归见 `tests/creative-workbench-contract.test.tsx`。

ZEN-37 的研究退修和标题/封面反馈再生成均通过工作台异步请求工厂持有锁；保留编辑者、确切 Artifact/步骤/输出版本和原退修反馈。`creative-workbench-contract.test.tsx` 使用真实审批组件和原生 HTTP/Storage 边界，覆盖 risk/selection、拒绝、退修、来源失效、失败及重试。

热点详情打开时，Preparing/Saving 状态必须放在实际 `<dialog>` 内；手机模态框会使外部内容 inert。没有详情时状态显示在工作台。回归断言按当前对话框定位，延迟 HTTP 在断言前完成清理。

桌面热点详情面板从顶部导航下方开始（top-24 / bottom-4），自身滚动；不能遮挡全局导航。手机仍使用全屏模态框。视觉验收使用真实生产浏览器和确切 1280/390 视口，不仅检查 CSS 类。

热点工作台原生请求存储读取失败时禁止新建与重试，显式重查后恢复；清理失败保留原始字节、显示原因并释放操作锁，API 拒绝与清理失败并列呈现。已提交请求只重放原身份，不能重新构造命令。回归见 `tests/hotspots-storage-contract.test.tsx`。



批量研究 HTTP 201 的逐项失败不等于成功：成功 Run 保留，错误反馈向调用者返回；已知结果清理原意图，但本地清理失败时同时显示逐项业务原因与存储原因、保留精确重放清单。回归见 `tests/research-batch-contract.test.tsx`。


研究反馈再生成收到 HTTP 201 逐项拒绝时，`SubmitResult` 返回失败原因；当前手机对话框内必须显示该原因。已知未预留失败清理意图，不显示未知结果重试；如清理另失败，则仍保留精确身份与全部原因。

批量失败反馈由工作台保存并按热点 ID 传入 Detail；成功清理后的历史刷新会卸载子审批表单，因此不能仅依靠子表单局部错误状态。清理失败仍由未卸载的调用表单展示组合原因。

书籍创建的存储读取失败使用独立不可用状态，禁止写入；公开重查后恢复。读取上下文前后及 POST 完成后校验保存字节仍属于当前请求，避免覆盖或清除另一请求。有效未确认请求也可在检查 Books 后释放；操作中禁用清理，原生清理失败显示实际原因并保留字节。回归见 `tests/book-bootstrap-contract.test.tsx`。

planning 请求读存储失败时使用独立不可用状态与公开重查。提交前、异步上下文后、POST 完成后检查保存字节的所有权；变化或不可读时保留原数据并提示，检查历史后的清理也使用相同校验。原生 DOMException 清理原因可见，操作中禁用清理。回归见 `tests/story-planning-contract.test.tsx`。

chapter 请求读存储失败时使用独立不可用状态与公开重查。提交前、异步上下文后、POST 完成后检查保存字节的所有权；变化或不可读时保留原数据并提示，检查历史后的清理也使用相同校验。原生 DOMException 清理原因可见，操作中禁用清理。回归见 `tests/chapter-generation-contract.test.tsx`。

review 请求读存储失败时使用独立不可用状态与公开重查。提交前、异步上下文后、POST 完成后检查保存字节的所有权；变化或不可读时保留原数据并提示，检查历史后的清理也使用相同校验。原生 DOMException 清理原因可见，操作中禁用清理。回归见 `tests/chapter-review-contract.test.tsx`。
建书来源核验与幂等 POST 使用各自 120 秒客户端预算，与代理 maxDuration 对齐；超过预算仍保留原请求字节，必须由用户显式重试，不自动重发。测试覆盖实测量级的 23 秒读取、119 秒写入与有界超时恢复。该预算不是部署平台支持或可接受生产延迟的证明。

故事规划历史、上下文与写入采用各自120秒有界预算；轮询仍在上一请求结算后等待5秒，不按墙钟叠加。慢读取不提前中止并排队，提交仍保存同一来源与版本，超时不自动重新生成。

章节生成的上下文、精确触发、最新状态与 eligible brief 采用各自120秒有界请求；真实上下文曾耗时56.41秒。轮询等上一读取结算再等待5秒，终态停止规则不变。慢请求不重建命令或自动付费重试。

`tests/book-workspace.test.tsx` 经真实 Books/Book 路由、BookList/BookDetail 与 API 客户端验证空书架、旧书/初始化状态、编码链接、规范来源与规则展示、无 brief 时禁止生成及读取错误；仅替换 HTTP 边界，不模拟业务组件。
真实手机验收发现慢规划读取与5秒书籍轮询竞争。书籍详情改为读取结算后60秒再轮询，单次120秒有界，并提供原生 Refresh book；稳定或等待人工决策的规划历史停止空闲轮询，只有 creating/pending/running 保持5秒更新。新增 `book-read-budget.test.tsx` 和历史状态回归，慢运行测试继续严格验证不重叠及按时恢复轮询。

eligible brief 是只读来源，在空闲状态改为上一请求结算后60秒读取一次；Refresh chapter 仍立即刷新来源，不会自动生成或提交付费命令。运行中的 generation 状态保持5秒结算后更新，终态/人工门停止规则保留。
