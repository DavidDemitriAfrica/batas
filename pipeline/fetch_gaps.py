"""Fill acts missing from the LawPhil index using the Chan Robles Virtual Law Library.

LawPhil lacks roughly 330 act numbers, most of them from 1950 to 1952 and a
block from late 2022. Chan Robles lists every number in ranges of 100 and
links each to a full-text page, from which we take the title and the
approval date.

Output: data/interim/ra_gaps.json
"""

import html
import re

from common import INTERIM, RAW, fetch, read_json, write_json

BASE = "https://laws.chanrobles.com/republicacts"
LINK = re.compile(r"href='([0-9]+_republicacts\.php\?id=[0-9]+)'>\s*Republic Act No\.?\s*([0-9]+)", re.I)
APPROVED = re.compile(r"Approved\s*:?\s*([A-Z][a-z]+\.?\s+[0-9]{1,2}\s*,\s*[0-9]{4})")
LAPSED = re.compile(r"lapsed into law[^.]*?([A-Z][a-z]+\s+[0-9]{1,2},\s*[0-9]{4})", re.I)


def text_of(raw):
    t = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def main():
    have = {r["ra"] for r in read_json(INTERIM / "ra_index.json")}
    top = max(have)
    missing = [n for n in range(1, top + 1) if n not in have]
    pages = sorted({(n - 1) // 100 + 1 for n in missing})
    links = {}
    for p in pages:
        body = fetch(f"{BASE}/republicacts.php?id={p}", RAW / "chanrobles" / f"range_{p}.html",
                     note=f"Chan Robles index of Republic Acts {100*(p-1)+1}-{100*p}")
        for href, num in LINK.findall(body.decode("utf-8", "replace")):
            links[int(num)] = f"{BASE}/{href}"
    out = []
    for n in missing:
        if n not in links:
            continue
        body = fetch(links[n], RAW / "chanrobles" / f"ra_{n}.html",
                     note=f"Chan Robles full text of Republic Act No. {n}")
        if body is None:
            continue
        t = text_of(body.decode("utf-8", "replace"))
        m = re.search(rf"REPUBLIC ACT NO\.?\s*{n}\s*[-\u2013\u2014]\s*(.+?)(?=\s*:\s*(?:REPUBLIC ACTS|PHILIPPINE LAWS)"
                      rf"|\s+Be it enacted|\s+(?:Section|SECTION|Sec\.)\s*1\b|\s+[A-Z][a-z]+ (?:Tribune|Star|Times|Bulletin|Inquirer)"
                      rf"|\s+[0-9]+ O\.?G\.?|\s+REPUBLIC ACT NO)", t)
        if not m:
            continue
        title = m.group(1).strip()
        d = (re.search(rf"REPUBLIC ACT NO\.?\s*{n}\s*,\s*([A-Z][a-z]+\.?\s+[0-9]{{1,2}},\s*[0-9]{{4}})", t)
             or APPROVED.search(t) or LAPSED.search(t))
        lapsed = bool(re.search(r"lapsed into law", t, re.I))
        out.append({
            "ra": n,
            "year_page": None,
            "date_text": re.sub(r"\s+,", ",", d.group(1)) if d else None,
            "title": title[:1].upper() + title[1:].lower() if title.isupper() else title,
            "href": links[n],
            "source": "chanrobles",
            "lapsed_text": lapsed,
            "fulltext": t[m.start():][:60000],
        })
    write_json(INTERIM / "ra_gaps.json", out)
    print(f"{len(missing)} missing from LawPhil, {len(out)} filled from Chan Robles")


if __name__ == "__main__":
    main()
