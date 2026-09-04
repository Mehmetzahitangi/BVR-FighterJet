"""
EDMD -- Genisletilmis Dinamik Mod Ayristirmasi (Extended DMD).

=============================================================================
FIKIR
=============================================================================
DMD, dinamigi HAM durum uzayinda dogrusal saymaya calisir. F-16'nin
kapali cevrim dinamigi ise acikca dogrusal degildir; ornegin ucus yolu
kinematigi

        gamma_dot = g * (n * cos(phi) - cos(gamma)) / V

icinde cos(phi), cos(gamma) ve 1/V carpanlari vardir. Ham durumda dogrusal
bir A matrisi bu terimleri temsil EDEMEZ.

EDMD, durumu once dogrusal olmayan bir "gozlenebilirler" kumesine kaldirir:

        z = Psi(x) = [ x , cos(phi), sin(gamma), n*cos(phi), 1/V, ... ]

ve DOGRUSAL modeli o uzayda kurar. Eger dogru gozlenebilirler secilirse,
yukaridaki gibi terimler artik modelin DOGRUSAL bileseni haline gelir.

=============================================================================
NEDEN GENEL POLINOM DEGIL, FIZIK-BILGILI KITAPLIK?
=============================================================================
Standart EDMD tarifi "2. derece polinom al" der. 10 durumda bu 55 carpim
demektir; cogu fiziksel karsiligi olmayan terimdir ve gurultuye uyar.
Bunun yerine kitapligi ucus mekaniginden TURETIYORUZ:

  cos(phi), sin(phi)            -> yatis kinematigi (donus hizi ~ tan(phi))
  cos(gamma), sin(gamma)        -> ucus yolu kinematigi (h_dot = V sin gamma)
  n*cos(phi)                    -> gamma_dot ifadesinin cekirdegi
  (n*cos(phi) - cos(gamma))/V   -> gamma_dot'un TAMAMI (tek gozlenebilir!)
  V, 1/V                        -> hiz olcekleme
  qbar, qbar*alpha              -> aerodinamik kuvvet ~ dinamik basinc
  tan(phi)/V                    -> donus hizi (psi_dot) terimi
  V*sin(gamma)                  -> dikey hiz terimi

Bu, tezde "fizik-bilgili gozlenebilir secimi" olarak savunulabilecek bir
katkidir ve ayrica genel polinomdan DAHA AZ terimle daha iyi sonuc verir.
Karsilastirma icin `library="poly2"` ve `"physics+poly2"` de mevcuttur --
tezde ablasyon satiri olur.

Kaldirmanin ilk blogu her zaman x'tir (bkz. base.py, bariyer kisiti).
=============================================================================
"""
from __future__ import annotations

import itertools
from typing import List, Tuple

import numpy as np

from .base import DynamicsModel
from .state_def import X_DIM, X_NAMES, normalize_x, normalize_u, denormalize_x
from ..sim import aircraft as ac

_I = {n: k for k, n in enumerate(X_NAMES)}


