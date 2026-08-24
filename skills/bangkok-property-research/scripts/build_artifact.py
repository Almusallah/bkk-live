#!/usr/bin/env python3
"""
Build the Bangkok property Artifact page: one self-contained HTML file with every
listing photo inlined as a data: URI, plus client-side filters and sort orders.

    python3 build_artifact.py --rows final_rows.json --out bangkok.html [--width 320] [--quality 62]

Why data URIs: a published Artifact page runs under a strict CSP that blocks EVERY
external host, so <img src="https://..."> renders nothing. Photos must be inlined.
Do NOT set referrerpolicy="no-referrer" on portal images — cdn.fazwaz.com hotlink-
protects and 403s any request without a fazwaz.com Referer.
"""
import argparse, base64, io, json, os, sys, html, datetime
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

def fetch_thumb(url, width, quality):
    """Fetch + downscale one photo, caching the ORIGINAL bytes on disk so re-runs
    (and quality re-tunes) do not re-download. Returns a data: URI."""
    if not url:
        return None
    try:
        import requests
        from PIL import Image
        os.makedirs(CACHE_DIR, exist_ok=True)
        cp = _cache_path(url)
        raw = None
        if os.path.exists(cp) and os.path.getsize(cp) > 0:
            raw = open(cp, "rb").read()
        if raw is None:
            raw = _download(url)
            open(cp, "wb").write(raw)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = im.size
        nh = max(1, round(h * width / w))
        im = im.resize((width, nh), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        log(f"thumb fail {str(url)[:70]}: {e}")
        return None

def _download(url):
    try:
        import requests
        from PIL import Image
        host = urlsplit(url).netloc
        ref = "https://www.fazwaz.com/" if "fazwaz" in host else f"https://{host}/"
        r = requests.get(url, timeout=15, headers={
            "User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            "Referer": ref, "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "cross-site",
        })
        r.raise_for_status()
        return r.content
    except Exception:
        raise

OUTSIDE = ("samut prakan", "nonthaburi", "pathum thani", "outside bangkok province")

def is_outside(r):
    hay = " ".join(str(r.get(k) or "") for k in ("district", "position", "notes")).lower()
    return any(k in hay for k in OUTSIDE)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--quality", type=int, default=62)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--rate", type=float, default=None)
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
            "la": la, "lo": lo, "gp": prec, "gk": key,
            "s": r.get("score"), "t": r.get("title") or "", "d": r.get("district") or "",
            "p": r.get("position") or "", "u": r.get("price_usd"), "b": r.get("price_thb"),
            "m": r.get("sqm"), "ps": r.get("price_per_sqm_thb"), "bd": r.get("bedrooms"),
            "q": r.get("foreign_freehold") or "unknown", "l": r.get("link") or "",
            "src": r.get("source") or "", "n": r.get("notes") or "",
            "f": r.get("first_seen") or "", "ls": r.get("last_seen") or "",
            "img": thumbs.get(r.get("image_url")) or "",
            "out": 1 if is_outside(r) else 0,
        })

    new_ct = sum(1 for d in data if d["f"] == a.today)
    week_ct = sum(1 for d in data if d["ls"] == a.today)
    ff = sum(1 for d in data if d["q"] == "foreign_freehold")
    unk = sum(1 for d in data if d["q"] == "unknown")
    thai = sum(1 for d in data if d["q"] == "leasehold_or_thai_only")
    rate_txt = f"{a.rate:,.4f}" if a.rate else "—"
    band_txt = (f"฿{80000*a.rate/1e6:.2f}M–฿{200000*a.rate/1e6:.2f}M"
                if a.rate else "—")

    geoms = {
        "lines": [{"name": n, "color": c,
                   "pts": [geo.STATIONS[s] for s in stops if s in geo.STATIONS]}
                  for n, c, stops in geo.LINES],
        "river": geo.RIVER,
        "stations": {k: geo.STATIONS[k] for k in sorted({d["gk"] for d in data if d["gk"]})
                     if k in geo.STATIONS},
    }
    placed = sum(1 for d in data if d["la"] is not None)
    log(f"geocoded: {placed}/{len(data)} placed "
        f"({sum(1 for d in data if d['gp']=='station')} station-level, "
        f"{sum(1 for d in data if d['gp']=='district')} district-level)")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    doc = TEMPLATE.replace("__GEOM__", json.dumps(geoms, separators=(",", ":"))) \
                  .replace("__PLACED__", str(placed)) \
                  .replace("__DATA__", payload) \
                  .replace("__TODAY__", a.today).replace("__TOTAL__", str(len(data))) \
                  .replace("__NEW__", str(new_ct)).replace("__WEEK__", str(week_ct)) \
                  .replace("__FF__", str(ff)).replace("__UNK__", str(unk)) \
                  .replace("__THAI__", str(thai)).replace("__RATE__", rate_txt) \
                  .replace("__BAND__", band_txt).replace("__PHOTOS__", str(ok))
    open(a.out, "w", encoding="utf-8").write(doc)
    log(f"wrote {a.out}  ({len(doc)/1e6:.2f} MB)")

