# Sources & area clusters (rentals)

Assign **one subagent per cluster** (6–7 agents). Each searches its districts across several portals.

## Area clusters (subagent assignments)

1. **Lower Sukhumvit / CBD** — Asok, Nana, Phrom Phong, Thong Lo, Ekkamai, Ratchathewi, Phaya Thai,
   Victory Monument, Sukhumvit soi 1–63. At this budget expect studios and small 1-beds in older
   low-rise blocks; anything large and cheap here deserves suspicion.
2. **Upper Sukhumvit / value belt** — On Nut, Bang Chak, Punnawithi, Udom Suk, Bearing, Phra Khanong,
   Sukhumvit 64–107, Samrong. The sweet spot for this band: new-ish condos, real 1-beds, on the BTS.
3. **Riverside / Sathorn / Silom / Thonburi side** — Saphan Taksin, Surasak, Chong Nonsi, Sala Daeng,
   Sathorn, Charoen Nakhon, Krung Thonburi, Wongwian Yai, Khlong San, Rama 3, Talat Phlu.
4. **Ratchada / Rama 9 / MRT Blue** — Rama 9, Huai Khwang, Ratchadaphisek, Sutthisan, Din Daeng,
   Makkasan, Phetchaburi, Lat Phrao MRT. Deep rental stock, strong value.
5. **Ari / Phaya Thai / Chatuchak / north** — Ari, Saphan Khwai, Mo Chit, Sanam Pao, Phahon Yothin,
   Ratchayothin, Lat Yao, Kasetsart, Sena Nikhom, Bang Sue.
6. **Lat Phrao / north-east** — Lat Phrao, Chok Chai 4, Wang Thonglang, Bang Kapi, Ramkhamhaeng,
   Hua Mak, Bueng Kum, Bang Khen, Kaset-Nawamin, MRT Yellow corridor. Cheapest large units.
7. **Bangna / south-east + west / old town** — Bang Na, Srinakarin, Nong Bon, Rama 4, Suan Luang,
   Prawet; plus Pinklao, Bangkok Noi, Bang Phlat, Charan, Phasi Charoen, Bang Khae, Phra Nakhon.

## Portals

**Rental-first (prioritise):**
- **Renthub** (renthub.in.th) — the biggest Thai-language rental portal, by far the deepest inventory
  in this band. Search in Thai. Covers apartments and dorm-style blocks as well as condos, so apply
  the "no shared rooms" filter carefully.
- **DDproperty** (ddproperty.com/en/property-for-rent, and the Thai UI at /th) — largest EN inventory.
- **Hipflat** — good per-project rent medians, useful for the value component.
- **Thaiapartment** (thaiapartment.com), **BahtSold** — owner-direct and apartment-block stock.

**General portals with rent sections:**
- **FazWaz** — ⚠️ use `https://www.fazwaz.co.th/en/…`; `fazwaz.com` is Cloudflare-challenged (403
  "Just a moment"). ⚠️ The `.co.th` mirror renders prices in whatever currency the session resolves
  to — it has served **VND** — so confirm a figure is baht before recording it.
- **PropertyScout** (propertyscout.co.th), **PropertyHub** (propertyhub.in.th),
  **Thailand-Property**, **Dot Property** (dotproperty.co.th).
- **LivingInsider** rent boards (livinginsider.com) — reach via the Browser pane, WebFetch DNS-fails.
  Both the sale and rent boards render full card data in the DOM; scrape with
  `a[href*="/detail/"]` and parse `([\d.]+)\s*ตร\.ม\.` plus the ฿ figure. Avoid `async`/`await` in the
  page-eval helper (it times out) — do a plain `scrollTo(0, document.body.scrollHeight)` then scrape.
- **Baania**, **TerraBKK**, **ThinkOfLiving** — Thai analytics, useful for building age/quality.
- ~~Prakard~~ — defunct since 2026-07, skip.

## Search-query patterns
- `<district> Bangkok condo for rent 12000-21000 THB`
- `site:renthub.in.th <ย่าน> เช่า`, `คอนโดให้เช่า <ย่าน> <ราคา> บาท`, `ห้องเช่า <ย่าน>`,
  `อพาร์ตเมนต์ให้เช่า <ย่าน>`
- `ddproperty <district> condo for rent near BTS`
- On a listing page, read: monthly rent, size m², bedrooms (studio = 0), floor, furnishing,
  **deposit and advance months**, minimum lease, pets, availability date, and the primary image URL.

## Extraction notes
- The **direct image URL** is usually `<meta property="og:image">` or the first gallery `<img src>`.
- Strip everything after `?` for a stable canonical `link`.
- Rent may be written `฿15,000`, `15000 บาท/เดือน`, or `15K`. Normalise to integer THB per month.
- **Deposit is the field portals most often omit.** Leave it null rather than filling in the 2+1 norm;
  the score treats unknown as neutral precisely so silence is not rewarded.
- Watch for the same unit posted by several agents at slightly different rents — that is a real
  cross-portal duplicate, and the lowest quoted rent is the negotiating floor worth recording.
