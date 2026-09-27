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
