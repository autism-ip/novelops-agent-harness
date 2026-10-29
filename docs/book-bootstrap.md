# Book bootstrap and StoryState v1 (ZEN-38 / GitHub #11)

## Enablement

Set `BOOKS_ENABLED=true` only after the Harness, generation, research, and creative selection dependencies are enabled. Provision the additive `Books` fields and `StoryStates` table in [the Feishu schema](feishu-schema.md), then set `FEISHU_TABLE_ID_BOOKS` and `FEISHU_TABLE_ID_STORY_STATES`. Preserve the Kernel intent journal across restarts. No separate AgentStates, external database, or autonomous book Agent is created.

## Exact source contract

`GET /api/books/bootstrap-context/{cover_run_id}` resolves the **current** selected cover, its selected title, and its approved opportunity. It returns their immutable artifact IDs plus a stable Book ID. `POST /api/books` takes that exact object. The server re-resolves the chain under the Kernel writer lock and rejects unselected, superseded, or mismatched inputs before creating a canonical state.

The Book ID derives from the cover artifact ID; StoryState v1 and its Artifact also use stable business IDs. The Book starts as `initializing`. The service then saves one immutable Artifact containing eight namespaces (`StoryBible`, `World`, `Characters`, `PowerSystem`, `Timeline`, `Plot`, `Foreshadowing`, `StyleContract`), creates one StoryStates projection row, and finally updates the Book to `ready` with the state content hash. Values present in approved inputs are projected without an extra model call; unknown world, character, timeline, and rule details remain explicit empty structures. The artifact stores source refs, content hash, workflow version, deterministic creator, and creation time.

An exact retry returns the existing ready Book or completes a partially initialized Book if the source chain remains current. Each create uses the existing fsynced intent journal and Feishu business-key reconciliation, so an ambiguous POST never triggers a blind second create. If the source changes while an initialization remains partial, the service leaves it visible as `initializing` and fails closed; a human must inspect its source/provenance before recovery.

## Read boundary and legacy records

`GET /api/books` lists Book records. `GET /api/books/{book_id}` returns the Book and either its verified StoryState or `state: null` for an incomplete or legacy record. `GET /api/books/{book_id}/story-state` and `StoryContextProvider.get(book_id)` require a ready canonical state and verify its Book pointer, version, Artifact ID, hash, and source references. Future chapter workflows must use this context provider rather than `mini_bible`, `AgentStates`, or `AgentTeamSnapshots`. Existing legacy Book records remain readable and are never silently migrated or overwritten.

The frontend stores the exact bootstrap body in session storage before POST; retry after timeout or reload sends the same body. The Book workspace shows all eight namespaces, version/hash/source references, and distinguishes legacy/incomplete records. A missing `BOOKS_ENABLED` capability hides creation in the hotspot detail panel.

## Verification boundary

The automated suite uses real FastAPI, Kernel, Feishu repository code with synthetic HTTP transport, and synthetic model output. A production Next browser path has exercised selected cover → create Book → read all eight namespaces and provenance. The separate test Base proves the additive Books/StoryStates field types accept synthetic records through the Feishu Base v3 CLI; it does not prove the backend's live Feishu runtime path or production model quality. Production enablement still requires actual table IDs, credentials, migration checks, and a live runtime acceptance run.
