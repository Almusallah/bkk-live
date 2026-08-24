# bkk-live

Weekly Bangkok property scans, run **laptop-off** by two Claude Code cloud routines:

| Routine | Runbook | Output | Schedule (ICT) |
|---|---|---|---|
| bkk-property-weekly | `RUN-PROPERTY.md` | `docs/bangkok.html` | Mon 08:00 |
| bkk-rental-weekly | `RUN-RENTAL.md` | `docs/rentals.html` | Mon 11:00 |

`docs/` is served by GitHub Pages → https://almusallah.github.io/bkk-live/ — which is what
the **BKK Scout** Android app (repo `bkk-app`) displays. `skills/` holds the scan scripts,
references and the dedup master (`state.json`) that each run updates and pushes back.

Data = aggregated public listings; nothing sensitive lives here. The xlsx archives stay
local-only (too big for weekly commits).
