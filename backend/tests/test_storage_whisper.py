"""Tests for Emergent Object Storage upload/download and Whisper transcription."""
import os
import uuid
import io
import struct
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"


# --- helpers ---
def _tiny_jpeg_bytes() -> bytes:
    # 1x1 white JPEG (baseline). Minimal valid JPEG.
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "07090908") + b"\xff\xd9"  # not fully valid but content_type sniff at server is via UploadFile.content_type header

# We can't easily hand-craft a valid JPEG; use a real minimal one:
MINIMAL_JPEG = bytes.fromhex(
    "FFD8FFE000104A46494600010101006000600000FFDB004300080606070605080707"
    "070909080A0C140D0C0B0B0C1912130F141D1A1F1E1D1A1C1C20242E2720222C231C"
    "1C2837292C30313434341F27393D38323C2E333432FFDB0043010909090C0B0C180D"
    "0D1832211C213232323232323232323232323232323232323232323232323232323232"
    "323232323232323232323232323232323232323232FFC00011080001000103012200"
    "021101031101FFC4001F0000010501010101010100000000000000000102030405060"
    "708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131"
    "410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25"
    "262728292A3435363738393A434445464748494A535455565758595A636465666768696A"
    "737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3"
    "B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1"
    "F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405"
    "060708090A0BFFC400B51100020102040403040705040400010277000102031104052131"
    "06124151076171132232810814429115A1B1C109233352F0156272D10A162434E125F117"
    "1819191A262728292A35363738393A434445464748494A535455565758595A636465666768"
    "696A737475767778797A82838485868788898A92939495969798999AA2A3A4A5A6A7A8A9"
    "AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE2E3E4E5E6E7E8E9"
    "EAF2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00FBD0A28A2803FFD9"
)


@pytest.fixture(scope="session")
def unique_email():
    return f"TEST_{uuid.uuid4().hex[:10]}@lono.io"


@pytest.fixture(scope="session")
def token(unique_email):
    r = requests.post(f"{API}/auth/register", json={
        "email": unique_email, "password": "Passw0rd!", "name": "Storage Tester"
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Storage upload / files ---
class TestStorageUpload:
    def test_upload_jpeg_and_download(self, auth_headers):
        files = {"file": ("test.jpg", MINIMAL_JPEG, "image/jpeg")}
        r = requests.post(f"{API}/storage/upload", files=files, headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "file_id" in d and "path" in d
        assert d["url"].startswith("/api/files/")
        assert d["content_type"] == "image/jpeg"
        assert d["size"] > 0
        # download via /api/files/{path}
        get_url = f"{BASE_URL}{d['url']}"
        g = requests.get(get_url, timeout=30)
        assert g.status_code == 200
        assert g.headers.get("Content-Type", "").startswith("image/jpeg")
        assert len(g.content) > 0
        # save for other tests
        pytest.jpeg_path = d["path"]
        pytest.jpeg_url = d["url"]

    def test_upload_mp3(self, auth_headers):
        # download a real tiny mp3
        mp3 = requests.get("https://download.samplelib.com/mp3/sample-3s.mp3", timeout=60).content
        assert len(mp3) > 100
        files = {"file": ("sample.mp3", mp3, "audio/mpeg")}
        r = requests.post(f"{API}/storage/upload", files=files, headers=auth_headers, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["url"].startswith("/api/files/lono/uploads/")
        assert d["url"].endswith(".mp3")
        assert d["content_type"].startswith("audio/")
        pytest.mp3_url = d["url"]
        pytest.mp3_path = d["path"]

    def test_upload_no_auth(self):
        files = {"file": ("test.jpg", MINIMAL_JPEG, "image/jpeg")}
        r = requests.post(f"{API}/storage/upload", files=files, timeout=30)
        # HTTPBearer(auto_error=False) → dependency raises 401
        assert r.status_code == 401, r.text

    def test_upload_disallowed_mime(self, auth_headers):
        files = {"file": ("note.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/storage/upload", files=files, headers=auth_headers, timeout=30)
        assert r.status_code == 400
        assert "video, audio, or image" in r.text.lower()


# --- Transcription pipeline ---
class TestTranscribe:
    def test_full_flow(self, auth_headers):
        # 1. ensure mp3 uploaded (rely on prior test but re-upload if missing)
        mp3_url = getattr(pytest, "mp3_url", None)
        if not mp3_url:
            mp3 = requests.get("https://download.samplelib.com/mp3/sample-3s.mp3", timeout=60).content
            files = {"file": ("sample.mp3", mp3, "audio/mpeg")}
            up = requests.post(f"{API}/storage/upload", files=files, headers=auth_headers, timeout=120)
            assert up.status_code == 200
            mp3_url = up.json()["url"]

        # 2. create content via /creator/upload
        # Provision channel first
        r = requests.get(f"{API}/creator/dashboard", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        content_body = {
            "title": "TEST Whisper Clip",
            "description": "tiny mp3 for whisper",
            "kind": "podcast",
            "category": "Tech",
            "thumbnail_url": "https://images.unsplash.com/photo-1655947717064-d856af599bd1",
            "stream_url": mp3_url,
            "duration_sec": 3,
        }
        r = requests.post(f"{API}/creator/upload",
                          json=content_body,
                          headers={**auth_headers, "Content-Type": "application/json"}, timeout=30)
        assert r.status_code == 200, r.text
        content_id = r.json()["id"]
        pytest.tx_content_id = content_id

        # 3. transcribe first call
        r = requests.post(f"{API}/ai/transcribe/{content_id}", headers=auth_headers, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["vtt"].startswith("WEBVTT")
        assert d.get("cached") is False

        # 4. transcribe second call → cached
        r = requests.post(f"{API}/ai/transcribe/{content_id}", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        assert r.json().get("cached") is True

        # 5. subtitles.vtt endpoint
        r = requests.get(f"{API}/content/{content_id}/subtitles.vtt", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("Content-Type", "").startswith("text/vtt")
        assert r.text.startswith("WEBVTT")

    def test_subtitles_404_when_not_transcribed(self, auth_headers):
        # create fresh content but do NOT transcribe
        mp3_url = getattr(pytest, "mp3_url", None) or "/api/files/nonexistent.mp3"
        body = {
            "title": "TEST NoSubs", "description": "no subs",
            "kind": "podcast", "category": "Tech",
            "thumbnail_url": "https://x/y.jpg", "stream_url": mp3_url, "duration_sec": 3,
        }
        r = requests.post(f"{API}/creator/upload", json=body,
                          headers={**auth_headers, "Content-Type": "application/json"}, timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]
        r = requests.get(f"{API}/content/{cid}/subtitles.vtt", timeout=30)
        assert r.status_code == 404
