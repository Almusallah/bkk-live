#!/usr/bin/env python3
"""Aggregate, hard-filter, dedup, score. Bangkok weekly scan."""
import json, os, re, sys, statistics, datetime, unicodedata
from urllib.parse import urlsplit

# All four are overridable so the same script runs locally AND in the cloud checkout:
#   BKK_SKILL_DIR  dir holding state.json + references/ (default: the local skill install)
#   BKK_WORK_DIR   workdir holding the agent/harvest JSON files (default: cwd)
#   BKK_TODAY      run date YYYY-MM-DD (default: today)
#   BKK_RATE       REQUIRED — this run's live USD->THB rate; refuse to guess it
SKILL = os.environ.get("BKK_SKILL_DIR") or os.path.expanduser("~/.claude/skills/bangkok-property-research")
SCR   = os.environ.get("BKK_WORK_DIR") or os.getcwd()
TODAY = os.environ.get("BKK_TODAY") or datetime.date.today().isoformat()
RATE  = float(os.environ.get("BKK_RATE") or 0)
if not RATE:
    sys.exit("BKK_RATE not set — fetch the live USD->THB rate and export it; never reuse a stale rate")
LO, HI = round(80000*RATE), round(200000*RATE)

# ---------- helpers ----------
def canon(u):
    if not u: return None
    u = u.strip().split("?")[0].split("#")[0].rstrip("/")
    u = re.sub(r"^https?://(www\.)?", "https://", u)
    return u

NON_BKK = ["nonthaburi","rattanathibet","pak kret","muang thong","pathum thani","samut prakan",
    "samrong","thepharak","bang phli","bang sao thong","pattaya","jomtien","na jomtien","hua hin",
    "cha-am","chiang mai","chiang rai","phuket","kamala","patong","rawai","kathu","thalang",
    "khon kaen","khao yai","pak chong","koh samui","samui","krabi","rayong","chonburi","sriracha",
    "si racha","bang saray","hat yai","udon thani","nakhon","ayutthaya","khu khot","lam luk ka",
    "bang bua thong","bang yai","bang kruai","phra pradaeng","hua mak"]  # hua mak removed below
NON_BKK.remove("hua mak")
NON_BKK_TH = ["นนทบุรี","รัตนาธิเบศร์","ปากเกร็ด","เมืองทองธานี","ปทุมธานี","สมุทรปราการ","พัทยา",
    "จอมเทียน","หัวหิน","ชะอำ","เชียงใหม่","ภูเก็ต","ขอนแก่น","เขาใหญ่","ปากช่อง","สมุย","กระบี่",
    "ระยอง","ชลบุรี","ศรีราชา","หาดใหญ่","อุดรธานี","อยุธยา"]

LANDED = ["townhouse","town house","townhome","shophouse","shop house","single house","detached house",
    "villa","land for sale","land plot","ทาวน์เฮ้าส์","ทาวน์โฮม","บ้านเดี่ยว","ที่ดิน"]

def is_non_bkk(row):
    hay = " ".join(str(row.get(k) or "") for k in ("title","district","position","link")).lower()
    for t in NON_BKK:
        if t in hay: return t
    for t in NON_BKK_TH:
        if t in hay: return t
    return None

def is_landed(row):
    """Title + link ONLY (v6 lesson: reading notes evicted good condos)."""
    hay = (str(row.get("title") or "") + " " + str(row.get("link") or "")).lower()
    if "condo" in hay or "คอนโด" in hay:
        return None
    for t in LANDED:
        if t in hay: return t
    return None

def norm_quota(v):
    if not v: return "unknown"
    s = str(v).strip().lower()
    if s in ("foreign_freehold","unknown","leasehold_or_thai_only"): return s
    if "foreign" in s and "thai" not in s and "company" not in s and "lease" not in s:
        return "foreign_freehold"
    if "foreign" in s:  # "Foreign Quota, Thai Quota" — either, weaker
        return "foreign_freehold"
    if "thai" in s or "lease" in s or "company" in s: return "leasehold_or_thai_only"
    return "unknown"

def fuzzy_key(row):
    t = unicodedata.normalize("NFKD", str(row.get("title") or "")).lower()
    t = re.sub(r"\b(\d+\s*bedroom|\d+\s*bed|condo|for sale|at|in|bangkok|apartment|unit)\b"," ",t)
    t = re.sub(r"[^a-z0-9฀-๿]+","",t)[:34]
    sqm = row.get("sqm") or 0
    return (t, round(float(sqm)/3) if sqm else 0, round((row.get("price_thb") or 0)/150000))

