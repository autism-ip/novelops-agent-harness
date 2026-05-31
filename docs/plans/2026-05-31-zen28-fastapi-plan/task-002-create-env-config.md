# Task 002: Create environment config with Pydantic Settings

**depends-on**: task-001

## Description

Create a Pydantic Settings-based configuration module that loads environment variables for backend secrets (Feishu credentials, LLM API keys, OpenCLI config, API key for frontend auth). Secrets must never be exposed to the frontend.

## Execution Context

**Task Number**: 002 of 006
**Phase**: Foundation
**Prerequisites**: Task 001 completed, project structure exists

## BDD Scenario

```gherkin
Scenario: Environment config loads secrets from env vars
  Given a .env file with FEISHU_APP_ID, FEISHU_APP_SECRET, LLM_API_KEY, BACKEND_API_KEY set
  When the config module is loaded
  Then all secret values are available in the Settings object
  And no secret values are exposed in the /api/system/health response
  And no secret values are exposed in the /api/system/status response

Scenario: Missing required env var raises clear error
  Given BACKEND_API_KEY is not set in environment
  When the config module is loaded
  Then a clear error message indicates which variable is missing
```

## Files to Modify/Create

- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Modify: `backend/app/main.py` (wire config)

## Steps

### Step 1: Create config module

`app/config.py` should define a `Settings` class using `pydantic-settings`:

Fields:
- `BACKEND_API_KEY: str` — API key for frontend-to-backend auth
- `FEISHU_APP_ID: str = ""`
- `FEISHU_APP_SECRET: str = ""`
- `LLM_API_KEY: str = ""`
- `LLM_PROVIDER: str = "openai"`
- `OPENCLI_ENABLED: bool = False`
- `CORS_ORIGINS: list[str] = ["*"]`

Config: `env_file = ".env"`, `env_file_encoding = "utf-8"`

### Step 2: Create .env.example

Document all env vars with placeholder values (no real secrets).

### Step 3: Wire config into FastAPI app

`app/main.py` should:
- Import and instantiate Settings
- Store as `app.state.settings`
- Add CORS middleware using `settings.CORS_ORIGINS`

### Step 4: Verify

Settings should load from `.env` or environment variables.

## Verification Commands

```bash
cd backend
# Test config loads
python -c "from app.config import Settings; s = Settings(); print(s.BACKEND_API_KEY)"

# Test .env.example exists
cat .env.example
```

## Success Criteria

- `app/config.py` defines Settings with all required fields
- `.env.example` documents all variables
- Settings object is accessible via `app.state.settings`
- No secrets appear in any API response
