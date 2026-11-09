"""MongoDB handle. MONGO_URL=mongomock:// runs fully in memory (demo/tests)."""
from . import config

if config.MONGO_URL.startswith("mongomock://"):
    from mongomock_motor import AsyncMongoMockClient as _Client
    client = _Client()
else:
    from motor.motor_asyncio import AsyncIOMotorClient as _Client
    client = _Client(config.MONGO_URL, serverSelectionTimeoutMS=5000)  # fail in 5s, not 30s

db = client[config.DB_NAME]


async def ensure_indexes():
    await db.users.create_index("id", unique=True)
    await db.users.create_index("email", unique=True)
    await db.content.create_index("id", unique=True)
    await db.content.create_index([("kind", 1), ("category", 1)])
    await db.channels.create_index("id", unique=True)
    await db.transactions.create_index([("user_id", 1), ("at", -1)])
    await db.watch_sessions.create_index("id", unique=True)
    await db.watch_sessions.create_index([("user_id", 1), ("day", 1)])
    await db.votes.create_index([("proposal_id", 1), ("user_id", 1)], unique=True)
    await db.files.create_index("storage_path", unique=True)
    await db.courses.create_index("id", unique=True)
    await db.enrollments.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    await db.certificates.create_index("id", unique=True)
    await db.reviews.create_index([("course_id", 1), ("user_id", 1)], unique=True)
    await db.reviews.create_index([("course_id", 1), ("updated_at", -1)])
    await db.reviews.create_index("id", unique=True)
    await db.reports.create_index([("status", 1), ("created_at", -1)])
    await db.audit_log.create_index([("at", -1)])
    await db.audit_log.create_index([("action", 1), ("at", -1)])
    await db.ingests.create_index("id", unique=True)
    await db.ingests.create_index("owner_id", unique=True)
    await db.destinations.create_index([("owner_id", 1), ("id", 1)])
    await db.broadcast_sessions.create_index("id", unique=True)
    await db.broadcast_sessions.create_index([("owner_id", 1), ("status", 1)])
    await db.broadcast_events.create_index([("session_id", 1), ("at", 1)])
    await db.recordings.create_index("id", unique=True)
    await db.rooms.create_index("id", unique=True)
    await db.contributors.create_index("id", unique=True)
    await db.contributors.create_index("token_hash", unique=True)
    await db.contributors.create_index([("room_id", 1), ("created_at", 1)])
    await db.room_events.create_index([("room_id", 1), ("at", -1)])
