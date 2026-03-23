# iModel v3 (Go) — Scaffold

Components:
- cmd/web: Fiber HTTP server with `/tg/webhook`, `/healthz`, `/metrics`, `/admin/queues`.
- cmd/worker: Asynq worker processing `Generate` and `Upscale` tasks.
- internal/services: Replicate, S3, images, queue, openai (stub), payments (stub).
- internal/repo: Postgres store (pgx), minimal methods.
- migrations: Goose SQL for initial schema.

Env (minimal): `BOT_TOKEN`, `WEBHOOK_SECRET`, `PUBLIC_URL`, `REPLICATE_API_TOKEN`, `REDIS_ADDR`, `DATABASE_URL`.

Run locally (requires Go, Redis, Postgres):
- `go run ./cmd/web` (port 8080)
- `go run ./cmd/worker`

Webhook:
- Set webhook to `https://<PUBLIC_URL>/tg/webhook` with header `X-Telegram-Bot-Api-Secret-Token: $WEBHOOK_SECRET`.

Notes:
- OpenAI Vision is stubbed; fill `internal/services/openai` with real calls when ready.
- Replicate client is generic and polls until success; expects first output URL.
- `SendPhoto` uses Telegram HTTP API directly.
