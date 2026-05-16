import asyncio
import base64
import io
import os

os.environ.setdefault("BOT_TOKEN", "123456:ABCDEF")
os.environ.setdefault("REPLICATE_API_TOKEN", "dummy")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")

from PIL import Image
from fastapi.testclient import TestClient

import app


def image_bytes(size=(640, 640), mode="RGB", fmt="PNG", color=(40, 90, 140)):
    if mode == "RGBA" and len(color) == 3:
        color = (*color, 255)
    if mode == "RGB" and len(color) == 4:
        color = color[:3]
    im = Image.new(mode, size, color)
    out = io.BytesIO()
    im.save(out, format=fmt)
    return out.getvalue()


def test_normalize_alpha_png_to_telegram_jpeg():
    out = app.normalize_image_for_telegram(image_bytes(mode="RGBA", fmt="PNG"))

    assert out.bytes.startswith(b"\xff\xd8")
    assert out.width == 640
    assert out.height == 640
    assert out.photo_compatible is True


def test_normalize_resizes_large_dimension_sum(monkeypatch):
    monkeypatch.setattr(app, "TELEGRAM_PHOTO_MAX_DIM_SUM", 1000)

    out = app.normalize_image_for_telegram(image_bytes(size=(1600, 1200), fmt="JPEG", color=(10, 20, 30)))

    assert out.width + out.height <= 1000
    assert out.resized is True


def test_normalize_marks_extreme_ratio_incompatible():
    out = app.normalize_image_for_telegram(image_bytes(size=(2000, 50), fmt="JPEG", color=(10, 20, 30)))

    assert out.photo_compatible is False
    assert out.reason == "aspect_ratio"


def test_replicate_output_parser_supports_url_and_read():
    class FileWithUrl:
        url = "https://example.com/out.jpg"

    class FileWithRead:
        def read(self):
            return b"image-bytes"

    assert app._extract_replicate_output({"output": [FileWithUrl()]}).url == "https://example.com/out.jpg"
    assert app._extract_replicate_output({"output": [FileWithRead()]}).data == b"image-bytes"


def test_deliver_result_falls_back_to_document(monkeypatch):
    calls = {"photo": 0, "document": 0}

    class FakeBot:
        async def send_photo(self, **kwargs):
            calls["photo"] += 1
            raise RuntimeError("photo rejected")

        async def send_document(self, **kwargs):
            calls["document"] += 1
            return object()

    monkeypatch.setattr(app, "bot", FakeBot())
    monkeypatch.setattr(app, "s3_put_and_presign", lambda *args, **kwargs: "https://s3.example/result.jpg")
    monkeypatch.setattr(app, "stats_incr", lambda *args, **kwargs: None)

    result = asyncio.run(app.deliver_result(123, image_bytes(fmt="JPEG", color=(10, 20, 30)), job_id="job1"))

    assert result.ok is True
    assert result.method == "document"
    assert calls == {"photo": 1, "document": 1}


def test_api_generation_payload_can_decode_data_url():
    raw = image_bytes(fmt="JPEG", color=(10, 20, 30))
    data_url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    decoded = base64.b64decode(data_url.split(",", 1)[1])

    assert decoded == raw


def test_enqueue_generation_job_is_nonblocking(monkeypatch):
    created = []

    def fake_create_task(coro):
        created.append(coro)
        coro.close()
        return object()

    monkeypatch.setattr(app.asyncio, "create_task", fake_create_task)
    job_id = asyncio.run(
        app.enqueue_telegram_generation_job(
            chat_id=123,
            username="tester",
            image_bytes=image_bytes(fmt="JPEG", color=(10, 20, 30)),
            prompt="studio portrait",
            lang="en",
            seed=1,
            caption="✅",
            success_stat="gens_ok",
            fail_stat="gens_fail",
            wait_message=None,
        )
    )

    assert app.JOBS[job_id]["status"] == "queued"
    assert len(created) == 1


def test_telegram_webhook_uses_secret_header(monkeypatch):
    calls = []

    async def fake_feed_update(bot, update):
        calls.append(update.update_id)

    monkeypatch.setattr(app.dp, "feed_update", fake_feed_update)
    client = TestClient(app.app)

    forbidden = client.post("/", json={"update_id": 1})
    accepted = client.post(
        "/",
        headers={"X-Telegram-Bot-Api-Secret-Token": app.WEBHOOK_SECRET},
        json={"update_id": 2},
    )

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True}
    assert calls == [2]
