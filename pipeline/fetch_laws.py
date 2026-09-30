"""Fetch the list of every Republic Act, and each act's full text, from lawphil.

The Arellano Law Foundation's LawPhil Project publishes one index page per
year (lawphil.net/statutes/repacts/raYYYY/raYYYY.html) and one page per act.
Index pages give the number, approval date, and title. Act pages give the
enacting Congress and session, the bills the act came from, and the text.

Outputs
  data/interim/ra_index.json   one record per act listed on an index page
  data/raw/lawphil/acts/*.html cached act pages (not committed; refetchable)
"""

import html
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import INTERIM, RAW, USER_AGENT, fetch, log_provenance, write_json

BASE = "https://lawphil.net/statutes/repacts"
YEARS = range(1946, 2027)

ROW_SPLIT = re.compile(r"<tr\b[^>]*>", re.I)
NUM = re.compile(r"Republic Act No\.?\s*([0-9]+)", re.I)
HREF = re.compile(r'<a\s+href="(ra_[0-9]+_[0-9]{4}\.html)"', re.I)
DATE = re.compile(r"<br\s*/?>\s*([A-Z][a-z]+\.?\s+[0-9]{1,2},\s*[0-9]{4})")


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_index(year, text):
    # Drop commented-out placeholder rows (acts listed before publication).
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    rows = []
    for chunk in ROW_SPLIT.split(text)[1:]:
        cells = re.split(r"</td>\s*<td[^>]*>", chunk, flags=re.I)
        m = NUM.search(cells[0])
        if not m:
            continue
        href = HREF.search(cells[0])
        d = DATE.search(cells[0])
        title = clean(cells[1]) if len(cells) > 1 else ""
        rows.append({
            "ra": int(m.group(1)),
            "year_page": year,
            "date_text": d.group(1) if d else None,
            "title": title,
            "href": f"{BASE}/ra{year}/{href.group(1)}" if href else None,
        })
    return rows


def fetch_index():
    out = []
    for y in YEARS:
        body = fetch(f"{BASE}/ra{y}/ra{y}.html", RAW / "lawphil" / "index" / f"ra{y}.html",
                     note=f"LawPhil index of Republic Acts approved in {y}")
        if body is None:
            continue
        out.extend(parse_index(y, body.decode("latin-1")))
    # A few acts appear on two year pages; keep the first listing.
    seen, dedup = set(), []
    for r in sorted(out, key=lambda r: (r["ra"], r["year_page"])):
        if r["ra"] in seen:
            continue
        seen.add(r["ra"])
        dedup.append(r)
    write_json(INTERIM / "ra_index.json", dedup)
    return dedup


def _curl(url, dest):
    """Bulk fetch with a hard wall-clock limit per page (requests can stall on slow reads)."""
    if dest.exists() and dest.stat().st_size > 500:
        return True
    tmp = dest.with_suffix(".part")
    for _ in range(3):
        r = subprocess.run(["curl", "-sfL", "--max-time", "45", "-A", USER_AGENT, "-o", str(tmp), url])
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 500:
            tmp.rename(dest)
            time.sleep(0.2)
            return True
        time.sleep(3)
    return False


def fetch_acts(rows, workers=4):
    todo = [r for r in rows if r["href"]]
    outdir = RAW / "lawphil" / "acts"
    outdir.mkdir(parents=True, exist_ok=True)
    done = failed = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(_curl, r["href"], outdir / r["href"].rsplit("/", 1)[1]): r for r in todo}
        for f in as_completed(futs):
            ok = f.result()
            done += 1
            failed += 0 if ok else 1
            if not ok:
                print("ERR", futs[f]["ra"], file=sys.stderr, flush=True)
            if done % 500 == 0:
                print(f"{done}/{len(todo)} act pages ({failed} failed)", flush=True)
    log_provenance({
        "file": "data/raw/lawphil/acts/",
        "source_url": f"{BASE}/raYYYY/ra_NNNN_YYYY.html",
        "note": f"LawPhil full-text pages for {len(todo)} Republic Acts ({failed} failed; cached, not committed)",
    })


if __name__ == "__main__":
    rows = fetch_index()
    print(len(rows), "acts in index;", min(r["ra"] for r in rows), "to", max(r["ra"] for r in rows))
    if "--acts" in sys.argv:
        fetch_acts(rows)
