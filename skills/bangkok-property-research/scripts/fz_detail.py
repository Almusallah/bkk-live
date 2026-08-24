#!/usr/bin/env python3
"""Fetch FazWaz detail pages: TRUE THB price from the dataLayer property_view event,
plus per-unit Condo Ownership, year built and floor. Immune to the VND currency trap."""
import json,re,sys,os,concurrent.futures as cf, urllib.request
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36")
def get(url):
    r=urllib.request.Request(url, headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"})
    return urllib.request.urlopen(r, timeout=45).read().decode("utf-8","replace")

ITEM=re.compile(r'<div class="basic-information__item".*?</div>\s*</div>', re.S)
def basic_info(h):
    """label -> value, reading the span.basic-information-info child (the item's own
    text begins with a long generic 49%-rule explainer)."""
    out={}
    for m in re.finditer(r'class="basic-information__item"(.{0,2500}?)basic-information-info[^>]*>(.*?)<', h, re.S):
        blob, val = m.group(1), re.sub(r'\s+',' ',m.group(2)).strip()
        lab=re.sub(r'<[^>]+>',' ',blob); lab=re.sub(r'\s+',' ',lab).strip()[:60]
        if val: out.setdefault(lab, val)
    return out

def one(u):
    try: h=get(u["link"])
    except Exception as e: return u["id"], None, f"ERR {e}"
    m=re.search(r"event:\s*'property_view'.*?price:\s*([\d.]+),\s*currency:\s*'([A-Z]{3})'", h, re.S)
    if not m: return u["id"], None, "no dataLayer price"
    price, cur = float(m.group(1)), m.group(2)
    if cur!="THB": return u["id"], None, f"currency {cur}"
    bi=basic_info(h)
    own=None; year=None; floor=None
    for lab,val in bi.items():
        L=lab.lower()
        if own is None and "condo ownership" in L: own=val
        elif year is None and ("completed" in L or "year built" in L or "construction" in L): year=val
        elif floor is None and re.match(r'^floor\b', L): floor=val
    r=dict(u); r["price_thb"]=int(round(price)); r["ownership"]=own or "N/A"
    r["year"]=year; r["floor"]=floor
    r.pop("raw_price",None)
    return u["id"], r, None

if __name__=="__main__":
    units=json.load(open("fz_units.json"))
    done={}
    if os.path.exists("fz_detail.json"): done=json.load(open("fz_detail.json"))
    todo=[u for k,u in units.items() if k not in done]
    print(f"{len(units)} units, {len(done)} already, fetching {len(todo)}")
    errs=[]
    with cf.ThreadPoolExecutor(10) as ex:
        for i,(uid,rec,err) in enumerate(ex.map(one, todo),1):
            if rec: done[uid]=rec
            elif err: errs.append(f"{uid}:{err}")
            if i%150==0:
                json.dump(done, open("fz_detail.json","w")); print("  ...",i, flush=True)
    json.dump(done, open("fz_detail.json","w"))
    from collections import Counter
    print("detail ok:",len(done),"errors:",len(errs), errs[:5])
    print("ownership:", dict(Counter(r["ownership"] for r in done.values())))
