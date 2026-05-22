from imodel.config.packages import credits_for_payload, get_package


def test_legacy_packages_intact():
    assert get_package("pack_10")["stars"] == 200
    assert get_package("pack_30")["credits"] == 30
    assert get_package("pack_100")["credits"] == 100


def test_premium_packages_defined():
    assert get_package("starter_249")["stars"] == 249
    assert get_package("creator_599")["credits"] == 18
    assert get_package("pro_999")["hd_upgrades"] == 5
    assert get_package("max_1999")["credits"] == 80


def test_credits_for_payload():
    assert credits_for_payload("pack_10") == 10
    assert credits_for_payload("creator_599") == 18
    assert credits_for_payload("unknown") == 0
