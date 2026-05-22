# 01 — Million-Dollar Product Spec

**Status:** Phase 0 constitution (target state + MVP gaps)  
**Source of truth for today:** [00 Current State Audit](./00_CURRENT_STATE_AUDIT.md)  
**Execution order:** [05 Implementation Phases](./05_IMPLEMENTATION_PHASES.md)  
**Rollback:** [07 Rollback Plan](./07_ROLLBACK_PLAN.md)

---

## 1. Product positioning

**Name:** iModel Studio  
**One line:** *Your AI photo studio inside Telegram. Create premium photos of yourself without a photographer, studio, or expensive photoshoot.*

**Doctrine:**

- **Prompts are the product** — users buy curated commercial *photoshoots*, not blank text boxes.
- **Trends are the growth engine** — weekly drops, Trend Lab, seasonal packs.
- **Mini App is the premium showroom** — full-screen cinematic UX.
- **Telegram Bot is the transaction layer** — onboarding, payments, delivery, notifications, support, referrals.
- **Copy Mode is premium magic** — same scene, user's face; preserve [`USER_COPY_MODE`](../app.py) behavior until Phase 7 integration is proven.

**Not:** A generic AI image generator, emoji-heavy toy bot, or API-first tool.

**User-facing language — avoid:** preset, generation, job, API, model, prompt.  
**Prefer:** photoshoot, premium photo, look, style pack, AI studio, *Create my photos*, *final polish*, *studio is building your look*.

---

## 2. Who pays and why

| Segment | Job to be done | Willingness to pay |
|---------|----------------|-------------------|
| Professionals | LinkedIn/CV, founder, realtor, beauty master | High — status + trust |
| Dating / social | Tinder, Instagram, Telegram avatar | High — confidence + matches |
| Status / luxury | “Old money”, hotel, jet mood editorial | Medium–high — dopamine + share |
| Trend chasers | Viral safe looks (90s flash, glow up) | Medium — impulse + share |
| Copy users | Recreate a reference with their face | High — perceived magic |

**Emotional sale:** identity transformation, confidence, premium social presence—not “AI tech.”

---

## 3. Main product modules

| # | Module | Today (`main`) | Owner agent (Phase 1+) |
|---|--------|----------------|-------------------------|
| 1 | Telegram Bot | `app.py` aiogram handlers | Backend + Product |
| 2 | Telegram Mini App | Embedded `/webapp` HTML | Mini App Engineer |
| 3 | Prompt & Trend Engine | `PRESETS` only | Prompt & Trend Director |
| 4 | AI Photo Engine | `generate_image_from_bytes` | AI Pipeline Engineer |
| 5 | Payments / Credits / Stars | `got_payment`, `USER_CREDITS` | Payments Engineer |
| 6 | Persistent Gallery | `USER_HISTORY` (5, RAM) | Backend Engineer |
| 7 | Admin & Analytics | `/admin`, `/metrics` | Admin & Analytics |
| 8 | Growth Loops | Partial (referral, nudges env-off) | Product Director |
| 9 | Safety & Privacy | Filters in `app.py`; gaps below | Product + Backend |
| 10 | Trend Operations | None | Prompt & Trend Director |

---

## 4. Telegram Bot role (target)

Bot is **not** the primary UI. Responsibilities:

- Onboarding gate  
- Fast upload fallback  
- Payment channel (Stars)  
- Result delivery (photo messages)  
- Notifications / nudges  
- Support entry  
- Referral deep links (`ref_*`)  
- Admin commands (`/stats`, `/grant`, `/credits`)

### Target `/start` copy

```
Welcome to iModel Studio ✨

Your AI photo studio inside Telegram.
Create premium photos of yourself without a photographer, studio, or expensive photoshoot.

Choose a trending photoshoot, upload your selfie, and get premium portraits in seconds.
```

### Target main buttons

