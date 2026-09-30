"""Write the main clean table: data/clean/laws.csv, one row per Republic Act."""

import csv

from classify import CATEGORIES
from common import CLEAN, INTERIM, read_json
from geocode import load_gazetteer
from make_site_data import FAMILIES, FAM_OF

COLUMNS = ["ra", "date", "year", "congress", "president", "title", "category", "category_label", "scope", "family",
           "action", "facility", "provinces", "towns", "town_psgc10", "geo_level", "lapsed", "funding",
           "house_bills", "senate_bills", "source", "url", "title_source", "date_source", "congress_source", "lapsed_source"]


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    lgus, _, _ = load_gazetteer()
    name = {L["psgc10"]: L["name"].strip() for L in lgus}
    with open(CLEAN / "laws.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for L in sorted(laws, key=lambda L: L["ra"]):
            w.writerow({
                "ra": L["ra"], "date": L["date"] or "", "year": L["year"] or "", "congress": L.get("congress") or "",
                "president": L.get("president") or "", "title": L["title"], "category": L["category"],
                "category_label": CATEGORIES[L["category"]][0], "scope": L["scope"],
                "family": FAMILIES[FAM_OF[L["category"]]][1], "action": L.get("action") or "",
                "facility": L.get("facility") or "", "provinces": "; ".join(L["provinces"]),
                "towns": "; ".join(name.get(c, c) for c in L["munis"]), "town_psgc10": "; ".join(L["munis"]),
                "geo_level": L["geo_level"], "lapsed": "yes" if L.get("lapsed") else "",
                "funding": L.get("funding") or "", "house_bills": "; ".join(map(str, L.get("hb") or [])),
                "senate_bills": "; ".join(map(str, L.get("sb") or [])), "source": L["source"], "url": L.get("href") or "",
                "title_source": L.get("title_from") or {"chanrobles": "act text", "house record": "house record"}.get(L["source"], ""),
                "date_source": L.get("date_from") or "", "congress_source": L.get("congress_from") or "",
                "lapsed_source": L.get("lapsed_from") or "" if L.get("lapsed") else "",
            })
    print(f"wrote {CLEAN / 'laws.csv'} ({len(laws)} rows)")


if __name__ == "__main__":
    main()
