# 06 — QA and Launch Checklist

**Status:** Executable regression + launch contract  
**Baseline audit:** [00 Current State Audit](./00_CURRENT_STATE_AUDIT.md)  
**Phases:** [05 Implementation Phases](./05_IMPLEMENTATION_PHASES.md)  
**Rollback:** [07 Rollback Plan](./07_ROLLBACK_PLAN.md)

Run checks after **every** phase that touches production code. Phase 0: docs review only.

---

## Automated baseline (run every code phase)

```bash
python3 -m py_compile app.py
python3 -m pytest -q
```

**Test file:** [`tests/test_security.py`](../tests/test_security.py)

| Test | Protects |
|------|----------|
| `test_telegram_webhook_requires_secret_header` | `POST /` + `WEBHOOK_SECRET` |
| `test_metrics_requires_secret` | `/metrics` |
| `test_admin_requires_secret` | `/admin` |
| `test_webapp_session_validates_init_data` | `/api/v1/webapp/session` |
| `test_webapp_me_requires_session_token` | Bearer auth |
| `test_shutdown_does_not_delete_webhook` | Deploy webhook persistence |

If pytest fails due to missing env in CI, document failure in phase report—**do not** change production code in Phase 0 to fix unrelated failures.

---

## Bot regression

| Check | Phase required | Notes |
|-------|----------------|-------|
| [ ] `/start` works | All | Onboarding + `main_menu_inline` |
| [ ] Open Studio button works | All | `WebAppInfo` → `/webapp` |
| [ ] `/buy` works | All | `cmd_buy` |
| [ ] Existing `pack_10` works | All | 200★ → 10 credits |
| [ ] Existing `pack_30` works | All | 500★ → 30 credits |
| [ ] Existing `pack_100` works | All | 1200★ → 100 credits |
| [ ] New packages work | 6+ | `starter_249`, `creator_599`, `pro_999`, `max_1999` |
| [ ] User can upload photo | All | `on_photo` |
| [ ] User can choose preset/style | All / 7 | `cb_preset_pick` / style_key |
| [ ] User receives result | All | `safe_answer_photo` |
| [ ] Credits deducted correctly | All | Only on success |
| [ ] Failed generation does not wrongly charge | All | No deduct on `gens_fail` |
| [ ] Copy Mode works | All | `USER_COPY_MODE` strict path |
| [ ] Gallery works | All / 8 | `/gallery`, `USER_HISTORY` |
| [ ] `/admin` works | All | `ADMIN_PANEL_SECRET` |
| [ ] `/metrics` works | All | `METRICS_SECRET` |
| [ ] `/healthz` works | All | `{"status":"ok"}` |

---

## Webhook

| Check | Notes |
|-------|-------|
| [ ] `POST /` returns fast 200 | `{"ok":true}` before slow work |
| [ ] `WEBHOOK_SECRET` header required | 403 without header |
| [ ] `WEBHOOK_ALLOW_QUERY_SECRET` remains `0` in production | Query secret disabled |
| [ ] Background processing works | Updates reach bot handlers |
| [ ] `ensure_webhook` on startup | After Railway deploy |

---

## Mini App

| Check | Phase | Notes |
|-------|-------|-------|
| [ ] Opens inside Telegram | 5+ | Real device |
| [ ] `initData` auth works | All | `validate_webapp_init_data` |
| [ ] Bearer token works | All | `make_webapp_token` |
| [ ] `/api/v1/me` returns credits | All | |
| [ ] `/api/v1/gallery` works | All / 8 | |
| [ ] `/api/v1/generations` starts job | All | |
| [ ] Polling works | All | until `ready` / `failed` |
| [ ] Shows styles | 3+ | `/api/v1/styles` |
| [ ] Shows trending | 3+ | |
| [ ] Shows pricing | 6+ | `/api/v1/packages` |
| [ ] Safe area works | 5+ | CSS insets |
| [ ] `BackButton` works | 5+ | |
| [ ] Haptics do not crash | 5+ | Optional SDK calls |
| [ ] `WEBAPP_V2_STATIC=0` fallback | 5 | Embedded HTML still loads |

---

## Prompt safety (catalog + generation)

| Check | Phase |
|-------|-------|
| [ ] No celebrity names in catalog | 1+ |
| [ ] No brand names in catalog | 1+ |
| [ ] No NSFW styles in active catalog | 1+ |
| [ ] No minors sexualization | 1+ |
| [ ] No weapon/violence glamorization | 1+ |
| [ ] Identity lock included in `build_prompt` output | 1+ |
| [ ] Negative prompt included | 1+ |
| [ ] `style_key` stored on job | 7+ |
| [ ] `prompt_version` stored on job | 7+ |

---

## Payments (Phase 6+)

| Check | Notes |
|-------|-------|
| [ ] `successful_payment` adds credits | `got_payment` |
| [ ] Duplicate payment protection | `telegram_charge_id` unique |
| [ ] Payment row created | `imodel_payments` |
| [ ] Credit transaction row created | `imodel_credit_transactions` |
| [ ] Refund transaction on failed gen (if pre-hold) | Policy decision |

---

## Deploy

| Check | Command / action |
|-------|------------------|
| [ ] `python3 -m py_compile app.py` | |
| [ ] `python3 -m pytest -q` | |
| [ ] Docker build works | `docker build -f Dockerfile .` |
| [ ] Railway deploy works | Manual or CI |
| [ ] `/healthz` returns ok | curl public URL |
| [ ] Webhook persists on startup | Telegram `getWebhookInfo` |
| [ ] No secrets in logs | Review Railway logs |
| [ ] No secrets in docs | This repo |

---

## Phase-specific gates

| Phase | Minimum gate before merge |
|-------|---------------------------|
| 1 | Unit tests new modules; `app.py` diff empty or imports only dead code |
| 2 | Postgres tables exist; app starts with `DATABASE_URL` |
| 3 | New API auth + 404/403 behavior |
| 5 | Mini App E2E in Telegram |
| 6 | Pay test in Telegram Stars test mode |
| 7 | Copy Mode + 3 preset gens manual |
| 8 | Gallery survives process restart |
| 12 | Full checklist above |

---

## Launch sign-off

| Role | Sign-off |
|------|----------|
| Product | Positioning + packs + Trend Lab content |
| Engineering | All critical bot/webhook/payment/generation checks |
| Ops | Railway env complete per `.env.example` |
| Owner | Trend playbook first weekly report scheduled |

---

## Cross-links

- Rollback if gate fails: [07](./07_ROLLBACK_PLAN.md)  
- What not to break: [00](./00_CURRENT_STATE_AUDIT.md) §18
