"""Who writes the laws: principal authors, their provinces, and family seats.

1. Every House bill (BetterGov open-congress-data) is classified with the same
   title rules as the laws, so filed bills and enacted laws are comparable.
2. Each Republic Act is linked to the House bill it came from, using the
   bill's own history ("REPUBLIC ACT NO. 11849") and the act's closing
   clause ("This Act which is a consolidation of House Bill No. ...").
3. Each principal author is matched to OpenHalalan's list of House district
   winners for the election before that Congress, which gives the author's
   province. Party-list members have no province and are kept separately.
4. A "family seat" follows OpenHalalan's surname rule, narrowed to the
   offices most often shared inside a clan: a representative holds one when
   someone else with the same surname was elected governor, vice governor,
   another House seat, or mayor in the same province in the same election,
   or held a House seat in that province in one of the two previous
   elections. Surnames are an imperfect marker of kinship (see caveats).

Outputs
  data/clean/house_bills_classified.csv.gz
  data/clean/law_authors.csv          one row per enacted law with a House author
  data/clean/rep_terms.csv            one row per district representative per Congress
"""

import csv
import gzip
import re
from collections import Counter, defaultdict

from build_laws import smart_title
from classify import CATEGORIES, classify_title
from common import CLEAN, INTERIM, RAW, fetch, read_json
from geocode import fold

ELECTION = {13: 2004, 14: 2007, 15: 2010, 16: 2013, 17: 2016, 18: 2019, 19: 2022, 20: 2025}
MATCH_ELECTION = {12: 2001, **ELECTION}
TOP_OFFICES = {"GOVERNOR", "VICE GOVERNOR", "MEMBER, HOUSE OF REPRESENTATIVES", "MAYOR"}


def name_key(s):
    s = fold(s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v|dr|atty|engr|hon)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def province_key(p):
    p = fold(p)
    p = re.sub(r"^(ncr )?(first|second|third|fourth) district$", "metro manila", p)
    return p


OH_URL = "https://github.com/RobertRLeung/OpenHalalan/releases/download/data-latest/NLE_Winners_2004-2025.csv"


def load_winners():
    path = RAW / "openhalalan" / "NLE_Winners_2004-2025.csv"
    if not path.exists():
        # not redistributed here; fetched from the canonical OpenHalalan release
        fetch(OH_URL, path, note="OpenHalalan winners dataset (Leung et al. 2026), ODbL", min_bytes=1000)
    rows = list(csv.DictReader(open(path)))
    house = defaultdict(list)          # year -> House winners
    top = defaultdict(lambda: defaultdict(list))  # (year) -> province -> [(surname, first, office)]
    for r in rows:
        y = int(r["Year"])
        if r["Position"] == "MEMBER, HOUSE OF REPRESENTATIVES":
            house[y].append(r)
        if r["Position"] in TOP_OFFICES and r["Province"]:
            top[y][province_key(r["Province"])].append((name_key(r["Last Name"]), name_key(r["First Name"]), r["Position"]))
    return house, top


def match_winner(person_last, person_first, person_middle, winners, namesakes=1):
    """Find a House winner with the same surname and a compatible first name.

    OpenHalalan's records from 2016 on often carry the name on the ballot
    ("JB" Bernos, "Joey" Salceda). When no first name fits, a winner is still
    accepted if they are the only winner with that surname in that election,
    no other member with that surname sat in that Congress, and the middle
    names, when both are known, agree."""
    lk = name_key(person_last)
    fk = set(name_key(person_first).split())
    mk = name_key(person_middle)
    exact = [w for w in winners if name_key(w["Last Name"]) == lk]
    cands = exact or [w for w in winners if lk and (lk in name_key(w["Last Name"]) or name_key(w["Last Name"]) in lk)]

    def middle_ok(w):
        # OpenHalalan's middle-name field sometimes holds a second given name, so any shared
        # word or initial will do; only two different, fully spelled names rule a match out
        wm = set(name_key(w.get("Middle Name", "")).replace(".", " ").split())
        mine = set(mk.replace(".", " ").split()) | fk
        if not mk or not wm:
            return True
        return bool(wm & mine) or any(len(a) == 1 and any(b.startswith(a) for b in mine) for a in wm)
    for w in cands:
        wf = set(name_key(w["First Name"]).split())
        if fk & wf or (fk and wf and any(a[:3] == b[:3] for a in fk for b in wf)):
            return w
    if len(exact) == 1 and namesakes == 1 and middle_ok(exact[0]):
        return exact[0]
    if len(cands) == 1 and not fk:
        return cands[0]
    return None


