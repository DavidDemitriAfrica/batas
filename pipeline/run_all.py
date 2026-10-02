"""Rebuild everything, in order. Downloads are cached, so reruns are fast.

    python3 pipeline/run_all.py            # everything
    python3 pipeline/run_all.py --no-fetch # skip network steps, rebuild from cache

Two inputs cannot be fetched from a datacenter IP and are committed to the
repo instead: DepEd's enrolment files (data/raw/deped/) and PhilHealth's
hospital list (data/raw/philhealth/). The PSGC and population tables come from
the Philippine Internal Migration Dataset (data/raw/pim/).
"""

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

STEPS_FETCH = ["fetch_laws.py --acts", "fetch_gaps.py", "house_bills.py"]
STEPS = ["build_laws.py", "classify.py", "geocode.py", "towns.py", "deped.py", "philhealth.py", "match_schools.py",
         "match_hospitals.py", "match_barangays.py", "authors.py", "effort.py", "make_site_data.py", "validate.py", "export_csv.py"]


def run(step):
    name, *args = step.split()
    print(f"\n== {step}", flush=True)
    sys.argv = [name] + args
    runpy.run_path(str(HERE / name), run_name="__main__")


if __name__ == "__main__":
    fetch = "--no-fetch" not in sys.argv
    for s in (STEPS_FETCH if fetch else []) + STEPS:
        run(s)
