# 02 — Premium Mini App Spec

**Status:** Phase 0 UX/API contract (not implemented)  
**Current implementation:** `webapp_index()` embedded HTML in [`app.py`](../app.py) (~line 3820)  
**Audit:** [00 Current State Audit](./00_CURRENT_STATE_AUDIT.md) · **Phases:** [05](./05_IMPLEMENTATION_PHASES.md) · **Rollback:** [07](./07_ROLLBACK_PLAN.md)

---

## 1. Product role of Mini App

The Mini App is the **premium showroom**—not a settings page.

| Question every screen answers |
|-------------------------------|
| What can I create? |
| Why is this valuable? |
| How much does it cost? |
| What should I tap next? |

**Bot** opens Studio via `WebAppInfo(url=f"{WEBHOOK_BASE}/webapp")` in `main_menu_inline`. Bot remains payment fallback and result delivery.

---

## 2. Target `/webapp` tree (Phase 4 — do not create in Phase 0)

```
/webapp/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  postcss.config.js
  src/
    main.tsx
    App.tsx
    routes.tsx
    styles.css
    pages/
      Home.tsx
      Create.tsx
      Photoshoots.tsx
      TrendLab.tsx
      Gallery.tsx
      Pricing.tsx
      Profile.tsx
      Referrals.tsx
      Settings.tsx
      Result.tsx
    components/
      PremiumButton.tsx
      GlassCard.tsx
      Hero.tsx
      CreditBadge.tsx
      StyleCard.tsx
      TrendBadge.tsx
      PricingCard.tsx
      ResultCard.tsx
      UploadBox.tsx
      BottomNav.tsx
      LoadingStudio.tsx
      IdentityScore.tsx
      PromptPreview.tsx
      StatusPill.tsx
      EmptyState.tsx
    lib/
      api.ts
      telegram.ts
      haptics.ts
      format.ts
      constants.ts
    data/
      mockStyles.ts      # dev only until API Phase 3
      mockPackages.ts
```

---

## 3. Frontend stack

- Vite  
- React 18+  
- TypeScript  
- Tailwind CSS  
- Telegram WebApp SDK (`@twa-dev/sdk` or official script)

**Build output:** `webapp/dist/` served by FastAPI StaticFiles in Phase 5.

---

## 4. Design tokens

| Token | Value |
|-------|-------|
| Background | `#05070D` |
| BackgroundAlt | `#080B12` |
| Surface | `#101622` |
| Surface2 | `#171F2D` |
| SurfaceGlass | `rgba(255,255,255,0.07)` |
| Text | `#F5F7FA` |
| TextMuted | `#98A2B3` |
| TextSoft | `#CDD5E0` |
| AccentMint | `#8EF6E4` |
| PremiumGold | `#E8C878` |
| HotPink | `#FF6FAE` |
| ElectricBlue | `#8EA7FF` |
| Success | `#5CF2A8` |
| Danger | `#FF5C7A` |
| Border | `rgba(255,255,255,0.10)` |

Map Telegram `themeParams` where compatible; default to dark luxury palette above.

---

## 5. Typography

| Role | Size |
|------|------|
| Hero | 34–42px |
| Section title | 20–24px |
| Card title | 16–18px |
| Body | 14–15px |
| Microcopy | 12–13px |

Font stack: system UI, `Inter`, sans-serif.

---

## 6. Telegram SDK requirements

| API | Use |
|-----|-----|
| `Telegram.WebApp.ready()` | Boot |
| `Telegram.WebApp.expand()` | Full height |
| `Telegram.WebApp.HapticFeedback` | Primary CTAs, success, errors |
| `Telegram.WebApp.BackButton` | Stack navigation |
| `themeParams` | Optional accent sync |
| Safe area insets | `env(safe-area-inset-*)` padding |
| Fullscreen | Enable when `isVersionAtLeast` supports |
| `initData` | POST to `/api/v1/webapp/session` only—never trust client-side alone |

**Auth flow (today, keep):**

1. `POST /api/v1/webapp/session` `{ initData }`  
2. Store `token` from response  
3. `Authorization: Bearer <token>` on API calls  

Implemented in `validate_webapp_init_data`, `make_webapp_token`, `webapp_user_from_request` in `app.py`.

---

## 7. Screens

### Home

Sections: Hero, Credit badge, Trending Now, Popular for Business, Dating Upgrade, Luxury Status, Copy Any Style, Latest Result, Pricing teaser.

**Hero:** “Your AI photo studio inside Telegram” / subtitle / CTAs *Create Photoshoot*, *Explore Trending Looks*.

**Data:** `GET /api/v1/styles/trending` (Phase 3)—until then mock → `PRESETS` subset.

### Photoshoots

Filters: Trending, Business, Dating, Luxury, Cinematic, Viral, Seasonal, Copy Mode. Search: “Search photoshoots…”

Card fields: name, category, commercial promise, audience, trend level, premium badge, price credits, CTA.

### Create (5 steps)

1. Choose photoshoot (`style_key`)  
2. Upload selfie  
3. Identity quality check (`assess_selfie_quality` parity via API)  
4. Output count: 4 / 8 / 12 premium photos (Phase 7+ multi-gen)  
5. Intensity: Natural / Premium / Cinematic; Identity mode: Keep / Slight polish / Strong editorial  

