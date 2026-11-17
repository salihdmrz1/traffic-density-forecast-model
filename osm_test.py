"""OSM yol etiketleme fizibilite testi.

Kullanim (Colab veya kendi bilgisayarin):
    pip install osmnx geopandas shapely pandas matplotlib
    python osm_test.py traffic_density_202306.csv --n 20

Ne yapar:
  1. CSV'den hucreleri (geohash) okur, rastgele n tanesini secer (hiza bakmadan).
  2. Her geohash'in kutusunu (bounding box) hesaplar.
  3. OSM'den bu kutularin kapsadigi alandaki yollari indirir.
  4. Her hucre icin yol tipine gore toplam uzunluk, baskin yol tipi,
     serit/hiz limiti/ref etiketlerinin ne kadar dolu oldugunu raporlar.
  5. sonuc: osm_test_cells.csv + osm_test_map.png
"""
import argparse
import sys
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

B32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def gh_bbox(g):
    lat, lon, even = [-90.0, 90.0], [-180.0, 180.0], True
    for c in g:
        v = B32.index(c)
        for i in range(4, -1, -1):
            rng = lon if even else lat
            mid = (rng[0] + rng[1]) / 2
            if (v >> i) & 1:
                rng[0] = mid
            else:
                rng[1] = mid
            even = not even
    return lon[0], lat[0], lon[1], lat[1]  # minx, miny, maxx, maxy


# Yol siniflari: kucuk sayi = ust sinif
CLASS = {
    "motorway": "otoyol", "motorway_link": "otoyol",
    "trunk": "devlet_yolu", "trunk_link": "devlet_yolu",
    "primary": "ana_arter", "primary_link": "ana_arter",
    "secondary": "ana_arter", "secondary_link": "ana_arter",
    "tertiary": "ikincil", "tertiary_link": "ikincil",
    "unclassified": "dar_sehir_ici", "residential": "dar_sehir_ici",
    "living_street": "dar_sehir_ici", "service": "dar_sehir_ici",
}


def first(v):
    """OSM etiketi liste olabilir; ilkini al."""
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v


ORDER = ["otoyol", "devlet_yolu", "ana_arter", "ikincil", "dar_sehir_ici"]


def classify_cells(cells, roads, min_m=300):
    """cells: GeoDataFrame(geohash, geometry) EPSG:4326; roads: yol cizgileri GeoDataFrame."""
    roads = roads.copy()
    roads["hw"] = roads["highway"].map(first)
    roads["sinif"] = roads["hw"].map(CLASS)
    roads = roads[roads["sinif"].notna()]
    for col in ("lanes", "maxspeed", "ref", "tunnel", "bridge"):
        if col not in roads:
            roads[col] = None
    # metre cinsinden uzunluk icin UTM 35N (Istanbul)
    c_m = cells.to_crs(32635)
    r_m = roads.to_crs(32635)
    inter = gpd.overlay(r_m, c_m[["geohash", "geometry"]], how="intersection", keep_geom_type=True)
    inter["len_m"] = inter.geometry.length
    rows = []
    for g, d in inter.groupby("geohash"):
        by = d.groupby("sinif")["len_m"].sum()
        tot = by.sum()
        # en ust sinif: hucrede en az min_m metre bulunan en yuksek sinif
        dom = next((c for c in ORDER if by.get(c, 0) >= min_m), by.idxmax())
        dd = d[d["sinif"] == dom]
        ref = dd.assign(ref=dd["ref"].map(first)).dropna(subset=["ref"]).groupby("ref")["len_m"].sum()
        rows.append(dict(
            geohash=g,
            toplam_yol_m=round(tot),
            baskin_sinif=dom,
            uzunluk_ozet=";".join(f"{k}:{round(v)}" for k, v in by.items()),
            baskin_oran=round(by[dom] / tot, 2),
            otoyol_oran=round(by.get("otoyol", 0) / tot, 2),
            baskin_ref=ref.idxmax() if len(ref) else None,
            serit_dolu=round(dd["lanes"].notna().mean(), 2),
            hizlimiti_dolu=round(dd["maxspeed"].notna().mean(), 2),
            tunel_var=bool(d["tunnel"].notna().any()),
            kopru_var=bool(d["bridge"].notna().any()),
        ))
    out = pd.DataFrame(rows)
    missing = set(cells.geohash) - set(out.geohash) if len(out) else set(cells.geohash)
    if missing:
        out = pd.concat([out, pd.DataFrame({"geohash": sorted(missing), "baskin_sinif": "yol_yok"})], ignore_index=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-m", type=float, default=300, help="sinif icin hucrede gereken minimum yol uzunlugu (m)")
    ap.add_argument("--all", action="store_true", help="tum hucreleri sinifla (--n yok sayilir)")
    ap.add_argument("--roads", help="onceden indirilmis yol dosyasi (gpkg/geojson); verilmezse OSM'den indirilir")
    a = ap.parse_args()

    df = pd.read_csv(a.csv, usecols=["GEOHASH"])
    uniq = df.GEOHASH.drop_duplicates()
    ghs = (uniq if a.all else uniq.sample(min(a.n, len(uniq)), random_state=a.seed)).tolist()
    cells = gpd.GeoDataFrame(
        {"geohash": ghs}, geometry=[box(*gh_bbox(g)) for g in ghs], crs=4326)

    if a.roads:
        roads = gpd.read_file(a.roads)
    else:
        import osmnx as ox
        minx, miny, maxx, maxy = cells.total_bounds
        print(f"OSM indiriliyor: bbox=({minx:.3f},{miny:.3f},{maxx:.3f},{maxy:.3f}) ...")
        # osmnx >= 2: bbox = (left, bottom, right, top)
        roads = ox.features_from_bbox((minx, miny, maxx, maxy), tags={"highway": True})
        roads = roads[roads.geometry.type.isin(["LineString", "MultiLineString"])].reset_index(drop=True)
        print("indirilen yol parcasi:", len(roads))

    res = classify_cells(cells, roads, a.min_m)
    res.to_csv("osm_test_cells.csv", index=False)
    print(res.to_string(index=False))
    print("\nOzet:")
    print(res.baskin_sinif.value_counts().to_string())
    ok = res[res.baskin_sinif != "yol_yok"]
    if len(ok):
        print(f"serit etiketi dolu (ort): {ok.serit_dolu.mean():.0%}, hiz limiti dolu (ort): {ok.hizlimiti_dolu.mean():.0%}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 8))
        roads.plot(ax=ax, linewidth=0.3, color="lightgray")
        m = cells.merge(res[["geohash", "baskin_sinif"]], on="geohash")
        for s, col in [("otoyol", "red"), ("devlet_yolu", "purple"), ("ana_arter", "orange"), ("ikincil", "green"),
                       ("dar_sehir_ici", "blue"), ("yol_yok", "black")]:
            sub = m[m.baskin_sinif == s]
            if len(sub):
                sub.boundary.plot(ax=ax, color=col, linewidth=1.5, label=s)
        ax.legend()
        minx, miny, maxx, maxy = cells.total_bounds
        ax.set_xlim(minx - .02, maxx + .02); ax.set_ylim(miny - .02, maxy + .02)
        fig.savefig("osm_test_map.png", dpi=120)
        print("harita: osm_test_map.png")
    except Exception as e:
        print("harita cizilemedi:", e)


if __name__ == "__main__":
    sys.exit(main())
