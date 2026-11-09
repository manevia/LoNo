"""LoNo — hybrid media, broadcasting, streaming, learning and Web3 platform (API)."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from . import config
from .db import client, ensure_indexes
from .routers import account, admin, ai, auth, content, creator, creator_courses, files, governance, learn, payments, wallet, watch
from .seed import seed_catalogue, seed_courses
from .util import now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
VERSION = "2.5.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.warn_on_insecure_defaults()
    await ensure_indexes()
    if config.SEED_DEMO_DATA:
        await seed_catalogue()
        await seed_courses()
    yield
    client.close()


app = FastAPI(title="LoNo API", version=VERSION, lifespan=lifespan)
api = APIRouter(prefix="/api")
for r in (auth, account, admin, content, watch, creator, creator_courses, wallet, governance, ai, payments, files, learn):
    api.include_router(r.router)


@api.get("/")
async def root():
    return {"service": "LoNo", "version": VERSION, "status": "ok"}


@api.get("/health")
async def health():
    return {"status": "healthy", "time": now_iso()}


@api.get("/config")
async def public_config():
    """Which optional features are switched on, so the UI can adapt."""
    return config.features()


app.include_router(api)


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")          # no MIME sniffing of uploads
    h.setdefault("X-Frame-Options", "DENY")                    # no clickjacking via iframes
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(self)")
    if request.url.path.startswith("/api/") and "cache-control" not in h:
        h["Cache-Control"] = "no-store"                        # API answers can be personal
    return resp

if config.FRONTEND_DIR:
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    web = Path(config.FRONTEND_DIR).resolve()
    app.mount("/static", StaticFiles(directory=web / "static"), name="static")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = (web / path).resolve()
        if path and web in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(web / "index.html")  # client-side routes
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=config.CORS_ORIGINS != ["*"],
                   allow_methods=["*"], allow_headers=["*"])
