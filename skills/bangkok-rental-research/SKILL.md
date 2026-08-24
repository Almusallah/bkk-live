---
name: bangkok-rental-research
description: Weekly market-research routine for Bangkok RENTAL homes in the USD 350–650/month band — condos, apartments and studios a foreigner can rent long-term. Fans out subagents across the Thai and expat rental portals (Renthub, DDproperty, FazWaz, PropertyScout, PropertyHub, Baania, LivingInsider, BahtSold), dedupes and scores every listing, and republishes ONE live artifact page with an interactive map, photos, filters and sorts. Trigger when the user asks to research Bangkok rentals, run the weekly rental scan, refresh the rental page, or invokes this skill by name. Designed to run headless on a schedule as well as interactively.
---

# Bangkok Rental Research — Weekly Subagent Scan

Sibling of `bangkok-property-research` (which covers units to **buy**). This one covers units to
**rent**, and the analysis is different: there is no foreign-ownership question when you rent, so the
axes that matter become **rent per m², walk to transit, move-in cash, and lease terms**.

## The buy-box (hard filters — non-negotiable)

1. **Location:** Bangkok, Thailand. Contiguous metro on the BTS/MRT (Samut Prakan, Nonthaburi) is
   allowed but must be flagged `OUTSIDE BANGKOK PROVINCE` at the start of `notes`.
2. **Rent: USD 350–650 per month**, converted to THB at the *live* rate each run (step 2 below).
   This is the advertised monthly rent **excluding utilities**. Outside the band = dropped, never
   rounded in.
3. **Long-term residential rental** — lease of roughly 6 months or more. Drop daily / weekly /
   short-stay / Airbnb-style / hotel / by-the-night serviced apartments. Drop shared rooms, dorm
   beds and co-living bed-in-a-room products. A studio is in scope; a bed in someone's flat is not.
4. **A real, currently-advertised unit** with an actual rent figure — not a "from THB X" project
   advert with no unit behind it.

**There is no minimum bedroom count.** At this budget the market is mostly studios and 1-beds, with
2-beds appearing at the top of the band and in outer districts. Studios are recorded as
`bedrooms: 0`, and the published page exposes a bedroom filter so the reader sets their own floor
rather than having one imposed.

## Output schema (one row per unit)

| Field | Notes |
|---|---|
| `title` | Project / unit name |
| `district` | Area |
| `position` | Nearest BTS/MRT/ARL + walking notes |
| `walk_min` | Minutes' walk to that station **only if stated/derivable**, else null |
| `rent_thb` | Monthly rent, THB |
| `rent_usd` | Computed at the live rate |
| `sqm`, `bedrooms`, `bathrooms`, `floor` | `bedrooms: 0` = studio |
| `thb_per_sqm` | Computed rent per m² per month — the value yardstick |
| `furnished` | `fully` \| `partly` \| `unfurnished` \| null |
| `deposit_months`, `advance_months` | Null when unstated — never assume the 2+1 norm |
| `movein_thb` | Computed: rent × (1 + deposit + advance) when both are known, else null |
| `min_lease_months`, `pets`, `available_from` | Null when unstated |
| `lister` | `owner` \| `agent` \| null |
| `score` | 0–100, see `references/scoring.md` |
| `link`, `image_url`, `source`, `notes` | |
| `first_seen` / `last_seen` | Dates — dedup + freshness |

## Runtime workflow

### 1. Load context
Read `references/sources.md`, `references/scoring.md` and `state.json` (create as
`{"rows": [], "parked": [], "last_run": null}` if missing). `rows` is the running master keyed by `link`.

### 2. Fix the currency band
Fetch the live USD→THB rate (`curl -s https://open.er-api.com/v6/latest/USD`). Compute the THB band
and use *this run's* rate for every `rent_usd`. Record the rate.

### 3. Fan out research subagents
Spawn **one `general-purpose` subagent per area cluster** in `references/sources.md` (6–7 agents), all
in a single message so they run concurrently. Give each: the four hard filters verbatim, the THB band,
its districts and portals, the schema above, and the instruction that its final message must be
**only a raw JSON array**. Tell them explicitly: unstated deposit is `null`, not the norm.

### 4. Aggregate, dedupe, score
- Collect each agent's JSON straight from its task output file (see `scripts/extract.py`) so the
  orchestrator never holds hundreds of listings in context.
- Dedupe by canonical `link`, then fuzzy (project + sqm ±1 + rent ±2%) **within the run and against
  the master**. Cross-portal matches merge; same-portal near-matches stay distinct.
- Re-verify all four hard filters yourself.
- Score 0–100 per `references/scoring.md`, sort descending.

### 5. Publish
```bash
python3 scripts/build_artifact.py --rows final_rows.json --out bangkok-rentals.html \
    --rate <rate> --today <YYYY-MM-DD>
python3 scripts/publish.py --rows final_rows.json --xlsx runs/bangkok-rentals.xlsx
```
Then publish the HTML to **the same artifact URL every week** (see `runs/log.md` for the URL).
The page is self-contained: photos inlined as data URIs, map drawn as inline SVG. **The Artifact CSP
blocks every external host** — no tile server, no CDN, no remote images. Ever.

### 6. Persist state & report
Write the merged master back to `state.json` (`rows`, `parked`, `last_run`, `rate_thb_per_usd`),
append a dated entry to `runs/log.md` (rate, agents, new vs total, top picks, blockers), and report
the page URL, counts and top 3 with one-line rationales.

## Guardrails
- **Never fabricate** listings, rents, photos, deposits or lease terms. A thin week is a valid result.
- **Never assume the deposit.** "2 months + 1 advance" is the Bangkok norm, not a fact about a listing.
- **Rent that looks too good is usually not long-term.** Sub-market rents in prime areas are typically
  short-stay products or bait; flag rather than celebrate them.
- **Money:** this skill researches and ranks. It never contacts landlords, agents, or pays a deposit.
- **Idempotent:** re-running in the same week updates rows in place via dedup.
