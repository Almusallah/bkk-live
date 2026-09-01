# RUN-RENTAL.md — weekly Bangkok RENTAL scan (cloud routine runbook)

You are running the **bangkok-rental-research** weekly scan headless in a cloud sandbox.
Zero context: this file is the complete procedure. The user is not present — never ask;
choose reasonably and record choices in the log.

**Goal:** refresh the scored table of Bangkok long-term rentals at **USD 350–650/month**
(live rate), then publish `docs/rentals.html` and push to this repo (GitHub Pages serves it
to the user's phone app).

**Hard filters (all four, from skills/bangkok-rental-research/SKILL.md — read it first):**
Bangkok metro (non-Bangkok-province flagged `OUTSIDE BANGKOK PROVINCE` in notes); rent in
band excl. utilities; long-term (~6mo+) residential only — no daily/short-stay/co-living/
shared rooms; a real advertised unit with an actual rent figure. **No minimum bedrooms**
(studios = `bedrooms: 0`). **Never assume deposits** — unstated deposit/advance is null.
Never fabricate anything; a thin week is valid; research only, never contact landlords.

## 0a. Cost rules

**COST DISCIPLINE (measured 2026-09-01).** The subagent fan-out is 40-80% of what a run costs
($31-$168/run at Opus rates). Three rules:
1. **A portal with a documented recipe is a SCRIPT, never an agent** — server-side harvesting costs
   zero model tokens. Two scripts returned 2,358 rows for $0 on 2026-09-01; five agents returned 835
   rows for $31. FazWaz, LivingInsider, Thailand-Property, DDproperty, Baania, Kaidee, PropertyScout,
   PropertyHub and BahtSold all have recipes in references/sources.md — do not hand them to agents.
2. **Pass `model: "haiku"` on every mechanical harvest/extraction agent** (~5x cheaper). Keep the
   default model only for the foreign-quota / ownership verification agent — never downgrade the
   agent whose mistake would mislead a purchase decision.
3. **Agents WRITE rows to $BKK_WORK_DIR/clusterN.json and reply ONE LINE** (count + which portals
   worked/failed). An agent that pastes a JSON array back gets it re-read on every later turn — one
   run hit 178M cache-read tokens ($89) that way.
Also: never WebFetch the published artifact page (12-36 MB) — parse the saved copy with a script.
Spawn as few agents as the *unscripted* portals require: 2-4, not 8.


## 0. Setup
```bash
cd $(git rev-parse --show-toplevel)
pip install --quiet pillow requests openpyxl
SKILL=$PWD/skills/bangkok-rental-research
mkdir -p /tmp/rentwork && cd /tmp/rentwork
cp $SKILL/state.json $SKILL/state.json.bak
```
Read the skill's SKILL.md, references/sources.md, references/scoring.md.

## 1. Live rate
`curl -s https://open.er-api.com/v6/latest/USD` → rates.THB. Band = 350×rate … 650×rate
THB/month. RATE and TODAY are passed to the scripts as flags below.

## 2. PropertyHub bulk harvest (works via plain HTTP)
```bash
python3 $SKILL/scripts/harvest_propertyhub.py --min <bandlow> --max <bandhigh> --out ph_rows.json
```

## 3. Other portals
Try plain HTTP first (Renthub, FazWaz rentals via fazwaz.co.th/en, thailand-property,
propertyscout, BahtSold). If the subagent/Task tool is available, fan out one agent per area
cluster in references/sources.md, each returning ONLY a JSON array in the SKILL.md schema
(unstated deposit = null), written incrementally to /tmp/rentwork/clusterN.json. If
subagents are unavailable, proceed with what direct harvesting yields — do NOT pad.

## 4. Aggregate, dedupe, score
```bash
python3 $SKILL/scripts/extract.py ...   # if agent outputs need extracting; see its --help
python3 $SKILL/scripts/aggregate.py --rate <rate> --today $(date +%F)   # -> final_rows.json (FINAL_ROWS_OUT env to relocate)
```
It re-verifies filters, dedupes vs state.json, scores per references/scoring.md.

## 5. Build + publish
```bash
python3 $SKILL/scripts/build_artifact.py --rows final_rows.json --out rentals.html \
    --rate <rate> --today $(date +%F)
cp rentals.html $(git -C $SKILL rev-parse --show-toplevel)/docs/rentals.html
```
No xlsx in the cloud (local-only archive). If an Artifact publish tool exists in this
session, also republish the stable page
https://claude.ai/code/artifact/27d3dc1d-6f0a-4732-bdf7-271340054f87 (as `url`); on a
version conflict, WebFetch that URL once (any short prompt) and retry the publish ONCE;
absent or still failing, skip silently — Pages is canonical.

## 6. Commit + push (ALWAYS)
```bash
REPO=$(git -C $SKILL rev-parse --show-toplevel); cd $REPO
git config user.email "routine@bkk-live" && git config user.name "bkk weekly routine"
# append a dated LOG.md entry: rate, counts, top 3, blockers
git add skills/bangkok-rental-research/state.json docs/rentals.html LOG.md
git commit -m "rental scan $(date +%F): <new> new / <total> total @ <rate>"
git push origin HEAD:main || git push origin HEAD:weekly-scan
```
Report: totals, new, top 3 with one-line rationales, move-in-cash caveats where deposits
were stated.
