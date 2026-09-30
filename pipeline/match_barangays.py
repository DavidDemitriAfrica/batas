"""Check laws that create barangays against the barangays counted in the 2020 census.

A barangay created by law exists only after a plebiscite ratifies it. We look
for the new barangay's name, inside the town the law names, among the 42,041
barangays in the 2020 census (via the Philippine Internal Migration Dataset).
We check laws from 1992 (the Local Government Code) to 2019, so every
barangay had time to be ratified before the census.

Output: data/clean/barangay_laws.csv
"""

import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

from common import CLEAN, INTERIM, RAW, read_json
from geocode import fold

NEW_BRGY = [
    re.compile(r"to be known as (?:the )?Barangay\s+(?:of\s+)?([A-Z][^,]*?)(?=,| and | in the | in [A-Z]|$)", re.I),
    re.compile(r"Creating (?:a |the )?(?:New |Separate |Independent )?Barangay (?:of |to be known as )?(?:Barangay )?([A-Z][^,]*?)"
               r"(?= in the | in [A-Z]|,| from |$)", re.I),
    re.compile(r"(?:into|as) (?:a |an )?(?:distinct and independent |separate |independent |regular )?barangay "
               r"(?:to be known as )?(?:Barangay )?([A-Z][^,]*?)(?=,| in the | in [A-Z]|$)", re.I),
]


def key(s):
    s = fold(s)
    s = re.sub(r"\b(barangay|brgy|poblacion|pob)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    by_muni = defaultdict(list)
    with open(RAW / "pim" / "population_barangay_2020.csv") as fh:
        for r in csv.DictReader(fh):
            raw = r["muni_psgc10"] or (r["psgc10"][:7] + "000" if r["psgc10"] else "")
            if not raw:
                continue
            code = str(int(float(raw))).zfill(10)
            by_muni[code].append(r["barangay_src"])
    out = []
    for L in laws:
        if L["category"] != "lgu" or not re.search(r"barangay", L["title"], re.I):
            continue
        if not re.search(r"\b(creat|separat|constitut|convert)", L["title"], re.I):
            continue
        if re.search(r"local government code|republic act no\.? 7160", L["title"], re.I):
            continue  # general amendments to the Local Government Code, not a barangay
        name = None
        for p in NEW_BRGY:
            m = p.search(L["title"])
            if m:
                name = re.sub(r"\s+(?:and|Appropriating|Providing).*$", "", m.group(1)).strip(" .")
                break
        brgys = []
        for code in L["munis"]:
            brgys += by_muni.get(code[:7] + "000", []) + by_muni.get(code, [])
        best, score = None, 0.0
        if name and brgys:
            k = key(name)
            for b in brgys:
                s = 1.0 if key(b) == k else SequenceMatcher(None, key(b), k).ratio()
                if s > score:
                    best, score = b, s
        status = "no_town" if not brgys else ("no_name" if not name else ("found" if score >= 0.88 else "not_found"))
        out.append({"ra": L["ra"], "date": L["date"], "year": L["year"], "title": L["title"], "new_barangay": name or "",
                    "munis": ";".join(L["munis"]), "provinces": ";".join(L["provinces"]), "match": status,
                    "census_2020_name": best if status == "found" else "", "closest": best or "",
                    "score": round(score, 2)})
    with open(CLEAN / "barangay_laws.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    window = [r for r in out if r["year"] and 1992 <= r["year"] <= 2019]
    print("barangay-creation laws 1992-2019:", len(window), dict(Counter(r["match"] for r in window)))


if __name__ == "__main__":
    main()
