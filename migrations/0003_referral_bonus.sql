-- +goose Up
ALTER TABLE users ADD COLUMN IF NOT EXISTS start_bonus_claimed BOOLEAN DEFAULT FALSE;
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS bonus_paid BOOLEAN DEFAULT FALSE;

-- +goose Down
ALTER TABLE referrals DROP COLUMN IF EXISTS bonus_paid;
ALTER TABLE users DROP COLUMN IF EXISTS start_bonus_claimed;
