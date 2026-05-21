import os

os.environ.setdefault("BOT_TOKEN", "123456:ABCDEF")


def test_migration_sql_is_additive_only():
    from imodel.db.migrations import MIGRATION_SQL
    combined = " ".join(MIGRATION_SQL).upper()
    assert "DROP TABLE" not in combined
    assert "CREATE TABLE IF NOT EXISTS" in combined


def test_seed_file_loads():
    from imodel.prompts.prompt_builder import _load_seed, reload_styles
    reload_styles()
    styles = _load_seed()
    assert len(styles) >= 30
