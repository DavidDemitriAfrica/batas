"""Build one table of every public school DepEd listed from SY 2017-18 to SY 2025-26.

Source: DepEd machine-ready files, School Characteristics: Enrollment
(deped.gov.ph/machine-ready-files). One CSV per school year, one row per
school. We keep public schools and record, for each school ID, its latest
name, location, annex status, which levels it offers, total enrolment in
each year, and every name it has been listed under.

Output: data/interim/deped_schools.json
"""

import csv
import io
import re
import zipfile
from collections import defaultdict

from common import INTERIM, RAW, write_json

YEARS = ["2017-2018", "2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023",
         "2023-2024", "2024-2025", "2025-2026"]
COUNT = re.compile(r"^(kinder|g\d+|esng|jhsng)_|^g1[12]_")


def rows_of(year):
    z = zipfile.ZipFile(RAW / "deped" / f"Enrollment-in-SY-{year}.zip")
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    raw = z.read(name)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return csv.DictReader(io.StringIO(text))


def truthy(v):
    return str(v).strip().lower() in ("true", "yes", "1")


def main():
    schools = {}
    names = defaultdict(set)
    for y in YEARS:
        sy = y[:4]
        for r in rows_of(y):
            sector = (r.get("sector") or "").strip()
            if not sector.lower().startswith("public"):
                continue
            sid = r["school_id"].strip()
            total = 0
            for k, v in r.items():
                if k and COUNT.match(k) and v not in (None, ""):
                    try:
                        total += int(float(v))
                    except ValueError:
                        pass
            s = schools.setdefault(sid, {"school_id": sid, "enrolment": {}})
            s.update({
                "name": re.sub(r"\s+", " ", r["school_name"]).strip(),
                "region": r["region"].strip(), "division": r["division"].strip(),
                "province": r["province"].strip(), "municipality": re.sub(r"\s+", " ", r["municipality"]).strip(),
                "barangay": re.sub(r"\s+", " ", r["barangay"] or "").strip(),
                "annex_status": (r.get("annex_status") or "").strip(),
                "offers_es": truthy(r.get("offers_es")), "offers_jhs": truthy(r.get("offers_jhs")),
                "offers_shs": truthy(r.get("offers_shs")), "last_year": sy,
            })
            s.setdefault("first_year", sy)
            s["enrolment"][sy] = total
            names[sid].add(s["name"])
    for sid, s in schools.items():
        s["names"] = sorted(names[sid])
    write_json(INTERIM / "deped_schools.json", list(schools.values()))
    latest = sum(1 for s in schools.values() if s["last_year"] == "2025")
    print(f"{len(schools)} public school IDs over nine school years; {latest} listed in SY 2025-26")


if __name__ == "__main__":
    main()
