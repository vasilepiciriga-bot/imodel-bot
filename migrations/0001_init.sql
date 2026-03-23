-- +goose Up
CREATE TABLE IF NOT EXISTS users (
  tg_id BIGINT PRIMARY KEY,
  username TEXT,
  lang TEXT,
  first_seen TIMESTAMPTZ DEFAULT now(),
  last_seen TIMESTAMPTZ DEFAULT now(),
  sessions INT DEFAULT 1,
  messages INT DEFAULT 0,
  photos INT DEFAULT 0,
  gens_ok INT DEFAULT 0,
  gens_fail INT DEFAULT 0,
  premium_until TIMESTAMPTZ,
  credits INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS referrals (
  user_id BIGINT PRIMARY KEY REFERENCES users(tg_id) ON DELETE CASCADE,
  referrer_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS promo_codes (
  code TEXT PRIMARY KEY,
  add INT NOT NULL,
  uses_total INT NOT NULL,
  uses_left INT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY,
  user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
  provider TEXT,
  amount INT,
  stars INT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generations (
  id TEXT PRIMARY KEY,
  user_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
  mode TEXT,
  preset TEXT,
  prompt TEXT,
  negative TEXT,
  seed TEXT,
  style_url TEXT,
  selfie_url TEXT,
  preview_url TEXT,
  final_url TEXT,
  replicate_id TEXT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stats_daily (
  day DATE PRIMARY KEY,
  updates INT DEFAULT 0,
  messages INT DEFAULT 0,
  photos INT DEFAULT 0,
  gens_ok INT DEFAULT 0,
  gens_fail INT DEFAULT 0,
  previews INT DEFAULT 0,
  finals INT DEFAULT 0,
  payments INT DEFAULT 0,
  promo_used INT DEFAULT 0,
  referrals INT DEFAULT 0
);

-- +goose Down
DROP TABLE IF EXISTS stats_daily;
DROP TABLE IF EXISTS generations;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS promo_codes;
DROP TABLE IF EXISTS referrals;
DROP TABLE IF EXISTS users;
