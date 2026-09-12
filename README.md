# Property Scout — Saigon & Bangkok

Unified responsive web app with buying/renting, shared shortlist, comparison, accent-insensitive search, price/bedroom/area/freshness/ownership filters, source-linked details and CSV export.

Serve `docs/` with a static server. Local preview: http://localhost:3510/. The existing Android wrapper loads this same interface after publication.

Data loads per market and thumbnails are lazy-loaded external files. Saigon purchases and Bangkok purchases/rentals use historical observed records. Saigon rentals show an explicit empty state until real observations exist. Prices use the original snapshot conversion. Source dates and ownership uncertainty stay visible.

`docs/bangkok.html` and `docs/rentals.html` redirect to the corresponding unified view, preserving old entry URLs. Four-city research remains separate.

Refresh reviewed observations with `python3 tools/build_catalog.py --workflows PATH`. Expected folders: hcmc-property-research, bangkok-property-research, bangkok-rental-research; optional hcmc-rental-research. Each contains state.json. Retain data/photo-index.json and images/ for repeat builds. The builder merges identical canonical URLs or FazWaz IDs only within the same city/market, retaining alternative source links. Similar-looking units stay separate.

Tests: `npm test` and `python3 -m unittest discover -s test -v`.

The legacy cloud routines do not automatically rebuild this new catalog. Their status remains unverified. Coordinate publication before scheduling updates. Publication was explicitly authorized on 12 September 2026. Source photos can be low-resolution or unavailable; the app retains the original listing link. Saved homes are local to each device, without cloud sync.
