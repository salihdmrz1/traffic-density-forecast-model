"""Hucre secimi: her yol grubundan ~N hucre, tohumlu rastgele, birbirinden uzak.

Kullanim:
    python select_cells.py cell_quality_arac10.csv --n 20 --seed 42
Girdi: cell_quality.py cikti dosyasi (--min-arac 10 ile uretilen).
Cikti: secilen_hucreler.csv, secilen_hucreler_harita.png

Secim hiza BAKMAZ; yalniz yol grubu, 'secilebilir' (trafik filtresi + yol uzunlugu) ve mesafe kullanilir.
Gruplar: otoyol, devlet_yolu, ana_arter, kucuk_yol (= ikincil + dar_sehir_ici).
"""
import argparse
import math
import random
import pandas as pd

B32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def gh_center(g):
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
    return sum(lat) / 2, sum(lon) / 2


def km(a, b):
    dlat = (a[0] - b[0]) * 111.0
    dlon = (a[1] - b[1]) * 111.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dlat, dlon)


GROUP = {"otoyol": "otoyol", "devlet_yolu": "devlet_yolu", "ana_arter": "ana_arter",
         "ikincil": "kucuk_yol", "dar_sehir_ici": "kucuk_yol"}


def pick(cands, n, seed, min_km_start=3.0):
    """Tohumlu karistir, secilenlerden en az d km uzak olanlari al; yetmezse d'yi dusur."""
    for d in [min_km_start, 2.0, 1.5, 1.0, 0.5, 0.0]:
        rnd = random.Random(seed)
        order = cands[:]
        rnd.shuffle(order)
        chosen = []
        for c in order:
            if all(km(c["xy"], s["xy"]) >= d for s in chosen):
                chosen.append(c)
            if len(chosen) == n:
                return chosen, d
    return chosen, 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    df = pd.read_csv(a.csv)
    df = df[df["secilebilir"] == True].copy()  # noqa: E712
    df["grup"] = df["baskin_sinif"].map(GROUP)
    df = df[df["grup"].notna()]
    rows = []
    for grup, d in df.groupby("grup"):
        cands = [dict(r, xy=gh_center(r["GEOHASH"])) for r in d.to_dict("records")]
        chosen, dist = pick(cands, a.n, a.seed)
        print(f"{grup}: havuz {len(cands)}, secilen {len(chosen)}, en az mesafe {dist} km")
        rows += chosen
    out = pd.DataFrame(rows)
    out["enlem"] = out["xy"].map(lambda t: round(t[0], 5))
    out["boylam"] = out["xy"].map(lambda t: round(t[1], 5))
    keep = [c for c in ["GEOHASH", "grup", "baskin_sinif", "baskin_ref", "enlem", "boylam", "toplam_yol_m",
                        "otoyol_oran", "min_kapsam", "min_medyan_arac"] if c in out.columns]
    out[keep].sort_values(["grup", "GEOHASH"]).to_csv("secilen_hucreler.csv", index=False)
    print("\nToplam:", len(out))
    print(out.groupby("grup").size().to_string())

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        col = {"otoyol": "red", "devlet_yolu": "purple", "ana_arter": "orange", "kucuk_yol": "blue"}
        fig, ax = plt.subplots(figsize=(8, 6))
        for g, d in out.groupby("grup"):
            ax.scatter(d["boylam"], d["enlem"], s=40, c=col.get(g, "gray"), label=f"{g} ({len(d)})")
        ax.set_xlabel("boylam"); ax.set_ylabel("enlem"); ax.legend()
        fig.savefig("secilen_hucreler_harita.png", dpi=120)
        print("harita: secilen_hucreler_harita.png")
    except Exception as e:
        print("harita cizilemedi:", e)


if __name__ == "__main__":
    main()
