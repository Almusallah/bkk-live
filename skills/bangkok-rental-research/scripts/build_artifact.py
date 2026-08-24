#!/usr/bin/env python3
"""
Build the Bangkok rental Artifact page: one self-contained HTML file with every listing
photo inlined as a data: URI, an inline-SVG map, and client-side filters/sorts.

    python3 build_artifact.py --rows final_rows.json --out rentals.html --rate 33.15 --today 2026-08-14

Why everything is inlined: a published Artifact page runs under a strict CSP that blocks
EVERY external host — no tile server, no CDN, no remote <img>. Do NOT set
referrerpolicy="no-referrer" on portal images; cdn.fazwaz.com 403s without a fazwaz Referer.
"""
import argparse, base64, io, json, os, sys, datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo

def log(*a): print("[artifact]", *a, file=sys.stderr)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs", ".imgcache")


def _cache_path(url):
    import hashlib
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".jpg")


def _download(url):
    import requests
    host = urlsplit(url).netloc
    ref = "https://www.fazwaz.com/" if "fazwaz" in host else f"https://{host}/"
    r = requests.get(url, timeout=15, headers={
        "User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        "Referer": ref, "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "cross-site"})
    r.raise_for_status()
    return r.content


def fetch_thumb(url, width, quality):
    """Cache original bytes on disk so re-runs and quality re-tunes cost nothing."""
    if not url:
        return None
    try:
        from PIL import Image
        os.makedirs(CACHE_DIR, exist_ok=True)
        cp = _cache_path(url)
        raw = open(cp, "rb").read() if (os.path.exists(cp) and os.path.getsize(cp) > 0) else None
        if raw is None:
            raw = _download(url)
            open(cp, "wb").write(raw)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = im.size
        im = im.resize((width, max(1, round(h * width / w))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        log(f"thumb fail {str(url)[:70]}: {e}")
        return None


OUTSIDE = ("samut prakan", "nonthaburi", "pathum thani", "outside bangkok province")


def is_outside(r):
    hay = " ".join(str(r.get(k) or "") for k in ("district", "position", "notes")).lower()
    return any(k in hay for k in OUTSIDE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=220)
    ap.add_argument("--quality", type=int, default=48)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--rate", type=float, required=True)
    a = ap.parse_args()

    rows = json.load(open(a.rows))
    urls = sorted({r.get("image_url") for r in rows if r.get("image_url")})
    log(f"{len(rows)} rows, {len(urls)} distinct photos -> fetching")
    with ThreadPoolExecutor(max_workers=12) as ex:
        thumbs = dict(zip(urls, ex.map(lambda u: fetch_thumb(u, a.width, a.quality), urls)))
    ok = sum(1 for v in thumbs.values() if v)
    log(f"thumbnails ok: {ok}/{len(urls)}")

    data = []
    for r in rows:
        la, lo, prec, key = geo.geocode(r)
        data.append({
            "la": la, "lo": lo, "gp": prec,
            "s": r.get("score"), "t": r.get("title") or "", "d": r.get("district") or "",
            "p": r.get("position") or "", "w": r.get("walk_min"),
            "u": r.get("rent_usd"), "b": r.get("rent_thb"), "m": r.get("sqm"),
            "ps": r.get("thb_per_sqm"), "bd": r.get("bedrooms"), "ba": r.get("bathrooms"),
            "fl": r.get("floor"), "fu": r.get("furnished"), "mi": r.get("movein_thb"),
            "dep": r.get("deposit_months"), "adv": r.get("advance_months"),
            "ml": r.get("min_lease_months"), "pet": r.get("pets"), "av": r.get("available_from"),
            "li": r.get("lister"), "l": r.get("link") or "", "src": r.get("source") or "",
            "fg": r.get("flags") or [],
            "n": r.get("notes") or "", "f": r.get("first_seen") or "", "ls": r.get("last_seen") or "",
            "img": thumbs.get(r.get("image_url")) or "", "out": 1 if is_outside(r) else 0,
        })

    geoms = {"lines": [{"color": c, "pts": [geo.STATIONS[s] for s in stops if s in geo.STATIONS]}
                       for _, c, stops in geo.LINES],
             "river": geo.RIVER}
    placed = sum(1 for d in data if d["la"] is not None)
    log(f"geocoded: {placed}/{len(data)} placed")

    st = lambda k, v: sum(1 for d in data if d[k] == v)
    reps = {
        "__DATA__": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        "__GEOM__": json.dumps(geoms, separators=(",", ":")),
        "__TODAY__": a.today, "__TOTAL__": str(len(data)),
        "__NEW__": str(st("f", a.today)), "__WEEK__": str(st("ls", a.today)),
        "__PLACED__": str(placed), "__PHOTOS__": str(ok),
        "__RATE__": f"{a.rate:,.4f}",
        "__BAND__": f"฿{round(350*a.rate):,}–฿{round(650*a.rate):,}",
        "__MEDRENT__": str(int(sorted(d["u"] for d in data if d["u"])[len(data)//2])) if data else "—",
    }
    doc = TEMPLATE
    for k, v in reps.items():
        doc = doc.replace(k, v)
    open(a.out, "w", encoding="utf-8").write(doc)
    log(f"wrote {a.out}  ({len(doc)/1e6:.2f} MB)")


TEMPLATE = r"""<meta charset="utf-8">
<title>Bangkok rentals — $350–650 a month</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{
  --ground:#EFF0F4; --surface:#FBFBFD; --surface-2:#F4F5F9; --line:#DBDDE6; --line-strong:#C3C6D4;
  --ink:#12131A; --ink-2:#3B3F52; --muted:#666B80;
  --accent:#1D6F63; --accent-soft:#DDEFEA;
  --ok:#136B4E; --ok-soft:#DDEFE7; --warn:#8A5A06; --warn-soft:#F6EBD5; --bad:#9A3628; --bad-soft:#F5E1DD;
  --shadow:0 1px 2px rgba(18,19,26,.06),0 8px 24px -16px rgba(18,19,26,.30);
}
@media (prefers-color-scheme:dark){:root{
  --ground:#0D0F15; --surface:#161923; --surface-2:#1D2130; --line:#282D3C; --line-strong:#3A4054;
  --ink:#E8EAF2; --ink-2:#BFC4D6; --muted:#8D93A8;
  --accent:#5FC7B4; --accent-soft:#12312C;
  --ok:#6FCFA8; --ok-soft:#12291F; --warn:#E3B45C; --warn-soft:#2C2312; --bad:#E88A78; --bad-soft:#2E1A16;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.9);}}
:root[data-theme="dark"]{
  --ground:#0D0F15; --surface:#161923; --surface-2:#1D2130; --line:#282D3C; --line-strong:#3A4054;
  --ink:#E8EAF2; --ink-2:#BFC4D6; --muted:#8D93A8; --accent:#5FC7B4; --accent-soft:#12312C;
  --ok:#6FCFA8; --ok-soft:#12291F; --warn:#E3B45C; --warn-soft:#2C2312; --bad:#E88A78; --bad-soft:#2E1A16;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.9);}
:root[data-theme="light"]{
  --ground:#EFF0F4; --surface:#FBFBFD; --surface-2:#F4F5F9; --line:#DBDDE6; --line-strong:#C3C6D4;
  --ink:#12131A; --ink-2:#3B3F52; --muted:#666B80; --accent:#1D6F63; --accent-soft:#DDEFEA;
  --ok:#136B4E; --ok-soft:#DDEFE7; --warn:#8A5A06; --warn-soft:#F6EBD5; --bad:#9A3628; --bad-soft:#F5E1DD;
  --shadow:0 1px 2px rgba(18,19,26,.06),0 8px 24px -16px rgba(18,19,26,.30);}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);overflow-x:hidden;
  font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.wrap{max-width:1440px;margin:0 auto;padding:0 20px}
header.mast{border-bottom:1px solid var(--line);background:var(--surface)}
.mast-in{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end;justify-content:space-between;padding:26px 0 20px}
h1{margin:0;font-size:26px;line-height:1.15;letter-spacing:-.02em;font-weight:640;text-wrap:balance}
.sub{margin:6px 0 0;color:var(--muted);font-size:13.5px;max-width:64ch}
.eyebrow{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);font-weight:640;margin:0 0 8px}
.stats{display:flex;flex-wrap:wrap;gap:8px}
.stat{background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:8px 12px;min-width:92px}
.stat .k{display:block;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600}
.stat .v{display:block;font-size:19px;font-weight:640;letter-spacing:-.01em;margin-top:1px;font-variant-numeric:tabular-nums}
.controls{position:sticky;top:0;z-index:30;background:var(--surface);border-bottom:1px solid var(--line);box-shadow:0 1px 0 var(--line)}
.controls-in{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:flex-end;padding:12px 0}
/* ---- mobile filter menu (2026-08-24): below 720px the filter panel collapses behind a
   Filters button; the results count stays visible in the bar. Desktop is unchanged. ---- */
.fbar{display:none}
.fbtn{font:inherit;font-size:14px;font-weight:640;color:var(--accent);background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:999px;padding:8px 16px;cursor:pointer;
  display:inline-flex;align-items:center;gap:7px}
.fbadge{background:var(--accent);color:var(--surface);border-radius:999px;font-size:11px;
  font-weight:700;padding:1px 7px;line-height:1.5}
.chev{display:inline-block;transition:transform .15s}
.count-m{font-size:13px;color:var(--muted)}
.count-m b{color:var(--ink);font-weight:640}
@media (max-width:719px){
  .fbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0}
  .controls-in{display:none}
  .controls.open .controls-in{display:flex;padding-top:0;max-height:65vh;overflow:auto;
    -webkit-overflow-scrolling:touch}
  .controls.open .chev{transform:rotate(180deg)}
}

.field{display:flex;flex-direction:column;gap:5px}
.field label{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:640}
select,input[type=search]{font:inherit;font-size:13.5px;color:var(--ink);background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:8px;padding:7px 10px;min-width:132px}
input[type=search]{min-width:190px}
select:focus-visible,input:focus-visible,button:focus-visible,a:focus-visible,.mapdot:focus-visible{
  outline:2px solid var(--accent);outline-offset:2px}
.toggles{display:flex;gap:7px;flex-wrap:wrap}
.toggle{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:999px;padding:6px 11px;cursor:pointer;user-select:none}
.toggle input{accent-color:var(--accent);margin:0}
.toggle:has(input:checked){background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:620}
.appliedbar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;padding:0 0 11px;min-height:0}
.appliedbar:empty{display:none}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;background:var(--accent-soft);
  color:var(--accent);border:1px solid var(--accent);border-radius:999px;padding:4px 6px 4px 10px}
.chip button{all:unset;cursor:pointer;line-height:1;font-size:14px;padding:0 3px;border-radius:50%}
.chip button:hover{background:rgba(0,0,0,.12)}
.clearall{all:unset;cursor:pointer;font-size:12px;font-weight:640;color:var(--muted);text-decoration:underline;padding:4px}
.count{margin-left:auto;font-size:13px;color:var(--muted);padding-bottom:7px}
.count b{color:var(--ink);font-weight:640;font-variant-numeric:tabular-nums}
.note{background:var(--warn-soft);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent);
  color:var(--warn);border-radius:10px;padding:11px 13px;font-size:12.5px;margin:16px 0 0;max-width:86ch}
/* ---- two-column: sticky map beside the list ---- */
.layout{display:grid;grid-template-columns:1fr;gap:18px;padding:16px 0 48px;align-items:start}
@media(min-width:1080px){.layout{grid-template-columns:minmax(430px,46%) 1fr}}
@media(min-width:1500px){.layout{grid-template-columns:minmax(560px,50%) 1fr}}
.mapcol{position:relative}
@media(min-width:1080px){.mapcol{position:sticky;top:104px}}
.mapwrap{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;box-shadow:var(--shadow)}
.maphead{display:flex;gap:10px;align-items:baseline;justify-content:space-between;margin-bottom:9px}
.maphead h2{margin:0;font-size:13px;font-weight:640;letter-spacing:.02em}
.maptoggle{font:inherit;font-size:11.5px;font-weight:620;color:var(--accent);background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:999px;padding:4px 10px;cursor:pointer}
.mapbox{position:relative;width:100%;overflow:hidden;border-radius:9px;background:var(--surface-2)}
/* On a short viewport the sticky map must still leave the list visible, so cap by height. */
@media(min-width:1080px){.mapbox{max-height:calc(100vh - 210px)}
  .mapbox svg{max-height:calc(100vh - 210px);width:100%;height:auto;object-fit:contain}}
.mapbox svg{display:block;width:100%;height:auto}
.riverpath{fill:none;stroke:#4a84b8;stroke-opacity:.32;stroke-width:9;stroke-linecap:round;stroke-linejoin:round}
.railpath{fill:none;stroke-width:2.2;stroke-opacity:.45;stroke-linecap:round;stroke-linejoin:round}
.mapdot{cursor:pointer;stroke:var(--surface);stroke-width:1.1}
.mapdot:hover,.mapdot.hot{stroke:var(--ink);stroke-width:2.2}
.mapdot.dim{opacity:.18}
.d-a{fill:#1a9e7a}.d-b{fill:#6bbf59}.d-c{fill:#e0a800}.d-d{fill:#d2691e}
.maplbl{font-size:9px;fill:var(--muted);letter-spacing:.04em;pointer-events:none}
.maptip{position:absolute;pointer-events:none;background:var(--ink);color:var(--ground);border-radius:7px;
  padding:6px 9px;font-size:11.5px;line-height:1.35;max-width:230px;opacity:0;transition:opacity .1s;z-index:5}
.maptip b{display:block;font-size:12px;margin-bottom:2px}
.maplegend{display:flex;flex-wrap:wrap;gap:9px;margin-top:9px;font-size:11px;color:var(--muted)}
.maplegend .k{display:inline-flex;align-items:center;gap:5px}
.maplegend .sw{width:9px;height:9px;border-radius:50%;display:inline-block}
.areabars{margin-top:11px;display:flex;flex-direction:column;gap:4px}
.abar{display:grid;grid-template-columns:104px 1fr 28px;gap:7px;align-items:center;font-size:11px;color:var(--muted);
  background:none;border:0;padding:2px 0;cursor:pointer;text-align:left;width:100%}
.abar:hover .abar-t{color:var(--accent)}
.abar .track{height:6px;background:var(--surface-2);border-radius:3px;overflow:hidden}
.abar .fill{height:100%;background:var(--accent);border-radius:3px}
.abar .n{text-align:right;font-variant-numeric:tabular-nums}
.abar.on .abar-t{color:var(--accent);font-weight:700}
/* ---- cards ---- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;
  display:flex;flex-direction:column;box-shadow:var(--shadow);scroll-margin-top:120px}
.card.hot{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft),var(--shadow)}
.card.flash{outline:3px solid var(--accent);outline-offset:2px}
.shot{position:relative;aspect-ratio:16/10;background:var(--surface-2);overflow:hidden}
.shot img{width:100%;height:100%;object-fit:cover;display:block}
.noshot{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--muted);
  font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.score{position:absolute;top:9px;left:9px;background:var(--ink);color:var(--ground);border-radius:8px;
  padding:3px 8px;font-size:14px;font-weight:680;font-variant-numeric:tabular-nums}
.score small{display:block;font-size:8px;letter-spacing:.1em;text-transform:uppercase;opacity:.72;font-weight:600}
.newtag{position:absolute;top:9px;right:9px;background:var(--accent);color:var(--surface);border-radius:999px;
  padding:3px 9px;font-size:10px;letter-spacing:.09em;text-transform:uppercase;font-weight:660}
.rentbadge{position:absolute;bottom:9px;left:9px;background:color-mix(in srgb,var(--ink) 88%,transparent);
  color:var(--ground);border-radius:8px;padding:4px 9px;font-size:15px;font-weight:680;font-variant-numeric:tabular-nums}
.rentbadge span{font-size:10.5px;font-weight:500;opacity:.8}
.body{padding:11px 13px 13px;display:flex;flex-direction:column;gap:8px;flex:1}
.title{margin:0;font-size:14.5px;font-weight:640;line-height:1.3;overflow-wrap:anywhere}
.title a{color:inherit;text-decoration:none}
.title a:hover{color:var(--accent);text-decoration:underline}
.where{font-size:12px;color:var(--muted);margin:0;overflow-wrap:anywhere}
.specs{display:flex;flex-wrap:wrap;gap:5px}
.spec{font-size:11px;font-weight:600;border-radius:6px;padding:3px 7px;background:var(--surface-2);
  border:1px solid var(--line);color:var(--ink-2);font-variant-numeric:tabular-nums}
.spec.w-a{background:var(--ok-soft);border-color:color-mix(in srgb,var(--ok) 30%,transparent);color:var(--ok)}
.spec.w-b{background:var(--warn-soft);border-color:color-mix(in srgb,var(--warn) 30%,transparent);color:var(--warn)}
.spec.w-c{background:var(--bad-soft);border-color:color-mix(in srgb,var(--bad) 30%,transparent);color:var(--bad)}
.movein{font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.movein b{color:var(--ink-2);font-weight:640}
details.why{margin-top:auto}
details.why summary{font-size:11.5px;color:var(--accent);cursor:pointer;font-weight:600;list-style:none}
details.why summary::-webkit-details-marker{display:none}
details.why summary::before{content:"\25B8 "}
details.why[open] summary::before{content:"\25BE "}
details.why p{margin:6px 0 0;font-size:12px;color:var(--ink-2);line-height:1.5;overflow-wrap:anywhere}
.srcline{font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding-top:7px;margin-top:auto}
.empty{grid-column:1/-1;padding:52px 18px;text-align:center;color:var(--muted);background:var(--surface);
  border:1px dashed var(--line-strong);border-radius:12px}
.empty b{display:block;color:var(--ink);font-size:15px;margin-bottom:6px}
footer{border-top:1px solid var(--line);background:var(--surface);padding:22px 0 34px;color:var(--muted);font-size:12.5px}
footer p{margin:0 0 8px;max-width:82ch}footer b{color:var(--ink-2)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
@media(max-width:620px){h1{font-size:21px}.count{margin-left:0;width:100%}
  select,input[type=search]{min-width:0;width:100%}.field{flex:1 1 132px}}
</style>

<header class="mast"><div class="wrap mast-in">
  <div>
    <p class="eyebrow">Weekly rental scan &middot; __TODAY__</p>
    <h1>Bangkok rentals a foreigner can take today</h1>
    <p class="sub">Long-term lets from <b>$350 to $650 a month</b> &mdash; studios through 2-beds, no
    minimum bedroom count. Converted at <span class="mono">__RATE__</span> THB/USD this run, a band of
    <span class="mono">__BAND__</span>/month. Scored on rent per m&sup2;, walk to transit, size,
    move-in cash, furnishing and building age.</p>
  </div>
  <div class="stats">
    <div class="stat"><span class="k">Listings</span><span class="v">__TOTAL__</span></div>
    <div class="stat"><span class="k">New</span><span class="v">__NEW__</span></div>
    <div class="stat"><span class="k">Median rent</span><span class="v">$__MEDRENT__</span></div>
    <div class="stat"><span class="k">Mapped</span><span class="v">__PLACED__</span></div>
    <div class="stat"><span class="k">Photos</span><span class="v">__PHOTOS__</span></div>
  </div>
</div></header>

<div class="controls"><div class="wrap">
  <div class="fbar">
    <div class="count-m" id="count-m"></div>
    <button class="fbtn" id="fbtn" aria-expanded="false" aria-controls="controls-in">Filters<span class="fbadge" id="fbadge" hidden></span><span class="chev">&#9662;</span></button>
  </div>
  <div class="controls-in">
    <div class="field"><label for="f-search">Search</label>
      <input type="search" id="f-search" placeholder="Project, street, station&hellip;"></div>
    <div class="field"><label for="f-area">Area</label>
      <select id="f-area"><option value="all">All Bangkok</option></select></div>
    <div class="field"><label for="f-beds">Bedrooms</label>
      <select id="f-beds"><option value="any">Any</option><option value="0">Studio only</option>
        <option value="1">1-bed or more</option><option value="2">2-bed or more</option></select></div>
    <div class="field"><label for="f-rent">Max rent</label>
      <select id="f-rent"><option value="0">Any</option><option value="400">$400</option>
        <option value="450">$450</option><option value="500">$500</option>
        <option value="550">$550</option><option value="600">$600</option></select></div>
    <div class="field"><label for="f-walk">Walk to rail</label>
      <select id="f-walk"><option value="0">Any</option><option value="5">5 min or less</option>
        <option value="10">10 min or less</option><option value="15">15 min or less</option></select></div>
    <div class="field"><label for="f-furn">Furnishing</label>
      <select id="f-furn"><option value="any">Any</option><option value="fully">Fully furnished</option>
        <option value="some">Furnished or part</option><option value="unfurnished">Unfurnished</option></select></div>
    <div class="field"><label for="f-sort">Sort</label>
      <select id="f-sort"><option value="score">Score, best first</option>
        <option value="rentup">Rent, low to high</option><option value="rentdown">Rent, high to low</option>
        <option value="persqm">Cheapest per m&sup2;</option><option value="size">Largest first</option>
        <option value="walk">Closest to rail</option><option value="fresh">Newest to the list</option></select></div>
    <div class="toggles">
      <label class="toggle"><input type="checkbox" id="f-new"> New</label>
      <label class="toggle"><input type="checkbox" id="f-photo"> Has photo</label>
      <label class="toggle"><input type="checkbox" id="f-owner"> Owner-direct</label>
      <label class="toggle"><input type="checkbox" id="f-bkk"> Bangkok province</label>
      <label class="toggle"><input type="checkbox" id="f-clean"> Hide flagged</label>
    </div>
    <div class="count" id="count"></div>
  </div>
  <div class="appliedbar" id="applied"></div>
</div></div>

<main class="wrap">
  <p class="note"><b>Read the move-in line, not just the rent.</b> Bangkok normally asks two months'
  deposit plus one month in advance, so a &#3647;15,000 flat can cost &#3647;60,000 to walk into. Where a
  listing did not state its deposit we leave it blank rather than assume &mdash; blank means
  <i>ask</i>, not <i>none</i>. Rents exclude utilities. Nothing here has been viewed or verified in person.</p>

  <div class="layout">
    <div class="mapcol"><div class="mapwrap">
      <div class="maphead"><h2>Where they are</h2>
        <button class="maptoggle" id="maptoggle" aria-expanded="true">Hide</button></div>
      <div class="mapbox" id="mapbox"></div>
      <div class="maplegend">
        <span class="k"><i class="sw" style="background:#1a9e7a"></i>&le;$425</span>
        <span class="k"><i class="sw" style="background:#6bbf59"></i>&le;$500</span>
        <span class="k"><i class="sw" style="background:#e0a800"></i>&le;$575</span>
        <span class="k"><i class="sw" style="background:#d2691e"></i>&gt;$575</span>
        <span class="k" style="margin-left:4px">Dot = nearest station, not the address</span>
      </div>
      <div class="areabars" id="areabars"></div>
    </div></div>
    <div><div class="grid" id="grid"></div></div>
  </div>
</main>

<footer><div class="wrap">
  <p><b>How to read a dot.</b> Portals do not publish building coordinates, so each listing is placed
  at the station named in its listing (or its district centre when none is named), fanned out when
  several share a station. Treat it as &ldquo;near here&rdquo;, accurate to a few hundred metres.</p>
  <p>Rents are asking rents as published, re-checked weekly; listings that stop appearing keep their
  last-seen date. Scores are comparable within this run only. This page researches and ranks &mdash;
  it never contacts a landlord or agent, and never pays a deposit.</p>
</div></footer>

<script id="rows" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("rows").textContent),TODAY="__TODAY__",GEO=__GEOM__;
D.forEach((d,i)=>d.i=i);
const AREAS=[["CBD Sukhumvit",["asok","asoke","nana","phrom phong","thong lo","thonglor","ekkamai","ploenchit","chit lom","lumphini","pathum wan","watthana","khlong tan","ratchathewi","phaya thai","victory monument","siam"]],
["Upper Sukhumvit",["on nut","bang chak","punnawithi","udom suk","bearing","phra khanong","samrong","lasalle","la salle"]],
["Sathorn / Silom / River",["sathorn","sathon","silom","taksin","surasak","chong nonsi","sala daeng","charoen nakhon","krung thon","wongwian yai","khlong san","bang kho laem","yannawa","yan nawa","rama 3","talat phlu","thonburi","bang rak","suriyawong","sam yan"]],
["Ratchada / Rama 9",["rama 9","phra ram 9","huai khwang","ratchada","sutthisan","din daeng","makkasan","phetchaburi","cultural"]],
["Ari / Chatuchak",["ari","saphan khwai","mo chit","sanam pao","phahon","chatuchak","ratchayothin","lat yao","kaset","sena nikhom","chom phon","chan kasem","bang sue","sam sen nai"]],
["Lat Phrao / north-east",["lat phrao","ladprao","chok chai","wang thonglang","bang kapi","ramkhamhaeng","hua mak","bueng kum","bang khen","nawamin","phlapphla","saphan song","anusawari"]],
["Bangna / south-east",["bangna","bang na","srinakarin","si nakharin","nong bon","rama 4","suan luang","prawet","si iam","si udom","pattanakarn"]],
["West / old town",["pinklao","bangkok noi","bang phlat","charan","bang yi khan","phasi charoen","bang khae","phetkasem","petchkasem","lak song","phra nakhon","sam yot","taling chan"]]];
/* District+position first; title only as a fallback. Thai project names collide with place
   names ("Lumpini Place Rama IX" is an LPN building in Huai Khwang, not in Lumphini). */
function areaOf(d){const where=((d.d||"")+" "+(d.p||"")).toLowerCase();
  for(const[n,kws]of AREAS)for(const w of kws)if(where.includes(w))return n;
  const t=(d.t||"").toLowerCase();
  for(const[n,kws]of AREAS)for(const w of kws)if(t.includes(w))return n;
  return "Other Bangkok";}
D.forEach(d=>d.a=areaOf(d));
const g=id=>document.getElementById(id);
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const areaSel=g("f-area");
[...new Set(D.map(d=>d.a))].sort().forEach(a=>{const o=document.createElement("option");o.value=a;o.textContent=a;areaSel.appendChild(o);});
const bedLabel=b=>b===0?"Studio":(b+"-bed");
const rentBand=u=>u<=425?"d-a":u<=500?"d-b":u<=575?"d-c":"d-d";
const walkCls=w=>w==null?"":(w<=5?"w-a":w<=12?"w-b":"w-c");

/* ---------- filter state ---------- */
const F={search:"",area:"all",beds:"any",rent:"0",walk:"0",furn:"any",sort:"score",
         new:false,photo:false,owner:false,bkk:false,clean:false};
const IDS={search:"f-search",area:"f-area",beds:"f-beds",rent:"f-rent",walk:"f-walk",
           furn:"f-furn",sort:"f-sort",new:"f-new",photo:"f-photo",owner:"f-owner",bkk:"f-bkk",
           clean:"f-clean"};
function readControls(){for(const k in IDS){const e=g(IDS[k]);F[k]=e.type==="checkbox"?e.checked:e.value;}}
function writeControls(){for(const k in IDS){const e=g(IDS[k]);if(e.type==="checkbox")e.checked=F[k];else e.value=F[k];}}
const DEFAULTS={search:"",area:"all",beds:"any",rent:"0",walk:"0",furn:"any",
                new:false,photo:false,owner:false,bkk:false,clean:false};
const CHIPLABEL={search:v=>'"'+v+'"',area:v=>v,beds:v=>v==="0"?"Studio only":v+"-bed or more",
  rent:v=>"Under $"+v,walk:v=>"≤"+v+" min walk",
  furn:v=>({fully:"Fully furnished",some:"Furnished or part",unfurnished:"Unfurnished"}[v]),
  new:()=>"New this week",photo:()=>"Has photo",owner:()=>"Owner-direct",bkk:()=>"Bangkok province",
  clean:()=>"No caveats"};

function applies(d){
  if(F.area!=="all"&&d.a!==F.area)return false;
  if(F.beds==="0"&&d.bd!==0)return false;
  if(F.beds==="1"&&(d.bd||0)<1)return false;
  if(F.beds==="2"&&(d.bd||0)<2)return false;
  if(+F.rent&&(d.u||0)>+F.rent)return false;
  if(+F.walk&&(d.w==null||d.w>+F.walk))return false;
  if(F.furn==="fully"&&d.fu!=="fully")return false;
  if(F.furn==="some"&&!(d.fu==="fully"||d.fu==="partly"))return false;
  if(F.furn==="unfurnished"&&d.fu!=="unfurnished")return false;
  if(F.new&&d.f!==TODAY)return false;
  if(F.photo&&!d.img)return false;
  if(F.owner&&d.li!=="owner")return false;
  if(F.bkk&&d.out)return false;
  if(F.clean&&(d.fg||[]).length)return false;
  if(F.search){const h=(d.t+" "+d.d+" "+d.p+" "+d.n+" "+d.src).toLowerCase();
    if(!h.includes(F.search.toLowerCase().trim()))return false;}
  return true;
}
const SORTS={score:(a,b)=>(b.s||0)-(a.s||0)||(a.ps||9e9)-(b.ps||9e9),
  rentup:(a,b)=>(a.u||9e9)-(b.u||9e9),rentdown:(a,b)=>(b.u||0)-(a.u||0),
  persqm:(a,b)=>(a.ps||9e9)-(b.ps||9e9),size:(a,b)=>(b.m||0)-(a.m||0),
  walk:(a,b)=>(a.w==null?999:a.w)-(b.w==null?999:b.w)||(b.s||0)-(a.s||0),
  fresh:(a,b)=>String(b.f).localeCompare(String(a.f))||(b.s||0)-(a.s||0)};

/* ---------- chips ---------- */
function drawChips(){
  const bar=g("applied");let h="";
  for(const k in DEFAULTS){
    if(String(F[k])===String(DEFAULTS[k]))continue;
    h+='<span class="chip">'+esc(CHIPLABEL[k](F[k]))+'<button data-k="'+k+'" aria-label="Remove filter">&times;</button></span>';
  }
  bar.innerHTML=h?h+'<button class="clearall" id="clearall">Clear all</button>':"";
  bar.querySelectorAll(".chip button").forEach(b=>b.addEventListener("click",()=>{
    F[b.dataset.k]=DEFAULTS[b.dataset.k];writeControls();render();}));
  const ca=g("clearall");
  if(ca)ca.addEventListener("click",()=>{Object.assign(F,DEFAULTS);writeControls();render();});
}

/* ---------- render ---------- */
let VISIBLE=[];
function render(){
  readControls();
  VISIBLE=D.filter(applies).sort(SORTS[F.sort]);
  g("count").innerHTML="<b>"+VISIBLE.length+"</b> of "+D.length+" rentals";
  drawChips();
  const grid=g("grid");
  if(!VISIBLE.length){
    grid.innerHTML='<div class="empty"><b>Nothing matches those filters.</b>'+
      'Try widening the rent ceiling or the walking distance &mdash; the walk filter only keeps listings '+
      'that actually published a distance, so it hides a lot.</div>';
  } else {
    grid.innerHTML=VISIBLE.map(d=>{
      const specs=[];
      specs.push('<span class="spec">'+bedLabel(d.bd)+'</span>');
      if(d.m)specs.push('<span class="spec">'+d.m+' m&sup2;</span>');
      if(d.ps)specs.push('<span class="spec">&#3647;'+d.ps.toLocaleString()+'/m&sup2;</span>');
      if(d.w!=null)specs.push('<span class="spec '+walkCls(d.w)+'">'+d.w+' min to rail</span>');
      if(d.fu)specs.push('<span class="spec">'+({fully:"Furnished",partly:"Part furnished",unfurnished:"Unfurnished"}[d.fu]||d.fu)+'</span>');
      if(d.out)specs.push('<span class="spec w-c">Outside Bangkok</span>');
      // Caveats the research agents raised, surfaced rather than buried in the notes.
      (d.fg||[]).forEach(f=>specs.push('<span class="spec '+(f==="may not be a real let"?"w-c":"w-b")+'">⚑ '+esc(f)+'</span>'));
      const mv=d.mi?('Move in with <b>&#3647;'+d.mi.toLocaleString()+'</b> ('+(1+(d.dep||0)+(d.adv||0))+'&times; rent)')
        :'Move-in cost <b>not stated</b> &mdash; ask before viewing';
      return '<article class="card" id="card-'+d.i+'" data-i="'+d.i+'">'+
        '<div class="shot">'+(d.img?'<img loading="lazy" src="'+d.img+'" alt="">':'<div class="noshot">No photo</div>')+
        '<div class="score">'+(d.s==null?"&mdash;":d.s)+'<small>score</small></div>'+
        (d.f===TODAY?'<div class="newtag">New</div>':'')+
        '<div class="rentbadge">$'+(d.u||0).toLocaleString()+'<span>/mo &middot; &#3647;'+(d.b||0).toLocaleString()+'</span></div></div>'+
        '<div class="body">'+
        '<h3 class="title"><a href="'+esc(d.l)+'" target="_blank" rel="noopener">'+esc(d.t)+'</a></h3>'+
        '<p class="where">'+esc(d.d)+(d.p?' &middot; '+esc(d.p):'')+'</p>'+
        '<div class="specs">'+specs.join("")+'</div>'+
        '<div class="movein">'+mv+'</div>'+
        (d.n?'<details class="why"><summary>Notes &amp; caveats</summary><p>'+esc(d.n)+'</p></details>':'')+
        '<div class="srcline">'+esc(d.src)+(d.li?' &middot; '+esc(d.li):'')+' &middot; first seen '+esc(d.f)+
        (d.ls!==TODAY?' &middot; last seen '+esc(d.ls):'')+'</div>'+
        '</div></article>';}).join("");
    grid.querySelectorAll(".card").forEach(c=>{
      c.addEventListener("mouseenter",()=>hot(+c.dataset.i,true));
      c.addEventListener("mouseleave",()=>hot(+c.dataset.i,false));
    });
  }
  drawAreaBars();
  drawMap();
}
function hot(i,on){
  const dot=document.querySelector('.mapdot[data-i="'+i+'"]');if(dot)dot.classList.toggle("hot",on);
  const card=g("card-"+i);if(card)card.classList.toggle("hot",on);
}
function drawAreaBars(){
  const counts={};VISIBLE.forEach(d=>counts[d.a]=(counts[d.a]||0)+1);
  const rows=Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  const max=rows.length?rows[0][1]:1;
  g("areabars").innerHTML=rows.map(([a,n])=>
    '<button class="abar'+(F.area===a?" on":"")+'" data-a="'+esc(a)+'">'+
    '<span class="abar-t">'+esc(a)+'</span><span class="track"><span class="fill" style="width:'+
    Math.round(n/max*100)+'%"></span></span><span class="n">'+n+'</span></button>').join("");
  g("areabars").querySelectorAll(".abar").forEach(b=>b.addEventListener("click",()=>{
    F.area=(F.area===b.dataset.a)?"all":b.dataset.a;writeControls();render();}));
}

/* ---------- map ----------
   1 deg lat = 110.6 km; 1 deg lon at 13.76N = 108.2 km. Bounds hug the inventory. */
const LON0=100.370,LON1=100.700,LAT0=13.630,LAT1=13.890;
const MW=1000,MH=Math.round(MW*((LAT1-LAT0)*110.6)/((LON1-LON0)*108.2));
const px=lon=>(lon-LON0)/(LON1-LON0)*MW, py=lat=>(LAT1-lat)/(LAT1-LAT0)*MH;
const mapbox=g("mapbox");
const STATIC=(()=>{
  let s='<path class="riverpath" d="'+GEO.river.map((p,i)=>(i?"L":"M")+px(p[1]).toFixed(1)+" "+py(p[0]).toFixed(1)).join(" ")+'"/>';
  for(const ln of GEO.lines){if(ln.pts.length<2)continue;
    s+='<path class="railpath" stroke="'+ln.color+'" d="'+ln.pts.map((p,i)=>(i?"L":"M")+px(p[1]).toFixed(1)+" "+py(p[0]).toFixed(1)).join(" ")+'"/>';}
  const labels=[["Sukhumvit",13.7371,100.5601],["Silom",13.7237,100.5290],["Rama 9",13.7580,100.5652],
    ["Chatuchak",13.8140,100.5620],["On Nut",13.7057,100.6013],["Bang Kapi",13.7660,100.6420],
    ["Bang Na",13.6680,100.6046],["Pinklao",13.7800,100.4850]];
  return s+labels.map(([t,la,lo])=>'<text class="maplbl" x="'+(px(lo)+7).toFixed(1)+'" y="'+(py(la)-6).toFixed(1)+'">'+t+'</text>').join("");
})();
function drawMap(){
  if(mapbox.dataset.hidden==="1")return;
  const placed=VISIBLE.filter(d=>d.la!=null);
  // Shrink markers as the map fills up: 1,400 dots at full size is a smear.
  const R=placed.length>900?2.7:placed.length>400?3.4:4.4, SP=placed.length>900?3.6:5;
  const groups=new Map();
  placed.forEach(d=>{const k=d.la.toFixed(4)+","+d.lo.toFixed(4);
    if(!groups.has(k))groups.set(k,[]);groups.get(k).push(d);});
  let dots="";
  for(const[,gp]of groups){const n=gp.length;
    gp.forEach((d,i)=>{let x=px(d.lo),y=py(d.la);
      if(n>1){const ring=Math.floor(i/8),ang=(i%8)/8*2*Math.PI+ring*.4,rad=SP+ring*(SP*1.5);
        x+=Math.cos(ang)*rad;y+=Math.sin(ang)*rad;}
      dots+='<circle class="mapdot '+rentBand(d.u||0)+'" tabindex="0" role="button" cx="'+x.toFixed(1)+
        '" cy="'+y.toFixed(1)+'" r="'+(d.gp==="district"?R*0.82:R)+'" data-i="'+d.i+'"'+
        (d.gp==="district"?' opacity=".7"':'')+'><title>'+esc(d.t)+'</title></circle>';});}
  mapbox.innerHTML='<svg viewBox="0 0 '+MW+' '+MH+'" role="img" aria-label="Map of '+placed.length+
    ' rentals by nearest station">'+STATIC+dots+'</svg><div class="maptip"></div>';
  const tip=mapbox.querySelector(".maptip");
  mapbox.querySelectorAll(".mapdot").forEach(el=>{
    const i=+el.dataset.i,d=D[i];
    const show=()=>{const b=mapbox.getBoundingClientRect(),c=el.getBoundingClientRect();
      tip.innerHTML="<b>"+esc(d.t.slice(0,58))+"</b>$"+(d.u||0)+"/mo &middot; "+bedLabel(d.bd)+
        (d.m?" &middot; "+d.m+" m&sup2;":"")+(d.w!=null?"<br>"+d.w+" min to rail":"")+
        (d.gp==="district"?"<br><i>district-level position</i>":"");
      tip.style.opacity="1";
      let L=c.left-b.left+c.width/2-tip.offsetWidth/2,T=c.top-b.top-tip.offsetHeight-9;
      tip.style.left=Math.max(4,Math.min(L,b.width-tip.offsetWidth-4))+"px";
      tip.style.top=(T<4?c.top-b.top+c.height+9:T)+"px";
      hot(i,true);};
    const hide=()=>{tip.style.opacity="0";hot(i,false);};
    const jump=()=>{const card=g("card-"+i);if(!card)return;
      card.scrollIntoView({behavior:"smooth",block:"center"});
      document.querySelectorAll(".card.flash").forEach(c=>c.classList.remove("flash"));
      card.classList.add("flash");setTimeout(()=>card.classList.remove("flash"),2000);};
    el.addEventListener("mouseenter",show);el.addEventListener("focus",show);
    el.addEventListener("mouseleave",hide);el.addEventListener("blur",hide);
    el.addEventListener("click",jump);
    el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();jump();}});
  });
}
g("maptoggle").addEventListener("click",function(){
  const hidden=mapbox.dataset.hidden==="1";
  mapbox.dataset.hidden=hidden?"0":"1";mapbox.style.display=hidden?"":"none";
  this.textContent=hidden?"Hide":"Show";this.setAttribute("aria-expanded",hidden?"true":"false");
  if(hidden)drawMap();});
Object.values(IDS).forEach(id=>{const e=g(id);
  e.addEventListener("input",render);e.addEventListener("change",render);});
render();
</script>
<script>
/* mobile filter menu: toggle, active-filter badge, and a mirror of the results count */
(function(){
 var c=document.querySelector('.controls'),b=document.getElementById('fbtn'),
     bd=document.getElementById('fbadge'),cm=document.getElementById('count-m'),
     ct=document.getElementById('count'),defaults=null;
 if(!c||!b)return;
 function ctl(){return Array.prototype.slice.call(c.querySelectorAll('.controls-in select, .controls-in input'));}
 function snap(){var m={};ctl().forEach(function(e){m[e.id]=(e.type==='checkbox')?e.checked:e.value;});return m;}
 function badge(){ if(!defaults)return; var n=0;
   ctl().forEach(function(e){ if(e.id==='f-sort')return;
     var v=(e.type==='checkbox')?e.checked:e.value;
     if(String(v)!==String(defaults[e.id]))n++; });
   bd.hidden=!n; bd.textContent=n; }
 function mirror(){ if(cm&&ct)cm.innerHTML=ct.innerHTML; }
 b.addEventListener('click',function(){var o=c.classList.toggle('open');b.setAttribute('aria-expanded',String(o));});
 c.addEventListener('change',badge); c.addEventListener('input',badge);
 if(ct&&window.MutationObserver)new MutationObserver(mirror).observe(ct,{childList:true,subtree:true,characterData:true});
 window.addEventListener('load',function(){defaults=snap();badge();mirror();});
})();
</script>
"""

if __name__ == "__main__":
    main()
