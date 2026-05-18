import asyncio
import os

os.environ.setdefault("BOT_TOKEN", "123456:ABCDEF")
os.environ.setdefault("REPLICATE_API_TOKEN", "dummy")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("METRICS_SECRET", "test-metrics-secret")
os.environ.setdefault("ADMIN_PANEL_SECRET", "test-admin-secret")

from fastapi.testclient import TestClient

import app


def test_telegram_webhook_requires_secret_header(monkeypatch):
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


def test_metrics_requires_secret():
    client = TestClient(app.app)

    forbidden = client.get("/metrics")
    accepted = client.get(f"/metrics?secret={app.METRICS_SECRET}")

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert "updates" in accepted.json()


def test_admin_requires_secret():
    client = TestClient(app.app)

    forbidden = client.get("/admin")
    accepted = client.get(f"/admin?secret={app.ADMIN_PANEL_SECRET}")

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert "iModel" in accepted.text


def test_shutdown_does_not_delete_webhook(monkeypatch):
    calls = {"close": 0, "delete_webhook": 0, "get_webhook_info": 0}

    class FakeSession:
        async def close(self):
            calls["close"] += 1

    class FakeBot:
        session = FakeSession()

        async def delete_webhook(self):
            calls["delete_webhook"] += 1

        async def get_webhook_info(self):
            calls["get_webhook_info"] += 1
            return object()

    monkeypatch.setattr(app, "bot", FakeBot())

    asyncio.run(app.on_shutdown())

    assert calls == {"close": 1, "delete_webhook": 0, "get_webhook_info": 0}
