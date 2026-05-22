# iModel Studio — Deployment

## Railway (production MVP)

1. Connect repo `imodel-bot` to Railway; use root `Dockerfile`.
2. Set env from `.env.example` (never commit `.env`).
3. Process: `uvicorn app:api --host 0.0.0.0 --port 8080` (port from `PORT` if set).
4. Health: `GET /healthz` must return 200.
5. Telegram webhook: `WEBHOOK_BASE` + `WEBHOOK_SECRET`; `POST /` must stay fast (200 + background worker).

## Mini App v2 (optional)

1. Build static app: `cd webapp && npm ci && npm run build`.
2. Set `WEBAPP_V2_STATIC=1` on the service.
3. `webapp/dist/` is served at `/webapp` with SPA fallback; embedded HTML remains when flag is `0`.

## Feature flags (staged rollout)

Enable one flag at a time in staging, then production:

| Order | Flag | Risk |
|-------|------|------|
| 1 | `WEBAPP_V2_STATIC` | UI only |
| 2 | `STYLE_CATALOG_V2` | Analytics writes |
| 3 | `NEW_STAR_PACKAGES` + `PAYMENT_LEDGER_V2` | Payments |
| 4 | `USE_PROMPT_BUILDER` | Generation |
| 5 | `PERSISTENT_GALLERY` | Storage |
| 6 | `ADMIN_ANALYTICS_V2`, `TREND_LAB_V2`, `GROWTH_LOOPS_V2` | Ops / growth |

## Rollback

Set all flags to `0` and redeploy. See `docs/07_ROLLBACK_PLAN.md`.
