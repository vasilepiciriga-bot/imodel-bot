# 03 — Prompt & Trend Engine Spec

**Status:** Phase 0 technical product contract  
**Today:** [`PRESETS`](../app.py) list (24 items), inline prompts in `generate_image_from_bytes`  
**Phases:** Catalog Phase 1 · DB Phase 2 · API Phase 3 · Integration Phase 7  
**Ops:** [Trend Operations Playbook](./TREND_OPERATIONS_PLAYBOOK.md)  
**Audit:** [00](./00_CURRENT_STATE_AUDIT.md) · **Rollback:** [07](./07_ROLLBACK_PLAN.md)

---

## Prompt System Is The Product

The prompt system is not a helper.  
It is the **core commercial engine** of iModel.

Every photoshoot must be treated as a paid product:

- audience  
- use case  
- trend reason  
- commercial promise  
- prompt version  
- safety notes  
- quality grade  
- price  
- conversion tracking placeholder  

---

## 1. Doctrine

| Principle | Implementation |
|-----------|----------------|
| User picks a *look*, not a blank prompt | Create flow starts with `style_key` |
| Identity preserved | `base_identity.py` + existing `IDENTITY_LOCK` in `app.py` |
| Trends drive growth | `trend_catalog.py` + weekly ops |
| Weak prompts hidden | `prompt_quality.score_prompt` grade C → `is_active=false` |
| Copy Mode is premium | Strict path in `app.py`; future 4 credits/result |

---

## 2. Future module layout (Phase 1 — no generation wire yet)

```
/imodel/prompts/
  __init__.py
  base_identity.py
  negative_prompts.py
  style_prompts.py
  trend_prompts.py
  prompt_builder.py
  prompt_versions.py
  prompt_quality.py
  prompt_ab_tests.py

/imodel/trends/
  __init__.py
  trend_catalog.py
  weekly_trends.md
  viral_style_packs.py
  trend_research.md
  trend_scoring.py

/imodel/styles/
  __init__.py
  commercial_styles.py
  seasonal_styles.py
  premium_packs.py
```

**Phase 1 exit:** Modules importable; unit tests on `build_prompt` / `score_prompt`; **no** change to `generate_image_from_bytes`.

---

## 3. Commercial style object schema

```json
{
  "key": "old_money_portrait",
  "name": "Old Money Portrait",
  "category": "Luxury",
  "audience": ["entrepreneurs", "dating", "instagram", "men", "women"],
  "use_case": ["social profile", "status", "personal brand"],
  "trend_level": "high",
  "commercial_angle": "look expensive, calm, confident, refined",
  "prompt_version": "v1.0",
  "base_prompt": "...",
  "identity_lock": "...",
  "lighting": "...",
  "camera": "...",
  "clothing": "...",
  "background": "...",
  "mood": "...",
  "negative_prompt": "...",
  "safety_notes": "...",
  "price_credits": 4,
  "is_premium": true,
  "is_trending": true,
  "is_active": true,
  "sort_order": 10,
  "ab_test_group": "luxury_a",
  "success_rate": null,
  "conversion_score": null
}
```

**DB mirror (Phase 2):** `imodel_styles` — see [04](./04_ARCHITECTURE_REFACTOR_PLAN.md).

---

## 4. `build_prompt` contract (Phase 1)

```python
def build_prompt(
    style_key: str,
    user_description: str | None = None,
    intensity: str = "premium",  # natural | premium | cinematic
    gender_mode: str = "keep",
    output_mode: str = "portrait",
    locale: str = "en",
) -> dict:
    ...
```

**Returns:**

```python
{
    "final_prompt": str,
    "negative_prompt": str,
    "prompt_version": str,
    "style_key": str,
    "price_credits": int,
    "safety_notes": list[str],
}
```

**Assembly order:**

1. Load style object by `style_key`  
2. Append `base_identity` (or per-style `identity_lock`)  
3. Apply intensity modifier (lighting/mood strength)  
4. Append optional `user_description` (sanitized via `enforce_safe_prompt` logic)  
5. Append safety suffix  
6. Merge `negative_prompt` from style + global baseline  

**Phase 7 integration:** `generation_service` calls `build_prompt` when `USE_PROMPT_BUILDER=1`; else existing `PRESETS[].prompt` or user text.

---

## 5. Identity lock baseline (`base_identity.py`)

```
Preserve the exact same facial identity from the input selfie: same person, same age range, same facial structure, same ethnicity, same skin tone, same natural eye color, same hairline and hair color, same face proportions. Do not de-age, do not reshape the face, do not change ethnicity, do not create a different person. Improve only lighting, clothing, background, camera quality and professional styling.
```

**Align with today:** `IDENTITY_LOCK` in `app.py` (~1814) — migration should not weaken Copy Mode or standard gen.

---

## 6. Negative prompt baseline (`negative_prompts.py`)

