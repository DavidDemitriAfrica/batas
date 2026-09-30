"""Centroids of every city and municipality, for placing laws on the map.

Source: faeldon/philippines-json-maps (PSA 2023 boundaries, low resolution).
data/raw/boundaries/municities/ has one file of town outlines per province.
Independent cities, and a few towns whose outline was simplified away, come
from their barangay outlines in data/raw/boundaries/barangays/.

A town's centroid is the area-weighted centre of its largest polygon, so that
island towns sit on their main island; for towns built from barangays it is
the area-weighted centre of the barangays.

The gazetteer uses 2024 PSGC codes, in which Negros Occidental, Negros
Oriental and Siquijor moved to the new Negros Island Region (18); the 2023
boundaries still carry their old codes, so those are translated.

Output: data/interim/town_centroids.json  {psgc10: [lon, lat]}
"""

import glob
import json

from common import INTERIM, RAW, write_json
from geocode import load_gazetteer

NIR = {"18045": "06045", "18046": "07046", "18061": "07061", "18302": "06302"}


def ring_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if abs(a) < 1e-12:
        xs, ys = zip(*ring)
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    return abs(a) / 2, (cx / (3 * a), cy / (3 * a))


def polygons(geom):
    if not geom:
        return []
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def main():
    by_code = {}
    for f in sorted(glob.glob(str(RAW / "boundaries" / "municities" / "*.json"))):
        for ft in json.load(open(f)).get("features", []):
            parts = [ring_centroid(p[0]) for p in polygons(ft["geometry"]) if p and p[0]]
            if parts:
                by_code[str(ft["properties"]["adm3_psgc"]).zfill(10)] = max(parts, key=lambda t: t[0])[1]
    for f in sorted(glob.glob(str(RAW / "boundaries" / "barangays" / "*.json"))):
        feats = json.load(open(f)).get("features", [])
        parts = [ring_centroid(p[0]) for ft in feats for p in polygons(ft["geometry"]) if p and p[0]]
        area = sum(a for a, _ in parts)
        if not parts or area == 0:
            continue
        code = str(feats[0]["properties"]["adm3_psgc"]).zfill(10)
        by_code.setdefault(code, (sum(a * x for a, (x, _) in parts) / area, sum(a * y for a, (_, y) in parts) / area))
    lgus, _, _ = load_gazetteer()
    out, missing = {}, []
    for L in lgus:
        c = L["psgc10"]
        xy = by_code.get(c) or by_code.get(NIR.get(c[:5], c[:5]) + c[5:])
        if xy:
            out[c] = [round(xy[0], 4), round(xy[1], 4)]
        else:
            missing.append(f"{L['name']} ({L['province']})")
    write_json(INTERIM / "town_centroids.json", out)
    print(f"{len(out)} of {len(lgus)} towns placed" + (f"; missing: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main()
