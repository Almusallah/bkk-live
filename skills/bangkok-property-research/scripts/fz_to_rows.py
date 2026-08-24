#!/usr/bin/env python3
"""fz_detail.json -> the skill's row schema, filtered to this run's THB band."""
import json,re
import os,sys
RATE=float(os.environ.get("BKK_RATE") or 0)
if not RATE: sys.exit("BKK_RATE not set")
LO,HI=round(80000*RATE),round(200000*RATE)
d=json.load(open("fz_detail.json"))
def quota(o):
    o=(o or "").strip()
    if o=="Foreign Quota": return "foreign_freehold","Ownership: Foreign Quota (foreign-only title) — confirmed on the FazWaz unit page."
    if o.startswith("Foreign Quota"):
        return "foreign_freehold", (f"Ownership: \"{o}\" — offered under EITHER quota, which is weaker than a foreign-only title; "
                                    "confirm the building still has foreign quota left before committing.")
    if o in ("N/A","",None): return "unknown","Ownership not stated on the unit page — confirm quota with agent."
    if o=="Freehold": return "unknown","Ownership reads only \"Freehold\" — does not say whether the title is in the foreign or the Thai quota; confirm with agent."
    return "leasehold_or_thai_only", f"Ownership: {o} — NOT buyable in a foreigner's own name as listed."
rows=[]; dropped=0
for u in d.values():
    p=u.get("price_thb") or 0
    if p<LO or p>HI: dropped+=1; continue
    q,note=quota(u.get("ownership"))
    extra=[]
    if u.get("floor") and u["floor"]!="N/A": extra.append(f"Floor {u['floor']}")
    if u.get("year"): extra.append(f"Completed {u['year']}")
    addr=(u.get("addr") or "")
    rows.append({"title":u.get("title") or "","district":addr,
      "position":u.get("near") or "No BTS/MRT/ARL listed",
      "price_thb":p,"sqm":u.get("sqm"),"bedrooms":u.get("bedrooms"),
      "foreign_freehold":q,"link":u.get("link"),"image_url":u.get("image_url"),
      "source":"fazwaz","notes":". ".join(extra+[note])})
json.dump(rows,open("fazwaz.json","w"),ensure_ascii=False)
from collections import Counter
print(f"fazwaz: {len(rows)} in band (of {len(d)}), {dropped} out of band")
print("quota:", dict(Counter(r['foreign_freehold'] for r in rows)))
