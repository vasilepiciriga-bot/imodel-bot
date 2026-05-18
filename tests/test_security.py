import asyncio
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

os.environ.setdefault("BOT_TOKEN", "123456:ABCDEF")
os.environ.setdefault("REPLICATE_API_TOKEN", "dummy")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("METRICS_SECRET", "test-metrics-secret")
os.environ.setdefault("ADMIN_PANEL_SECRET", "test-admin-secret")

from fastapi.testclient import TestClient

import app


def _webapp_init_data(uid=42, username="tester"):
    pairs = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": uid, "username": username}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", app.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(pairs)


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


def test_webapp_session_validates_init_data():
    client = TestClient(app.app)

    forbidden = client.post("/api/v1/webapp/session", json={"initData": "bad"})
    accepted = client.post("/api/v1/webapp/session", json={"initData": _webapp_init_data()})

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["credits"] >= 0
    assert "token" in accepted.json()


def test_webapp_me_requires_session_token():
    client = TestClient(app.app)
    session = client.post("/api/v1/webapp/session", json={"initData": _webapp_init_data(uid=43)})
    token = session.json()["token"]

    forbidden = client.get("/api/v1/me")
    accepted = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert forbidden.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["chat_id"] == 43


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
