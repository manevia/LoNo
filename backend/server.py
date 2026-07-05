"""LoNo — Hybrid Media, Broadcasting, Streaming, Learning & Web3 Platform."""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, status, UploadFile, File, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, jwt, bcrypt, stripe, httpx, random, asyncio, io
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ------------------- CONFIG -------------------
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ.get('JWT_SECRET', 'lono_secret')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
stripe.api_key = STRIPE_API_KEY

# ------------------- OBJECT STORAGE -------------------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "lono"
_storage_key: Optional[str] = None
_storage_lock = asyncio.Lock()

async def _get_storage_key(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    async with _storage_lock:
        if _storage_key and not force:
            return _storage_key
        async with httpx.AsyncClient(timeout=30) as hc:
            r = await hc.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY})
            r.raise_for_status()
            _storage_key = r.json()["storage_key"]
    return _storage_key

async def storage_put(path: str, data: bytes, content_type: str) -> dict:
    key = await _get_storage_key()
    async with httpx.AsyncClient(timeout=300) as hc:
        r = await hc.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key, "Content-Type": content_type},
                         content=data)
        if r.status_code == 403:
            key = await _get_storage_key(force=True)
            r = await hc.put(f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": key, "Content-Type": content_type},
                             content=data)
        r.raise_for_status()
        return r.json()

async def storage_get(path: str) -> tuple[bytes, str]:
    key = await _get_storage_key()
    async with httpx.AsyncClient(timeout=120) as hc:
        r = await hc.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key})
        if r.status_code == 403:
            key = await _get_storage_key(force=True)
            r = await hc.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key})
        r.raise_for_status()
        return r.content, r.headers.get("Content-Type", "application/octet-stream")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="LoNo API", version="1.0.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("lono")

# ------------------- MODELS -------------------
def uid(): return str(uuid.uuid4())
def now_iso(): return datetime.now(timezone.utc).isoformat()

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class GoogleSessionIn(BaseModel):
    session_id: str

class ContentCreate(BaseModel):
    title: str
    description: str
    kind: Literal["movie", "series", "short", "music", "podcast", "live_tv", "live_radio", "course"]
    category: str
    thumbnail_url: str
    stream_url: str
    duration_sec: int = 0
    is_original: bool = False
    is_premium: bool = False

class WatchEventIn(BaseModel):
    content_id: str
    seconds_watched: int

class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None

class SummarizeIn(BaseModel):
    content_id: str

class StakeIn(BaseModel):
    amount: float
    lock_days: int = 30

class VoteIn(BaseModel):
    proposal_id: str
    choice: Literal["for", "against", "abstain"]

class CheckoutIn(BaseModel):
    plan: Literal["free", "premium", "creator"]

class TokenBuyIn(BaseModel):
    amount_usd: float

# ------------------- AUTH HELPERS -------------------
def make_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")

async def get_user_optional(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not creds: return None
    try:
        data = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        u = await db.users.find_one({"id": data["sub"]}, {"_id": 0, "password_hash": 0})
        return u
    except Exception:
        return None

async def get_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    u = await get_user_optional(creds)
    if not u:
        raise HTTPException(401, "Not authenticated")
    return u

# ------------------- AUTH ROUTES -------------------
@api.post("/auth/register")
async def register(body: RegisterIn):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    user_id = uid()
    doc = {
        "id": user_id,
        "email": body.email.lower(),
        "name": body.name,
        "password_hash": bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode(),
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}",
        "role": "viewer",
        "provider": "email",
        "created_at": now_iso(),
        "wallet": {"lono_balance": 100.0, "staked": 0.0, "total_earned": 100.0},
        "watch_history": [],
        "subscribed_channels": [],
        "plan": "free",
    }
    await db.users.insert_one(doc)
    await _log_tx(user_id, "signup_bonus", 100.0, "Welcome bonus")
    doc.pop("password_hash", None); doc.pop("_id", None)
    return {"token": make_token(user_id), "user": doc}

@api.post("/auth/login")
async def login(body: LoginIn):
    u = await db.users.find_one({"email": body.email.lower()})
    if not u or not u.get("password_hash"):
        raise HTTPException(400, "Invalid credentials")
    if not bcrypt.checkpw(body.password.encode(), u["password_hash"].encode()):
        raise HTTPException(400, "Invalid credentials")
    u.pop("password_hash", None); u.pop("_id", None)
    return {"token": make_token(u["id"]), "user": u}

