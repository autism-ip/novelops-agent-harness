"""Loopback-only UI acceptance fixture; real API/kernel, synthetic HTTP storage.

Run: python -m tests.ui_fixture_app. Never import this module in production.
"""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from fastapi.responses import JSONResponse

from app.config import Settings
from app.generation import TraceRecorder
from app.harness import HarnessKernel
from app.hotspots import HotspotService
from app.main import create_app
from app.tools.adapters.douyin_hotspots import DouyinHotspotAdapter
from app.tools.runner import OpenCLIRunner
from tests.feishu_transport import make_storage


def create_fixture_app():
    directory = tempfile.TemporaryDirectory(prefix="novelops-ui-")
    root = Path(directory.name)
    payload = root / "public-fixture.json"
    records = [{"title": f"Synthetic public idea {index + 1}", "rank": index + 1,
        "heat_value": 1000 - index, "url": f"https://example.com/idea/{index}",
        "captured_at": "2026-09-28T00:00:00Z"} for index in range(35)]
    payload.write_text(json.dumps(records))
    storage, _, client = make_storage()
    kernel = HarnessKernel(storage, journal_dir=root / "journal", poll_interval=0.1, max_retries=1)
    kernel.telemetry = TraceRecorder(kernel)
    adapter = DouyinHotspotAdapter(OpenCLIRunner(sys.executable, 5), SimpleNamespace(OPENCLI_ENABLED=True),
        ["-c", "import sys; print(open(sys.argv[1]).read())", str(payload)])
    kernel.hotspots = HotspotService(kernel, adapter)
    app = create_app(Settings(_env_file=None, BACKEND_API_KEY="ui-fixture-key"), kernel=kernel)
    app.state.drop_manual_response = False
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        try:
            async with original(instance):
                yield
        finally:
            client._http.close()
            directory.cleanup()

    app.router.lifespan_context = lifespan

    @app.middleware('http')
    async def uncertain_response(request, call_next):
        response = await call_next(request)
        if request.url.path == '/api/hotspots/manual' and response.status_code == 201 and app.state.drop_manual_response:
            app.state.drop_manual_response = False
            return JSONResponse(status_code=503, content={'detail': 'Synthetic response lost after commit'})
        return response

    @app.post('/api/_fixture/uncertain-manual')
    def uncertain_manual():
        app.state.drop_manual_response = True
        return {'mode': 'lose next manual response'}

    @app.post('/api/_fixture/source-failure')
    def fail_source():
        payload.write_text('{"error":"synthetic upstream drift"}')
        return {"mode": "malformed source"}

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_fixture_app(), host='127.0.0.1', port=18000)