| Button | Action |
|--------|--------|
| Create Photoshoot | Deep link to Mini App Create or preset picker |
| Open Studio | `WebAppInfo` → `/webapp` |
| Trending Looks | Mini App Trend Lab |
| Buy Credits | `/buy` + premium packages (Phase 6) |
| My Gallery | `/gallery` → persistent gallery (Phase 8) |
| Invite & Earn | `/refer` |
| Help | `/help` |

**Today:** Legacy menu in `main_menu_inline` (Buy, Balance, Presets, Copy, etc.). Bot copy overhaul **after** Phase 5 Mini App parity ([05](./05_IMPLEMENTATION_PHASES.md)).

### After result (target)

Upsell buttons: Try Trending Look, Business version, Cinematic, Luxury, HD Upgrade, Open Gallery, Buy More Credits.

### Zero credits (target — never “No credits.”)

```
You need credits to create this photoshoot.
Choose a package and continue instantly.
```

Buttons: Starter 249★, Creator 599★, Pro 999★, Invite & Earn.

**Today:** `credits_none` string in `T` i18n — change Phase 6+ with bot text module.

---

## 5. Mini App role

Premium **showroom**: trends, packs, create flow, gallery, pricing, profile. Full spec: [02 Premium Mini App Spec](./02_PREMIUM_MINI_APP_SPEC.md).

**Rule:** Do not replace `webapp_index()` until Phase 5; use `WEBAPP_V2_STATIC` fallback.

---

## 6. Prompt & Trend Engine role

Commercial catalog of photoshoots with versioning, scoring, weekly ops. Spec: [03 Prompt & Trend Engine](./03_PROMPT_AND_TREND_ENGINE_SPEC.md), ops: [Trend Operations Playbook](./TREND_OPERATIONS_PLAYBOOK.md).

**Integration:** `build_prompt(style_key)` behind `USE_PROMPT_BUILDER` in Phase 7 only—keep `PRESETS` + free text until then.

---

## 7. AI Photo Engine role

Wrap [`generate_image_from_bytes`](../app.py) in `imodel/ai/generation_service.py` (Phase 5–7):

- style_key, prompt version, credit price, multi-output count  
- S3 result storage, gallery row, credit transaction, refund on failure  
- User-facing statuses: *Preparing your studio*, *Locking your face identity*, etc.

**Must preserve:** `IDENTITY_LOCK`, `SCENE_LOCK`, Nano Banana `image_input`, Copy strict path.

---

## 8. Payments / Credits role

| Package | Stars | Premium photos | Notes |
|---------|-------|----------------|-------|
| **Starter** | 249 | 6 | First test |
| **Creator** | 599 | 18 | Most popular |
| **Pro** | 999 | 35 | +5 HD upgrades, priority queue |
| **iModel Max** | 1999 | 80 | +15 HD, all premium looks, priority |

**Legacy (must remain):**

| Payload | Stars | Credits today |
|---------|-------|---------------|
| `pack_10` | 200 | 10 |
| `pack_30` | 500 | 30 |
| `pack_100` | 1200 | 100 |

**New payloads (Phase 6):** `starter_249`, `creator_599`, `pro_999`, `max_1999`.

**Rules (Phase 6+):**

- Row in `imodel_payments` per charge  
- Row in `imodel_credit_transactions` per credit change  
- Idempotent `telegram_charge_id`  
- Copy Mode: 4 credits/result or 12 for 4-photo set (Phase 7 pricing)  
- HD upscale: extra credits (Phase 8+)

**Today:** `send_stars_invoice`, `got_payment` only—see [00](./00_CURRENT_STATE_AUDIT.md) §8.

---

## 9. Persistent Gallery role

- Last **50** results per user  
- DB: `imodel_generation_results` + S3 keys  
- Actions: download, regenerate, try another look, upscale HD, share, delete  

**Today:** `USER_HISTORY` max 5 bytes in memory; API gallery from `imodel_jobs` with `status=ready`. Phase 8.

---

## 10. Admin / Analytics role

**Business dashboard (Phase 10):** revenue, stars, paying users, conversion, top packages, AI cost estimate, gross profit.

