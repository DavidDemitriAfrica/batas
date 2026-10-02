"""Sort every Republic Act into one category using its title.

Philippine law titles are formulaic ("An Act Establishing a National High
School in Barangay X, Municipality of Y, Province of Z ..."), so an ordered
list of patterns classifies them well. The first matching rule wins. Rules
are ordered from the most specific to the most general, and each rule is
checked against a hand-labelled sample (see validate_classifier.py).

Every law gets:
  category   one of CATEGORIES below
  scope      local (about one named place), private (one company or person),
             or national
  action     what the law does: establish, convert, separate, rename,
             upgrade, increase, create, grant, renew, declare, amend, other
  facility   the name after "to be known as", when the title gives one
  beds_from, beds_to   for laws that change a hospital's bed capacity
"""

import re

from common import INTERIM, read_json, write_json

CATEGORIES = {
    # key: (label, scope)
    "school":        ("Public schools", "local"),
    "college":       ("State universities and colleges", "local"),
    "hospital":      ("Hospitals and health facilities", "local"),
    "lgu":           ("New towns, cities, barangays and charters", "local"),
    "rename_place":  ("Renamed towns and barangays", "local"),
    "road":          ("Roads, bridges and streets", "local"),
    "court":         ("Court branches", "local"),
    "office":        ("Government offices and facilities", "local"),
    "holiday":       ("Local holidays", "local"),
    "district":      ("Legislative districts", "local"),
    "land":          ("Land grants, reservations and protected areas", "local"),
    "public_works":  ("Local public works funds", "local"),
    "other_local":   ("Other local laws", "local"),
    "franchise":     ("Franchises", "private"),
    "citizenship":   ("Citizenship grants", "private"),
    "private_other": ("Pensions, claims and other private grants", "private"),
    "commemoration": ("National days and symbols", "national"),
    "appropriation": ("Budgets and appropriations", "national"),
    "national":      ("National policy", "national"),
}

LOCAL_MARK = re.compile(
    r"\b(municipalit(y|ies)|province|city|cities|barangays?|barrios?|sitios?|poblacion|town of|island of)\b", re.I)

# Words that mark a national-scope law even when a place is named in passing.
NATIONAL_HINT = re.compile(
    r"\b(of the philippines|nationwide|in the philippines|throughout the (country|philippines)|all (cities|municipalities|provinces|barangays)|"
    r"(every|each) (city|municipality|province|barangay|region)|conference|embassy|legation|consulate)\b", re.I)

# Wording that applies a local kind of law to the whole country.
EVERYWHERE = re.compile(r"\b((all|every|each) (barangays?|cities|city|municipalit(y|ies)|provinces?|regions?)|nationwide|"
                        r"throughout the (country|philippines)|(in )?the entire country)\b", re.I)

SCHOOL = (r"(high ?school|elementary school|integrated school|primary school|central school|community school|paaralan|"
          r"science high\b|national (high school|trade|vocational|agricultural|fishery|comprehensive|school)\b|"
          r"(trade|vocational|agricultural|fishery|fisheries|arts and trades|rural|industrial|farm|normal) (high )?school|"
          r"school of (arts and trades|fisheries|agriculture)|barrio high|barangay high|community high|"
          r"secondary school|technical(-| )vocational high|agro(-| )industrial (high )?school|"
          r"pilot school|laboratory school|school for the (deaf|blind)|special education)")
COLLEGE = (r"(state (university|college|polytechnic)|polytechnic (university|college)|"
           r"college of (medicine|law|nursing|veterinary|agriculture|fisheries|engineering|arts|science|education)|"
           r"\buniversity\b|\bcollege\b|\bcampus\b|institute of technology|school of (medicine|law)|"
           r"community college|junior college|(state|national) institute)")
HOSPITAL = (r"(hospital|medical center|infirmar|health (center|centre|unit|office|station)|"
            r"sanitari|maternity|leprosarium|puericulture|clinic|dialysis|cancer center|heart center|"
            r"lying-in|rural health|bed capacity|emergency hospital|specialty center)")
