"""NovelOps Agent Harness — FastAPI Entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import APIKeyMiddleware
from app.api.routes import api_router

app = FastAPI(
    title="NovelOps Agent Harness",
    version="0.1.0",
    description="AI-assisted web-novel production system",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(APIKeyMiddleware)
app.include_router(api_router, prefix="/api")
