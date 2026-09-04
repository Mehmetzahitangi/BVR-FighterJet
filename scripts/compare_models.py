"""
TEZ KARSILASTIRMA TABLOSU: butun dinamik modelleri ayni veri, ayni
protokolle degerlendirir.

Adil karsilastirma kurallari (hepsi burada uygulaniyor):
  1. Ayni egitim seti, ayni dogrulama seti, ayni normalizasyon.
  2. Her modelin ridge'i KENDI icin dogrulama setinde secilir
     (aksi halde bir modeli kayirmis oluruz).
  3. Ayni ufuklar (1 / 5 / 20 adim) ve ayni ornek indeksleri (sabit tohum).
  4. Persistence (hicbir sey degismedi) tabani her satirda gosterilir.
  5. Model karmasikligi (z_dim) raporlanir -- "daha iyi ama 3 kat buyuk"
     bilgisi olmadan karsilastirma eksiktir.

Cikti: konsol tablosu + runs/model_comparison.png + runs/model_comparison.csv
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bvr.models.dmd import DMDModel
from bvr.models.edmd import EDMDModel
from bvr.models.deep_koopman import DeepKoopmanModel
from bvr.models.state_def import X_NAMES, X_SCALE
from bvr.sysid.evaluate import load_dataset, multi_step_error, select_ridge

HORIZONS = (1, 5, 20)

# (isim, fabrika, sabit fit argumanlari, ridge taransin mi)
# Deep-Koopman'da ridge anlamsizdir (regresyon degil, gradyan egitimi);
# onun yerine spektral ceza bir ablasyon ekseni olarak yer alir.
CANDIDATES = [
    ("DMD", lambda: DMDModel(affine=True), {}, True),
    ("EDMD-fizik", lambda: EDMDModel(library="physics"), {}, True),
    ("EDMD-poly2", lambda: EDMDModel(library="poly2"), {}, True),
    ("EDMD-fizik+poly2", lambda: EDMDModel(library="physics+poly2"), {}, True),
    ("Deep-Koopman",
     lambda: DeepKoopmanModel(latent_dim=32, hidden=(128, 128)),
     dict(horizon=10, epochs=12, batch=4096, lr=1e-3, verbose=False), False),
    ("Deep-Koopman + kararlilik",
     lambda: DeepKoopmanModel(latent_dim=32, hidden=(128, 128)),
     dict(horizon=10, epochs=12, batch=4096, lr=1e-3, spectral_penalty=10.0,
          verbose=False), False),
]


def main(args):
    train = load_dataset(args.train)
    val = load_dataset(args.val)
    print(f"egitim {len(train['X']):,} gecis | dogrulama {len(val['X']):,} gecis "
          f"| dt = {train['dt']:.2f} s")
    print()

    results = []
    for name, factory, fkw, tune in CANDIDATES:
        print(f"--- {name} ---", flush=True)
        lam = select_ridge(factory, train, val, horizon=20, verbose=False) if tune else 0.0
        kw = dict(fkw)
        if not tune:
            kw["ep_id"] = train["ep_id"]      # coklu adim kaybi bolum sinirlarina uysun
        t0 = time.time()
        m = factory()
        m.fit(train["X"], train["U"], train["Xn"], ridge=lam, **kw)
        fit_s = time.time() - t0
        r = np.abs(np.linalg.eigvals(m.A))
        row = dict(name=name, z_dim=m.z_dim, ridge=lam, fit_s=fit_s,
                   rho=r.max(), growth20=r.max() ** 20, model=m)
        for mode in ("relift", "linear"):
            for H in HORIZONS:
                e = multi_step_error(m, val, H, mode, n_samples=4000, seed=7)
                row[f"{mode}{H}"] = e["nrmse"]
                if mode == "relift":
                    row[f"rmse{H}"] = e["rmse"]
                    row[f"pers{H}"] = e["rmse_pers"]
        results.append(row)
        print(f"    ridge={lam:.0e}  z_dim={m.z_dim}  fit={fit_s:.2f}s  "
              f"rho={r.max():.6f}", flush=True)

    # ---------------- ANA TABLO ----------------
    print()
    print("=" * 100)
    print("MODEL KARSILASTIRMASI  (nRMSE: normalize durumlarda ortalama RMSE, "
          "kucuk = iyi)")
    print("=" * 100)
    print(f"{'model':>18} {'z_dim':>6} {'ridge':>8} "
          f"{'relift H=1':>11} {'H=5':>9} {'H=20':>9} "
          f"{'linear H=1':>11} {'H=5':>9} {'H=20':>9} {'rho(A)':>9}")
    pers = {H: multi_step_error(results[0]["model"], val, H, "relift",
                                n_samples=4000, seed=7)["nrmse_pers"]
            for H in HORIZONS}
    print(f"{'persistence':>18} {'-':>6} {'-':>8} "
          f"{pers[1]:11.5f} {pers[5]:9.5f} {pers[20]:9.5f} "
          f"{'-':>11} {'-':>9} {'-':>9} {'-':>9}")
    for r in results:
        print(f"{r['name']:>18} {r['z_dim']:6d} {r['ridge']:8.0e} "
              f"{r['relift1']:11.5f} {r['relift5']:9.5f} {r['relift20']:9.5f} "
              f"{r['linear1']:11.5f} {r['linear5']:9.5f} {r['linear20']:9.5f} "
              f"{r['rho']:9.6f}")

    # ---------------- BECERI (persistence'a gore) ----------------
    print()
    print("BECERI SKORU = 1 - nRMSE_model / nRMSE_persistence   (buyuk = iyi)")
    print(f"{'model':>18} {'H=1':>9} {'H=5':>9} {'H=20':>9}")
    for r in results:
        sk = [100 * (1 - r[f"relift{H}"] / pers[H]) for H in HORIZONS]
        print(f"{r['name']:>18} {sk[0]:8.1f}% {sk[1]:8.1f}% {sk[2]:8.1f}%")

    # ---------------- ZARF DURUMLARI (CBF icin kritik olanlar) ----------------
    # CBF bariyerleri bu durumlar uzerinde tanimli; modelin asil sinavi bunlar.
    key = ["alpha_rad", "beta_rad", "n_eff", "mach", "phi_rad", "alt_ft", "h_dot_fps"]
    ki = [X_NAMES.index(k) for k in key]
    print()
    print("ZARF DURUMLARINDA 1-ADIM RMSE (CBF bunlari kisitliyor; fiziksel birim)")
    print(f"{'model':>18} " + " ".join(f"{k:>11}" for k in key))
    print(f"{'persistence':>18} " +
          " ".join(f"{results[0]['pers1'][i]:11.4f}" for i in ki))
    for r in results:
        print(f"{r['name']:>18} " + " ".join(f"{r['rmse1'][i]:11.4f}" for i in ki))

    # ---------------- CIKTILAR ----------------
    os.makedirs("runs", exist_ok=True)
    with open("runs/model_comparison.csv", "w", encoding="utf-8") as f:
        f.write("model,z_dim,ridge,rho," +
                ",".join(f"relift_H{H}" for H in HORIZONS) + "," +
                ",".join(f"linear_H{H}" for H in HORIZONS) + "\n")
        f.write("persistence,,,," + ",".join(f"{pers[H]:.6f}" for H in HORIZONS)
                + ",,,\n")
        for r in results:
            f.write(f"{r['name']},{r['z_dim']},{r['ridge']:.0e},{r['rho']:.6f},"
                    + ",".join(f"{r[f'relift{H}']:.6f}" for H in HORIZONS) + ","
                    + ",".join(f"{r[f'linear{H}']:.6f}" for H in HORIZONS) + "\n")

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
    hs = np.array(HORIZONS)
    for r in results:
        ax[0].plot(hs, [r[f"relift{H}"] for H in HORIZONS], "o-", label=r["name"])
        ax[1].plot(hs, [r[f"linear{H}"] for H in HORIZONS], "o-", label=r["name"])
    for a, ttl in ((ax[0], "relift (CBF'nin fiili kullanimi)"),
                   (ax[1], "linear (saf Koopman yuvarlanmasi)")):
        a.plot(hs, [pers[H] for H in HORIZONS], "k--", label="persistence")
        a.set_xlabel("ufuk [adim]"); a.set_ylabel("nRMSE")
        a.set_title(ttl, fontsize=10); a.grid(alpha=.3); a.legend(fontsize=8)
        a.set_xscale("log"); a.set_yscale("log")
    w = 0.8 / len(results)
    xs = np.arange(len(key))
    ax[2].bar(xs - 0.4, [results[0]["pers1"][i] / X_SCALE[i] for i in ki],
              width=w, label="persistence", color="0.6")
    for j, r in enumerate(results):
        ax[2].bar(xs - 0.4 + (j + 1) * w,
                  [r["rmse1"][i] / X_SCALE[i] for i in ki], width=w, label=r["name"])
    ax[2].set_xticks(xs); ax[2].set_xticklabels(key, rotation=40, ha="right", fontsize=7)
    ax[2].set_ylabel("1-adim RMSE (normalize)")
    ax[2].set_title("zarf durumlari (CBF kisitlari)", fontsize=10)
    ax[2].legend(fontsize=7); ax[2].grid(alpha=.3, axis="y")
    fig.tight_layout()
    fig.savefig("runs/model_comparison.png", dpi=110)
    print()
    print("runs/model_comparison.csv  ve  runs/model_comparison.png yazildi")

    # HER modeli ACIK ISIMLE kaydet.
    # Tek bir "model_best.pkl" uzerine yazmak kirilgandir: hangi politikanin
    # hangi modele karsi egitildigi zamanla degisir ve geri izlenemez.
    # Konfigurasyon dosyalari modeli acik yoluyla secer.
    os.makedirs("data/models", exist_ok=True)
    SLUG = {"DMD": "dmd",
            "EDMD-fizik": "edmd_physics",
            "EDMD-poly2": "edmd_poly2",
            "EDMD-fizik+poly2": "edmd_physics_poly2",
            "Deep-Koopman": "deep_koopman",
            "Deep-Koopman + kararlilik": "deep_koopman_stable"}
    print()
    for r in results:
        slug = SLUG.get(r["name"])
        if slug:
            p = f"data/models/{slug}.pkl"
            r["model"].save(p)
            print(f"  {p:<42} z_dim {r['z_dim']:3d}  "
                  f"H=1 {r['relift1']:.5f}  H=20 {r['relift20']:.5f}")
    best = min(results, key=lambda r: r["relift1"])
    print(f"\nEn iyi 1-adim dogruluk: {best['name']} ({best['relift1']:.5f})")
    print("NOT: kalkanin varsayilan modeli DOGRULUKLA degil, MDL-08 geregi")
    print("     DENETLENEBILIRLIKLE secilir (bkz. REQUIREMENTS.md).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="data/sysid_train.npz")
    ap.add_argument("--val", default="data/sysid_val.npz")
    main(ap.parse_args())