LGU = (r"(creating (the |a |an )?(new )?(municipalit|city|cities|barangay|barrio|province|town)|"
       r"creating (certain|two|three|four|five|six|seven|eight|nine|ten|\d+|additional|several|one) "
       r"(new )?(barangays?|barrios?|municipalit)|"
       r"converting (the )?(municipality|town) of .* (into|to) (a |an )?(component |highly urbanized |independent )?city|"
       r"into a (component |highly urbanized |independent component )?city|cityhood|"
       r"charter of the city|city charter|\bcharter\b.*\bcity\b|"
       r"(merging|dividing|annexing|abolishing|consolidating|separating)\s+(?:[\w'.,-]+\s+){0,6}?(barangays?|barrios?|municipalit|sitios?|provinces?\b)|"
       r"constituting .*(into|as) (a |an )?(distinct|separate|independent|regular|new)? ?(barangay|barrio|municipalit)|"
       r"(transferring|fixing|defining|delineating) .*(seat of government|boundar|territorial)|"
       r"seat of (the )?(municipal|provincial) government|"
       r"into (a |an )?(distinct and independent|separate|regular|independent) (municipalit|barangay|barrio)|"
       r"(highly urbanized|component) city|plebiscite|"
       r"(special|chartered) city|subprovince|sub-province|regular province|township)")
RENAME_PLACE = (r"(chang(e|es|ing) the name of (the )?(barrio|barangay|municipality|town|province|city|sitio|poblacion|island)|"
                r"renam(e|es|ing) (the )?(barrio|barangay|municipality|town|province|city|sitio|island)|"
                r"chang(e|es|ing) the name of .* (municipality|province) (of|to)|"
                r"changing the names? of (certain|the) (barrios|barangays|municipalities|sitios))")
ROAD = (r"(\broads?\b|highway|bridge|street|avenue|boulevard|diversion|by-pass|bypass|circumferential|"
        r"expressway|causeway|flyover|interchange|tunnel|provincial road|national road|farm-to-market|"
        r"coastal road|\bdrive\b|lane\b)")
COURT = (r"(regional trial court|municipal trial court|municipal circuit trial court|metropolitan trial court|"
         r"court of first instance|municipal court|city court|circuit criminal court|juvenile and domestic|"
         r"family court|shari'?a|court branches|branches of the (regional|municipal)|additional branch|"
         r"judicial district|court of agrarian|justice of the peace|trial courts?)")
OFFICE = (r"(district engineering office|engineering district|district office|extension office|satellite office|"
          r"regional office|provincial office|field office|sub-office|land transportation office|"
          r"bureau of internal revenue|immigration|\blto\b|\bdar\b|\bdti\b|tesda|training (center|centre|institute)|"
          r"fish port|fishport|seaport|\bport\b|airport|landing|wharf|pier|lighthouse|"
          r"market|slaughterhouse|abattoir|waterworks|water system|irrigation|dam\b|reservoir|power plant|"
          r"electrification|station|nursery|seed farm|breeding|stock farm|experiment|demonstration farm|"
          r"research (center|station|and development)|hatchery|laboratory|museum|library|"
          r"sports (complex|center|academy)|coliseum|stadium|gymnasium|park\b|plaza|tourist|tourism|"
          r"eco-?tourism|police|fire (station|district)|jail|prison|penal|detention|drug (rehabilitation|abuse treatment)|"
          r"post office|postal|telegraph|telephone (system|exchange|office)|radio station of the|"
          r"cemetery|monument|shrine|historical|landmark|center for|centre for|hall of|convention center|"
          r"provincial (fiscal|assessor|treasurer|auditor|engineer)|assistant (provincial|city) fiscal|city fiscal|"
          r"economic zone|ecozone|freeport|special economic|industrial estate|export processing|development authority|"
          r"authority|commission on|board of|council of|office of|agency|bureau)")
HOLIDAY = (r"(special (non-?working|working) (holiday|day)|non-working holiday|legal holiday|public holiday|"
           r"holiday in the|founding anniversary|foundation day|charter day|araw ng|festival|fiesta)")
DISTRICT = (r"(legislative district|reapportion|congressional district|lone district|"
            r"(first|second|third|fourth|fifth|sixth|seventh|two|three|four|five|six|seven) (legislative )?districts?)")
LAND = (r"(protected (area|landscape|seascape)|natural park|national park|wildlife sanctuary|marine (reserve|sanctuary)|"
        r"forest reserve|watershed|mangrove|\breservation\b|townsite|parcels? of (public |private )?land|"
        r"(public|government|friar|private|agricultural|foreshore|marshy) lands?|lands? (owned|located|situated|reserved|of the public domain)|"
        r"(sale|lease|donation|transfer|conveyance|disposition) of (the |certain )?(public )?(lands?|lots?|parcels?|properties|property)|"
        r"\blots? (no|number)|real property|donat(e|ing) .* (land|lot|property)|reclassif|public domain|homestead|"
        r"cadastral|free patent|reclamation|foreshore|hot spring|mountain|\bmount\b|\bmt\.|lake\b|river\b|falls\b|cave)")
