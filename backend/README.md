# NovelOps backend

Local persistent FastAPI backend for NovelOps. Requires Python 3.12 or newer;
CI verifies Python 3.12.

From this directory, in an active virtual environment:

```bash
python -m pip install -e '.[dev]'
python -m ruff check app tests
BACKEND_API_KEY=local-test-key python -m pytest tests -q -m 'not integration' --cov=app
python -m build
```

The offline coverage floor is the current 87.82% application baseline. Real Feishu
integration tests require a separately configured test Base and are not represented
as passing by the offline gate.

Run the API with `uvicorn app.main:app` after configuring `BACKEND_API_KEY` and the
required backend environment. The API process currently exposes execution
primitives; it does not start a background scheduler automatically.

Repository documentation in `docs/ci-cd.md` describes merge protection, artifacts,
and deployment integration. The package contains the `app` modules; source
distributions also retain the existing tests.

When `STORY_PLANNING_ENABLED=true`, configure `BOOKS_ENABLED=true` and the
`story_architect` and `chapter_planner` entries in `MODEL_ROUTES_JSON`. See
[`docs/story-planning.md`](../docs/story-planning.md) for the StoryBible approval,
canonical StoryState patch, snapshot, and ChapterBrief contracts.

When `CHAPTER_LOOP_ENABLED=true`, also configure `STORY_PLANNING_ENABLED=true`,
the ChapterVersions table with the additive fields in `docs/feishu-schema.md`,
and `writer`, `critic`, and `rewrite` model routes. `CHAPTER_MAX_REWRITES` is 0 or
1. Optional `CHAPTER_MAX_ESTIMATED_COST` fails the run closed if token usage or
route prices are unavailable. See [`docs/chapter-loop.md`](../docs/chapter-loop.md)
for exact-source generation, deterministic checks, critique, revision and final-lock semantics.

The ZEN-41 review desk optionally holds the first
`CHAPTER_REVIEW_FIRST_N` chapters or a chapter with any Critic dimension at or
below `CHAPTER_REVIEW_SCORE_THRESHOLD` for an exact editor decision. Both
default to 0, so ordinary validated chapters proceed to review automatically.
Configure the additive RevisionTasks fields in `docs/feishu-schema.md` before
using editor-directed revision. See
[`docs/chapter-review.md`](../docs/chapter-review.md) for the decision and
retry contract.
