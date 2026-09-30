"""Check hospital laws against PhilHealth's list of accredited hospitals (July 2026).

Two questions:
  1. For laws that set a hospital's bed capacity ("increasing the bed capacity
     of X from 50 to 200 beds"), how many beds does PhilHealth list for X today?
  2. For laws that establish, convert, upgrade or rename a hospital, does a
     hospital with that name appear in PhilHealth's list for that town or province?

PhilHealth lists only accredited facilities, and its bed count is the count it
accredits. A hospital that is missing may still exist unaccredited, so
"not found" here is weaker evidence than for schools.

Output: data/clean/hospital_laws.csv
"""

import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

from common import CLEAN, INTERIM, read_json
from geocode import core, fold, load_gazetteer

GENERIC = set("""hospital hospitals district provincial municipal memorial medical center centre general regional
training teaching of the and in city community emergency infirmary health care complex inc corporation
national specialty doctors doctor dr sr jr ii iii de del la san santa santo sto sta mayor governor gov
congressman cong senator president hon the medicare municipality province barangay town
maternity children childrens and hosp clinic""".split())


def norm(s):
    s = fold((s or "").replace("'", "").replace("’", ""))
    s = re.sub(r"\bmed\b", "medical", s)
    s = re.sub(r"\bgen\b", "general", s)
    s = re.sub(r"\bhosp\b", "hospital", s)
    s = re.sub(r"\bmem\b", "memorial", s)
    return s


def tokens(s):
    return {w for w in norm(s).split() if w not in GENERIC and len(w) > 1}


def _close(w, others):
    return any(w == o or (len(w) > 4 and SequenceMatcher(None, w, o).ratio() >= 0.88) for o in others)


def sim(a, b, place=frozenset()):
    """How well hospital name b matches law name a.

    Words that are only place names (the town or province) are set aside: two
    different hospitals in Valenzuela share "Valenzuela". When the law's name has
    distinctive words left, we score how many of them the other name contains.
    When it has none ("Valenzuela Medical Center"), we require the full names to
    be nearly identical.
    """
    ta, tb = tokens(a) - place, tokens(b) - place
    if ta:
        hits = sum(1 for w in ta if _close(w, tb))
        return hits / len(ta) - 0.02 * max(0, len(tb) - len(ta))
    na, nb = norm(a).strip(), norm(b).strip()
    if nb.startswith(na) or na.startswith(nb):
        return 0.95  # "Bataan General Hospital" / "Bataan General Hospital and Medical Center"
    r = SequenceMatcher(None, na, nb).ratio()
    if tb:
        r -= 0.2
    return r if r >= 0.92 else r * 0.5


NAME = [
    re.compile(r"(?:Capacity|Beds?) of (?:the )?(.+?)(?= in the | in [A-Z]| located| situated| at the | at [A-Z]|, |\s+from\s)", re.I),
    re.compile(r"(?:to be known|shall be known|to be called|hereafter known|henceforth known)\s+(?:as\s+)?(?:the\s+)?(.+?)(?=,| and (?:appropriating|authorizing|providing|for other)| appropriating|$)", re.I),
    re.compile(r"(?:Converting|Upgrading|Renaming|Changing the Name of|Establishing|Separating)\s+(?:the\s+)?(?:Existing\s+)?"
               r"([A-Z].+?(?:Hospital|Medical Center|Infirmary|Health Center|Sanitarium))\b"),
]


def law_hospital_name(title):
    for p in NAME:
        m = p.search(title)
        if m:
            n = re.sub(r"\s*\([^)]*\)", "", m.group(1)).strip(" .,\"'")
            n = re.sub(r"(?i)^the\s+", "", n)
            if 5 < len(n) < 150 and re.search(r"hospital|medical|center|infirmar|sanitari|clinic|unit", n, re.I):
                return n
    return None


RENAME = [
    re.compile(r"(?:Changing the Name of|Renaming)\s+(?:the\s+)?(.+?(?:Hospital|Medical Center|Infirmary|Sanitarium|Health Center))"
               r"(?:\s+(?:in|at|located|situated)\b.*?)?\s+(?:to|as|into)\s+(?:the\s+)?(.+?(?:Hospital|Medical Center|Infirmary|Sanitarium|Health Center))", re.I),
    re.compile(r"(?:Converting|Upgrading|Integrating)\s+(?:the\s+)?(.+?(?:Hospital|Medical Center|Infirmary|Sanitarium|Health Center|Health Unit))"
               r".*?(?:to be known|shall be known|renaming (?:it|the same) as|henceforth known)\s+(?:as\s+)?(?:the\s+)?"
               r"(.+?(?:Hospital|Medical Center|Infirmary|Sanitarium|Health Center))", re.I),
]


