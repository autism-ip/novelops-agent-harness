# Task 004: Create base repository with generic CRUD

**Type:** impl
**Depends-on:** ["002"]

## BDD Scenario

```gherkin
Scenario: BaseRepository provides generic CRUD operations
  Given a BaseRepository instance configured with a FeishuClient and table name
  When I call create(record_data)
  Then a new record is created in Feishu Bitable
  And the created record (with record_id) is returned

  When I call get(record_id)
  Then the record is fetched by ID
  And the record fields are returned as a dict

  When I call list_records(filter_expr=None, page_size=20)
  Then a list of records is returned
  And pagination is handled automatically

  When I call update(record_id, fields)
  Then the specified fields are updated
  And the updated record is returned

  When I call delete(record_id)
  Then the record is deleted
  And True is returned on success
```

```gherkin
Scenario: BaseRepository maps Python field names to Feishu field names
  Given a BaseRepository with a field_map {"book_id": "Book ID", "title": "Title"}
  When I create({"book_id": "B001", "title": "My Novel"})
  Then the request body uses {"Book ID": "B001", "Title": "My Novel"}
```

## What to Implement

Create `backend/app/feishu/repositories/__init__.py` — package marker.

Create `backend/app/feishu/repositories/base.py` with:

- `BaseRepository` class:
  - `__init__(self, client: FeishuClient, app_token: str, table_id: str, field_map: dict[str, str])`
  - `_to_feishu(self, data: dict) -> dict` — map Python keys → Feishu keys
  - `_from_feishu(self, record: dict) -> dict` — map Feishu keys → Python keys
  - `async create(self, data: dict) -> dict`
  - `async get(self, record_id: str) -> dict | None`
  - `async list(self, filter_expr: str | None = None, page_size: int = 20) -> list[dict]`
  - `async update(self, record_id: str, fields: dict) -> dict`
  - `async delete(self, record_id: str) -> bool`

## Files to Create

- `backend/app/feishu/repositories/__init__.py`
- `backend/app/feishu/repositories/base.py`

## Verification

```bash
cd backend && python -c "
from app.feishu.repositories.base import BaseRepository
print('BaseRepository imported OK')
"
```

Expected: Import succeeds, exit code 0.
