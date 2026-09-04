"""
CBF KOMUT YONETICISI (Control Barrier Function command governor).

=============================================================================
NE YAPAR
=============================================================================
Ajanin istedigi komutu, ucus zarfindan cikmayacak EN YAKIN komuta projekte
eder:

        min ||w - w_istenen||^2 + rho * sum(s)
        oyle ki   G w <= rhs + s ,   s >= 0 ,   w_alt <= w <= w_ust

G ve rhs, dinamik modelden gelir (bvr/models/base.py::cbf_rows):

        h(x) = d - C x >= 0                 (bariyer: zarfin icindeyiz)
        h(x_{k+1}) >= (1 - gamma) h(x_k)    (ayrik zamanli CBF kosulu)

Sozle: "bir sonraki adimda sinira olan mesafen, simdikinin en fazla
(1-gamma) katina inebilir." gamma sinira yaklasma HIZINI ayarlar;
gamma -> 0 asiri muhafazakar, gamma -> 1 kisit yok demektir.

=============================================================================
NEDEN DIS DONGUDE (KOMUT UZERINDE), YUZEY KOMUTUNDA DEGIL
=============================================================================
Onceki mimaride kalkan 60 Hz'de yuzey komutuna uygulaniyordu ve islevsizdi:
1/60 saniyede elevator, pitch ACISINI neredeyse hic degistirmez (bagil
derece 2-3), dolayisiyla QP'nin gordugu otorite |CB| ~ 0.01 idi -- kalkan
matematiksel olarak "hicbir sey yapamam" diyordu. 0.1 saniyelik bir dis
dongu adiminda ise komut, durumu GERCEKTEN degistirir. Ayrica bu katmanda
ic dongunun ve FLCS'in kendi limitleri zaten alt katmani koruyor.

=============================================================================
NEDEN QP MATRISI SABIT (ve bu neden onemli)
=============================================================================
Kaldirilmis model komutta DOGRUSAL oldugundan (z+ = A z + B w), kisitin
sol tarafi  G = (C*S) @ B[:X_DIM]  duruma HIC bagli degildir; yalnizca
sag taraf (rhs) x ile degisir. Bu sayede QP bir kez kurulur, her cagride
sadece l/u/q vektorleri guncellenir -> OSQP ile ~50-100 mikrosaniye.
Eski kodda her adimda cvxpylayers ile satir satir cozum yapiliyordu
(256 satir ~0.5 s); egitim bu yuzden surunuyordu.

=============================================================================
SLACK (GEVSEKLIK) HAKKINDA
=============================================================================
Slack olmadan QP infeasible olabilir (orn. zaten zarf disindaysak, ya da
model hatasi yuzunden hicbir komut kosulu saglamiyorsa) ve cozucu coker.
Ama slack cezasi cok dusukse kalkan kisiti "satin alip" ihlal eder --
eski mimaride olan buydu: politika surekli ulasilamaz komut veriyor,
kalkan surekli yamaliyordu (Shield_Da ~ 1.2) ve ajan zarfi hic ogrenmiyordu.

Buradaki denge: slack cezasi YUKSEK (varsayilan 1e4) tutulur, yani slack
yalnizca gercek infeasibility durumunda devreye girer; ve slack kullanimi
AYRICA RAPORLANIR. `hard=True` ile tamamen kapatilabilir (tez ablasyonu).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import scipy.sparse as sp

try:
    import osqp
    _HAS_OSQP = True
except Exception:                                    # pragma: no cover
    _HAS_OSQP = False

from ..models.base import DynamicsModel
from ..models.state_def import U_DIM, U_SCALE, envelope_constraints
from ..sim import aircraft as ac


@dataclass
class ShieldStats:
    """Kalkanin ne kadar mudahale ettigi -- tezin ana guvenlik metrigi."""
    n_calls: int = 0
    n_active: int = 0            # komutu fiilen degistirdigi adim sayisi
    n_slack: int = 0             # kisitin ihlal edildigi (infeasible) adim
    sum_dev: float = 0.0         # toplam ||w_safe - w_des||
    max_dev: float = 0.0
    n_fail: int = 0              # cozucu hatasi

    def add(self, dev: float, slack: float, ok: bool) -> None:
        self.n_calls += 1
        if not ok:
            self.n_fail += 1
        if dev > 1e-6:
            self.n_active += 1
        if slack > 1e-6:
            self.n_slack += 1
        self.sum_dev += dev
        self.max_dev = max(self.max_dev, dev)

    def summary(self) -> dict:
        n = max(self.n_calls, 1)
        return dict(mudahale_orani=self.n_active / n,
                    slack_orani=self.n_slack / n,
                    ort_sapma=self.sum_dev / n,
                    max_sapma=self.max_dev,
                    cozucu_hata=self.n_fail)


class CBFShield:
    """Ayrik zamanli CBF komut projeksiyonu (OSQP)."""

    #: Varsayilan ufuklar: 0.1 / 0.5 / 1.0 saniye (dis dongu 10 Hz).
    #: Tek adim (1) bazi bariyerler icin gurultu seviyesinde otorite verir;
    #: uzun ufuk komuta gercek yetki kazandirir. Ara ufuklar da tutulur ki
    #: filtre "sonunda toparlarim" diyerek aradan tehlikeli gecmesin.
    #: Kisa ufuklar: hizli durumlar (alpha, beta, n) icin. 0.1 - 2 s.
    #: Uzun ufuklar: YALNIZCA enerji/Mach bariyeri icin. 5 - 30 s.
    #:
    #: NEDEN AYRI: olcum, bariyerlerin ZAMAN OLCEKLERININ farkli oldugunu
    #: gosterdi. alpha/beta/n saniye altinda degisir; 2 s ufuk yeterlidir
    #: (ihlal ~%0.03). Enerji ise ONLARCA SANIYE olceginde evrilir: ucak
    #: 40 saniye once basladigi bir tirmanista enerjisini bitirir, Mach
    #: tabana yaklastiginda artik hicbir komut kurtaramaz. 2 saniyelik bir
    #: filtre bunu goremez.
    #:
    #: Uzun ufuklarin YALNIZCA Mach satirina uygulanmasi sart: hizli
    #: durumlara 30 s ufuk koymak, modelin o olcekteki hatasi yuzunden
    #: filtreyi asiri muhafazakar yapar (olculdu: her bariyere uzun ufuk
    #: -> gorev coker).
    DEFAULT_HORIZONS = (1, 5, 10, 20, 50, 150, 300)
    LONG_HORIZON_FROM = 50
    LONG_HORIZON_BARRIERS = ("mach_min", "mach_max")

    def __init__(self, model: DynamicsModel, gamma: float = 0.1,
                 horizons: Optional[Tuple[int, ...]] = None,
                 slack_weight: float = 1e3, slack_quad: float = 1.0,
                 hard: bool = False, margins: Optional[np.ndarray] = None,
                 long_barriers: Optional[Tuple[str, ...]] = None,
                 long_from: Optional[int] = None,
                 w_lo: Optional[np.ndarray] = None,
                 w_hi: Optional[np.ndarray] = None):
        if not _HAS_OSQP:
            raise ImportError("osqp gerekli:  pip install osqp")
        self.model = model
        self.gamma = float(gamma)
        self.horizons = tuple(horizons or self.DEFAULT_HORIZONS)
        self.slack_weight = float(slack_weight)
        self.slack_quad = float(slack_quad)
        # Robust CBF marji (bvr/safety/robust.py). None ise sikilastirma yok.
        self._raw_margins = None if margins is None else np.asarray(margins, float)
        self.margins = None            # _build icinde satir secimine gore ayarlanir
        self.hard = bool(hard)
        self.stats = ShieldStats()

        C, d, base_names = envelope_constraints()
        self.long_barriers = tuple(long_barriers if long_barriers is not None
                                   else self.LONG_HORIZON_BARRIERS)
        self.long_from = int(long_from if long_from is not None
                             else self.LONG_HORIZON_FROM)
        # Uzun ufuklarda YALNIZCA long_barriers satirlari tutulur.
        hs = sorted(set(int(h) for h in self.horizons))
        keep, names = [], []
        for k, h in enumerate(hs):
            for j, nm in enumerate(base_names):
                if h < self.long_from or nm in self.long_barriers:
                    keep.append(k * len(base_names) + j)
                    names.append(f"{nm}@{h}")
        self._keep = np.asarray(keep, dtype=int)
        self.names = tuple(names)
        self.nc = len(keep)

        # Komut kutusu, dis dongunun FIZIKSEL aksiyon zarfina esittir.
        # (Onceki hali +-4.0 idi; QP gamma_cmd'yi -91 dereceye kadar
        #  itebiliyordu -- yani hicbir zaman uygulanamayacak bir komut.)
        u_lo = np.array([-math.radians(ac.BANK_MAX_DEG),
                         math.radians(ac.GAMMA_MIN_DEG), ac.MACH_MIN])
        u_hi = np.array([+math.radians(ac.BANK_MAX_DEG),
                         math.radians(ac.GAMMA_MAX_DEG), ac.MACH_MAX])
        self.w_lo = model.u_to_w(u_lo)[0] if w_lo is None else np.asarray(w_lo)
        self.w_hi = model.u_to_w(u_hi)[0] if w_hi is None else np.asarray(w_hi)

        # Dis dongu adimi (0.1 s) basina izin verilen komut degisimi.
        # Normal gudume engel olmayacak kadar genis, sacma sicramalari
        # engelleyecek kadar dar secilir.
        du = np.array([math.radians(25.0), math.radians(8.0), 0.15])
        self.dw = du / U_SCALE
        self._w_prev: Optional[np.ndarray] = None

        self._build()

    def reset_state(self) -> None:
        """Bolum basinda cagrilir: komut hiz sinirlayicinin hafizasini temizler."""
        self._w_prev = None

    # ------------------------------------------------------------------
    def _build(self) -> None:
        """QP'yi bir kez kur. Kisit matrisi duruma bagli DEGILDIR."""
        nc, nu = self.nc, U_DIM
        # G = (C * X_SCALE) @ B[:X_DIM]  -- yalnizca sabitlerden olusur,
        # duruma bagli degildir. Nominal bir x ile bir kez cikarilir.
        G_full, _ = self.model.cbf_rows(self._probe_x(), self.gamma, self.horizons)
        G = G_full[self._keep]

        # --- OTORITESIZ SATIRLARI AT, KALANLARI NORMALIZE ET ---
        # ||G_row|| ~ 0 olan bir kisit, komutun O ADIMDA hicbir etkisinin
        # olmadigi bir bariyerdir (orn. hard_deck@1: 0.1 saniyede irtifa
        # degismez, katsayilar gurultudur). Boyle bir satiri QP'de tutmak
        # yalnizca slack harcatir ve cozucuyu zorlar -- kontrol edemedigin
        # seyi kisit yapamazsin. Kalan satirlar birim norma olceklenir:
        # kisitin ANLAMI degismez (h >= 0 pozitif sabitle bolununce ayni
        # kalir) ama QP'nin kosullanmasi duzelir (olculdu: 925x -> ~1x).
        nrm = np.linalg.norm(G, axis=1)
        alive = nrm >= 0.02
        self._keep = self._keep[alive]
        self.names = tuple(n for n, a in zip(self.names, alive) if a)
        self._row_scale = nrm[alive]
        self.G = G[alive] / self._row_scale[:, None]
        self.nc = nc = int(alive.sum())
        # Marjlar tam yigin icin hesaplanmisti; ayni satir secimi ve ayni
        # olcekleme onlara da uygulanmali.
        if self._raw_margins is not None:
            self.margins = self._raw_margins[self._keep] / self._row_scale

        if self.hard:
            nz = nu
            P = sp.diags(np.r_[np.full(nu, 2.0)]).tocsc()
            A = sp.vstack([sp.csc_matrix(self.G), sp.eye(nu)]).tocsc()
            l = np.r_[np.full(nc, -np.inf), self.w_lo]
            u = np.r_[np.zeros(nc), self.w_hi]
        else:
            nz = nu + nc
            # Slack'e KUCUK BIR KARESEL terim eklenir. Saf dogrusal ceza
            # (P'de sifir) OSQP icin cok sert bir problem uretir: olculdu,
            # 4000 iterasyonda yakinsamiyordu ("maximum iterations reached").
            # Karesel terim problemi kesin (exact) cezadan uzaklastirmayacak
            # kadar kucuk, ama sayisal olarak cozulebilir hale getirir.
            P = sp.diags(np.r_[np.full(nu, 2.0),
                               np.full(nc, 2.0 * self.slack_quad)]).tocsc()
            A = sp.vstack([
                sp.hstack([sp.csc_matrix(self.G), -sp.eye(nc)]),      # Gw - s <= rhs
                sp.hstack([sp.csc_matrix((nc, nu)), sp.eye(nc)]),  # s >= 0
                sp.hstack([sp.eye(nu), sp.csc_matrix((nu, nc))]),  # kutu
            ]).tocsc()
            l = np.r_[np.full(nc, -np.inf), np.zeros(nc), self.w_lo]
            u = np.r_[np.zeros(nc), np.full(nc, np.inf), self.w_hi]

        self._nz = nz
        q = np.zeros(nz)
        if not self.hard:
            q[nu:] = self.slack_weight

        self.prob = osqp.OSQP()
        self.prob.setup(P=P, q=q, A=A, l=l, u=u, verbose=False,
                        eps_abs=1e-5, eps_rel=1e-5, polish=True,
                        max_iter=20000, warm_starting=True)
        self._l, self._u, self._q = l.copy(), u.copy(), q.copy()

    @staticmethod
    def _probe_x() -> np.ndarray:
        """G'yi cikarmak icin nominal bir durum (G, x'e bagli degildir)."""
        from ..models.state_def import X_CENTER
        return X_CENTER.copy()

    # ------------------------------------------------------------------
    def filter(self, x: np.ndarray, u_des: np.ndarray
               ) -> Tuple[np.ndarray, dict]:
        """Fiziksel durum x ve istenen komut u_des -> guvenli komut."""
        _, rhs_full = self.model.cbf_rows(x, self.gamma, self.horizons)
        rhs = rhs_full[self._keep] / self._row_scale
        if self.margins is not None:
            # Model hatasi kadar SIKILASTIR: kalkan, modele guvendigi kadar
            # degil, modelin dogrulanmis dogrulugu kadar guvenir.
            rhs = rhs - self.margins
        w_des = self.model.u_to_w(u_des)[0]

        # KOMUT DEGISIM HIZI SINIRI.
        # Olcum: zarfin DISINDA (h < 0) baslarken saf projeksiyon,
        # kisiti saglamanin "en ucuz" yolu olarak komutu bir adimda uca
        # firlatiyordu (orn. Mach 0.30 -> 2.00). Matematiksel olarak dogru
        # ama fiziksel olarak sacma. Hiz sinirlamasi, kutu kisitlarini her
        # cagride bir onceki UYGULANAN komutun etrafinda daraltarak bunu
        # engeller -- klasik kontrolde komut sinirlayicinin (rate limiter)
        # tam karsiligidir.
        if self._w_prev is None:
            lo, hi = self.w_lo, self.w_hi
        else:
            lo = np.maximum(self.w_lo, self._w_prev - self.dw)
            hi = np.minimum(self.w_hi, self._w_prev + self.dw)
        self._l[-U_DIM:] = lo
        self._u[-U_DIM:] = hi

        self._u[:self.nc] = rhs
        self._q[:U_DIM] = -2.0 * w_des
        self.prob.update(q=self._q, l=self._l, u=self._u)
        res = self.prob.solve()

        ok = res.info.status_val in (1, 2)     # solved / solved_inaccurate
        if ok and res.x is not None and np.all(np.isfinite(res.x[:U_DIM])):
            w_safe = res.x[:U_DIM]
            slack = 0.0 if self.hard else float(np.max(res.x[U_DIM:]))
        else:
            # Cozucu basarisiz: kalkani devre disi birakma, ama kisiti da
            # zorlama -- istenen komutu kutuya kirpip gec ve bunu RAPORLA.
            w_safe = np.clip(w_des, self.w_lo, self.w_hi)
            slack = float("nan")

        dev = float(np.linalg.norm(w_safe - w_des))
        self.stats.add(dev, 0.0 if not np.isfinite(slack) else slack, ok)

        self._w_prev = w_safe.copy()
        u_safe = self.model.w_to_u(w_safe)[0]
        # Teshis: hangi bariyer GERCEKTEN etkin? argmax tek basina yaniltici,
        # cunku hicbir kisit aktif degilken de "en az negatif" satiri
        # doner (olculdu: kalkan hic calismazken bile %71 'alpha_min@1'
        # raporlaniyordu). Bu yuzden yalnizca sifira yakin satiri bildiririz.
        margin = self.G @ w_safe - rhs
        j = int(np.argmax(margin))
        binding = self.names[j] if margin[j] > -1e-3 else None
        info = dict(dev=dev, slack=slack, ok=ok,
                    active=dev > 1e-6, binding=binding, margin=float(margin[j]))
        return u_safe, info

    def reset_stats(self) -> None:
        self.stats = ShieldStats()
