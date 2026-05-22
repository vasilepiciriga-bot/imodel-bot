# Environment variables

Copy `.env.example` to `.env` locally. In Railway, set the same keys in the service variables.

## Required for production bot

- `BOT_TOKEN` — Telegram bot token
- `WEBHOOK_BASE` — Public HTTPS origin (no trailing slash)
- `WEBHOOK_SECRET` — Telegram webhook secret header
- `REPLICATE_API_TOKEN` — Image generation
- `DATABASE_URL` — Postgres (recommended)

## S3 (delivery)

- `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`

## Admin / metrics

- `ADMIN_IDS`, `ADMIN_USERNAMES`
- `METRICS_SECRET`, `ADMIN_PANEL_SECRET`

## iModel Studio flags (default `0`)

All defined in `.env.example` under “iModel Studio feature flags”. Import path: `imodel.config.settings`.

## Model

- `NANOBANANA_MODEL` — Replicate model id (default `google/nano-banana`)