TEMPLATE = r"""<meta charset="utf-8">
<title>Bangkok buy-box — foreigner-buyable 2-bed condos</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{
  --ground:#EFF0F4; --surface:#FBFBFD; --surface-2:#F4F5F9; --line:#DBDDE6; --line-strong:#C3C6D4;
  --ink:#12131A; --ink-2:#3B3F52; --muted:#666B80;
  --accent:#26469B; --accent-soft:#E4E9F7;
  --ok:#136B4E; --ok-soft:#DDEFE7; --warn:#8A5A06; --warn-soft:#F6EBD5; --bad:#9A3628; --bad-soft:#F5E1DD;
  --shadow:0 1px 2px rgba(18,19,26,.06),0 8px 24px -16px rgba(18,19,26,.30);
}
@media (prefers-color-scheme:dark){
  :root{
    --ground:#0D0F15; --surface:#161923; --surface-2:#1D2130; --line:#282D3C; --line-strong:#3A4054;
    --ink:#E8EAF2; --ink-2:#BFC4D6; --muted:#8D93A8;
    --accent:#8AA6F2; --accent-soft:#1C2540;
    --ok:#6FCFA8; --ok-soft:#12291F; --warn:#E3B45C; --warn-soft:#2C2312; --bad:#E88A78; --bad-soft:#2E1A16;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.9);
  }
}
:root[data-theme="dark"]{
  --ground:#0D0F15; --surface:#161923; --surface-2:#1D2130; --line:#282D3C; --line-strong:#3A4054;
  --ink:#E8EAF2; --ink-2:#BFC4D6; --muted:#8D93A8;
  --accent:#8AA6F2; --accent-soft:#1C2540;
  --ok:#6FCFA8; --ok-soft:#12291F; --warn:#E3B45C; --warn-soft:#2C2312; --bad:#E88A78; --bad-soft:#2E1A16;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -18px rgba(0,0,0,.9);
}
:root[data-theme="light"]{
  --ground:#EFF0F4; --surface:#FBFBFD; --surface-2:#F4F5F9; --line:#DBDDE6; --line-strong:#C3C6D4;
  --ink:#12131A; --ink-2:#3B3F52; --muted:#666B80;
  --accent:#26469B; --accent-soft:#E4E9F7;
  --ok:#136B4E; --ok-soft:#DDEFE7; --warn:#8A5A06; --warn-soft:#F6EBD5; --bad:#9A3628; --bad-soft:#F5E1DD;
  --shadow:0 1px 2px rgba(18,19,26,.06),0 8px 24px -16px rgba(18,19,26,.30);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
header.mast{border-bottom:1px solid var(--line);background:var(--surface)}
.mast-in{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end;justify-content:space-between;padding:26px 0 20px}
h1{margin:0;font-size:26px;line-height:1.15;letter-spacing:-.02em;font-weight:640;text-wrap:balance}
.sub{margin:6px 0 0;color:var(--muted);font-size:13.5px;max-width:62ch}
.eyebrow{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--accent);font-weight:640;margin:0 0 8px}
.stats{display:flex;flex-wrap:wrap;gap:8px}
.stat{background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:8px 12px;min-width:96px}
.stat .k{display:block;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600}
.stat .v{display:block;font-size:19px;font-weight:640;letter-spacing:-.01em;margin-top:1px}
.stat.ok .v{color:var(--ok)} .stat.warn .v{color:var(--warn)} .stat.bad .v{color:var(--bad)}
.controls{position:sticky;top:0;z-index:20;background:var(--surface);border-bottom:1px solid var(--line);box-shadow:0 1px 0 var(--line)}
.controls-in{display:flex;flex-wrap:wrap;gap:14px 18px;align-items:flex-end;padding:14px 0}
.field{display:flex;flex-direction:column;gap:5px}
.field label{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:640}
select,input[type=search]{font:inherit;font-size:13.5px;color:var(--ink);background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:8px;padding:7px 10px;min-width:150px}
input[type=search]{min-width:210px}
select:focus-visible,input:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.toggles{display:flex;gap:8px;flex-wrap:wrap}
.toggle{display:inline-flex;align-items:center;gap:7px;font-size:13px;background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:999px;padding:7px 13px;cursor:pointer;user-select:none}
.toggle input{accent-color:var(--accent);margin:0}
.count{margin-left:auto;font-size:13px;color:var(--muted);padding-bottom:8px}
.count b{color:var(--ink);font-weight:640}
.note{background:var(--warn-soft);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent);color:var(--warn);
  border-radius:10px;padding:12px 14px;font-size:12.5px;margin:18px 0 0;max-width:80ch}
.note b{color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px;padding:22px 0 48px}
/* Left edge encodes ownership — the one axis that decides whether a foreigner can buy at all. */
.card{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--edge,var(--line));
  border-radius:12px;overflow:hidden;display:flex;flex-direction:column;box-shadow:var(--shadow)}
.card.q-ok{--edge:var(--ok)} .card.q-unk{--edge:var(--warn)} .card.q-thai{--edge:var(--bad)}
.shot{position:relative;aspect-ratio:16/10;background:var(--surface-2);overflow:hidden}
.shot img{width:100%;height:100%;object-fit:cover;display:block}
.noshot{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--muted);
  font-size:11.5px;letter-spacing:.08em;text-transform:uppercase}
.score{position:absolute;top:10px;left:10px;background:var(--ink);color:var(--ground);border-radius:8px;
  padding:4px 9px;font-size:15px;font-weight:680;letter-spacing:-.01em}
.score small{display:block;font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;opacity:.72;font-weight:600}
.newtag{position:absolute;top:10px;right:10px;background:var(--accent);color:#fff;border-radius:999px;
  padding:3px 9px;font-size:10px;letter-spacing:.09em;text-transform:uppercase;font-weight:660}
@media (prefers-color-scheme:dark){.newtag{color:#0D0F15}}
:root[data-theme="dark"] .newtag{color:#0D0F15}
:root[data-theme="light"] .newtag{color:#fff}
.body{padding:13px 14px 14px;display:flex;flex-direction:column;gap:9px;flex:1}
.title{margin:0;font-size:15px;font-weight:640;letter-spacing:-.01em;line-height:1.3;overflow-wrap:anywhere}
.title a{color:inherit;text-decoration:none;background-image:linear-gradient(var(--line-strong),var(--line-strong));
  background-size:100% 1px;background-repeat:no-repeat;background-position:0 100%}
.title a:hover{color:var(--accent);background-image:linear-gradient(var(--accent),var(--accent))}
.where{font-size:12.5px;color:var(--muted);margin:0;overflow-wrap:anywhere}
.where .pos{display:block;margin-top:2px}
.figs{display:grid;grid-template-columns:auto auto auto;gap:2px 14px;align-items:baseline;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:9px 0}
.figs .n{font-size:16px;font-weight:660;letter-spacing:-.02em}
.figs .n.small{font-size:14px;font-weight:620}
.figs .lbl{grid-row:2;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pill{font-size:11px;font-weight:620;border-radius:999px;padding:3px 9px;border:1px solid transparent;letter-spacing:.01em}
.pill.q-ok{background:var(--ok-soft);color:var(--ok);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
.pill.q-unk{background:var(--warn-soft);color:var(--warn);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}
.pill.q-thai{background:var(--bad-soft);color:var(--bad);border-color:color-mix(in srgb,var(--bad) 30%,transparent)}
.pill.flag{background:var(--surface-2);color:var(--ink-2);border-color:var(--line-strong)}
.pill.meta{background:transparent;color:var(--muted);border-color:var(--line)}
details.why{margin-top:auto}
details.why summary{font-size:12px;color:var(--accent);cursor:pointer;font-weight:600;list-style:none}
details.why summary::-webkit-details-marker{display:none}
details.why summary::before{content:"\25B8 ";display:inline-block}
details.why[open] summary::before{content:"\25BE "}
details.why p{margin:7px 0 0;font-size:12.5px;color:var(--ink-2);line-height:1.5;overflow-wrap:anywhere}
/* ---- map ---- */
.mapwrap{background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:14px 14px 10px;margin-top:18px;box-shadow:var(--shadow)}
.maphead{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.maphead h2{margin:0;font-size:14px;font-weight:640;letter-spacing:-.01em}
.maphead .hint{font-size:11.5px;color:var(--muted);max-width:66ch}
.maptoggle{font:inherit;font-size:12px;font-weight:620;color:var(--accent);background:var(--surface-2);
  border:1px solid var(--line-strong);border-radius:999px;padding:5px 12px;cursor:pointer}
/* Cap the width: the projection is ~1000x805, so full-bleed on a wide screen makes the
   map ~1000px tall and pushes the listings off the page. */
.mapbox{position:relative;width:100%;max-width:860px;margin:0 auto;overflow:hidden;
  border-radius:9px;background:var(--surface-2)}
.mapbox svg{display:block;width:100%;height:auto}
.mapdot{cursor:pointer;stroke:var(--surface);stroke-width:1.1;transition:r .12s}
.mapdot:hover{stroke:var(--ink);stroke-width:1.8}
.mapdot.d-ok{fill:var(--ok)} .mapdot.d-unk{fill:var(--warn)} .mapdot.d-thai{fill:var(--bad)}
.maplbl{font-size:9px;fill:var(--muted);letter-spacing:.04em;pointer-events:none}
.riverpath{fill:none;stroke:#4a84b8;stroke-opacity:.34;stroke-width:9;stroke-linecap:round;stroke-linejoin:round}
.railpath{fill:none;stroke-width:2.2;stroke-opacity:.5;stroke-linecap:round;stroke-linejoin:round}
.maplegend{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:9px;font-size:11.5px;color:var(--muted)}
.maplegend .k{display:inline-flex;align-items:center;gap:5px}
.maplegend .sw{width:9px;height:9px;border-radius:50%;display:inline-block}
.maplegend .ln{width:15px;height:3px;border-radius:2px;display:inline-block}
.maptip{position:absolute;pointer-events:none;background:var(--ink);color:var(--ground);
  border-radius:7px;padding:6px 9px;font-size:11.5px;line-height:1.35;max-width:230px;
  opacity:0;transition:opacity .1s;z-index:5;box-shadow:0 6px 20px -8px rgba(0,0,0,.6)}
.maptip b{display:block;font-size:12px;margin-bottom:2px}
.card.flash{outline:3px solid var(--accent);outline-offset:2px}
.empty{padding:60px 0;text-align:center;color:var(--muted)}
footer{border-top:1px solid var(--line);background:var(--surface);padding:22px 0 34px;color:var(--muted);font-size:12.5px}
footer p{margin:0 0 8px;max-width:78ch}
footer b{color:var(--ink-2)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
@media (max-width:620px){
  .mast-in{padding:20px 0 16px} h1{font-size:22px}
  .count{margin-left:0;width:100%;padding-bottom:0}
  select,input[type=search]{min-width:0;width:100%} .field{flex:1 1 140px}
}
</style>

<header class="mast">
  <div class="wrap mast-in">
    <div>
      <p class="eyebrow">Weekly scan &middot; __TODAY__</p>
      <h1>Bangkok condos a foreigner can actually buy</h1>
      <p class="sub">Two bedrooms or more, USD 80,000&ndash;200,000, condominium title only. Converted at
      <span class="mono">__RATE__</span> THB/USD this run &mdash; a band of
      <span class="mono">__BAND__</span>. Scored 0&ndash;100 on value, quota certainty, transit, size, yield, age and resale.</p>
    </div>
    <div class="stats">
      <div class="stat"><span class="k">Listings</span><span class="v mono">__TOTAL__</span></div>
      <div class="stat"><span class="k">New this week</span><span class="v mono">__NEW__</span></div>
      <div class="stat ok"><span class="k">Foreign quota</span><span class="v mono">__FF__</span></div>
      <div class="stat warn"><span class="k">Quota unknown</span><span class="v mono">__UNK__</span></div>
      <div class="stat bad"><span class="k">Thai / lease</span><span class="v mono">__THAI__</span></div>
    </div>
  </div>
</header>

<div class="controls">
  <div class="wrap controls-in">
    <div class="field"><label for="f-quota">Ownership</label>
      <select id="f-quota">
        <option value="all">Everything</option>
        <option value="nothai">Exclude Thai-only / leasehold</option>
        <option value="fq">Confirmed foreign freehold only</option>
        <option value="unk">Quota unknown only</option>
      </select></div>
    <div class="field"><label for="f-area">Area</label>
      <select id="f-area"><option value="all">All Bangkok</option></select></div>
    <div class="field"><label for="f-beds">Bedrooms</label>
      <select id="f-beds"><option value="2">2 or more</option><option value="3">3 or more</option></select></div>
    <div class="field"><label for="f-price">Price</label>
      <select id="f-price">
        <option value="all">Full band</option>
        <option value="80000-120000">$80k &ndash; $120k</option>
        <option value="120000-160000">$120k &ndash; $160k</option>
        <option value="160000-200000">$160k &ndash; $200k</option>
      </select></div>
    <div class="field"><label for="f-sort">Sort</label>
      <select id="f-sort">
        <option value="score">Score, best first</option>
        <option value="persqm">Cheapest per m&sup2;</option>
        <option value="priceup">Price, low to high</option>
        <option value="pricedown">Price, high to low</option>
        <option value="size">Largest first</option>
        <option value="fresh">Newest to the list</option>
      </select></div>
    <div class="field"><label for="f-search">Search</label>
      <input type="search" id="f-search" placeholder="Project, street, BTS station&hellip;"></div>
    <div class="toggles">
      <label class="toggle"><input type="checkbox" id="f-new"> New this week</label>
      <label class="toggle"><input type="checkbox" id="f-seen"> Re-checked this run</label>
      <label class="toggle"><input type="checkbox" id="f-bkk"> Bangkok province only</label>
      <label class="toggle"><input type="checkbox" id="f-photo"> With photo</label>
    </div>
    <div class="count" id="count"></div>
  </div>
</div>

<main class="wrap">
  <p class="note"><b>Read the ownership pill before the price.</b> A foreigner cannot own land in Thailand, so only
  condominium units qualify, and only while the building sits inside its 49% foreign-ownership quota.
  <b>Quota unknown</b> means the portal never stated ownership &mdash; that is an open question for the agent, not a
  green light. Nothing here has been verified against a chanote.</p>

  <section class="mapwrap">
    <div class="maphead">
      <div>
        <h2>Where they are</h2>
        <p class="hint">__PLACED__ of __TOTAL__ listings placed. Each dot sits on the listing&rsquo;s
        <b>nearest station</b> (or its district centre when no station is named) &mdash; <b>not</b> the building&rsquo;s
        actual address, which no portal publishes. Dots at the same station are fanned out so they stay countable.
        Colour is ownership. Click a dot to jump to its card; the map follows the filters above.</p>
      </div>
      <button class="maptoggle" id="maptoggle" aria-expanded="true">Hide map</button>
    </div>
    <div class="mapbox" id="mapbox"><div class="maptip" id="maptip"></div></div>
    <div class="maplegend">
      <span class="k"><i class="sw" style="background:var(--ok)"></i>Foreign freehold</span>
      <span class="k"><i class="sw" style="background:var(--warn)"></i>Quota unknown</span>
      <span class="k"><i class="sw" style="background:var(--bad)"></i>Thai / leasehold</span>
      <span class="k" style="margin-left:6px"><i class="ln" style="background:#7ac143"></i>BTS Sukhumvit</span>
      <span class="k"><i class="ln" style="background:#0f7a3d"></i>BTS Silom</span>
      <span class="k"><i class="ln" style="background:#1f5fbf"></i>MRT Blue</span>
      <span class="k"><i class="ln" style="background:#e0b100"></i>MRT Yellow</span>
      <span class="k"><i class="ln" style="background:#c0392b"></i>Airport link</span>
    </div>
  </section>

  <div class="grid" id="grid"></div>
</main>

<footer><div class="wrap">
  <p><b>Thai quota / leasehold</b> units are kept for reference and scored down by design; they can never outrank a
  confirmed foreign-freehold unit. Scores are comparable within this run only &mdash; the whole list is re-scored with
  one function every week.</p>
  <p>Prices are asking prices as published by the portals, not transacted prices, and are re-checked weekly.
  Listings that stopped appearing keep their last-seen date. This page researches and ranks only &mdash; nothing here
  contacts an agent or commits money.</p>
</div></footer>

<script id="rows" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("rows").textContent), TODAY="__TODAY__";
const GEO=__GEOM__;
D.forEach((d,i)=>d.i=i);
const AREAS=[["CBD Sukhumvit",["asok","phrom phong","thong lo","thonglor","ekkamai","nana","ploenchit","lumphini","pathum wan","watthana","khlong tan","sukhumvit 39","sukhumvit 42"]],
["Upper Sukhumvit",["on nut","bang chak","punnawithi","udom suk","bearing","phra khanong","lasalle","la salle","sukhumvit 50","sukhumvit 65","sukhumvit 101","sukhumvit 105"]],
["Sathorn / Silom / River",["sathorn","sathon","silom","taksin","charoen nakhon","thonburi","khlong san","bang kho laem","yannawa","rama 3","wongwian yai","chong nonsi","bang rak","suriyawong","si lom"]],
["Ratchada / Rama 9",["rama 9","phra ram 9","huai khwang","ratchada","sutthisan","din daeng","makkasan","ratchathewi"]],
["Ari / Phaya Thai / Chatuchak",["ari","saphan khwai","mo chit","phahon","chatuchak","ratchayothin","lat yao","kaset","sena nikhom","chom phon","chan kasem","phaya thai","sam sen nai"]],
["Lat Phrao / North-east",["lat phrao","ladprao","chok chai","wang thonglang","bang kapi","ramkhamhaeng","hua mak","bang khen","bueng kum","nawamin","phlapphla","saphan song","anusawari"]],
["Bangna / South-east",["bangna","bang na","srinakarin","nong bon","rama 4","si iam","suan luang","pattanakarn","prawet","samrong"]],
["West / old town / north",["pinklao","bangkok noi","bang phlat","charan","phasi charoen","bang khae","phetkasem","petchkasem","phra nakhon","bang khun phrom","lak si","don mueang","bang lamphu"]]];
function areaOf(d){const h=((d.d||"")+" "+(d.p||"")+" "+(d.t||"")).toLowerCase();
  for(const[name,kws]of AREAS)for(const w of kws)if(h.includes(w))return name;return "Other Bangkok";}
D.forEach(d=>d.a=areaOf(d));
const sel=document.getElementById("f-area");
[...new Set(D.map(d=>d.a))].sort().forEach(a=>{const o=document.createElement("option");o.value=a;o.textContent=a;sel.appendChild(o);});
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const QP={foreign_freehold:["q-ok","Foreign freehold"],unknown:["q-unk","Quota unknown"],leasehold_or_thai_only:["q-thai","Thai quota / leasehold"]};
const grid=document.getElementById("grid"),count=document.getElementById("count");
const g=id=>document.getElementById(id);
function render(){
  const q=g("f-search").value.toLowerCase().trim(),own=g("f-quota").value,ar=sel.value;
  const bd=+g("f-beds").value,pr=g("f-price").value,so=g("f-sort").value;
  const oNew=g("f-new").checked,oSeen=g("f-seen").checked,oBkk=g("f-bkk").checked,oPh=g("f-photo").checked;
  let r=D.filter(d=>{
    if(own==="fq"&&d.q!=="foreign_freehold")return false;
    if(own==="unk"&&d.q!=="unknown")return false;
    if(own==="nothai"&&d.q==="leasehold_or_thai_only")return false;
    if(ar!=="all"&&d.a!==ar)return false;
    if((d.bd||0)<bd)return false;
    if(pr!=="all"){const[a,b]=pr.split("-").map(Number);if((d.u||0)<a||(d.u||0)>b)return false;}
    if(oNew&&d.f!==TODAY)return false;
    if(oSeen&&d.ls!==TODAY)return false;
    if(oBkk&&d.out)return false;
    if(oPh&&!d.img)return false;
    if(q&&!((d.t+" "+d.d+" "+d.p+" "+d.n+" "+d.src).toLowerCase().includes(q)))return false;
    return true;});
  const S={score:(a,b)=>(b.s||0)-(a.s||0)||(a.ps||0)-(b.ps||0),
    persqm:(a,b)=>(a.ps||1e9)-(b.ps||1e9),priceup:(a,b)=>(a.u||1e9)-(b.u||1e9),
    pricedown:(a,b)=>(b.u||0)-(a.u||0),size:(a,b)=>(b.m||0)-(a.m||0),
    fresh:(a,b)=>String(b.f).localeCompare(String(a.f))||(b.s||0)-(a.s||0)};
  r.sort(S[so]);
  count.innerHTML="<b>"+r.length+"</b> of "+D.length+" listings";
  if(!r.length){grid.innerHTML='<p class="empty">No listing matches those filters.</p>';return;}
  grid.innerHTML=r.map(d=>{
    const[qc,ql]=QP[d.q]||QP.unknown;
    const pills=['<span class="pill '+qc+'">'+ql+'</span>'];
    if(d.out)pills.push('<span class="pill flag">Outside Bangkok province</span>');
    if(d.ls===TODAY&&d.f!==TODAY)pills.push('<span class="pill meta">Re-checked '+esc(d.ls)+'</span>');
    if(d.ls!==TODAY)pills.push('<span class="pill meta">Last seen '+esc(d.ls)+'</span>');
    pills.push('<span class="pill meta">'+esc(d.src)+'</span>');
    return '<article class="card '+qc+'" id="card-'+d.i+'">'+
      '<div class="shot">'+(d.img?'<img loading="lazy" src="'+d.img+'" alt="">':'<div class="noshot">No photo</div>')+
      '<div class="score">'+(d.s==null?"&mdash;":d.s)+'<small>score</small></div>'+
      (d.f===TODAY?'<div class="newtag">New</div>':'')+'</div>'+
      '<div class="body">'+
      '<h2 class="title"><a href="'+esc(d.l)+'" target="_blank" rel="noopener">'+esc(d.t)+'</a></h2>'+
      '<p class="where">'+esc(d.d)+'<span class="pos">'+esc(d.p)+'</span></p>'+
      '<div class="figs">'+
        '<span class="n mono">$'+(d.u||0).toLocaleString()+'</span>'+
        '<span class="n small mono">'+(d.m||"?")+' m&sup2;</span>'+
        '<span class="n small mono">&#3647;'+(d.ps||0).toLocaleString()+'</span>'+
        '<span class="lbl">'+(d.bd||"?")+'-bed price</span><span class="lbl">size</span><span class="lbl">per m&sup2;</span>'+
      '</div>'+
      '<div class="pills">'+pills.join("")+'</div>'+
      (d.n?'<details class="why"><summary>Notes &amp; caveats</summary><p>'+esc(d.n)+'</p></details>':'')+
      '</div></article>';}).join("");
  drawMap(r);
}

/* ---------- map ----------
   Equirectangular projection, scaled by cos(lat) so Bangkok is not stretched. The map is
   schematic: dots are station/district positions, never surveyed building coordinates. */
/* Bounds hug the inventory (lon 100.40-100.65, lat 13.65-13.87) plus margin, rather than
   greater Bangkok — otherwise a third of the canvas is empty eastern suburbs. The Airport
   Rail Link tail past Ban Thap Chang runs off-canvas and is clipped, which is fine. */
const LON0=100.370,LON1=100.700,LAT0=13.630,LAT1=13.890;
/* 1 deg lat = 110.6 km; 1 deg lon at 13.76N = 111.32*cos(13.76) = 108.2 km. */
const MW=1000, MH=Math.round(MW*((LAT1-LAT0)*110.6)/((LON1-LON0)*108.2));
function px(lon){return (lon-LON0)/(LON1-LON0)*MW;}
function py(lat){return (LAT1-lat)/(LAT1-LAT0)*MH;}
const QD={foreign_freehold:"d-ok",unknown:"d-unk",leasehold_or_thai_only:"d-thai"};
const mapbox=document.getElementById("mapbox");
let staticLayer="";
(function buildStatic(){
  let s='<path class="riverpath" d="'+GEO.river.map((p,i)=>(i?"L":"M")+px(p[1]).toFixed(1)+" "+py(p[0]).toFixed(1)).join(" ")+'"/>';
  for(const ln of GEO.lines){
    if(ln.pts.length<2)continue;
    s+='<path class="railpath" stroke="'+ln.color+'" d="'+ln.pts.map((p,i)=>(i?"L":"M")+px(p[1]).toFixed(1)+" "+py(p[0]).toFixed(1)).join(" ")+'"/>';
  }
  staticLayer=s;
})();
function drawMap(rows){
  if(mapbox.dataset.hidden==="1")return;
  const placed=rows.filter(d=>d.la!=null);
  // fan out dots that share a coordinate so a busy station stays countable
  const groups=new Map();
  placed.forEach(d=>{const k=d.la.toFixed(4)+","+d.lo.toFixed(4);
    if(!groups.has(k))groups.set(k,[]);groups.get(k).push(d);});
  let dots="";
  for(const[,g]of groups){
    const n=g.length;
    g.forEach((d,i)=>{
      let x=px(d.lo),y=py(d.la);
      if(n>1){const ring=Math.floor(i/8),ang=(i%8)/8*2*Math.PI+ring*0.4,rad=5+ring*7.5;
        x+=Math.cos(ang)*rad;y+=Math.sin(ang)*rad;}
      const rr=d.gp==="district"?3.6:4.4;
      dots+='<circle class="mapdot '+(QD[d.q]||"d-unk")+'" cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+
        '" r="'+rr+'" data-i="'+d.i+'"'+(d.gp==="district"?' opacity=".72"':'')+'></circle>';
    });
  }
  const labels=[["Sukhumvit CBD",13.7371,100.5601],["Silom / Sathorn",13.7237,100.5290],
    ["Rama 9",13.7580,100.5652],["Chatuchak",13.8140,100.5620],["On Nut",13.7057,100.6013],
    ["Bang Kapi",13.7660,100.6420],["Bang Na",13.6680,100.6046],["Pinklao",13.7800,100.4850],
    ["Chao Phraya",13.7000,100.4980]];
  const lbl=labels.map(([t,la,lo])=>'<text class="maplbl" x="'+(px(lo)+7).toFixed(1)+'" y="'+(py(la)-7).toFixed(1)+'">'+t+'</text>').join("");
  mapbox.innerHTML='<svg viewBox="0 0 '+MW+' '+MH+'" role="img" aria-label="Schematic map of Bangkok showing '+placed.length+' listings by nearest station">'+
    staticLayer+lbl+dots+'</svg><div class="maptip" id="maptip"></div>';
  const tip=mapbox.querySelector(".maptip");
  mapbox.querySelectorAll(".mapdot").forEach(el=>{
    el.addEventListener("mouseenter",e=>{
      const d=D[+el.dataset.i];const b=mapbox.getBoundingClientRect();const c=el.getBoundingClientRect();
      tip.innerHTML="<b>"+esc(d.t.slice(0,64))+"</b>$"+(d.u||0).toLocaleString()+" &middot; "+(d.m||"?")+" m&sup2; &middot; "+(d.bd||"?")+"-bed<br>"+
        esc(d.p||d.d)+(d.gp==="district"?"<br><i>district-level position</i>":"");
      tip.style.opacity="1";
      let L=c.left-b.left+c.width/2-tip.offsetWidth/2, T=c.top-b.top-tip.offsetHeight-9;
      tip.style.left=Math.max(4,Math.min(L,b.width-tip.offsetWidth-4))+"px";
      tip.style.top=(T<4?c.top-b.top+c.height+9:T)+"px";
    });
    el.addEventListener("mouseleave",()=>{tip.style.opacity="0";});
    el.addEventListener("click",()=>{
      const card=document.getElementById("card-"+el.dataset.i);
      if(!card)return;
      card.scrollIntoView({behavior:"smooth",block:"center"});
      document.querySelectorAll(".card.flash").forEach(c=>c.classList.remove("flash"));
      card.classList.add("flash");setTimeout(()=>card.classList.remove("flash"),2200);
    });
  });
}
document.getElementById("maptoggle").addEventListener("click",function(){
  const hidden=mapbox.dataset.hidden==="1";
  mapbox.dataset.hidden=hidden?"0":"1";
  mapbox.style.display=hidden?"":"none";
  this.textContent=hidden?"Hide map":"Show map";
  this.setAttribute("aria-expanded",hidden?"true":"false");
  if(hidden)render();
});
["f-search","f-quota","f-area","f-beds","f-price","f-sort","f-new","f-seen","f-bkk","f-photo"]
  .forEach(id=>{const e=g(id);e.addEventListener("input",render);e.addEventListener("change",render);});
render();
</script>
"""

if __name__ == "__main__":
    main()
