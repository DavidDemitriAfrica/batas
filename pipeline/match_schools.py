"""Check each school law against DepEd's list of public schools.

For every law that establishes, separates, converts, or renames a public
school, we look for the school the law names in DepEd's enrolment lists
(SY 2017-18 to SY 2025-26), inside the town the law names.

Match levels
  named      a school with the law's name (or a close variant) is listed in that town
  barangay   no name match, but a public school offering the same level is listed in
             the barangay the law names (the school may exist under another name)
  annex      the law made an annex independent, but DepEd still lists it as an annex
  not_found  nothing in DepEd's lists matches

A school that is not found is not proof that the law failed: schools merge,
change names again, or are listed under a different town. We report the
levels separately and show examples so readers can judge.

Output: data/clean/school_laws.csv
"""

import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

from common import CLEAN, INTERIM, read_json
from geocode import core, fold, load_gazetteer

ABBR = [
    (r"\bnhs\b", "national high school"), (r"\bnchs\b", "national comprehensive high school"),
    (r"\bnshs\b", "national science high school"), (r"\bshs\b", "science high school"),
    (r"\bnvhs\b", "national vocational high school"), (r"\bnats\b", "national agricultural and trade school"),
    (r"\bnas\b", "national agricultural school"), (r"\bnts\b", "national trade school"),
    (r"\bhs\b", "high school"), (r"\bces\b", "central elementary school"), (r"\bcs\b", "central school"),
    (r"\bes\b", "elementary school"), (r"\bis\b", "integrated school"), (r"\bnis\b", "national integrated school"),
    (r"\bps\b", "primary school"), (r"\bnat l\b", "national"), (r"\bnatl\b", "national"), (r"\bmem\b", "memorial"),
    (r"\bsch\b", "school"), (r"\bbrgy\b", "barangay"), (r"\bmun\b", "municipal"), (r"\bagri\b", "agricultural"),
    (r"\btech voc\b", "technical vocational"), (r"\btvhs\b", "technical vocational high school"),
    (r"\bhighschool\b", "high school"), (r"\bsr\b", "senior"), (r"\bjr\b", "junior"),
]
GENERIC = set("""national high school elementary integrated primary central annex extension of the and in
secondary science technical vocational comprehensive agricultural trade agro industrial fishery fisheries
school schools memorial barangay community rural municipal city provincial regional pilot
independent campus a an de del la las los sa ng""".split())
LEVEL_HS = re.compile(r"high school|secondary|integrated|trade school|agricultural school|vocational|fishery|fisheries|science", re.I)
LEVEL_ES = re.compile(r"elementary|primary|central school", re.I)


def norm_school(s):
    s = fold(s.replace("'", " "))
    for a, b in ABBR:
        s = re.sub(a, b, s)
    return re.sub(r"\s+", " ", s).strip()


def distinctive(s):
    return {w for w in norm_school(s).split() if w not in GENERIC and len(w) > 1}


def _close(w, others):
    return any(w == o or (len(w) > 4 and SequenceMatcher(None, w, o).ratio() >= 0.88) for o in others)


def similar(a, b):
    """Share of the law name's distinctive words found in the DepEd name, with a
    small bonus for overall likeness so that exact names win ties."""
    b = re.sub(r"\([^)]*\)", " ", b)
    na, nb = norm_school(a), norm_school(b)
    if na == nb:
        return 1.05
    da, db = distinctive(a), {w for w in distinctive(b) if not w.isdigit()}
    whole = SequenceMatcher(None, na, nb).ratio()
    if not da or not db:
        return whole * 0.8
    hits = sum(1 for w in da if _close(w, db))
    return hits / len(da) - 0.03 * max(0, len(db) - len(da)) + 0.04 * whole


TARGET = [
    re.compile(r"(?:to be known|shall be known|to be called|hereafter known|henceforth known|as the)\s+(?:as\s+)?(?:the\s+)?"
               r"(.+?(?:School|Academy|Institute|Center|Centre|Annex|Extension))\b", re.I),
    re.compile(r"\bto\s+(?:the\s+)?([A-Z][^,]+?(?:School|Academy|Institute))\b"),
    re.compile(r"\binto an? (?:independent |separate )?((?:[A-Z][\w.'-]* )+(?:National |Integrated )?(?:High |Elementary |Integrated )?School)\b"),
]
BRGY = re.compile(r"\b(?:Barangay|Barrio|Sitio)\s+(?:of\s+)?([A-Z][\w.'À-ſ-]*(?:\s+(?:[A-Z][\w.'À-ſ-]*|de|del|dela|I{1,3}|IV|V|\d+))*)")
SOURCE = re.compile(r"\b(?:Separating|Converting|Changing the Name of|Renaming|Integrating)\s+(?:the\s+)?(?:Existing\s+)?"
                    r"(.+?(?:School|Annex|Extension))\b", re.I)


NAMED_DIRECT = re.compile(
    r"\b(?:Establishing|Creating|Converting|Integrating|Renaming|Separating)\s+(?:the\s+|an?\s+)?"
    r"((?:[A-Z][\w.'\u00c0-\u017f-]*|de|del|y|of)(?:\s+(?:[A-Z][\w.'\u00c0-\u017f-]*|de|del|y|of|and))*?\s+"
    r"(?:National\s+|Integrated\s+|Science\s+|Comprehensive\s+|Vocational\s+|Agricultural\s+|Technical\s+)*"
    r"(?:High|Elementary|Integrated|Trade|Agricultural|Vocational|Fishery|Fisheries|Science|Comprehensive|Central|Primary)\s+"
    r"(?:and\s+\w+\s+)?(?:High\s+)?School"
    r"|(?:[A-Z][\w.'\u00c0-\u017f-]*\s+)+(?:National\s+)?School\s+of\s+(?:Arts\s+and\s+Trades?|Fisheries|Agriculture))\b")
