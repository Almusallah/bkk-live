---
name: bangkok-property-research
description: Weekly market-research routine for Bangkok condominiums a foreigner can buy — budget USD 80,000–200,000, 2+ bedrooms, foreign-freehold quota only. Fans out subagents across the major Thai property portals, dedupes and scores every listing, and publishes/refreshes ONE live Google Sheet (with an .xlsx fallback) containing Price, sqm, price/sqm, link, score, position/area, and picture thumbnails. Trigger when the user asks to research Bangkok property, run the weekly property scan, update the property sheet, or invokes this skill by name. Designed to run headless on a schedule (cloud routine / cron) as well as interactively.
---

# Bangkok Property Research — Weekly Subagent Scan

Produce and keep-alive a single Google Sheet of Bangkok condo listings that match Yuri's buy-box, refreshed on a weekly cadence by a fleet of research subagents. The sheet accumulates over time (it is not thrown away each week) so trends and new inventory are visible.

## The buy-box (hard filters — non-negotiable)

1. **Location:** Bangkok, Thailand (Krung Thep). Prime + emerging foreigner-friendly districts (see `references/sources.md`).
2. **Budget:** **USD 80,000 – 200,000** total price. Convert to THB at the *live* rate each run (see step 2). Anything outside the band is dropped, never "rounded in".
3. **Bedrooms:** **2 bedrooms or more.** 1-bed, studio, and "1+study" are dropped.
4. **Foreigner-buyable — this is the critical legal filter.** In Thailand a foreigner **cannot own land**, so houses/townhouses/villas on freehold land are **out**. A foreigner **can** own a **condominium unit in freehold** as long as the building is within its **49% foreign-ownership quota**. Therefore:
   - **Only condominiums.** No houses, townhouses, land, or "villa" unless it is explicitly a condominium title.
   - Prefer listings that state **"foreign freehold" / "foreign quota available" / "farang name"**. If a unit is only offered as **Thai freehold / leasehold / company-owned**, mark it `foreign_freehold: "leasehold_or_thai_only"` and **penalise the score heavily** (it is a fallback, not a target) — do not silently drop it, but never let it outrank a true foreign-freehold unit.
   - If quota status is unstated, mark `"unknown"` and note "confirm quota with agent".

A listing must pass **all four** to enter the sheet. When in doubt about legality, keep the row but flag it — never fabricate quota status.

## Output schema (one row per unit)

| Field | Notes |
|---|---|
| `title` | Project / unit name |
| `district` | Area, e.g. "Sukhumvit — Phrom Phong" |
| `position` | Nearest BTS/MRT + walking notes (this is the "position" column) |
| `price_thb` | Asking price, THB |
| `price_usd` | Computed at live rate |
| `sqm` | Interior area, m² |
| `price_per_sqm_thb` | Computed |
| `bedrooms` | Integer ≥ 2 |
| `foreign_freehold` | `foreign_freehold` \| `unknown` \| `leasehold_or_thai_only` |
| `score` | 0–100, see `references/scoring.md` |
| `link` | Canonical listing URL |
| `image_url` | Direct URL to the primary photo (used for the picture thumbnail) |
| `source` | Portal name |
| `notes` | Yield/quota/age flags, agent, anything decision-relevant |
| `first_seen` / `last_seen` | Dates (dedup + freshness) |

## Runtime workflow

Follow these steps in order. Steps 3–5 are the subagent fan-out.

### 1. Load context
Read `references/sources.md`, `references/scoring.md`, and `state.json` (the dedup + master-row memory; create it as `{"rows": [], "last_run": null}` if missing). The `rows` array is the running master list keyed by `link`.

### 2. Fix the currency band
Get the **live USD→THB rate** (`WebSearch "USD THB exchange rate"` or WebFetch a rate page). Compute the THB budget window and record the rate used. Example at ~36.5: **USD 80k–200k ≈ THB 2.92M – 7.30M**. Use *this run's* rate for all `price_usd` conversions so the sheet is internally consistent.

### 2b. Harvest FazWaz server-side FIRST (highest-yield step, no subagent needed)

FazWaz is the only portal that publishes a **per-unit ownership/quota** field, and as of
2026-08-24 the whole harvest runs in Bash with no browser:

