# Codebook

All files are UTF-8 CSV. Every downloaded source is logged in
`data/provenance.jsonl` with its URL, checksum and retrieval time. Nothing is
filled in by guesswork: when a value could not be read or matched, it is left
empty and a `match`, `geo_level` or `*_source` column says why.

## laws.csv (12,322 rows)

**Start here.** One row per Republic Act, 1946 to 2026. Act numbers run to
12,325; three (RA 678, 5446 and 11999) are in no source we could find.

| Column | What it is |
|---|---|
| `ra` | Republic Act number |
| `date`, `year` | Approval date (or the date the act lapsed into law). `date_source` says where it comes from |
| `congress` | Enacting Congress. The 1st to 7th Congresses sat from 1946 to 1972, the 8th to 20th from 1987. `congress_source` says how it was found |
| `president` | President in office on that date |
| `title` | Title as published. All-capital and all-lower-case titles were converted to title case. `title_source` says where it comes from |
| `category`, `category_label` | One of 19 kinds, from the title rules in `pipeline/classify.py` (list below) |
| `scope` | `local` (about one named place), `private` (one company or person), or `national` |
| `family` | One of seven families used for colour on the site |
| `action` | First verb of the title: establish, convert, separate, rename, increase, create, grant, renew, declare, amend, ... |
| `facility` | The name after "to be known as", when the title gives one |
| `provinces` | Current provinces the law is about, separated by `; ` |
| `towns`, `town_psgc10` | Cities and municipalities matched in the title, with their 10-digit PSGC codes (2024 codes) |
| `geo_level` | `muni` (placed at a town), `province` (province only), `none` |
| `lapsed` | `yes` when the act became law without the President's signature |
| `funding` | How the text says it will be paid for: `gaa` (future General Appropriations Acts), `current` (current appropriations or the Treasury), `none_stated` |
| `house_bills`, `senate_bills` | Bill numbers cited in the act's closing clause |
| `source`, `url` | `lawphil`, `chanrobles` (309 acts missing from LawPhil) or `house record` (22 acts in neither library, including the General Appropriations Acts for 2010, 2011, 2012, 2016, 2019, 2021, 2023 and 2024), and the full-text page |
| `title_source` | `index` (LawPhil's list of acts), `act text` (the title printed in the act, used when LawPhil's list garbles or cuts off a title, or repeats a neighbouring act's title, and for every Chan Robles act), or `house record` (the long title of the House bill the act came from) |
| `date_source` | `index`, `act text` (the act's "Approved:" line), `house record` (the House's status date for the bill), or empty when no source gives a date (9 acts) |
| `congress_source` | `header` (the act's "Nineteenth Congress, Third Regular Session" header), `passage date` (the dates the act says the Senate and House passed it), `house record` (the Congress of the House bill it came from), `act number` (signed in the first months of a new Congress, with a lower number than that Congress's first identified act, so it belongs to the Congress that just closed), `approval date`, or `neighbouring acts` (undated acts between two acts of the same Congress) |
| `lapsed_source` | `act text` (the act says it lapsed into law) or `house record` (the House records the bill as "Lapsed Into Law") |

### The 19 kinds

| Key | Label | Scope |
|---|---|---|
| `school` | Public schools | local |
| `college` | State universities and colleges | local |
| `hospital` | Hospitals and health facilities | local |
| `lgu` | New towns, cities, barangays and charters | local |
| `rename_place` | Renamed towns and barangays | local |
| `road` | Roads, bridges and streets | local |
| `court` | Court branches | local |
| `office` | Government offices and facilities | local |
| `holiday` | Local holidays | local |
| `district` | Legislative districts | local |
| `land` | Land grants, reservations and protected areas | local |
| `public_works` | Local public works funds: amended line items of the public works acts of 1951 to 1969 | local |
| `other_local` | Other local laws | local |
| `franchise` | Franchises | private |
| `citizenship` | Citizenship grants | private |
| `private_other` | Pensions, claims and other private grants | private |
| `commemoration` | National days and symbols | national |
| `appropriation` | Budgets and appropriations | national |
| `national` | National policy | national |

Validation: on 400 randomly drawn laws labelled by hand, the first version of
the rules agreed with the labels on 91.5% of laws (kind) and 96.8% (scope).
After fixing the rules that failed, a fresh sample of 200 laws gave 92.0% and
98.5% (`pipeline/validate.py` rescores it against the current rules). The
rules are scored on the titles as they were sampled: one of them, RA 3142,
was later found to carry a neighbouring act's title in LawPhil's list and now
shows the title printed in the act. No `district` law happened to be sampled.
Samples and labels are in `data/validation/`.

## school_laws.csv

Every law classified as `school`, with what we found in DepEd's lists of public
schools for SY 2017-18 to SY 2025-26.

| Column | What it is |
|---|---|
| `action` | establish, separate, convert, rename, ... |
| `target_name` | The school the law names ("to be known as ...") |
| `source_name` | The school the law acts on (for separations, conversions and renamings) |
| `barangays`, `munis`, `provinces` | Places in the title |
| `match` | `named`: a school with that name (or a close variant) is listed in that town. `barangay`: no name match, but a public school at the same level is listed in the named barangay. `annex`: the law made an annex independent but DepEd still lists it as an annex. `not_found`. `no_town`: the town could not be identified or has no DepEd schools. `no_name`: the title names no school |
| `match_score` | Share of the name's distinctive words found (1 = all) |
| `deped_school_id`, `deped_name` | The matched school |
| `deped_first_year`, `deped_last_year` | First and last school year (starting year) the school appears in, 2017 to 2025 |
| `deped_enrolment_latest` | Total enrolment in its last listed year |
| `closest_name`, `closest_score` | For unmatched laws, the nearest DepEd name in that town, for checking by hand |

## hospital_laws.csv

Every law classified as `hospital`, matched to PhilHealth's list of accredited
hospitals and infirmaries (July 31, 2026). Only government hospitals are
candidates. Words that are just the town or province name do not count toward
a match. Later renaming laws are followed, so a law about "Mindanao Central
Sanitarium" can match the hospital now called "Zamboanga Regional Medical Center".

| Column | What it is |
|---|---|
| `hospital_name` | The hospital the title names |
| `beds_from`, `beds_to` | Bed capacity before and after, for bed-capacity laws |
| `match` | `found`, `not_found`, `no_place` (no accredited government hospital in the place), `no_name` (no hospital name in the title) |
| `match_score` | 1 means every distinctive word matched |
| `match_level` | Where the match was found: `town`, `province`, or `national` (only for titles that name no usable place, and only for near-identical names) |
| `later_names` | Names the hospital took in later laws |
| `philhealth_name`, `philhealth_beds`, `philhealth_level`, `philhealth_sector` | The matched PhilHealth entry |
| `closest_name` | For unmatched laws, the nearest PhilHealth name, for checking by hand |

The site's bed chart uses `found` matches with a `match_score` of at least 0.9
and the latest bed-capacity law per hospital. It leaves out facilities that
PhilHealth lists as psychiatric hospitals or sanitaria, where PhilHealth
accredits only the general beds; a former sanitarium that is now a general
hospital, such as Zamboanga Regional Medical Center, stays in.

## barangay_laws.csv

Laws that create a barangay, matched to the barangays counted in the 2020 census.
From 1992 to 2019 there are only 26 such laws, since provinces and cities can
create barangays themselves.

## law_bills.csv

Republic Acts linked to the House bill they came from (3,125 acts). `linked_by`
is `bill history` (the House record names the act) or `act text` (the act names
the bill).

## law_authors.csv

One row per enacted law with a House principal author (3,023 acts). Most are
from the 13th Congress on, when the House record names authors consistently;
100 are from earlier Congresses where it does.

| Column | What it is |
|---|---|
| `author`, `author_id` | Principal author, and BetterGov's person ID |
| `author_province` | Province of the author's district, from OpenHalalan (blank for party-list members and unmatched names) |
| `district_rep` | True when the author was matched to an OpenHalalan district winner |
| `family_seat` | See rep_terms.csv |
| `family_evidence` | Which offices share the surname |

## rep_terms.csv

One row per district representative per Congress, 13th to 20th, matched to
OpenHalalan's House winners for the election before that Congress (1,573 terms).
A member is matched by surname and first name; because OpenHalalan's records
from 2016 on often carry the name on the ballot ("JB" Bernos, "Joey" Salceda),
a member whose first name does not match is still matched when they are the only
winner with that surname in that election and the only member with that surname
in that Congress. Members who could not be matched are not listed, so the table
covers most but not all district representatives.

| Column | What it is |
|---|---|
| `family_seat` | True when someone else with the same surname won the governorship, vice governorship, another House seat, or a mayoralty in the same province in the same election, or held a House seat there in one of the two previous elections. The member's own earlier terms never count, however OpenHalalan spells their first name |
| `bills_filed`, `local_bills_filed` | House bills with this member as principal author |
| `laws_enacted`, `local_laws_enacted` | Of those, the ones that became Republic Acts |

Surnames are a rough marker of kinship: unrelated people can share a common
surname, and relatives can have different ones. OpenHalalan's 2004 to 2013
records come from an older source that its authors could not check against
ballots.

## house_bills_classified.csv.gz

Every House bill filed from the 8th to the 20th Congress (143,156 rows) from
BetterGov's open-congress-data, with `category` and `scope` from the same title
rules as the laws. `scope_house` is the House's own Local/National tag. It is
blank for the 8th to 12th and the 20th Congresses, where the record gives every
bill the same default value. `ra` is the Republic Act the bill became, when the
House record says so.

## Maps

`docs/provinces.topojson` holds PSA 2023 province outlines. Town centroids
(`data/interim/town_centroids.json`) are the area-weighted centres of each
town's largest polygon in faeldon/philippines-json-maps, or of its barangays for
the towns whose outline is missing at low resolution. Kalayaan (Palawan) has no
outline and is not placed.
