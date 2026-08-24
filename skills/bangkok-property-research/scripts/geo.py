#!/usr/bin/env python3
"""
Approximate geocoding for Bangkok listings, from the data we already have.

We do NOT have building coordinates — portals rarely publish them. What we do have is
`position` (nearest BTS/MRT/ARL station) and `district`. So a listing is placed at:

  1. its named station          -> precision "station"  (typ. within ~100-600 m of the unit)
  2. its district centre        -> precision "district" (typ. within ~1-2 km)
  3. nothing                    -> precision "none"     (not drawn on the map)

Station and district coordinates below are hand-entered approximations good to roughly
100-300 m — fine for a city-scale orientation map, useless for navigation. Never present
a plotted dot as the property's actual address.
"""
import re, unicodedata

# ---------------------------------------------------------------- stations
# lat, lon (WGS84), approximate.
STATIONS = {
    # BTS Sukhumvit line
    "mo chit": (13.8025, 100.5537), "saphan khwai": (13.7938, 100.5497),
    "ari": (13.7797, 100.5447), "sanam pao": (13.7735, 100.5417),
    "victory monument": (13.7648, 100.5372), "phaya thai": (13.7566, 100.5337),
    "ratchathewi": (13.7519, 100.5316), "siam": (13.7455, 100.5340),
    "chit lom": (13.7442, 100.5432), "chidlom": (13.7442, 100.5432),
    "phloen chit": (13.7433, 100.5488), "ploenchit": (13.7433, 100.5488),
    "nana": (13.7405, 100.5551), "asok": (13.7371, 100.5601), "asoke": (13.7371, 100.5601),
    "phrom phong": (13.7304, 100.5697), "thong lo": (13.7241, 100.5786),
    "thonglor": (13.7241, 100.5786), "thong lor": (13.7241, 100.5786),
    "ekkamai": (13.7194, 100.5853), "phra khanong": (13.7154, 100.5918),
    "on nut": (13.7057, 100.6013), "onnut": (13.7057, 100.6013),
    "bang chak": (13.6968, 100.6053), "punnawithi": (13.6893, 100.6093),
    "udom suk": (13.6797, 100.6098), "udomsuk": (13.6797, 100.6098),
    "bang na": (13.6680, 100.6046), "bearing": (13.6614, 100.6017),
    "samrong": (13.6459, 100.5976), "sena nikhom": (13.8420, 100.5720),
    "ratchayothin": (13.8280, 100.5680), "kasetsart university": (13.8470, 100.5700),
    "kasetsart": (13.8470, 100.5700), "phahon yothin 24": (13.8180, 100.5620),
    "phahonyothin 24": (13.8180, 100.5620), "ha yaek lat phrao": (13.8165, 100.5610),
    "wat phra si mahathat": (13.8740, 100.5940), "khu khot": (13.9236, 100.6198),
    # BTS Silom line
    "national stadium": (13.7464, 100.5292), "ratchadamri": (13.7397, 100.5395),
    "sala daeng": (13.7286, 100.5343), "chong nonsi": (13.7237, 100.5290),
    "saint louis": (13.7203, 100.5250), "st louis": (13.7203, 100.5250),
    "surasak": (13.7190, 100.5162), "saphan taksin": (13.7188, 100.5140),
    "krung thon buri": (13.7207, 100.5087), "krung thonburi": (13.7207, 100.5087),
    "wongwian yai": (13.7211, 100.4999), "pho nimit": (13.7150, 100.4900),
    "talat phlu": (13.7135, 100.4760), "wutthakat": (13.7080, 100.4680),
    "bang wa": (13.7205, 100.4570),
    # MRT Blue line
    "hua lamphong": (13.7376, 100.5170), "sam yan": (13.7327, 100.5300),
    "si lom": (13.7292, 100.5360), "silom": (13.7292, 100.5360),
    "lumphini": (13.7256, 100.5458), "lumpini": (13.7256, 100.5458),
    "khlong toei": (13.7223, 100.5537), "queen sirikit": (13.7231, 100.5601),
    "sukhumvit": (13.7378, 100.5610), "phetchaburi": (13.7485, 100.5637),
    "phra ram 9": (13.7580, 100.5652), "rama 9": (13.7580, 100.5652),
    "thailand cultural centre": (13.7665, 100.5697),
    "thailand cultural center": (13.7665, 100.5697),
    "huai khwang": (13.7768, 100.5743), "huay khwang": (13.7768, 100.5743),
    "sutthisan": (13.7890, 100.5745), "ratchadaphisek": (13.7986, 100.5740),
    "lat phrao": (13.8062, 100.5744), "ladprao": (13.8062, 100.5744),
    "phahon yothin": (13.8137, 100.5620), "phahonyothin": (13.8137, 100.5620),
    "chatuchak park": (13.8025, 100.5537), "kamphaeng phet": (13.8000, 100.5500),
    "bang sue": (13.8025, 100.5380), "tao poon": (13.8060, 100.5300),
    "bang pho": (13.8060, 100.5250), "bang phlat": (13.7935, 100.4980),
    "bang yi khan": (13.7830, 100.4900), "sirindhorn": (13.7850, 100.4830),
    "bang khun non": (13.7620, 100.4740), "fai chai": (13.7690, 100.4760),
    "charan 13": (13.7580, 100.4700), "itsaraphap": (13.7420, 100.4870),
    "sanam chai": (13.7420, 100.4950), "wat mangkon": (13.7420, 100.5100),
    "sam yot": (13.7443, 100.5005), "phasi charoen": (13.7150, 100.4380),
    "bang khae": (13.7160, 100.4090), "lak song": (13.7130, 100.3950),
    # MRT Yellow line (Srinagarindra corridor)
    "phawana": (13.8000, 100.5850), "chok chai 4": (13.7960, 100.5960),
    "lat phrao 71": (13.7900, 100.6060), "lat phrao 83": (13.7850, 100.6130),
    "mahat thai": (13.7800, 100.6180), "lat phrao 101": (13.7760, 100.6250),
    "bang kapi": (13.7660, 100.6420), "yaek lam sali": (13.7580, 100.6440),
    "si kritha": (13.7500, 100.6450), "hua mak": (13.7460, 100.6450),
    "kalantan": (13.7350, 100.6450), "si nut": (13.7200, 100.6450),
    "srinagarindra 38": (13.7000, 100.6450), "si nakharin 38": (13.7000, 100.6450),
    "srinakarin 38": (13.7000, 100.6450), "si udom": (13.6900, 100.6450),
    "si iam": (13.6800, 100.6450), "si la salle": (13.6700, 100.6300),
    "si bearing": (13.6650, 100.6200), "si dan": (13.6560, 100.6100),
    # Airport Rail Link
    "ratchaprarop": (13.7565, 100.5420), "makkasan": (13.7510, 100.5610),
    "ramkhamhaeng": (13.7510, 100.6100), "ban thap chang": (13.7300, 100.6600),
    "lat krabang": (13.7270, 100.7460), "suvarnabhumi": (13.6980, 100.7480),
    # misc
    "khlong san": (13.7300, 100.5050), "charoen nakhon": (13.7270, 100.5100),
}