@api.post("/auth/google")
async def google_auth(body: GoogleSessionIn):
    """Exchange Emergent Google session_id for LoNo JWT."""
    async with httpx.AsyncClient(timeout=10) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(401, "Invalid Google session")
    d = r.json()
    email = d["email"].lower()
    u = await db.users.find_one({"email": email})
    if not u:
        user_id = uid()
        u = {
            "id": user_id,
            "email": email,
            "name": d.get("name", email.split("@")[0]),
            "avatar_url": d.get("picture", f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}"),
            "role": "viewer",
            "provider": "google",
            "created_at": now_iso(),
            "wallet": {"lono_balance": 100.0, "staked": 0.0, "total_earned": 100.0},
            "watch_history": [], "subscribed_channels": [], "plan": "free",
        }
        await db.users.insert_one(u)
        await _log_tx(user_id, "signup_bonus", 100.0, "Welcome bonus")
    u.pop("password_hash", None); u.pop("_id", None)
    return {"token": make_token(u["id"]), "user": u}

@api.get("/auth/me")
async def me(user=Depends(get_user)):
    return user

# ------------------- CONTENT / STREAMING -------------------
@api.get("/content")
async def list_content(kind: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    q = {}
    if kind: q["kind"] = kind
    if category: q["category"] = category
    items = await db.content.find(q, {"_id": 0}).limit(limit).to_list(limit)
    return items

@api.get("/content/rails")
async def home_rails(user=Depends(get_user_optional)):
    all_items = await db.content.find({}, {"_id": 0}).to_list(500)
    def pick(pred, n=12):
        return [c for c in all_items if pred(c)][:n]
    rails = [
        {"key": "featured", "title": "Featured Today", "items": pick(lambda c: c.get("is_original"), 8)},
        {"key": "trending", "title": "Trending Now", "items": random.sample(all_items, min(12, len(all_items)))},
        {"key": "top10", "title": "Top 10 in Your Region", "items": all_items[:10]},
        {"key": "originals", "title": "LoNo Originals", "items": pick(lambda c: c.get("is_original"), 12)},
        {"key": "new", "title": "New Releases", "items": sorted(all_items, key=lambda c: c.get("created_at", ""), reverse=True)[:12]},
        {"key": "movies", "title": "Movies", "items": pick(lambda c: c.get("kind") == "movie", 12)},
        {"key": "series", "title": "Series", "items": pick(lambda c: c.get("kind") == "series", 12)},
        {"key": "podcasts", "title": "Popular Podcasts", "items": pick(lambda c: c.get("kind") == "podcast", 12)},
        {"key": "music", "title": "Sounds of the Moment", "items": pick(lambda c: c.get("kind") == "music", 12)},
    ]
    if user:
        history_ids = [h["content_id"] for h in user.get("watch_history", [])][:12]
        cw = [c for c in all_items if c["id"] in history_ids]
        if cw:
            rails.insert(0, {"key": "continue", "title": "Continue Watching", "items": cw})
    return rails

@api.get("/content/{content_id}")
async def get_content(content_id: str):
    c = await db.content.find_one({"id": content_id}, {"_id": 0})
    if not c: raise HTTPException(404, "Not found")
    creator = await db.channels.find_one({"id": c.get("channel_id")}, {"_id": 0}) if c.get("channel_id") else None
    c["channel"] = creator
    similar = await db.content.find({"category": c["category"], "id": {"$ne": content_id}}, {"_id": 0}).limit(8).to_list(8)
    c["similar"] = similar
    return c

@api.post("/content/watch")
async def record_watch(body: WatchEventIn, user=Depends(get_user)):
    c = await db.content.find_one({"id": body.content_id})
    if not c: raise HTTPException(404, "Content not found")
    # Watch-to-Earn: 1 LONO per minute, capped 10 per event
    minutes = max(0, body.seconds_watched // 60)
    reward = min(minutes * 1.0, 10.0)
    entry = {"content_id": body.content_id, "seconds": body.seconds_watched, "at": now_iso()}
    await db.users.update_one(
        {"id": user["id"]},
        {"$push": {"watch_history": {"$each": [entry], "$position": 0, "$slice": 100}}},
    )
    if reward > 0:
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"wallet.lono_balance": reward, "wallet.total_earned": reward}},
        )
        await _log_tx(user["id"], "watch_to_earn", reward, f"Watched: {c['title']}")
    await db.content.update_one({"id": body.content_id}, {"$inc": {"views": 1}})
    return {"reward": reward, "message": f"You earned {reward} $LONO"}

