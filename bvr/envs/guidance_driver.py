"""
CANLI (egitim dışı) guidance surucusu 

GuidanceEnv (bvr/envs/guidance_env.py) bir gym.Env: fizik + odul + rastgele
hedef uretimi + Gym episode (terminated/truncated) mantigi iç içedir, RL
EGITIMI icin tasarlanmistir

Bu sinif sadece fiziği içerir: JSBSim + Ic Dongu (60 Hz) + (opsiyonel) Kalkan.
Odul yok, rastgele hedef yok, Gym yok -- Faz 1.5'te bir angajmanin bitisini
zaten Engagement (bvr/combat/engagement.py) yonetiyor, guidance sadece
"verilen komutu uygula" der.

Hedef secimi (komutanin/TAC-08'in isi) ve gozlem uretimi (bvr/envs/
guidance_shared.py::build_obs) BILEREK bu sinifin DISINDA tutuldu -- cagiran
taraf `driver.st` ve `driver.last_applied`'i kullanarak gozlemi kendisi
kurar:

    driver = GuidanceDriver(cfg)
    st = driver.reset(alt_ft=20000, mach=0.8, heading_deg=90)
    obs = guidance_shared.build_obs(driver.st, tgt_n, tgt_e, tgt_alt, tgt_mach,
                                     driver.last_applied)
    action, _ = frozen_model.predict(obs, deterministic=True)
    st = driver.tick(action)
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..sim.jsbsim_bridge import F16Sim
from ..control.inner_loop import InnerLoop, InnerLoopCommand
from ..models.state_def import state_from_flight, cmd_to_u
from .guidance_env import GuidanceConfig, ACT_DIM
from . import guidance_shared as gs

# payload_check.py'de OLCULEN degerler -- f16.xml'in TEK gercek nokta
# kutlesi pointmass[0] (varsayilan: pilot, 230 lb @ X=-336.2 in). Ek yuk
# (ornegin kalan fuze agirligi) BU yuvaya eklenir ve konumu birlesik
# momenti koruyacak sekilde secilir; aksi halde CG kayar (F-16 gevsek
# kararli, bu olcumu yanli hale getirir). bkz. HANDOFF.md tuzak 38.
_PAYLOAD_PILOT_W_LB = 230.0
_PAYLOAD_PILOT_X_IN = -336.2
_PAYLOAD_STATION_X_IN = -191.0   # ucagin CG'sine yakin (gercekte de böyle halledilir)


class GuidanceDriver:
    """Dondurulmus guidance politikasinin canli surucusu (sadece fizik)."""

    def __init__(self, cfg: Optional[GuidanceConfig] = None, seed: Optional[int] = None):
        self.cfg = cfg or GuidanceConfig()
        self.sim = F16Sim(seed=seed)
        self.inner = InnerLoop(dt=1.0 / self.cfg.ctrl_hz)
        self._sub = int(round(self.sim.fdm_hz / self.cfg.ctrl_hz))
        self._inner_per_outer = int(round(self.cfg.ctrl_hz / self.cfg.outer_hz))

        self.last_applied = np.zeros(ACT_DIM)
        self.st = None

        # GuidanceEnv.__init__ ile BIREBIR ayni kurulum -- iki ayri yerde
        # kalkan kurma mantigi tutulursa biri guncellenip digeri unutulabilir.
        self.shield = None
        if self.cfg.use_shield:
            from ..models.base import DynamicsModel
            from ..safety.cbf import CBFShield
            model = DynamicsModel.load(self.cfg.shield_model_path)
            margins = (np.load(self.cfg.shield_margin_path)
                       if self.cfg.shield_margin_path else None)
            self.shield = CBFShield(model, gamma=self.cfg.shield_gamma,
                                    horizons=(tuple(self.cfg.shield_horizons)
                                              if self.cfg.shield_horizons else None),
                                    hard=self.cfg.shield_hard, margins=margins)

    def reset(self, alt_ft: float, mach: float, heading_deg: float = 0.0,
              fuel_frac: Optional[float] = None, gamma_deg: float = 0.0):
        """Belirli bir baslangic kosulunda trim. GuidanceEnv.reset()'in
        aksine RASTGELE degil -- baslangic kosulu cagiran tarafin (komutan/
        senaryo) kararidir."""
        self.st = self.sim.reset(alt_ft=alt_ft, mach=mach, heading_deg=heading_deg,
                                  gamma_deg=gamma_deg, trim=True, fuel_frac=fuel_frac)
        if not self.sim.trimmed:
            raise RuntimeError("GuidanceDriver.reset: trim yakinsamadi")
        self.inner.reset(trim_throttle=self.sim["fcs/throttle-cmd-norm"])
        if self.shield is not None:
            self.shield.reset_state()
        self.last_applied = np.zeros(ACT_DIM)
        return self.st

    def set_payload(self, extra_lb: float) -> None:
        """JSBSim'in gercek agirligina ek yuk (ornegin kalan fuze kutlesi)
        yazar -- payload_check.py'de dogrulanan yontemle (pointmass[0],
        CG korunarak). `combat_state`'e (dataclasses.replace kopyasi) veya
        FlightState'e DEGIL, DOGRUDAN JSBSim'e yazar; boylece Engagement.
        fire()'in mass_lb/weight_lb denemesinin (FlightState'te böyle bir
        alan olmadigi icin hicbir zaman gercek fizige ulasmayan, sadece
        mock durumlarda calisan) BOSLUGUNU dolduruyor -- bkz. HANDOFF.md.

        RESET ARASINDA KALICIDIR (JSBSim tuzagi, HANDOFF.md tuzak 37) --
        `reset()`'ten ONCE cagrilirsa trim onu hesaba katar; ucus SIRASINDA
        (ornegin bir fuze atilinca) tekrar cagirmak yeniden trim GEREKTIRMEZ,
        sonraki adimdan itibaren gecerli olur (tipki yakit tuketimi gibi
        surekli degisen bir kutleye ic dongu zaten uyum sagliyor)."""
        w = _PAYLOAD_PILOT_W_LB + extra_lb
        x = (_PAYLOAD_PILOT_X_IN if extra_lb == 0.0 else
             (_PAYLOAD_PILOT_W_LB * _PAYLOAD_PILOT_X_IN + extra_lb * _PAYLOAD_STATION_X_IN) / w)
        self.sim["inertia/pointmass-weight-lbs[0]"] = w
        self.sim["inertia/pointmass-location-X-inches[0]"] = x

    def tick(self, action: np.ndarray):
        """Bir dis-dongu (outer_hz) adimi ilerlet -- GuidanceEnv.step()'in
        FIZIK kismiyla (odul/hedef/tanı haric) birebir ayni.

        action: [-1,1]^3, GuidanceEnv ile AYNI aksiyon sozlesmesi (phi/gamma/mach).
        """
        a_raw = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)

        # KOMUT SLEW SINIRI -- GuidanceEnv.step() ile AYNI olmali. Bu egitime
        # ozgu bir sey DEGIL: "gercek bir gudum sistemi de komutu 10 Hz'de
        # tam olcekte savurmaz" (guidance_env.py basligindaki gerekce), yani
        # dondurulmus model bu filtre ALTINDA egitildi/kalibre oldu. Atlarsak
        # modelin ham cikisini, egitimde hic gormedigi (filtresiz) bir
        # bicimde uygulamis oluruz.
        if self.cfg.action_rate_limit is not None:
            lim = float(self.cfg.action_rate_limit)
            a = np.clip(a_raw, self.last_applied - lim, self.last_applied + lim)
        else:
            a = a_raw
        cmd = gs.action_to_cmd(a, self.cfg.mach_lo, self.cfg.mach_hi)

        if self.shield is not None:
            u_des = cmd_to_u(cmd)
            u_safe, _ = self.shield.filter(state_from_flight(self.st), u_des)
            cmd = InnerLoopCommand(float(u_safe[0]), float(u_safe[1]),
                                   float(u_safe[2])).clipped()
        self.last_applied = gs.cmd_to_action(cmd, self.cfg.mach_lo, self.cfg.mach_hi)

        for _ in range(self._inner_per_outer):
            el, ail, thr, rud = self.inner.update(self.st, cmd)
            self.sim.send_fcs(el, ail, thr, rud)
            self.st = self.sim.run(self._sub)

        return self.st
