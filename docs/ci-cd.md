# CI and deployment gates

## Scope

The `CI` workflow in `.github/workflows/backend-gates.yml` validates changes before
merge or deployment. It runs on every pull request, merge queue entry, pushes to
`main`, `feature/**`, `fix/**`, and `codex/**`, and manual dispatch. There are no path
filters: documentation-only pull requests still produce the required check.

This change supplies deployment prerequisites and integration instructions. It
does not deploy to Vercel, restart the local backend, or change repository rules.

## Checks

| Check | Blocking behavior |
| --- | --- |
| Workflow lint | actionlint 1.7.12 validates Actions syntax, expressions, and job dependencies; the downloaded binary is SHA-256 verified. |
| Backend lint | Ruff checks all `app/` and `tests/` Python files using project-owned rules. |
| ZEN-28 behavior contract | Dependency consistency, offline pytest suite, at least 87.82% application statement coverage, source/wheel build, installed-wheel smoke test. |
| Frontend lint, types and build | `npm ci`, zero-warning ESLint, `next typegen` plus TypeScript, and production Next.js build. |
| CI quality gate | Runs even when a dependency fails or is skipped. Succeeds only when all four checks report `success`. |

The original backend check name is retained for existing branch rules. The backend
suite now covers repository, pipeline/worker, API, configuration, and OpenCLI tool
behavior, beyond the original skeleton contract.

Python is 3.12; Node is 24, selected by `frontend/.nvmrc`. Frontend dependencies use
the committed npm lockfile. Ruff, pytest-cov, and the build frontend are pinned in
`backend/pyproject.toml`; Python runtime dependencies still use version ranges.
`pip check` detects inconsistent installations, but these ranges are not a full
reproducible dependency lock.

Ruff enables `E4`, `E7`, `E9`, `F`, and `RUF100` for correctness, unused imports,
undefined names, and stale suppressions. This is a lint baseline, not a mass
formatting migration. Application files are not excluded to raise coverage.

### Coverage and test integrity

The measured baseline at `808167e` is **169 passing offline tests**, covering
**800 of 911 application statements (87.82%, two decimal places)**. Configuration
uses the exact measured percentage, `87.81558726673984`, to avoid comparing a raw
measurement with its rounded-up display value. The gate starts at that baseline,
not a lower generic threshold. Raise it as coverage improves.
Do not lower the threshold, remove/weaken assertions, add skips, or exclude
application code just to make CI pass. New behavior and regression fixes require
behavioral tests; if coverage falls, address the uncovered behavior.

The four existing Feishu integration tests remain in the repository and are
reported as deselected in offline CI. They are not counted as passing. Coverage
percentages also do not prove semantic correctness: keep the behavior-contract
assertions and review the uncovered-line report, not only the aggregate percentage.

## Run locally

From the repository root, use Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[dev]'
cd backend
python -m pip check
python -m ruff check app tests
BACKEND_API_KEY=local-test-key python -m pytest tests -q --tb=short \
  -m 'not integration' --cov=app --cov-report=term-missing \
  --cov-report=xml:coverage.xml --junitxml=test-results/pytest.xml
python -m build
```

For the frontend, from the repository root:

```bash
cd frontend
nvm use
npm ci
npm run check
```

`npm run check` runs lint, route-type generation/type checking, and build in order.
Use `npm run lint:fix` for ESLint autofixes. Install actionlint 1.7.12 and run
`actionlint` at the repository root to validate the workflow itself.

CI uses synthetic backend keys and requires no Feishu, model, OpenCLI, Vercel, or
production credentials. Tests marked `integration` are explicitly deselected.
Run those separately against a configured test Feishu Base; they can create and
delete records. An offline green check does not establish live provider access,
Base v3 feasibility, model quality, or a working background scheduler.

There is currently no frontend test runner or browser test suite in the repository.
The frontend gate checks lint, types, and build; it does not claim browser behavior
coverage. Add behavior tests as the product workflows and APIs are implemented.

## Reports and distributions

- `backend-test-reports-<sha>` contains coverage XML and pytest JUnit XML, retained
  for 14 days. Available reports are uploaded even after test failure.
- `backend-dist-<sha>` contains the source archive and wheel after backend checks
  pass. CI installs that wheel, leaves the source directory, and checks health and
  API-key enforcement with Python isolated mode.
- The frontend build is verified but is not uploaded as a deployment package.
  Vercel must build the same validated revision for its own runtime.

An artifact's existence alone is not release approval: another job can still fail.
Use the aggregate result for the same workflow run and revision.

## Enable merge protection

After the workflow has run on GitHub:

1. Open repository Settings → Rules → Rulesets (or branch protection for `main`).
2. Require pull requests and the status check **CI quality gate** from GitHub
   Actions. Keep **ZEN-28 behavior contract** if an existing rule already uses it.
3. Require the branch to be up to date, or use the merge queue; `merge_group`
   triggers are already supported.
4. Restrict direct pushes/bypasses according to the repository's release policy.

These repository-side rules must be enabled separately. Committing workflow YAML
does not itself prevent merging a failed check. See GitHub's
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Connect a deployment target later

### Shared contract

- Gate production deployment on a successful `CI quality gate` for the exact
  commit being deployed. Never consume the latest artifact without matching its
  SHA and successful run.
- In this workflow, a future deployment job must depend on `quality-gate` and run
  only for `push` to `refs/heads/main`; configure a `production` environment for
  deployment credentials and any required approval.
- In a separate workflow, validate the upstream workflow identity, success,
  repository, event/branch, and SHA. Check out that SHA rather than moving `main`.
- A manual re-run or a successful PR merge-ref build alone is not a production
  release signal. Use the post-merge `main` run.
- Keep deployment credentials out of pull-request jobs. Serialize production
  deployments and retain the previous validated revision for rollback.

### Vercel frontend

Use `frontend/` as the project root, Node 24, `npm ci`, and `npm run build`. Configure
the server-only values from `frontend/.env.example` in the target environment.
The remote frontend needs a reachable backend URL; its own `localhost:8000` is not
the operator's local backend.

Choose a deployment integration that waits for the exact commit's quality gate.
Independent Git-triggered auto-deployment must not be assumed to wait for this
workflow. Confirm that behavior before enabling production promotion. After
deployment, verify the frontend health proxy and protected-session flow.

### Local persistent backend

Deploy the matching validated wheel into a Python 3.12 runtime with target-specific
dependencies and backend-only configuration. Choose the host/service manager and
restart procedure before adding automation; no host or restart command is assumed
here. Check `/api/system/health` and API-key enforcement after restart, then verify
the required live providers independently. Roll back to the previous validated
wheel/configuration when those checks fail.