```
different person, changed ethnicity, changed age, face reshaped, de-aged, over-beautified, plastic skin, doll face, fake smile, uncanny face, distorted face, asymmetrical eyes, extra fingers, extra hands, bad anatomy, low quality, blurry, pixelated, watermark, logo, text, brand name, celebrity, copyrighted character, nudity, sexual content, violence, weapon
```

**Today:** `NEGATIVE_LOCK`, `STRICT_NEGATIVE` in `app.py` — map into builder output.

---

## 7. Trend catalog categories (`trend_catalog.py`)

Full seed list for Phase 1. **No celebrity or brand names.**

### Business Money (10)

LinkedIn Premium, CEO Portrait, Founder Portrait, Real Estate Agent, Consultant Look, Beauty Master Profile, Podcast Guest, Luxury Realtor, Private Banker, Speaker Profile

### Dating / Social (10)

Tinder Natural, Golden Hour Dating, Coffee Date, Soft Smile, Urban Attractive, Weekend Lifestyle, Elegant Evening, Instagram Lifestyle, Travel Profile, Warm Window Light

### Luxury / Status (10)

Old Money, Quiet Luxury, Dubai Mood, Luxury Hotel Lobby, Rooftop Night, Private Jet Mood, CEO After Dark, Monaco Evening, Luxury Car Portrait, Premium Watch Editorial (no visible brand logos)

### Cinematic (10)

Dark Hero, Noir Detective, Movie Poster, Rainy Street, Royal Drama, Cyber City, Vintage Film Portrait, Dramatic Studio, Night Drive, Elegant Mystery

### TikTok / Viral (10)

AI Yearbook, 90s Studio Flash, Y2K Flash, LinkedIn Glow Up, Passport Photo Glow Up, Clean Aesthetic, Euro Summer, Corporate Villain (safe), Soft Life, Mob Wife Inspired (safe luxury)

### Seasonal (10)

Christmas Portrait, New Year Luxury, Valentine Dating, Summer Vacation, Autumn Coffee, Birthday Photoshoot, Wedding Guest, Black Friday Business, Winter Luxury, Spring Soft Portrait

### Local Europe (8)

Frankfurt Business Portrait, Berlin Startup Founder, Munich Luxury, European Old Money, German LinkedIn, Real Estate Agent Germany, Beauty Salon Owner Germany, European Café Portrait

**Safe naming examples:**

| Unsafe trend name | Safe commercial photoshoot |
|-------------------|----------------------------|
| Mob Wife | Luxury Evening Editorial |
| Corporate Villain | CEO After Dark |
| Thomas Shelby / John Wick / James Bond | Dark elegant vintage cinematic portrait / Formal noir city portrait |

---

## 8. First 30 Premium Photoshoots (launch catalog)

| # | key (proposed) | Category |
|---|----------------|----------|
| 1 | linkedin_premium | Business |
| 2 | ceo_portrait | Business |
| 3 | founder_portrait | Business |
| 4 | real_estate_agent | Business |
| 5 | consultant_look | Business |
| 6 | beauty_master_profile | Business |
| 7 | podcast_guest | Business |
| 8 | speaker_profile | Business |
| 9 | golden_hour_dating | Dating |
| 10 | coffee_date | Dating |
| 11 | natural_smile | Dating |
| 12 | urban_confidence | Dating |
| 13 | weekend_lifestyle | Dating |
| 14 | elegant_evening | Dating |
| 15 | old_money_portrait | Luxury |
| 16 | quiet_luxury | Luxury |
| 17 | luxury_hotel_lobby | Luxury |
| 18 | dubai_mood | Luxury |
| 19 | ceo_after_dark | Luxury |
| 20 | rooftop_night | Luxury |
| 21 | private_jet_mood | Luxury |
| 22 | dark_hero | Cinematic |
| 23 | noir_portrait | Cinematic |
| 24 | rainy_street | Cinematic |
| 25 | movie_poster | Cinematic |
| 26 | royal_drama | Cinematic |
| 27 | nineties_studio_flash | Viral |
| 28 | linkedin_glow_up | Viral |
| 29 | passport_glow_up | Viral |
| 30 | euro_summer | Viral |

Copy Any Style remains separate flow (`USER_COPY_MODE`), not a single style_key portrait.

---

## 9. Premium packs (`premium_packs.py`)

| Pack | Styles (subset) | Price | Promise |
|------|-----------------|-------|---------|
| Money Profile Pack | LinkedIn Premium, CEO, Founder, Real Estate, Consultant, Podcast Guest | 599★ / 18 credits | Professional, expensive, trustworthy |
| Dating Upgrade Pack | Golden Hour, Coffee Date, Natural Smile, Urban Confidence, Soft Lifestyle, Elegant Evening | 599★ / 18 credits | Better profiles without looking fake |
| Luxury Status Pack | Old Money, Luxury Hotel, Dubai, Rooftop, Private Jet, CEO After Dark | 999★ / 35 credits | Luxury editorial world |
| Viral TikTok Pack | 90s Flash, Y2K, LinkedIn Glow Up, Passport Glow Up, Clean Aesthetic, Euro Summer | 999★ / 35 credits | Trending social looks |
| Copy Any Style Pack | Copy flow | 4 credits/result or 999★ for 12 | Any style, your face |

