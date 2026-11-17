"""Elenen hucrelerin yerine ayni gruptan yedek secer.

Kullanim:
    python replace_cells.py cell_quality_arac10.csv secilen_hucreler.csv hucre_ozet.csv --seed 7
Girdi: cell_quality (havuz), ilk secim, filter_cells.py'nin hucre_ozet.csv'si.
Cikti: secilen_hucreler_v2.csv (gecenler + yedekler). Sonra filter_cells.py'yi bununla tekrar calistir.
Yedekler: ilk secimde olmayan, 'secilebilir' hucreler; kalan hucrelerden en az d km uzakta.
"""
import argparse
import random
import pandas as pd
from select_cells import gh_center, km, GROUP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quality")
    ap.add_argument("secilen")
    ap.add_argument("ozet")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    q = pd.read_csv(a.quality)
    q = q[q["secilebilir"] == True].copy()  # noqa: E712
    q["grup"] = q["baskin_sinif"].map(GROUP)
    sec = pd.read_csv(a.secilen)
    oz = pd.read_csv(a.ozet)
    gecen = set(oz[oz.durum == "GECTI"].GEOHASH)
    kal = set(oz[oz.durum == "KALDI"].GEOHASH)
    kept = sec[sec.GEOHASH.isin(gecen)].copy()
    used = set(sec.GEOHASH)

    new_rows = []
    for grup, d in sec[sec.GEOHASH.isin(kal)].groupby("grup"):
        k = len(d)
        pool = q[(q.grup == grup) & (~q.GEOHASH.isin(used))].to_dict("records")
        chosen = []
        for dist in [3.0, 2.0, 1.5, 1.0, 0.5, 0.0]:
            rnd = random.Random(a.seed)
            rnd.shuffle(pool)
            chosen = []
            anchors = [gh_center(g) for g in kept[kept.grup == grup].GEOHASH]
            for c in pool:
                xy = gh_center(c["GEOHASH"])
                if all(km(xy, p) >= dist for p in anchors):
                    chosen.append(c)
                    anchors.append(xy)
                if len(chosen) == k:
                    break
            if len(chosen) == k:
                break
        print(f"{grup}: {k} yedek gerekli, bulunan {len(chosen)}, en az mesafe {dist} km, havuz {len(pool)}")
        for c in chosen:
            xy = gh_center(c["GEOHASH"])
            new_rows.append({"GEOHASH": c["GEOHASH"], "grup": grup, "baskin_sinif": c["baskin_sinif"],
                             "baskin_ref": c.get("baskin_ref"), "enlem": round(xy[0], 5), "boylam": round(xy[1], 5),
                             "toplam_yol_m": c["toplam_yol_m"], "otoyol_oran": c.get("otoyol_oran"),
                             "min_kapsam": c.get("min_kapsam"), "min_medyan_arac": c.get("min_medyan_arac")})
    out = pd.concat([kept, pd.DataFrame(new_rows)], ignore_index=True)
    out.to_csv("secilen_hucreler_v2.csv", index=False)
    print("\nToplam:", len(out))
    print(out.groupby("grup").size().to_string())
    print("Yeni eklenenler:", [r["GEOHASH"] for r in new_rows])


if __name__ == "__main__":
    main()
