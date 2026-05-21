# iModel Studio — Launch Checklist

## Pre-deploy

- [ ] `BOT_TOKEN`, `WEBHOOK_BASE`, `WEBHOOK_SECRET` set on Railway
- [ ] `REPLICATE_API_TOKEN`, S3 keys, `DATABASE_URL` (Postgres)
- [ ] `METRICS_SECRET`, `ADMIN_PANEL_SECRET` set
- [ ] `cd webapp && npm install && npm run build` (or use committed `webapp/dist`)

## Feature rollout (one flag per deploy)

1. `STYLE_CATALOG_V2=1` — API catalog live
2. `USE_PROMPT_BUILDER=1` — commercial prompts in generation
3. `PAYMENT_LEDGER_V2=1` — idempotent Stars logging
4. `NEW_STAR_PACKAGES=1` — premium Star packs in /buy
5. `PERSISTENT_GALLERY=1` — gallery survives restarts
6. `WEBAPP_V2_STATIC=1` — premium React Mini App

## Smoke tests (Telegram)

- [ ] `/start` → photo + prompt → result
- [ ] `/copy` → reference → selfie → result
- [ ] `/buy` → `pack_10` payment → credits increase once (retry payment idempotency)
- [ ] `/app` → Mini App opens, session works, pick style, generate
- [ ] `/gallery` bot command still works
- [ ] `/forget` clears user gallery rows

## Regression

- [ ] `python3 -m pytest -q`
- [ ] `python3 -m py_compile app.py`
- [ ] `/metrics?secret=...` returns `db_ready`
- [ ] `/admin?secret=...` shows payment ledger block when enabled

## Rollback

- Set all new flags to `0`
- Railway → redeploy previous deployment
