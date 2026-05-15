-- +goose Up
ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_tier TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_until TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS subscription_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
    tier        TEXT NOT NULL,
    stars       INT NOT NULL,
    payload     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- +goose Down
DROP TABLE IF EXISTS subscription_events;
ALTER TABLE users DROP COLUMN IF EXISTS sub_until;
ALTER TABLE users DROP COLUMN IF EXISTS sub_tier;
