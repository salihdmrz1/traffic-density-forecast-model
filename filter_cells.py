"""80 secilen hucrenin verisini tum aylik dosyalardan suzer ve her hucreyi her ay icin dogrular.

Kullanim (kendi bilgisayarinda, dosyalarin oldugu klasorde):
    pip install pandas pyarrow
    python filter_cells.py secilen_hucreler.csv traffic_density_*.csv --min-arac 10 --min-kapsam 0.9

Ciktilar:
    secilen_veri.parquet   -> sadece 80 hucrenin tum satirlari (modelleme verisi)
    aylik_dogrulama.csv    -> hucre x ay: kapsam, medyan arac
    hucre_ozet.csv         -> hucre basina: kac ay gecti, en kotu ay, GECTI/KALDI
    ay_ozet.csv            -> ay basina: dosyadaki saat sayisi / beklenen saat
Dosyalar tek tek okunur, bellek sorunu olmaz.
"""
import argparse
import glob
import re
import sys
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cells")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min-arac", type=float, default=10)
    ap.add_argument("--min-kapsam", type=float, default=0.9)
    a = ap.parse_args()
    # Windows '*' joker karakterini acmaz; burada kendimiz aciyoruz
    files = []
    for p in a.files:
        files += sorted(glob.glob(p)) or [p]
    a.files = files
    print(len(files), 'dosya bulundu')

    cells = pd.read_csv(a.cells)
    keep = set(cells["GEOHASH"])
    parts, mrows, hrows = [], [], []
    for f in sorted(a.files):
        d = pd.read_csv(f, parse_dates=["DATE_TIME"])
        m = re.search(r"(\d{6})", f)
        ay = m.group(1) if m else f
        file_hours = d.DATE_TIME.nunique()
        nominal = d.DATE_TIME.dt.days_in_month.iloc[0] * 24
        hrows.append(dict(ay=ay, dosyadaki_saat=file_hours, beklenen_saat=nominal, toplam_satir=len(d)))
        s = d[d.GEOHASH.isin(keep)].copy()
        s["ay"] = ay
        parts.append(s)
        g = s.groupby("GEOHASH").agg(n=("DATE_TIME", "size"), med=("NUMBER_OF_VEHICLES", "median")).reindex(list(keep))
        g["n"] = g["n"].fillna(0)
        g["kapsam"] = g["n"] / file_hours
        g["ay"] = ay
        mrows.append(g.reset_index().rename(columns={"index": "GEOHASH"}))
        print(f"{ay}: dosyada {file_hours}/{nominal} saat, secilen hucre satiri {len(s)}", flush=True)
        del d

    pd.concat(parts).to_parquet("secilen_veri.parquet", index=False)
    mo = pd.concat(mrows)
    mo.to_csv("aylik_dogrulama.csv", index=False)
    pd.DataFrame(hrows).to_csv("ay_ozet.csv", index=False)

    mo["kotu"] = (mo.kapsam < a.min_kapsam) | (mo.med.fillna(0) < a.min_arac)
    h = mo.groupby("GEOHASH").agg(ay=("ay", "nunique"), kotu_ay=("kotu", "sum"),
                                  min_kapsam=("kapsam", "min"), min_medyan=("med", "min")).reset_index()
    h["durum"] = h.kotu_ay.map(lambda k: "GECTI" if k == 0 else "KALDI")
    h = h.merge(cells[["GEOHASH", "grup"]], on="GEOHASH")
    h.to_csv("hucre_ozet.csv", index=False)

    print("\nAy sayisi:", mo.ay.nunique())
    print(h.groupby(["grup", "durum"]).size().unstack(fill_value=0).to_string())
    print("\nKalan hucreler:")
    print(h[h.durum == "KALDI"][["GEOHASH", "grup", "kotu_ay", "min_kapsam", "min_medyan"]].to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
