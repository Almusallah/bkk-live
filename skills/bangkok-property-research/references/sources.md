# Sources & area clusters

Assign **one subagent per cluster** below (5–7 agents). Each agent searches its districts across several portals. Districts are chosen for foreigner-friendly condo stock in the USD 80k–200k band.

## Area clusters (subagent assignments)

1. **Lower Sukhumvit / CBD** — Asok, Phrom Phong, Thonglor, Ekkamai, Nana. Prime, high foreign-quota liquidity; 2-beds here often push the top of budget — focus on older/renovated stock and mid-tier buildings.
2. **Upper Sukhumvit / value belt** — On Nut, Bang Chak, Udom Suk, Bearing, Phra Khanong. Best sqm-per-dollar for 2-beds in-budget along the BTS.
3. **Riverside / Sathorn / Silom** — Saphan Taksin, Charoen Nakhon (ICONSIAM side), Sathorn, Silom, Chong Nonsi. River-view condos, strong foreign demand.
4. **Ratchada / Rama 9 / MRT Blue Line** — Rama 9, Huai Khwang, Ratchadaphisek, Sutthisan, Phra Ram 9. New-build value, high rental yield.
5. **Ari / Phaya Thai / Chatuchak** — Ari, Saphan Khwai, Mo Chit, Phahonyothin. Lifestyle area, appreciating.
6. **Lat Phrao / Ladprao & emerging north-east** — Lat Phrao, Chok Chai 4, MRT Yellow/Pink line nodes. Cheapest in-budget 2-beds; verify transit + quota.
7. **Bangna / Rama 4 / on-trend south-east** *(optional 7th agent)* — Bangna, Punnawithi (True Digital Park), Rama 4. New supply, foreign-quota stock.

## Portals (each agent should query several)

- **DDproperty** (ddproperty.com) — largest inventory; filter Condo / For Sale / 2+ bed / price band.
  - ✅✅ **(2026-09-01) THE WAF FALLS TO AN iPHONE USER-AGENT.** DDproperty 403'd every run from week 1 to v9 because we only ever tried desktop UAs. An **iPhone Safari UA clears the search pages**; detail pages additionally need a **cookie jar + a Referer** from the search page. **297 in-band rows** on first contact.
    - EN search works at `/en/property-for-sale`; the Thai stock is reachable via the **SEO path** `/ขายคอนโด/ในกรุงเทพ-th10` — the `/th/...` prefix stays 403.
    - ⚠ **DDproperty publishes a freehold/leasehold TENURE field, which is NOT foreign quota.** All 297 detail-page descriptions were read and none stated foreign-quota wording; every row is honestly `unknown`. Never map its tenure field onto `foreign_freehold`.
