"""
ROBUST CBF: ogrenilmis model hatasini bariyer sikilastirmasina cevirmek.

=============================================================================
PROBLEM
=============================================================================
CBF'in guvenlik garantisi, modelin DOGRU olmasi varsayimina dayanir.
Bizim modelimiz veriden ogrenilmis bir Koopman/DMD yaklasimidir ve hatasi
sifir degildir. Model "bir sonraki adimda alpha 20 derece olacak" derken
gercekte 21 dereceye ciktiysa, kalkan "guvendeyiz" der ve zarf ihlal edilir.

Olculen sonuc bu teoriyi dogruluyor: kalkanla nz ihlal orani 3 kat dustu
ama SIFIRLANMADI (%0.084 -> %0.028). Kalan ihlaller, tam da modelin
yanildigi anlardir.

=============================================================================
COZUM
=============================================================================
Bariyeri, model hatasinin ust sinirı kadar SIKILASTIRMAK:

        c_j . x_{k+i}  <=  rhs_{j,i}  -  eps_{j,i}

Burada eps, DOGRULAMA setinde olculen tahmin hatasinin bir ust yuzdeligidir:

        e_{j,i} = c_j . ( x_gercek_{k+i} - x_tahmin_{k+i} )
        eps_{j,i} = quantile_q( e_{j,i} )

Isaret onemli: yalnizca POZITIF hata tehlikelidir -- yani modelin
"c_j . x" degerini OLDUGUNDAN KUCUK tahmin etmesi ("sandigimizdan daha
yakiniz sinira"). Negatif hata muhafazakar yondedir, marj gerektirmez.

Bu, "ogrenilmis model + CBF" calismalarini ampirik bir iddiadan
("model daha iyi oldu, kalkan da daha iyi korudu") olculebilir bir
garantiye tasiyan adimdir: q yuzdeligi secilerek "kalan ihlal olasiligi
en fazla (1-q)" seklinde bir ifade kurulabilir.

SINIRLARI (tezde durustce yazilmali):
  - Bu bir OLASILIKSAL sinirdir, kotu-durum (worst-case) sinir degildir;
    dogrulama dagilimina kosulludur.
  - Politika degistikce dagilim kayar (distribution shift); marjlar
    egitim sonrasi on-policy veriyle yeniden olculmelidir.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from ..models.base import DynamicsModel
from ..models.state_def import (
    X_DIM, envelope_constraints, normalize_x, normalize_u, denormalize_x,
)


def compute_margins(model: DynamicsModel, data: dict,
                    horizons: Sequence[int], quantile: float = 0.99,
                    n_samples: int = 20000, seed: int = 0) -> np.ndarray:
    """Bariyer x ufuk basina model hata marji (eps).

    Donen dizi, CBFShield'in kisit siralamasiyla AYNI duzendedir:
    ufuklar dis dongu, bariyerler ic dongu -> uzunluk = len(h) * n_bariyer.
    """
    C, d, names = envelope_constraints()
    nb = C.shape[0]
    hs = sorted(set(int(h) for h in horizons))
    Hmax = hs[-1]

    X, U, ep = data["X"], data["U"], data["ep_id"]
    # i .. i+Hmax-1 ayni bolumde olan baslangiclar
    idx = np.arange(len(X) - Hmax)
    idx = idx[ep[idx] == ep[idx + Hmax - 1]]
    rng = np.random.default_rng(seed)
    if len(idx) > n_samples:
        idx = rng.choice(idx, n_samples, replace=False)

    # Toplu (batched) coklu adim tahmin: kaldirilmis uzayda dogrusal ilerlet
    Z = model.lift(normalize_x(X[idx]))                     # (N, z)
    out = np.zeros((len(hs) * nb,))
    k = 0
    for i in range(1, Hmax + 1):
        W = normalize_u(U[idx + i - 1])                     # (N, u)
        Z = Z @ model.A.T + W @ model.B.T
        if i in hs:
            x_pred = denormalize_x(Z[:, :X_DIM])
            x_true = data["Xn"][idx + i - 1]                # i adim sonraki gercek
            # e = c . (gercek - tahmin);  pozitif = model bizi fazla guvenli sandi
            e = (x_true - x_pred) @ C.T                     # (N, nb)
            eps = np.quantile(e, quantile, axis=0)
            out[k * nb:(k + 1) * nb] = np.maximum(eps, 0.0)
            k += 1
    return out


def report_margins(margins: np.ndarray, horizons: Sequence[int]) -> None:
    C, d, names = envelope_constraints()
    nb = len(names)
    hs = sorted(set(int(h) for h in horizons))
    print(f"{'bariyer':<12} " + " ".join(f"{('H=' + str(h)):>9}" for h in hs))
    for j, nm in enumerate(names):
        vals = " ".join(f"{margins[k * nb + j]:9.4f}" for k in range(len(hs)))
        print(f"{nm:<12} {vals}")
    print("(birim: boyutsuz bariyer olcegi; 1.0 = kisitin karakteristik olcegi "
          "kadar sikilastirma)")
