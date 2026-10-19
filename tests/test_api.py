import base64
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.main import MAX_UPLOAD_BYTES, app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

# 1x1 transparent PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"\x00" * 16


def post(name, data, ctype="image/png"):
    return client.post("/api/upload", files={"file": (name, data, ctype)})


def assert_error(resp, status, code):
    assert resp.status_code == status
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"success": True, "message": "INCI Sight backend is running"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "healthy"}


def test_info():
    body = client.get("/api/info").json()
    assert body["success"] is True
    assert body["supported_formats"] == ["JPG", "JPEG", "PNG", "WEBP"]
    assert body["max_upload_bytes"] == MAX_UPLOAD_BYTES


def test_valid_uploads():
    for name, data, ctype, fmt in [
        ("label.png", PNG, "image/png", "png"),
        ("label.JPG", JPEG, "image/jpeg", "jpeg"),
        ("label.jpeg", JPEG, "image/jpeg", "jpeg"),
        ("label.webp", WEBP, "image/webp", "webp"),
    ]:
        r = post(name, data, ctype)
        assert r.status_code == 200, r.text
        f = r.json()["file"]
        assert f["filename"] == name and f["size_bytes"] == len(data) and f["detected_format"] == fmt


def test_unsupported_extension():
    assert_error(post("notes.txt", b"hello", "text/plain"), 415, "unsupported_format")


def test_invalid_image_content():
    assert_error(post("fake.png", b"this is not an image"), 400, "invalid_image")


def test_extension_content_mismatch():
    assert_error(post("fake.png", JPEG), 400, "invalid_image")


def test_empty_upload():
    assert_error(post("empty.png", b""), 400, "empty_file")


def test_oversized_upload():
    assert_error(post("big.png", PNG + b"\x00" * MAX_UPLOAD_BYTES), 413, "file_too_large")


def test_missing_file_field():
    assert_error(client.post("/api/upload"), 422, "invalid_request")


def test_unknown_route_uses_error_format():
    assert_error(client.get("/nope"), 404, "not_found")


def test_unexpected_error_hides_details(monkeypatch):
    import backend.main as m

    monkeypatch.setattr(m, "detect_image_format", lambda d: 1 / 0)
    r = post("a.png", PNG)
    assert_error(r, 500, "server_error")
    assert "ZeroDivision" not in r.text and "Traceback" not in r.text