---

## 10. Prompt quality scoring (`prompt_quality.py`)

```python
def score_prompt(prompt_object: dict) -> dict:
    return {
        "score": 92,
        "grade": "A+",  # A+ | A | B | C
        "warnings": [],
        "recommendations": [],
    }
```

**Criteria (15):** identity preservation, commercial attractiveness, trend relevance, realism, lighting, camera, clothing, background, mood, safety, no celebrity names, no brand names, no oversexualization, no unrealistic body change, no contradiction.

| Grade | Mini App visibility |
|-------|---------------------|
| A+ | Featured / Trending |
| A | Active catalog |
| B | Test cohort only |
| C | Hidden (`is_active=false`) |

---

## 11. Prompt versioning

- Every style has `prompt_version` (e.g. `v1.0`)  
- Jobs store: `style_key`, `prompt_version`, `ab_test_group`, `final_prompt_hash`, `negative_prompt_hash` (Phase 2/7 extend `imodel_jobs` / `imodel_generation_results`)  
- `prompt_versions.py` — changelog per key  

---

## 12. A/B testing placeholders (`prompt_ab_tests.py`)

- Variant A vs B per `style_key`  
- Traffic split env or DB flag (future)  
- Metrics: success_rate, regeneration_rate, payment_conversion_after_style, repeat_use_rate, refund_rate  

**Phase 7+:** read split in `build_prompt`; write group to job row.

---

## 13. Mapping: existing `PRESETS` → future `style_key`

| PRESETS.key (today) | Proposed style_key | Notes |
|---------------------|-------------------|-------|
| studio_soft | studio_soft_v1 | Keep prompt text as v1.0 seed |
| cinematic | cinematic_portrait | |
| golden_hour | golden_hour_dating | Align dating pack |
| editorial_highkey | editorial_highkey | |
| bw_film | bw_film_portrait | |
| kodak_portra | kodak_portra | |
| beauty_dish | beauty_dish | |
| headshot | linkedin_premium | Rename commercial |
| neon_night | neon_night | |
| cafe | coffee_date | |
| forest | forest_lifestyle | |
| beach | beach_sunrise | |
| architecture | architecture_editorial | |
| luxury_interior | luxury_hotel_lobby | |
| rain_window | rainy_street | |
| snow | winter_luxury | |
| rembrandt | rembrandt_classic | |
| soft_glam | soft_glam | |
| vintage70 | nineties_studio_flash | Partial overlap viral |
| mono_hicon | mono_high_contrast | |
| park | park_lifestyle | |
| fitness | fitness_portrait | |
| garage | garage_cinematic | |
| bookstore | european_cafe_portrait | |

**Migration rule (Phase 7):**

1. `cb_preset_pick` continues to work via index → map index to `style_key`  
2. `USE_PROMPT_BUILDER=0` uses `PRESETS[i].prompt` unchanged  
3. `USE_PROMPT_BUILDER=1` uses `build_prompt(style_key)`  

---

## 14. Copy Mode as premium feature

**Today (`app.py`):**

- `USER_COPY_MODE`, `USER_COPY_STYLE`, `craft_mj_prompt_from_image`, `generate_image_from_bytes(strict=True, style_bytes=...)`  
- **1 credit** per success  
- **Do not break** until Phase 7 regression passes  

**Future:**

- Price: **4 credits** per result OR **12 credits** for 4-photo set  
- Prompt: same scene/lighting/framing/mood; identity from selfie only  
- Optional: `prompt_engine.py` Vision JSON merged into builder (Phase 1 cleanup)  

**Scene lock:** Keep `SCENE_LOCK` string behavior in strict mode.

---

## 15. Job metadata (future)

Extend `record_job` / `imodel_jobs` when Phase 7 enables:

| Field | Source |
|-------|--------|
| style_key | User selection |
| prompt_version | `build_prompt` |
| ab_test_group | `prompt_ab_tests` |
| final_prompt_hash | SHA256 truncated |
| negative_prompt_hash | SHA256 truncated |
| user_action_after_result | Phase 11 events |

---

## Cross-links

- Weekly ops: [TREND_OPERATIONS_PLAYBOOK](./TREND_OPERATIONS_PLAYBOOK.md)  
- Architecture: [04](./04_ARCHITECTURE_REFACTOR_PLAN.md)  
- Phases: [05](./05_IMPLEMENTATION_PHASES.md) — Phase 1 skeleton, Phase 7 integration
