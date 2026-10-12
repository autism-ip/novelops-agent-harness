# ZEN-36 candidate reads and real-provider acceptance — 2026-10-12

## Goal and delivery

[ZEN-36](https://linear.app/zenhungyep/issue/ZEN-36/implement-title-and-cover-planning-workflow) requires **at least 10 title candidates and at least 3 cover directions**, selected through exact immutable artifacts. The existing supported ranges are 10–20 and 3–5. Delivery remains [PR #30](https://github.com/autism-ip/novelops-agent-harness/pull/30), based on ZEN-35. No new PR, merge or Done transition is used as acceptance.

Source repair: `72502bf5027293525c28f15c53a0b75fd9d979b8`.

## Real chain evidence and probe correction

Real DeepSeek research and independent risk review completed, both synthetic-editor gates were accepted through production APIs, and the approved opportunity produced **20 distinct title artifacts** in the authorized synthetic Feishu Base. These artifacts include model, prompt, source references and content hashes. The native selection gate contained the same IDs. The probe then failed because it incorrectly asserted exactly 10 candidates. Current Linear and schema show this was a probe error, not invalid product output. No production quantity bound or valid test assertion was weakened.

All 72 attempted business IDs were recorded before writes. The failed probe completed scoped cleanup; a separate client verified zero remaining IDs in every affected collection. The report retains the assertion traceback, actual 20-title data, persisted rows, model traces, timings and cleanup results. No cover, book, chapter, constrained rewrite or final lock occurred in that attempt.

The complete attempt took 1399.733 seconds including initial generation, reads and cleanup, with 1235 Feishu requests. Its title materialization tick took 266.052 seconds and the following selection tick 114.872 seconds. These timings include the probe's additional ownership checks; they are not a clean deployed latency benchmark. They nevertheless expose repeated remote reads in the production candidate path. No acceptable UI latency or throughput is claimed.

## Implementation and test evidence

`CreativeService.candidates` now uses the existing `ArtifactStore.get_many` to validate all declared candidate IDs together, then restores their declared order. Missing or corrupted data fails the entire operation; no partial candidate set is returned. Each call reads storage anew. The selection step reuses its one candidate ID list for both selection and output references. Model routes, prompts, output schemas, quantity ranges and paid-call policy are unchanged.

The 10/20-candidate read regressions first failed with 11/21 native read-only search requests. After the repair, each case makes exactly two: one batch artifact and one candidate search. Payloads, order, filter identities and zero mutations are asserted. Additional cases prove 20 titles/5 covers remain selectable and prove missing/tampered candidate data is detected after a previous successful read. The complete creative workflow suite passed: 20 tests. Full offline backend at the owning branch passed: 440, with 10 explicit live integration cases deselected. Ruff and diff checks passed.

Owner-branch coverage: statements/lines 2833/2991 = 94.72%; branches 657/758 = 86.68%; combined coverage.py display 93.09%. Function coverage was not remeasured on this branch. Existing Protocol defaults still report 11 excluded source lines; no exclusions, skips or lowered gates were added. **The project's requested 100% coverage is not met.** Descendant-branch tests and real improved reads remain separate pending evidence.

## Review, risk and next acceptance

The latest audit before the change found zero unresolved threads across the 13 existing PRs. Valid behavior includes the wider candidate ranges; the incorrect probe count is explicitly rejected as a requirement interpretation. Request savings are an offline transport fact, not a measured percentage reduction in real elapsed time.

The real artifacts are genuine model results; recovery may restore only their previously captured, verified IDs and contents into the same authorized synthetic Base, with ownership preflight and a new write journal. Such restoration must be reported and independently checked, and must never be described as fresh generation or an uninterrupted run. Full cover → book → approved Bible → brief → generation → constrained immutable revision → exact approval → final lock still requires actual verification.

Security limits: fixed authorized synthetic Base, application identity, no secret publication, no unrelated record mutation, current hash/identity validation and scoped independent cleanup. No second primary store or cached business truth was introduced. Cost metadata from these earlier routes is unavailable because prices were not configured; null cost is not zero spend.

Reusable workflow assessment: existing issue-pr-delivery, lark-base and TDD skills were reused. This failure demonstrates a stable rule for future probes: derive minimum/maximum acceptance bounds from the current issue and schema, independently of fixture sizes. The full recovery workflow is not yet validated and is not claimed as a completed new skill.
