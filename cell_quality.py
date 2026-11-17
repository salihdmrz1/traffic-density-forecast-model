"""Yol sinifi + trafik kalitesi birlestirme.

Kullanim:
    python cell_quality.py osm_test_cells.csv traffic_density_2022*.csv traffic_density_2023*.csv ...
    (osm_test_cells.csv: osm_test.py --all ile uretilen sinif tablosu)

Her ay icin her hucrede: kayit kapsami (ayin saatlerinin kacinda satir var) ve medyan arac sayisi.
Sonra tum aylar uzerinden ozetler ve "filtreyi gecen hucre" tablosunu sinif bazinda yazar.
Sonuc: cell_quality.csv
"""
import argparse
import re
import pandas as pd


def month_stats(path):
    d = pd.read_csv(path, usecols=["DATE_TIME", "GEOHASH", "NUMBER_OF_VEHICLES"], parse_dates=["DATE_TIME"])
    file_hours = d.DATE_TIME.nunique()                       # dosyada en az bir kaydi olan saat sayisi
    nominal = d.DATE_TIME.dt.days_in_month.iloc[0] * 24      # takvime gore beklenen saat
    g = d.groupby("GEOHASH").agg(n=("DATE_TIME", "size"), med=("NUMBER_OF_VEHICLES", "median"))
    # tum hucreler icin birden eksik saatler (kesinti) hucrenin sucu sayilmaz: payda = dosyadaki saat
    g["kapsam"] = g.n / file_hours
    print(f"   {path}: dosyadaki saat {file_hours}/{nominal}, satir {len(d)}, hucre {len(g)}, "
          f"kapsam>=0.9: {(g.kapsam >= 0.9).sum()}, medyan arac>=20: {(g.med >= 20).sum()}")
    m = re.search(r"(\d{6})", path)
    g["ay"] = m.group(1) if m else path
    return g.reset_index()[["GEOHASH", "ay", "kapsam", "med"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cells")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min-kapsam", type=float, default=0.9)
    ap.add_argument("--min-arac", type=float, default=20)
    ap.add_argument("--min-yol-m", type=float, default=500, help="hucrede en az bu kadar toplam yol (kenari sıyıran hucreleri eler)")
    a = ap.parse_args()

    cells = pd.read_csv(a.cells).rename(columns={"geohash": "GEOHASH"})
    parts = []
    for f in sorted(a.files):
        print("okunuyor:", f)
        parts.append(month_stats(f))
    ms = pd.concat(parts)
    n_ay = ms["ay"].nunique()

    q = ms.groupby("GEOHASH").agg(
        ay_sayisi=("ay", "nunique"),
        min_kapsam=("kapsam", "min"),
        ort_kapsam=("kapsam", "mean"),
        min_medyan_arac=("med", "min"),
        ort_medyan_arac=("med", "median"),
    ).reset_index()
    # hic gorunmedigi aylar icin ay_sayisi < n_ay olur (kapsam 0 sayilir)
    q["tum_aylarda_var"] = q.ay_sayisi == n_ay
    q["filtre_gecti"] = (q.tum_aylarda_var & (q.min_kapsam >= a.min_kapsam) & (q.min_medyan_arac >= a.min_arac))

    out = cells.merge(q, on="GEOHASH", how="left")
    out["filtre_gecti"] = out["filtre_gecti"].fillna(False)
    out["yol_yeterli"] = out["toplam_yol_m"].fillna(0) >= a.min_yol_m
    out["secilebilir"] = out["filtre_gecti"] & out["yol_yeterli"] & (out["baskin_sinif"] != "yol_yok")
    out.to_csv("cell_quality.csv", index=False)

    print(f"\nay sayisi: {n_ay}  (esikler: kapsam>={a.min_kapsam}, medyan arac>={a.min_arac}, yol>={a.min_yol_m} m)")
    t = out.groupby("baskin_sinif").agg(
        toplam=("GEOHASH", "size"),
        tum_aylarda_var=("tum_aylarda_var", "sum"),
        trafik_filtresi=("filtre_gecti", "sum"),
        secilebilir=("secilebilir", "sum"),
    )
    print(t.to_string())
    print("\nToplam secilebilir:", int(out.secilebilir.sum()))


if __name__ == "__main__":
    main()