FRANCHISE = r"(franchise|temporary permit to (construct|establish|operate|install)|radio(-| )?(telephone|telegraph) station)"
CITIZENSHIP = (r"(granting (the )?(philippine )?citizenship|citizenship (to|upon|on) [A-Z]|conferring .*citizenship|"
               r"declaring .* (a )?citizens? of the philippines|adopting .* as (a )?(son|daughter) of the philippines|"
               r"naturaliz(ing|ation of) [A-Z])")
PRIVATE_OTHER = (r"(granting (a )?(pension|gratuity|life pension)|pension to|gratuity to|"
                 r"(payment|settlement|refund) of (the )?(claim|claims)|claim of|for the relief of|"
                 r"exempting the .* from (the payment|taxes|customs)|condoning|to pay (the )?(heirs|widow)|heirs of|widow of|"
                 r"granting (mr\.|mrs\.|miss|dr\.|attorney|atty\.)|authorizing .* to (practice|take the))")
COMMEMORATION = (r"(declaring .* (day|week|month|year) (of|in) (every|each) year|"
                 r"(national|international|world) .* (day|week|month)\b|(day|week|month) of (every|each) year|"
                 r"national (symbol|flower|tree|bird|animal|fish|dance|song|hero|artist|shrine|gem|language|costume|"
                 r"emblem|anthem|motto|seal|leaf|fruit|house)|"
                 r"postage stamps?|centennial|sesquicentennial|national (martial art|sport|game)|"
                 r"(day|week|month) in the entire (country|philippines)|observance of|throughout the entire philippines)")
APPROPRIATION = (r"(appropriating funds for public works$|appopriating funds for the operation of the government|defray the expenses of the national government|general appropriations|supplemental (appropriations|budget)|appropriating funds for the operation of the government|"
                 r"appropriating (funds|the sum|additional|the amount) .* (fiscal year|for the (operation|expenses))|"
                 r"public works (act|appropriations)|reappropriat|(fiscal|calendar) year (19|20)\d\d)")

NUM_WORDS = {
    "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "seventy-five": 75, "eighty": 80, "ninety": 90, "one hundred": 100,
    "one hundred fifty": 150, "two hundred": 200, "two hundred fifty": 250, "three hundred": 300,
    "four hundred": 400, "five hundred": 500, "six hundred": 600, "seven hundred": 700, "eight hundred": 800,
    "one thousand": 1000, "one thousand five hundred": 1500, "two thousand": 2000,
}


def rx(p):
    return re.compile(p, re.I)


# Province names, current and historical, for titles such as "in Malinao, Aklan".
PROVINCE_NAMES = "|".join(sorted([
    "Abra", "Agusan", "Agusan del Norte", "Agusan del Sur", "Aklan", "Albay", "Antique", "Apayao", "Aurora", "Basilan",
    "Bataan", "Batanes", "Batangas", "Benguet", "Biliran", "Bohol", "Bukidnon", "Bulacan", "Cagayan", "Camarines Norte",
    "Camarines Sur", "Camiguin", "Capiz", "Catanduanes", "Cavite", "Cebu", "Compostela Valley", "Cotabato", "Davao",
    "Davao Occidental", "Davao Oriental", "Davao de Oro", "Davao del Norte", "Davao del Sur", "Dinagat Islands",
    "Eastern Samar", "Guimaras", "Ifugao", "Ilocos Norte", "Ilocos Sur", "Iloilo", "Isabela", "Kalinga", "Kalinga-Apayao",
    "La Union", "Laguna", "Lanao", "Lanao del Norte", "Lanao del Sur", "Leyte", "Maguindanao", "Marinduque", "Masbate",
    "Mindoro", "Misamis Occidental", "Misamis Oriental", "Mountain Province", "Negros Occidental", "Negros Oriental",
    "North Cotabato", "Northern Samar", "Nueva Ecija", "Nueva Vizcaya", "Occidental Mindoro", "Oriental Mindoro",
    "Palawan", "Pampanga", "Pangasinan", "Quezon", "Quirino", "Rizal", "Romblon", "Samar", "Sarangani", "Siquijor",
    "Sorsogon", "South Cotabato", "Southern Leyte", "Sultan Kudarat", "Sulu", "Surigao", "Surigao del Norte",
    "Surigao del Sur", "Tarlac", "Tawi-Tawi", "Zambales", "Zamboanga", "Zamboanga Sibugay", "Zamboanga del Norte",
    "Zamboanga del Sur", "Metro Manila", "Western Samar", "Mindoro Oriental", "Mindoro Occidental",
], key=len, reverse=True))

