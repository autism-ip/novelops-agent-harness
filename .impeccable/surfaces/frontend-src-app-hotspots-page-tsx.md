---
version: 1
slug: "frontend-src-app-hotspots-page-tsx"
primary_target: "frontend/src/app/hotspots/page.tsx"
related_targets: ["frontend/src/app/page.tsx","frontend/src/app/books/page.tsx","frontend/src/app/books/[bookId]/page.tsx","frontend/src/app/pipelines/page.tsx","frontend/src/app/agents/page.tsx"]
---

Scope: ZEN-107 replaces the visual system across the current NovelOps web app and establishes conventions for future book/chapter pages. Mode: Operate.
Audience and task: a solo web-novel author/editor reviews hotspots, approves opportunity/title/cover decisions, opens books, and checks system status during long desktop sessions; mobile is for status and light approval.
Approved composition: .impeccable/mocks/zen-107-b-review-split.png, chosen by the user on 2026-09-29. Use a compact top navigation and a list/detail split on desktop, with focused single-column progression on mobile. The mock's names, counts, book cover, manuscript actions, and sample data are illustrative only.
Visual world: cool pearl and blue-gray canvas, opaque or gently translucent floating chrome where useful, deep ink type, cobalt actions, soft offset depth, generous rounded cards, precise dividers, system sans, and restrained motion.
Implementation inventory: navigation and icons—semantic HTML plus lucide icons; hotspot list and right review surface—semantic HTML/CSS; cards, controls, status, focus—CSS tokens/components; source provenance—real API data; image-native region—none retained from mock; primary action—existing exact approval/creation actions; responsive behavior—top navigation desktop, bottom navigation mobile, modal detail on narrow screens; reduced motion—CSS preference.
Constraints: preserve workflow, exact retry, approval and provenance semantics. Do not add unimplemented routes or fabricated product data. Maintain keyboard access, contrast, status/error/empty states, and 44px mobile targets.
