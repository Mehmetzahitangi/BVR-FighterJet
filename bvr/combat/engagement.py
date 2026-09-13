"""
Görüş Ötesi (BVR) Angajman Yöneticisi.
- Silah Envanteri ve Kütle Değişimi (Uçak başına 4 AMRAAM, 335 lb/adet)
- 4 Aşamalı Atış Yetki Kontrolü (can_fire)
- Aktif Füzeler Datalink Köprüsü ve Datalink Memory Toleransı
- Çatışma Olay Günlüğü (CombatEvent Stream)
"""

import math
import numpy as np
from dataclasses import dataclass, field
from types import SimpleNamespace

from bvr.combat.missile import Missile, MissileConfig
from bvr.combat.radar import Radar
from bvr.combat.geometry import relative_geometry

from bvr.combat.rwr import RWR, RWRConfig, RWRContact  
from bvr.combat.missile import off_boresight_deg 

@dataclass
class Loadout:
    amraam: int = 4

@dataclass
class LaunchRules:
    max_launch_nm: float = 35.0 #açık kaynak tahmini, Azami atış menzili
    max_per_target: int = 2 # Aynı hedefe eşzamanlı aktif füze sınırı
    require_track: bool = True # Kilit zorunluluğu
    # DIKKAT: datalink hafizasi/toleransi BURADA DEGIL -- MissileConfig.datalink_memory_s'te
    # (MSL-06, Faz 1.3). Iki ayri yerde iki ayri sayac tutulursa toleranslar
    # ust uste biner ve hicbiri anlamli kalmaz. Tek dogruluk kaynagi Missile'in
    # kendisi; Engagement ham (aninda) is_tracking() sonucunu oldugu gibi iletir.

@dataclass
class CombatEvent:
    t: float
    kind: str ## "ates" | "pitbull" | "isabet" | "iska" | "kor" | "tukenme" | "hedefsiz"
    actor: str # Atan uçak ID
    target: str # Hedef uçak ID
    detail: dict = field(default_factory=dict)  # her ornek icin AYRI sozluk -- bkz. dataclass mutable default tuzagi

@dataclass
class AircraftEntry:
    id: str
    state: any
    radar: Radar
    loadout: Loadout
    alive: bool = True
    rwr: RWR = field(default_factory=RWR)  # YENI: Her uçağın bir RWR'ı var


@dataclass
class ActiveMissile:
    id: str
    missile: Missile
    shooter_id: str
    target_id: str
    was_pitbull: bool = False

def _extract_pos_vel(state) -> tuple[np.ndarray, np.ndarray]:
    """Durum nesnesinden 3D pozisyon [ft] ve hız [fps] vektörlerini çıkarır.
    Gercek FlightState sozlesmesi (radyan: psi_rad/gamma_rad/beta_rad/vt_fps)
    beklenir -- relative_geometry()'nin (Faz 1.1) kullandigi AYNI sozlesme."""
    if hasattr(state, "pos_ft") and hasattr(state, "vel_fps"):
        return np.array(state.pos_ft, dtype=float), np.array(state.vel_fps, dtype=float)

    pos = np.array([state.north_ft, state.east_ft, state.alt_ft], dtype=float)
    gamma_rad = getattr(state, "gamma_rad", 0.0)
    track_rad = getattr(state, "psi_rad", 0.0) + getattr(state, "beta_rad", 0.0)
    v = getattr(state, "vt_fps", 900.0)
    vel = np.array([
        v * math.cos(gamma_rad) * math.cos(track_rad),
        v * math.cos(gamma_rad) * math.sin(track_rad),
        v * math.sin(gamma_rad)
    ], dtype=float)
    return pos, vel