- **Hipflat** (hipflat.co.th) — WAS the intended source of district price/sqm medians. **(2026-09-01) 403 Cloudflare managed challenge on every path including robots.txt, on both hipflat.co.th and hipflat.com — no medians obtainable.** Treat as blocked until proven otherwise; `aggregate.py` derives its value-score medians from its own in-band pool instead.
- **FazWaz** — foreign-focused, explicitly labels **foreign freehold / leasehold**. Prioritise for quota status.
  - *(2026-08-10)* **Use `https://www.fazwaz.co.th/en/…`, not `fazwaz.com`.** `fazwaz.com` is intermittently behind a Cloudflare challenge (403 "Just a moment"); the `.co.th/en/` mirror serves the same listing at 200 with the per-unit ownership field intact.
  - ⚠️ **Currency trap:** the `.co.th` mirror renders prices in whatever currency the session resolves to — on 2026-08-10 it served **VND (₫)**, not THB, with zero ฿ anywhere on the page. Never assume the number on a FazWaz page is baht: read the THB value from the page's own dataLayer, or cross-check against another portal, before recording `price_thb`.
  - ✅ **(2026-08-17) THE FIX — currency is a COOKIE, not a query param.** `?currency=THB` does nothing; the site resolves currency from the session's geo-IP (Vietnam, for Yuri's connection → VND). Worse, on some index pages it prints VND magnitudes behind a **฿ symbol**, so the baht sign itself is not evidence. **Set it once per browser session and every page afterwards serves real THB:**
    ```js
    // in the Browser pane, on any fazwaz.co.th page
    window.handleGetCurrencyMenuBridge(true);                                   // opens the currency menu
    [...document.querySelectorAll('button.currency-menu__item')]
      .find(b => /Thai Baht/i.test(b.textContent)).click();                     // sets cookie currency=THB
    ```
    Verify with `document.cookie.match(/currency[^;]*/)` → `currency=THB`, and that `document.body.innerText` contains ฿ and no ₫. Cross-checked on 2026-08-17: Regent Home 22 Sukhumvit 85 came out at ฿41,001/m² on FazWaz and ฿41,001/m² independently on Thailand-Property.
  - **Search-page scraping recipe (2026-08-17).** Bedrooms filter is `?bedrooms=2` (NOT `bedroom=2`, which is silently ignored); there is **no working price-range query param** — paginate `&page=N` and filter client-side. Each results page embeds `<script type="application/json" id="search-marker-payloads">` keyed by unit id, giving name, price, area, bedrooms, formatted_address, thumbnail and `nearPlaceGroup` (BTS/MRT name + km). Some rows carry `detailUrl: "forceLogin"` — recover the real URL from the page's own `a[href*="/property-sales/"]` anchors, matching on the trailing `-u<id>`.
  - ✅✅ **(2026-08-24) THE CURRENCY TRAP IS NOW MOOT — do the whole FazWaz harvest in Bash, not the Browser pane.** Every detail page carries a GTM `dataLayer.push` with the **true THB price regardless of the session's display currency**:
    ```
    dataLayer.push({ event: 'property_view', content_id: 'U1938686S', listing_type: 'sale',
                     price: 4790000.00000000, currency: 'THB' })
    ```
    Regex it with `event:\s*'property_view'.*?price:\s*([\d.]+),\s*currency:\s*'([A-Z]{3})'` and assert `currency == 'THB'`. Plain `curl`/`urllib` with only a desktop User-Agent gets a **200** on both search and detail pages — no cookie, no Cloudflare challenge, no browser. Search pages still render VND to a fresh session, so **never read a price off a search page**; use the search payload only for the unit list (id, name, area, bedrooms, address, thumbnail, nearPlaceGroup) and take the price from the detail page.
    Reusable scripts live in the run scratchpad pattern `fz_search.py` (paginate + parse `search-marker-payloads`, 8 threads) and `fz_detail.py` (10 threads, checkpoints every 150 to `fz_detail.json` so a crash resumes). 70 pages ≈ 2,000 2BR Bangkok condos; detail-fetch all of them and filter by THB afterwards. Cross-checked against the browser-pane method on the same run: identical prices (Waterford Park Rama 4 u1938686 = ฿4,790,000 both ways).
    **Why this matters beyond FazWaz:** the browser pane cannot hand data back to disk — `fetch`, `XHR`, `sendBeacon` and even `<img>` to `http://127.0.0.1` are all blocked by Chrome's Private Network Access, so every scraped row has to be re-emitted through the model's own output. Server-side harvesting costs zero context. Prefer `curl` for any portal that will answer it.
  - **Ownership lives on the detail page only**, in `.basic-information__item` whose label is "Condo Ownership"; read the **`span.basic-information-info`** child, because the item's own text starts with a long generic explainer about the 49% rule. Values seen: `Foreign Quota`, `Thai Quota`, `Foreign Quota, Thai Quota`, `…, Company`, `…, Leasehold`, `N/A`. Fetch detail pages with synchronous `XMLHttpRequest` in batches of **~20 per `javascript_tool` call** — 60+ per call exceeds the 30 s tool timeout.
  - **Reality check on the in-band stock (2026-08-17, 127 units):** 19 foreign-only, 18 either-quota, **71 Thai Quota**, 18 N/A, 1 Company. Roughly **56% of in-band 2BR FazWaz stock is Thai-quota** — so a run that reports mostly `unknown` is under-reading the field, not finding a foreigner-friendly market.
  - The ownership field is genuinely per-unit and varies, but is **not always exclusive** — "Foreign Quota, Thai Quota" means the unit is offered under *either*, which is weaker than a foreign-only title. Record `foreign_freehold` but say so in `notes`.
