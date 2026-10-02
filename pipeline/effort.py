"""How much Senate floor time each law took, and which laws the President certified as urgent.

The House record in BetterGov's open-congress-data gives each House bill's
status but not its floor history. The Senate's record does: for every Senate
bill, and every House bill sent to the Senate, from the 13th Congress (2004) on,
it lists each sponsorship speech, interpellation, period of amendments and vote
with its date. We link each Republic Act to the Senate records that end in it,
or that the act cites in its closing clause, and count:

  floor_days    days on which the Senate took the bill up after first reading:
                sponsorship, interpellation, amendments, the votes on second and
                third reading, and the conference committee report
  debate_days   days on which a senator interpellated the sponsor or spoke
                against the bill
  third_reading_with
                laws the Senate approved on third reading the same day,
                this one included
  batch         sponsored in an omnibus speech, or approved with other bills
                in a single motion

Under Article VI, Section 26(2) of the Constitution, the President can certify
a bill as urgent, which lets a chamber pass it on second and third reading on
the same day. The Senate record notes these certifications. The Presidential
Legislative Liaison Office (PLLO) published lists of certified bills for the
18th and 19th Congresses, which add bills certified to the House only. Its site
is offline, so the lists come from the Internet Archive. A law counts as
certified when either source says so.

Outputs
  data/interim/senate_floor.json  per act: Senate records and dated floor actions
  data/clean/law_effort.csv       one row per act from the 13th Congress on
"""

import csv
import glob
import re
import sys
import tomllib
from collections import Counter, defaultdict

import pdfplumber

from common import CLEAN, INTERIM, RAW, fetch, read_json, write_json
from house_bills import DEST, ensure_repo

FLOOR_JSON = INTERIM / "senate_floor.json"

PLLO = {
    18: "https://web.archive.org/web/20250408124917id_/https://pllo.gov.ph/images/Documents/Downloads/"
        "PriorityLegislativeMeasures/18C_Certified/20220728_18C_Summ_CertBills.pdf",
    19: "https://web.archive.org/web/20250408121110id_/https://pllo.gov.ph/images/Documents/Downloads/"
        "PriorityLegislativeMeasures/19thCongress/CertifiedBills.pdf",
}

FINAL = re.compile(r"^\s*REPUBLIC\s+ACT\s+NO\.?\s*([0-9]{4,5})", re.I)
FLOOR = re.compile(r"^(omnibus\s+)?(co-?)?sponsorship speech|^interpellations?\b|^period of (interpellation|amendment|"
                   r"committee amendment|individual amendment)|^turno en contra|^manifestation|^explanation of vote|"
                   r"^approved on (second|third) reading|^conference committee report.*approved by the senate|^motion of", re.I)
DEBATE = re.compile(r"^(interpellations? of|turno en contra)", re.I)
THIRD = re.compile(r"^approved on third reading", re.I)
BATCH = re.compile(r"^omnibus|^motion of .*\ball (the )?listed\b", re.I)
CERT = re.compile(r"certified (by the president|for (its )?immediate enactment)", re.I)


def senate_records():
    """Dated floor actions for every Senate record, keyed by the act it became and by bill number."""
    by_ra, by_bill = defaultdict(list), {}
    for f in glob.glob(str(DEST / "data" / "document" / "*" / "*" / "*.toml")):
        d = tomllib.load(open(f, "rb"))
        m = d.get("meta", {})
        hist = d.get("history") or []
        rec = {"doc": f"{d.get('subtype', '')}-{m.get('congress')}-{m.get('bill_number')}", "floor": [], "debate": [],
               "third": [], "batch": False, "certified": False}
        for h in hist:
            a, day = (h.get("action") or "").strip(), h.get("date")
            if CERT.search(a):
                rec["certified"] = True
            if not day:
                continue
            if FLOOR.search(a):
                rec["floor"].append(day)
            if DEBATE.search(a):
                rec["debate"].append(day)
            if THIRD.search(a):
                rec["third"].append(day)
            if BATCH.search(a):
                rec["batch"] = True
        by_bill[(d.get("subtype"), m.get("congress"), m.get("bill_number"))] = rec
        for h in hist:
            mm = FINAL.match(h.get("action") or "")
            if mm:
                by_ra[int(mm.group(1))].append(rec["doc"])
    return by_ra, {r["doc"]: r for r in by_bill.values()}, by_bill


