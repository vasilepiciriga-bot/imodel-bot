import os
import time
import hashlib
import hmac
import json
from urllib.parse import urlencode

os.environ["BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
os.environ["REPLICATE_API_TOKEN"] = "dummy"
os.environ["WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["STYLE_CATALOG_V2"] = "1"
os.environ["METRICS_SECRET"] = "test-metrics-secret"
os.environ["ADMIN_PANEL_SECRET"] = "test-admin-secret"

from fastapi.testclient import TestClient

import app


def _webapp_init_data(uid=99):
    pairs = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": uid, "username": "tester"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", app.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def _auth_headers(client):
    session = client.post("/api/v1/webapp/session", json={"initData": _webapp_init_data()})
    token = session.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_styles_endpoint_when_enabled():
    client = TestClient(app.app)
    r = client.get("/api/v1/styles", headers=_auth_headers(client))
    assert r.status_code == 200
    data = r.json()
    assert data.get("enabled") is True
    assert len(data.get("items", [])) >= 1


def test_packages_endpoint():
    client = TestClient(app.app)
    r = client.get("/api/v1/packages", headers=_auth_headers(client))
    assert r.status_code == 200
    payloads = {p["payload"] for p in r.json().get("packages", [])}
    assert "pack_10" in payloads