# ---------- station / area ----------
AREA_BUCKETS = [
 ("Lower Sukhumvit / CBD", ["asok","asoke","phrom phong","prompong","thong lo","thonglor","ekkamai","nana",
   "khlong tan","klongton","watthana","phloen chit","ploenchit","chit lom","chidlom","ratchadamri","lumphini","lumpini","sukhumvit 2","sukhumvit 3","sukhumvit 4","phra khanong nuea"]),
 ("Upper Sukhumvit", ["on nut","onnut","bang chak","punnawithi","udom suk","bearing","phra khanong","bang na","bangna","sukhumvit 7","sukhumvit 8","sukhumvit 9","sukhumvit 10","sukhumvit 6","suan luang","prawet"]),
 ("Riverside / Sathorn / Silom", ["saphan taksin","charoen nakhon","krung thonburi","wongwian yai","sathorn","sathon","silom","chong nonsi","surasak","bang rak","klong san","khlong san","thonburi","talat phlu","bang wa","yannawa","rama 3","chao phraya","icon siam","iconsiam"]),
 ("Ratchada / Rama 9", ["ratchada","rama 9","rama ix","phra ram 9","huai khwang","huay khwang","sutthisan","din daeng","cultural cent","thailand cultural","phetchaburi","makkasan","ratchathewi","phra ram 9"]),
 ("Ari / Phaya Thai / Chatuchak", ["ari","saphan khwai","mo chit","phahon","phaya thai","sanam pao","victory monument","chatuchak","lat yao","kaset","senanikom","ratchayothin","bang sue","tao poon"]),
 ("Lat Phrao / north-east", ["lat phrao","ladprao","chok chai","wang thonglang","bang kapi","ramkhamhaeng","bueng kum","khan na yao","min buri","nawamin","sena nikhom","hua mak"]),
 ("Bangna / Rama 4 / south-east", ["rama 4","rama iv","khlong toei","klong toey","srinakarin","srinagarindra","true digital","udomsuk","bang na"]),
 ("Other Bangkok", []),
]
def area_of(row):
    hay = " ".join(str(row.get(k) or "") for k in ("district","position","title","link")).lower()
    for name, keys in AREA_BUCKETS:
        for k in keys:
            if k in hay: return name
    return "Other Bangkok"

PRIME = {"Lower Sukhumvit / CBD", "Riverside / Sathorn / Silom", "Ratchada / Rama 9", "Ari / Phaya Thai / Chatuchak"}

def transit_score(row):
    p = (str(row.get("position") or "") + " " + str(row.get("notes") or "")).lower()
    d = None
    m = re.search(r"([\d.]+)\s*km", p)
    if m:
        try: d = float(m.group(1))*1000
        except: pass
    if d is None:
        m = re.search(r"(\d{2,5})\s*(?:m\b|metre|meter|m\.)", p)
        if m:
            try: d = float(m.group(1))
            except: pass
    if d is None:
        m = re.search(r"(\d+)\s*(?:min|minute)", p)
        if m:
            try: d = float(m.group(1))*80
            except: pass
    if re.search(r"no bts|no mrt|no bts/mrt|no station|not near", p):
        base = 0.15
    elif d is not None:
        if d <= 300: base = 1.0
        elif d >= 2500: base = 0.12
        else: base = max(0.12, 1.0 - (d-300)/2200*0.88)
    elif re.search(r"\b(bts|mrt|arl|airport rail)\b", p):
        base = 0.5
    else:
        base = 0.35
    return base * (1.0 if area_of(row) in PRIME else 0.82)

def size_score(sqm):
    if not sqm: return 0.5
    s = float(sqm)
    if s >= 70: return 1.0
    if s >= 55: return 0.6 + (s-55)/15*0.4
    if s >= 45: return 0.6
    if s >= 38: return 0.35
    return 0.12

def age_score(row):
    txt = " ".join(str(row.get(k) or "") for k in ("notes","title"))
    m = re.search(r"(19|20)\d{2}", txt)
    if not m: return 0.5
    yr = int(m.group(0))
    if yr < 1970 or yr > 2029: return 0.5
    age = 2026 - yr
    if age <= 8: return 1.0
    if age >= 30: return 0.15
    return max(0.15, 1.0 - (age-8)/22*0.85)

def yield_score(row):
    txt = " ".join(str(row.get(k) or "") for k in ("notes",))
    m = re.search(r"([\d.]+)\s*%\s*(?:gross\s*)?(?:rental\s*)?yield", txt, re.I)
    if not m:
        m = re.search(r"yield[^0-9]{0,12}([\d.]+)\s*%", txt, re.I)
    if m:
        try: y = float(m.group(1))
        except: return 0.5
        if y >= 6: return 1.0
        if y <= 2.5: return 0.0
        return (y-2.5)/3.5
    return 0.5

