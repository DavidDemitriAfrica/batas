"""Write the data files behind the site (docs/data/*.json) and the clean CSVs.

Everything the page shows is computed here, so each number on the site can be
traced to a script and a source file.
"""

import csv
import gzip
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import date

from classify import CATEGORIES
from common import CLEAN, DOCS, INTERIM, RAW, read_json
from build_laws import smart_title
from geocode import NCR, CITY_PROVINCE, load_gazetteer

OUT = DOCS / "data"

# Seven families for colour; categories inside each family share a hue.
FAMILIES = [
    ("education", "Schools and colleges", ["school", "college"]),
    ("health", "Hospitals", ["hospital"]),
    ("places", "Towns, barangays and districts", ["lgu", "rename_place", "district"]),
    ("infra", "Roads and public works", ["road", "public_works"]),
    ("offices", "Offices, courts and other local", ["office", "court", "holiday", "land", "other_local"]),
    ("private", "Franchises and private grants", ["franchise", "citizenship", "private_other"]),
    ("national", "National laws", ["national", "appropriation", "commemoration"]),
]
FAM_OF = {c: i for i, (_, _, cs) in enumerate(FAMILIES) for c in cs}
CATS = list(CATEGORIES)
CONGRESS_LABEL = {1: "1st", 2: "2nd", 3: "3rd"}


def ordinal(n):
    return CONGRESS_LABEL.get(n, f"{n}th")


