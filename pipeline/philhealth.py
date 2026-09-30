"""Parse PhilHealth's list of accredited hospitals and infirmaries (as of July 31, 2026).

The PDF prints one row per facility with its name, bed count, service level,
municipality and sector (G government, P private), grouped under region and
province headings. We read the words by their x position and rebuild rows,
joining names that wrap onto the line above or below. Contact details in the
PDF are not kept.

Output: data/interim/philhealth_hospitals.json
"""

import re
from collections import defaultdict

import pdfplumber

from common import INTERIM, RAW, write_json

PDF = RAW / "philhealth" / "HOSP_073126.pdf"
COLS = [("num", 0, 30), ("name", 30, 230), ("beds", 230, 253), ("cat", 253, 287), ("tel", 287, 410),
        ("email", 410, 540), ("street", 540, 678), ("muni", 678, 765), ("expire", 765, 812), ("sec", 812, 900)]


def col_of(x):
    for c, a, b in COLS:
        if a <= x < b:
            return c
    return "sec"


def main():
    rows = []
    region = province = None
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            lines = defaultdict(list)
            for w in words:
                lines[round(w["top"] / 2)].append(w)
            keys = sorted(lines)
            recs, loose = [], []
            for k in keys:
                ws = sorted(lines[k], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws)
                if ws[0]["top"] < 75 or text.startswith("Page ") or "List of Accredited" in text:
                    continue
                if ws[0]["x0"] < 20 and not re.match(r"^\d+$", ws[0]["text"]):
                    if "REGION" in text or text in ("NCR", "BARMM", "CARAGA", "MIMAROPA"):
                        region = text
                    else:
                        province = text
                    continue
                cells = defaultdict(list)
                for w in ws:
                    cells[col_of(w["x0"])].append(w["text"])
                if cells.get("num") and re.match(r"^\d+$", cells["num"][0]):
                    recs.append({"top": ws[0]["top"], "cells": cells, "region": region, "province": province})
                else:
                    loose.append((ws[0]["top"], cells))
            for top, cells in loose:
                if not recs:
                    continue
                r = min(recs, key=lambda r: abs(r["top"] - top))
                if abs(r["top"] - top) > 13:
                    continue
                for c, v in cells.items():
                    r.setdefault("extra", defaultdict(list))[c].append((top, v))
            for r in recs:
                c = r["cells"]
                name_parts = [(r["top"], c.get("name", []))] + [(t, v) for t, v in r.get("extra", {}).get("name", [])]
                name = " ".join(" ".join(v) for t, v in sorted(name_parts))
                muni_parts = [(r["top"], c.get("muni", []))] + [(t, v) for t, v in r.get("extra", {}).get("muni", [])]
                muni = " ".join(" ".join(v) for t, v in sorted(muni_parts))
                bc = " ".join(c.get("beds", []) + c.get("cat", []))
                bc = re.sub(r"(\d)(LEVEL|INF)", r"\1 \2", bc)
                m = re.match(r"^\s*(\d+)?\s*(.*)$", bc)
                beds, cat = (m.group(1) or ""), m.group(2)
                if "Ã" in name or "Ã" in muni:
                    try:
                        name = name.encode("cp1252").decode("utf-8")
                        muni = muni.encode("cp1252").decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                rows.append({
                    "name": re.sub(r"\s+", " ", name).strip(), "beds": int(beds) if beds.isdigit() else None,
                    "category": cat.strip(), "municipality": re.sub(r"\s+", " ", muni).strip(),
                    "province": r["province"], "region": r["region"], "sector": " ".join(c.get("sec", [])).strip()[:1],
                })
    write_json(INTERIM / "philhealth_hospitals.json", rows)
    print(f"{len(rows)} accredited facilities; {sum(1 for r in rows if r['beds'])} with bed counts; "
          f"{sum(r['beds'] or 0 for r in rows):,} beds")


if __name__ == "__main__":
    main()
