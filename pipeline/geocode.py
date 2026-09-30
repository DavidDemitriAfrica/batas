"""Find the towns, cities and provinces each law names, and match them to the PSGC.

Titles name places in a handful of fixed ways ("Municipality of Baler,
Province of Aurora", "City of Iligan", "Barangay Tamdagan", "in Malinao,
Aklan"). We pull those mentions out, then match them to the 1,642 cities and
municipalities in the 2025 PSGC (via the Philippine Internal Migration
Dataset, which also records former names). A town name is accepted only when
it is unique nationally or sits inside a province the same title names.

Province names in old laws refer to old boundaries ("Province of Davao" in
1960 covers five provinces today), so each historical name maps to the set
of current provinces carved from it.

Output: data/interim/laws_geo.json with, for each law,
  munis      list of matched psgc10 codes
  provinces  list of current provinces the law is about
  geo_level  "muni", "province", or "none"
"""

import csv
import re
import unicodedata
from collections import defaultdict

from common import INTERIM, RAW, read_json, write_json

# Geographic province of each highly urbanized or independent city.
CITY_PROVINCE = {
    "City of Baguio": "Benguet", "City of Angeles": "Pampanga", "City of Olongapo": "Zambales",
    "City of Lucena": "Quezon", "City of Puerto Princesa": "Palawan", "City of Iloilo": "Iloilo",
    "City of Bacolod": "Negros Occidental", "City of Cebu": "Cebu", "City of Lapu-Lapu": "Cebu",
    "City of Mandaue": "Cebu", "City of Tacloban": "Leyte", "City of Isabela": "Basilan",
    "City of Zamboanga": "Zamboanga del Sur", "City of Cagayan De Oro": "Misamis Oriental",
    "City of Iligan": "Lanao del Norte", "City of Davao": "Davao del Sur",
    "City of General Santos": "South Cotabato", "City of Butuan": "Agusan del Norte",
}
NCR = "Metro Manila"
SGA = "Cotabato"  # the BARMM Special Geographic Area lies inside Cotabato province

# Provinces carved out of older ones since 1946: (parent, child, year).
# A law naming the parent before the split year also covers the child.
SPLITS = [
    ("Capiz", "Aklan", 1956), ("Leyte", "Southern Leyte", 1959), ("Leyte", "Biliran", 1992),
    ("Negros Oriental", "Siquijor", 1971), ("Iloilo", "Guimaras", 1992), ("Quezon", "Aurora", 1979),
    ("Nueva Vizcaya", "Quirino", 1971), ("Sulu", "Tawi-Tawi", 1973), ("Cotabato", "South Cotabato", 1966),
    ("Cotabato", "Sultan Kudarat", 1973), ("Cotabato", "Maguindanao", 1973), ("South Cotabato", "Sarangani", 1992),
    ("Maguindanao", "Maguindanao del Norte", 2022), ("Maguindanao", "Maguindanao del Sur", 2022),
    ("Davao", "Davao del Norte", 1967), ("Davao", "Davao del Sur", 1967), ("Davao", "Davao Oriental", 1967),
    ("Davao del Norte", "Davao de Oro", 1998), ("Davao del Sur", "Davao Occidental", 2013),
    ("Zamboanga", "Zamboanga del Norte", 1952), ("Zamboanga", "Zamboanga del Sur", 1952),
    ("Zamboanga del Sur", "Zamboanga Sibugay", 2001), ("Lanao", "Lanao del Norte", 1959), ("Lanao", "Lanao del Sur", 1959),
    ("Samar", "Northern Samar", 1965), ("Samar", "Eastern Samar", 1965), ("Surigao", "Surigao del Norte", 1960),
    ("Surigao", "Surigao del Sur", 1960), ("Surigao del Norte", "Dinagat Islands", 2006),
    ("Agusan", "Agusan del Norte", 1967), ("Agusan", "Agusan del Sur", 1967),
    ("Mountain Province", "Benguet", 1966), ("Mountain Province", "Ifugao", 1966), ("Mountain Province", "Kalinga-Apayao", 1966),
    ("Kalinga-Apayao", "Kalinga", 1995), ("Kalinga-Apayao", "Apayao", 1995), ("Mindoro", "Oriental Mindoro", 1950),
    ("Mindoro", "Occidental Mindoro", 1950), ("Misamis Oriental", "Camiguin", 1966), ("Rizal", NCR, 1975),
]
# Names that no longer exist as provinces, or that changed spelling.
ALIASES = {
    "north cotabato": "Cotabato", "western samar": "Samar", "compostela valley": "Davao de Oro",
    "mindoro oriental": "Oriental Mindoro", "mindoro occidental": "Occidental Mindoro", "tayabas": "Quezon",
    "kalinga apayao": "Kalinga-Apayao", "metropolitan manila": NCR, "metro manila": NCR,
    "national capital region": NCR, "manila": NCR, "leyte del sur": "Southern Leyte", "samar del norte": "Northern Samar",
    "samar del este": "Eastern Samar", "camarines": "Camarines", "ilocos": "Ilocos", "misamis": "Misamis",
    "mountain": "Mountain Province",
}
# Older spellings and former names of towns that the gazetteer does not list.
TOWN_ALIASES = {"kalookan": ("Caloocan", NCR), "legaspi": ("Legazpi", "Albay"), "ozamis": ("Ozamiz", "Misamis Occidental"),
                "paracales": ("Paracale", "Camarines Norte"), "dansalan": ("Marawi", "Lanao del Sur"),
                "despujols": ("San Andres", "Romblon"), "badajoz": ("San Agustin", "Romblon"),
                "brooke": ("Brooke's Point", "Palawan")}