def _physics_features(x: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    """Fiziksel birimli x (N, X_DIM) -> fizik-bilgili ozellikler (N, F)."""
    phi = x[:, _I["phi_rad"]]
    gam = x[:, _I["gamma_rad"]]
    mach = x[:, _I["mach"]]
    alt = x[:, _I["alt_ft"]]
    alpha = x[:, _I["alpha_rad"]]
    beta = x[:, _I["beta_rad"]]
    n = x[:, _I["n_eff"]]
    p = x[:, _I["p_rads"]]
    q = x[:, _I["q_rads"]]

    rho, a = ac.atmos(alt)
    V = np.maximum(mach * a, 100.0)              # gercek hiz (ft/s)
    qbar = 0.5 * rho * V * V                     # dinamik basinc (psf)

    cphi, sphi = np.cos(phi), np.sin(phi)
    cgam, sgam = np.cos(gam), np.sin(gam)
    # tan(phi) 90 derecede patlar; calisma zarfi +-80 derece oldugu icin kirp
    tphi = np.tan(np.clip(phi, -1.30, 1.30))

    feats = [
        cphi, sphi, cgam, sgam,
        n * cphi,                                 # gamma_dot cekirdegi
        (n * cphi - cgam) / V * ac.G_FPS2,        # gamma_dot'un kendisi
        tphi / V * ac.G_FPS2,                     # psi_dot (donus hizi)
        V, 1.0 / V,
        qbar, qbar * alpha, qbar * beta,
        V * sgam,                                 # h_dot
        alpha * V, n / np.maximum(qbar, 1.0),
        p * q, p * sphi, q * cphi,
        mach * mach,
    ]
    names = [
        "cos_phi", "sin_phi", "cos_gam", "sin_gam",
        "n_cos_phi", "gamma_dot_kin", "psi_dot_kin",
        "V", "inv_V", "qbar", "qbar_alpha", "qbar_beta",
        "V_sin_gam", "alpha_V", "n_over_qbar",
        "p_q", "p_sin_phi", "q_cos_phi", "mach2",
    ]
    return np.column_stack(feats), names


def _poly2_features(xn: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    """Normalize durum uzerinde 2. derece carpimlar (i <= j)."""
    cols, names = [], []
    for i, j in itertools.combinations_with_replacement(range(X_DIM), 2):
        cols.append(xn[:, i] * xn[:, j])
        names.append(f"{X_NAMES[i]}*{X_NAMES[j]}")
    return np.column_stack(cols), names


class EDMDModel(DynamicsModel):
    """Fizik-bilgili (ve/veya polinom) gozlenebilirlerle EDMD."""

    name = "EDMD"

    def __init__(self, library: str = "physics", affine: bool = True):
        super().__init__()
        if library not in ("physics", "poly2", "physics+poly2"):
            raise ValueError(library)
        self.library = library
        self.affine = affine
        self.feat_names: List[str] = []
        # Ozellik blogu icin SABIT standardizasyon (fit sirasinda hesaplanip
        # dondurulur). Bu, regresyonun kosullanmasi icindir; bariyer yalnizca
        # ilk X_DIM blogunu kullandigindan guvenli kume etkilenmez.
        self._fmu: np.ndarray | None = None
        self._fsd: np.ndarray | None = None
        self._n_feat: int | None = None

    # ------------------------------------------------------------------
    def _raw_features(self, xn: np.ndarray) -> np.ndarray:
        x = denormalize_x(xn)
        blocks, names = [], []
        if "physics" in self.library:
            f, nm = _physics_features(x)
            blocks.append(f); names += nm
        if "poly2" in self.library:
            f, nm = _poly2_features(xn)
            blocks.append(f); names += nm
        self.feat_names = names
        return np.hstack(blocks)

    @property
    def z_dim(self) -> int:
        if self._n_feat is None:
            # fit oncesi: bir ornek uzerinde boyutu olc
            probe = np.zeros((2, X_DIM))
            self._n_feat = self._raw_features(probe).shape[1]
        return X_DIM + self._n_feat + (1 if self.affine else 0)

    def lift(self, xn: np.ndarray) -> np.ndarray:
        xn = np.atleast_2d(np.asarray(xn, dtype=np.float64))
        F = self._raw_features(xn)
        if self._fmu is None:
            self._fmu = np.zeros(F.shape[1])
            self._fsd = np.ones(F.shape[1])
            self._n_feat = F.shape[1]
        F = (F - self._fmu) / self._fsd
        parts = [xn, F]
        if self.affine:
            parts.append(np.ones((xn.shape[0], 1)))
        return np.hstack(parts)

    # ------------------------------------------------------------------
    def fit(self, X, U, Xn, ridge: float = 1e-6, **kw) -> "EDMDModel":
        Zx = normalize_x(np.asarray(X, dtype=np.float64))
        Zxn = normalize_x(np.asarray(Xn, dtype=np.float64))
        W = normalize_u(np.asarray(U, dtype=np.float64))

        # Ozellik standardizasyonunu EGITIM setinden hesapla ve DONDUR
        F = self._raw_features(Zx)
        self._n_feat = F.shape[1]
        self._fmu = F.mean(axis=0)
        self._fsd = F.std(axis=0)
        self._fsd[self._fsd < 1e-9] = 1.0

        self._check_lift_contract(Zx)
        self._fit_linear(self.lift(Zx), W, self.lift(Zxn), ridge=ridge)

        if self.affine:
            j = self.z_dim - 1
            self.A[j, :] = 0.0
            self.A[j, j] = 1.0
            self.B[j, :] = 0.0
        return self
