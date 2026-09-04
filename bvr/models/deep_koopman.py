"""
DEEP-KOOPMAN: kaldirma fonksiyonunu ELLE SECMEK yerine OGRENMEK.

=============================================================================
DMD -> EDMD -> DEEP-KOOPMAN ZINCIRI
=============================================================================
  DMD           : Psi(x) = x                       (kaldirma yok)
  EDMD          : Psi(x) = [x, elle secilmis ozellikler]
  Deep-Koopman  : Psi(x) = [x, encoder_NN(x)]      (ozellikler OGRENILIR)

Ucunde de dinamik AYNI bicimdedir:  z_{k+1} = A z_k + B w_k
ve ucu de ayni CBF'i besler. Degisen tek sey, kaldirmanin nereden geldigi.

=============================================================================
DURUM-ICEREN GOZLENEBILIRLER (state-inclusive) SOZLESMESI
=============================================================================
Psi'nin ilk blogu yine x'in KENDISIDIR. Bunun iki sonucu var:
  1. CBF bariyerleri (h = d - Cx) degismeden kaldirilmis uzayda ifade
     edilebilir -- projedeki butun guvenlik altyapisi aynen calisir.
  2. KOD COZUCU (decoder) OGRENILMEZ: x, z'nin ilk X_DIM bileseni oldugu
     icin cozme islemi bir DILIMLEMEDIR. Klasik Koopman-autoencoder'daki
     "reconstruction loss" boylece kendiliginden ve TAM olarak saglanir;
     ogrenilecek tek sey ileri dinamiktir. Bu, egitimi hem basitlestirir
     hem de bir hata kaynagini tamamen ortadan kaldirir.

=============================================================================
KAYIP FONKSIYONLARI
=============================================================================
  1. DOGRUSALLIK (linearity): kaldirilmis uzayda z_{k+1} ~ A z_k + B w_k
     -> "bu uzayda dinamik gercekten dogrusal mi" iddiasini egitir.
  2. DURUM TAHMINI (prediction): coz(A z + B w) ~ x_{k+1}
     -> asil onemsedigimiz buyukluk; kaldirilmis uzaydaki hata,
        durum uzayindaki hataya cevrilmeden anlamsizdir.
  3. COK ADIMLI TAHMIN (multi-step): komut dizisi ile H adim ilerletip
     her adimda durum hatasi. CBF ufuklari 1..20 adim oldugu icin bu
     kayip DOGRUDAN kullanim amacini egitir; yalnizca tek adim egitilen
     bir model uzun ufukta savrulur.

=============================================================================
KARARLILIK
=============================================================================
A serbest birakilirsa ozdegerleri birim cemberi asabilir ve coklu adim
tahmini ustel patlar. Kayip 3 bunu buyuk olcude cezalandirir; ayrica
`spectral_penalty` ile rho(A) > 1 dogrudan cezalandirilabilir
(stability-constrained Koopman; tezde ayri bir ablasyon satiri).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from .base import DynamicsModel
from .state_def import X_DIM, U_DIM, normalize_x, normalize_u


class DeepKoopmanModel(DynamicsModel):
    """Ogrenilmis kaldirma + kaldirilmis uzayda dogrusal dinamik."""

    name = "DeepKoopman"

    def __init__(self, latent_dim: int = 32, hidden: Sequence[int] = (128, 128),
                 affine: bool = True):
        super().__init__()
        self.latent_dim = int(latent_dim)
        self.hidden = tuple(hidden)
        self.affine = affine
        self._W: list = []          # numpy agirliklar (lift icin)
        self._b: list = []

    # ------------------------------------------------------------------
    @property
    def z_dim(self) -> int:
        return X_DIM + self.latent_dim + (1 if self.affine else 0)

    def lift(self, xn: np.ndarray) -> np.ndarray:
        """Psi(x) = [x, encoder(x), 1]. Encoder numpy'da ileri beslenir.

        Egitimden sonra torch'a bagimlilik kalmaz: kalkan (OSQP) saf numpy
        calisir, boylece paralel RL isciler torch yuklemek zorunda kalmaz.
        """
        xn = np.atleast_2d(np.asarray(xn, dtype=np.float64))
        if not self._W:                       # fit oncesi: sifir latent
            lat = np.zeros((xn.shape[0], self.latent_dim))
        else:
            h = xn
            for k, (W, b) in enumerate(zip(self._W, self._b)):
                h = h @ W.T + b
                if k < len(self._W) - 1:
                    h = np.tanh(h)            # egitimdeki aktivasyonla AYNI
            lat = h
        parts = [xn, lat]
        if self.affine:
            parts.append(np.ones((xn.shape[0], 1)))
        return np.hstack(parts)

    # ------------------------------------------------------------------
    def fit(self, X, U, Xn, ridge: float = 1e-6, *, ep_id=None,
            horizon: int = 10, epochs: int = 12, batch: int = 4096,
            lr: float = 1e-3, spectral_penalty: float = 0.0,
            w_lin: float = 1.0, w_pred: float = 10.0, w_multi: float = 5.0,
            device: Optional[str] = None, verbose: bool = True,
            **kw) -> "DeepKoopmanModel":
        """Encoder + (A, B) birlikte egitilir.

        `ep_id` verilirse coklu adim kaybi icin BOLUM SINIRLARINA saygi
        gosterilir (iki farkli bolumu birbirine zincirlemek modeli bozar).
        """
        import torch
        import torch.nn as nn

        dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        Zx = torch.tensor(normalize_x(np.asarray(X, np.float64)), dtype=torch.float32)
        W = torch.tensor(normalize_u(np.asarray(U, np.float64)), dtype=torch.float32)
        Zxn = torch.tensor(normalize_x(np.asarray(Xn, np.float64)), dtype=torch.float32)

        # Coklu adim icin gecerli baslangic indeksleri
        n = len(Zx)
        if ep_id is None:
            starts = np.arange(n - horizon)
        else:
            ep_id = np.asarray(ep_id)
            idx = np.arange(n - horizon)
            starts = idx[ep_id[idx] == ep_id[idx + horizon - 1]]
        starts_t = torch.tensor(starts, dtype=torch.long)

        # --- Encoder ---
        dims = [X_DIM] + list(self.hidden) + [self.latent_dim]
        layers = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.Tanh())
        enc = nn.Sequential(*layers).to(dev)

        zd = self.z_dim
        # A birim matrise yakin baslatilir: 0.1 s'lik adimda dogru on kabul
        # budur (bkz. base.py, artik regresyonu gerekcesi).
        A = nn.Parameter(torch.eye(zd, device=dev) + 0.01 * torch.randn(zd, zd, device=dev))
        B = nn.Parameter(0.01 * torch.randn(zd, U_DIM, device=dev))
        opt = torch.optim.Adam(list(enc.parameters()) + [A, B], lr=lr)

        def lift_t(x):
            parts = [x, enc(x)]
            if self.affine:
                parts.append(torch.ones(x.shape[0], 1, device=x.device))
            return torch.cat(parts, dim=1)

        Zx, W, Zxn = Zx.to(dev), W.to(dev), Zxn.to(dev)
        for ep in range(epochs):
            perm = torch.randperm(len(starts_t), device="cpu")
            tot = {"lin": 0.0, "pred": 0.0, "multi": 0.0}
            nb = 0
            for i in range(0, len(perm), batch):
                sel = starts_t[perm[i:i + batch]].to(dev)
                x0, u0, x1 = Zx[sel], W[sel], Zxn[sel]
                z0 = lift_t(x0)
                z1_hat = z0 @ A.T + u0 @ B.T
                z1 = lift_t(x1)

                loss_lin = ((z1_hat - z1) ** 2).mean()
                loss_pred = ((z1_hat[:, :X_DIM] - x1) ** 2).mean()

                # Coklu adim: kaldirilmis uzayda ilerlet, her adimda durum hatasi
                z = z0
                loss_multi = 0.0
                for k in range(horizon):
                    z = z @ A.T + W[sel + k] @ B.T
                    loss_multi = loss_multi + ((z[:, :X_DIM] - Zxn[sel + k]) ** 2).mean()
                loss_multi = loss_multi / horizon

                loss = w_lin * loss_lin + w_pred * loss_pred + w_multi * loss_multi
                if spectral_penalty > 0:
                    # rho(A) > 1 dogrudan cezalandirilir (kararlilik kisitli Koopman)
                    sv = torch.linalg.matrix_norm(A, ord=2)
                    loss = loss + spectral_penalty * torch.relu(sv - 1.0) ** 2

                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    list(enc.parameters()) + [A, B], 10.0)
                opt.step()
                tot["lin"] += float(loss_lin.detach()); tot["pred"] += float(loss_pred.detach())
                tot["multi"] += float(loss_multi.detach()); nb += 1
            if verbose:
                rho = float(np.abs(np.linalg.eigvals(A.detach().cpu().numpy())).max())
                print(f"  epoch {ep+1:2d}/{epochs}  lin {tot['lin']/nb:.5f}  "
                      f"pred {tot['pred']/nb:.5f}  multi {tot['multi']/nb:.5f}  "
                      f"rho(A) {rho:.5f}", flush=True)

        # --- numpy'a aktar ---
        self._W = [l.weight.detach().cpu().numpy().astype(np.float64)
                   for l in enc if hasattr(l, "weight")]
        self._b = [l.bias.detach().cpu().numpy().astype(np.float64)
                   for l in enc if hasattr(l, "bias")]
        self.A = A.detach().cpu().numpy().astype(np.float64)
        self.B = B.detach().cpu().numpy().astype(np.float64)
        if self.affine:
            j = self.z_dim - 1
            self.A[j, :] = 0.0; self.A[j, j] = 1.0; self.B[j, :] = 0.0
        self._fitted = True
        self._check_lift_contract(normalize_x(np.asarray(X[:16], np.float64)))
        return self
