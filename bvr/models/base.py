"""
DINAMIK MODEL ARAYUZU (tak-cikar).

=============================================================================
TEZIN DENEY OMURGASI
=============================================================================
Ayni RL, ayni CBF, ayni veri -- degisen tek sey model. Uc uygulama:
    DMDModel          (baseline)
    EDMDModel         (elle secilen ozellik kitapligi)
    DeepKoopmanModel  (sinir agi ile ogrenilen latent uzay)
CBF katmani modelin turunu BILMEZ; sadece `cbf_rows()` cagirir.

=============================================================================
KOOPMAN SOZLESMESI VE "DURUM-ICEREN GOZLENEBILIRLER" KISITI
=============================================================================
Koopman fikri: dogrusal olmayan sistemi, durumu daha yuksek boyutlu bir
"gozlenebilirler" (observables) uzayina KALDIRIP orada DOGRUSAL bir
operatorle temsil etmek:

        z = Psi(x)          (lifting / kaldirma)
        z_{k+1} = A z_k + B w_k

Bu projede Psi'nin ilk blogu ZORUNLU olarak x'in KENDISIDIR:

        Psi(x) = [ x , ek_ozellikler... ]

Neden zorunlu: CBF bariyerleri h(x) = d - C x seklinde HAM durum uzerinde
tanimli (alpha limiti, g limiti, irtifa tabani...). Eger Psi icinde x'in
kendisi bulunmazsa C @ z tanimsiz olur ve bariyeri kaldirilmis uzaya
tasiyamayiz. Literaturde buna "state-inclusive observables" denir ve
Koopman + CBF birlestiren calismalarin standart varsayimidir. Tezde
"bariyerin korunmasi icin gozlenebilir secim kisiti" olarak savunulur.

=============================================================================
NEDEN ARTIK (DELTA) REGRESYONU?
=============================================================================
Dis dongu adimi 0.1 s; bu surede durum cok az degisir, yani gercek A
matrisi BIRIM MATRISE yakindir. Ridge duzenlemesi katsayilari SIFIRA
ceker; A'yi dogrudan fit edersek modeli yanlis yere (sifira) cekmis
oluruz. Bunun yerine  z_{k+1} - z_k  regresyonu yapilir:

        z_{k+1} - z_k = A_d z_k + B w_k     ->     A = I + A_d

Boylece ridge, A'yi BIRIM MATRISE dogru duzenler -- fiziksel olarak dogru
on kabul budur.
=============================================================================
"""
from __future__ import annotations

import abc
import pickle
from typing import Optional, Sequence, Tuple

import numpy as np

from .state_def import (
    X_DIM, U_DIM, X_CENTER, X_SCALE, U_CENTER, U_SCALE,
    normalize_x, denormalize_x, normalize_u, envelope_constraints,
)


