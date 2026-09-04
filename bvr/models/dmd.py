"""
DMDc -- Kontrollu Dinamik Mod Ayristirmasi (TABAN CIZGISI / BASELINE).

Kaldirma yok: Psi(x) = x  (+ istege bagli sabit terim).
Yani model, kapali cevrimi HAM durum uzayinda tek bir dogrusal sistemle
temsil eder:

        x_{k+1} = A x_k + B u_k  (+ c)

Bu, karsilastirmanin taban cizgisidir. EDMD ve Deep-Koopman'in katkisi
tam olarak "bu dogrusal temsilin yetmedigi yerde ne kadar iyilestiriyor"
sorusuyla olculur; o yuzden baseline'in DURUST ve iyi uygulanmis olmasi
gerekir (zayif bir baseline, sahte bir iyilesme uretir).

Durust baseline icin yapilanlar:
  - sabit, belgelenmis normalizasyon (state_def.py)
  - ARTIK (delta) regresyonu -> ridge, A'yi birim matrise dogru duzenler
  - ridge katsayisi dogrulama seti uzerinde secilir (elle degil)
  - affine terim opsiyonu (denge noktasi ofseti)
"""
from __future__ import annotations

import numpy as np

from .base import DynamicsModel
from .state_def import X_DIM, normalize_x, normalize_u


class DMDModel(DynamicsModel):
    """Ham durum uzayinda dogrusal model (opsiyonel affine terim)."""

    name = "DMD"

    def __init__(self, affine: bool = True):
        super().__init__()
        self.affine = affine

    @property
    def z_dim(self) -> int:
        # Sabit terim, dinamigin denge noktasindan kaymasini (affine offset)
        # temsil eder. Onsuz model, orijinden gecmeye zorlanir.
        return X_DIM + (1 if self.affine else 0)

    def lift(self, xn: np.ndarray) -> np.ndarray:
        xn = np.atleast_2d(xn)
        if not self.affine:
            return xn
        return np.hstack([xn, np.ones((xn.shape[0], 1))])

    def fit(self, X, U, Xn, ridge: float = 1e-6, **kw) -> "DMDModel":
        Zx = normalize_x(np.asarray(X, dtype=np.float64))
        Zxn = normalize_x(np.asarray(Xn, dtype=np.float64))
        W = normalize_u(np.asarray(U, dtype=np.float64))
        self._check_lift_contract(Zx)
        self._fit_linear(self.lift(Zx), W, self.lift(Zxn), ridge=ridge)
        # Sabit terimin dinamigi: 1 -> 1 (kendine esler). Regresyon bunu
        # yaklasik bulur; kesin degeri dayatmak coklu adim yuvarlanmasinda
        # kaymayi (drift) onler.
        if self.affine:
            self.A[X_DIM, :] = 0.0
            self.A[X_DIM, X_DIM] = 1.0
            self.B[X_DIM, :] = 0.0
        return self