def rename_edges(laws):
    """Old name -> newer names, from laws that rename or convert a hospital."""
    edges = defaultdict(list)  # newer names in the order the renaming laws were passed
    for L in sorted(laws, key=lambda L: L["ra"]):
        if L["category"] != "hospital":
            continue
        for p in RENAME:
            m = p.search(L["title"])
            if m:
                a, b = m.group(1).strip(), m.group(2).strip()
                if tokens(a) and tokens(b) and tokens(a) != tokens(b) and b not in edges[norm(a)]:
                    edges[norm(a)].append(b)
                break
    return edges


def later_names(name, edges, depth=4):
    out, frontier = [name], [name]
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for b in edges.get(norm(n), ()):
                if b not in out:
                    out.append(b)
                    nxt.append(b)
        frontier = nxt
    return out


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    edges = rename_edges(laws)
    ph = read_json(INTERIM / "philhealth_hospitals.json")
    lgus, _, _ = load_gazetteer()
    psgc = {L["psgc10"]: L for L in lgus}
    by_town = defaultdict(list)
    by_prov = defaultdict(list)
    for h in ph:
        by_town[core(h["municipality"])].append(h)
        if core(h["province"] or "") != core(h["municipality"]):
            by_town[core(h["province"] or "")].append(h)  # city headings such as MANILA, QUEZON CITY
        by_prov[core(h["province"] or "")].append(h)
    gov = [h for h in ph if h["sector"] == "G"]
    out = []
    for L in laws:
        if L["category"] != "hospital":
            continue
        name = law_hospital_name(L["title"])
        town_pool = []
        for code in L["munis"]:
            for k in psgc[code]["keys"]:
                town_pool += [h for h in by_town.get(k, []) if h["sector"] == "G"]
        prov_pool = []
        for p in L["provinces"]:
            prov_pool += [h for h in by_prov.get(core(p), []) if h["sector"] == "G"]
        best, score = None, 0.0
        names = later_names(name, edges) if name else []
        place = set()
        for code in L["munis"]:
            for k in psgc[code]["keys"]:
                place |= set(k.split())
        for p in L["provinces"]:
            place |= set(norm(p).split())
        place -= GENERIC
        if name:
            for pool, need in ((town_pool, 0.66), (prov_pool, 0.99)):
                for h in pool:
                    hp = place | set(norm(h["municipality"]).split()) | set(norm(h["province"] or "").split())
                    hp -= GENERIC
                    for n in names:
                        s = sim(n, h["name"], frozenset(hp))
                        if s > score:
                            best, score = h, s
                if best is not None and score >= need:
                    break
            else:
                pass
        level = "town" if best is not None and best in town_pool else "province"
        need = 0.66 if level == "town" else 0.99
        found = best is not None and score >= need
        if name and not found and not (town_pool or prov_pool):
            # the title names no place we can use: accept only a near-identical name anywhere
            # every distinctive word must match, then the closest full name wins
            cands = [h for h in gov if sim(name, h["name"]) >= 0.95]
            if cands:
                h = max(cands, key=lambda h: SequenceMatcher(None, norm(name), norm(h["name"])).ratio())
                r = SequenceMatcher(None, norm(name), norm(h["name"])).ratio()
                if r >= 0.9:
                    best, score, level, found = h, max(r, sim(name, h["name"])), "national", True
        has_place = bool(town_pool or prov_pool)
        match = "found" if found else ("no_place" if not has_place else "not_found")
        if not name:
            match = "no_name"
        out.append({
            "ra": L["ra"], "date": L["date"], "year": L["year"], "congress": L["congress"], "action": L["action"],
            "title": L["title"], "hospital_name": name or "", "beds_from": L.get("beds_from") or "",
            "beds_to": L.get("beds_to") or "", "munis": ";".join(L["munis"]), "provinces": ";".join(L["provinces"]),
            "match": match, "match_score": round(score, 2), "match_level": level if match == "found" else "",
            "later_names": " | ".join(names[1:]),
            "philhealth_name": best["name"] if best and match == "found" else "",
            "philhealth_beds": best["beds"] if best and match == "found" else "",
            "philhealth_level": best["category"] if best and match == "found" else "",
            "philhealth_sector": best["sector"] if best and match == "found" else "",
            "closest_name": best["name"] if best else "",
        })
    with open(CLEAN / "hospital_laws.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    beds = [r for r in out if r["beds_to"]]
    print("hospital laws:", len(out), dict(Counter(r["match"] for r in out)))
    print("bed-capacity laws:", len(beds), dict(Counter(r["match"] for r in beds)))


if __name__ == "__main__":
    main()
