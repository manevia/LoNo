"""Runtime configuration. Every external service is optional: features switch
themselves off (and report so via GET /api/config) when their keys are absent."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

log = logging.getLogger("lono")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    v = _env(name)
    return default if not v else v.lower() in ("1", "true", "yes", "on")


# Core
MONGO_URL = _env("MONGO_URL", "mongodb://localhost:27017")  # "mongomock://" = in-memory demo mode
DB_NAME = _env("DB_NAME", "lono")
JWT_SECRET = _env("JWT_SECRET", "change-me-in-production")
JWT_TTL_DAYS = int(_env("JWT_TTL_DAYS", "30"))
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]
PUBLIC_ORIGIN = _env("PUBLIC_ORIGIN", "http://localhost:3000").rstrip("/")
SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", True)
# Optional: serve the built React app from the API process (single-container deploys)
FRONTEND_DIR = _env("FRONTEND_DIR")

# AI (Anthropic Claude)
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5-5")

# Speech-to-text (any OpenAI-compatible /audio/transcriptions endpoint)
TRANSCRIBE_API_KEY = _env("TRANSCRIBE_API_KEY") or _env("OPENAI_API_KEY")
TRANSCRIBE_BASE_URL = _env("TRANSCRIBE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
TRANSCRIBE_MODEL = _env("TRANSCRIBE_MODEL", "whisper-1")

# Storage: "local" (default) or "s3"
STORAGE_BACKEND = _env("STORAGE_BACKEND", "local").lower()
LOCAL_STORAGE_DIR = Path(_env("LOCAL_STORAGE_DIR", str(BACKEND_DIR / "data" / "uploads")))
S3_BUCKET = _env("S3_BUCKET")
S3_REGION = _env("S3_REGION", "us-east-1")
S3_ENDPOINT_URL = _env("S3_ENDPOINT_URL") or None  # for R2 / MinIO / Spaces
MAX_UPLOAD_MB = int(_env("MAX_UPLOAD_MB", "100"))

# Google sign-in (Google Identity Services)
GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID")

# Payments
STRIPE_API_KEY = _env("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = _env("STRIPE_WEBHOOK_SECRET")
SIMULATED_TOKEN_PURCHASE = _bool("SIMULATED_TOKEN_PURCHASE", True)

# Token economics ($LONO is a simulated internal ledger)
LONO_PRICE_USD = float(_env("LONO_PRICE_USD", "0.184"))
SIGNUP_BONUS = float(_env("SIGNUP_BONUS", "100"))
WATCH_REWARD_PER_MIN = float(_env("WATCH_REWARD_PER_MIN", "1"))
WATCH_REWARD_CAP_PER_TITLE = float(_env("WATCH_REWARD_CAP_PER_TITLE", "10"))
WATCH_REWARD_DAILY_CAP = float(_env("WATCH_REWARD_DAILY_CAP", "60"))
HEARTBEAT_SEC = int(_env("HEARTBEAT_SEC", "30"))
# Administration and compliance
# Admin accounts are created by the server at startup (see app/admin_setup.py), so nobody
# can register an admin address first. ADMIN_PASSWORD is optional: without it a random
# password is generated and printed once in the server log.
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EMAILS").split(",") if e.strip()}
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")
TERMS_VERSION = _env("TERMS_VERSION", "2026-11")  # bump when the terms change; new consent is recorded
SUPPORT_EMAIL = _env("SUPPORT_EMAIL")              # shown on the Terms page for privacy requests

# Android phone/TV app (Trusted Web Activity) verification: /.well-known/assetlinks.json
ANDROID_APP_PACKAGE = _env("ANDROID_APP_PACKAGE")            # e.g. lr.edu.ciu.lono
ANDROID_CERT_SHA256 = [f.strip() for f in _env("ANDROID_CERT_SHA256").split(",") if f.strip()]

# Live broadcasting (MediaMTX media server + ffmpeg relays). See docs/BROADCAST.md.
MEDIA_ENABLED = _bool("MEDIA_ENABLED", False)
MEDIA_API_URL = _env("MEDIA_API_URL", "http://127.0.0.1:9997").rstrip("/")     # MediaMTX control API
MEDIA_HLS_URL = _env("MEDIA_HLS_URL", "http://127.0.0.1:8888").rstrip("/")     # MediaMTX HLS (proxied at /media/hls)
MEDIA_WEBRTC_URL = _env("MEDIA_WEBRTC_URL", "http://127.0.0.1:8889").rstrip("/")  # WHIP for browser cameras
MEDIA_RTMP_INTERNAL = _env("MEDIA_RTMP_INTERNAL", "rtmp://127.0.0.1:1935").rstrip("/")
MEDIA_RTSP_INTERNAL = _env("MEDIA_RTSP_INTERNAL", "rtsp://127.0.0.1:8554").rstrip("/")
INGEST_RTMP_URL = _env("INGEST_RTMP_URL", "rtmp://localhost:1935/live")          # what creators paste into OBS
INGEST_RTMPS_URL = _env("INGEST_RTMPS_URL", "")                                  # e.g. rtmps://live.example.org:1936/live
INGEST_SRT_URL = _env("INGEST_SRT_URL", "srt://localhost:8890")
MEDIA_INTERNAL_SECRET = _env("MEDIA_INTERNAL_SECRET") or ("internal-" + JWT_SECRET[:24])
SECRET_ENC_KEY = _env("SECRET_ENC_KEY")                                          # encrypts stored stream keys
def _sibling_tool(path: str, tool: str) -> str:
    """ffprobe lives next to ffmpeg; replace only the file name (works for / and \\ paths)."""
    cut = max(path.rfind("/"), path.rfind("\\"))
    folder, name = path[:cut + 1], path[cut + 1:]
    return folder + name.replace("ffmpeg", tool) if cut >= 0 else tool


FFMPEG_BIN = _env("FFMPEG_BIN", "ffmpeg")
# ffprobe sits next to ffmpeg in every build; derive it so a full FFMPEG_BIN path works without PATH.
FFPROBE_BIN = _env("FFPROBE_BIN") or _sibling_tool(FFMPEG_BIN, "ffprobe")
RECORDINGS_DIR = _env("RECORDINGS_DIR", str(BACKEND_DIR / "data" / "recordings"))

# Creator API
API_RATE_PER_MINUTE = int(_env("API_RATE_PER_MINUTE", "120"))   # per integration
WEBHOOK_ALLOW_PRIVATE = _bool("WEBHOOK_ALLOW_PRIVATE", False)    # only for local development/testing

# Abuse protection
LOGIN_MAX_FAILURES = int(_env("LOGIN_MAX_FAILURES", "5"))        # per email+IP
LOGIN_WINDOW_SEC = int(_env("LOGIN_WINDOW_SEC", "900"))
SIGNUPS_PER_IP_PER_HOUR = int(_env("SIGNUPS_PER_IP_PER_HOUR", "10"))
# Creator-published courses: the platform sets the learner reward (creators can't
# mint their own), and pays the creator a share each time a learner passes.
CREATOR_COURSE_REWARD = float(_env("CREATOR_COURSE_REWARD", "10"))
CREATOR_PAYOUT_PER_CERT = float(_env("CREATOR_PAYOUT_PER_CERT", "2"))


def features() -> dict:
    return {
        "ai": bool(ANTHROPIC_API_KEY),
        "transcription": bool(TRANSCRIBE_API_KEY),
        "payments": bool(STRIPE_API_KEY),
        "google_client_id": GOOGLE_CLIENT_ID or None,
        "simulated_token_purchase": SIMULATED_TOKEN_PURCHASE,
        "storage": STORAGE_BACKEND,
        "heartbeat_sec": HEARTBEAT_SEC,
        "lono_price_usd": LONO_PRICE_USD,
        "broadcasting": MEDIA_ENABLED,
        "terms_version": TERMS_VERSION,
        "support_email": SUPPORT_EMAIL or None,
    }


def warn_on_insecure_defaults():
    if JWT_SECRET == "change-me-in-production":
        log.warning("JWT_SECRET is the default value — set a long random secret before deploying.")
    if CORS_ORIGINS == ["*"]:
        log.warning("CORS_ORIGINS is '*' — restrict it to your frontend origin in production.")
