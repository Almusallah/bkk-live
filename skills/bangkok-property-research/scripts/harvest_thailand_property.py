#!/usr/bin/env python3
"""Thailand-Property server-side harvest -> thailand_property.json

Recipe proven 2026-08-31 (v9), scripted 2026-09-01 (v10). Curls cleanly (200)
with a desktop UA — the single most reliable EN portal in the set.

  * ?min_price=&max_price= (THB) IS honoured server-side. Push the buy-box down.
  * ?bedroom=2 is NOT honoured as a QUERY param — but the bedroom facet exists
    as a PATH: /condos-for-sale/bangkok/2-bedrooms (also /3-bedrooms, /4-bedrooms).
    Use those; still re-check beds client-side.
  * Any single result set caps at ~1,200 rows (~48 pages of 25). Harvesting only
    the flat /bangkok path therefore returns mostly 1-beds and yields ~135 in-band
    rows. Fan across the bedroom + district facet paths to get past the cap.
  * Each listing URL appears ~3x per card; ONLY the segment containing
    class="price" carries the data. Key by URL and keep that segment.
  * Size is `35 m<sup>2</sup>` — a regex for m²|sqm misses ~60% of rows.
  * Images live on img.thailand-property.com in the PRECEDING (gallery) segment.
  * NO listing on this portal states foreign quota. Every row is honestly
    `unknown` — do not infer.
  * It syndicates FazWaz stock, so expect heavy fuzzy overlap in aggregate.py.
"""
import concurrent.futures as cf, json, os, re, sys, urllib.request

RATE = float(os.environ.get("BKK_RATE") or 0)
if not RATE:
    sys.exit("BKK_RATE not set")
LO, HI = round(80000 * RATE), round(200000 * RATE)
MAXPAGE = int(os.environ.get("TP_MAXPAGE") or 140)
BASE = "https://www.thailand-property.com/condos-for-sale/bangkok"
# Facet paths appended to BASE. Each result set caps at ~1,200 rows, so the
# bedroom facets (which is where the buy-box lives) must be harvested separately
# from the flat path. District slugs are listed on the un-filtered Bangkok page.
FACETS = ["", "/2-bedrooms", "/3-bedrooms", "/4-bedrooms",
          "/bang-rak", "/chatuchak", "/huai-khwang", "/khlong-toei",
          "/pathum-wan", "/ratchathewi", "/sathon", "/watthana"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
SPLIT = 'href="https://www.thailand-property.com/ads/'

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as f:
        return f.read().decode("utf-8", "ignore")

def parse_page(job):
    facet, n = job
    url = f"{BASE}{facet}?min_price={LO}&max_price={HI}&page={n}"
    try: h = get(url)
    except Exception as e:
        if "404" not in str(e):
            print(f"  !! {facet or '/'} page {n}: {e}", file=sys.stderr)
        return []
    segs = h.split(SPLIT)
    out = []
    for i, s in enumerate(segs[1:], start=1):
        if 'class="price"' not in s: continue
        slug = s.split('"', 1)[0]
        link = "https://www.thailand-property.com/ads/" + slug
        pm = re.search(r'class="price">\s*฿\s*([\d,]+)', s)
        if not pm: continue
        price = int(pm.group(1).replace(",", ""))
        bm = re.search(r'icon-bedroom"></i>\s*<span>(\d+)</span>', s)
        beds = int(bm.group(1)) if bm else None
        if beds is None:
            sm = re.match(r"(\d+)-bedroom", slug)
            beds = int(sm.group(1)) if sm else None
        am = re.search(r"([\d.]+)\s*m\s*<sup>\s*2", s)
        sqm = float(am.group(1)) if am else None
        nm = re.search(r'<h3 class="name">\s*(.*?)\s*</h3>', s, re.S)
        headline = re.sub(r"\s+", " ", nm.group(1)).strip() if nm else None
        lm = re.search(r'fa-map-marker"></i>\s*<small>\s*(.*?)\s*</small>', s, re.S)
        loc = re.sub(r"\s+", " ", lm.group(1)).strip() if lm else None
        tm = re.search(r'icon-subway"></span>\s*<small>\s*(.*?)\s*</small>', s, re.S)
        station = re.sub(r"\s+", " ", tm.group(1)).strip() if tm else None
        # title from the URL slug is stable; the h3 is the seller's headline
        title = " ".join(w.capitalize() for w in
                         re.sub(r"^\d+-bedroom-condo-for-sale-in-", "", slug.split("_")[0])
                         .replace("-near-bts", " near BTS").replace("-near-mrt", " near MRT")
                         .split("-") if w)
        im = re.search(r"(https://img\.thailand-property\.com/[^\s\"']+)", segs[i - 1])
        notes = []
        if headline: notes.append(headline)
        notes.append("Thailand-Property states no ownership/quota field on any listing "
                     "(verified v8+v9) — quota genuinely unknown, confirm with agent")
        out.append({"title": title or headline, "district": loc, "position": station,
                    "price_thb": price, "sqm": sqm, "bedrooms": beds,
                    "foreign_freehold": "unknown", "link": link,
                    "image_url": im.group(1) if im else None,
                    "source": "thailand-property", "notes": " | ".join(notes)})
    return out

def main():
    by_link = {}
    for facet in FACETS:
        before = len(by_link)
        jobs = [(facet, n) for n in range(1, MAXPAGE + 1)]
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            for res in ex.map(parse_page, jobs):
                for r in res: by_link.setdefault(r["link"], r)
        print(f"  {facet or '(all)':<14} +{len(by_link)-before:<5} unique (total {len(by_link)})")
    rows = list(by_link.values())
    json.dump(rows, open("thailand_property_all.json", "w"), ensure_ascii=False)
    inband = [r for r in rows if r["bedrooms"] and r["bedrooms"] >= 2
              and r["sqm"] and LO <= r["price_thb"] <= HI]
    json.dump(inband, open("thailand_property.json", "w"), ensure_ascii=False)
    print(f"thailand-property: {len(rows)} unique cards -> {len(inband)} in-band 2BR+ "
          f"(band ฿{LO:,}-฿{HI:,})")

if __name__ == "__main__":
    main()