def main():
    bills = list(csv.DictReader(gzip.open(INTERIM / "house_bills.csv.gz", "rt")))
    laws = {L["ra"]: L for L in read_json(INTERIM / "laws_geo.json")}
    people = read_json(INTERIM / "house_people.json")
    house, top = load_winners()

    # 1. classify every House bill with the law rules. The House's own Local/National
    # tag is only real in Congresses that use both values; elsewhere it is a default.
    tagged = {b["congress"] for b in bills if b["scope_house"] == "Local"}
    for b in bills:
        if b["congress"] not in tagged:
            b["scope_house"] = ""
    for b in bills:
        t = smart_title(b["long_title"] or b["title"])
        c = classify_title(t)
        b["category"] = c
        b["scope"] = CATEGORIES[c][1]
    with gzip.open(CLEAN / "house_bills_classified.csv.gz", "wt", newline="") as fh:
        keep = ["congress", "bill", "date_filed", "title", "long_title", "scope_house", "category", "scope", "author_code", "author",
                "author_id", "n_authors", "status", "ra", "committee"]
        w = csv.DictWriter(fh, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(bills)

    # 2. link acts to House bills
    by_cb = {(int(b["congress"]), int(b["bill"])): b for b in bills if b["bill"]}
    ra_to_bill = {}
    for b in bills:
        if b["ra"]:
            ra_to_bill.setdefault(int(b["ra"]), b)
    for ra, L in laws.items():
        if ra in ra_to_bill or not L.get("hb") or not L.get("congress"):
            continue
        for n in L["hb"]:
            b = by_cb.get((L["congress"], n))
            if b:
                ra_to_bill[ra] = b
                break

    with open(CLEAN / "law_bills.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["ra", "congress", "house_bill", "linked_by"])
        for ra, b in sorted(ra_to_bill.items()):
            wr.writerow([ra, b["congress"], b["bill"], "bill history" if b["ra"] and int(b["ra"]) == ra else "act text"])

    # 3. match each author-Congress to an OpenHalalan district winner. The 12th
    # Congress (2001 election) is matched too, only so that a member's own earlier
    # term is never counted as a relative's.
    persons = list({p["id"]: p for p in people.values()}.values())
    namesakes = Counter((name_key(p["last"]), c) for p in persons for c in p["house"])
    rep_prov = {}
    for p in persons:
        for c in p["house"]:
            y = MATCH_ELECTION.get(c)
            if not y:
                continue
            w = match_winner(p["last"], p["first"], p.get("middle", ""), house[y], namesakes[(name_key(p["last"]), c)])
            if w:
                rep_prov[(p["id"], c)] = w
    # 4. family seats
    def family(pid, c, w):
        y = ELECTION[c]
        prov = province_key(w["Province"])
        sn, fn = name_key(w["Last Name"]), name_key(w["First Name"])
        same_year = [x for x in top[y].get(prov, []) if x[0] == sn and x[1] != fn]
        # the member's own terms in the two previous Congresses, however OpenHalalan spells the first name
        own = [rep_prov[(pid, cc)] for cc in (c - 1, c - 2) if (pid, cc) in rep_prov]
        earlier = []
        for yy in (y - 3, y - 6):
            earlier += [x for x in house.get(yy, []) if name_key(x["Last Name"]) == sn
                        and province_key(x["Province"]) == prov and not any(x is o for o in own)]
        return bool(same_year or earlier), "; ".join(sorted({f"{x[2].title()} {yy}" for x in same_year for yy in [y]} |
                                                              {"Earlier House seat" for _ in earlier}))

    # per law
    out = []
    for ra, b in sorted(ra_to_bill.items()):
        L = laws.get(ra)
        if not L or not b["author_id"]:
            continue
        c = int(b["congress"])
        w = rep_prov.get((b["author_id"], c)) if c in ELECTION else None
        fam, how = family(b["author_id"], c, w) if w else (None, "")
        out.append({"ra": ra, "year": L["year"], "congress": c, "category": L["category"], "scope": L["scope"],
                    "title": L["title"], "house_bill": b["bill"], "author": b["author"], "author_id": b["author_id"],
                    "author_province": w["Province"].title() if w else "", "district_rep": bool(w),
                    "family_seat": fam, "family_evidence": how})
    with open(CLEAN / "law_authors.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)

    # per representative-term
    filed = Counter()
    filed_local = Counter()
    for b in bills:
        if b["author_id"] and b["congress"]:
            k = (b["author_id"], int(b["congress"]))
            filed[k] += 1
            filed_local[k] += b["scope"] == "local"
    enacted = Counter()
    enacted_local = Counter()
    for r in out:
        k = (r["author_id"], r["congress"])
        enacted[k] += 1
        enacted_local[k] += r["scope"] == "local"
    terms = []
    id_to_person = {p["id"]: p for p in people.values()}
    for (pid, c), w in rep_prov.items():
        if c not in ELECTION:
            continue
        p = id_to_person[pid]
        fam, how = family(pid, c, w)
        terms.append({"author_id": pid, "name": f"{p['first']} {p['last']}", "congress": c, "election": ELECTION[c],
                      "province": w["Province"].title(), "party": w["Party"], "family_seat": fam, "family_evidence": how,
                      "bills_filed": filed[(pid, c)], "local_bills_filed": filed_local[(pid, c)],
                      "laws_enacted": enacted[(pid, c)], "local_laws_enacted": enacted_local[(pid, c)]})
    terms.sort(key=lambda t: (t["congress"], t["province"], t["name"]))
    with open(CLEAN / "rep_terms.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(terms[0]))
        wr.writeheader()
        wr.writerows(terms)
    print(f"{len(ra_to_bill)} acts linked to a House bill; {len(out)} with a named author; "
          f"{len(terms)} district representative-terms matched to OpenHalalan "
          f"({sum(1 for t in terms if t['family_seat'])} family seats)")


if __name__ == "__main__":
    main()