def liquidity_score(row):
    a = area_of(row)
    base = {"Lower Sukhumvit / CBD":1.0, "Riverside / Sathorn / Silom":0.85,
            "Upper Sukhumvit":0.8, "Ratchada / Rama 9":0.7,
            "Ari / Phaya Thai / Chatuchak":0.7, "Bangna / Rama 4 / south-east":0.55,
            "Lat Phrao / north-east":0.4, "Other Bangkok":0.4}.get(a, 0.5)
    if row.get("foreign_freehold") == "leasehold_or_thai_only": base *= 0.6
    return base

def score_row(row, medians):
    a = area_of(row)
    med = medians.get(a) or medians.get("_all")
    pps = row.get("price_per_sqm_thb")
    if pps and med:
        ratio = pps/med
        if ratio <= 0.80: v = 1.0
        elif ratio >= 1.20: v = 0.0
        else: v = 1.0 - (ratio-0.80)/0.40
    else:
        v = 0.5
    q = {"foreign_freehold":1.0, "unknown":0.4, "leasehold_or_thai_only":0.0}[row["foreign_freehold"]]
    comps = [(v,0.30), (q,0.20), (transit_score(row),0.15), (size_score(row.get("sqm")),0.10),
             (yield_score(row),0.10), (age_score(row),0.08), (liquidity_score(row),0.07)]
    return max(0, min(100, round(sum(c*w for c,w in comps)*100))), v

# ---------- load ----------
def load(p):
    try:
        with open(p) as f: d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception as e:
        print(f"  !! {os.path.basename(p)}: {e}", file=sys.stderr); return []

incoming = []
AGENT_FILES = ["cluster1.json","cluster2.json","cluster3.json","cluster4.json",
               "cluster5.json","cluster6.json","cluster7.json","thai.json"]
for fn in AGENT_FILES:
    rows = load(os.path.join(SCR, fn))
    print(f"  {fn}: {len(rows)}")
    incoming += rows

fz = load(os.path.join(SCR, "fazwaz.json"))
print(f"  fazwaz.json: {len(fz)}")
incoming += fz
li = load(os.path.join(SCR, "livinginsider.json"))
print(f"  livinginsider.json: {len(li)}")
incoming += li

print(f"raw candidates: {len(incoming)}")

# ---------- hard-filter re-verify ----------
kept, dropped = [], {"price":0,"beds":0,"nonbkk":0,"landed":0,"nolink":0,"nosqm":0}
for r in incoming:
    if not isinstance(r, dict): continue
    link = canon(r.get("link"))
    if not link: dropped["nolink"] += 1; continue
    try: p = int(round(float(r.get("price_thb") or 0)))
    except: p = 0
    if p < LO or p > HI: dropped["price"] += 1; continue
    try: b = int(r.get("bedrooms") or 0)
    except: b = 0
    if b < 2: dropped["beds"] += 1; continue
    if is_non_bkk(r): dropped["nonbkk"] += 1; continue
    if is_landed(r): dropped["landed"] += 1; continue
    sqm = r.get("sqm")
    try: sqm = float(sqm) if sqm else None
    except: sqm = None
    if sqm and (sqm < 20 or sqm > 400): sqm = None
    kept.append({
        "title": (r.get("title") or "").strip()[:160],
        "district": (r.get("district") or "").strip()[:80],
        "position": (r.get("position") or "").strip()[:120],
        "price_thb": p,
        "price_usd": round(p/RATE),
        "sqm": round(sqm,2) if sqm else None,
        "price_per_sqm_thb": round(p/sqm) if sqm else None,
        "bedrooms": b,
        "foreign_freehold": norm_quota(r.get("foreign_freehold")),
        "link": link,
        "image_url": (r.get("image_url") or None),
        "source": (r.get("source") or "").strip().lower()[:32] or "unknown",
        "notes": (r.get("notes") or "").strip()[:900],
    })
print("hard-filter kept:", len(kept), "dropped:", dropped)

