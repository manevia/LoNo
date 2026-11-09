"""MongoDB handle. MONGO_URL=mongomock:// runs fully in memory (demo/tests)."""
from . import config

if config.MONGO_URL.startswith("mongomock://"):
    from mongomock_motor import AsyncMongoMockClient as _Client
    client = _Client()
else:
    from motor.motor_asyncio import AsyncIOMotorClient as _Client
    client = _Client(config.MONGO_URL)

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
