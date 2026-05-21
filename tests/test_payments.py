import os

os.environ["BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"

from imodel.config.packages import credits_for_payload, list_packages


def test_legacy_pack_credits():
    assert credits_for_payload("pack_10") == 10
    assert credits_for_payload("pack_30") == 30
    assert credits_for_payload("pack_100") == 100


def test_premium_pack_credits():
    assert credits_for_payload("pack_starter") == 6
    assert credits_for_payload("pack_max") == 80


def test_list_packages_includes_legacy():
    payloads = {p["payload"] for p in list_packages(include_premium=True)}
    assert "pack_10" in payloads
    assert "pack_starter" in payloads
