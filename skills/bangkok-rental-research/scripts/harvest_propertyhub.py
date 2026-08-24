#!/usr/bin/env python3
"""
Systematic PropertyHub rental harvest.

Agent free-text search only ever samples a portal. PropertyHub alone advertises ~139k
Bangkok rentals, so searching it by hand was never going to be representative. Every
zone page (district, BTS/MRT station, road, area) embeds a __NEXT_DATA__ blob carrying
60 fully-structured listings plus links to neighbouring zones — so we crawl the zone
graph and take each zone's page instead.

Known limit, stated rather than hidden: server-side pagination is not reachable
(?page/​/page/N/_next-data all fail), so we get the FIRST 60 listings per zone and the
site puts sponsored listings first. The union over ~100 zones is far broader than a
hand search, but it is a wide sample, not a census. `harvest_note` records this.

    python3 harvest_propertyhub.py --min 11604 --max 21551 --out ph_rows.json [--zones 120]
"""
import argparse, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125 Safari/537.36")
BASE = "https://propertyhub.in.th"
IMG = "https://bcdn.propertyhub.in.th"

def log(*a): print("[harvest]", *a, file=sys.stderr)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def next_data(html):
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def zone_page(slug):
    """-> (listings, neighbour slugs). Empty on any failure; the crawl continues."""
    try:
        d = next_data(get(f"{BASE}/en/condo-for-rent/{slug}"))
        pp = (d or {}).get("props", {}).get("pageProps", {})
        L = pp.get("listings") or {}
        listings = L.get("listings") or []
        nb = []
        for group in (pp.get("zone", {}).get("nearbyZones") or {}).values():
            for z in group:
                if z.get("slug"):
                    nb.append(z["slug"])
        return listings, nb
    except Exception as e:
        log(f"zone {slug}: {type(e).__name__}")
        return [], []


ROOMTYPE_BEDS = {"STUDIO": 0, "ONE_BED_ROOM": 1, "TWO_BED_ROOM": 2,
                 "THREE_BED_ROOM": 3, "FOUR_BED_ROOM": 4}


def to_row(x, note):
    """PropertyHub record -> this skill's schema. Only fields the feed actually carries."""
    price = (x.get("price") or {}).get("forRent") or {}
    monthly = (price.get("monthly") or {}).get("price")
    daily = (price.get("daily") or {}).get("type")
    if x.get("postType") != "FOR_RENT" or not monthly:
        return None
    ri = x.get("roomInformation") or {}
    beds = ri.get("numberOfBed")
    if beds is None:
        beds = ROOMTYPE_BEDS.get(ri.get("roomType"))
    if beds is None:
        return None
    proj = x.get("project") or {}
    cover = x.get("coverPicture")
    slug = x.get("slug") or ""
    lid = x.get("id")
    flags = []
    # The feed states this outright, so short-stay risk is data here, not a keyword guess.
    if daily and daily != "NO_DAILY_RENTAL":
        flags.append("also let nightly")
    # The feed's coverPicture ends in a watermark variant ("/<key>/be7210af.jpg") that the CDN
    # 403s. The plain "<key>.jpg" form serves fine. This silently cost ~450 photos on the first run.
    if cover:
        cover = re.sub(r"/([A-Za-z0-9]+)/[0-9a-f]{6,}\.jpg$", r"/\1.jpg", cover)
    return {
        "title": (x.get("title") or proj.get("nameEnglish") or proj.get("name") or "").strip(),
        "district": (proj.get("address") or "").strip() or None,
        "position": None,
        "walk_min": None,
        "rent_thb": int(monthly),
        "sqm": ri.get("roomArea") or None,
        "bedrooms": int(beds),
        "bathrooms": ri.get("numberOfBath"),
        "floor": ri.get("onFloor"),
        "furnished": None,
        "deposit_months": None, "advance_months": None, "min_lease_months": None,
        "pets": None, "available_from": None, "lister": None,
        "link": f"{BASE}/en/listings/{slug}---{lid}" if slug else f"{BASE}/en/listings/{lid}",
        "image_url": (IMG + cover) if cover else None,
        "source": "propertyhub",
        "notes": note + (
            f" Project: {proj.get('nameEnglish') or proj.get('name')}." if proj.get("name") else "")
              + (f" Listing refreshed {(x.get('updatedAt') or '')[:10]}." if x.get("updatedAt") else ""),
        "_flags_seed": flags,
        "_id": str(lid),
    }


SEEDS = ["bangkok", "watthana", "khlong-toei", "huai-khwang", "din-daeng", "ratchathewi",
         "phaya-thai", "chatuchak", "bang-rak", "sathon", "khlong-san", "thon-buri",
         "phra-khanong", "suan-luang", "bang-na", "lat-phrao", "wang-thong-lang",
         "bang-kapi", "bueng-kum", "bang-sue", "phasi-charoen", "bangkok-noi",
         "bang-phlat", "prawet", "bang-khen", "lak-si", "pathum-wan", "bang-khae",
         "mrt-huai-khwang", "mrt-phra-ram-9", "mrt-sutthisan", "mrt-lat-phrao",
         "mrt-phetchaburi", "mrt-thailand-cultural-centre", "mrt-sukhumvit",
         "mrt-queen-sirikit-national-convention-centre", "mrt-lumphini", "mrt-si-lom",
         "mrt-sam-yan", "mrt-hua-lamphong", "mrt-bang-phlat", "mrt-bang-yi-khan"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, required=True)
    ap.add_argument("--max", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zones", type=int, default=120, help="max zone pages to crawl")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    note = ("Harvested from PropertyHub's structured zone feed (first 60 listings of the zone; "
            "the portal ranks sponsored listings first, so this is a wide sample, not a census). "
            "Deposit, furnishing, lease term and walk distance are not in the feed and are left "
            "unstated rather than assumed.")

    seen_zone, queue, rows_by_id = set(), list(SEEDS), {}
    crawled = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        while queue and crawled < a.zones:
            batch = []
            while queue and len(batch) < a.workers and crawled + len(batch) < a.zones:
                s = queue.pop(0)
                if s in seen_zone:
                    continue
                seen_zone.add(s)
                batch.append(s)
            if not batch:
                break
            futs = {ex.submit(zone_page, s): s for s in batch}
            for f in as_completed(futs):
                crawled += 1
                listings, nb = f.result()
                for x in listings:
                    r = to_row(x, note)
                    if not r or not (a.min <= r["rent_thb"] <= a.max):
                        continue
                    rows_by_id.setdefault(r["_id"], r)
                for s in nb:
                    if s not in seen_zone and len(seen_zone) + len(queue) < a.zones * 3:
                        queue.append(s)
            log(f"zones {crawled}/{a.zones}  in-band unique listings: {len(rows_by_id)}")
            time.sleep(0.3)

    rows = list(rows_by_id.values())
    json.dump(rows, open(a.out, "w"), ensure_ascii=False, indent=1)
    log(f"DONE zones={crawled} in-band unique={len(rows)} -> {a.out}")
    if rows:
        beds = {}
        for r in rows:
            beds[r["bedrooms"]] = beds.get(r["bedrooms"], 0) + 1
        log("beds:", dict(sorted(beds.items())))
        log("with sqm:", sum(1 for r in rows if r["sqm"]),
            "| rent range:", min(r["rent_thb"] for r in rows), "-", max(r["rent_thb"] for r in rows))


if __name__ == "__main__":
    main()