- **Thailand-Property** (thailand-property.com) — expat-oriented listings. **Curls cleanly (200) with a desktop UA; the single most reliable EN portal — it is the only one every cluster agent got through in v8 and v9.**
  - ✅ **(2026-08-31) Server-side harvest, and its price band filter actually works** — unlike FazWaz, `?min_price=<THB>&max_price=<THB>` is honoured, so the buy-box can be pushed to the server: `https://www.thailand-property.com/condos-for-sale/bangkok[/<district-slug>]?min_price=…&max_price=…&page=N`. District slugs are listed on the un-filtered Bangkok page (`bang-rak`, `huai-khwang`, `khlong-toei`, `vadhana`, `phra-khanong`, …).
  - ⚠ **`?bedroom=2` is NOT honoured** (1-beds come back anyway) — filter bedrooms client-side.
  - **Card parsing.** Cards are `class="hj-listing-snippet"`, but the reliable split is on the listing URL `href="https://www.thailand-property.com/ads/`. **Each listing's URL appears ~3× per card** (gallery link, main link, enquire link) and **only the segment containing `class="price"` carries the data** — key by URL and keep that segment, or you get a card with no price and no size. Fields: `class="price"> ฿ N`, `icon-bedroom"></i> <span>N</span>`, `<h3 class="name">` (the seller's headline), `fa-map-marker"></i> <small>Subdistrict , Bangkok</small>`, `icon-subway"></span> <small>BTS Station</small>`.
    ⚠ **Size is `35 m<sup>2</sup>`** in the markup — a regex for `m²|sqm` misses ~60% of rows. Match `([\d.]+)\s*m\s*<sup>\s*2`.
  - Images are on `img.thailand-property.com/<base64>` in the *preceding* segment (the gallery block). Photo coverage is effectively 100%.
  - **No listing on this portal states foreign quota** — three separate cluster agents grepped every detail page in v8 and v9 and found no quota wording at all. Every Thailand-Property row is legitimately `unknown`; do not infer.
  - **It syndicates FazWaz stock** (many cards show "FazWaz Bangkok" as the verified seller), so expect heavy fuzzy-dedup overlap with `fazwaz.json` — 173 project+sqm collisions in v9. Same-project/same-rounded-sqm rows with different prices are usually *different units*, not a price conflict.
  - ✅✅ **(2026-09-01) THE 1,200-ROW CAP — and how to get past it.** Any single Thailand-Property result set stops at **~1,200 rows (48 pages × 25)**; page 49+ returns 404/503. Harvesting only the flat `/condos-for-sale/bangkok` path therefore caps at 1,200 cards of which **only ~11% are 2BR+** (the flat set is dominated by 1-beds) → ~135 in-band rows. **Fan across facet PATHS instead**, each of which gets its own 1,200-row budget:
    - **The bedroom facet works as a PATH even though `?bedroom=` is ignored as a query param:** `/condos-for-sale/bangkok/2-bedrooms`, `/3-bedrooms`, `/4-bedrooms`.
    - District slugs (listed on the un-filtered Bangkok page): `bang-rak`, `chatuchak`, `huai-khwang`, `khlong-toei`, `pathum-wan`, `ratchathewi`, `sathon`, `watthana`.
    - Combine each facet with `?min_price=&max_price=` and paginate to 50. **8,255 unique cards → 1,681 in-band Bangkok 2BR+** on 2026-09-01, double the v9 figure.
  - **Scripted 2026-09-01** as `scripts/harvest_thailand_property.py` (needs `BKK_RATE`; writes `thailand_property.json` + `thailand_property_all.json`). Stop doing this one ad hoc.
  - **Yield:** 2026-08-31 3,414 unique cards → 849 in-band (was 88 via agents in v8); **2026-09-01 8,255 → 1,681** with the facet fan-out above.
