# ZEN-38 — Book bootstrap and canonical StoryState v1

- Linear: [ZEN-38](https://linear.app/zenhungyep/issue/ZEN-38/implement-book-bootstrap-and-canonical-storystate-initialization)
- GitHub: [Issue #11](https://github.com/autism-ip/novelops-agent-harness/issues/11)
- Branch: `codex/zen-38-book-bootstrap`; review base: ZEN-37 [PR #31](https://github.com/autism-ip/novelops-agent-harness/pull/31).

## Goal and delivered behavior

Bootstrap one Book and one canonical StoryState v1 from a currently approved opportunity and selected title/cover chain. The service resolves immutable source artifacts through the existing domain guards, validates exact submitted IDs, derives stable business IDs, and projects eight explicit state namespaces. It uses the Kernel writer and intent journal to recover an interrupted Book/Artifact/StoryState sequence without duplicate records. Book and state APIs expose version, hash, source refs, and timestamps. The product UI supports creation from a selected cover, Book list/detail views, and exact-body retry after an uncertain response. Legacy Books remain readable with `state: null`; no new AgentStates are written.

## Design and modules

`backend/app/books.py` owns bootstrap and the canonical `StoryContextProvider`. Feishu table mapping and `StoryStatesRepo` add an additive table while retaining legacy fields. `backend/app/api/routes/books.py` exposes authenticated endpoints. `frontend/src/components/books` and `/books` provide the workspace. `PRODUCT.md` records the confirmed solo editor desktop-first use case and the user's binding iOS-inspired visual direction; the full existing-page visual replacement is tracked separately from this issue.

## Review and verification

| Evidence | Result |
| --- | --- |
| Backend non-live suite | 329 passed, 9 integration deselected; 92.62% coverage (87.82% required) |
| Backend static/package gates | Ruff passed; source and wheel distributions built |
| Frontend | 10 pure-state tests; ESLint, TypeScript and production Next build passed |
| Synthetic browser | Selected cover → Create book → Open book workspace → eight namespaces and source provenance visible; mobile navigation to Books and no horizontal overflow |
| Real Feishu test Base schema | [Synthetic test Base](https://fcnaul7kb1kf.feishu.cn/base/T8I6buCMoaiLB6srVBrc9i2jnph): StoryStates `tblsYdH22yFXPNty` and Books `tblDUwg0EPLjflGf` created; synthetic rows read back with numeric version 1, text hashes and refs |
| Impeccable detector | No findings on new Book UI targets |

The Feishu test Base check used `lark-cli` Base v3 under user identity. It confirms field schema and cells, **not** a live end-to-end run through the backend's Feishu runtime. The browser used synthetic HTTP storage and model outputs. Book initialization deliberately leaves unprovided story facts blank; later StoryArchitect/Chapter workflows own their evolution. The current UI's full visual redesign across existing pages belongs to a separate design issue/PR.

## Risks and follow-up

An interrupted initialization whose approved source is later superseded stays visible as `initializing` and requires manual reconciliation; the service will not commit stale canonical state. The Base provider has no transaction or atomic compare-and-swap, so production must preserve the intent journal, one writer, and backup/recovery procedures. Live Base/runtime migration and model quality need production-specific acceptance. Existing legacy Book records are readable but not automatically upgraded to StoryState.

The issue/PR workflow has already been captured in the reusable `issue-pr-delivery` skill; this task did not create another skill because Book bootstrap is domain-specific.
