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
- **Hipflat** (hipflat.co.th) — good price/sqm analytics per project; useful for area medians.
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
- **Thailand-Property** (thailand-property.com) — expat-oriented listings.
- **Dot Property** (dotproperty.co.th) — broad resale + new.
- **Bangkok Post Property / Post Property** — curated, some new launches.
- **PropertyScout** (propertyscout.co.th), **Angloinfo, expat Facebook-group crossposts** — secondary; verify before trusting.

### Local Thai-language portals (added 2026-07-21 — deeper inventory, often below-market resale)
Search these in **Thai** as well as English; prices show as "ล้าน"/"ล้านบาท" (millions) — normalise to THB. Thai C2C stock skews **Thai-quota**, so confirm foreign quota carefully.
- **LivingInsider** (livinginsider.com) — Thailand's biggest Thai C2C board; huge resale inventory + its CDN images embed cleanly. **Note: WebFetch DNS-fails on it — reach it via the Browser pane (read_page DOM).** Query: `livinginsider คอนโด 2 ห้องนอน ขาย <district>`.
  - *(2026-08-10)* Much richer than in v4/v5 — **31 usable Bangkok rows this run vs 4**. Both the 3–5M *and* the 5–10M sale boards now render full card data (price, sqm, beds, floor, image `src`) in the DOM, so the older "5–10M is titles-only" note no longer holds. Pages 3–4 of the 3–5M board are far denser than pages 1–2, which are dominated by bumped **Nonthaburi/Rattanathibet** stock — drop those, they are not Bangkok province. Card text parses cleanly with `/([\d.]+)\s*ตร\.ม\.\s*฿([\d,]+)/`. Avoid `async`/`await` loops in the page-eval helper: they time out; do a plain `scrollTo(0, document.body.scrollHeight)` then scrape synchronously.
  - *(2026-07-27)* The site 500s on many deep/constructed URLs. Reliable path: load `https://www.livinginsider.com/` then follow its own price-band links. The **3–5M sale board** renders full card data (price, sqm, beds, floor, image `src`) in the DOM; the **5–10M board** renders titles only, so it needs per-listing visits. Scrape cards with JS (`a[href*="/detail/"]`, walk up to the card, read `innerText` + nested `img.src`) — the `img` nearest the anchor can be a favourite-icon SVG, so walk parents until a real `/upload/topic*/` URL appears. Boards are sorted by "bumped", not by district, so filter by `2bedroom` in the href and drop non-Bangkok results (Khu Khot, Chiang Mai, Cha-am, Pak Chong all appear).
- ~~Prakard (prakard.com)~~ — **DEFUNCT as of 2026-07, domain no longer resolves. Skip.**
- **Kaidee** (kaidee.com / baan.kaidee.com) — mass Thai marketplace; but detail pages are login-gated and much stock is **stale 2020 reposts** (images 404). Low signal — use sparingly.
- **Baania** (baania.com) — Thai, data-rich (price/sqm history per project).
- **DDproperty Thai** (ddproperty.com/th) & **Dot Property Thai** — run the Thai UI for more stock than the EN site.
- **ThinkOfLiving** (thinkofliving.com) — Thai new-launch reviews; good for building quality/age.
- **Realist** (realist.co.th), **PropertyHub** (propertyhub.in.th), **TerraBKK** (terrabkk.com) — Thai analytics + listings.
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
