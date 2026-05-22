# Trend Operations Playbook

**Audience:** Product owner / operator (non-developer)  
**Technical spec:** [03 Prompt & Trend Engine Spec](./03_PROMPT_AND_TREND_ENGINE_SPEC.md)  
**Developer file (Phase 1):** `imodel/trends/weekly_trends.md`  
**Phases:** Enable catalog Phase 1 · Trend Lab UI Phase 9 · Broadcast Phase 11

---

## 1. Purpose

Run iModel like a **living fashion studio**, not a static bot:

- Weekly trend research → safe commercial photoshoots  
- Enable/disable looks without code deploys (Phase 2+ via `imodel_styles.is_active`)  
- Improve prompts based on what sold and what looked fake  

---

## 2. Weekly trend report template

Copy into `imodel/trends/weekly_trends.md` or Notion each Monday:

```markdown
# Weekly Trend Report

## Week
YYYY-MM-DD

## Hot Trends
1.
2.
3.
4.
5.

## Commercial Interpretation

### Trend: 
**Safe paid version:** 
**Why it sells:** 

(repeat per trend)

## New Styles To Add
- style_key:
- category:
- commercial_angle:

## Styles To Disable
- style_key:
- reason: (low quality / safety / poor conversion)

## Prompt Improvements
- style_key: (e.g. stronger identity lock, less retouching)

## A/B Tests
- style_key: v1.0 vs v1.1 — hypothesis:

## Notes
- What users clicked:
- What failed:
- What looked fake:
- What sold:
```

---

## 3. Convert unsafe/raw trends into safe photoshoots

| Raw trend (social media) | Safe paid photoshoot name | Never use |
|--------------------------|---------------------------|-----------|
| Mob Wife | Luxury Evening Editorial | Character names |
| Corporate Villain | CEO After Dark | Weapons, violence |
| Old Money aesthetic | Quiet Luxury Portrait | — |
| AI Yearbook | AI Yearbook Portrait (safe school studio) | Minors sexualization |
| John Wick / Bond / Shelby | Formal noir city portrait / Dark elegant vintage cinematic | Celebrity names |
| Brand drops (Gucci, etc.) | Quiet luxury editorial, no logos | Brand names in prompt |

**Rule:** If you cannot explain the look in plain commercial language, do not ship it.

---

## 4. Decide which styles to add

Add a new photoshoot when **all** are true:

1. Clear audience (dating, LinkedIn, luxury, viral)  
2. Safe description (passes [03](./03_PROMPT_AND_TREND_ENGINE_SPEC.md) scoring ≥ A)  
3. Distinct visual from existing `style_key` (not duplicate of `headshot` vs `linkedin_premium`)  
4. Expected conversion story (why pay 4 credits?)  

**Process:**

1. Owner fills “New Styles To Add” in weekly report  
2. Prompt Director drafts object in `commercial_styles.py`  
3. `score_prompt` ≥ A → staging  
4. Enable `is_trending` for Trend Lab “New drops”  

---

## 5. Decide which styles to disable

Disable when:

- Identity complaints > threshold for that style  
- Replicate sensitive failures spike  
- Grade C in quality review  
- Trend dead (no clicks 14 days)  
- Safety concern  

**Action:** Set `is_active=false` in DB (Phase 2) or remove from trending flags. **Do not** delete keys—preserve analytics.

---

## 6. Prompt improvement notes

Focus areas (from production learnings):

- Stronger identity lock (less face drift)  
- Reduce over-retouching / plastic skin  
- Better clothing and fabric detail  
- Safer cinematic language (no weapons/violence)  
- Stronger camera realism (lens, f-stop, lighting direction)  

Attach notes to `style_key` + bump `prompt_version` (e.g. `v1.0` → `v1.1`).

---

## 7. A/B testing notes

| When to A/B | Example |
|-------------|---------|
| High traffic style | `old_money_portrait` v1.0 vs v1.1 lighting |
| New launch uncertainty | `linkedin_glow_up` two mood variants |
| Conversion drop | `golden_hour_dating` softer vs stronger grade |

Record in weekly report; engineering enables split via `ab_test_group` (Phase 7+).

**Success metrics:** payment after view, regeneration rate, refund rate, repeat use within 7d.

---

## 8. Trend drop announcement copy

**Bot (short):**

```
New trending looks just dropped in iModel Studio.
Open Studio and try this week’s premium photoshoots.
```

**Mini App hero:** “Trending this week” carousel updated from `trend_catalog` + `is_trending` flags.

**Seasonal examples:**

- Valentine: “Dating Upgrade — Elegant Evening & Golden Hour”  
- Q4: “Winter Luxury & New Year Portrait”  

---

## 9. Admin checklist (weekly)

- [ ] Weekly report filed  
- [ ] New styles reviewed for celebrity/brand/NSFW  
- [ ] `score_prompt` run on new entries (Phase 1+)  
- [ ] Trending flags updated (`is_trending`)  
- [ ] Weak styles disabled (`is_active=false`)  
- [ ] A/B tests documented with end date  
- [ ] Announcement scheduled (bot broadcast Phase 11)  
- [ ] Review `/admin` metrics: top styles, failures (Phase 10)  

---

## 10. Developer handoff

When owner completes weekly report, Backend/Prompt agent:

1. Updates `trend_catalog.py` / `imodel_styles` seeds  
2. Bumps `prompt_version` where noted  
3. Deploys Phase 3+ API cache refresh (no full app rewrite)  

**Phase 0:** Manual prompt edits in spec files only—no production deploy required.

---

## Cross-links

- [00 Current State Audit](./00_CURRENT_STATE_AUDIT.md) — no trend system today  
- [05 Implementation Phases](./05_IMPLEMENTATION_PHASES.md) — Phase 9 Trend Lab  
- [07 Rollback Plan](./07_ROLLBACK_PLAN.md) — disable Trend Lab route