@api.get("/live/channels")
async def live_channels():
    tv = await db.content.find({"kind": "live_tv"}, {"_id": 0}).to_list(50)
    radio = await db.content.find({"kind": "live_radio"}, {"_id": 0}).to_list(50)
    return {"tv": tv, "radio": radio}

@api.get("/search")
async def search(q: str):
    if not q: return []
    items = await db.content.find(
        {"$or": [{"title": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}, {"category": {"$regex": q, "$options": "i"}}]},
        {"_id": 0},
    ).limit(40).to_list(40)
    return items

@api.get("/channels")
async def list_channels():
    return await db.channels.find({}, {"_id": 0}).to_list(100)

@api.get("/channels/{channel_id}")
async def get_channel(channel_id: str):
    ch = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not ch: raise HTTPException(404, "Not found")
    ch["content"] = await db.content.find({"channel_id": channel_id}, {"_id": 0}).to_list(100)
    return ch

# ------------------- CREATOR STUDIO -------------------
@api.get("/creator/dashboard")
async def creator_dash(user=Depends(get_user)):
    ch = await db.channels.find_one({"owner_id": user["id"]}, {"_id": 0})
    if not ch:
        # Auto-provision a channel on first visit
        ch = {
            "id": uid(),
            "owner_id": user["id"],
            "name": f"{user['name']}'s Channel",
            "handle": f"@{user['name'].lower().replace(' ', '')}_{user['id'][:4]}",
            "banner_url": "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwxfHxwb2RjYXN0ZXIlMjBzdHVkaW8lMjBtaWNyb3Bob25lfGVufDB8fHx8MTc4MzI1MDY0OHww&ixlib=rb-4.1.0&q=85",
            "avatar_url": user["avatar_url"],
            "bio": "New creator on LoNo",
            "subscribers": 0,
            "created_at": now_iso(),
        }
        await db.channels.insert_one(ch)
        ch.pop("_id", None)
    videos = await db.content.find({"channel_id": ch["id"]}, {"_id": 0}).to_list(100)
    total_views = sum(v.get("views", 0) for v in videos)
    # Revenue: $0.005 per view (simulated)
    revenue = round(total_views * 0.005, 2)
    return {
        "channel": ch,
        "videos": videos,
        "stats": {
            "subscribers": ch.get("subscribers", 0),
            "total_views": total_views,
            "videos_count": len(videos),
            "revenue_usd": revenue,
            "lono_earned": round(total_views * 0.05, 2),
        },
        "chart": [
            {"day": (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%b %d"),
             "views": random.randint(200, 2000)} for i in range(13, -1, -1)
        ],
    }

@api.post("/creator/upload")
async def creator_upload(body: ContentCreate, user=Depends(get_user)):
    ch = await db.channels.find_one({"owner_id": user["id"]}, {"_id": 0})
    if not ch:
        raise HTTPException(400, "Create channel first via /creator/dashboard")
    doc = {
        **body.model_dump(),
        "id": uid(),
        "channel_id": ch["id"],
        "views": 0,
        "likes": 0,
        "created_at": now_iso(),
    }
    await db.content.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ------------------- WALLET / TOKEN -------------------
async def _log_tx(user_id: str, kind: str, amount: float, memo: str):
    await db.transactions.insert_one({
        "id": uid(), "user_id": user_id, "kind": kind, "amount": amount, "memo": memo, "at": now_iso(),
    })

@api.get("/wallet")
async def wallet(user=Depends(get_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    stakes = await db.stakes.find({"user_id": user["id"], "active": True}, {"_id": 0}).to_list(50)
    return {"wallet": u["wallet"], "stakes": stakes, "address": f"lono1{user['id'].replace('-','')[:38]}"}

@api.get("/wallet/transactions")
async def wallet_tx(user=Depends(get_user)):
    return await db.transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("at", -1).limit(100).to_list(100)

@api.post("/wallet/stake")
async def stake(body: StakeIn, user=Depends(get_user)):
    u = await db.users.find_one({"id": user["id"]})
    if u["wallet"]["lono_balance"] < body.amount:
        raise HTTPException(400, "Insufficient balance")
    apy = {30: 8, 90: 14, 180: 22, 365: 35}.get(body.lock_days, 8)
    stake_doc = {
        "id": uid(), "user_id": user["id"], "amount": body.amount,
        "lock_days": body.lock_days, "apy": apy, "active": True,
        "started_at": now_iso(),
        "unlock_at": (datetime.now(timezone.utc) + timedelta(days=body.lock_days)).isoformat(),
    }
    await db.stakes.insert_one(stake_doc)
    await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet.lono_balance": -body.amount, "wallet.staked": body.amount}})
    await _log_tx(user["id"], "stake", -body.amount, f"Staked for {body.lock_days}d @ {apy}% APY")
    stake_doc.pop("_id", None)
    return stake_doc

@api.post("/wallet/unstake/{stake_id}")
async def unstake(stake_id: str, user=Depends(get_user)):
    s = await db.stakes.find_one({"id": stake_id, "user_id": user["id"], "active": True})
    if not s: raise HTTPException(404, "Stake not found")
    # Compute rewards
    started = datetime.fromisoformat(s["started_at"])
    days = max(1, (datetime.now(timezone.utc) - started).days)
    reward = round(s["amount"] * (s["apy"] / 100) * (days / 365), 4)
    total = s["amount"] + reward
    await db.stakes.update_one({"id": stake_id}, {"$set": {"active": False, "ended_at": now_iso(), "reward": reward}})
    await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet.lono_balance": total, "wallet.staked": -s["amount"], "wallet.total_earned": reward}})
    await _log_tx(user["id"], "unstake", total, f"Unstaked +{reward} reward")
    return {"returned": total, "reward": reward}

@api.get("/tokenomics")
async def tokenomics():
    total_users = await db.users.count_documents({})
    total_staked = 0.0
    async for u in db.users.find({}, {"wallet": 1}):
        total_staked += u.get("wallet", {}).get("staked", 0.0)
    circulating = 250_000_000
    max_supply = 1_000_000_000
    burned = 12_500_000
    treasury = 350_000_000
    return {
        "symbol": "LONO",
        "name": "LoNo Utility Token",
        "circulating_supply": circulating,
        "max_supply": max_supply,
        "burned": burned,
        "treasury": treasury,
        "creator_fund": 120_000_000,
        "education_fund": 80_000_000,
        "community_fund": 60_000_000,
        "rewards_distributed": 45_231_512,
        "total_wallets": max(total_users, 128_540),
        "total_staked": total_staked,
        "price_usd": 0.184,
        "market_cap": circulating * 0.184,
        "change_24h": 4.72,
        "network_health": 98.6,
        "chart_7d": [
            {"day": (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%a"),
             "price": round(0.15 + random.random() * 0.06, 4)} for i in range(6, -1, -1)
        ],
        "allocation": [
            {"name": "Community & Rewards", "value": 35},
            {"name": "Treasury", "value": 20},
            {"name": "Creator Fund", "value": 15},
            {"name": "Education Fund", "value": 10},
            {"name": "Team & Advisors", "value": 12},
            {"name": "Public Sale", "value": 8},
        ],
    }

# ------------------- GOVERNANCE -------------------
@api.get("/governance/proposals")
async def proposals():
    props = await db.proposals.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return props

@api.post("/governance/vote")
async def vote(body: VoteIn, user=Depends(get_user)):
    p = await db.proposals.find_one({"id": body.proposal_id})
    if not p: raise HTTPException(404, "Proposal not found")
    u = await db.users.find_one({"id": user["id"]})
    power = u["wallet"]["lono_balance"] + u["wallet"]["staked"] * 2
    if power < 1:
        raise HTTPException(400, "Insufficient voting power")
    existing = await db.votes.find_one({"proposal_id": body.proposal_id, "user_id": user["id"]})
    if existing:
        raise HTTPException(400, "Already voted on this proposal")
    await db.votes.insert_one({
        "id": uid(), "proposal_id": body.proposal_id, "user_id": user["id"],
        "choice": body.choice, "power": power, "at": now_iso(),
    })
    await db.proposals.update_one({"id": body.proposal_id}, {"$inc": {f"votes.{body.choice}": power}})
    return {"ok": True, "power": power}

# ------------------- AI (Claude via emergentintegrations) -------------------
@api.post("/ai/chat")
async def ai_chat(body: ChatIn, user=Depends(get_user_optional)):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    session_id = body.session_id or uid()
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=(
            "You are LoNo AI, a helpful assistant inside the LoNo streaming, learning, and Web3 platform. "
            "Users can ask about content, tokens ($LONO), staking, creator tools, and governance. "
            "Keep answers concise, friendly, and informative. Use markdown-style bullets when helpful."
        ),
    ).with_model("anthropic", "claude-sonnet-4-5")
    try:
        reply = await chat.send_message(UserMessage(text=body.message))
    except Exception as e:
        log.exception("ai_chat")
        raise HTTPException(500, f"AI error: {e}")
    return {"reply": reply, "session_id": session_id}

@api.post("/ai/summarize")
async def ai_summarize(body: SummarizeIn, user=Depends(get_user_optional)):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    c = await db.content.find_one({"id": body.content_id})
    if not c: raise HTTPException(404, "Content not found")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"sum_{body.content_id}",
        system_message="You produce concise 3-sentence summaries and 5 SEO tags for streaming content.",
    ).with_model("anthropic", "claude-sonnet-4-5")
    prompt = f"Title: {c['title']}\nCategory: {c['category']}\nDescription: {c['description']}\n\nReturn a compelling 3-sentence summary followed by a line 'Tags:' with 5 comma-separated SEO tags."
    try:
        text = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"summary": text}

@api.get("/ai/recommend")
async def ai_recommend(user=Depends(get_user)):
    """Recommendations based on watch history categories."""
    history_ids = [h["content_id"] for h in user.get("watch_history", [])][:20]
    watched = await db.content.find({"id": {"$in": history_ids}}, {"_id": 0}).to_list(20)
    categories = list({w["category"] for w in watched}) or ["Drama", "Documentary"]
    recs = await db.content.find(
        {"category": {"$in": categories}, "id": {"$nin": history_ids}}, {"_id": 0}
    ).limit(12).to_list(12)
    return {"based_on": categories, "items": recs}

# ------------------- PAYMENTS -------------------
@api.post("/payments/checkout")
async def stripe_checkout(body: CheckoutIn, user=Depends(get_user)):
    prices = {"premium": 999, "creator": 2499}
    if body.plan not in prices:
        return {"url": None, "message": "Free plan activated"}
    try:
        origin = os.environ.get("PUBLIC_ORIGIN", "https://lono-preview.preview.emergentagent.com")
        s = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": prices[body.plan],
                    "recurring": {"interval": "month"},
                    "product_data": {"name": f"LoNo {body.plan.title()} Plan"},
                },
                "quantity": 1,
            }],
            success_url=f"{origin}/wallet?checkout=success",
            cancel_url=f"{origin}/wallet?checkout=cancelled",
            metadata={"user_id": user["id"], "plan": body.plan},
        )
        return {"url": s.url, "session_id": s.id}
    except Exception as e:
        log.exception("stripe")
        raise HTTPException(500, f"Stripe error: {e}")

