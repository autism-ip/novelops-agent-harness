# Agent Runtime Design v0.2

> v0.2 no longer treats the Harness itself as an Agent Team. Deterministic control-plane responsibilities belong to Harness services; Agents are reserved for semantic reasoning and generation.

## Core rule

If the same input must produce the same control behavior, use normal code rather than an LLM Agent.

Harness services own:

- workflow orchestration
- runnable-step selection
- lifecycle/state transitions
- schema validation
- deterministic verification
- approvals
- retries/recovery
- reconciliation
- tracing/logging/cost accounting
- storage synchronization

## Initial semantic Agent roles

| Agent | Responsibility |
|---|---|
| `ResearchAgent` | Convert selected research/hotspot inputs into structured opportunity intelligence. |
| `StoryArchitectAgent` | Create/evolve StoryBible and propose structured StoryState changes. |
| `ChapterPlannerAgent` | Generate versioned ChapterBrief artifacts from current StoryState. |
| `WriterAgent` | Generate chapter drafts from StoryContextSnapshot and ChapterBrief. |
| `CriticAgent` | Evaluate semantic quality: pacing, voice/style, dialogue, reader promise, interpretive continuity, repetition, AI-like patterns. |
| `RewriteAgent` | Apply constrained revisions only when critique/policy requires them. |

Other model-backed workflow steps such as title or cover planning do not need to become long-lived Agent identities unless evals demonstrate a clear benefit.

## Canonical StoryState

Story truth is not owned by independent Agent memories.

```text
StoryState
├─ StoryBible
├─ World
├─ Characters
├─ PowerSystem
├─ Timeline
├─ Plot
├─ Foreshadowing
└─ StyleContract
```

Agents read canonical StoryState and emit structured outputs or proposed patches. Harness validation and consistency rules decide whether changes may be committed.

## Structured state changes

Prefer structured patch operations over opaque memory summaries, for example:

```json
{
  "operations": [
    {
      "type": "update_character",
      "character_id": "char_001",
      "field": "relationship.char_003",
      "value": "hostile"
    }
  ]
}
```

The Harness validates schema, references, hard rules, and version preconditions before committing a new StoryState version.

## Artifact-first communication

Agents should primarily consume and produce versioned Artifacts rather than exchanging unconstrained messages.

Typical artifacts:

- OpportunityAnalysis
- StoryBible
- ChapterBrief
- StoryContextSnapshot
- ChapterVersion
- CriticReport
- RevisionInstruction

Each important artifact should include provenance such as source refs, content hash, run/creator refs, model/prompt version where applicable, and timestamps.

## StoryContextSnapshot

Before chapter generation, Context Builder freezes the exact StoryState/Artifact versions used for that chapter.

A snapshot typically references:

- StoryBible version
- World/Character/Plot/Foreshadowing state versions
- StyleContract version
- ChapterBrief version
- relevant historical/retrieved context

Every generated ChapterVersion links to its StoryContextSnapshot.

This replaces the v0.1 `AgentTeamSnapshot` model.

## Chapter generation loop

```text
Context Builder
    ↓
WriterAgent
    ↓
Deterministic Verifier
    ↓
CriticAgent
    ↓
revision required?
 ┌──┴──┐
 yes   no
  ↓     │
RewriteAgent
  ↓     │
Verifier ◄┘
  ↓
Selective Human Gate
  ↓
Final
```

The old unconditional `Writer → StyleAgent → AntiAIFlavorAgent → ReviewAgent` chain is deprecated.

## Agent configuration

Agent definitions should be configuration-driven where practical and describe:

- logical model route/capability
- input Artifact/context requirements
- tool permissions
- output schema
- prompt version
- budget/retry constraints

Provider-specific model names should not leak into domain/workflow logic.

## Growth rule

Do not add an Agent because a domain noun exists. Add a distinct Agent role only when evals show that separating the role improves quality, reliability, or cost enough to justify the added coordination surface.