PLACE_WORD = r"(?:municipality|province|city|barangay|barrio|sitio|town|island|islands|municipal district|poblacion|district)"
# A named place: "Municipality of Baler", "Barangay Tamdagan", "Iligan City",
# "Metro Manila". Place words match in any case; the name must be capitalised.
# "Barangay Officials" or "Barangay Elections" are offices and events, not places.
SPECIFIC_PLACE = re.compile(
    r"(\b(?i:" + PLACE_WORD + r")s? (?i:of) (?:(?i:the) )?[A-Z]"
    r"|\b(?i:barangays?|barrios?|sitios?) (?!(?:Officials?|Elections?|Health|Roads?|Captains?|Chair\w*|Tanods?|Councils?|"
    r"Workers?|Level|Justice|Kagawads?|Secretar\w*|Treasurer\w*|Nutrition)\b)[A-Z]"
    r"|\b(?!(?:Component|Chartered|Urbanized|Independent|Said|Such|New|Each|Every|Any|Capital|Inner|Mother|Highly|The|A|Of)\b)"
    r"[A-Z][a-zñ]+(?: (?!(?:Component|Chartered|Urbanized|Independent)\b)[A-Z][a-zñ]+)? (?i:city)\b"
    r"|\b(?i:metro(?:politan)? manila)\b|\b(?i:city|mayor|vice-mayor|municipal board|auditor|treasurer|charter|fiscal|engineer) (?i:of) Manila\b"
    r"|\b(?i:in|at) [A-Z][a-zñ]+(?: [A-Z][a-zñ]+)?, (?:(?i:province of) )?(?:" + PROVINCE_NAMES + r")\b)")

PUBLIC_WORKS = rx(r"(amend\w* (and repeal\w* )?(a )?(certain )?(items?|priority number)|\bitems? \(?[a-z0-9]+\)?,? (under|on page|page|paragraph|subparagraph|group|title)|"
                  r"priority number|public works (projects|and projects) for|regarding public works)")

# The public works acts of 1951-1969, whose line items later acts amend one project at a time.
PUBLIC_WORKS_ACTS = {670, 920, 1200, 1411, 1613, 1900, 2093, 2301, 2701, 3101, 5187, 5979}
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                        "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_NUMBER_WORDS = r"(?:(?:" + "|".join(list(_UNITS) + list(_TENS) + ["hundred", "thousand", "and"]) + r")\b[\s-]*)+"
RA_REF = re.compile(r"republic acts? (?:numbered|no\.?|nos\.?)\s*(" + _NUMBER_WORDS + r"|\d{2,5})", re.I)


def words_to_int(s):
    """'Fourteen Hundred and Eleven' -> 1411."""
    total, cur = 0, 0
    for w in re.split(r"[\s-]+", s.lower()):
        if w in ("", "and"):
            continue
        if w in _UNITS:
            cur += _UNITS[w]
        elif w in _TENS:
            cur += _TENS[w]
        elif w == "hundred":
            cur = (cur or 1) * 100
        elif w == "thousand":
            total, cur = total + (cur or 1) * 1000, 0
        else:
            break
    return (total + cur) or None


def referenced_acts(title):
    out = set()
    for m in RA_REF.finditer(title):
        g = m.group(1).strip()
        n = int(g) if g.isdigit() else words_to_int(g)
        if n:
            out.add(n)
    return out


def is_public_works_item(t):
    """An amended line item counts as local public works only when it is an item of a
    public works act, or the title names public works or a place."""
    if re.search(r"\bbonds?\b", t, re.I):  # national bond issues for public works
        return False
    return bool(referenced_acts(t) & PUBLIC_WORKS_ACTS or re.search(r"public works", t, re.I)
                or re.search(r"\b(?:" + PROVINCE_NAMES + r")\b", t) or SPECIFIC_PLACE.search(t))


