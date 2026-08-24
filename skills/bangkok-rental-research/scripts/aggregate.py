#!/usr/bin/env python3
"""
Merge this run's rental candidates with the master, dedupe, re-verify the four hard
filters, and score 0-100 per references/scoring.md.

    python3 aggregate.py agent_rows.json [more.json ...] --rate 33.154966 --today 2026-08-14 [--write-state]
"""
import json, re, os, sys, statistics, unicodedata

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("FINAL_ROWS_OUT", "final_rows.json")


def arg(flag, default=None):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


RATE = float(arg("--rate", "33.154966"))
TODAY = arg("--today", "2026-08-14")
LO, HI = 350 * RATE, 650 * RATE          # THB / month

# ---------------------------------------------------------------- helpers
def canon(link):
    if not link:
        return ""
    l = link.split("?")[0].split("#")[0].rstrip("/")
    return re.sub(r"^www\.", "", re.sub(r"^https?://", "", l)).lower()


def norm_title(t):
    t = unicodedata.normalize("NFKD", str(t or "")).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    stop = {"condo", "condominium", "for", "rent", "rental", "the", "bedroom", "bed", "br", "at",
            "in", "bangkok", "sqm", "m2", "unit", "floor", "fl", "fully", "furnished", "new",
            "near", "bts", "mrt", "arl", "with", "and", "a", "of", "studio", "room", "apartment",
            "month", "monthly", "thb", "baht", "corner", "high", "low", "view", "city"}
    words = []
    for w in t.split():
        if w.isdigit() or re.fullmatch(r"\d+(st|nd|rd|th)", w) or w in stop:
            continue
        words.append(w)
    return " ".join(words)


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.]", "", str(v))
    try:
        return float(s)
    except Exception:
        return None


# ---------------------------------------------------------------- clusters
AREAS = [
    ("cbd_sukhumvit", ["asok", "asoke", "nana", "phrom phong", "thong lo", "thonglor", "thong lor",
                       "ekkamai", "ploenchit", "phloen chit", "chit lom", "chidlom", "lumphini",
                       "lumpini", "pathum wan", "watthana", "khlong tan", "ratchathewi", "phaya thai",
                       "victory monument", "siam", "ratchaprarop"]),
    ("upper_sukhumvit", ["on nut", "onnut", "bang chak", "punnawithi", "udom suk", "udomsuk",
                         "bearing", "phra khanong", "samrong", "lasalle", "la salle", "sukhumvit 50",
                         "sukhumvit 64", "sukhumvit 71", "sukhumvit 77", "sukhumvit 101",
                         "sukhumvit 105", "sukhumvit 107", "sukhumvit 81", "sukhumvit 93"]),
    ("riverside_sathorn", ["sathorn", "sathon", "silom", "saphan taksin", "surasak", "chong nonsi",
                           "sala daeng", "charoen nakhon", "krung thonburi", "krung thon buri",
                           "wongwian yai", "khlong san", "bang kho laem", "yannawa", "yan nawa",
                           "rama 3", "talat phlu", "thonburi", "bang rak", "suriyawong", "sam yan"]),
    ("ratchada_rama9", ["rama 9", "phra ram 9", "huai khwang", "huay khwang", "ratchada",
                        "sutthisan", "din daeng", "makkasan", "phetchaburi", "cultural centre",
                        "cultural center", "asoke ratchada"]),
    ("ari_chatuchak", ["ari", "saphan khwai", "mo chit", "sanam pao", "phahon", "phaholyothin",
                       "chatuchak", "jatujak", "ratchayothin", "lat yao", "kaset", "sena nikhom",
                       "chom phon", "chan kasem", "bang sue", "sam sen nai"]),
    ("latphrao_ne", ["lat phrao", "ladprao", "latphrao", "chok chai", "wang thonglang", "bang kapi",
                     "ramkhamhaeng", "hua mak", "huamark", "bueng kum", "bang khen", "nawamin",
                     "phlapphla", "saphan song", "anusawari", "lat pla khao", "si kritha"]),
    ("bangna_west", ["bangna", "bang na", "srinakarin", "srinakharin", "si nakharin", "nong bon",
                     "rama 4", "suan luang", "prawet", "si iam", "si udom", "pattanakarn",
                     "pinklao", "pin klao", "bangkok noi", "bang phlat", "charan", "bang yi khan",
                     "phasi charoen", "bang khae", "petchkasem", "phetkasem", "lak song",
                     "phra nakhon", "sam yot", "bang khun phrom", "taling chan"]),
]
PRIME = {"cbd_sukhumvit", "riverside_sathorn", "ratchada_rama9"}