```bash
cd <scratchpad>
python3 ~/.claude/skills/bangkok-property-research/scripts/fz_search.py 1 70   # -> fz_units.json (~2,000 units)
python3 ~/.claude/skills/bangkok-property-research/scripts/fz_detail.py        # -> fz_detail.json (true THB + ownership)
python3 ~/.claude/skills/bangkok-property-research/scripts/fz_to_rows.py       # -> fazwaz.json (in-band rows)
```

`fz_detail.py` reads the **true THB price out of each detail page's `dataLayer` `property_view`
event**, so the VND geo-IP display-currency trap cannot affect it, and it asserts
`currency == 'THB'` rather than converting. It checkpoints every 150 units, so re-running
resumes. Budget ~15 min for 2,000 detail pages. See `references/sources.md` for the details.

### 3. Fan out research subagents

> **COST DISCIPLINE — read before spawning anything.** Measured 2026-09-01 across every past run:
> the subagent fan-out is 40–80% of what a run costs (`$31–$168` per run at Opus rates), and the
> orchestrator's own cache reads are most of the rest. Three rules, in priority order:
>
> 1. **A portal with a known recipe is a SCRIPT, never an agent.** Server-side harvesting costs
>    *zero model tokens*. On 2026-09-01 two scripts returned 2,358 rows for $0 while five agents
>    returned 835 rows for $31. Before assigning a portal to an agent, check `references/sources.md`
>    — if it documents a working curl/API recipe, write or reuse a `harvest_*.py` instead. Agents are
>    for portals whose recipe is *unknown*, and their real job is to come back with the recipe so the
>    next run doesn't need them.
> 2. **Match the model to the work — pass `model` on the Agent call.**
>    - `model: "haiku"` for mechanical harvest and extraction: fetch pages, regex out fields, emit
>      JSON. This is most of the fleet and Haiku is ~5× cheaper than Opus.
>    - Leave the default (Opus) **only** for agents making a legal or judgement call — foreign-quota
>      / ownership-eligibility verification, conflicting-price adjudication, anything where being
>      wrong misleads a purchase decision. Never downgrade the quota-verification agent to save money.
> 3. **Agents WRITE their rows to a file and reply with ONE LINE** (`N rows written, which portals
>    worked/failed`). Never let an agent paste a JSON array back through the conversation — that array
>    is then re-read on every subsequent turn and is the single largest driver of orchestrator cache
>    reads (one run hit 178M cache-read tokens = $89 in re-reads alone).
>
> Also: **never `WebFetch` the published artifact page** to inspect it — these pages are 12–36 MB and
> a single fetch dumps megabytes into context. Read the local build output, or parse the saved copy
> with a script.


Spawn `general-purpose` subagents in a single message so they run concurrently — **as few as the
unscripted portals require**, not one per area-cluster by reflex. With the scripts in place a normal
run needs 2–4 agents, not 8. Pass `model: "haiku"` on every harvest/extraction agent; keep the
default model only for the quota-verification agent. Give each subagent:
- The buy-box (all four hard filters, verbatim), the THB band from step 2, and its assigned districts + portals.
- The output schema above, and this instruction: **"WRITE your rows as a JSON array to `<workdir>/clusterN.json`. Do NOT return them in your reply — your final message must be ONE LINE: the row count and which portals worked or failed. Try plain HTTP first (curl/urllib with a desktop UA, `Accept-Language: th-TH` for Thai sites) before WebFetch or a browser. Include the direct listing URL and a direct image URL for every unit. Do not invent listings, prices, or quota status — null any field you cannot verify. A thin result is a valid result; never pad."**
- Portals whose recipe is already documented in `references/sources.md` — FazWaz, LivingInsider,
  Thailand-Property, and (since 2026-09-01) DDproperty, Baania, Kaidee, PropertyScout, PropertyHub,
  BahtSold — **must not be assigned to an agent.** Harvest them with the `harvest_*.py` scripts or
  write the missing script once. Agents exist to crack portals we do *not* yet have a recipe for.

Portals to cover (details in `references/sources.md`): DDproperty, Hipflat, FazWaz, Thailand-Property, Dot Property, Bangkok Post Property, Angloinfo/expat boards. Each area-cluster agent should hit several portals for its districts.

### 4. Aggregate, dedup, score

