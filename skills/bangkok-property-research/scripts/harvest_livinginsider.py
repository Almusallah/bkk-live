#!/usr/bin/env python3
"""LivingInsider server-side harvest -> livinginsider.json

Recipe proven 2026-08-31 (v9), scripted 2026-09-01 (v10). No browser needed:
plain urllib with a desktop UA + Accept-Language: th-TH returns fully
server-rendered listing cards.

  * Use the FACET boards, not /searchpage/... (which 500s).
  * Paginate by appending /N to the board path; ?page=N is silently ignored.
  * 48 listings/page, zero overlap between pages.
  * The bedroom facet filters for real; the price facet does not.
  * Detail pages return 202 with a zero-byte body -> everything off the card.
  * Title trap: the first title= in a block is the favourite icon's
    "Add to Favorite". Derive the project name from the URL slug instead.
  * The foreign-quota board is a SELLER-DECLARED tag, not a verified title.
"""
import concurrent.futures as cf, json, os, re, sys, urllib.request

BASE = "https://www.livinginsider.com/condo-buysell"
BOARDS = [("2-bedrooms", None), ("3-bedrooms", None), ("4-bedrooms", None),
          ("foreign-quota", "foreign_freehold")]
MAXPAGE = int(os.environ.get("LI_MAXPAGE") or 40)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "th-TH,th;q=0.9,en;q=0.8"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as f:
        return f.read().decode("utf-8", "ignore")

SLUG_TITLE = re.compile(r"/detail/(?:condo|apartment)-for-(?:sale|rent)-(?:condo-)?(.+?)-(\d+)$")

def parse_block(b, quota):
    m = re.search(r'href="(https://www\.livinginsider\.com/detail/[^"]+)"', b)
    if not m: return None
    link = m.group(1)
    sm = SLUG_TITLE.search(link)
    slug = sm.group(1) if sm else ""
    beds = None
    bm = re.search(r"-(\d+)bedroom", slug)
    if bm: beds = int(bm.group(1))
    slug_clean = re.sub(r"-\d+bedroom.*$", "", slug)
    title = " ".join(w.capitalize() for w in slug_clean.split("-") if w)
    pm = re.search(r'text_price"><span>&#3647;</span>\s*([\d,]+)', b)
    if not pm: return None
    price = int(pm.group(1).replace(",", ""))
    am = re.search(r"([\d,.]+)\s*ตร\.ม\.", b)
    sqm = float(am.group(1).replace(",", "")) if am else None
    fm = re.search(r"ชั้น\s*</span>?\s*([\d\-]+)", b) or re.search(r"ชั้น\s+([\d\-]+)", b)
    floor = fm.group(1) if fm else None
    im = re.search(r"(https://www\.livinginsider\.com/upload/topic\d+/[0-9a-f]+\.(?:jpeg|jpg|png))", b)
    # the seller's Thai blurb carries the province words the non-Bangkok filter needs
    tm = re.findall(r'/detail/[^"]+"[^>]*title="([^"]*)"', b)
    blurb = tm[0].strip() if tm else ""
    notes = []
    if floor: notes.append(f"floor {floor}")
    if quota:
        notes.append('on LivingInsider\'s "ขาย คอนโด โควต้า ต่างชาติ / Condo Foreign Quota for sale" '
                     "board — SELLER-DECLARED tag, not a verified chanote; confirm with agent")
    if blurb: notes.append(blurb)
    return {"title": title or None, "district": None, "position": None,
            "price_thb": price, "sqm": sqm, "bedrooms": beds,
            "foreign_freehold": quota or "unknown", "link": link,
            "image_url": im.group(1) if im else None, "source": "livinginsider",
            "notes": " | ".join(notes) or None}

def board_page(args):
    board, quota, n = args
    url = f"{BASE}/{board}" + (f"/{n}" if n > 1 else "")
    try: h = get(url)
    except Exception as e:
        print(f"  !! {board}/{n}: {e}", file=sys.stderr); return []
    out = []
    for b in h.split('<div class="istock-list ')[1:]:
        try:
            r = parse_block(b, quota)
            if r: out.append(r)
        except Exception: pass
    return out

def main():
    seen, rows = set(), []
    for board, quota in BOARDS:
        jobs = [(board, quota, n) for n in range(1, MAXPAGE + 1)]
        got = 0
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            for res in ex.map(board_page, jobs):
                for r in res:
                    if r["link"] in seen: continue
                    seen.add(r["link"]); rows.append(r); got += 1
        print(f"  {board}: +{got} unique (total {len(rows)})")
    json.dump(rows, open("livinginsider_all.json", "w"), ensure_ascii=False)
    print(f"livinginsider: {len(rows)} unique cards -> livinginsider_all.json")
    print("  (band/bedroom/geography filtering is aggregate.py's job)")

if __name__ == "__main__":
    main()
