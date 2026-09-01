# RUN-PROPERTY.md — weekly Bangkok BUY scan (cloud routine runbook)

You are running the **bangkok-property-research** weekly scan headless in a cloud sandbox.
You start with zero context: this file is the complete procedure. The user is not present —
never ask questions; make reasonable choices and record them in the log.

**Goal:** refresh the scored table of Bangkok CONDOMINIUMS a foreigner can legally buy
(USD 80,000–200,000 at this run's live rate, 2+ bedrooms, condominium title only), then
publish `docs/bangkok.html` and push everything back to this repo. The push IS the
deliverable — GitHub Pages serves `docs/` to the user's phone app.

**Guardrails (non-negotiable):** never fabricate listings, prices, photos or quota status.
A thin week is a valid result. This scan researches and ranks only — it never contacts
agents or transacts. When quota is unclear, flag it; don't assume.

## 0. Setup
```bash
cd $(git rev-parse --show-toplevel)
pip install --quiet pillow requests openpyxl
export BKK_SKILL_DIR=$PWD/skills/bangkok-property-research
mkdir -p /tmp/bkkwork && export BKK_WORK_DIR=/tmp/bkkwork && cd /tmp/bkkwork
```
Read `skills/bangkok-property-research/SKILL.md`, `references/sources.md`,
`references/scoring.md`. `state.json` is the dedup master (~1,500 rows). Back it up first:
`cp $BKK_SKILL_DIR/state.json $BKK_SKILL_DIR/state.json.bak`

## 1. Live rate
```bash
curl -s https://open.er-api.com/v6/latest/USD   # -> rates.THB
export BKK_RATE=<that number>  BKK_TODAY=$(date +%F)
```
Band = 80,000×rate … 200,000×rate THB. Use this run's rate for every conversion.

## 2. FazWaz server-side harvest (the bulk of the data — do this FIRST)
```bash
python3 $BKK_SKILL_DIR/scripts/fz_search.py 1 70    # -> fz_units.json (~2,000 units)
python3 $BKK_SKILL_DIR/scripts/fz_detail.py         # -> fz_detail.json (true THB + per-unit ownership; checkpoints every 150, resumable)
python3 $BKK_SKILL_DIR/scripts/fz_to_rows.py        # -> fazwaz.json (in-band rows)
```
The detail script reads the true THB price from each page's dataLayer `property_view` event,
so display-currency issues cannot affect it, and it rejects any page whose currency isn't THB.

## 3. LivingInsider + Thailand-Property server-side harvests (SCRIPTED — do not skip)

Both of these are plain-`urllib` harvests with no browser and no subagent, and between them
they carry more rows than everything else in the run combined. Runs before 2026-09-01 did them
ad hoc or not at all, which is why the cloud master had ~1,000 fewer rows than the local one.

```bash
python3 $BKK_SKILL_DIR/scripts/harvest_livinginsider.py        # -> livinginsider_all.json (~5,700 cards)
python3 $BKK_SKILL_DIR/scripts/harvest_thailand_property.py    # -> thailand_property.json (in-band 2BR+)
```

`harvest_livinginsider.py` writes every card; pre-filter to in-band 2BR+ before aggregating:
```bash
python3 - <<'EOF'
import json, os
RATE=float(os.environ["BKK_RATE"]); LO,HI=round(80000*RATE),round(200000*RATE)
rows=json.load(open("livinginsider_all.json"))
inband=[r for r in rows if r["bedrooms"] and r["bedrooms"]>=2 and r["sqm"] and LO<=r["price_thb"]<=HI]
json.dump(inband,open("livinginsider.json","w"),ensure_ascii=False); print("livinginsider.json",len(inband))
EOF
```

Yields to expect (2026-09-01): LivingInsider 5,751 unique cards -> 677 in-band 2BR+;
Thailand-Property 8,255 unique cards -> 1,681 in-band 2BR+. If either comes back an order of
magnitude below that, something changed on the portal — say so in the log rather than shipping
a quiet under-harvest. Both scripts carry the full parsing gotchas in their docstrings.

## 3b. Other portals (subagent fan-out)
- Try plain HTTP first everywhere (curl/WebFetch): thailand-property.com, propertyscout.co.th,
  propertyhub.in.th work; DDproperty/Hipflat/DotProperty/Baania are WAF-403 to non-browser
  clients — probe once each, don't grind.
- If the subagent/Task tool is available, fan out one agent per area cluster from
  `references/sources.md` (Lower Sukhumvit/CBD, Upper Sukhumvit, Riverside/Sathorn,
  Ratchada/Rama 9, Ari/Chatuchak, Lat Phrao/NE, Bangna/SE + a Thai-portals agent), each
  returning ONLY a JSON array in the SKILL.md schema, written incrementally to
  $BKK_WORK_DIR/clusterN.json. Tell each agent to WRITE its file and reply with a one-line
  count — do not let it paste the JSON back through the conversation. If subagents are
  unavailable, skip — do NOT pad.
- Do NOT assign LivingInsider or Thailand-Property to a subagent: step 3 already harvests both
  far more completely than an agent can, and a duplicate pass just adds fuzzy-dedup work.

Whatever you harvest yourself, write as `$BKK_WORK_DIR/cluster1..7.json` / `thai.json`
in the SKILL.md row schema (missing files are fine — the aggregator tolerates absent inputs).

## 4. Aggregate, dedupe, score
```bash
python3 $BKK_SKILL_DIR/scripts/aggregate.py    # uses BKK_* env; writes final_rows.json + updates state.json
```
This re-verifies the four hard filters, dedupes (link + fuzzy) against the master, applies the
authoritative FazWaz price/quota override from fz_detail.json, parks out-of-band rows on rate
moves, and scores 0–100 per references/scoring.md.

## 5. Build + publish the page
```bash
python3 $BKK_SKILL_DIR/scripts/build_artifact.py --rows final_rows.json \
    --out bangkok.html --width 250 --quality 52 --rate $BKK_RATE --today $BKK_TODAY
cp bangkok.html $(git -C $BKK_SKILL_DIR rev-parse --show-toplevel)/docs/bangkok.html
```
Do NOT build or commit the xlsx in the cloud (30 MB+ per week; it is a local-only archive).
If an Artifact publish tool is available in this session, ALSO republish to the stable
artifact URL https://claude.ai/code/artifact/5dd30dcf-4948-4cf8-bbd4-c19f941d6da5 (pass it as
`url`); if the publish returns a version conflict, WebFetch the artifact URL once (any short prompt) and retry the publish ONCE; if the tool is absent or still errors, skip silently — the Pages copy is canonical.

## 6. Commit + push (ALWAYS, even after a partial run)
```bash
REPO=$(git -C $BKK_SKILL_DIR rev-parse --show-toplevel); cd $REPO
git config user.email "routine@bkk-live" && git config user.name "bkk weekly routine"
# append a dated entry to LOG.md: rate, harvest counts, new vs total rows, top 3 by score
#   (title/score/price/link), and anything that blocked
git add skills/bangkok-property-research/state.json docs/bangkok.html LOG.md
git commit -m "property scan $(date +%F): <new> new / <total> total @ <rate>"
git push origin HEAD:main || git push origin HEAD:weekly-scan
```
A partial run that harvested nothing must still commit the LOG.md entry saying so.
Finish with a short report: total rows, new rows, top 3 picks with one-line rationale each,
and any listing whose foreign-quota status is unknown flagged "confirm with agent".