DEFUNCT = {"Davao", "Zamboanga", "Lanao", "Surigao", "Agusan", "Mindoro", "Kalinga-Apayao", "Maguindanao", "Misamis",
           "Camarines", "Ilocos"}
EXTRA_KIDS = {"Misamis": ["Misamis Oriental", "Misamis Occidental"], "Camarines": ["Camarines Norte", "Camarines Sur"],
              "Ilocos": ["Ilocos Norte", "Ilocos Sur"]}


def successors(name, year):
    """Current provinces covering what `name` meant in `year`."""
    kids = [c for p, c, y in SPLITS if p == name and (year is None or year < y)] + EXTRA_KIDS.get(name, [])
    out = set() if name in DEFUNCT else {name}
    for k in kids:
        out |= successors(k, None if year is None else max(year, [y for p, c, y in SPLITS if p == name and c == k][0]
                                                             if [y for p, c, y in SPLITS if p == name and c == k] else year))
    if name in DEFUNCT and not out:
        out = {c for p, c, y in SPLITS if p == name}
    return out


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("±", "n")  # a mis-encoded ñ in some LawPhil titles
    s = re.sub(r"\bsto\.?\s", "santo ", s)
    s = re.sub(r"\bsta\.?\s", "santa ", s)
    s = re.sub(r"\bgen\.?\s", "general ", s)
    s = re.sub(r"\bpres\.?\s", "president ", s)
    s = re.sub(r"\bsn\.?\s", "san ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(name):
    n = fold(re.sub(r"\s*\([^)]*\)", "", name or ""))
    n = re.sub(r"^(island garden city of|science city of|city of|municipality of|town of)\s+", "", n)
    n = re.sub(r"\s+city$", "", n)
    n = re.sub(r"\s*\(.*$", "", n)
    return n.strip()


def load_gazetteer():
    lgus = []
    with open(RAW / "pim" / "municipalities.csv") as fh:
        for r in csv.DictReader(fh):
            name = r["name"].strip()
            prov = r["province"].strip()
            if name in CITY_PROVINCE:
                prov = CITY_PROVINCE[name]
            elif prov.startswith("National Capital Region"):
                prov = NCR
            elif prov.startswith("Bangsamoro"):
                prov = SGA
            olds = [o.strip() for o in (r.get("old_names") or "").split(";") if o.strip()]
            lgus.append({"psgc10": r["psgc10"], "name": name, "province": prov, "level": r["level"],
                         "keys": {core(name)} | {core(o) for o in olds}})
    for alias, (name, prov) in TOWN_ALIASES.items():
        for L in lgus:
            if core(L["name"]) == core(name) and L["province"] == prov:
                L["keys"].add(alias)
    by_key = defaultdict(list)
    for L in lgus:
        for k in L["keys"]:
            by_key[k].append(L)
    provinces = sorted({L["province"] for L in lgus})
    return lgus, by_key, provinces


NAME = r"[A-Z][\wÀ-ſ±.'\-]*(?:\s+(?:(?:de la|dela|del|de|y)\b|[A-Z][\wÀ-ſ±.'\-]*))*"
OF = r"\s+(?i:of)\s+(?:(?i:the)\s+)?"
MUNI_PAT = re.compile(r"\b(?i:Municipalit(?:y|ies)|Towns?|Capital Town|Cities|City|Island Garden City|Science City|Municipal District)" + OF +
                      r"(" + NAME + r"(?:\s*,\s*" + NAME + r")*(?:,?\s+(?i:and)\s+" + NAME + r")?)")
CITY_SUFFIX = re.compile(r"\b(" + NAME + r")\s+(?i:city)\b")
PROV_PAT = re.compile(r"\b(?i:Provinces?|Sub-?provinces?)" + OF + r"(" + NAME + r"(?:\s*,\s*" + NAME + r")*(?:,?\s+(?i:and)\s+" + NAME + r")?)")
PROV_SUFFIX = re.compile(r"\b(" + NAME + r")\s+Province\b")
IN_PAT = re.compile(r"\b(?i:in|at)\s+(" + NAME + r")(?:,\s+(" + NAME + r"))?,\s+(" + NAME + r")")
BRGY_PAT = re.compile(r"\b(?i:Barangays?|Barrios?|Sitios?)\s+(?:(?i:of)\s+)?(" + NAME + r")")
STOP = re.compile(r"\s+(?:to be|and appropriating|appropriating|into|from|in the|for|as|with|which|traversing|stretching|"
                  r"connecting|located|situated|province|to|under|all|comprising|amending|its|the)\b.*$", re.I)


def split_names(s):
    s = STOP.sub("", s)
    parts = re.split(r"\s*,\s*|\s+and\s+", s)
    return [p.strip() for p in parts
            if p.strip() and not re.match(r"(?i)(province|municipality|city|barangay|barrio)\b", p.strip())]


YEAR = [None]  # set per law in main()
CONGRESS_YEAR = {1: 1947, 2: 1951, 3: 1955, 4: 1959, 5: 1963, 6: 1967, 7: 1971, 8: 1990, 9: 1994, 10: 1997,
                 11: 2000, 12: 2003, 13: 2006, 14: 2009, 15: 2012, 16: 2015, 17: 2018, 18: 2021, 19: 2024, 20: 2026}


def province_set(prov_text, provinces_lc):
    k = re.sub(r"^the\s+", "", fold(prov_text))
    name = ALIASES.get(k) or provinces_lc.get(k)
    if name is None:
        known = {fold(p) for p, _, _ in SPLITS} | {fold(c) for _, c, _ in SPLITS}
        if k in known:
            name = next(x for x in [p for p, _, _ in SPLITS] + [c for _, c, _ in SPLITS] if fold(x) == k)
    if name is None:
        return set()
    return successors(name, YEAR[0])


def province_from_suffix(name, provinces_lc):
    words = name.split()
    for n in range(min(4, len(words)), 0, -1):
        ps = province_set(" ".join(words[-n:]), provinces_lc)
        if ps:
            return ps
    return set()


from difflib import SequenceMatcher

_BY_PROV = {}


def fuzzy_in_provinces(key, provs):
    """Misspelled or shortened town names ("Pres. Garcia", "Lapaz") inside named provinces."""
    if len(key) < 4:
        return []
    best, score = None, 0.0
    for p in provs:
        for L in _BY_PROV.get(p, []):
            for k in L["keys"]:
                a, b = set(key.split()), set(k.split())
                s = SequenceMatcher(None, key.replace(" ", ""), k.replace(" ", "")).ratio()
                if a <= b and len(a) >= 2 and a != b:
                    s = max(s, 0.9)
                if s > score:
                    best, score = L, s
    return [best] if best is not None and score >= 0.86 else []


def geocode_title(title, by_key, provinces_lc):
    t = title.replace("\u00b1", "ñ")
    groups = []  # one set of current provinces per province the title names

    def add(ps):
        if ps and ps not in groups:
            groups.append(ps)

    for m in PROV_PAT.finditer(t):
        for p in split_names(m.group(1)):
            add(province_set(p, provinces_lc))
    for m in PROV_SUFFIX.finditer(t):
        add(province_from_suffix(m.group(1), provinces_lc))
    mentions = []  # (name, said_city)
    for m in MUNI_PAT.finditer(t):
        said_city = bool(re.match(r"(?i)(cit|island garden|science)", m.group(0)))
        names = split_names(m.group(1))
        for i, p in enumerate(names):
            ps = province_set(p, provinces_lc)
            # "Municipality of Rosario, Batangas": a province name after a town in that province
            after_town = i > 0 and any(c["province"] in ps for c in by_key.get(core(names[i - 1]), []))
            if ps and (not by_key.get(core(p)) or after_town):
                add(ps)
            else:
                mentions.append((p, said_city))
    for m in CITY_SUFFIX.finditer(t):
        words = m.group(1).split()
        for n in (1, 2, 3):
            if len(words) >= n:
                mentions.append((" ".join(words[-n:]), True))
    for m in IN_PAT.finditer(t):
        ps = province_set(m.group(3), provinces_lc) or province_from_suffix(m.group(3), provinces_lc)
        if ps:
            add(ps)
            mentions.append((m.group(2) or m.group(1), False))
            if m.group(2):
                mentions.append((m.group(1), False))
    if re.search(r"\bMetro(?:politan)? Manila\b|National Capital Region", t):
        add({NCR})
    provs = set().union(*groups) if groups else set()
    munis = {}
    for mention, said_city in mentions:
        cands = by_key.get(core(mention), [])
        if not cands and provs:
            cands = fuzzy_in_provinces(core(mention), provs)
        if not cands:
            continue
        pick = [c for c in cands if c["province"] in provs] if provs else cands
        if len(pick) > 1 and said_city:
            pick = [c for c in pick if c["level"] == "City"]
        if len(pick) == 1:
            munis[pick[0]["psgc10"]] = pick[0]
    if munis:
        mprov = {m["province"] for m in munis.values()}
        # A named province whose successors include a matched town's province is
        # accounted for by that town; any other named province stays in.
        extra = set()
        for g in groups:
            if not (g & mprov):
                extra |= g
        return sorted(munis), sorted(mprov | extra), "muni"
    if provs:
        return [], sorted(provs), "province"
    return [], [], "none"


def main():
    lgus, by_key, provinces = load_gazetteer()
    provinces_lc = {fold(p): p for p in provinces}
    provinces_lc[fold(NCR)] = NCR
    for L in lgus:
        _BY_PROV.setdefault(L["province"], []).append(L)
    laws = read_json(INTERIM / "laws_classified.json")
    for L in laws:
        YEAR[0] = L.get("year") or CONGRESS_YEAR.get(L.get("congress"))
        L["munis"], L["provinces"], L["geo_level"] = geocode_title(L["title"], by_key, provinces_lc)
    write_json(INTERIM / "laws_geo.json", laws)
    loc = [L for L in laws if L["scope"] == "local"]
    from collections import Counter
    c = Counter(L["geo_level"] for L in loc)
    print(f"local laws: {len(loc)}; placed at town level {c['muni']}, province only {c['province']}, unplaced {c['none']}")


if __name__ == "__main__":
    main()
