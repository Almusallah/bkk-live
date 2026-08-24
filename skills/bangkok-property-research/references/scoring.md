# Scoring rubric — 0 to 100

Score every unit that passes the four hard filters. Higher = better buy for Yuri. Compute the weighted sum; clamp to 0–100. Show the number in the sheet's Score column and sort by it.

| Component | Weight | How to score (0–1, then × weight × 100) |
|---|---|---|
| **Value (price/sqm vs area median)** | 0.30 | 1.0 if price/sqm is ≥20% below the district median (from Hipflat/portal analytics); 0.5 at median; 0.0 if ≥20% above. Interpolate. |
| **Foreign-freehold certainty** | 0.20 | 1.0 = confirmed foreign freehold quota; 0.4 = unknown (needs agent confirmation); 0.0 = leasehold / Thai-only / company. |
| **Position (transit + district)** | 0.15 | 1.0 if ≤300 m to BTS/MRT in a prime district; scale down with walking distance and for fringe districts. |
| **Size / layout** | 0.10 | 1.0 for ≥70 m² true 2-bed; 0.6 for 45–55 m² compact 2-bed; penalise sub-45 m² "2-beds". |
| **Rental yield potential** | 0.10 | Estimate gross yield from comparable rents; 1.0 at ≥6%, 0.5 at ~4%, 0.0 at ≤2.5%. Note the estimate in `notes`. |
| **Building quality / age** | 0.08 | 1.0 for ≤8-yr-old, reputable developer, good facilities; lower for aging or unknown-developer stock. |
| **Liquidity / resale** | 0.07 | 1.0 in high-turnover foreign-favoured buildings/areas; lower where foreign resale is thin. |

**Total = Σ(component_0to1 × weight) × 100**, rounded to an integer.

## Rules
- If a data point is missing, score that component at its neutral midpoint (0.5) and add a `notes` flag, rather than zero — but **foreign-freehold "unknown" is 0.4, not 0.5** (uncertainty here is a real cost).
- A `leasehold_or_thai_only` unit can never score above ~55 because it loses the full 0.20 freehold weight — that is intentional; it should sit below any decent foreign-freehold unit.
- Record a one-line score rationale in `notes` for the top rows (e.g. "18% under-median THB/sqm, 250 m to BTS, foreign quota confirmed").
