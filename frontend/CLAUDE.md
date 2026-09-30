@AGENTS.md

# frontend/
> L2 | 父级: /Users/zen/Desktop/project/novelops-agent-harness/CLAUDE.md

## 技术栈
Next.js 16.3.6 + React 19 + Tailwind CSS 4 + shadcn/ui + TypeScript

## 验证门禁
Node 24（`.nvmrc`）。`npm ci` 安装锁定依赖；`npm run check` 依次执行零警告 ESLint、`next typegen && tsc --noEmit` 和生产构建。`npm run lint:fix` 用于自动修复 lint。CI/CD 接入说明见 `../docs/ci-cd.md`。

`npm test` 验证日期过滤、未知结果重试身份和安全来源链接；CI 必须通过该门禁。`/hotspots` 使用已有会话代理，浏览器不配置后端密钥。新增组件位于 `src/components/hotspots/`；`docs/hotspot-product-page.md` 记录人工操作与浏览器验收步骤。

`src/components/hotspots/editor-identity.ts` 在会话内保存编辑者署名；研究、标题和封面决策共用它。`docs/approval-ui.md` 记录审批版本、退修和冲突行为。
`src/components/books/story-planning.tsx` 提供 StoryBible 审批与版本化章节 brief 工作台；`planning-state.ts` 校验待重放的精确命令。视觉规范以仓库根目录 `DESIGN.md` 为准，包含响应式圆角卡片与短时动效。
`src/components/books/chapter-generation.tsx` 提供 ZEN-40 章节生成、Critic 摘要、全版本历史与来源/模型细节；`chapter-state.ts` 校验待重放章节命令的 Book/章节/源版本身份。
`src/components/books/chapter-review-desk.tsx` 提供 ZEN-41 Book 内章节审阅台：正文与历史、Critic/Verifier、批准/拒绝/退修/终锁、选择性人工关卡和折叠的来源/模型细节；切换 Book/章节时由 `chapter-generation.tsx` 的 key 重置本地审阅表单；`review-state.ts` 校验待重放命令的精确版本身份。

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
