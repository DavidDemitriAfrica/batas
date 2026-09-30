"""Every House bill filed since 1987, from BetterGov's open-congress-data.

bettergovph/open-congress-data (CC0) mirrors the House and Senate records:
one TOML file per bill with its title, filing date, principal author and
co-authors, committee referrals, and history. For the 13th Congress on, the
history records the Republic Act a bill became, and the House's own
"Local"/"National" scope tag.

Outputs
  data/interim/house_bills.csv.gz  one row per House bill (8th-20th Congress)
  data/interim/house_people.json   author code -> person
"""

import csv
import glob
import gzip
import re
import subprocess
import tomllib
from pathlib import Path

from common import INTERIM, RAW, log_provenance, write_json

REPO = "https://github.com/bettergovph/open-congress-data"
PIN = "6e853ee027790427c5b5961c6318ff907cf717d5"
DEST = RAW / "open-congress-data"

RA = re.compile(r"REPUBLIC\s+ACT\s*(?:NO\.?|NUMBER)?\s*([0-9]{3,5})", re.I)
APPROVED = re.compile(r"(approved by the president|signed into law|enacted into law|lapsed into law|became (?:republic act|law))", re.I)


def ensure_repo():
    if not DEST.exists():
        subprocess.run(["git", "clone", "-q", REPO, str(DEST)], check=True)
        subprocess.run(["git", "-C", str(DEST), "checkout", "-q", PIN], check=True)
        log_provenance({"file": "data/raw/open-congress-data/", "source_url": REPO, "commit": PIN,
                        "note": "BetterGov open-congress-data (CC0): House and Senate bills and members"})


def people():
    out = {}
    for f in glob.glob(str(DEST / "data" / "person" / "*.toml")):
        d = tomllib.load(open(f, "rb"))
        house = sorted(m["congress"] for m in d.get("memberships", []) if m.get("subtype") == "house")
        senate = sorted(m["congress"] for m in d.get("memberships", []) if m.get("subtype") == "senate")
        rec = {"id": d["id"], "last": d.get("last_name", ""), "first": d.get("first_name", ""),
               "middle": d.get("middle_name", ""), "house": house, "senate": senate}
        for k in d.get("congress_website_author_keys", []):
            out[k] = rec
    return out


def main():
    if not DEST.exists() and (INTERIM / "house_bills.csv.gz").exists() and "--refresh" not in __import__("sys").argv:
        print("using committed data/interim/house_bills.csv.gz (pass --refresh to rebuild from BetterGov)")
        return
    ensure_repo()
    ppl = people()
    rows = []
    for f in glob.glob(str(DEST / "data" / "document" / "hb" / "*" / "*.toml")):
        d = tomllib.load(open(f, "rb"))
        m = d.get("meta", {})
        hist = d.get("history", []) or []
        ra, ra_date = None, None
        for i, h in enumerate(hist):
            a = h.get("action", "")
            mm = RA.search(a)
            if mm and (APPROVED.search(a) or (i and APPROVED.search(hist[i - 1].get("action", ""))) or "REPUBLIC ACT NO" in a.upper()):
                ra, ra_date = int(mm.group(1)), h.get("date")
        st = d.get("status", []) or []
        codes = m.get("congress_website_author_codes") or []
        auth = codes[0] if codes else None
        p = ppl.get(auth)
        rows.append({
            "congress": m.get("congress"), "bill": m.get("bill_number"), "date_filed": m.get("date_filed"),
            "title": (m.get("title") or "").strip(),
            "long_title": (m.get("long_title") or m.get("congress_website_title") or "").strip(),
            "scope_house": m.get("scope"), "author_code": auth,
            "author": f"{p['first']} {p['last']}".strip() if p else "",
            "author_last": p["last"] if p else "", "author_id": p["id"] if p else "",
            "n_authors": len(set(codes)), "status": st[-1]["status"] if st else "",
            "status_date": st[-1].get("date") if st else "", "ra": ra, "ra_history_date": ra_date,
            "committee": ((d.get("committees") or [{}])[0]).get("name", ""),
        })
    rows.sort(key=lambda r: (r["congress"] or 0, r["bill"] or 0))
    out = INTERIM / "house_bills.csv.gz"
    with gzip.open(out, "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    write_json(INTERIM / "house_people.json", ppl)
    resolved = sum(1 for r in rows if r["author"])
    print(f"{len(rows)} House bills; principal author resolved for {resolved} ({resolved/len(rows):.1%}); "
          f"{sum(1 for r in rows if r['ra'])} linked to a Republic Act")


if __name__ == "__main__":
    main()