@api.post("/payments/token-buy")
async def token_buy(body: TokenBuyIn, user=Depends(get_user)):
    """Simulated crypto/token purchase: 1 USD ~ 5.43 LONO at $0.184."""
    tokens = round(body.amount_usd / 0.184, 4)
    await db.users.update_one({"id": user["id"]}, {"$inc": {"wallet.lono_balance": tokens, "wallet.total_earned": tokens}})
    await _log_tx(user["id"], "token_purchase", tokens, f"Bought {tokens} LONO for ${body.amount_usd}")
    return {"tokens": tokens, "message": f"Acquired {tokens} $LONO"}

# ------------------- SEED -------------------
SEED_IMAGES = {
    "movie": [
        "https://images.unsplash.com/photo-1782020934325-cfe4cea4fd9c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1778585040075-0991abfd4ed9?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwzfHxjaW5lbWF0aWMlMjBtb3ZpZSUyMHBvc3RlciUyMGRhcmt8ZW58MHx8fHwxNzgzMjUwNjQ4fDA&ixlib=rb-4.1.0&q=85",
        "https://images.pexels.com/photos/3137890/pexels-photo-3137890.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    ],
    "live": [
        "https://images.pexels.com/photos/9072394/pexels-photo-9072394.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzB8MHwxfHNlYXJjaHwyfHxsaXZlJTIwY29uY2VydCUyMHN0YWdlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDl8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzB8MHwxfHNlYXJjaHwxfHxsaXZlJTIwY29uY2VydCUyMHN0YWdlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDl8MA&ixlib=rb-4.1.0&q=85",
    ],
    "podcast": [
        "https://images.unsplash.com/photo-1655947717064-d856af599bd1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwxfHxwb2RjYXN0ZXIlMjBzdHVkaW8lMjBtaWNyb3Bob25lfGVufDB8fHx8MTc4MzI1MDY0OHww&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1636294155433-29863ca33aa6?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwyfHxwb2RjYXN0ZXIlMjBzdHVkaW8lMjBtaWNyb3Bob25lfGVufDB8fHx8MTc4MzI1MDY0OHww&ixlib=rb-4.1.0&q=85",
    ],
    "abstract": [
        "https://images.unsplash.com/photo-1759771963975-8a4885446f1f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1737505599162-d9932323a889?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
        "https://images.unsplash.com/photo-1775057154553-0f3e8902fea3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjh8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMG5ldHdvcmslMjBub2RlJTIwZGFya3xlbnwwfHx8fDE3ODMyNTA2NDh8MA&ixlib=rb-4.1.0&q=85",
    ],
}

SAMPLE_VIDEO = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
SAMPLE_AUDIO = "https://download.samplelib.com/mp3/sample-3s.mp3"

async def seed_if_empty():
    if await db.content.count_documents({}) > 0:
        return
    log.info("Seeding LoNo demo content...")

    channels_data = [
        ("Aurora Studios", "@aurora", "Cinematic originals & documentaries.", 245000),
        ("Neon Beats", "@neon", "Late-night music & indie sessions.", 189000),
        ("Cortex Learning", "@cortex", "Deep-dive tech & science courses.", 412000),
        ("BroadWave Radio", "@broadwave", "24/7 talk, news & culture.", 76000),
        ("Solstice Cinema", "@solstice", "Sci-fi originals & short films.", 358000),
        ("Meridian Podcasts", "@meridian", "Long-form interviews and ideas.", 121000),
    ]
    channels = []
    for name, handle, bio, subs in channels_data:
        cid = uid()
        ch = {
            "id": cid, "owner_id": "system", "name": name, "handle": handle,
            "banner_url": SEED_IMAGES["abstract"][len(channels) % 3],
            "avatar_url": f"https://api.dicebear.com/7.x/shapes/svg?seed={handle}",
            "bio": bio, "subscribers": subs, "created_at": now_iso(),
        }
        channels.append(ch)
    await db.channels.insert_many(channels)

    titles = {
        "movie": [
            ("Midnight Static", "Drama", "A hacker's late-night discovery unravels a corporate empire."),
            ("Solar Flare", "Sci-Fi", "Astronauts race to prevent a catastrophic solar event."),
            ("The Cartographer", "Thriller", "A mapmaker inherits a chart to a hidden city."),
            ("Ember & Ash", "Drama", "Two sisters rebuild their lives after the fire."),
            ("Verdant Machine", "Sci-Fi", "Nature and AI collide in a lost Amazonian temple."),
            ("Nightingale Protocol", "Action", "A rogue agent breaks the silence."),
        ],
        "series": [
            ("Hollow Cities", "Drama", "Six strangers, one collapsing metropolis."),
            ("Quantum Diaries", "Sci-Fi", "Time-jumping researchers seek the anomaly."),
            ("The Broadcast", "Mystery", "A pirate radio show predicts real crimes."),
            ("Aurora Kids", "Family", "A whimsical adventure for young explorers."),
        ],
        "podcast": [
            ("Signal Path", "Tech", "Conversations at the edge of software and life."),
            ("Deep Focus", "Business", "Founders on building at scale."),
            ("Studio Sessions", "Music", "Musicians dissect their creative process."),
            ("Meridian Notes", "Culture", "Long-form ideas from the world's best thinkers."),
        ],
        "music": [
            ("After Hours EP", "Electronic", "A moody electronic set for late-night hours."),
            ("Solstice", "Ambient", "Ambient textures for focused work."),
            ("Neon Highway", "Synthwave", "Drive fast, feel the neon."),
            ("Analog Church", "Indie", "Warm indie recorded to tape."),
        ],
        "short": [
            ("60 Seconds in Tokyo", "Travel", "A minute of neon-drenched Shibuya."),
            ("Studio Cut", "Behind the Scenes", "Inside a director's edit bay."),
        ],
        "course": [
            ("Foundations of Web3", "Education", "Understand tokens, wallets, and DAOs in 10 lessons."),
            ("AI for Creators", "Education", "Practical AI tools for creators and studios."),
        ],
        "live_tv": [
            ("LoNo News 24", "News", "Rolling world news around the clock."),
            ("Culture Live", "Culture", "Interviews, performances, and events."),
            ("Sports Central", "Sports", "Live commentary and analysis."),
            ("Cinema Classics", "Movies", "Curated classic cinema, all day."),
        ],
        "live_radio": [
            ("BroadWave 101", "Talk", "Talk radio for curious minds."),
            ("Neon FM", "Music", "Non-stop synthwave and indie."),
            ("Meridian Voices", "Interview", "Long-form interviews on air."),
        ],
    }
    content_docs = []
    all_channels = channels
    for kind, entries in titles.items():
        for title, cat, desc in entries:
            ch = random.choice(all_channels)
            img_pool = SEED_IMAGES["live"] if kind in ("live_tv", "live_radio") else \
                       SEED_IMAGES["podcast"] if kind in ("podcast",) else \
                       SEED_IMAGES["abstract"] if kind in ("music", "course") else \
                       SEED_IMAGES["movie"]
            content_docs.append({
                "id": uid(),
                "title": title,
                "description": desc,
                "kind": kind,
                "category": cat,
                "thumbnail_url": random.choice(img_pool),
                "stream_url": SAMPLE_AUDIO if kind in ("music", "podcast", "live_radio") else SAMPLE_VIDEO,
                "duration_sec": random.randint(600, 7200) if kind not in ("live_tv", "live_radio") else 0,
                "is_original": random.random() > 0.5,
                "is_premium": random.random() > 0.7,
                "channel_id": ch["id"],
                "views": random.randint(1000, 950000),
                "likes": random.randint(100, 45000),
                "rating": round(random.uniform(3.5, 4.9), 1),
                "year": random.randint(2020, 2026),
                "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90))).isoformat(),
            })
    await db.content.insert_many(content_docs)

    # Governance proposals
    props = [
        {"id": uid(), "title": "Increase Creator Fund by 25M $LONO",
         "summary": "Expand grants for emerging creators focused on documentary and educational content.",
         "status": "active", "votes": {"for": 1240000, "against": 210000, "abstain": 45000},
         "ends_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Enable Learn-to-Earn Multiplier during Q2",
         "summary": "Double LONO rewards for completing certified courses during Q2 2026.",
         "status": "active", "votes": {"for": 890000, "against": 175000, "abstain": 30000},
         "ends_at": (datetime.now(timezone.utc) + timedelta(days=12)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Launch Community-Curated Live TV Channel",
         "summary": "Allow token holders to curate a 24/7 live channel by weekly vote.",
         "status": "active", "votes": {"for": 512000, "against": 420000, "abstain": 60000},
         "ends_at": (datetime.now(timezone.utc) + timedelta(days=8)).isoformat(), "created_at": now_iso()},
        {"id": uid(), "title": "Burn 5M $LONO from Treasury (Executed)",
         "summary": "Reduce circulating supply to strengthen network economics.",
         "status": "passed", "votes": {"for": 2100000, "against": 320000, "abstain": 80000},
         "ends_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(), "created_at": now_iso()},
    ]
    await db.proposals.insert_many(props)
    log.info(f"Seeded {len(content_docs)} content items, {len(channels)} channels, {len(props)} proposals.")

# ------------------- STORAGE UPLOAD / DOWNLOAD -------------------
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
ALLOWED_MIME = {"video/", "audio/", "image/"}

@api.post("/storage/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(get_user)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 100MB)")
    ct = file.content_type or "application/octet-stream"
    if not any(ct.startswith(prefix) for prefix in ALLOWED_MIME):
        raise HTTPException(400, "Only video, audio, or image files allowed")
    filename = file.filename or "upload.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    file_id = uid()
    path = f"{APP_NAME}/uploads/{user['id']}/{file_id}.{ext}"
    try:
        result = await storage_put(path, data, ct)
    except httpx.HTTPStatusError as e:
        log.exception("storage_put")
        raise HTTPException(502, f"Storage upload failed: {e.response.status_code}")
    stored_path = result.get("path", path)
    await db.files.insert_one({
        "id": file_id, "user_id": user["id"], "storage_path": stored_path,
        "original_filename": filename, "content_type": ct,
        "size": result.get("size", len(data)),
        "is_deleted": False, "created_at": now_iso(),
    })
    return {
        "file_id": file_id, "path": stored_path,
        "url": f"/api/files/{stored_path}",
        "content_type": ct, "size": len(data),
    }

@api.get("/files/{path:path}")
async def download_file(path: str):
    rec = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not rec:
        raise HTTPException(404, "File not found")
    try:
        data, ct = await storage_get(path)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, "File not found in storage")
        raise HTTPException(502, f"Storage read failed: {e.response.status_code}")
    return Response(content=data, media_type=rec.get("content_type", ct),
                    headers={"Cache-Control": "public, max-age=3600"})

# ------------------- WHISPER TRANSCRIPTION -------------------
def _fmt_vtt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def _segments_to_vtt(segments, fallback_text: str = "") -> str:
    lines = ["WEBVTT", ""]
    if not segments:
        lines += ["00:00:00.000 --> 00:05:00.000", (fallback_text or "").strip(), ""]
        return "\n".join(lines)
    for seg in segments:
        start = getattr(seg, "start", None)
        end = getattr(seg, "end", None)
        text = getattr(seg, "text", "") or ""
        if start is None or end is None:
            continue
        lines.append(f"{_fmt_vtt_time(start)} --> {_fmt_vtt_time(end)}")
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)

@api.post("/ai/transcribe/{content_id}")
async def ai_transcribe(content_id: str, user=Depends(get_user)):
    from emergentintegrations.llm.openai import OpenAISpeechToText
    c = await db.content.find_one({"id": content_id})
    if not c:
        raise HTTPException(404, "Content not found")
    if c.get("subtitles_vtt"):
        return {"vtt": c["subtitles_vtt"], "text": c.get("transcript", ""), "cached": True}

    src = c.get("stream_url") or ""
    try:
        if src.startswith("/api/files/"):
            path = src.split("/api/files/", 1)[1]
            data, ct = await storage_get(path)
        else:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as hc:
                r = await hc.get(src, headers={"User-Agent": "Mozilla/5.0 LoNoBot/1.0"})
                r.raise_for_status()
                data = r.content
                ct = r.headers.get("Content-Type", "audio/mpeg")
    except Exception as e:
        raise HTTPException(502, f"Could not fetch media: {e}")

    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Media exceeds Whisper's 25MB limit. Please upload a shorter clip.")

    ext_guess = "mp4" if "video" in ct else ("mp3" if "audio" in ct else "wav")
    buf = io.BytesIO(data)
    buf.name = f"media.{ext_guess}"

    try:
        stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
        resp = await stt.transcribe(
            file=buf, model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    except Exception as e:
        log.exception("whisper")
        raise HTTPException(500, f"Transcription failed: {e}")

    text = getattr(resp, "text", "") or ""
    segments = getattr(resp, "segments", []) or []
    vtt = _segments_to_vtt(segments, fallback_text=text)
    await db.content.update_one(
        {"id": content_id},
        {"$set": {"subtitles_vtt": vtt, "transcript": text,
                  "subtitle_lang": getattr(resp, "language", "en")}},
    )
    return {"vtt": vtt, "text": text, "cached": False}

@api.get("/content/{content_id}/subtitles.vtt")
async def content_subtitles(content_id: str):
    c = await db.content.find_one({"id": content_id})
    if not c or not c.get("subtitles_vtt"):
        raise HTTPException(404, "No subtitles available")
    return Response(content=c["subtitles_vtt"], media_type="text/vtt",
                    headers={"Cache-Control": "public, max-age=3600"})

@app.on_event("startup")
async def on_startup():
    await seed_if_empty()
    try:
        await _get_storage_key()
        log.info("Emergent object storage initialized")
    except Exception as e:
        log.warning(f"Storage init deferred: {e}")

@api.get("/")
async def root():
    return {"service": "LoNo", "version": "1.0.0", "status": "ok"}

@api.get("/health")
async def health():
    return {"status": "healthy", "time": now_iso()}

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    client.close()
