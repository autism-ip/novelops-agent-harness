# ZEN-107 — Responsive NovelOps frontend

- Linear: [ZEN-107](https://linear.app/zenhungyep/issue/ZEN-107/redesign-novelops-frontend-with-an-ios-inspired-responsive-visual)
- GitHub: [Issue #33](https://github.com/autism-ip/novelops-agent-harness/issues/33)
- Branch: `codex/zen-107-ios-design`; review base: ZEN-38 [PR #32](https://github.com/autism-ip/novelops-agent-harness/pull/32).

## User direction and delivered behavior

The user selected composition B: a compact top navigation with the hotspot list and approval detail in adjacent desktop panes. The visual system uses a cool pearl background, slate text, a cobalt action color, rounded cards and controls, soft depth, and short transitions. At phone widths, navigation moves to a bottom bar and a selected hotspot opens in a focused detail dialog. The same system now covers Dashboard, Hotspots, Books, Pipelines, and Agents. Existing workflow behavior and source/version/provenance remain visible; the Dashboard points to real workflow pages rather than displaying fabricated zero metrics. The analysis summary, risk, and artifact ID precede the approval controls, with full analysis and provenance in an expandable section.

The design follows the confirmed solo author/editor use case: sustained desktop editing and light phone approvals. The book workspace presents the canonical StoryState namespaces without inventing book content. `DESIGN.md` and `.impeccable/design.json` record the built system for later pages.

## Verification

| Evidence | Result |
| --- | --- |
| Frontend tests | 10 passed |
| Static and production gates | ESLint, TypeScript, Next production build passed |
| Impeccable detector | No findings on changed ZEN-107 targets |
| Independent Impeccable finish review | PASS after first-viewport decision layout revision |
| Desktop browser, 1440×900 | Hotspot list and detail visible together; approval button at y773–817 in first viewport; no horizontal overflow |
| Phone browser, 390×844 | Approval button at y740–784 in first viewport; real synthetic approval changed status to `approved`; all five routes fit viewport width |
| Book browser workflow | Selected approved title/cover → created and opened Book; eight canonical StoryState sections and provenance visible; final card clears fixed phone navigation after scrolling |

The browser acceptance used the repository's synthetic HTTP storage and model fixture. It verifies frontend interaction and responsive behavior, not live model quality or production Feishu access. The illustrative composition mocks under `.impeccable/mocks/` contain invented layout content; the shipped interface renders repository and API content only.

Screenshots: [desktop approval](assets/zen-107-desktop-approval.png), [phone approval](assets/zen-107-mobile-approval.png), and [phone book at page bottom](assets/zen-107-mobile-book-bottom.png).

## 2026-09-30 review follow-up

Resolved four Codex review findings on PR #34:

- The hotspot detail pane no longer sits inside an animated containing block. Its desktop position remains fixed while the document scrolls. The pane now layers above the sticky header, so its Close control remains clickable.
- A mounted detail dialog follows the 1024px breakpoint: modeless beside the list on desktop, modal with backdrop and Escape handling on phone/tablet. It retains the selected hotspot while switching modes.
- The five-item bottom navigation stays active through tablet widths; content gets matching bottom clearance. Desktop top navigation begins at 1024px.
- Both pending-request recovery notices use an explicit amber surface modifier, avoiding the Tailwind layer precedence conflict with the default white surface.

On the review head, 10 frontend tests, ESLint, TypeScript, and the Next production build passed. A local production build against the loopback synthetic fixture showed the desktop pane at viewport top 16px before and after scrolling 95px; at 820px it changed to a full-height modal and bottom navigation replaced the top links; at 390px the modal opened, Escape closed it, and document width stayed within the viewport. Returning to 1440px restored modeless mode. The Close button was the top hit target after the layer fix. The warning surface computed to `rgb(255, 251, 235)` with an `rgb(242, 194, 102)` border. This verifies the reviewed UI paths with synthetic data; it does not change the separate live-model or Feishu acceptance boundaries.