**Prompt dashboard:** top styles, converting styles, failures, regenerations, A/B versions.

**Today:** `/admin` HTML + `/metrics` JSON—extend, do not remove secret gates.

---

## 11. Growth loops

| Loop | Mechanism | Phase |
|------|-----------|-------|
| Share result | Telegram share + “Made with iModel Studio” | 11 |
| Referral upgrade | Friend +3 on start; referrer +3 on first gen/purchase | 11 (today: immediate on `/start`) |
| Trend drops | Weekly push / broadcast | 9–11 |
| Comeback nudges | 24h / 3d style-specific (`NUDGE_ENABLED` exists) | 11 |
| Seasonal drops | Christmas, Valentine, etc. | 9 + ops playbook |
| Profile upsells | LinkedIn / dating version after result | 11 |
| HD / variations | Post-result buttons | 8–11 |

---

## 12. Safety & privacy requirements

| Requirement | Today | Phase |
|-------------|-------|-------|
| NSFW block | `ALLOW_NSFW`, `blocked()` | Keep |
| Celebrity block | `ALLOW_CELEBS` | Keep + catalog scan Phase 3 |
| No training on user images | Policy copy | Document + enforce Phase 11 |
| Delete uploads / gallery | Partial `/clear` | `/forget` implement Phase 11 |
| Retention policy | Mentioned 72h in tos strings | Backend TTL Phase 11 |
| Safe trend names | N/A | [Trend Operations Playbook](./TREND_OPERATIONS_PLAYBOOK.md) |

**Known gaps:**

- `/forget` referenced in help/privacy strings but **no** `Command("forget")` in `app.py`  
- Delete gallery needs `imodel_generation_results`  
- Consent for training must stay opt-in explicit  

---

## 13. Monetization summary

- Primary: Telegram Stars packages  
- Secondary: referral credits, promo codes (`PROMO_CODES`)  
- Future: style packs (599★ / 999★ bundles), Copy pack  

**Metric focus:** payment conversion per style, regeneration rate, repeat purchase, referral-attributed LTV.

---

## 14. Success metrics (placeholders)

| Metric | Definition |
|--------|------------|
| Pay conversion | % users who buy Stars within 7d |
| Style conversion | % views → paid generation per `style_key` |
| Regeneration rate | Regens / successful gens |
| Identity complaint rate | Support + manual tags |
| ARPPU | Stars / paying user / month |
| D7 retention | Users with 2+ sessions |

Populate from `imodel_style_events` + payments ledger after Phase 2/6.

---

## 15. MVP gaps vs final vision

| Area | MVP (`app.py`) | Final iModel Studio |
|------|----------------|---------------------|
| UX surface | Bot-first + demo Mini App | Mini App showroom |
| Prompts | 24 `PRESETS` | 30+ commercial photoshoots + packs |
| Payments | 3 legacy packs, no ledger | 4 premium + legacy + idempotency |
| Gallery | 5 images RAM | 50 persistent |
| Copy | 1 credit, working strict path | Premium pricing + pack positioning |
| Trends | Static presets | Weekly Trend Lab + ops playbook |
| Language | “generations”, “presets” | “premium photos”, “photoshoots” |
| Code structure | Monolith | `imodel/*` + `webapp/*` thin `app.py` |

---

## Cross-links

- **What exists:** [00](./00_CURRENT_STATE_AUDIT.md)  
- **Mini App UX:** [02](./02_PREMIUM_MINI_APP_SPEC.md)  
- **Prompts:** [03](./03_PROMPT_AND_TREND_ENGINE_SPEC.md)  
- **Architecture:** [04](./04_ARCHITECTURE_REFACTOR_PLAN.md)  
- **Phases:** [05](./05_IMPLEMENTATION_PHASES.md)  
- **QA:** [06](./06_QA_AND_LAUNCH_CHECKLIST.md)  
- **Rollback:** [07](./07_ROLLBACK_PLAN.md)
