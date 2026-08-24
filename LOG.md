# LOG.md — cloud run log

## 2026-08-24 — repo seeded (migration from laptop-scheduled tasks)
Seeded from the local skills after the 2026-08-24 local runs: property 1,469 live rows @
32.659832; rentals page of 2026-08-17 (that week's build; the 2026-08-24 local rental run was
still writing its xlsx at migration time). First cloud runs: Monday 2026-08-31.

## 2026-08-24 — property scan ABORTED: no network egress
This run fired (ahead of the planned first-cloud-run date of 2026-08-31) but could not harvest
anything. This session's egress proxy denies every external host with a policy 403 — confirmed
against `open.er-api.com` (live rate), `www.fazwaz.co.th`, `www.thailand-property.com`,
`www.propertyscout.co.th`, and even `www.google.com`, via both `curl` and the `WebFetch` tool
(`EGRESS_BLOCKED`). Only `WebSearch` (Anthropic's own search synthesis, not raw fetch) got
through, and it surfaced a snippet rate of ~32.79 THB/USD — but with FazWaz and every other
portal unreachable there was nothing to harvest, verify, or price against that rate, so no rows
were added or re-scored.
Per the runbook's no-fabrication guardrail, `state.json` (1,469 rows @ 32.659832, last_run
2026-08-24) and `docs/bangkok.html` are left exactly as seeded — rebuilding the page with no
network would have silently dropped every embedded photo (the image cache doesn't exist in
this cloud checkout) for zero new data, which is a worse outcome than leaving last week's page
live. New rows: 0. Total rows: 1,469 (unchanged). Top 3: unchanged from last week's build.
Blocked: FazWaz server-side harvest, all other portals, live-rate curl — all network egress.
Action needed: an admin should check this session's egress allowlist against
`/root/.ccr/README.md`'s "403 / 407 from the proxy" section before the next scheduled run.

## 2026-08-24 — property scan (retry, same day — egress recovered)
Egress was working this run (`open.er-api.com`, FazWaz, and every other portal all returned
200/normal codes) — the prior abort this same day was transient. Full scan per RUN-PROPERTY.md.

**Rate:** 32.659832 THB/USD (live, `open.er-api.com`) → band THB 2,612,787–6,531,966.

**FazWaz server-side harvest:** `fz_search.py` found 2,013 units across 70 search pages (0
errors); `fz_detail.py` fetched 2,010/2,013 detail pages (3 errors: 1×404, 2×non-THB currency
on the dataLayer event); `fz_to_rows.py` kept 602 in-band rows (178 foreign_freehold, 305
leasehold/Thai-only, 119 unknown).

**Subagent fan-out:** all 8 area-cluster/Thai-portal agents completed (cluster1 ran long, ~9
min vs ~6 min for its siblings, but landed) — cluster1 (Lower Sukhumvit/CBD) 7, cluster2 (Upper
Sukhumvit) 11, cluster3 (Riverside/Sathorn/Silom) 8, cluster4 (Ratchada/Rama 9) 12, cluster5
(Ari/Chatuchak) 9, cluster6 (Lat Phrao/NE) 12, cluster7 (Bangna/Rama 4) 14, thai (LivingInsider/
Kaidee/Baania/BahtSold) 10 — 83 raw rows via thailand-property.com, propertyscout.co.th,
propertyhub.in.th, and Kaidee/BahtSold. DDproperty and Hipflat both 403'd as expected (skipped,
not ground on). LivingInsider itself did not yield usable cards this run (the Thai-portals agent
substituted Kaidee/BahtSold coverage instead) — flagged as a partial-source gap, not fabricated.

**Aggregate:** 685 raw candidates (602 FazWaz + 83 subagent) → hard-filter kept 672 (dropped 13
non-Bangkok) → in-run dedup -46 fuzzy → 626 → vs `state.json` master: **60 new**, 566 re-seen (8
matched by fuzzy key), 0 un-parked. FazWaz authoritative override corrected 2 quota values (0
price corrections this run). 0 rows newly parked on the rate move (21 stayed parked from prior
runs).

**Result:** state.json now **1,529 total live rows** (was 1,469) @ rate 32.659832, **60 new**
this run. Quota mix across all live rows: 254 foreign_freehold, 331 leasehold/Thai-only, 944
unknown.

**Top 3 by score:**
1. **93 — Chateau In Town Ratchada 13** (Din Daeng) — $153,093, foreign_freehold confirmed.
   https://www.fazwaz.co.th/en/property-sales/2-bedroom-condo-for-sale-at-chateau-in-town-ratchada-13-in-din-daeng-bangkok-u5370614
2. **92 — Ratchada Orchid** (Huai Khwang) — $97,980, foreign_freehold confirmed.
   https://fazwaz.co.th/en/property-sales/2-bedroom-condo-for-sale-at-ratchada-orchid-in-huai-khwang-bangkok-u6588665
3. **90 — Srivara Mansion** (Din Daeng) — $119,413, foreign_freehold confirmed.
   https://fazwaz.co.th/en/property-sales/2-bedroom-condo-for-sale-at-srivara-mansion-in-din-daeng-bangkok-u5742948

**Page build:** `build_artifact.py` wrote `bangkok.html` (13.09 MB, 1529 rows, thumbnails
1436/1459 ok — the rest 403/404'd off their CDNs, mostly thailand-property.com and
propertyscout.co.th watermark-proxy URLs going stale between search-time and build-time; page
still renders with the fallback state for those cards). Geocoded 1464/1529 (1243 station-level,
221 district-level). Copied to `docs/bangkok.html` for GitHub Pages.

**Stable-artifact republish:** skipped. The Artifact tool refused the publish because the
target's live version had unmerged content from a prior session and this is a headless run with
no user present to confirm a `force` overwrite — per the runbook this is a silent-skip case;
`docs/bangkok.html` on Pages remains canonical.

Blocked/gaps: none blocking. LivingInsider yielded no rows directly this run (noted above,
covered by other Thai C2C sources). Any row with `foreign_freehold: unknown` should be confirmed
with the listing agent before an offer — that is most of the book (944/1,529 live rows), which
matches the known pattern that Thai C2C/portal stock under-states quota rather than most of the
market being genuinely foreign-buyable.
