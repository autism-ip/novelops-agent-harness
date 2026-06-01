# Task 003: Add domain exceptions and transport error classification to client

**Type**: impl
**depends-on**: []

## BDD Scenario

```gherkin
Scenario: HTTP 4xx raises FeishuAPIError (not FeishuAuthError)
  Given a FeishuClient with valid credentials
  When a request returns HTTP 403
  Then FeishuAPIError is raised with status code 403
  And the error message contains "HTTP 403"

Scenario: Transport failure raises FeishuAPIError
  Given a FeishuClient with valid credentials
  When a request fails with a network error
  Then FeishuAPIError is raised (not FeishuAuthError)

Scenario: 401 still raises FeishuAuthError
  Given a FeishuClient with valid credentials
  When a request returns 401 twice
  Then FeishuAuthError is raised
```

## Files to Modify

- `backend/app/feishu/client.py`
- `backend/tests/test_feishu_client.py`

## Steps

1. In `client.py`:
   - Add `FeishuAPIError` exception class (with `code` attribute) after `FeishuAuthError`
   - In `_request()`, change the `except httpx.HTTPError` block to raise `FeishuAPIError` instead of `FeishuAuthError` for transport failures
   - Add a new branch after 401 handling: `if resp.status_code >= 400:` raise `FeishuAPIError` with status code
   - Update L3 header OUTPUT to include `FeishuAPIError`
   - Update `__init__.py` re-exports if needed

2. In `test_feishu_client.py`:
   - Add `from app.feishu.client import FeishuAPIError`
   - Add `TestHttpErrors` class with:
     - `test_http_4xx_raises_api_error`: mock 403 response, assert `FeishuAPIError` with "HTTP 403"
     - `test_transport_error_raises_api_error`: mock `httpx.ConnectError`, assert `FeishuAPIError`
     - `test_401_still_raises_auth_error`: verify 401 still raises `FeishuAuthError`

## Verification

```bash
cd backend && python -m pytest tests/test_feishu_client.py -v
```