# ---------- dedup within run ----------
QRANK = {"foreign_freehold":2, "unknown":1, "leasehold_or_thai_only":0}
def merge_into(dst, src):
    if not dst.get("sqm") and src.get("sqm"):
        dst["sqm"] = src["sqm"]; dst["price_per_sqm_thb"] = round(dst["price_thb"]/src["sqm"])
    if not dst.get("image_url") and src.get("image_url"): dst["image_url"] = src["image_url"]
    # quota: only explicit evidence upgrades/downgrades; never demote confirmed on silence
    if QRANK[src["foreign_freehold"]] > QRANK[dst["foreign_freehold"]]:
        dst["foreign_freehold"] = src["foreign_freehold"]
    elif src["foreign_freehold"] == "leasehold_or_thai_only" and dst["foreign_freehold"] == "unknown":
        dst["foreign_freehold"] = src["foreign_freehold"]
    if src.get("notes") and src["notes"] not in (dst.get("notes") or ""):
        dst["notes"] = ((dst.get("notes") or "") + " | " + src["notes"]).strip(" |")[:900]
    for k in ("position","district"):
        if not dst.get(k) and src.get(k): dst[k] = src[k]

bylink, byfuzz = {}, {}
dup_link = dup_fuzz = 0
for r in kept:
    if r["link"] in bylink:
        merge_into(bylink[r["link"]], r); dup_link += 1; continue
    fk = fuzzy_key(r)
    if fk[0] and fk in byfuzz:
        merge_into(byfuzz[fk], r); dup_fuzz += 1; continue
    bylink[r["link"]] = r
    if fk[0]: byfuzz[fk] = r
pool = list(bylink.values())
print(f"in-run dedup: -{dup_link} link, -{dup_fuzz} fuzzy -> {len(pool)}")

# ---------- merge against master ----------
state = json.load(open(os.path.join(SKILL, "state.json")))
master = state["rows"]; parked = state.get("parked", [])

m_link = {canon(r["link"]): r for r in master if r.get("link")}
m_fuzz = {}
for r in master:
    fk = fuzzy_key(r)
    if fk[0]: m_fuzz.setdefault(fk, r)
p_link = {canon(r["link"]): r for r in parked if r.get("link")}

new_rows, reseen, reseen_fuzz, unparked = [], 0, 0, 0
for r in pool:
    tgt = m_link.get(r["link"])
    if tgt is None:
        fk = fuzzy_key(r)
        if fk[0]: tgt = m_fuzz.get(fk)
        if tgt is not None: reseen_fuzz += 1
    if tgt is None and r["link"] in p_link:
        tgt = p_link.pop(r["link"])
        tgt.pop("parked_reason", None)
        master.append(tgt); m_link[r["link"]] = tgt; unparked += 1
    if tgt is not None:
        first = tgt.get("first_seen") or TODAY
        merge_into(r, tgt)          # carry forward richer old data
        merge_into(tgt, r)          # then update with new
        tgt.update({k: r[k] for k in ("price_thb","price_usd","sqm","price_per_sqm_thb","link")})
        tgt["last_seen"] = TODAY; tgt["first_seen"] = first
        reseen += 1
    else:
        r["first_seen"] = TODAY; r["last_seen"] = TODAY
        master.append(r); m_link[r["link"]] = r
        fk = fuzzy_key(r)
        if fk[0]: m_fuzz.setdefault(fk, r)
        new_rows.append(r)
parked = list(p_link.values())
print(f"vs master: {len(new_rows)} new, {reseen} re-seen ({reseen_fuzz} fuzzy), {unparked} un-parked")

# ---------- authoritative FazWaz override ----------
# Agents that read FazWaz through a VND session back-converted prices and sometimes
# asserted a quota the page does not state. fz_detail.json holds the TRUE THB price
# (from the page's own dataLayer) and the verbatim Condo Ownership value, so it wins
# over anything an agent reported for the same unit id.
try:
    auth = json.load(open(os.path.join(SCR, "fz_detail.json")))
except Exception:
    auth = {}
def _fzid(link):
    m = re.search(r"-u(\d+)$", canon(link) or "")
    return m.group(1) if m else None
def _authq(o):
    o = (o or "").strip()
    if o == "Foreign Quota": return "foreign_freehold"
    if o.startswith("Foreign Quota"): return "foreign_freehold"
    if o in ("N/A", "", "Freehold"): return "unknown"
    return "leasehold_or_thai_only"
