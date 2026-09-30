"""Score the title rules against the hand-labelled samples in data/validation/.

The first sample (400 laws) was scored against the first version of the rules
and is kept as recorded in summary.json. The second (200 fresh laws) is
rescored here against the current rules, on the titles exactly as they were
sampled and labelled.

Output: data/validation/summary.json and docs/data/validation.json
"""

import csv
import json

from classify import CATEGORIES, classify_title
from common import DATA, DOCS

VAL = DATA / "validation"


def main():
    summary = json.loads((VAL / "summary.json").read_text())
    titles = {r["ra"]: r["title"] for r in csv.DictReader(open(VAL / "sample_3.csv"))}
    labels = {r["ra"]: r["category"] for r in csv.DictReader(open(VAL / "labels_3.csv"))}
    n = cat = scope = 0
    for ra, lab in labels.items():
        if ra not in titles:
            continue
        pred = classify_title(titles[ra])
        n += 1
        cat += pred == lab
        scope += CATEGORIES[pred][1] == CATEGORIES[lab][1]
    summary["second"] = {"n": n, "category": round(cat / n, 4), "scope": round(scope / n, 4),
                         "note": "fresh sample, current rules, titles as sampled"}
    (VAL / "summary.json").write_text(json.dumps(summary, indent=1))
    (DOCS / "data" / "validation.json").write_text(json.dumps(
        {k: {"n": v["n"], "category": v["category"], "scope": v["scope"]} for k, v in summary.items()}))
    print(f"second sample: {n} laws, kind {cat / n:.1%}, scope {scope / n:.1%}")


if __name__ == "__main__":
    main()
