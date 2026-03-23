# iModel v3 (Go) — Scaffold

Components:
- cmd/web: Fiber HTTP server with `/tg/webhook`, `/healthz`, `/metrics`, `/admin/queues`.
- cmd/worker: Asynq worker processing `Generate` and `Upscale` tasks.
- internal/services: Replicate, S3, images, queue, openai (stub), payments (stub).
- internal/repo: Postgres store (pgx), minimal methods.
- migrations: Goose SQL for initial schema.

Env (minimal): `BOT_TOKEN`, `WEBHOOK_SECRET`, `PUBLIC_URL`, `REPLICATE_API_TOKEN`, `REDIS_ADDR`, `DATABASE_URL`. See `.env.example`.

Run locally (requires Go, Redis, Postgres):
- `go run ./cmd/web` (port 8080)
- `go run ./cmd/worker`

Webhook:
- Set webhook to `https://<PUBLIC_URL>/tg/webhook`:
  - `make set-webhook` (expects BOT_TOKEN, PUBLIC_URL, WEBHOOK_SECRET in env)
  - or run `go run scripts/set_webhook.go -token $BOT_TOKEN -url $PUBLIC_URL/tg/webhook -secret $WEBHOOK_SECRET`

Notes:
- PREVIEW_FIRST=1 sends quick preview, then final after ESRGAN.
- Replicate client polls and expects output URL; ESRGAN result stored to S3 if configured.
- Admin HTTP: `/admin/ui`, `/admin/grant`, `/admin/whitelist`, `/admin/user` (header `X-Admin-Secret`).
- Metrics: `/metrics` (Prometheus format), Health: `/healthz`.