def area_of(r):
    """Location comes from district + position. The TITLE is only a last resort, because
    Thai project names collide with place names — "Lumpini Place Rama IX" is an LPN-brand
    building in Huai Khwang, not a building in Lumphini, and matching the title first filed
    every LPN tower in the CBD and skewed that cluster's median rent."""
    where = " ".join(str(r.get(k) or "") for k in ("district", "position")).lower()
    for key, kws in AREAS:
        for kw in kws:
            if kw in where:
                return key
    title = str(r.get("title") or "").lower()
    for key, kws in AREAS:
        for kw in kws:
            if kw in title:
                return key
    return "other"


# ---------------------------------------------------------------- hard filters
SHORTSTAY = ("per night", "/night", "per day", "/day", "nightly", "daily rate", "airbnb",
             "short stay", "short-stay", "short term only", "hotel", "guesthouse", "hostel",
             "dorm", "dormitory", "shared room", "co-living", "coliving", "รายวัน", "รายสัปดาห์")
NOT_A_UNIT = ("shared", "bed in", "bunk")


def hard_filters(r):
    rent = num(r.get("rent_thb"))
    if rent is None:
        return False, "no rent"
    if not (LO <= rent <= HI):
        return False, f"rent {int(rent)} outside band"
    ml = num(r.get("min_lease_months"))
    if ml is not None and ml < 6:
        return False, f"min lease {ml:g} months"
    b = num(r.get("bedrooms"))
    if b is None:
        return False, "no bedroom count"
    # A stated lease of >=6 months IS the evidence that this is a long-term let. Only when no
    # lease term is given do we fall back to keyword sniffing — and then only on TITLE + LINK,
    # never on notes, because agents routinely write caveats like "confirm it is not nightly"
    # and matching those would evict exactly the listings that were checked most carefully.
    if ml is None:
        hay = " ".join(str(r.get(k) or "") for k in ("title", "link")).lower()
        for bad in SHORTSTAY:
            if bad in hay:
                return False, f"short-stay/shared product ({bad})"
    return True, ""


# Strong risk signals: the listing may not be the long-term rental it appears to be.
# These cap the score. Phrased as the researching agents actually write them.
SUSPECT = ("repurposed sale", "written for a buyer", "reads as a sale", "bait", "scam",
           "possible short", "unusually cheap", "too good to be true",
           "genuinely available to rent", "not a genuine")
# Softer caveats worth showing the reader as a chip, but not worth capping the score over.
SOFT = [("also for sale", ("for rent / sale", "for rent and for sale", "dual-listed",
                           "dual listed", "also listed for sale", "for sale at thb",
                           "landlord selling", "selling under a tenant")),
        ("may be stale", ("stale", "likely stale", "confirm before travelling",
                          "verify before relying", "has been on market", "photos date")),
        ("distance unverified", ("not a verified one", "verify on a map", "check on a map",
                                 "treat the 1-minute walk", "does not specify walking")),
        ("also let nightly", ("thb/night", "thb/day", "baht/night", "nightly rate", "/night",
                              "per night", "nightly at", "also sells nightly", "รายวัน",
                              "confirm you are on the 1-year", "confirm you are booked on the annual")),
        ("rate depends on lease length", ("6-month contract is quoted", "on a 6-month contract is",
                                          "is the 1-year price", "is the 1-year contract rate",
                                          "short-term contract and")),
        ("terms not stated", ("deposit and advance are not stated",
                              "deposit and advance are not published",
                              "do not assume the 2+1 norm"))]


def risk_flags(r):
    hay = " ".join(str(r.get(k) or "") for k in ("notes", "title")).lower()
    return [label for label, keys in SOFT if any(k in hay for k in keys)]


# ---------------------------------------------------------------- scoring
def yr_built(r):
    yrs = [int(y) for y in re.findall(r"\b(19[6-9]\d|20[0-2]\d)\b",
                                      " ".join(str(r.get(k) or "") for k in ("notes", "title")))]
    yrs = [y for y in yrs if 1965 <= y <= 2026]
    return min(yrs) if yrs else None