ANNEX_TAIL = re.compile(r"^\s*[-\u2013\u2014]?\s*((?:[A-Z][\w.'-]*\s+){0,3}(?:Annex|Extension)(?:\s+[IVX\d]+)?)\b")


def target_name(title):
    title = re.sub(r",\s*(Sr|Jr|II|III|IV)\b\.?", r" \1.", title)
    for p in TARGET:
        m = p.search(title)
        if m:
            name = m.group(1).strip(" .,\"'")
            tail = ANNEX_TAIL.match(title[m.end(1):])
            if tail and not re.search(r"annex|extension", name, re.I):
                name = f"{name} {tail.group(1)}"
            if 6 < len(name) < 140 and not re.match(r"(?i)^(an?|the)?\s*(national )?(high|elementary|integrated) school$", name):
                return name
    m = NAMED_DIRECT.search(title)
    if m and not re.match(r"(?i)^(an?|the)?\s*(national )?(high|elementary|integrated) school$", m.group(1)):
        return m.group(1).strip()
    m = re.search(r"Establishing (?:an? )?(National High School|High School|Elementary School|Integrated School|Science High School)"
                  r" in (?:the )?Barangay (?:of )?([A-Z][\w.'À-ſ-]*(?:\s+[A-Z][\w.'À-ſ-]*)*)", title)
    if m:
        return f"{m.group(2)} {m.group(1)}"
    return None


def deped_key(prov, muni):
    return core(prov), core(muni)


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    schools = read_json(INTERIM / "deped_schools.json")
    lgus, by_key, _ = load_gazetteer()
    psgc = {L["psgc10"]: L for L in lgus}
    by_muni = defaultdict(list)
    by_muni_name = defaultdict(list)
    for s in schools:
        by_muni[deped_key(s["province"], s["municipality"])].append(s)
        by_muni_name[core(s["municipality"])].append(s)

    def town_schools(code):
        L = psgc[code]
        # current name first, then former names, in a fixed order
        for k in sorted(L["keys"], key=lambda k: (k != core(L["name"]), k)):
            hits = by_muni_name.get(k, [])
            if not hits:
                continue
            provs = {core(s["province"]) for s in hits}
            if len(provs) == 1:
                return hits
            prov = core(L["province"])
            same = [s for s in hits if core(s["province"]) == prov or k in core(s["province"])
                    or L["province"] == "Metro Manila"]
            if same:
                return same
        return []

    out = []
    for L in laws:
        if L["category"] != "school":
            continue
        title = L["title"]
        tgt = target_name(title)
        src_m = SOURCE.search(title)
        src = src_m.group(1) if src_m else None
        brgys = [b.strip() for b in BRGY.findall(title)
                 if not re.match(r"(?i)^(high|elementary|national|integrated|school)\b", b.strip())]
        want_hs = bool(LEVEL_HS.search(tgt or title)) and not LEVEL_ES.search(tgt or "")
        pool = []
        for code in L["munis"]:
            pool += town_schools(code)
        want_es = bool(LEVEL_ES.search(tgt or "")) or (not want_hs and bool(LEVEL_ES.search(title)))
        def level_ok(s):
            if want_hs:
                return s["offers_jhs"] or s["offers_shs"] or not s["offers_es"]
            if want_es:
                return s["offers_es"]
            return True
        best, score = None, 0.0
        for s in pool:
            if not level_ok(s):
                continue
            for nm in s["names"]:
                sc = similar(tgt, nm) if tgt else 0.0
                if sc > score:
                    best, score = s, sc
        level = "no_town"
        if pool and not tgt and not brgys:
            level = "no_name"
        elif pool:
            level = "not_found"
            if best is not None and score >= 0.72:
                level = "named"
                annexy = re.search(r"\b(annex|extension)\b", best["name"], re.I) or best["annex_status"] in (
                    "Annex or Extension school(s)", "Annex/Extension School")
                if L["action"] == "separate" and annexy:
                    level = "annex"
            elif brgys:
                bset = {fold(b) for b in brgys}
                inb = [s for s in pool if fold(s["barangay"]) in bset or any(fold(b) in fold(s["barangay"]) for b in bset)]
                inb = [s for s in inb if (s["offers_jhs"] or s["offers_shs"]) == want_hs or not want_hs]
                if inb:
                    level = "barangay"
                    best = inb[0]
        out.append({
            "ra": L["ra"], "date": L["date"], "year": L["year"], "congress": L["congress"], "action": L["action"],
            "title": title, "target_name": tgt or "", "source_name": src or "", "barangays": "; ".join(brgys),
            "munis": ";".join(L["munis"]), "provinces": ";".join(L["provinces"]), "match": level,
            "match_score": round(score, 2), "deped_school_id": best["school_id"] if best and level != "not_found" else "",
            "deped_name": best["name"] if best and level != "not_found" else "",
            "deped_first_year": best["first_year"] if best and level != "not_found" else "",
            "deped_last_year": best["last_year"] if best and level != "not_found" else "",
            "deped_enrolment_latest": (best["enrolment"].get(best["last_year"]) if best and level != "not_found" else ""),
            "closest_name": best["name"] if best else "", "closest_score": round(score, 2),
        })
    CLEAN.mkdir(parents=True, exist_ok=True)
    with open(CLEAN / "school_laws.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    c = Counter((r["match"]) for r in out if r["year"] and 1987 <= r["year"] <= 2023 and r["action"] in ("establish", "separate", "convert", "create"))
    print("school laws 1987-2023 that establish/separate/convert:", dict(c))


if __name__ == "__main__":
    main()
