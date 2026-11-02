import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

os.environ.update({
    "MONGO_URL": "mongomock://", "DB_NAME": "lono_test", "JWT_SECRET": "test-secret",
    "LOCAL_STORAGE_DIR": tempfile.mkdtemp(), "ANTHROPIC_API_KEY": "", "TRANSCRIBE_API_KEY": "",
    "OPENAI_API_KEY": "", "STRIPE_API_KEY": "", "GOOGLE_CLIENT_ID": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(client):
    email = f"u_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "Passw0rd!", "name": "Test User"})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "id": d["user"]["id"],
            "h": {"Authorization": f"Bearer {d['token']}"}}
