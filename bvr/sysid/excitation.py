"""
Sistem tanimlama icin UYARIM (excitation) sinyali tasarimi.

=============================================================================
NEDEN ONEMLI: PERSISTENT EXCITATION (kalici uyarim)
=============================================================================
Veriden model cikarmanin (DMD/EDMD/Koopman) matematiksel on kosulu, verinin
"bilgi tasimasi"dir. Formel olarak regresyon matrisinin tam ranka sahip
olmasi gerekir; sezgisel olarak: sistem YETERINCE cesitli sekilde
uyarilmalidir.

Eski mimarinin sessiz hatasi tam buradaydi: DMD, RL'in kendi urettigi
(on-policy) veriden ogreniyordu. Ajan duz ucmayi ogrendikce veri
cesitliligini kaybediyor, regresyon rank dusuyor, model curuyordu --
ve tam da o anda kalkanin dogru calismasi gerekiyordu.

Cozum: modeli TASARLANMIS uyarimla toplanan OFFLINE veriden fit etmek.
Ucus testi literaturunde kullanilan standart sinyaller:

  MULTISINE  : farkli frekanslarda sinuslerin toplami. Genis bir frekans
               bandini AYNI ANDA uyarir, genligi sinirlidir (ucak zarfta
               kalir), ve enerjisi zamanda yayilmistir. Ucus testinde
               tercih edilen sinyaldir.
  RANDOM STEP: rastgele suredeki basamaklar. Gecici (transient) davraniti
               ve genlik-lineerlik disi etkileri yakalar.
  DOUBLET/3-2-1-1: klasik el manevralari; belirli bir modu (orn. short
               period) temiz uyarir. Dogrulama/karsilastirma icin faydali.
  CHIRP      : frekansi suren suresince suzulen sinus; frekans yanitini
               tarar.

Bu modul hepsini uretir; collect.py bunlari karistirarak kullanir.

FREKANS SECIMI: uyarim, modellenecek dinamigin bant genisligini kapsamalidir.
Ic dongu olcumlerimizden (scripts/test_inner_loop.py):
  phi   yukselme ~0.8 s  -> ilgili bant ~0.02-0.6 Hz
  gamma yukselme ~1.5 s  -> ilgili bant ~0.02-0.4 Hz
  mach  yukselme ~10 s   -> ilgili bant ~0.005-0.06 Hz  (cok yavas kanal)
=============================================================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


class Signal:
    """t (saniye) -> skaler deger."""

    def __call__(self, t: float) -> float:
        raise NotImplementedError


@dataclass
class MultiSine(Signal):
    """Farkli frekanslarda sinuslerin toplami; tepe degeri `amp`e normalize.

    Fazlar rastgele secilir. Tepe-normalizasyonu, sinyalin zarf disina
    tasmamasini garanti eder -- genligi bilerek sinirli tutmak, ucagi
    departure'a sokmadan genis frekans bandi uyarmanin yoludur.
    """
    amp: float
    f_lo: float
    f_hi: float
    n_tones: int = 8
    bias: float = 0.0
    rng: np.random.Generator = field(default_factory=np.random.default_rng)

    def __post_init__(self):
        # Log-esit araliklandirilmis frekanslar: dusuk frekansta da yuksekte
        # de esit "cozunurluk" saglar.
        self.freqs = np.geomspace(self.f_lo, self.f_hi, self.n_tones)
        self.phases = self.rng.uniform(0.0, 2 * math.pi, self.n_tones)
        # Tepe normalizasyonu icin bir tur ornekle
        t = np.linspace(0.0, 1.0 / self.f_lo, 4000)
        y = np.sum(np.sin(2 * math.pi * self.freqs[:, None] * t[None, :]
                          + self.phases[:, None]), axis=0)
        self._norm = float(np.abs(y).max()) or 1.0

    def __call__(self, t: float) -> float:
        y = float(np.sum(np.sin(2 * math.pi * self.freqs * t + self.phases)))
        return self.bias + self.amp * y / self._norm


@dataclass
class RandomSteps(Signal):
    """Rastgele sureli, rastgele genlikli basamaklar (piecewise constant).

    Gecici davranisi ve genlik dogrusalsizligini yakalar. Bekleme sureleri
    [hold_lo, hold_hi] araligindan cekilir; bu aralik sistemin zaman
    sabitlerini kapsamalidir (cok kisa -> sistem hic oturmaz, cok uzun ->
    veri tekrar eder).
    """
    lo: float
    hi: float
    hold_lo: float
    hold_hi: float
    rng: np.random.Generator = field(default_factory=np.random.default_rng)

    def __post_init__(self):
        self._t_next = 0.0
        self._val = float(self.rng.uniform(self.lo, self.hi))

    def __call__(self, t: float) -> float:
        if t >= self._t_next:
            self._val = float(self.rng.uniform(self.lo, self.hi))
            self._t_next = t + float(self.rng.uniform(self.hold_lo, self.hold_hi))
        return self._val


@dataclass
class Doublet(Signal):
    """Klasik doublet: +A (T sn), -A (T sn), sonra 0. Belirli bir modu uyarir."""
    amp: float
    period: float
    t0: float = 0.0

    def __call__(self, t: float) -> float:
        dt = t - self.t0
        if 0.0 <= dt < self.period:
            return self.amp
        if self.period <= dt < 2 * self.period:
            return -self.amp
        return 0.0


@dataclass
class Multistep3211(Signal):
    """3-2-1-1 manevrasi: ucus testinin standart genis-bant uyarimi.

    Sureler 3T, 2T, 1T, 1T ve isaretler +,-,+,- seklindedir. Tek bir
    doublet'ten daha genis bir frekans bandi uyarir; kisa suredir, bu yuzden
    ucak trim noktasindan uzaklasmadan olcum yapilabilir.
    """
    amp: float
    T: float
    t0: float = 0.0

    def __call__(self, t: float) -> float:
        dt = t - self.t0
        if dt < 0:
            return 0.0
        for span, sign in ((3, +1), (2, -1), (1, +1), (1, -1)):
            if dt < span * self.T:
                return sign * self.amp
            dt -= span * self.T
        return 0.0


@dataclass
class Chirp(Signal):
    """Logaritmik suzulen sinus: frekans yanitini tarar."""
    amp: float
    f_lo: float
    f_hi: float
    duration: float

    def __call__(self, t: float) -> float:
        u = min(max(t / self.duration, 0.0), 1.0)
        f = self.f_lo * (self.f_hi / self.f_lo) ** u
        return self.amp * math.sin(2 * math.pi * f * t)


@dataclass
class Sum(Signal):
    """Birden fazla sinyali topla, sonra sinirlara kirp."""
    parts: Sequence[Signal]
    lo: float = -np.inf
    hi: float = np.inf

    def __call__(self, t: float) -> float:
        return float(np.clip(sum(p(t) for p in self.parts), self.lo, self.hi))


@dataclass
class Constant(Signal):
    value: float

    def __call__(self, t: float) -> float:
        return self.value