class DynamicsModel(abc.ABC):
    """Tum dinamik modellerin ortak sozlesmesi."""

    name: str = "base"

    def __init__(self):
        self.A: Optional[np.ndarray] = None    # (Z, Z)
        self.B: Optional[np.ndarray] = None    # (Z, U)
        self._fitted = False

    # ---------------- alt siniflarin doldurmasi gerekenler ----------------
    @property
    @abc.abstractmethod
    def z_dim(self) -> int:
        """Kaldirilmis uzayin boyutu."""

    @abc.abstractmethod
    def lift(self, xn: np.ndarray) -> np.ndarray:
        """Normalize durum (N, X_DIM) -> kaldirilmis (N, z_dim).

        SOZLESME: cikti[:, :X_DIM] == xn  (durum-iceren gozlenebilirler).
        """

    @abc.abstractmethod
    def fit(self, X: np.ndarray, U: np.ndarray, Xn: np.ndarray, **kw) -> "DynamicsModel":
        """Fiziksel birimli veriden modeli uydur."""

    # ---------------- ortak yetenekler ------------------------------------
    def _fit_linear(self, Z: np.ndarray, W: np.ndarray, Zn: np.ndarray,
                    ridge: float = 1e-6) -> None:
        """Kaldirilmis uzayda ARTIK (delta) ridge regresyonu.

        Zn - Z = A_d Z + B W  cozulur, sonra A = I + A_d.
        """
        Om = np.hstack([Z, W])                       # (N, z+u)
        Y = Zn - Z                                   # (N, z)   ARTIK hedef
        G = Om.T @ Om
        G += ridge * np.trace(G) / G.shape[0] * np.eye(G.shape[0])
        Theta = np.linalg.solve(G, Om.T @ Y).T       # (z, z+u)
        A_d = Theta[:, : self.z_dim]
        self.B = np.ascontiguousarray(Theta[:, self.z_dim:])
        self.A = np.eye(self.z_dim) + A_d
        self._fitted = True

    def _check_lift_contract(self, xn: np.ndarray) -> None:
        z = self.lift(xn[:8])
        if not np.allclose(z[:, :X_DIM], xn[:8], atol=1e-9):
            raise AssertionError(
                f"{self.name}: lift() sozlesmesi ihlal -- ilk {X_DIM} bilesen "
                "ham (normalize) durum olmak zorunda.")

    # -- tahmin -------------------------------------------------------------
    def predict(self, x: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Bir dis dongu adimi ileri (fiziksel birimler)."""
        xn = normalize_x(np.atleast_2d(x))
        w = normalize_u(np.atleast_2d(u))
        zn = self.lift(xn) @ self.A.T + w @ self.B.T
        return denormalize_x(zn[:, :X_DIM])

    def rollout(self, x0: np.ndarray, U_seq: np.ndarray,
                mode: str = "relift") -> np.ndarray:
        """Coklu adim tahmin.

        mode="relift": her adimda x'e don ve YENIDEN kaldir. CBF'nin fiilen
                       yaptigi sey budur (adim adim tahmin).
        mode="linear": z'yi kaldirilmis uzayda DOGRUSAL olarak ilerlet, en
                       sonda coz. Saf Koopman iddiasini test eder: "bu uzayda
                       dinamik gercekten dogrusal mi?"
        Ikisi arasindaki fark, kaldirmanin ne kadar "gercek Koopman" oldugunun
        olcusudur; tezde ayri satir olarak raporlanir.
        """
        H = len(U_seq)
        out = np.zeros((H, X_DIM))
        W = normalize_u(np.atleast_2d(U_seq))
        if mode == "relift":
            xn = normalize_x(np.atleast_2d(x0))
            for k in range(H):
                zn = self.lift(xn) @ self.A.T + W[k:k + 1] @ self.B.T
                xn = zn[:, :X_DIM]
                out[k] = xn[0]
            return denormalize_x(out)
        elif mode == "linear":
            z = self.lift(normalize_x(np.atleast_2d(x0)))
            for k in range(H):
                z = z @ self.A.T + W[k:k + 1] @ self.B.T
                out[k] = z[0, :X_DIM]
            return denormalize_x(out)
        raise ValueError(mode)

    # -- CBF arayuzu --------------------------------------------------------
    def cbf_rows(self, x: np.ndarray, gamma: float = 0.1,
                 horizons: Sequence[int] = (1,)
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """COK ADIMLI (ongorulu) ayrik zamanli CBF kisiti -> QP satirlari.

        NEDEN COK ADIM?  (tek adim neden yetmiyor)
        ------------------------------------------------------------------
        0.1 saniyelik TEK bir adimda komutun bazi durumlar uzerindeki
        etkisi olculemeyecek kadar kucuktur. Olculen B matrisi:
            n_eff  <- gamma_cmd :  +0.101   (guclu)
            alpha  <- gamma_cmd :  +0.013   (zayif)
            h_dot  <- gamma_cmd :  -0.0005  (GURULTU; isareti bile yanlis)
            alt    <- her sey   :  ~0       (0.1 s'de irtifa degismez)
        Yani irtifa tabani (hard_deck) bariyerinin tek-adim otoritesi
        gurultudur; QP bu yanlis isareti somurup komutu TERS yone iter.
        Bu, eski mimarinin 60 Hz'deki bagil derece (relative degree)
        probleminin bir kat yukarida tekrar ortaya cikmasidir.

        COZUM: komut ZOH ile i adim tutulursa etkisi BIRIKIR:
            z_{k+i} = A^i z_k + S_i w ,   S_i = (I + A + ... + A^{i-1}) B
        Kisit hala w'de DOGRUSALDIR, yani QP yapisi bozulmaz.

        Uygulanan kosul (tek adimli DT-CBF'in dogal genellemesi):
            h(x_{k+i}) >= (1 - gamma)^i h(x_k)      i in horizons
        =>  C x_{k+i} <= (1-(1-gamma)^i) d + (1-gamma)^i C x_k

        i=1 icin klasik DT-CBF ifadesine indirgenir.

        ZOH VARSAYIMI: "bu komutu i adim boyunca tutsam guvende kalir
        miyim?" Ajan bir sonraki adimda komutu degistirebilecegi icin bu
        MUHAFAZAKAR bir varsayimdir -- ongorulu guvenlik filtrelerinde
        (predictive safety filter) standart yaklasim budur.
        """
        key = (float(gamma), tuple(sorted(set(int(h) for h in horizons))))
        cache = getattr(self, "_cbf_cache", None)
        if cache is None or cache["key"] != key:
            cache = self._build_cbf_cache(*key)
            self._cbf_cache = cache

        x = np.asarray(x, dtype=np.float64).reshape(-1)
        z = self.lift(normalize_x(x[None, :]))[0]
        # rhs_i = (1-decay_i) d + decay_i (C x) - C m - M_i z
        # const ve decay, ufuklar boyunca yiginlanmis (nc*nh) vektorlerdir;
        # C@x her ufuk blogunda tekrarlanir.
        rhs = (cache["const"]
               + cache["decay"] * np.tile(cache["C"] @ x, cache["nh"])
               - cache["M"] @ z)
        return cache["G"], rhs

    def _build_cbf_cache(self, gamma: float, hs) -> dict:
        """A^i ve S_i SABITTIR; her cagride yeniden hesaplamak israftir.

        Olcum: z_dim=85 icin 20 ufka kadar matris kuvvetleri, QP cozumunun
        kendisinden daha pahaliydi. Sabit parcalar bir kez hesaplanip
        onbellege alinir; her cagride kalan is yalnizca bir kaldirma (lift)
        ve iki matris-vektor carpimidir.
        """
        C, d, _ = envelope_constraints()
        Cs = C * X_SCALE[None, :]
        nc = C.shape[0]
        Ai = np.eye(self.z_dim)
        Si = np.zeros((self.z_dim, U_DIM))
        G, M, const, decay = [], [], [], []
        for i in range(1, hs[-1] + 1):
            Si = self.A @ Si + self.B
            Ai = self.A @ Ai
            if i in hs:
                dc = (1.0 - gamma) ** i
                G.append(Cs @ Si[:X_DIM, :])
                M.append(Cs @ Ai[:X_DIM, :])
                const.append((1.0 - dc) * d - C @ X_CENTER)
                decay.append(np.full(nc, dc))
        return dict(key=(gamma, hs), G=np.vstack(G), M=np.vstack(M),
                    const=np.concatenate(const), decay=np.concatenate(decay),
                    C=C, nc=nc, nh=len(hs))

    @staticmethod
    def u_to_w(u: np.ndarray) -> np.ndarray:
        return normalize_u(np.atleast_2d(u))

    @staticmethod
    def w_to_u(w: np.ndarray) -> np.ndarray:
        return np.atleast_2d(w) * U_SCALE + U_CENTER

    # -- kalicilik ----------------------------------------------------------
    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str) -> "DynamicsModel":
        with open(path, "rb") as f:
            return pickle.load(f)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} z_dim={self.z_dim} fitted={self._fitted}>"
