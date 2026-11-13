"""FastAPI application. Run with `python -m api` (or `uvicorn api.main:app --reload`)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.core import NexusJSON
from api.routes import router
from nexus.security.privacy import PrivacyError

DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from nexus.core.embeddings import get_embedder

    get_embedder()  # load the embedding model once, at startup, not on the first page view
    yield


app = FastAPI(title="NEXUS API", default_response_class=NexusJSON, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.exception_handler(PrivacyError)
async def privacy_error(_, exc: PrivacyError):
    return NexusJSON({"detail": str(exc)}, status_code=403)


if DIST.exists():  # production build: one process serves the API and the React app
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (DIST / path).resolve()
        inside = file.is_relative_to(DIST.resolve())  # never serve anything outside the build folder
        return FileResponse(file if path and inside and file.is_file() else DIST / "index.html")