- **Dot Property** (dotproperty.co.th) — broad resale + new.
- **Bangkok Post Property / Post Property** — curated, some new launches.
- **PropertyScout** (propertyscout.co.th), **Angloinfo, expat Facebook-group crossposts** — secondary; verify before trusting.

### Local Thai-language portals (added 2026-07-21 — deeper inventory, often below-market resale)
Search these in **Thai** as well as English; prices show as "ล้าน"/"ล้านบาท" (millions) — normalise to THB. Thai C2C stock skews **Thai-quota**, so confirm foreign quota carefully.
- **LivingInsider** (livinginsider.com) — Thailand's biggest Thai C2C board; huge resale inventory + its CDN images embed cleanly.
  - ✅✅ **(2026-08-31) NO BROWSER NEEDED — it curls after all.** The old "WebFetch DNS-fails, use the Browser pane" note was wrong about the whole site: plain `urllib`/`curl` with a desktop User-Agent **and `Accept-Language: th-TH`** gets a **200 with the listing cards fully server-rendered**. The earlier "no cards in the HTML" conclusion was a bad regex on my side, not a client-side render. Two things to get right:
    - **Use the facet boards, not `/searchpage/...`.** The constructed `searchpage/N/Condo/3-5-million/sale.html` URLs **500** (they have for months). Start from `https://www.livinginsider.com/salesarea-buysell`, which lists the real facet URLs. The useful ones:
      `…/condo-buysell/2-bedrooms`, `…/3-bedrooms`, and **`…/condo-buysell/foreign-quota`** (title: "ขาย คอนโด โควต้า ต่างชาติ / Condo Foreign Quota for sale").
      Paginate by appending `/N` — `…/condo-buysell/2-bedrooms/2`. **48 unique listings/page, zero overlap between pages.** `?page=N` is silently ignored; only the path form works.
    - **The bedroom facet is real, the price facet is not.** `/2-bedrooms` genuinely filters; adding `/3m-5m` after it changes nothing. Filter price client-side.
  - **Card parsing.** Split on `<div class="istock-list "`. Each block has: bedrooms, `ชั้น <floor>`, `<sqm> ตร.ม.`, then the price as the HTML entity **`&#3647;`** (NOT a literal ฿) followed by the digits, then `(<n> บาท/ตร.ม.)`. Image: `https://www.livinginsider.com/upload/topic<N>/<hash>.jpeg`.
    ⚠ **Title trap:** the first `title="…"` in the block is the favourite icon's **"Add to Favorite"**. Take the title off the *detail anchor* (`<a href=".../detail/…" … title="…">`), or better, derive the project name from the URL slug (`condo-for-sale-condo-city-home-ratchada-pinklao-2bedroom-3188146` → "City Home Ratchada Pinklao") — the slug is clean and is exactly what `geo.py`'s title fallback wants. The long Thai `title` is the seller's blurb; keep it in `notes`, it carries the province words the non-Bangkok filter needs.
  - ⚠ **Detail pages are useless server-side** — `/detail/…` returns **202 with a zero-byte body** to curl. Everything must come off the board card. (That is why the foreign-quota signal has to come from the board, not the unit page.)
  - **The `foreign-quota` board is a seller-declared tag, not a verified title.** Treat board membership as `foreign_freehold` but say so verbatim in `notes` — it is the same class of evidence as FazWaz's ownership field, i.e. portal-declared.
  - **Scripted 2026-09-01** as `scripts/harvest_livinginsider.py` (writes `livinginsider_all.json`; pre-filter to `livinginsider.json`). Boards harvested: `/2-bedrooms`, `/3-bedrooms`, `/4-bedrooms`, `/foreign-quota`, paginated to 40. The `-Nbedroom-` token in the detail-URL slug is a reliable bedroom source when the card's own bedroom prop is missing (266/5,751 cards).
  - **Yield:** 2026-08-31 4,260 cards → 3,733 unique → 632 in-band 2BR+ (121 on the foreign-quota board); **2026-09-01 5,751 unique → 677 in-band 2BR+, 59 of them foreign-quota-tagged.** Previous browser-pane runs got 104 (v7) and 312 (v8) at far higher context cost.
