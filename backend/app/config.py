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
    }


def warn_on_insecure_defaults():
    if JWT_SECRET == "change-me-in-production":
        log.warning("JWT_SECRET is the default value — set a long random secret before deploying.")
    if CORS_ORIGINS == ["*"]:
        log.warning("CORS_ORIGINS is '*' — restrict it to your frontend origin in production.")
