"""Merge the act lists into one table and read facts out of each act's text.

From the full text of each act (LawPhil, or Chan Robles for the gaps) we read:
  title           the act's own title, used when the index title is garbled,
                  cut off, or copied from a neighbouring act
  congress        the enacting Congress, from the "Nth Congress" header, else
                  from the dates the Senate and House passed the bill
  bills           the House and Senate bill numbers the act came from
  lapsed          True when the act became law without the President's signature
  funding         how the act says it will be paid for (GAA, agency budget, none)

BetterGov's House records (data/interim/house_bills.csv.gz) add three things:
the Congress of the House bill an act came from, when the act's text does not
say; acts the House records as "Lapsed Into Law"; and the 22 acts that neither
library has, with the House bill's title and the House's status date.

Output: data/interim/laws_base.json
"""

import csv
import gzip
import html
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path

from common import INTERIM, RAW, read_json, write_json

ORD = {w: i for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
    "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split(), start=1)}
ORD.update({f"{i}{s}": i for i in range(1, 21) for s in ("st", "nd", "rd", "th")})
ORD.update({"nineth": 9, "nineteeth": 19})  # spellings used in some LawPhil headers

# Congress terms. Pre-1972 numbering runs 1st to 7th; the 1987 Constitution
# restarted at the 8th. Acts can be signed a few weeks after a Congress ends.
TERMS = [
    (1, date(1946, 5, 25), date(1949, 12, 29)), (2, date(1949, 12, 30), date(1953, 12, 29)),
    (3, date(1953, 12, 30), date(1957, 12, 29)), (4, date(1957, 12, 30), date(1961, 12, 29)),
    (5, date(1961, 12, 30), date(1965, 12, 29)), (6, date(1965, 12, 30), date(1969, 12, 29)),
    (7, date(1969, 12, 30), date(1973, 1, 16)),
    (8, date(1987, 7, 27), date(1992, 7, 26)), (9, date(1992, 7, 27), date(1995, 7, 23)),
    (10, date(1995, 7, 24), date(1998, 7, 26)), (11, date(1998, 7, 27), date(2001, 7, 22)),
    (12, date(2001, 7, 23), date(2004, 7, 25)), (13, date(2004, 7, 26), date(2007, 7, 22)),
    (14, date(2007, 7, 23), date(2010, 7, 25)), (15, date(2010, 7, 26), date(2013, 7, 21)),
    (16, date(2013, 7, 22), date(2016, 7, 24)), (17, date(2016, 7, 25), date(2019, 7, 21)),
    (18, date(2019, 7, 22), date(2022, 7, 24)), (19, date(2022, 7, 25), date(2025, 7, 27)),
    (20, date(2025, 7, 28), date(2028, 7, 23)),
]

PRESIDENTS = [
    ("Roxas", date(1946, 5, 28), date(1948, 4, 15)), ("Quirino", date(1948, 4, 17), date(1953, 12, 30)),
    ("Magsaysay", date(1953, 12, 30), date(1957, 3, 17)), ("Garcia", date(1957, 3, 18), date(1961, 12, 30)),
    ("Macapagal", date(1961, 12, 30), date(1965, 12, 30)), ("Marcos Sr.", date(1965, 12, 30), date(1986, 2, 25)),
    ("Aquino", date(1986, 2, 25), date(1992, 6, 30)), ("Ramos", date(1992, 6, 30), date(1998, 6, 30)),
    ("Estrada", date(1998, 6, 30), date(2001, 1, 20)), ("Arroyo", date(2001, 1, 20), date(2010, 6, 30)),
    ("Aquino III", date(2010, 6, 30), date(2016, 6, 30)), ("Duterte", date(2016, 6, 30), date(2022, 6, 30)),
    ("Marcos Jr.", date(2022, 6, 30), date(2028, 6, 30)),
]


SMALL = set("a an and as at by de del dela for from in into its of on or the to with ng sa y".split())
ROMAN = re.compile(r"^(ii|iii|iv|vi|vii|viii|ix|xi|xii|xiii)$", re.I)
ACRONYM = re.compile(r"^\(([A-Z][A-Z0-9&.\-]{1,11})\)[,;:.]?$")  # (LTO), (DSWD), (PSU-CCRD)
# Windows-1252 punctuation that some pages carry as C1 control characters
CP1252 = str.maketrans({"\x91": "'", "\x92": "'", "\x93": '"', "\x94": '"', "\x96": "-", "\x97": "-",
                        "\x85": "...", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})


def _cap(w):
    return re.sub(r"[a-z\u00e0-\u00ff]", lambda m: m.group(0).upper(), w, count=1)


def _cap_hyphenated(w):
    """Capitalise each part of a hyphenated word, except after a short prefix that marks
    a glottal stop (Bag-ong, Pag-asa) and small words (Walk-in)."""
    parts = w.split("-")
    out = [_cap(parts[0])]
    for prev, p in zip(parts, parts[1:]):
        core = p.strip("(\"'.,;:)")
        glottal = (len(prev) <= 4 and prev[-1:].isalpha() and prev[-1:].lower() not in "aeiou"
                   and core[:1].lower() in "aeiou")
        out.append(p if (glottal or core in SMALL) else _cap(p))
    return "-".join(out)


def smart_title(s):
    """Title-case titles that a source printed in all capitals or all lower case."""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s
    upper = sum(c.isupper() for c in letters) / len(letters)
    if 0.15 < upper < 0.85:
        return s
    out = []
    orig = s.split(" ")
    for i, w in enumerate(s.lower().split(" ")):
        core = w.strip("(\"'.,;:")
        if upper >= 0.85 and ACRONYM.match(orig[i]):
            out.append(orig[i])
        elif ROMAN.match(core):
            out.append(w.upper())
        elif re.fullmatch(r"\(?(?:[a-z]\.)+[,;:)]*", w):  # initials: "Hilarion A. Ramiro", "J.P. Rizal"
            out.append(w.upper())
        elif i > 0 and core in SMALL:
            out.append(w)
        else:
            out.append(_cap_hyphenated(w))
    return " ".join(out)


MONTHS = ("January February March April May June July August September October November December").split()


def parse_date(s):
    if not s:
        return None
    s = re.sub(r"\s+", " ", s.replace(".", "")).strip()
    s = s.replace("Sept ", "Sep ")
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d,%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    # "OCT 23 2025", and typos in the index such as "Februaty 12, 2001" or "Novemer 11, 2015"
    m = re.fullmatch(r"([A-Za-z]+) (\d{1,2}),? ?(\d{4})", s)
    if not m:
        return None
    word = m.group(1).capitalize()
    month = next((i for i, n in enumerate(MONTHS, 1) if len(word) >= 3 and n.startswith(word)), None)
    if month is None:
        close = get_close_matches(word, MONTHS, n=1, cutoff=0.7)
        month = MONTHS.index(close[0]) + 1 if close else None
    try:
        return date(int(m.group(3)), month, int(m.group(2))) if month else None
    except ValueError:
        return None


# Congresses before 1972 began their terms on December 30 but first met on the
# fourth Monday of January, so an act signed in between belongs to the old Congress.
CONVENED = {2: date(1950, 1, 23), 3: date(1954, 1, 25), 4: date(1958, 1, 27), 5: date(1962, 1, 22),
            6: date(1966, 1, 24), 7: date(1970, 1, 26)}


def congress_of_date(d):
    if d is None:
        return None
    for n, a, b in TERMS:
        if a <= d <= b:
            return n
    # a signature after the term ended belongs to the Congress that just closed
    prev = None
    for n, a, b in TERMS:
        if d > b:
            prev = n
    return prev


def president_of(d):
    if d is None:
        return None
    for n, a, b in PRESIDENTS:
        if a <= d < b:
            return n
    return None


def text_of(raw):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


CONG = re.compile(r"(?<![\w-])(" + "|".join(sorted(ORD, key=len, reverse=True)) + r")\s+congress\b", re.I)
HB = re.compile(r"\b(?:house bill|h\.\s*b\.|h\.\s*no\.|h\.\s*bill)\s*(?:no\.?|nos\.?|number)?\s*([0-9]{1,5})", re.I)
SB = re.compile(r"\b(?:senate bill|s\.\s*b\.|s\.\s*no\.|s\.\s*bill)\s*(?:no\.?|nos\.?|number)?\s*([0-9]{1,5})", re.I)
LAPSED = re.compile(r"lapsed\s+into\s+law|became\s+law\s+without|without\s+(?:the\s+)?(?:executive\s+)?(?:approval|signature)\s+of\s+the\s+president|"
                    r"pursuant\s+to\s+(?:the\s+provisions\s+of\s+)?(?:section|sec\.)\s*27\s*\(1\)", re.I)
GAA = re.compile(r"general appropriations act|annual appropriations|included in the (?:annual )?(?:budget|appropriation)", re.I)
CURRENT = re.compile(r"(?:charged|taken) (?:against|from) the (?:current|existing|available)|out of any funds in the national treasury|"
                     r"current year'?s appropriations?|is hereby appropriated", re.I)


TITLE_END = re.compile(r"\bBe\s+it\s+(?:enacted|ordained)\b", re.I)
TITLE_END2 = re.compile(r"\b(?:Section|SECTION|Sec\.|SEC\.)\s*1\b")
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_IN_TEXT = re.compile(r"\b(" + MONTH + r")\s+(\d{1,2})\s*,?\s*(\d{4})", re.I)
PASSED = re.compile(r"\b(?:finally\s+)?(?:passed|approved)\s+by\s+the\s+(?:senate|house)", re.I)
TAIL_DATE = re.compile(r"(?:approved|lapsed\s+into\s+law\s+on)\s*[:,]?\s*(" + MONTH + r")\s+(\d{1,2})\s*,?\s*(\d{4})", re.I)
SIGN_BLOCK = re.compile(r"\(sgd\.?\)|\bapproved\s*[:,]|lapsed\s+into\s+law|president\s+of\s+the\s+philippines", re.I)


def title_from_text(t, ra):
    """The title as printed in the act, between 'REPUBLIC ACT No. N' and 'Be it enacted'."""
    head = t[:6000]
    e = TITLE_END.search(head) or TITLE_END2.search(head)
    if not e:
        return None
    pre = head[:e.start()]
    ms = list(re.finditer(r"REPUBLIC\s+ACT\s+(?:No\.?|Number|Numbered)?\s*" + str(ra) +
                          r"\b\s*(?:,\s*" + MONTH + r"\s+\d{1,2}\s*,?\s*\d{4})?\s*\]?", pre, re.I))
    if not ms:
        return None
    s = pre[ms[-1].end():].translate(CP1252)
    if re.match(r"\s*This\s+Act\s+which", s, re.I):
        return None
    m = re.search(r"Begun\s+and\s+held\b.*?\.\s", s, re.S | re.I)  # session header printed after the number
    if m:
        s = s[m.end():]
    s = re.sub(r"^\s*\w+\s+Congress\s+\w+\s+(?:Regular|Special)\s+Session\s*", "", s, flags=re.I)
    m = re.search(r"\bAN\s+ACT\b", s, re.I)
    if m and m.start() > 0 and re.search(r"amend|repeal|congress|session|\d{4}|\(|R\.?\s*A\.?\s*\d", s[:m.start()], re.I):
        s = s[m.start():]  # drop editors' notes such as "(as amended by RA 2077)"
    s = re.split(r"\bWHEREAS\b", s, flags=re.I)[0]
    # a heading printed right after the title: "ARTICLE I Title of Act", "CHAPTER I General Provisions"
    s = re.split(r"\b(?:ARTICLE|CHAPTER)\s+(?:I|1|ONE)\b(?!\s*(?:,|\.|of\b|and\b|to\b|hundred|thousand))", s, flags=re.I)[0]
    s = re.sub(r"\s+", " ", s).strip(" .:*")
    s = re.sub(r"\s*\((?:repealed|amended|as amended|re)\b[^)]*\)\s*$", "", s, flags=re.I).strip(" .:*")
    return s if len(s) >= 10 else None


def passage_dates(tail):
    """Dates in the closing statement 'This Act ... was passed by the Senate ... on May 20, 2025'."""
    m = PASSED.search(tail)
    if not m:
        return []
    seg = tail[m.start(): m.start() + 700]
    stop = SIGN_BLOCK.search(seg, 20)
    if stop:
        seg = seg[:stop.start()]
    out = []
    for mo, d, y in DATE_IN_TEXT.findall(seg):
        dt = parse_date(f"{mo} {d}, {y}")
        if dt:
            out.append(dt.isoformat())
    return sorted(set(out))


def text_dates(head, tail, ra):
    """Approval date printed in the act: 'Approved: July 3, 2015' at the end, and the
    editors' header '[ REPUBLIC ACT No. N, June 22, 1961 ]'."""
    signed = None
    for m in list(TAIL_DATE.finditer(tail))[::-1]:
        signed = parse_date(f"{m.group(1)} {m.group(2)}, {m.group(3)}")
        if signed:
            break
    header = None
    if ra:
        m = re.search(r"REPUBLIC\s+ACT\s+No\.?\s*" + str(ra) + r"\s*,\s*(" + MONTH + r")\s+(\d{1,2})\s*,?\s*(\d{4})", head, re.I)
        header = parse_date(f"{m.group(1)} {m.group(2)}, {m.group(3)}") if m else None
    return {"signed_text": signed.isoformat() if signed else None, "header_date": header.isoformat() if header else None}


GARBLED = re.compile(r"\ufffd|\\[a-z]{3,}|\{\\|&[A-Za-z]{3,8}\b|\u00c3|\u00e2\u20ac")
DANGLING = re.compile(r"\b(?:of|the|and|in|to|for|an?|as|by|under|with|from|amending|entitled|numbered|or|at|on|its|"
                      r"into|otherwise)\s*$", re.I)
SHORT_TITLE_PREFIX = re.compile(r"^\W*(?P<short>(?:(?!\ban act\b).){4,120}?)\W*\s+(?P<long>an act\b.*)$", re.I | re.S)


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fix_mojibake(s):
    if "\u00c3" in s or "\u00e2\u20ac" in s:
        try:
            return s.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def clean_gap_title(t):
    """Chan Robles pages run the title into the preamble, the approval line and the site's menu."""
    t = re.split(r"\bWhereas\b|\bApproved\s*:|\bBack to Main\b|chan\s*robles", t, flags=re.I)[0]
    words = re.sub(r"\s+", " ", t).strip(" .,;:").split()
    n = len(words)
    if n % 2 == 0 and words[: n // 2] == words[n // 2:]:  # the title printed twice
        words = words[: n // 2]
    return " ".join(words)


def choose_title(index_title, text_title, index_is_dup):
    """Keep LawPhil's index title unless it is garbled, cut off, or belongs to another act."""
    it = fix_mojibake(re.sub(r"\s+", " ", index_title or "").translate(CP1252)).strip()
    it = re.sub(r"\s*\((?:repealed|amended|as amended)\b[^)]*\)?\s*$", "", it, flags=re.I)
    m = SHORT_TITLE_PREFIX.match(it)
    if m and not re.match(r"\W*an act\b", it, re.I) and re.search(r"\b(?:act|law|code|charter|carta)\b", m["short"], re.I):
        it = "An Act" + m["long"][6:]  # "Speedy Trial Act of 1998 an Act to Ensure..." -> "An Act to Ensure..."
    m = re.match(r'^\s*["\u201c].{3,160}?\s(an act\b.*)$', it, re.S | re.I)  # '"Ninoy Aquino Day" an Act Declaring...'
    if m:
        it = "An Act" + m.group(1)[6:]
    it = it.replace("\ufffd", " ")
    if not text_title:
        return it, "index"
    tt = text_title
    ok_text = not GARBLED.search(tt) and not DANGLING.search(tt) and len(tt) >= 20
    starts_act = re.match(r"an\s+act\b", tt, re.I) is not None
    r = SequenceMatcher(None, _norm(it).split(), _norm(tt).split(), autojunk=False).ratio()
    if (GARBLED.search(it) or DANGLING.search(it) or len(it) < 12) and ok_text:
        return tt, "act text"
    if ok_text and starts_act and len(tt) >= 30 and (r < 0.5 or (index_is_dup and r < 0.8)):
        return tt, "act text"
    # an index title shared with another act, where the act's own title names a different place or grantee
    a, b = set(_norm(it).split()) - SMALL, set(_norm(tt).split()) - SMALL
    new = [w for w in b - a if not get_close_matches(w, list(a), n=1, cutoff=0.75)]
    gone = [w for w in a - b if not get_close_matches(w, list(b), n=1, cutoff=0.75)]
    if index_is_dup and ok_text and starts_act and len(new) + len(gone) >= 2:
        return tt, "act text"
    return it, "index"


def fulltext_facts(t, ra=None):
    head = t[:3000]
    m = CONG.search(head)
    cong = ORD[m.group(1).lower()] if m else None
    tail = t[-6000:]
    hbs = sorted({int(x) for x in HB.findall(tail)} | {int(x) for x in HB.findall(head[:1500])})
    sbs = sorted({int(x) for x in SB.findall(tail)} | {int(x) for x in SB.findall(head[:1500])})
    lapsed = bool(LAPSED.search(tail))
    if GAA.search(t):
        funding = "gaa"
    elif CURRENT.search(t):
        funding = "current"
    else:
        funding = "none_stated"
    return {"congress_text": cong, "hb": hbs, "sb": sbs, "lapsed": lapsed, "funding": funding,
            "n_words": len(t.split()), "passed": passage_dates(tail), **text_dates(head, tail, ra),
            "text_title": title_from_text(t, ra) if ra else None}


HOUSE_BILLS = INTERIM / "house_bills.csv.gz"


def house_records():
    """House bills that became Republic Acts, keyed by act number."""
    by_ra = defaultdict(list)
    if not HOUSE_BILLS.exists():
        return by_ra
    with gzip.open(HOUSE_BILLS, "rt") as fh:
        for b in csv.DictReader(fh):
            if b["ra"].isdigit():
                by_ra[int(b["ra"])].append(b)
    return by_ra


def assign_congress(laws, house):
    """Enacting Congress, from the best evidence available for each act.

    1. the act's header ("Nineteenth Congress, Third Regular Session")
    2. the dates the act says the Senate and House passed it
    3. the Congress of the House bill it came from (BetterGov)
    4. the approval date. An act signed in the first months of a new Congress
       without any of the above is assigned to the Congress that just closed
       when its number comes before the new Congress's first act identified
       by 1-3, since act numbers are issued in order.
    """
    for L in laws:
        d = date.fromisoformat(L["date"]) if L["date"] else None
        by_date = congress_of_date(d)
        ct = L.get("congress_text")
        passed = [date.fromisoformat(x) for x in L.get("passed", []) if not d or x <= L["date"]]
        hb = {int(b["congress"]) for b in house.get(L["ra"], [])}
        if ct and (by_date is None or abs(ct - by_date) <= 1):
            L["congress"], L["congress_from"] = ct, "header"
        elif passed and congress_of_date(max(passed)):
            L["congress"], L["congress_from"] = congress_of_date(max(passed)), "passage date"
        elif len(hb) == 1:
            L["congress"], L["congress_from"] = hb.pop(), "house record"
        else:
            L["congress"], L["congress_from"] = by_date, ("approval date" if by_date else None)
    first = {}
    for L in sorted(laws, key=lambda L: L["ra"]):
        if L["congress_from"] in ("header", "passage date", "house record"):
            first.setdefault(L["congress"], L["ra"])
    opening = {n: a for n, a, _ in TERMS}
    for L in laws:
        n = L["congress"]
        if L["congress_from"] != "approval date":
            continue
        d = date.fromisoformat(L["date"])
        if n in CONVENED and d < CONVENED[n]:
            L["congress"], L["congress_from"] = n - 1, "approval date"
        elif n >= 9 and d <= opening[n] + timedelta(days=120) and L["ra"] < first.get(n, 10 ** 6):
            L["congress"], L["congress_from"] = n - 1, "act number"
    # Undated acts: act numbers are issued in order, so take the neighbours' Congress when they agree.
    laws.sort(key=lambda L: L["ra"])
    for i, L in enumerate(laws):
        if L["congress"] is None:
            prev = next((laws[j]["congress"] for j in range(i - 1, -1, -1) if laws[j]["congress"]), None)
            nxt = next((laws[j]["congress"] for j in range(i + 1, len(laws)) if laws[j]["congress"]), None)
            if prev == nxt:
                L["congress"], L["congress_from"] = prev, "neighbouring acts"


def main():
    idx = read_json(INTERIM / "ra_index.json")
    gaps = read_json(INTERIM / "ra_gaps.json")
    house = house_records()
    acts_dir = RAW / "lawphil" / "acts"
    # Facts read from the act pages are cached in act_facts.json, which is committed,
    # so the tables can be rebuilt without re-downloading 12,000 pages.
    facts_path = INTERIM / "act_facts.json"
    cached = {int(k): v for k, v in read_json(facts_path).items()} if facts_path.exists() else {}
    facts = {}
    laws = []
    for r in idx:
        L = {k: r[k] for k in ("ra", "title", "date_text", "href")}
        L["source"] = "lawphil"
        page = acts_dir / r["href"].rsplit("/", 1)[1] if r.get("href") else None
        if page and page.exists():
            f = fulltext_facts(text_of(page.read_bytes().decode("latin-1")), r["ra"])
        else:
            f = cached.get(r["ra"])
        if f:
            L.update(f)
            facts[r["ra"]] = f
        laws.append(L)
    for r in gaps:
        L = {k: r[k] for k in ("ra", "title", "date_text", "href")}
        L["source"] = "chanrobles"
        L.update(fulltext_facts(r["fulltext"]))
        L["lapsed"] = L["lapsed"] or r.get("lapsed_text", False)
        laws.append(L)
    # Acts in neither library: take the House bill that became the act.
    have = {L["ra"] for L in laws}
    for ra, bs in sorted(house.items()):
        if ra in have:
            continue
        done = [b for b in bs if b["status"].startswith(("Approved by the President", "Lapsed Into Law"))]
        b = (done or bs)[0]
        d = date.fromisoformat(b["status_date"]) if done and b["status_date"] else None
        laws.append({"ra": ra, "title": b["long_title"] or b["title"],
                     "date_text": d.strftime("%B %d, %Y") if d else "", "href": None, "source": "house record",
                     "lapsed": b["status"] == "Lapsed Into Law", "hb": [int(b["bill"])] if b["bill"].isdigit() else []})
    dup = Counter(_norm(L["title"]) for L in laws)
    titles_from_text = 0
    for L in laws:
        # the index date; else the act's "Approved:" line; else the House record; else the editors' header
        d = parse_date(L["date_text"])
        L["date_from"] = ("house record" if L["source"] == "house record" else "index") if d else None
        house_dates = [b["status_date"] for b in house.get(L["ra"], [])
                       if b["status"].startswith(("Approved by the President", "Lapsed Into Law")) and b["status_date"]]
        for src, v in (("act text", L.get("signed_text")), ("house record", house_dates[0] if house_dates else None),
                       ("act header", L.get("header_date"))):
            if d is None and v:
                d, L["date_from"] = date.fromisoformat(v), src
        L["date"] = d.isoformat() if d else None
        L["year"] = d.year if d else None
        L["president"] = president_of(d)
        if L["source"] == "lawphil":
            t, how = choose_title(L["title"], L.get("text_title"), dup[_norm(L["title"])] > 1)
            titles_from_text += how == "act text"
            L["title_from"] = how
        elif L["source"] == "chanrobles":
            t = clean_gap_title(fix_mojibake(L["title"].translate(CP1252)))
        else:
            t = fix_mojibake(L["title"].translate(CP1252))
        t = re.sub(r"\s*&\s*-\s*", " - ", t)  # a broken "&mdash;"
        L["title"] = smart_title(re.sub(r"\s+", " ", t).strip())
        L.pop("text_title", None)
        # the House's record of acts that became law without the President's signature
        if not L.get("lapsed") and any(b["status"] == "Lapsed Into Law" for b in house.get(L["ra"], [])):
            L["lapsed"], L["lapsed_from"] = True, "house record"
        elif L.get("lapsed"):
            L["lapsed_from"] = "house record" if L["source"] == "house record" else "act text"
    assign_congress(laws, house)
    write_json(INTERIM / "laws_base.json", laws)
    write_json(facts_path, {str(k): v for k, v in sorted(facts.items())})
    have_text = sum(1 for L in laws if "n_words" in L)
    how = Counter(L.get("congress_from") for L in laws)
    print(f"{len(laws)} acts ({Counter(L['source'] for L in laws)}); {have_text} with full text; "
          f"{sum(1 for L in laws if L['date'])} dated; titles from act text: {titles_from_text}; "
          f"Congress from {dict(how)}; lapsed {sum(1 for L in laws if L.get('lapsed'))}")


if __name__ == "__main__":
    main()