CONGRESS_YEARS = {1: "1946-49", 2: "1950-53", 3: "1954-57", 4: "1958-61", 5: "1962-65", 6: "1966-69", 7: "1970-72",
                  8: "1987-92", 9: "1992-95", 10: "1995-98", 11: "1998-01", 12: "2001-04", 13: "2004-07",
                  14: "2007-10", 15: "2010-13", 16: "2013-16", 17: "2016-19", 18: "2019-22", 19: "2022-25", 20: "2025-"}


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def province_populations():
    """Population of each current province at each census, from the migration dataset."""
    lgus, _, _ = load_gazetteer()
    prov_of = {L["psgc10"]: L["province"] for L in lgus}
    pops = defaultdict(lambda: defaultdict(float))
    with open(RAW / "pim" / "municipal_master.csv") as fh:
        for r in csv.DictReader(fh):
            p = prov_of.get(r["psgc10"])
            if not p:
                continue
            for y in (1960, 1970, 1980, 1990, 2000, 2010, 2020, 2024):
                v = r.get(f"pop{y}")
                if v not in (None, ""):
                    pops[p][y] += float(v)
    return {p: {y: round(v) for y, v in d.items()} for p, d in pops.items()}


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    laws.sort(key=lambda L: L["ra"])
    lgus, _, _ = load_gazetteer()
    towns = {L["psgc10"]: L for L in lgus}
    pops = province_populations()
    provinces = sorted(pops)
    pidx = {p: i for i, p in enumerate(provinces)}
    town_codes = sorted({c for L in laws for c in L["munis"]})
    cent = read_json(INTERIM / "town_centroids.json")
    tidx = {c: i for i, c in enumerate(town_codes)}

    # ---- laws.json: one compact row per act
    rows = []
    for L in laws:
        y = L.get("year")
        href = L.get("href") or ""
        m = re.match(r"https://lawphil\.net/statutes/repacts/ra(\d{4})/ra_(\d+)_(\d{4})\.html$", href)
        link = int(m.group(1)) if m else href  # a year means "LawPhil page for that year"
        rows.append([
            L["ra"], L["date"] or "", L.get("congress") or 0, FAM_OF[L["category"]], CATS.index(L["category"]),
            L["title"], 1 if L.get("lapsed") else 0, [pidx[p] for p in L["provinces"] if p in pidx],
            [tidx[c] for c in L["munis"]], link,
        ])
    dump("laws.json", {
        "fields": ["ra", "date", "congress", "family", "category", "title", "lapsed", "provinces", "towns", "link"],
        "families": [{"key": k, "label": lab} for k, lab, _ in FAMILIES],
        "categories": [{"key": c, "label": CATEGORIES[c][0], "scope": CATEGORIES[c][1], "family": FAM_OF[c]} for c in CATS],
        "provinces": provinces,
        # [psgc10, name, province, lon, lat]; the centroid is null when the town has no outline
        "towns": [[c, towns[c]["name"].strip(), towns[c]["province"], *(cent.get(c) or [None, None])] for c in town_codes],
        "rows": rows,
    })

    # ---- per-province counts by Congress and family (fractional when a law names several provinces)
    counts = defaultdict(lambda: defaultdict(float))  # (prov) -> "congress|family" -> n
    for L in laws:
        if L["scope"] != "local" or not L["provinces"]:
            continue
        w = 1 / len(L["provinces"])
        for p in L["provinces"]:
            if p in pidx:
                counts[p][f"{L.get('congress') or 0}|{FAM_OF[L['category']]}"] += w
    dump("provinces.json", {
        "provinces": [{"name": p, "pop": pops[p], "counts": {k: round(v, 3) for k, v in counts[p].items()}}
                      for p in provinces],
        "congress_years": CONGRESS_YEARS,
    })

    # ---- House bills: filed vs enacted, and day-level filing
    bills = list(csv.DictReader(gzip.open(CLEAN / "house_bills_classified.csv.gz", "rt")))
    authors = list(csv.DictReader(open(CLEAN / "law_authors.csv")))
    enacted_bill = {(int(r["congress"]), int(r["house_bill"])) for r in csv.DictReader(open(CLEAN / "law_bills.csv"))}
    # links found only through the act text count too
    law_by_ra = {L["ra"]: L for L in laws}
    funnel = defaultdict(lambda: Counter())
    for b in bills:
        c = int(b["congress"])
        s = b["scope"]
        funnel[c][f"filed_{s}"] += 1
        if (c, int(b["bill"] or 0)) in enacted_bill or b["ra"]:
            funnel[c][f"enacted_{s}"] += 1
    daily = defaultdict(Counter)
    for b in bills:
        if b["date_filed"] and b["congress"] in ("17", "18", "19"):
            daily[b["congress"]][b["date_filed"]] += 1
    first_day = {}
    for c, dct in daily.items():
        d0, n0 = max(dct.items(), key=lambda kv: kv[1])
        first_day[c] = {"date": d0, "bills": n0, "total": sum(dct.values())}
    eighth_laws = Counter(L["scope"] for L in laws if L.get("congress") == 8)
    dump("bills.json", {
        "funnel": {c: dict(v) for c, v in sorted(funnel.items())},
        # the 8th Congress: every House bill it received, and every law it passed
        "eighth": {"filed": dict(funnel[8]), "laws": dict(eighth_laws)},
        "daily": {c: sorted(v.items()) for c, v in daily.items()},
        "first_day": first_day,
        "n_bills": len(bills),
    })

    # ---- signing days
    by_day = Counter(L["date"] for L in laws if L["date"])
    big_days = sorted(by_day.items(), key=lambda kv: -kv[1])[:12]
    by_month = Counter(int(L["date"][5:7]) for L in laws if L["date"])
    in_batches = sum(v for v in by_day.values() if v >= 20)
    signed = Counter(L["president"] for L in laws if L.get("president"))
    # lapsed: from the act's text, or the House record (merged in build_laws.py)
    lapsed = Counter(L["president"] for L in laws if L.get("lapsed") and L.get("president"))
    lapsed_local = Counter(L["president"] for L in laws if L.get("lapsed") and L.get("president") and L["scope"] == "local")
    cal = defaultdict(Counter)  # year -> day-of-year counts for a calendar strip
    for L in laws:
        if L["date"]:
            d = date.fromisoformat(L["date"])
            cal[d.year][d.timetuple().tm_yday] += 1
    dump("calendar.json", {
        "days": {y: sorted(v.items()) for y, v in sorted(cal.items())},
        "big_days": big_days, "by_month": sorted(by_month.items()),
        "share_in_batches": round(in_batches / sum(by_day.values()), 3),
        "n_dated": sum(by_day.values()),
        "lapsed": {p: {"lapsed": lapsed[p], "local": lapsed_local[p], "total": signed[p]} for p in signed},
    })

    # ---- hospitals: legislated vs accredited beds
    hosp = list(csv.DictReader(open(CLEAN / "hospital_laws.csv")))
    latest = {}
    for h in sorted(hosp, key=lambda h: int(h["ra"])):
        confident = h["match"] == "found" and (float(h["match_score"]) >= 0.9)
        # psychiatric and leprosy hospitals: PhilHealth accredits their general beds only
        # (judged by the facility PhilHealth lists today, so a sanitarium turned general hospital stays in)
        special = re.search(r"mental|psychiatr|sanitari|leprosari", h["philhealth_name"], re.I)
        if h["beds_to"] and confident and not special:
            latest[h["philhealth_name"]] = h
    beds = []
    for name, h in latest.items():
        beds.append({"name": h["hospital_name"], "philhealth_name": name, "ra": int(h["ra"]), "year": int(h["year"]),
                     "from": int(h["beds_from"]) if h["beds_from"] else None, "to": int(h["beds_to"]),
                     "accredited": int(h["philhealth_beds"]), "level": h["philhealth_level"],
                     "province": (h["provinces"].split(";") or [""])[0]})
    beds.sort(key=lambda b: (b["accredited"] - b["to"]))
    hosp_counts = Counter(h["match"] for h in hosp if h["year"] and int(h["year"]) >= 1987)
    dump("hospitals.json", {"beds": beds, "match_counts": dict(hosp_counts), "n_laws": len(hosp)})

    # ---- schools
    sch = list(csv.DictReader(open(CLEAN / "school_laws.csv")))
    window = [s for s in sch if s["year"] and 1987 <= int(s["year"]) <= 2023 and s["action"] in ("establish", "separate", "convert", "create")]
    levels = Counter((s["action"], s["match"]) for s in window)
    recent = [s for s in sch if s["year"] and int(s["year"]) >= 2019 and s["action"] in ("establish", "separate", "convert")
              and s["match"] in ("named", "annex")]
    pre = [s for s in recent if s["deped_first_year"] and int(s["deped_first_year"]) < int(s["year"])]
    recent_est = [s for s in recent if s["action"] == "establish"]
    pre_est = [s for s in recent_est if s in pre]
    per_congress = defaultdict(Counter)
    for s in sch:
        if s["congress"]:
            per_congress[int(s["congress"])][s["action"]] += 1
    examples_nf = [{"ra": int(s["ra"]), "year": int(s["year"]), "title": s["title"], "target": s["target_name"]}
                   for s in window if s["match"] == "not_found"][:400]
    dump("schools.json", {"levels": {f"{a}|{m}": v for (a, m), v in levels.items()}, "n_window": len(window),
                          "recent": len(recent), "recent_preexisting": len(pre),
                          "recent_establish": len(recent_est), "recent_establish_preexisting": len(pre_est),
                          "per_congress": {c: dict(v) for c, v in sorted(per_congress.items())},
                          "not_found": examples_nf})

    # ---- authors and family seats
    terms = list(csv.DictReader(open(CLEAN / "rep_terms.csv")))
    for t in terms:
        for k in ("bills_filed", "local_bills_filed", "laws_enacted", "local_laws_enacted", "congress"):
            t[k] = int(t[k])
    done = [t for t in terms if 13 <= t["congress"] <= 19]

    def summary(g, key):
        xs = [t[key] for t in g]
        if not xs:
            return None
        rnd = random.Random(7)
        means = []
        for _ in range(2000):
            s = [xs[rnd.randrange(len(xs))] for _ in xs]
            means.append(sum(s) / len(s))
        means.sort()
        xs_sorted = sorted(xs)
        return {"n": len(xs), "mean": round(sum(xs) / len(xs), 3), "median": xs_sorted[len(xs) // 2],
                "lo": round(means[50], 3), "hi": round(means[1949], 3),
                "zero_share": round(sum(1 for x in xs if x == 0) / len(xs), 3)}

    fam = [t for t in done if t["family_seat"] == "True"]
    non = [t for t in done if t["family_seat"] == "False"]
    by_congress = {}
    for c in range(13, 20):
        f = [t for t in fam if t["congress"] == c]
        n = [t for t in non if t["congress"] == c]
        by_congress[c] = {"family": summary(f, "local_laws_enacted"), "other": summary(n, "local_laws_enacted"),
                          "family_share": round(len(f) / max(1, len(f) + len(n)), 3)}
    hist = {"family": Counter(min(t["local_laws_enacted"], 12) for t in fam),
            "other": Counter(min(t["local_laws_enacted"], 12) for t in non)}
    # top authors of local laws, 13th-19th Congress, province from their own laws
    local_auth = [a for a in authors if a["scope"] == "local" and 13 <= int(a["congress"]) <= 19]
    by_person = defaultdict(list)
    for a in local_auth:
        by_person[(a["author_id"], a["author"])].append(a)
    top = []
    for (pid, name), xs in sorted(by_person.items(), key=lambda kv: -len(kv[1]))[:25]:
        provs = Counter()
        for a in xs:
            for p in law_by_ra[int(a["ra"])]["provinces"]:
                provs[p] += 1
        cats = Counter(law_by_ra[int(a["ra"])]["category"] for a in xs)
        top.append({"name": name, "province": provs.most_common(1)[0][0] if provs else "",
                    "laws": len(xs), "congresses": sorted({int(a["congress"]) for a in xs}),
                    "top_category": CATEGORIES[cats.most_common(1)[0][0]][0]})
    dump("authors.json", {
        "family": summary(fam, "local_laws_enacted"), "other": summary(non, "local_laws_enacted"),
        "family_bills": summary(fam, "local_bills_filed"), "other_bills": summary(non, "local_bills_filed"),
        "by_congress": by_congress, "hist": {k: sorted(v.items()) for k, v in hist.items()},
        "n_terms": len(done), "n_family": len(fam), "top": top,
        "n_laws_with_author": len(local_auth),
        "n_laws_district_author": sum(1 for a in local_auth if a["district_rep"] == "True"),
    })

    # ---- fashions: selected kinds of law, per Congress
    def kind(L):
        t, c, a = L["title"], L["category"], L.get("action")
        if c == "school" and a in ("establish", "separate", "convert", "create"):
            return "new_schools"
        if c == "school" and a == "rename":
            return "school_names"
        if c == "college":
            return "colleges"
        if c == "hospital" and re.search(r"bed capacity|\bbeds?\b", t, re.I):
            return "beds"
        if c == "hospital" and a in ("establish", "create"):
            return "new_hospitals"
        if c == "road" and re.search(r"national (road|highway)", t, re.I):
            return "national_roads"
        if c == "franchise":
            return "franchises"
        if c == "holiday":
            return "holidays"
        if c == "court":
            return "courts"
        if c == "lgu" and re.search(r"\b(barrios?|barangays?|sitios?)\b", t, re.I):
            return "barangays"
        if c == "lgu" and re.search(r"\bcity\b", t, re.I) and a == "convert":
            return "cityhood"
        if c == "citizenship":
            return "citizenship"
        if c == "rename_place":
            return "renamed_places"
        return None
    KINDS = [("new_schools", "New, separated or converted schools"), ("school_names", "Schools renamed"),
             ("colleges", "State universities and colleges"), ("beds", "Hospital bed capacity"),
             ("new_hospitals", "New hospitals"), ("national_roads", "Roads made national"),
             ("franchises", "Franchises"), ("holidays", "Local holidays"), ("courts", "Court branches"),
             ("barangays", "Barrios and barangays"), ("cityhood", "Towns made cities"),
             ("renamed_places", "Towns and barrios renamed")]
    fash = defaultdict(Counter)
    for L in laws:
        k = kind(L)
        if k and L.get("congress"):
            fash[k][L["congress"]] += 1
    dump("fashions.json", {"kinds": [{"key": k, "label": lab, "counts": dict(sorted(fash[k].items()))} for k, lab in KINDS],
                           "totals": dict(sorted(Counter(L.get("congress") or 0 for L in laws).items()))})

    # ---- House bills by month and scope, and examples from the 8th Congress wish list
    monthly = defaultdict(Counter)
    for b in bills:
        if b["date_filed"]:
            monthly[b["date_filed"][:7]][b["scope"]] += 1
    rnd = random.Random(8)
    eighth = [b for b in bills if b["congress"] == "8" and b["scope"] == "local" and b.get("long_title")]
    examples = [smart_title(b["long_title"])[:220] for b in rnd.sample(eighth, 40)]
    extra = json.loads((OUT / "bills.json").read_text())
    extra["monthly"] = sorted((m, dict(v)) for m, v in monthly.items())
    extra["examples_8th"] = examples
    dump("bills.json", extra)

    # ---- odd corners
    cit = [{"ra": L["ra"], "year": L["year"], "name": re.sub(r"(?i)^.*citizenship to\s+", "", L["title"])}
           for L in laws if L["category"] == "citizenship"]
    dump("odd.json", {"citizenship": cit})

    # ---- headline numbers
    n = len(laws)
    local = sum(1 for L in laws if L["scope"] == "local")
    fam_n = Counter(FAM_OF[L["category"]] for L in laws)
    post87 = [L for L in laws if (L.get("congress") or 0) >= 8]
    stats = {
        "n_laws": n, "local": local, "local_share": round(local / n, 3),
        "private": sum(1 for L in laws if L["scope"] == "private"),
        "national": sum(1 for L in laws if L["scope"] == "national"),
        "schools": sum(1 for L in laws if L["category"] == "school"),
        "hospitals": sum(1 for L in laws if L["category"] == "hospital"),
        "franchises": sum(1 for L in laws if L["category"] == "franchise"),
        "towns_named": len(town_codes),
        "placed": sum(1 for L in laws if L["scope"] == "local" and L["geo_level"] != "none"),
        "placed_town": sum(1 for L in laws if L["scope"] == "local" and L["geo_level"] == "muni"),
        "post87": len(post87), "post87_local_share": round(sum(1 for L in post87 if L["scope"] == "local") / len(post87), 3),
        "family_counts": [fam_n[i] for i in range(len(FAMILIES))],
        "first": laws[0]["date"], "last": max(L["date"] for L in laws if L["date"]),
        "max_ra": laws[-1]["ra"],
        "sources": dict(Counter(L["source"] for L in laws)),
        # act numbers in no source: neither library nor the House record
        "missing": sorted(set(range(1, laws[-1]["ra"] + 1)) - {L["ra"] for L in laws}),
    }
    dump("stats.json", stats)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
