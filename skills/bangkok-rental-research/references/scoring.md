# Scoring rubric — 0 to 100 (rentals)

Score every unit that passes the four hard filters. Higher = better rental for the money.
Weighted sum, clamped 0–100.

Renting is a *different problem from buying*: there is no ownership risk and no resale, so the weight
that the sales skill puts on foreign-quota certainty and liquidity moves here onto **transit access**
and **move-in cash**, which are what actually bite a tenant.

| Component | Weight | How to score (0–1, then × weight × 100) |
|---|---|---|
| **Value — rent per m² vs area median** | 0.28 | 1.0 if ≥25% below the cluster median THB/m²/month; 0.5 at median; 0.0 if ≥25% above. Interpolate. |
| **Transit access** | 0.22 | From `walk_min` to BTS/MRT/ARL: ≤3 min = 1.0, 5 min = 0.85, 8 min = 0.65, 12 min = 0.45, 20 min = 0.2, >25 min or no rail = 0.1. Unstated = 0.45 (a listing that hides its walk usually has one). Prime central clusters get a ×1.1 nudge, capped at 1.0. |
| **Absolute size** | 0.15 | Rent is paid for space you live in, so score m² directly, not per-baht: ≥60 m² = 1.0, 45 m² = 0.8, 35 m² = 0.6, 28 m² = 0.45, 22 m² = 0.3, ≤18 m² = 0.15. Null = 0.4 (undisclosed size skews small). |
| **Move-in cost** | 0.12 | Total cash to move in, as a multiple of one month's rent: ≤2× = 1.0, 3× = 0.8, 4× (the 2+1 norm) = 0.55, 5× = 0.3, ≥6× = 0.1. **Unknown = 0.5** — do not reward or punish silence. |
| **Furnishing & condition** | 0.10 | Fully furnished = 1.0, partly = 0.6, unfurnished = 0.25 (real cost to fix at this budget), null = 0.45. Nudge up for a recent building or a stated renovation, down for visibly dated stock. |
| **Building quality / age** | 0.08 | ≤8 years and a known developer = 1.0; scale down with age; unknown = 0.5. |
| **Listing quality & trust** | 0.05 | Owner-direct with photos, size, floor and terms all stated = 1.0. Missing size, no photo, no terms, or an agent-only phone-reveal = lower. Anything flagged as a possible short-stay or bait listing = 0.0. |

**Total = Σ(component × weight) × 100**, rounded.

## Rules
- Missing data scores its **neutral midpoint**, not zero — except where the rubric names a value
  (move-in unknown = 0.5, size null = 0.4, walk unstated = 0.45).
- A listing flagged as possible short-stay, bait, or with a rent far below its area's floor **cannot
  score above ~55**: it loses the trust weight outright and should be read as "verify before viewing".
- Record a one-line rationale in `notes` for the top rows (e.g. "31% under-median THB/m², 4 min to
  Punnawithi, fully furnished, 3× move-in").
- Scores are comparable **within a run only** — the whole master is re-scored with one function every
  week, so absolute values shift as the medians move.