Optional custom description—secondary, collapsed.

### Trend Lab

Sections: Trending this week, New drops, High-converting looks, Limited seasonal, TikTok-inspired safe versions.

**Data:** `GET /api/v1/trends`, `GET /api/v1/trends/weekly` (Phase 9).

### Gallery

50 persistent items; actions: Download, Regenerate, Try another look, Upscale HD, Share, Delete.

**Today:** `GET /api/v1/gallery` — jobs only, max 20. **Phase 8:** `imodel_generation_results`.

### Pricing

“Choose your studio pack” — packages from [01](./01_MILLION_DOLLAR_PRODUCT_SPEC.md). Stars purchase via bot invoice or Mini App `openInvoice` when supported.

### Profile

Credits, HD upgrades placeholder, total photos, favorite style, referral code, privacy, delete images, support.

### Referrals

“Invite friends. Earn premium photos.” Mechanics per Phase 11.

### Settings

Language, privacy, delete uploads/gallery, support, terms, model quality info, retention.

### Result

Image grid, share, upsells, return to Trend Lab.

---

## 8. Emotional UX standard

- Calm, cinematic, expensive—not playful chaos  
- No exposed: Replicate, API, job ID, model name  
- Loading copy: studio language (see §9)  
- Empty states: guided next step, not technical errors  

**Bad:** “Job failed”, “No credits”, “prompt blocked”  
**Good:** “We couldn’t finish this photoshoot”, “Choose a studio pack to continue”, “Try a different selfie in brighter light”

---

## 9. Loading choreography (“Shock Moment”)

After selfie + style selected, full-screen `LoadingStudio`:

| Step | User-facing line |
|------|------------------|
| 1 | Reading your selfie |
| 2 | Locking your identity |
| 3 | Designing the lighting |
| 4 | Styling the scene |
| 5 | Creating your premium photos |
| 6 | Final polish |

**Poll mapping** (`GET /api/v1/generations/{job_id}`):

| Internal `status` (future) | UI line |
|----------------------------|---------|
| queued | Preparing your studio |
| analyzing_selfie | Locking your face identity |
| building_prompt / generating | Creating your photoshoot |
| polishing | Final polish |
| ready | Done |
| failed | Gentle retry + support |

**Today:** statuses include `queued`, `running`, `ready`, `failed` from `record_job` / `run_webapp_generation_job`.

---

## 10. API dependencies

| Endpoint | Phase | Used by |
|----------|-------|---------|
| `POST /api/v1/webapp/session` | **Live** | Boot auth |
| `GET /api/v1/me` | **Live** | Credits, role |
| `GET /api/v1/gallery` | **Live** | Gallery (limited) |
| `POST /api/v1/generations` | **Live** | Create (prompt + image_b64) |
| `GET /api/v1/generations/{job_id}` | **Live** | Poll |
| `GET /api/v1/styles` | 3 | Photoshoots, Home |
| `GET /api/v1/styles/trending` | 3 | Home, Trend Lab |
| `GET /api/v1/styles/{style_key}` | 3 | Create preview |
| `GET /api/v1/packs` | 3 | Packs |
| `GET /api/v1/packages` | 6 | Pricing |
| `GET /api/v1/trends` | 9 | Trend Lab |
| `POST /api/v1/generations/{id}/regenerate` | 8 | Gallery, Result |
| `POST /api/v1/generations/{id}/upscale` | 8 | HD |
| `POST /api/v1/gallery/{id}/delete` | 8 | Gallery |
| `POST /api/v1/events/style` | 3 | Analytics |

**Phase 4** may use mocks in `data/mockStyles.ts` until Phase 3 ships.

---

## 11. Migration plan from embedded HTML

| Step | Action | Phase |
|------|--------|-------|
| 1 | Build React app; dev against mocks + live session/me | 4 |
| 2 | Wire styles/generations when API ready | 3–4 |
| 3 | Add `WEBAPP_V2_STATIC=1` → serve `webapp/dist` at `/webapp` | 5 |
| 4 | Parity test: auth, create, poll, gallery, credits | 5 |
| 5 | Default `WEBAPP_V2_STATIC=1` in prod | 5+ |
| 6 | Remove or gate embedded HTML in `webapp_index()` | 5+ only after parity |

**Do not delete** embedded HTML until Phase 5 checklist passes [06](./06_QA_AND_LAUNCH_CHECKLIST.md).

---

## 12. Fallback plan

| Env | Behavior |
|-----|----------|
| `WEBAPP_V2_STATIC=0` or unset | Serve current embedded HTML from `webapp_index()` |
| `WEBAPP_V2_STATIC=1` | Serve `webapp/dist/index.html` + assets |
| Build missing | Log warning; fall back to embedded HTML |

Rollback: [07](./07_ROLLBACK_PLAN.md) Phase 5 → set `WEBAPP_V2_STATIC=0`, redeploy.

---

## Cross-links

- Product: [01](./01_MILLION_DOLLAR_PRODUCT_SPEC.md)  
- Prompts/styles data: [03](./03_PROMPT_AND_TREND_ENGINE_SPEC.md)  
- Architecture: [04](./04_ARCHITECTURE_REFACTOR_PLAN.md)  
- QA: [06](./06_QA_AND_LAUNCH_CHECKLIST.md)