**Back up state first — `aggregate.py` writes `state.json` in place:**
```bash
cp ~/.claude/skills/bangkok-property-research/state.json ~/.claude/skills/bangkok-property-research/state.json.bak
python3 ~/.claude/skills/bangkok-property-research/scripts/aggregate.py
```
`aggregate.py` does all of the below in one pass, including an **authoritative FazWaz
override** that re-reads every FazWaz row's price and quota from `fz_detail.json` and
corrects anything an agent got wrong. Edit the `TODAY`/`RATE` constants at its top each run.
- Collect every subagent's JSON. Drop malformed rows.
- **Dedup** by canonical `link` (strip query strings/trackers) and by fuzzy (project + floorplan + price within 2%) against both this run's pool and `state.json.rows`. For a returning listing, keep the original `first_seen`, update `last_seen`, price, and score.
- **Re-verify the hard filters yourself** — do not trust an agent that let a 1-bed or a landed house through.
- **Score** each unit 0–100 per `references/scoring.md`.
- Sort by score descending.

### 5. Publish / refresh the sheet
Run the publisher, which writes the local xlsx artifact **and** (if configured) pushes to the live Google Sheet:

```bash
python3 ~/.claude/skills/bangkok-property-research/scripts/publish.py \
  --rows /path/to/aggregated_rows.json \
  --xlsx ~/.claude/skills/bangkok-property-research/runs/bangkok-properties.xlsx
```

- The script always (re)writes `runs/bangkok-properties.xlsx` with two sheets: **Master** (all live rows, newest/highest first, image thumbnails embedded) and **This Week** (rows whose `last_seen` == today). Columns are exactly: Score, Title, District, Position, Price USD, Price THB, sqm, THB/sqm, Beds, Foreign Freehold, Link, Picture, Source, Notes, First seen, Last seen.
- **Live Google Sheet:** if the env var `BANGKOK_SHEET_WEBHOOK` is set (a Google Apps Script Web-App URL — one-time setup in `assets/AppsScript.gs`), the script POSTs the full row set as JSON. The Apps Script keeps one persistent spreadsheet: it upserts into a **Master** tab (thumbnails via `=IMAGE(url)`) and appends a dated snapshot tab. This is the "live sheet that stays updated" — same URL every week. The script prints the sheet URL on success.
- **Fallback if no webhook:** upload/overwrite `bangkok-properties.xlsx` to Google Drive via the Drive MCP (`create_file`) so there is still a cloud copy; Drive renders it as a Sheet. Report the local path either way.

### 6. Persist state & report
- Write the merged master list back to `state.json` (`rows` + `last_run` = today's date).
- Append a short dated entry to `runs/log.md`: rate used, # agents, # new listings, # total live rows, top 3 by score (title + score + price + link), and anything that blocked (portal down, captcha, thin inventory).
- Report to the user: the live sheet URL (or xlsx path), count of new vs total, and the top 3 picks with one-line rationale each.

## Running it as a weekly routine

This skill is built to run unattended. To schedule it:

- **Cloud routine / cron (preferred, laptop-off):** create a scheduled agent whose prompt is *"Run the bangkok-property-research skill: do the full weekly scan and refresh the live sheet."* on a weekly cron (e.g. Monday 08:00 Asia/Bangkok). Use the `schedule` skill or `mcp__scheduled-tasks__create_scheduled_task`. For a headless run the **Google Sheet webhook path must be configured** (Drive-MCP/interactive fallbacks may be absent) — so set `BANGKOK_SHEET_WEBHOOK` in the routine's environment.
- **Local recurring:** the `/loop` skill weekly, or a launchd/cron entry that invokes Claude Code with the same prompt.

One-time setup for the live sheet is in `assets/AppsScript.gs` (deploy as a Web App, paste the URL into `BANGKOK_SHEET_WEBHOOK`). Until that's set, the skill still produces the xlsx every run.

## Guardrails
- **Never fabricate** listings, prices, photos, or foreign-quota status. A thin week (few real matches) is a valid result — report it honestly rather than padding.
- **Legality first:** the whole point is units a foreigner can actually buy. When quota is unclear, flag it; don't assume.
- **Money:** this skill only *researches and ranks*. It never contacts agents, pays deposits, or transacts. Surfacing a shortlist is where it stops.
- **Idempotent:** re-running in the same week updates rows in place (via dedup) rather than duplicating them.