RULES = [
    # (category, pattern) — order matters.
    ("appropriation", rx(APPROPRIATION)),
    ("citizenship", rx(CITIZENSHIP)),
    ("franchise", rx(FRANCHISE + r"|permit to (construct|establish|operate|install|maintain)")),
    ("office_specific", rx(r"(district engineering office|engineering district|highway engineering district|land transportation office|"
                  r"\blto\b|district office|extension office|satellite office|licensing center)")),
    ("public_works", PUBLIC_WORKS),
    ("district", rx(r"(reapportion|legislative districts? (in|of) the province|(creating|constituting) .*(congressional|legislative) district|"
                    r"(another|additional|new|separate|lone) (legislative|congressional) district)")),
    ("holiday", rx(r"(special (non-?working|working) (public )?(holiday|day)|non-?working (public )?holiday|special holiday|working holiday)")),
    ("rename_place", rx(r"(chang(e|es|ing) the names? of (the |certain )?(barrios?|barangays?|municipalit(y|ies)|towns?|province|sitios?|poblacion|islands?|"
                        r"municipal district)\b|renam(e|es|ing) (the )?(barrios?|barangays?|municipalit(y|ies)|towns?|province|sitios?|islands?)\b|"
                        r"chang(e|es|ing) the name of [A-Za-zñ .'-]+ (city|province) to|changing the name of the city of)")),
    ("hospital", rx(r"(bed capacity|hospital|chest (center|clinic)|dispensar|medical center|infirmar|sanitari|leprosarium|maternity (and|hospital|home|clinic)|"
                    r"puericulture|health (center|centre|unit|station|office)|rural health|lying-in|dialysis center|"
                    r"cancer (center|institute)|heart (center|institute)|kidney (center|institute)|lung center|"
                    r"specialty (center|hospital)|chest clinic|emergency clinic|medical clinic|treatment and rehabilitation center)")),
    ("college", rx(r"(to offer .*(degree|bachelor|curricul|courses leading)|offering of .*(degree|bachelor|curricul)|state (university|college|polytechnic)|polytechnic (university|college|state)|college of (medicine|law|nursing|veterinary)|"
                   r"into a (state |chartered |community )?(college|university)|into the [A-Za-z .'-]+ (college|university)\b|"
                   r"(university|college)\b.*\b(campus|extension|annex|satellite|branch)|"
                   r"(campus|extension campus|satellite campus|branch campus) of the .*(university|college)|"
                   r"(integrating|merging|converting|elevating|upgrading).*(into|to|as) (a |an |the )?.*(university|college)|"
                   r"community college|school of medicine|institute of technology|"
                   r"(national|state) (institute|polytechnic)|\buniversity\b)")),
    ("school", rx(SCHOOL)),
    ("court", rx(COURT + r"|municipal judges?|city judges?|position of (municipal |city )?judge")),
    ("lgu", rx(LGU + r"|(to )?(create|creating) (the |a |an )?(barrios?|sitios?|barangays?|municipalit|municipal district)|"
                    r"convert(ing)? (the )?sitios? .* into (a )?(barrio|barangay)|"
                    r"transferring (the )?(barrios?|barangays?|sitios?)|"
                    r"(declaring|recognizing) (the existence of )?certain (barrios|barangays)|"
                    r"(new )?capital of the province|charter of (the |said )?(city|municipality)|convert(ing)? certain sitios|to create the provinces?|"
                    r"separate the barrios|creating a certain barrio|seat of (the )?government|"
                    r"naming the (barrios|barangays)|creation of the (city|municipality|province) of|validating .* creation")),
    ("road", rx(r"(national (road|highway)|(provincial|municipal|barangay|city|farm-to-market|access|circumferential|coastal|"
                r"diversion|by-?pass) roads?|\broad\b(?! board)|highway|bridge|\bstreets?\b|avenue|boulevard|expressway|causeway|flyover|interchange)")),
    ("college", rx(r"(\bcollege\b|\bcampus\b)")),
    ("school_generic", rx(r"\bschools?\b")),
    ("private_other", rx(PRIVATE_OTHER)),
    ("commemoration", rx(COMMEMORATION)),
    ("holiday", rx(HOLIDAY)),
    ("land", rx(LAND)),
    ("public_works", PUBLIC_WORKS),
    ("office", rx(OFFICE + r"|shrine")),
]

NEEDS_PLACE = {"office", "land", "school_generic"}
FACILITY_WORDS = re.compile(r"\b(school|hospital|street|avenue|road|bridge|college|university|river|fort|park|plaza|hall|market|"
                            r"highway|boulevard|center|centre|station|port|airport|church|lake|mountain|mount|creek|falls)\b", re.I)