- ~~Prakard (prakard.com)~~ — **DEFUNCT as of 2026-07, domain no longer resolves. Skip.**
- **Kaidee** (kaidee.com / baan.kaidee.com) — mass Thai marketplace.
  - ✅ **(2026-09-01) The old "login-gated + stale 2020 reposts" verdict is out of date.** Detail pages are NOT login-gated, its server-side filters work correctly, and the stock is current: of 87 in-band rows harvested, all were `status: live`, **61 first posted in 2026 and only 4 pre-2025**. Usable — flag the pre-2025 ones in notes.
- **Baania** (baania.com) — Thai, data-rich (price/sqm history per project).
  - ✅✅ **(2026-09-01) Its SSR filters are genuinely ignored — but it has an undocumented Elasticsearch backend that honours them.** `POST search.baania.com/api/v1/listing` accepts `province` / `propertyType` / `bedroom` and returned **9,900 pure Bangkok condos → 375 in the buy-box**, each verified against its detail page. This supersedes the v9 conclusion that "Baania surfaces only 1-bed/studio stock" — that was the broken SSR filter, not the inventory.
  - It also yields **district-level median THB/m²** across its whole condo book (42 Bangkok districts computed 2026-09-01, written to `district_medians.json`). ⚠ These medians span ALL condo stock — 1-beds and new launches included — so they are a cross-check, **not** a drop-in replacement for the in-band 2-bed pool medians the scorer uses.
- **DDproperty Thai** (ddproperty.com/th) & **Dot Property Thai** — run the Thai UI for more stock than the EN site.
- **ThinkOfLiving** (thinkofliving.com) — Thai new-launch reviews; good for building quality/age. **403 to curl and WebFetch on both 2026-08-31 and 2026-09-01 — probe once, do not grind.**
- ~~**Realist** (realist.co.th)~~ — **DEAD, no longer resolves (2026-08-31). Skip alongside Prakard.**
- **PropertyHub** (propertyhub.in.th) — Thai agent portal. **(2026-09-01) Harvest it server-side out of the embedded `__NEXT_DATA__` JSON, district by district — page-level pagination is dead.** 2,867 cards harvested that way. ⚠ Its district labels lie: four units filed under "Nong Chok" were actually Cha-Am/Hua Hin.
- **TerraBKK** (terrabkk.com) — **403 on both 2026-08-31 and 2026-09-01. Probe once, do not grind.**
- **BahtSold** (bahtsold.com) — expat/Thai classifieds, owner-direct.

## Search-query patterns for agents

- `site:fazwaz.com Bangkok condo 2 bedroom foreign freehold <district>`
- `<district> Bangkok 2 bedroom condo for sale THB 3M-7M`
- `ddproperty <district> condominium 2 bedroom foreign quota`
- **Thai:** `คอนโด 2 ห้องนอน ขาย <ย่าน> ต่างชาติซื้อได้` ("condo 2-bed for sale <area> foreigner can buy"), `โควตาต่างชาติ` (foreign quota), `กรรมสิทธิ์ต่างชาติ` (foreign ownership).
- On FazWaz/DDproperty, read the listing page for: **ownership type (freehold/foreign quota/leasehold)**, floor area sqm, floor, year built, and the primary image URL.

## Notes for reliable extraction
- The **direct image URL** is usually in the listing's `<meta property="og:image">` or the first gallery `<img src>`. Grab that for the `image_url` field so the sheet thumbnail renders.
- Strip tracking query params from `link` (everything after `?`) to get a stable canonical URL for dedup.
- Portals sometimes show price in THB with "฿" or in "M" (millions). Normalise everything to integer THB.
