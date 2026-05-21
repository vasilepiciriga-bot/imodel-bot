# 07 — Rollback Plan

**Status:** Per-phase rollback contract  
**Current state:** [00 Current State Audit](./00_CURRENT_STATE_AUDIT.md)  
**Phases:** [05 Implementation Phases](./05_IMPLEMENTATION_PHASES.md)  
**QA gates:** [06 QA and Launch Checklist](./06_QA_AND_LAUNCH_CHECKLIST.md)

Use this document when a phase fails [06](./06_QA_AND_LAUNCH_CHECKLIST.md) or production incidents occur.

---

## Phase rollback table

| Phase | Rollback lever | Production impact |
|-------|----------------|-------------------|
| **0** | Delete docs branch / revert doc commit | None |
| **1** | Remove `imodel/` imports from `app.py`; delete package if needed | None if not wired |
| **2** | Stop writing new tables; reads optional; old code ignores empty tables | None if flags off |
| **3** | Disable new routers; keep existing `/api/v1/webapp/*` routes | Old Mini App works |
| **4** | Do not deploy `webapp/dist` | None |
| **5** | `WEBAPP_V2_STATIC=0` → embedded HTML in `webapp_index()` | Instant UI revert |
| **6** | `NEW_STAR_PACKAGES=0`; `PAYMENT_LEDGER_V2=0`; legacy `pack_*` only | New invoices hidden |
| **7** | `USE_PROMPT_BUILDER=0` → `PRESETS` + free-text path | Quality revert to known |
| **8** | `PERSISTENT_GALLERY=0` → `USER_HISTORY` + job gallery API | In-memory gallery |
| **9** | Hide Trend Lab route / nav entry | Home still works |
| **10** | Serve legacy `/admin` only | Old dashboard |
| **11** | `NUDGE_ENABLED=0`; disable broadcast flags | No growth messages |
| **12** | Redeploy previous Railway image | Full revert |

---

## Git rollback

| Action | When |
|--------|------|
| Revert last commit on feature branch | Single bad commit |
| Close PR without merge | Phase abandoned |
| Redeploy previous Railway deployment | Production incident post-merge |
| Keep docs on `cursor/phase-0-docs-b320` separate | Docs-only PR |

**Do not** force-push `main` unless explicitly approved by repo owner.

**Verify after revert:**

```bash
python3 -m py_compile app.py
python3 -m pytest -q
curl -s "$WEBHOOK_BASE/healthz"
```

---

## Data rollback

| Rule | Detail |
|------|--------|
| Early migrations additive only | No `DROP TABLE` in Phases 1–8 |
| New tables optional | Old code ignores `imodel_payments` etc. if not written |
| No destructive `ALTER` | No column drops that break old rows |
| Ledger | If Phase 6 rolled back, credits in `USER_CREDITS` / `imodel_credits` remain source of truth |
| Gallery | Phase 8 rollback: bot uses `USER_HISTORY`; API uses jobs without `generation_results` |

**Do not** delete user credits rows during rollback unless legal/privacy request.

---

## Webhook rollback

| Item | Action |
|------|--------|
| Logic change incident | Revert `telegram_webhook` / `_telegram_webhook_authorized` commit |
| Secret mismatch | Fix `WEBHOOK_SECRET` in Railway = BotFather secret token |
| Query secret | Keep `WEBHOOK_ALLOW_QUERY_SECRET=0` in production |
| Webhook URL | `WEBHOOK_BASE` must match Railway public domain |
| Startup | Confirm `on_startup` → `ensure_webhook` runs (do not delete webhook on shutdown—test expects this) |

**Symptom:** 403 on all updates → check header and env.

---

## Mini App rollback

| Step | Action |
|------|--------|
| 1 | Set `WEBAPP_V2_STATIC=0` in Railway |
| 2 | Redeploy (or restart) |
| 3 | Confirm `/webapp` serves embedded HTML from `app.py` |
| 4 | Confirm `POST /api/v1/webapp/session` still works |

**API routes are not rolled back** in Phase 5—only static UI source changes.

---

## Payment rollback

| Step | Action |
|------|--------|
| 1 | `NEW_STAR_PACKAGES=0` — stop sending new invoice payloads |
| 2 | `PAYMENT_LEDGER_V2=0` — optional stop writing ledger (legacy credits still work) |
| 3 | Verify `pack_10`, `pack_30`, `pack_100` in `cb_buy_stars` / `got_payment` unchanged |
| 4 | If double-credit bug: manual adjust via `/credits` admin + audit log |

**Never remove** legacy payload handlers without migration plan.

---

## Generation / Copy Mode rollback

| Step | Action |
|------|--------|
| 1 | `USE_PROMPT_BUILDER=0` |
| 2 | `COPY_MODE_V2=0` (future pricing) |
| 3 | Revert `generation_service` wrapper commit if needed |
| 4 | Manual test Copy Mode: style photo → selfie → result |

**Preserve:** `generate_image_from_bytes`, `IDENTITY_LOCK`, `SCENE_LOCK`, strict `image_input` variants.

---

## Deploy rollback (Railway)

1. Open Railway → Deployments → select last green deployment → **Redeploy**  
2. Confirm env vars unchanged (`BOT_TOKEN`, `WEBHOOK_BASE`, `WEBHOOK_SECRET`, `DATABASE_URL`, S3)  
3. Hit `/healthz`  
4. Send test message to bot  
5. Optional: `curl -X POST "$WEBHOOK_BASE/" -H "X-Telegram-Bot-Api-Secret-Token: $WEBHOOK_SECRET" -d '{"update_id":1}'`  

**Docker:** Previous image tag if using tagged releases.

---

## Incident severity guide

| Severity | Example | Response |
|----------|---------|----------|
| S1 | Webhook down, no messages | Revert deploy; fix `WEBHOOK_SECRET` |
| S1 | Double Stars credits | Disable `NEW_STAR_PACKAGES`; fix idempotency forward fix |
| S2 | Generation 100% fail | Revert Phase 7; check Replicate token |
| S2 | Mini App blank | `WEBAPP_V2_STATIC=0` |
| S3 | Admin panel wrong stats | Revert Phase 10 only |
| S4 | Trend Lab typo | Content fix, no rollback |

---

## Cross-links

- Preservation list: [00](./00_CURRENT_STATE_AUDIT.md) §18  
- Phase order: [05](./05_IMPLEMENTATION_PHASES.md)  
- Tests before declare safe: [06](./06_QA_AND_LAUNCH_CHECKLIST.md)