def classify_title(title):
    t = re.sub(r"\s+", " ", title)
    has_place = bool(SPECIFIC_PLACE.search(t))
    cat = None
    for c, p in RULES:
        if p.search(t):
            if c in NEEDS_PLACE and not has_place:
                continue
            if c == "rename_place" and FACILITY_WORDS.search(t):
                continue
            if c == "public_works" and not is_public_works_item(t):
                continue
            cat = {"school_generic": "school", "office_specific": "office"}.get(c, c)
            break
    if cat == "lgu" and not has_place and re.search(r"local government code|republic act no\.? 7160", t, re.I):
        cat = "national"  # amends the rules for every town, such as the income test for cityhood
    if cat is None:
        cat = "other_local" if (has_place and not NATIONAL_HINT.search(t)) else "national"
    elif CATEGORIES[cat][1] == "local" and not has_place and EVERYWHERE.search(t):
        cat = "national"  # a local kind of law applied everywhere, such as concrete roads in all barangays
    if cat == "commemoration" and has_place and not re.search(r"\b(national|philippine|international|world)\b", t, re.I):
        cat = "holiday"
    return cat


ACTIONS = [
    ("increase", r"\bincreas"), ("separate", r"\bseparat"), ("convert", r"\bconvert"), ("upgrade", r"\bupgrad"),
    ("rename", r"\b(renam|chang(e|es|ing) the name)"), ("establish", r"\bestablish"), ("create", r"\bcreat"),
    ("renew", r"\brenew"), ("grant", r"\bgrant"), ("declare", r"\bdeclar"), ("amend", r"\bamend"),
    ("integrate", r"\bintegrat"), ("merge", r"\bmerg"), ("divide", r"\bdivid"), ("transfer", r"\btransfer"),
    ("appropriate", r"\bappropriat"),
]


def action_of(title):
    head = re.sub(r"^(an?|the)\s+act\s+(to\s+)?", "", title.strip(), flags=re.I)[:60].lower()
    for a, p in ACTIONS:
        if re.match(r"\s*" + p[2:], head):
            return a
    for a, p in ACTIONS:
        if re.search(p, head):
            return a
    return "other"


KNOWN_AS = re.compile(r"(?:to be known|shall be known|hereafter known|henceforth known|to be called|as the)\s+(?:as\s+)?(?:the\s+)?"
                      r"(.+?)(?=,|\s+and\s+(?:appropriating|authorizing|providing|for other)|\s+appropriating|\s+in the (?:barangay|municipality|city|province)|$)",
                      re.I)
CHANGE_TO = re.compile(r"\bto\s+(?:the\s+)?([A-Z][^,]*?(?:School|Hospital|Center|University|College|Campus|Road|Highway|Bridge|Street|Avenue))\b")


def facility_of(title, cat):
    m = KNOWN_AS.search(title)
    if m and len(m.group(1)) > 4:
        return m.group(1).strip(" .\"'")
    if cat in ("school", "hospital", "college", "road"):
        m = CHANGE_TO.search(title)
        if m:
            return m.group(1).strip()
    return None


def _num(s):
    s = s.strip().lower().replace(",", "")
    if s.isdigit():
        return int(s)
    return NUM_WORDS.get(s)


BEDS = re.compile(r"from\s+(?:([a-z\- ]+?)\s*)?\(?\s*([0-9,]+)?\s*\)?\s*(?:beds?\s+)?to\s+(?:([a-z\- ]+?)\s*)?\(?\s*([0-9,]+)?\s*\)?\s*beds?", re.I)


def beds_of(title):
    m = BEDS.search(title)
    if not m:
        return None, None
    a = _num(m.group(2) or "") or _num(m.group(1) or "")
    b = _num(m.group(4) or "") or _num(m.group(3) or "")
    return a, b


def main():
    laws = read_json(INTERIM / "laws_base.json")
    for L in laws:
        cat = classify_title(L["title"])
        L["category"] = cat
        L["scope"] = CATEGORIES[cat][1]
        L["action"] = action_of(L["title"])
        L["facility"] = facility_of(L["title"], cat)
        if cat == "hospital":
            L["beds_from"], L["beds_to"] = beds_of(L["title"])
    write_json(INTERIM / "laws_classified.json", laws)
    from collections import Counter
    c = Counter(L["category"] for L in laws)
    for k, v in c.most_common():
        print(f"{v:6d} {k}")


if __name__ == "__main__":
    main()