# Longer names must be tried first so "lat phrao 101" wins over "lat phrao".
STATION_KEYS = sorted(STATIONS, key=len, reverse=True)

# ---------------------------------------------------------------- districts
DISTRICTS = {
    "watthana": (13.7400, 100.5850), "khlong toei": (13.7150, 100.5600),
    "phra khanong": (13.7000, 100.6100), "huai khwang": (13.7770, 100.5800),
    "din daeng": (13.7700, 100.5550), "ratchathewi": (13.7550, 100.5350),
    "pathum wan": (13.7400, 100.5300), "bang rak": (13.7300, 100.5200),
    "sathon": (13.7150, 100.5300), "sathorn": (13.7150, 100.5300),
    "yannawa": (13.6950, 100.5450), "yan nawa": (13.6950, 100.5450),
    "rama 3": (13.6900, 100.5250), "bang kho laem": (13.6950, 100.5050),
    "khlong san": (13.7300, 100.5050), "thon buri": (13.7200, 100.4900),
    "bangkok noi": (13.7650, 100.4750), "bangkok yai": (13.7350, 100.4750),
    "bang phlat": (13.7900, 100.5000), "phasi charoen": (13.7150, 100.4400),
    "bang khae": (13.7100, 100.4100), "chatuchak": (13.8300, 100.5600),
    "lat phrao": (13.8100, 100.6100), "wang thonglang": (13.7800, 100.6100),
    "bang kapi": (13.7650, 100.6450), "bueng kum": (13.7850, 100.6500),
    "bang khen": (13.8700, 100.6000), "lak si": (13.8850, 100.5750),
    "suan luang": (13.7250, 100.6300), "prawet": (13.7150, 100.6800),
    "bang na": (13.6800, 100.6100), "phra nakhon": (13.7550, 100.4980),
    "pom prap": (13.7530, 100.5130), "samphanthawong": (13.7400, 100.5120),
    "don mueang": (13.9150, 100.5900), "min buri": (13.8150, 100.7300),
    "nong bon": (13.7000, 100.6500), "hua mak": (13.7500, 100.6450),
    "lat yao": (13.8400, 100.5650), "chom phon": (13.8100, 100.5700),
    "chan kasem": (13.8200, 100.5800), "chantharakasem": (13.8200, 100.5800),
    "sena nikhom": (13.8420, 100.5720), "sam sen nai": (13.7800, 100.5450),
    "phaya thai": (13.7800, 100.5400), "makkasan": (13.7510, 100.5610),
    "suriyawong": (13.7290, 100.5320), "si lom": (13.7280, 100.5300),
    "thung wat don": (13.7050, 100.5250), "thung maha mek": (13.7180, 100.5380),
    "khlong ton sai": (13.7250, 100.5000), "bang lamphu lang": (13.7290, 100.5030),
    "bang chak": (13.6968, 100.6053), "bang phongphang": (13.6900, 100.5300),
    "phlapphla": (13.7700, 100.6300), "saphan song": (13.7900, 100.6000),
    "chorakhe bua": (13.8100, 100.6200), "anusawari": (13.8740, 100.5940),
    "khlong chaokhun sing": (13.7800, 100.6300), "khlong tan": (13.7280, 100.5800),
    "phra khanong nuea": (13.7180, 100.5950), "bang khun phrom": (13.7620, 100.5030),
    "samrong nuea": (13.6459, 100.5976), "samut prakan": (13.6000, 100.5970),
    "nonthaburi": (13.8600, 100.5150), "pak kret": (13.9130, 100.4980),
    "pathum thani": (13.9900, 100.5300), "lat pla khao": (13.8300, 100.6100),
    "sena nikom": (13.8420, 100.5720), "nong khaem": (13.7050, 100.3600),
    "taling chan": (13.7800, 100.4400), "thawi watthana": (13.7800, 100.3700),
    # Colloquial area names that appear inside PROJECT NAMES (added 2026-08-24 for the
    # LivingInsider title fallback — Thai C2C listings carry no district field at all).
    "ratchada": (13.7770, 100.5740), "huaikwang": (13.7770, 100.5800),
    "ratchayothin": (13.8300, 100.5670), "ratchavipha": (13.8200, 100.5460),
    "prachachuen": (13.8300, 100.5300), "langsuan": (13.7350, 100.5420),
    "pinklao": (13.7770, 100.4780), "talad plu": (13.7180, 100.4760),
    "talat plu": (13.7180, 100.4760), "bangsue": (13.8020, 100.5370),
    "ramintra": (13.8700, 100.6500), "ram inthra": (13.8700, 100.6500),
    "phetkasem": (13.7150, 100.4400), "srinakarin": (13.7000, 100.6450),
    "srinagarindra": (13.7000, 100.6450), "wongwian yai": (13.7210, 100.4990),
    "wutthakat": (13.7080, 100.4770), "charoen nakhon": (13.7270, 100.5090),
    "charoennakhon": (13.7270, 100.5090), "chaengwattana": (13.8850, 100.5500),
    "chaeng watthana": (13.8850, 100.5500), "rat burana": (13.6820, 100.5010),
    "ratburana": (13.6820, 100.5010), "itsaraphap": (13.7400, 100.4830),
    "siriraj": (13.7580, 100.4850), "yen akat": (13.7050, 100.5420),
    "sripatum": (13.8480, 100.5390), "kaset": (13.8480, 100.5720),
    "navamin": (13.8200, 100.6600), "wanghin": (13.8250, 100.6000),
    "seri thai": (13.7900, 100.6700), "bang mod": (13.6650, 100.4900),
    "bangmod": (13.6650, 100.4900), "bang aor": (13.7900, 100.4850),
    "bang khun non": (13.7660, 100.4720), "bangkhunnon": (13.7660, 100.4720),
    "samsen": (13.7780, 100.5100), "ratchaprarop": (13.7560, 100.5430),
    "rajprarop": (13.7560, 100.5430), "wongsawang": (13.8100, 100.5250),
    "pattanakarn": (13.7280, 100.6350), "pattanakran": (13.7280, 100.6350),
    "lasalle": (13.6650, 100.6150), "la salle": (13.6650, 100.6150),
    "bangkae": (13.7100, 100.4100), "bang wa": (13.7200, 100.4550),
    "thapra": (13.7150, 100.4750), "tha phra": (13.7150, 100.4750),
    "sathu": (13.6950, 100.5150), "kluaynamthai": (13.7180, 100.5900),
    "sutthisarn": (13.7890, 100.5730), "interchange": (13.8020, 100.5370),
}
DISTRICT_KEYS = sorted(DISTRICTS, key=len, reverse=True)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).lower()
    s = s.replace("–", " ").replace("—", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def geocode(row):
    """-> (lat, lon, precision, label). precision: station | district | none."""
    pos = _norm(row.get("position"))
    for k in STATION_KEYS:
        if k in pos:
            lat, lon = STATIONS[k]
            return lat, lon, "station", k
    hay = _norm((row.get("district") or "") + " " + (row.get("position") or ""))
    for k in STATION_KEYS:
        if k in hay:
            lat, lon = STATIONS[k]
            return lat, lon, "station", k
    for k in DISTRICT_KEYS:
        if k in hay:
            lat, lon = DISTRICTS[k]
            return lat, lon, "district", k
    # Last resort: Thai C2C listings (LivingInsider) often carry no district and only
    # "BTS"/"MRT" with no station name, but the PROJECT NAME encodes the area
    # ("Supalai Loft Prajadhipok Wongwian Yai", "Aspire Rama 9"). A project name is
    # weaker evidence than a stated nearest station, so anything matched here is
    # reported at "district" precision even when the token is a station name — the
    # page draws those dots smaller and semi-transparent and says so in the tooltip.
    title = _norm(row.get("title"))
    for k in STATION_KEYS:
        if k in title:
            lat, lon = STATIONS[k]
            return lat, lon, "district", k
    for k in DISTRICT_KEYS:
        if k in title:
            lat, lon = DISTRICTS[k]
            return lat, lon, "district", k
    return None, None, "none", ""


# Rail lines drawn on the map, as ordered station keys.
LINES = [
    ("BTS Sukhumvit", "#7ac143", ["khu khot", "wat phra si mahathat", "kasetsart university",
     "sena nikhom", "ratchayothin", "phahon yothin 24", "mo chit", "saphan khwai", "ari",
     "sanam pao", "victory monument", "phaya thai", "ratchathewi", "siam", "chit lom",
     "phloen chit", "nana", "asok", "phrom phong", "thong lo", "ekkamai", "phra khanong",
     "on nut", "bang chak", "punnawithi", "udom suk", "bang na", "bearing", "samrong"]),
    ("BTS Silom", "#0f7a3d", ["national stadium", "siam", "ratchadamri", "sala daeng",
     "chong nonsi", "saint louis", "surasak", "saphan taksin", "krung thon buri",
     "wongwian yai", "pho nimit", "talat phlu", "wutthakat", "bang wa"]),
    ("MRT Blue", "#1f5fbf", ["lak song", "bang khae", "phasi charoen", "bang wa", "itsaraphap",
     "sanam chai", "wat mangkon", "hua lamphong", "sam yan", "si lom", "lumphini",
     "khlong toei", "queen sirikit", "sukhumvit", "phetchaburi", "phra ram 9",
     "thailand cultural centre", "huai khwang", "sutthisan", "ratchadaphisek", "lat phrao",
     "phahon yothin", "chatuchak park", "kamphaeng phet", "bang sue", "tao poon", "bang pho",
     "bang phlat", "bang yi khan", "sirindhorn", "bang khun non", "fai chai", "charan 13"]),
    ("MRT Yellow", "#e0b100", ["lat phrao", "phawana", "chok chai 4", "lat phrao 71",
     "lat phrao 83", "mahat thai", "lat phrao 101", "bang kapi", "yaek lam sali", "si kritha",
     "hua mak", "kalantan", "si nut", "srinagarindra 38", "si udom", "si iam", "si la salle",
     "si bearing", "si dan", "samrong"]),
    ("Airport Rail Link", "#c0392b", ["phaya thai", "ratchaprarop", "makkasan",
     "ramkhamhaeng", "hua mak", "ban thap chang", "lat krabang", "suvarnabhumi"]),
]

# Chao Phraya, north to south through the city — schematic.
RIVER = [(13.860,100.505),(13.840,100.495),(13.822,100.503),(13.806,100.506),(13.795,100.497),
         (13.784,100.492),(13.772,100.492),(13.764,100.487),(13.757,100.489),(13.752,100.494),
         (13.747,100.492),(13.743,100.497),(13.739,100.503),(13.734,100.505),(13.729,100.508),
         (13.725,100.510),(13.721,100.513),(13.717,100.514),(13.713,100.511),(13.709,100.507),
         (13.704,100.504),(13.699,100.502),(13.694,100.505),(13.689,100.512),(13.685,100.521),
         (13.682,100.531),(13.681,100.542),(13.683,100.552),(13.688,100.560)]
