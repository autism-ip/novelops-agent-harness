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

`src/components/books/book-bootstrap.tsx` 从批准来源创建书籍；检查 Books 后的本地清除失败显示原因和恢复指引，并保留原请求，恢复存储后可再次清除。

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