fixed_price = fixed_quota = 0
for r in master:
    if "fazwaz" not in (r.get("link") or ""): continue
    a = auth.get(_fzid(r.get("link")) or "")
    if not a: continue
    if a.get("price_thb") and a["price_thb"] != r.get("price_thb"):
        r["notes"] = ((r.get("notes") or "") +
            f" | CORRECTED {TODAY}: price was recorded as THB {r.get('price_thb'):,}; "
            f"the unit page's own dataLayer says THB {a['price_thb']:,} — using the page value.")[:900]
        r["price_thb"] = a["price_thb"]; fixed_price += 1
    if a.get("sqm") and not r.get("sqm"): r["sqm"] = a["sqm"]
    aq = _authq(a.get("ownership"))
    if aq != r.get("foreign_freehold"):
        r["notes"] = ((r.get("notes") or "") +
            f" | CORRECTED {TODAY}: quota re-read from the unit page as \"{a.get('ownership')}\" "
            f"(was recorded as {r.get('foreign_freehold')}).")[:900]
        r["foreign_freehold"] = aq; fixed_quota += 1
    # Always disclose the VERBATIM ownership string. "Foreign Quota, Thai Quota" maps to
    # foreign_freehold but is materially weaker than a foreign-only title, and a row whose
    # notes came from an agent often never says which of the two it is.
    _ov = (a.get("ownership") or "N/A")
    if _ov not in (r.get("notes") or ""):
        _msg = {"Foreign Quota": f'FazWaz Condo Ownership reads "{_ov}" — foreign-only title.',
                "N/A": 'FazWaz Condo Ownership reads "N/A" — the page does not state the quota; confirm with agent.'}.get(
            _ov, (f'FazWaz Condo Ownership reads "{_ov}" — offered under EITHER quota, weaker than a '
                  f'foreign-only title; confirm the building still has foreign quota free.'
                  if _ov.startswith("Foreign Quota") else
                  f'FazWaz Condo Ownership reads "{_ov}" — not buyable in a foreigner\'s own name as listed.'))
        r["notes"] = ((r.get("notes") or "") + " | " + _msg).strip(" |")[:900]
    if r.get("sqm"): r["price_per_sqm_thb"] = round(r["price_thb"]/r["sqm"])
print(f"fazwaz authoritative override: {fixed_price} prices corrected, {fixed_quota} quota values corrected")

# ---------- park out-of-band master rows (rate moved) ----------
live, newly_parked = [], 0
for r in master:
    p = r.get("price_thb") or 0
    if p < LO or p > HI:
        r["parked_reason"] = f"outside band at rate {RATE:.4f} (THB {LO:,}-{HI:,}) on {TODAY}"
        parked.append(r); newly_parked += 1
    else:
        r["price_usd"] = round(p/RATE)   # re-convert everything at THIS run's rate
        live.append(r)
print(f"newly parked (rate move): {newly_parked}; parked total {len(parked)}")

# ---------- score ----------
buckets = {}
for r in live:
    if r.get("price_per_sqm_thb"):
        buckets.setdefault(area_of(r), []).append(r["price_per_sqm_thb"])
medians = {k: statistics.median(v) for k, v in buckets.items() if len(v) >= 5}
allp = [r["price_per_sqm_thb"] for r in live if r.get("price_per_sqm_thb")]
medians["_all"] = statistics.median(allp) if allp else None
print("area medians THB/m²:", {k: round(v) for k, v in sorted(medians.items()) if v})

for r in live:
    r["score"], _ = score_row(r, medians)
live.sort(key=lambda r: (-r["score"], -(r.get("price_per_sqm_thb") or 10**9)))

# ---------- write ----------
json.dump(live, open(os.path.join(SCR, "final_rows.json"), "w"), ensure_ascii=False)
state = {"rows": live, "parked": parked, "last_run": TODAY, "rate_thb_per_usd": RATE}
json.dump(state, open(os.path.join(SKILL, "state.json"), "w"), ensure_ascii=False)

seen_now = [r for r in live if r.get("last_seen") == TODAY]
qm = {}
for r in live: qm[r["foreign_freehold"]] = qm.get(r["foreign_freehold"], 0) + 1
qn = {}
for r in seen_now: qn[r["foreign_freehold"]] = qn.get(r["foreign_freehold"], 0) + 1
src = {}
for r in seen_now: src[r["source"]] = src.get(r["source"], 0) + 1

print("="*60)
print(f"TOTAL LIVE {len(live)} | NEW {len(new_rows)} | SEEN THIS RUN {len(seen_now)}")
print("quota all:", qm); print("quota this run:", qn)
print("sources this run:", dict(sorted(src.items(), key=lambda x:-x[1])))
print(f"with photo: {sum(1 for r in live if r.get('image_url'))}/{len(live)}")
print("-"*60)
for r in [x for x in seen_now][:12]:
    print(f"{r['score']:3d}  {r['title'][:62]:62s} ${r['price_usd']:>7,}  {r.get('price_per_sqm_thb') or 0:>7,}/m²  {r['foreign_freehold'][:16]:16s} {'NEW' if r.get('first_seen')==TODAY else ''}")
