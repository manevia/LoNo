"""LoNo — hybrid media, broadcasting, streaming, learning and Web3 platform (API)."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from pymongo.errors import ConfigurationError, ConnectionFailure, OperationFailure
from starlette.middleware.cors import CORSMiddleware

from . import config
from .db import client, ensure_indexes
from .routers import account, admin, ai, auth, broadcast, campaigns, creator_api, rooms, content, creator, creator_courses, files, governance, guide, learn, payments, wallet, watch
from .admin_setup import bootstrap_admins
from .seed import seed_catalogue, seed_courses
from .util import now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # no per-request lines (and no URLs in logs)
VERSION = "3.3.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.warn_on_insecure_defaults()
    try:
        await ensure_indexes()
    except (ConnectionFailure, ConfigurationError, OperationFailure) as error:
        logging.getLogger("lono").error(
            "MongoDB startup check failed (%s, code=%s).",
            type(error).__name__,
            error.code if isinstance(error, OperationFailure) else None,
        )
        raise SystemExit(1) from None
    if config.SEED_DEMO_DATA:
        await seed_catalogue()
        await seed_courses()
    await bootstrap_admins()
    from .pilot import init_pilot
    await init_pilot()
    stop = asyncio.Event()
    tasks = []

    async def repair_loop():          # finish or undo claims interrupted by a crash
        while not stop.is_set():
            try:
                await campaigns.repair_pending()
            except Exception:
                logging.getLogger("lono").exception("claim repair failed")
            try:
                await asyncio.wait_for(stop.wait(), 60)
            except asyncio.TimeoutError:
                pass
    tasks.append(asyncio.create_task(repair_loop()))
    if config.MEDIA_ENABLED:
        from .broadcast import media
        from .broadcast.relays import manager
        media.listeners.append(broadcast.on_feed_change)
        media.listeners.append(rooms.on_contributor_feed)
        manager.on_change = broadcast.on_relay_change
        tasks.append(asyncio.create_task(media.monitor(stop)))

        async def publish_loop():
            while not stop.is_set():
                await broadcast.publish_due_recordings()
                try:
                    await asyncio.wait_for(stop.wait(), 30)
                except asyncio.TimeoutError:
                    pass
        tasks.append(asyncio.create_task(publish_loop()))
    yield
    stop.set()
    if config.MEDIA_ENABLED:
        from .broadcast.relays import manager
        await manager.stop_all()
    for t in tasks:
        t.cancel()
    client.close()


app = FastAPI(title="LoNo API", version=VERSION, lifespan=lifespan, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
api = APIRouter(prefix="/api")
for r in (auth, account, admin, broadcast, rooms, guide, content, watch, creator, creator_courses, wallet, governance, ai, payments, files, learn):
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


api.include_router(campaigns.staff)
api.include_router(campaigns.fans)
api.include_router(campaigns.replay)
api.include_router(creator_api.manage)
api.include_router(creator_api.v1)
app.include_router(api)
app.include_router(broadcast.media_router)


@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks():
    """Lets the LoNo Android app (phone / Android TV, built as a Trusted Web Activity)
    open this site full screen without a browser bar."""
    from fastapi.responses import JSONResponse
    if not (config.ANDROID_APP_PACKAGE and config.ANDROID_CERT_SHA256):
        return JSONResponse([], headers={"Cache-Control": "max-age=300"})
    return JSONResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": config.ANDROID_APP_PACKAGE,
                   "sha256_cert_fingerprints": config.ANDROID_CERT_SHA256},
    }], headers={"Cache-Control": "max-age=300"})


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")          # no MIME sniffing of uploads
    h.setdefault("X-Frame-Options", "DENY")                    # no clickjacking via iframes
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Camera/mic/screen only for LoNo itself (Live Studio); never for embedded third parties.
    h.setdefault("Permissions-Policy", "camera=(self), microphone=(self), display-capture=(self), geolocation=(), payment=(self)")
    if request.url.path.startswith("/api/") and "cache-control" not in h:
        h["Cache-Control"] = "no-store"                        # API answers can be personal
    return resp

if config.FRONTEND_DIR:
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    import mimetypes
    mimetypes.add_type("application/manifest+json", ".webmanifest")
    web = Path(config.FRONTEND_DIR).resolve()
    app.mount("/static", StaticFiles(directory=web / "static"), name="static")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(path: str):
        f = (web / path).resolve()
        if path and web in f.parents and f.is_file():
            # The service worker must be re-checked on every visit so updates roll out.
            no_cache = path in ("sw.js", "manifest.webmanifest", "index.html") or path.endswith(".m3u8")  # live playlists change constantly
            return FileResponse(f, headers={"Cache-Control": "no-cache"} if no_cache else None)
        return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})  # client-side routes
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=config.CORS_ORIGINS != ["*"],
                   allow_methods=["*"], allow_headers=["*"])