class Engagement:
    def __init__(
        self,
        rules: LaunchRules | None = None,
        missile_cfg: MissileConfig | None = None,
        missile_substeps: int = 5,
    ):
        self.rules = rules or LaunchRules()
        self.missile_cfg = missile_cfg or MissileConfig()
        # OLCULDU (scripts/missile_dt_convergence.py): 6g manevra yapan bir
        # hedefe karsi marjinal bir angajmanda disari dt=0.1 (10 Hz) ile
        # sonuc (isabet/iska) dt=0.02-0.002 araligindakinden FARKLI cikabiliyor
        # (dt=0.05'te temiz bir iska, hem daha ince hem daha kaba dt'lerde
        # isabet -- monoton degil). Bu yuzden fuze fizigi disaridaki 10 Hz
        # muhasebe adimindan bagimsiz, kendi icinde N alt-adimla (varsayilan
        # 5 -> 50 Hz) kosuyor. Radar/muhasebe mantigi buna ihtiyac duymuyor
        # (zaman sabitleri saniyeler mertebesinde), sadece fuze.
        self.missile_substeps = max(1, missile_substeps)
        self.aircraft: dict[str, AircraftEntry] = {}
        self.missiles: list[ActiveMissile] = []
        self.events: list[CombatEvent] = []
        self.sim_time: float = 0.0
        self._missile_counter: int = 0

    def add_aircraft(self, id: str, state, radar: Radar, loadout: Loadout | None = None) -> None:
        """Uçağı angajman yöneticisine kaydeder."""
        is_alive = getattr(state, "alive", True)
        self.aircraft[id] = AircraftEntry(
            id=id,
            state=state,
            radar=radar,
            loadout=loadout or Loadout(),
            alive=is_alive
        )

    def can_fire(self, shooter: str, target: str) -> tuple[bool, str]:
        """
        Ateşleme yetki kontrolü (Hiyerarşi: Mühimmat -> Doygunluk -> Menzil -> Kilit).
        """
        if shooter not in self.aircraft:
            return False, "atan ucak yok"
        if target not in self.aircraft:
            return False, "hedef yok"

        s_entry = self.aircraft[shooter]
        t_entry = self.aircraft[target]

        if not s_entry.alive:
            return False, "atan ucak imha"
        if not t_entry.alive:
            return False, "hedef zaten imha"

        # 1. Mühimmat Kontrolü
        if s_entry.loadout.amraam <= 0:
            return False, "muhimmat"

        # 2. Hedef Doygunluğu (Aynı hedefe eşzamanlı uçan füze sayısı)
        active_on_target = sum(
            1 for m in self.missiles
            if m.shooter_id == shooter and m.target_id == target and m.missile.alive
        )
        if active_on_target >= self.rules.max_per_target:
            return False, "hedef doygun"

        # 3. Menzil Kontrolü
        geom = relative_geometry(s_entry.state, t_entry.state)
        if geom.range_nm > self.rules.max_launch_nm:
            return False, "menzil"

        # 4. Radar Kilit Kontrolü
        if self.rules.require_track and not s_entry.radar.is_tracking(target):
            return False, "kilit yok"

        return True, "ok"

    def fire(self, shooter: str, target: str) -> bool:
        """Ateşleme kuralları sağlanıyorsa füzeyi fırlatır."""
        allowed, _ = self.can_fire(shooter, target)
        if not allowed:
            return False

        s_entry = self.aircraft[shooter]
        t_entry = self.aircraft[target]

        # Envanter ve ağırlık düşüşü (335 lb/füze)
        s_entry.loadout.amraam -= 1
        for mass_attr in ("mass_lb", "weight_lb"):
            if hasattr(s_entry.state, mass_attr):
                setattr(s_entry.state, mass_attr, getattr(s_entry.state, mass_attr) - self.missile_cfg.mass_lb)
                break

        # Füze oluşturma -- Missile radyan-tabanlı gerçek FlightState (psi_rad/vt_fps
        # vb.) sözleşmesi bekler; uçak durumu derece-tabanlı bir mock ise
        # (test_engagement.py'de olduğu gibi) doğrudan verilirse AttributeError
        # patlar. _extract_pos_vel zaten iki sözleşmeyi de doğru ayırt ediyor
        # (asağıdaki füze güncelleme döngüsünde de kullanılıyor) -- onu kullanıp
        # Missile'ın doğrudan kabul ettiği pos_ft/vel_fps sözleşmesine çeviriyoruz.
        self._missile_counter += 1
        msl_id = f"msl_{shooter}_{self._missile_counter}"
        launch_pos, launch_vel = _extract_pos_vel(s_entry.state)
        launch_state = SimpleNamespace(pos_ft=launch_pos, vel_fps=launch_vel)
        missile = Missile(self.missile_cfg, launch_state, target_id=target)

        active_msl = ActiveMissile(
            id=msl_id,
            missile=missile,
            shooter_id=shooter,
            target_id=target
        )
        self.missiles.append(active_msl)

        geom = relative_geometry(s_entry.state, t_entry.state)
        event = CombatEvent(
            t=self.sim_time,
            kind="ates",
            actor=shooter,
            target=target,
            detail={"range_nm": geom.range_nm, "missile_id": msl_id}
        )
        self.events.append(event)
        return True

    def update(self, dt: float, states: dict[str, any]) -> list[CombatEvent]:
        """Simülasyonu bir adım ilerletir ve oluşan olayları döndürür."""
        self.sim_time += dt
        step_events: list[CombatEvent] = []

        # 1. Uçak durumlarını güncelle -- fuze alt-adim enterpolasyonu icin
        # ESKI (bu tikten once gecerli) pos/vel'i once sakla.
        prev_pos_vel: dict[str, tuple[np.ndarray, np.ndarray]] = {
            ac_id: _extract_pos_vel(entry.state) for ac_id, entry in self.aircraft.items()
        }

        for ac_id, new_state in states.items():
            if ac_id in self.aircraft:
                self.aircraft[ac_id].state = new_state

        # 2. Radarları ve RWR'ları (Arama/Kilit) güncelle
        # Önce radarları hesapla, sonuçları biriktir.
        radar_results = {}
        for s_id, s_entry in self.aircraft.items():
            if not s_entry.alive:  continue

            for t_id, t_entry in self.aircraft.items():
                if s_id == t_id or not t_entry.alive:
                    continue
                geom = relative_geometry(s_entry.state, t_entry.state)
                radar_contact = s_entry.radar.update(dt, t_id, geom)

                # 's_id', 't_id'yi nasıl görüyor kaydet
                radar_results[(s_id, t_id)] = radar_contact

        # Şimdi bu sonuçları TERSİNDEN okuyup t_id'nin RWR'ına beslemeliyiz
        for target_id, t_entry in self.aircraft.items():
            if not t_entry.alive: continue
            
            for shooter_id, s_entry in self.aircraft.items():
                if target_id == shooter_id or not s_entry.alive: continue
                
                contact = radar_results.get((shooter_id, target_id))
                if contact is None:
                    continue
                # Uc asamali zincirin RWR'a giren ilk iki basamagi:
                # tracked -> "kilit", (detected ama henuz tracked degil) -> "arama".
                # Ikisi de yoksa (gimbal/menzil/notch nedeniyle hic enerji
                # donmuyor) hicbir sey beslenmez -- bkz. RWR-Hata-3.
                if contact.tracked:
                    kind = "kilit"
                elif contact.detected:
                    kind = "arama"
                else:
                    continue

                # Bize (t_entry) shooter'ın kerterizi lazım.
                # Bunu bulmak için 't_entry'den 's_entry'ye çizilen geometriyi kullanıyoruz
                geom_reverse = relative_geometry(t_entry.state, s_entry.state)

                t_entry.rwr.feed_signal(
                    emitter_id=shooter_id,
                    kind=kind,
                    bearing_deg=geom_reverse.ata_deg
                )

        # 3. Aktif füzeleri güncelle
        for m in self.missiles:
            if not m.missile.alive:
                continue

            s_entry = self.aircraft.get(m.shooter_id)
            t_entry = self.aircraft.get(m.target_id)

            if not t_entry:
                continue

            if not t_entry.alive:
                # Hedef ZATEN imha (baska bir fuze onceki bir tikte dusurmus
                # olabilir) -- fuzenin gudecegi bir sey kalmadi. "isabet"
                # YAZILMAZ: tek ucak icin tek imha sayilir, yoksa ust katman
                # (taktik komutan) ayni hedefe fazladan fuze atarak odul
                # toplamayi ogrenebilir. Fizik de bunu soyluyor: hedef
                # patladiysa enkazin icinden gecer.
                m.missile.alive = False
                m.missile.result = "hedefsiz"
                ev = CombatEvent(t=self.sim_time, kind="hedefsiz", actor=m.shooter_id, target=m.target_id)
                self.events.append(ev)
                step_events.append(ev)
                continue

            t_pos_new, t_vel_new = _extract_pos_vel(t_entry.state)
            t_pos_old, t_vel_old = prev_pos_vel.get(m.target_id, (t_pos_new, t_vel_new))

            # Datalink kontrolü -- ANLIK durum, hiç yumuşatmadan. Hafıza/tolerans
            # (MSL-06) zaten Missile'ın İÇİNDE (MissileConfig.datalink_memory_s);
            # burada ikinci bir sayaç tutulursa toleranslar üst üste biner.
            # Radar zaman sabitleri (coast_s, lock_delay_s) saniyeler
            # mertebesinde -- bu tikte bir kez hesaplamak yeterli, alt-adımlar
            # arasında değişmez.
            shooter_tracking = (
                s_entry is not None and
                s_entry.alive and
                s_entry.radar.is_tracking(m.target_id)
            )

            # Füze fiziğini dış (10 Hz) muhasebe adımından bağımsız, N
            # alt-adımla (varsayılan 50 Hz) koştur -- bkz. __init__ notu.
            # Hedefin konum/hızı iki tik arasında DOĞRUSAL değişiyor
            # varsayımıyla enterpole edilir (MSL-08'in kendi CPA hesabındaki
            # varsayımla aynı, sadece bir seviye yukarıda uygulanmış hali).
            n = self.missile_substeps
            dt_sub = dt / n
            state = None
            for i in range(n):
                if not m.missile.alive:
                    break
                frac = i / n
                t_pos_i = t_pos_old + (t_pos_new - t_pos_old) * frac
                t_vel_i = t_vel_old + (t_vel_new - t_vel_old) * frac
                state = m.missile.update(dt_sub, t_pos_i, t_vel_i, datalink_ok=shooter_tracking)

            # YENİ: Pitbull olmuş füzenin RWR'a (Level 2) beslenmesi
            if state.phase == "pitbull":
                # Fuzenin arayici konisinde miyiz?
                m_pos, m_vel = state.pos_ft, state.vel_fps
                t_pos, _ = _extract_pos_vel(t_entry.state)
                
                # Adim 0'da disari aldigımız fonksiyonu kullanıyoruz çünkü fuze kendi konisini (seeker_fov_deg) biliyor.
                boresight_ang = off_boresight_deg(m_vel, m_pos, t_pos)
                
                if boresight_ang <= self.missile_cfg.seeker_fov_deg:
                    # Füze bizi görüyor. Bize füzeye bakan açı lazım.
                    # 1. Uçaktan füzeye doğru LOS (Line of Sight) vektörü
                    r_vec = m_pos - t_pos 
                    r_mag = float(np.linalg.norm(r_vec))
                    
                    if r_mag > 1e-3:
                        u_los = r_vec / r_mag
                    else:
                        u_los = np.array([1.0, 0.0, 0.0])

                    # 2. Uçağın kendi gidiş (burun) vektörü
                    # t_vel_new: Bu tick'in başındaki hedef uçağın hız vektörü 
                    # (Engagement'ın üst kısımlarında _extract_pos_vel ile zaten çekilmişti)
                    v_mag = float(np.linalg.norm(t_vel_new))
                    if v_mag > 1e-3:
                        u_hdg = t_vel_new / v_mag
                    else:
                        u_hdg = np.array([1.0, 0.0, 0.0])

                    # 3. İki vektör arasındaki açı (Dot Product)
                    cos_beta = float(np.dot(u_hdg, u_los))
                    cos_beta = max(-1.0, min(1.0, cos_beta)) # Hata önleme (Clamping)
                    bearing_to_msl_deg = math.degrees(math.acos(cos_beta))

                    # 4. Yön (Sağ/Sol) İşareti (Cross Product)
                    # Sadece X-Y (Kuzey-Doğu) düzlemindeki iz düşümüne göre sağ/sol kararı veriyoruz
                    # (Z ekseni irtifa, RWR genelde 2D çalışır)
                    cross_z = u_hdg[0] * u_los[1] - u_hdg[1] * u_los[0]
                    if cross_z < 0:
                        bearing_to_msl_deg = -bearing_to_msl_deg

                    # 5. RWR'a Sinyali Gönder
                    t_entry.rwr.feed_signal(
                        emitter_id=m.id,  # Füzenin ID'si (Örn: "msl_red_1")
                        kind="fuze",      # Level 2 tehdit
                        bearing_deg=bearing_to_msl_deg
                    )


            # Pitbull geçiş olayı
            if state.phase == "pitbull" and not m.was_pitbull:
                m.was_pitbull = True
                ev = CombatEvent(t=self.sim_time, kind="pitbull", actor=m.shooter_id, target=m.target_id)
                self.events.append(ev)
                step_events.append(ev)

            # Sonlanma olayları
            if not state.alive:
                ev = CombatEvent(
                    t=self.sim_time,
                    kind=state.result,
                    actor=m.shooter_id,
                    target=m.target_id,
                    detail={"time_of_flight": state.t_since_launch}
                )
                self.events.append(ev)
                step_events.append(ev)

                if state.result == "isabet":
                    t_entry.alive = False
                    if hasattr(t_entry.state, "alive"):
                        t_entry.state.alive = False

        # 4. RWR Zamanlayıcılarını güncelle
        for entry in self.aircraft.values():
            if entry.alive:
                entry.rwr.update(dt)

        return step_events