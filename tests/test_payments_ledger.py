import os
os.environ["PAYMENT_LEDGER_V2"] = "1"

from imodel import bootstrap
from imodel.db import ledger as ledger_db


def test_process_payment_idempotent(monkeypatch):
    seen = []

    def fetchall(sql, params=()):
        if "telegram_charge_id" in sql:
            return [(1,)] if seen else []
        return []

    def execute(sql, params=()):
        if "INSERT INTO imodel_payments" in sql:
            seen.append(1)
        return True

    add1 = bootstrap.process_payment(
        uid=1,
        payload="pack_10",
        stars_amount=200,
        telegram_charge_id="chg_test_1",
        legacy_add_map={"pack_10": 10},
        db_ready=True,
        db_execute=execute,
        db_fetchall=fetchall,
    )
    add2 = bootstrap.process_payment(
        uid=1,
        payload="pack_10",
        stars_amount=200,
        telegram_charge_id="chg_test_1",
        legacy_add_map={"pack_10": 10},
        db_ready=True,
        db_execute=execute,
        db_fetchall=fetchall,
    )
    assert add1 == 10
    assert add2 == 0