def interp(x, pts):
    """pts = [(x0,y0),(x1,y1),...] ascending in x."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def score_row(r, medians):
    a, p = r["_area"], {}

    # value 0.28 — rent per m2 vs cluster median
    pps, med = r.get("thb_per_sqm"), medians.get(a) or medians.get("_all")
    if pps and med:
        p["value"] = max(0.0, min(1.0, 0.5 + (1.0 - pps / med) * 2.0))
    else:
        p["value"] = 0.5

    # transit 0.22
    w = num(r.get("walk_min"))
    if w is None:
        base = 0.45
    else:
        base = interp(w, [(3, 1.0), (5, .85), (8, .65), (12, .45), (20, .2), (25, .1)])
    txt = str(r.get("position") or "").lower()
    if "no bts" in txt or "no rail" in txt or "no mrt" in txt or "not walkable" in txt:
        base = min(base, 0.15)
    if a in PRIME:
        base = min(1.0, base * 1.1)
    p["transit"] = base

    # absolute size 0.15
    s = num(r.get("sqm"))
    p["size"] = 0.4 if not s else interp(
        s, [(18, .15), (22, .3), (28, .45), (35, .6), (45, .8), (60, 1.0)])

    # move-in cost 0.12
    dep, adv = num(r.get("deposit_months")), num(r.get("advance_months"))
    if dep is None or adv is None:
        p["movein"] = 0.5
    else:
        mult = 1 + dep + adv
        p["movein"] = interp(mult, [(2, 1.0), (3, .8), (4, .55), (5, .3), (6, .1)])
        r["movein_thb"] = int(round(r["rent_thb"] * mult))

    # furnishing 0.10
    p["furn"] = {"fully": 1.0, "partly": 0.6, "unfurnished": 0.25}.get(
        (r.get("furnished") or "").lower(), 0.45)

    # building age 0.08
    y = yr_built(r)
    if y is None:
        p["quality"] = 0.5
    else:
        age = 2026 - y
        p["quality"] = 1.0 if age <= 8 else max(0.1, 1.0 - (age - 8) * 0.035)
        r["_year_built"] = y

    # trust 0.05
    hay = " ".join(str(r.get(k) or "") for k in ("notes", "title")).lower()
    suspicious = any(k in hay for k in SUSPECT)
    seeded = [f for f in (r.get("_flags_seed") or []) if f]
    r["flags"] = sorted(set((["may not be a real let"] if suspicious else []) + risk_flags(r) + seeded),
                        key=lambda f: (f != "may not be a real let", f))
    if suspicious:
        p["trust"] = 0.0
        r["_flag_suspicious"] = True
    else:
        t = 0.4
        if r.get("image_url"):
            t += 0.2
        if s:
            t += 0.15
        if r.get("floor"):
            t += 0.1
        if dep is not None:
            t += 0.1
        if (r.get("lister") or "") == "owner":
            t += 0.05
        p["trust"] = min(1.0, t)

    W = {"value": .28, "transit": .22, "size": .15, "movein": .12,
         "furn": .10, "quality": .08, "trust": .05}
    r["_parts"] = {k: round(v, 3) for k, v in p.items()}
    total = sum(p[k] * W[k] for k in W) * 100
    if suspicious:
        total = min(total, 55)
    return int(round(max(0, min(100, total))))


# ---------------------------------------------------------------- main
def main():
    state_path = os.path.join(SKILL, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    master = state.get("rows", [])

    incoming = []
    for f in sys.argv[1:]:
        if f.startswith("--") or f == TODAY or f == str(RATE):
            continue
        if f.endswith(".json"):
            incoming.extend(json.load(open(f)))
    print(f"incoming raw: {len(incoming)}")

    kept, dropped = [], []
    for raw in incoming:
        r = dict(raw)
        ok, why = hard_filters(r)
        if not ok:
            dropped.append((r.get("title"), why))
            continue
        r["rent_thb"] = int(num(r["rent_thb"]))
        r["rent_usd"] = int(round(r["rent_thb"] / RATE))
        r["bedrooms"] = int(num(r["bedrooms"]))
        s = num(r.get("sqm"))
        r["sqm"] = round(s, 1) if s else None
        r["thb_per_sqm"] = int(round(r["rent_thb"] / s)) if s else None
        for k in ("deposit_months", "advance_months", "min_lease_months", "walk_min"):
            r[k] = num(r.get(k))
        dep, adv = r["deposit_months"], r["advance_months"]
        r["movein_thb"] = int(round(r["rent_thb"] * (1 + dep + adv))) if (
            dep is not None and adv is not None) else None
        r.pop("_agent", None); r.pop("score", None)
        r["_flags_seed"] = raw.get("_flags_seed") or []
        kept.append(r)
    print(f"passed hard filters: {len(kept)}  dropped: {len(dropped)}")
    for t, w in dropped:
        print("   DROP:", str(t or "")[:66], "|", w)

    # in-run link dedupe
    seen, run_rows = set(), []
    for r in kept:
        k = canon(r.get("link"))
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        run_rows.append(r)
    print(f"after in-run link dedupe: {len(run_rows)}")

    # cross-portal fuzzy merge inside the run
    merged, fuzzy = [], []
    for r in run_rows:
        hit = None
        for m in merged:
            if m.get("source") == r.get("source"):
                continue
            if norm_title(m.get("title")) != norm_title(r.get("title")) or not norm_title(r.get("title")):
                continue
            if (m.get("sqm") or 0) and (r.get("sqm") or 0) and abs(m["sqm"] - r["sqm"]) > 1.0:
                continue
            if abs(m["rent_thb"] - r["rent_thb"]) / max(m["rent_thb"], 1) > 0.02:
                continue
            hit = m
            break
        if hit:
            fuzzy.append((hit.get("title"), hit.get("source"), r.get("source")))
            if not hit.get("image_url") and r.get("image_url"):
                hit["image_url"] = r["image_url"]
            # keep the lowest quoted rent — it is the negotiating floor
            if r["rent_thb"] < hit["rent_thb"]:
                hit["notes"] = (hit.get("notes") or "") + \
                    f" [also on {r.get('source')} at THB {hit['rent_thb']:,} — lower quote kept]"
                hit["rent_thb"] = r["rent_thb"]
                hit["rent_usd"] = int(round(r["rent_thb"] / RATE))
            else:
                hit["notes"] = (hit.get("notes") or "") + f" [also listed on {r.get('source')}]"
            continue
        merged.append(r)
    print(f"after cross-portal merge: {len(merged)} ({len(fuzzy)} merged)")
    for t, a, b in fuzzy:
        print("   MERGE:", str(t or "")[:56], f"{a} <- {b}")

    # merge into master
    by_link = {canon(m.get("link")): m for m in master if m.get("link")}
    new_count, rematch = 0, []
    for r in merged:
        k = canon(r.get("link"))
        prev = by_link.get(k)
        if prev is None:
            nt = norm_title(r.get("title"))
            for m in master:
                if not nt or norm_title(m.get("title")) != nt:
                    continue
                ms, mr = num(m.get("sqm")), num(m.get("rent_thb"))
                if mr is None or abs(mr - r["rent_thb"]) / max(mr, 1) > 0.02:
                    continue
                if ms and r.get("sqm") and abs(ms - r["sqm"]) > 1.0:
                    continue
                prev = m
                rematch.append((r.get("title"), m.get("source"), r.get("source")))
                break
        if prev:
            for key in ("title", "district", "position", "walk_min", "rent_thb", "rent_usd", "sqm",
                        "thb_per_sqm", "bedrooms", "bathrooms", "floor", "furnished",
                        "deposit_months", "advance_months", "movein_thb", "min_lease_months",
                        "pets", "available_from", "lister", "image_url", "source", "notes"):
                if r.get(key) is not None:
                    prev[key] = r[key]
            prev["last_seen"] = TODAY
        else:
            r["first_seen"] = TODAY
            r["last_seen"] = TODAY
            master.append(r)
            by_link[k] = r
            new_count += 1
    if rematch:
        print(f"fuzzy re-matched against master: {len(rematch)}")
        for t, a, b in rematch:
            print("   REMATCH:", str(t or "")[:56], f"{a} <- {b}")
    print(f"NEW: {new_count}   master total: {len(master)}")

    # re-verify + recompute everything, then score with one function
    live, parked = [], []
    for r in master:
        ok, why = hard_filters(r)
        if not ok:
            r["parked_reason"] = why
            r["parked_on"] = TODAY
            parked.append(r)
            continue
        r.pop("parked_reason", None); r.pop("parked_on", None)
        r["rent_thb"] = int(num(r["rent_thb"]))
        r["rent_usd"] = int(round(r["rent_thb"] / RATE))
        s = num(r.get("sqm"))
        # Portals mis-key floor area (a "1-bed, 431 m²" at THB 16k is the project's area, not
        # the unit's). Treat implausible sizes as unknown rather than deleting a real listing —
        # one bad value otherwise tops the cheapest-per-m2 sort and drags the cluster median.
        if s and not (12 <= s <= 200):
            r.setdefault("_flags_seed", []).append("size looks wrong")
            r["notes"] = (r.get("notes") or "") + f" [portal states {s:g} m2 — implausible for this rent, treated as unknown]"
            s = None
        r["sqm"] = round(s, 1) if s else None
        r["thb_per_sqm"] = int(round(r["rent_thb"] / s)) if s else None
        r["_area"] = area_of(r)
        live.append(r)
    if parked:
        print(f"parked (kept in state, first_seen preserved): {len(parked)}")
        for r in parked[:12]:
            print("   PARK:", str(r.get('title') or '')[:56], "|", r["parked_reason"])

    medians = {}
    for a in {r["_area"] for r in live}:
        vals = [r["thb_per_sqm"] for r in live if r["_area"] == a and r.get("thb_per_sqm")]
        if len(vals) >= 4:
            medians[a] = statistics.median(vals)
    allv = [r["thb_per_sqm"] for r in live if r.get("thb_per_sqm")]
    medians["_all"] = statistics.median(allv) if allv else None
    print("median THB/m2/month:", {k: int(v) for k, v in sorted(medians.items()) if v})

    for r in live:
        r["score"] = score_row(r, medians)
    live.sort(key=lambda r: (-r["score"], r.get("thb_per_sqm") or 10**9))

    KEEP = ("score", "title", "district", "position", "walk_min", "rent_usd", "rent_thb", "sqm",
            "thb_per_sqm", "bedrooms", "bathrooms", "floor", "furnished", "deposit_months",
            "advance_months", "movein_thb", "min_lease_months", "pets", "available_from",
            "lister", "link", "image_url", "source", "notes", "flags", "first_seen", "last_seen")
    out_rows = [{k: r.get(k) for k in KEEP} for r in live]
    json.dump(out_rows, open(OUT, "w"), ensure_ascii=False, indent=1)

    if "--write-state" in sys.argv:
        keep_parked, seenp = [], set()
        livelinks = {canon(r.get("link")) for r in live}
        for p in parked + [q for q in state.get("parked", []) if canon(q.get("link")) not in livelinks]:
            k = canon(p.get("link"))
            if k in seenp:
                continue
            seenp.add(k)
            keep_parked.append(p)
        state.update({"rows": out_rows, "parked": keep_parked,
                      "last_run": TODAY, "rate_thb_per_usd": RATE})
        json.dump(state, open(state_path, "w"), ensure_ascii=False, indent=1)
        print(f"state.json written: {len(out_rows)} live + {len(keep_parked)} parked")

    from collections import Counter
    fresh = [r for r in live if r.get("last_seen") == TODAY]
    print(f"\nlive: {len(live)}  seen this run: {len(fresh)}  new: {new_count}")
    print("beds:", Counter(r["bedrooms"] for r in live))
    print("furnished:", Counter(r.get("furnished") for r in live))
    print("photos:", sum(1 for r in live if r.get("image_url")))
    print("\nTOP 12:")
    for r in live[:12]:
        tag = "NEW" if r.get("first_seen") == TODAY else "seen"
        bd = "studio" if r["bedrooms"] == 0 else f'{r["bedrooms"]}BR'
        print(f'  {r["score"]:3d} {tag:4s} {str(r["title"])[:46]:46s} {bd:6s} '
              f'{(str(r["sqm"])+"m2") if r["sqm"] else "  ?  ":>7s} ${r["rent_usd"]:>4}/mo '
              f'{(str(r["thb_per_sqm"])+"/m2") if r["thb_per_sqm"] else "":>9s} '
              f'{("walk "+str(int(r["walk_min"]))+"m") if r.get("walk_min") else "walk ?":8s} {r["_area"]}')


if __name__ == "__main__":
    main()
