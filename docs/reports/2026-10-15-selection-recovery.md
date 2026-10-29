# Selection recovery and real workflow acceptance — 2026-10-15

## Requirement and delivery

[ZEN-36 / PR #30](https://github.com/autism-ip/novelops-agent-harness/pull/30) requires valid, versioned title/cover choices with persisted approval projection. [ZEN-39 / PR #35](https://github.com/autism-ip/novelops-agent-harness/pull/35) requires planning histories that retain exact sources and enforce current eligibility. [ZEN-41 / PR #37](https://github.com/autism-ip/novelops-agent-harness/pull/37) requires exact chapter review, constrained revision and final lock. These remain separate existing PRs; no merge, duplicate PR or Done transition occurred.

Production application source for this live run is an immutable copy of `0436b23806b22f99d19cda10ee16ac7f8c04c391`. Later synchronized commits change tests only. The primary checkout and credential file remain unchanged.

## Real event: committed title decision and partial projection

The previous real recovery restored 72 genuine DeepSeek/Feishu domain rows and independently checked exact equality. Its candidate read returned the same 20 artifacts in two native read-only queries, taking 2.925 seconds. The subsequent decision returned HTTP 503 `AmbiguousWrite` after the approval event, selection step and parent completion had committed. Candidate approval projection was only partly updated. This was not reported as an uncommitted decision or as a reason to regenerate titles.

That attempt made zero new model requests. All 73 attempted IDs, including the committed approval, were scoped for cleanup. Three deletes returned Feishu API errors; the separate verification client nevertheless found **zero remaining IDs in every collection**. This distinguishes ambiguous delete responses from residual data.

## Reproduction and exact replay contract

A new HTTP regression injects an external PUT failure after two projected candidates have updated. It proves:

- The first decision returns 503 and advertises reconciliation.
- The choice and parent completion are already durable, with exactly one approved candidate and some pending projections.
- A different candidate is rejected with 409.
- Repeating the exact same command returns 200 and completes one approved / nine rejected fixture rows.
- Approval records, immutable candidate artifacts and model-call history remain identical.

The existing production recovery logic passes this test; production behavior was not weakened or replaced. Owner commit: `2c15489439c0`. At the owning ZEN-36 branch, 441 offline backend tests passed. The test was then merged through every dependent PR with independent whole-backend and Ruff/diff gates: PR #31 441; #32 448; #34 448; #35 459; #36 476; #37 499. Each branch deselected 10 explicitly opt-in live integration tests; those are not claimed as passing.

## Real event: exact restoration and successful reconciliation

The next run restored the 73 previously captured genuine rows using eight official [Bitable v1 batch-create](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/batch_create) calls. All IDs were checked absent and journaled before their batch POST. There was no blind batch POST retry. The independent client then verified every domain row exactly matched its saved source. This is explicitly administrative restoration, not fresh generation or an uninterrupted workflow.

The recorded restore took 36.190 seconds; the previous per-record restore took 501.705 seconds. These are different attempts with administrative overhead, not a controlled production speedup benchmark.

The actual same title decision then returned **200**, in 193.587 seconds. Fresh Feishu projection reads confirmed **20 candidates: one approved and nineteen rejected**, with the approved artifact matching the original committed choice. Approval-event rows remained unchanged and there were still **zero new model requests**. The model-generated title data and its provenance were retained intact. This proves recovery of the actual interrupted selection event.

The current candidate read again used exactly two native search requests, this time taking 5.165 seconds. The difference from 2.925 seconds is retained; request savings are not described as a fixed elapsed-time improvement.

At this report snapshot, the real cover workflow has been reserved and is executing. Cover generation/selection, Book bootstrap, approved StoryBible, eligible brief, chapter generation, constrained immutable revision and final lock are still pending. No success is inferred from enqueueing a workflow or from its process remaining alive.

## Quality, coverage and review

Current final-branch backend: **499 passed**. Statements/lines: **3973/4260 = 93.26%**; branches and exact counts are in the JSON totals. The previous full function-entry run at the identical application source measured **403/419 = 96.18%**, including seven Protocol declarations; all 11 lambdas were entered. Function coverage was not remeasured for this test-only synchronization. Existing default Protocol exclusions remain explicitly visible. No new exclusion, disabled callback, skipped test, weakened assertion or reduced gate was introduced. **The required all-source 100% coverage remains unmet.**

Frontend source was unchanged. Its earlier 216-test/coverage result is historical evidence, not a fresh live frontend or deployed authorization check.

The complete current PR audit includes resolved/outdated threads, review submissions and discussion comments, with pagination checked. All 13 PRs have zero unresolved threads. Current feedback bodies match the already-reviewed report baseline; no new feedback was omitted. The report preserves the exact current-head checks, including any still-running CI; CI does not establish requirement completion.

## Risks and remaining work

Verified facts: canonical title selection survived a failed response; exact replay repaired derived projection without a new approval or model call; genuine rows were restored exactly under the authorized application identity; batch reads remain fresh and reject incomplete/corrupt artifacts.

Engineering judgment: repeated remote source validation and sequential projection writes materially affect response latency. The real decision took about 194 seconds; cover context about 61 seconds and enqueue about 95 seconds. A browser/proxy timeout budget must be checked against these values. No acceptable UI performance is claimed. The real backend probe uses synchronous production kernel ticks and in-process authenticated FastAPI calls, not a deployed frontend or background-scheduler test.

The failed schema prechecks on an earlier PR branch were a probe environment error: that branch predates StoryStates, while the probe expected the final table map. They stopped before any write. The precheck now uses the same immutable complete source as the runtime; all 13 tables and required fields were verified on the current day.

New cover/planning/chapter routes use conservative peak/cache-miss estimates of $0.30 input and $1.20 output per million tokens, as verified against [official DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/). Each new chapter-generation run has a $0.02 estimate cap. These are configured upper estimates, not actual charges or a cumulative cap across every historical revision. Earlier research/risk/title prices remain unavailable; null cost is not zero spend.

Still required: finish real generation/revision/final-lock and independent narrative/continuity review; exercise routine automatic-pass policy under real providers; validate deployed access and schema wiring; correct measured latency/polling/timeout risks; reach 100% applicable coverage; complete the full requirement-by-requirement audit. The whole goal remains active.

Reusable workflow assessment: issue-pr-delivery, lark-base and TDD skills were reused. Stable lessons are exact-command recovery after durable decisions, domain-ID journaling before batches, independent outcome verification, immutable source for multi-branch probes, and deriving quantity bounds from the current issue. A full new generation/recovery skill is not claimed as validated while downstream acceptance remains pending.
