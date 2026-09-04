"""
MODEL DOGRULAMA: coklu adim tahmin hatasi.

=============================================================================
NEDEN TEK-ADIM HATASI YETMEZ
=============================================================================
0.1 saniyelik bir adimda durum cok az degisir. "Hicbir sey degismedi"
diyen aptal bir model (persistence: x_{k+1} = x_k) bile kucuk bir tek-adim
hatasi verir. Bu yuzden her metrigi PERSISTENCE TABANINA gore raporlariz:
model, hicbir sey yapmayan tahminciden ne kadar iyi?

Ayrica CBF, sinira yaklasirken birkac adim ilerisini gormek zorundadir;
1 adimda iyi, 20 adimda saga sola savrulan bir model guvenlik icin
degersizdir. Bu yuzden 1 / 5 / 20 adim ufuklarinda olcum yapilir
(0.1 / 0.5 / 2.0 saniye).

Iki yuvarlanma (rollout) modu ayri raporlanir:
  relift : her adimda x'e donup yeniden kaldirilir -> CBF'nin fiili kullanimi
  linear : kaldirilmis uzayda dogrusal ilerletilir -> "Koopman iddiasi" testi
Ikisi arasindaki fark buyudukce, kaldirmanin gercek bir Koopman
gomulmesinden ziyade tek-adimlik bir regresyon numarasi oldugu anlasilir.
=============================================================================
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..models.state_def import X_NAMES, X_DIM, X_SCALE, normalize_x


def load_dataset(path: str) -> dict:
    d = np.load(path, allow_pickle=True)
    return dict(X=d["X"], U=d["U"], Xn=d["Xn"], ep_id=d["ep_id"], dt=float(d["dt"]))


def _valid_starts(ep_id: np.ndarray, H: int) -> np.ndarray:
    """i .. i+H-1 araligi TEK bir bolume ait olan baslangic indeksleri."""
    n = len(ep_id)
    idx = np.arange(n - H + 1)
    return idx[ep_id[idx] == ep_id[idx + H - 1]]


def multi_step_error(model, data: dict, horizon: int, mode: str = "relift",
                     n_samples: int = 4000, seed: int = 0) -> dict:
    """Verilen ufukta tahmin hatasi (fiziksel birimler) + persistence tabani."""
    rng = np.random.default_rng(seed)
    starts = _valid_starts(data["ep_id"], horizon)
    if len(starts) == 0:
        raise ValueError(f"ufuk {horizon} icin gecerli dizi yok")
    if len(starts) > n_samples:
        starts = rng.choice(starts, n_samples, replace=False)

    X, U, Xn = data["X"], data["U"], data["Xn"]
    err = np.zeros((len(starts), X_DIM))
    err_pers = np.zeros((len(starts), X_DIM))

    for j, i in enumerate(starts):
        x0 = X[i]
        Useq = U[i:i + horizon]
        truth = Xn[i + horizon - 1]
        pred = model.rollout(x0, Useq, mode=mode)[-1]
        err[j] = pred - truth
        err_pers[j] = x0 - truth          # "hicbir sey degismedi" tahmini

    rmse = np.sqrt((err ** 2).mean(axis=0))
    rmse_pers = np.sqrt((err_pers ** 2).mean(axis=0))
    # Normalize (birimsiz) toplam: durumlar karsilastirilabilir olsun
    nrmse = float(np.mean(rmse / X_SCALE))
    nrmse_pers = float(np.mean(rmse_pers / X_SCALE))
    return dict(horizon=horizon, mode=mode, rmse=rmse, rmse_pers=rmse_pers,
                nrmse=nrmse, nrmse_pers=nrmse_pers,
                skill=1.0 - nrmse / max(nrmse_pers, 1e-12),
                p95=np.percentile(np.abs(err), 95, axis=0))


def report(model, data: dict, horizons: Sequence[int] = (1, 5, 20),
           modes: Sequence[str] = ("relift", "linear"), verbose: bool = True):
    """Tez tablosuna hazir ozet."""
    rows = []
    for mode in modes:
        for H in horizons:
            rows.append(multi_step_error(model, data, H, mode))

    if verbose:
        print(f"--- {model.name} (z_dim={model.z_dim}) ---")
        print(f"{'mod':>8} {'ufuk':>5} {'sure s':>7} {'nRMSE':>9} "
              f"{'persist':>9} {'beceri':>8}")
        for r in rows:
            print(f"{r['mode']:>8} {r['horizon']:5d} {r['horizon']*0.1:7.1f} "
                  f"{r['nrmse']:9.5f} {r['nrmse_pers']:9.5f} {r['skill']*100:7.1f}%")
        print()
        rl = [r for r in rows if r["mode"] == "relift"]
        print("Durum bazinda RMSE (fiziksel birim, relift) -- her ufukta "
              "model / persistence:")
        hdr = " ".join(f"{('H=' + str(h)):>21}" for h in horizons)
        print(f"{'durum':>12} {hdr}")
        for i, nm in enumerate(X_NAMES):
            cells = " ".join(f"{r['rmse'][i]:10.4f}/{r['rmse_pers'][i]:10.4f}"
                             for r in rl)
            print(f"{nm:>12} {cells}")
    return rows


def select_ridge(model_factory, train: dict, val: dict,
                 candidates=(1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2),
                 horizon: int = 20, verbose: bool = True):
    """Ridge katsayisini DOGRULAMA setinde sec (egitim setinde degil).

    Neden dogrulama setinde: ridge bir duzenleme parametresidir; egitim
    hatasi ridge kucuktukce her zaman duser. Egitimde secmek, gurultuye
    uydurmayi (overfit) odullendirir. Ayrica 20 adim ufkunda secmek,
    "tek adimda iyi ama uzun ufukta savrulan" modelleri eler -- CBF'nin
    ihtiyaci uzun ufuk kararliligidir.
    """
    best, best_score = None, np.inf
    if verbose:
        print(f"{'ridge':>10} {'nRMSE@' + str(horizon):>12}")
    for lam in candidates:
        m = model_factory()
        m.fit(train["X"], train["U"], train["Xn"], ridge=lam)
        r = multi_step_error(m, val, horizon, "relift", n_samples=1500, seed=1)
        if verbose:
            print(f"{lam:10.1e} {r['nrmse']:12.5f}")
        if r["nrmse"] < best_score:
            best, best_score = lam, r["nrmse"]
    if verbose:
        print(f"  -> secilen ridge = {best:.1e}")
    return best