def build_floor(laws):
    ensure_repo()
    by_ra, docs, by_bill = senate_records()
    out = {}
    for L in laws:
        c = L.get("congress") or 0
        if c < 13:
            continue
        names = set(by_ra.get(L["ra"], []))
        # bills the act cites in its closing clause, when the Senate record has them
        for kind, nums in (("SB", L.get("sb") or []), ("HB", L.get("hb") or [])):
            for n in nums:
                r = by_bill.get((kind, c, n))
                if r and r["floor"]:
                    names.add(r["doc"])
        recs = [docs[n] for n in sorted(names)]
        if not recs:
            continue
        out[L["ra"]] = {
            "docs": sorted(names),
            "floor": sorted({d for r in recs for d in r["floor"]}),
            "debate": sorted({d for r in recs for d in r["debate"]}),
            "third": max((d for r in recs for d in r["third"]), default=None),
            "batch": any(r["batch"] for r in recs),
            "certified": any(r["certified"] for r in recs),
        }
    write_json(FLOOR_JSON, out)
    return out


def pllo_certified():
    """Acts on PLLO's lists of bills certified for immediate enactment."""
    out = {}
    for c, url in PLLO.items():
        dest = RAW / "pllo" / url.rsplit("/", 1)[1]
        fetch(url, dest, note=f"PLLO summary of bills certified for immediate enactment, {c}th Congress "
                              "(Internet Archive copy; pllo.gov.ph is offline)")
        with pdfplumber.open(dest) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        for ra in re.findall(r"\bRA\s+No\.\s*([0-9]{5})", text):
            out[int(ra)] = c
    return out


def main():
    laws = read_json(INTERIM / "laws_geo.json")
    if DEST.exists() or not FLOOR_JSON.exists() or "--refresh" in sys.argv:
        floor = build_floor(laws)
    else:
        print("using committed data/interim/senate_floor.json (pass --refresh to rebuild from BetterGov)")
        floor = {int(k): v for k, v in read_json(FLOOR_JSON).items()}
    pllo = pllo_certified()
    same_day = Counter(f["third"] for f in floor.values() if f["third"])
    rows = []
    for L in sorted(laws, key=lambda L: L["ra"]):
        if (L.get("congress") or 0) < 13:
            continue
        f = floor.get(L["ra"])
        sen, pl = bool(f and f["certified"]), L["ra"] in pllo
        rows.append({
            "ra": L["ra"], "congress": L["congress"], "scope": L["scope"], "category": L["category"],
            "senate_records": "; ".join(f["docs"]) if f else "",
            "floor_days": len(f["floor"]) if f else "", "debate_days": len(f["debate"]) if f else "",
            "third_reading": (f["third"] or "") if f else "",
            "third_reading_with": same_day[f["third"]] if f and f["third"] else "",
            "batch": "yes" if f and f["batch"] else "",
            "certified": "yes" if sen or pl else "",
            "certified_source": "both" if sen and pl else "senate record" if sen else "PLLO" if pl else "",
        })
    with open(CLEAN / "law_effort.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    linked = sum(1 for r in rows if r["senate_records"])
    print(f"{len(rows)} acts from the 13th Congress on; {linked} linked to the Senate record; "
          f"{sum(1 for r in rows if r['certified'])} certified urgent "
          f"({sum(1 for r in rows if r['certified_source'] == 'PLLO')} from PLLO only)")


if __name__ == "__main__":
    main()
