#!/usr/bin/env python3
"""Harvest FazWaz Bangkok 2BR+ search pages server-side. Prices on search pages are
VND (geo-IP), so we only use them as a COARSE pre-filter; the exact THB comes from
each detail page's dataLayer (see fz_detail.py)."""
import json,re,sys,concurrent.futures as cf
import urllib.request

UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36")
def get(url):
    r=urllib.request.Request(url, headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"})
    return urllib.request.urlopen(r, timeout=45).read().decode("utf-8","replace")

def page(p):
    url=f"https://www.fazwaz.co.th/en/property-for-sale/thailand/bangkok?bedrooms=2&page={p}"
    try: h=get(url)
    except Exception as e: return p,{},str(e)
    m=re.search(r'<script type="application/json" id="search-marker-payloads">(.*?)</script>',h,re.S)
    if not m: return p,{},"nopayload"
    d=json.loads(m.group(1))
    anchors=re.findall(r'href="(/en/property-sales/[^"?#]+)"',h)+re.findall(r'href="(https://www\.fazwaz\.co\.th/en/property-sales/[^"?#]+)"',h)
    out={}
    for uid,u in d.items():
        if not u.get("bedrooms") or u["bedrooms"]<2: continue
        if "condo" not in (u.get("propertyType") or "").lower(): continue
        link=u.get("detailUrl") or ""
        if not link or "forceLogin" in link:
            cand=[a for a in anchors if a.endswith("-u"+uid)]
            link=cand[0] if cand else ""
            if link.startswith("/"): link="https://www.fazwaz.co.th"+link
        if not link: continue
        out[uid]={"id":uid,"title":u.get("name"),"raw_price":u.get("price"),
          "sqm":(float(re.sub(r"[^\d.]","",u.get("area") or "0")) or None),
          "bedrooms":u["bedrooms"],"addr":u.get("formatted_address"),
          "image_url":u.get("thumbnail"),"link":link.split("?")[0],
          "near":"; ".join(f'{n.get("tooltip")} {n.get("distance")}' for n in (u.get("nearPlaceGroup") or [])[:2])}
    return p,out,None

if __name__=="__main__":
    lo,hi=int(sys.argv[1]),int(sys.argv[2])
    all_units={}; errs=[]
    with cf.ThreadPoolExecutor(8) as ex:
        for p,out,err in ex.map(page, range(lo,hi+1)):
            if err: errs.append(f"{p}:{err}")
            all_units.update(out)
    json.dump(all_units, open("fz_units.json","w"))
    print(f"pages {lo}-{hi} | units {len(all_units)} | errors {errs[:8]}")
