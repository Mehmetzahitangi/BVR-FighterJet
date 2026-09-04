"""
ADIM 1c: IC DONGU KABUL TESTI (basamak yaniti).

Klasik kontrol tarafinin kabul kriteri budur; RL'e gecmeden once bu testin
gecmesi gerekir. Olculen metrikler:

  - yukselme zamani (t_r)  : hedefin %90'ina ilk varis
  - asim (overshoot)       : hedefi asma yuzdesi
  - oturma zamani (t_s)    : +-%5 bandina girip kalma
  - kalici hata (ess)      : sonda kalan hata
  - CAPRAZ ETKI            : donuste irtifa kaybi, tirmanista hiz kaybi

KABUL KRITERLERI (ic dongu icin makul otopilot standardi):
  roll  : asim < %20, t_r < 2.5 s, |ess| < 2 deg
  gamma : asim < %25, t_r < 4.0 s, |ess| < 1 deg
  mach  : |ess| < 0.02  (yavas kanal, t_r serbest)
  donus : 45 derece bankta 20 s'de |dAlt| < 500 ft
  YATIK ALCALMA  : 55 deg bank + gamma -8 deg iken gerceklesen nz > -3.0 g
  ANI TERS DONUS : 70 deg bankta gamma +10 -> -20 basamagi, nz > -3.0 g

NEDEN "YATIK ALCALMA" GRUBU SONRADAN EKLENDI
Ilk 16 test kanat DUZ (ya da bank var ama gamma=0) yapilmisti. Guidance
katmani dondurulduktan sonra olculdu ki zarf ihlallerinin buyuk cogunlugu
ucak DONERKEN AYNI ANDA ALCALIRKEN olusuyor (alcalma 4.3x, yatis+alcalma
3.5x zenginlesme). Yani en cok ihlal ureten calisma noktasi hic
sinanmamisti -- gercek bir dogrulama bosluguydu.

Mekanizma kinematikte acik:  n = (V*gamma_dot/g + cos gamma) / cos(phi)
1/cos(phi) carpani 55 derecede komutu 1.74 kat buyutur; alcalma komutu
zaten negatif tarafa gidiyorsa yatiklik negatif g'yi DERINLESTIRIR.

Grup 5 eklendi ve GECTI (en kotu -2.35 g). Ama ortamda sakin havada
-3.76 g olculmustu -- yani SABIT yatik alcalma sorunu uretmiyor. Fark:
ortamda dis dongu 10 Hz'de komut yeniliyor ve slew siniri gamma komutunun
0.1 saniyede 15 derece degismesine izin veriyor. Bu yuzden Grup 6 (ANI
TERS DONUS) eklendi: gercek ariza noktasi SABIT durum degil, GECICIDIR.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bvr.sim.jsbsim_bridge import F16Sim
from bvr.control.inner_loop import InnerLoop, InnerLoopCommand, InnerLoopGains
from bvr.sim import aircraft as ac

CTRL_HZ = 60.0


def make(alt_ft, mach, gains=None):
    sim = F16Sim()
    sim.reset(alt_ft=alt_ft, mach=mach, trim=True)
    il = InnerLoop(dt=1.0 / CTRL_HZ, gains=gains)
    il.reset(trim_throttle=sim["fcs/throttle-cmd-norm"])
    return sim, il


def roll_sim(sim, il, cmd_fn, dur_s):
    """Kontrol dongusunu 60 Hz, FDM'i 120 Hz calistir."""
    sub = int(round(sim.fdm_hz / CTRL_HZ))
    n = int(dur_s * CTRL_HZ)
    log = []
    st = sim.state()
    for k in range(n):
        t = k / CTRL_HZ
        cmd = cmd_fn(t)
        el, ail, thr, rud = il.update(st, cmd)
        sim.send_fcs(el, ail, thr, rud)
        st = sim.run(sub)
        log.append((t, st.alt_ft, np.degrees(st.phi_rad), np.degrees(st.gamma_rad),
                    st.mach, np.degrees(st.alpha_rad), np.degrees(st.beta_rad),
                    -st.nz, el, ail, thr))
    return np.array(log)


def step_metrics(t, y, y0, y_target, tol_frac=0.05):
    """Basamak yaniti metrikleri."""
    span = y_target - y0
    if abs(span) < 1e-9:
        return dict(tr=np.nan, os=np.nan, ts=np.nan, ess=y[-1] - y_target)
    # yukselme zamani: %90
    thr90 = y0 + 0.9 * span
    tr = np.nan
    for i in range(len(y)):
        if (span > 0 and y[i] >= thr90) or (span < 0 and y[i] <= thr90):
            tr = t[i]
            break
    # asim
    peak = y.max() if span > 0 else y.min()
    os_pct = (peak - y_target) / span * 100.0
    os_pct = max(os_pct, 0.0)
    # oturma zamani: +-%5 bandina girip cikmama
    band = abs(span) * tol_frac
    ts = np.nan
    for i in range(len(y)):
        if np.all(np.abs(y[i:] - y_target) <= band):
            ts = t[i]
            break
    return dict(tr=tr, os=os_pct, ts=ts, ess=y[-1] - y_target)


def run_all(gains=None, verbose=True):
    COND = [(15000, 0.7), (25000, 0.85), (35000, 1.0), (45000, 1.3)]
    results = {"roll": [], "gamma": [], "mach": [], "turn": [],
               "banked_descent": [], "reversal": []}

    # ---------- 1) ROLL basamagi: 0 -> 45 deg ----------
    if verbose:
        print("=" * 74)
        print("1) ROLL BASAMAGI  phi: 0 -> 45 deg   (kriter: OS<20%, tr<2.5s, |ess|<2)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'tr s':>7} {'OS %':>7} {'ts s':>7} {'ess d':>7} {'PASS':>5}")
    for alt, m in COND:
        sim, il = make(alt, m, gains)
        log = roll_sim(sim, il, lambda t: InnerLoopCommand(np.radians(45.0), 0.0, m), 12.0)
        mt = step_metrics(log[:, 0], log[:, 2], 0.0, 45.0)
        ok = (mt["os"] < 20) and (mt["tr"] < 2.5) and (abs(mt["ess"]) < 2.0)
        results["roll"].append((alt, m, mt, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {mt['tr']:7.2f} {mt['os']:7.1f} {mt['ts']:7.2f} "
                  f"{mt['ess']:7.2f} {'OK' if ok else 'FAIL':>5}")

    # ---------- 2) GAMMA basamagi: 0 -> +8 deg ----------
    if verbose:
        print()
        print("=" * 74)
        print("2) GAMMA BASAMAGI  gamma: 0 -> +8 deg  (kriter: OS<25%, tr<4s, |ess|<1)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'tr s':>7} {'OS %':>7} {'ts s':>7} {'ess d':>7} "
              f"{'a_max':>6} {'PASS':>5}")
    for alt, m in COND:
        sim, il = make(alt, m, gains)
        log = roll_sim(sim, il, lambda t: InnerLoopCommand(0.0, np.radians(8.0), m), 20.0)
        mt = step_metrics(log[:, 0], log[:, 3], 0.0, 8.0)
        amax = log[:, 5].max()
        ok = (mt["os"] < 25) and (mt["tr"] < 4.0) and (abs(mt["ess"]) < 1.0)
        results["gamma"].append((alt, m, mt, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {mt['tr']:7.2f} {mt['os']:7.1f} {mt['ts']:7.2f} "
                  f"{mt['ess']:7.2f} {amax:6.2f} {'OK' if ok else 'FAIL':>5}")

    # ---------- 3) MACH basamagi: M -> M+0.15 ----------
    if verbose:
        print()
        print("=" * 74)
        print("3) MACH BASAMAGI  M -> M+0.15  (kriter: |ess|<0.02, yavas kanal)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'tr s':>7} {'OS %':>7} {'ess':>8} {'thr_end':>8} {'PASS':>5}")
    for alt, m in COND:
        sim, il = make(alt, m, gains)
        tgt = m + 0.15
        log = roll_sim(sim, il, lambda t: InnerLoopCommand(0.0, 0.0, tgt), 45.0)
        mt = step_metrics(log[:, 0], log[:, 4], m, tgt)
        ok = abs(mt["ess"]) < 0.02
        results["mach"].append((alt, m, mt, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {mt['tr']:7.2f} {mt['os']:7.1f} {mt['ess']:8.4f} "
                  f"{log[-1, 10]:8.3f} {'OK' if ok else 'FAIL':>5}")

    # ---------- 4) KOORDINELI DONUS: 45 deg bank, gamma=0 ----------
    if verbose:
        print()
        print("=" * 74)
        print("4) KOORDINELI DONUS  45 deg bank, gamma=0, 20 s")
        print("   (kriter: |dAlt|<500 ft -- yatis telafisi 1/cos(phi) calisiyor mu?)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'dAlt ft':>9} {'n_ort':>7} {'|beta|max':>10} "
              f"{'dM':>7} {'PASS':>5}")
    for alt, m in COND:
        sim, il = make(alt, m, gains)
        log = roll_sim(sim, il, lambda t: InnerLoopCommand(np.radians(45.0), 0.0, m), 20.0)
        settle = log[:, 0] > 6.0          # bank oturduktan sonrasi
        d_alt = log[-1, 1] - log[settle][0, 1]
        n_mean = log[settle][:, 7].mean()
        beta_max = np.abs(log[:, 6]).max()
        d_m = log[-1, 4] - m
        ok = abs(d_alt) < 500
        results["turn"].append((alt, m, d_alt, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {d_alt:9.0f} {n_mean:7.3f} {beta_max:10.2f} "
                  f"{d_m:7.3f} {'OK' if ok else 'FAIL':>5}")

    # Gruplar 5-6 icin GENISLETILMIS sart listesi. Ortam 10-42 kft ve
    # M 0.55-1.35 arasinda calisiyor; ilk dort sart bu zarfin ALT KOSESINI
    # (alcak irtifa + dusuk hiz) kapsamiyordu. Zarf ihlalleri orada
    # yogunlasiyor olabilir, o yuzden iki sart daha eklendi.
    COND_ENV = [(10000, 0.60), (12000, 0.75)] + COND

    # ---------- 5) YATIK ALCALMA: 55 deg bank + gamma -8 deg ----------
    # En cok zarf ihlali ureten calisma noktasi. Kriter, isletme
    # bariyerinin KENDISIDIR: gerceklesen nz, -3.0 g'nin altina inmemeli.
    # Bu testler SAKIN havada kosar (turbulans yok), yani olculen asim
    # tamamen ic dongu dinamiginden gelir -- ruzgar katkisi ayridir.
    if verbose:
        print()
        print("=" * 74)
        print("5) YATIK ALCALMA  phi=55 deg + gamma=-8 deg, 20 s   [SAKIN HAVA]")
        print(f"   (kriter: gerceklesen nz > {ac.NZ_MIN:.1f} g -- isletme bariyeri)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'nz_min':>8} {'nz_ort':>8} {'gam_ess':>8} "
              f"{'a_max':>6} {'PASS':>5}")
    for alt, m in COND_ENV:
        sim, il = make(alt, m, gains)
        log = roll_sim(sim, il, lambda t: InnerLoopCommand(
            np.radians(55.0), np.radians(-8.0), m), 20.0)
        settle = log[:, 0] > 6.0                  # bank ve gamma oturduktan sonra
        nz_min = log[:, 7].min()
        nz_mean = log[settle][:, 7].mean()
        gam_ess = log[-1, 3] - (-8.0)
        amax = log[:, 5].max()
        ok = nz_min > ac.NZ_MIN
        results["banked_descent"].append((alt, m, nz_min, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {nz_min:8.3f} {nz_mean:8.3f} {gam_ess:8.2f} "
                  f"{amax:6.2f} {'OK' if ok else 'FAIL':>5}")

    # ---------- 6) ANI TERS DONUS: 70 deg bankta gamma +10 -> -20 ----------
    # Grup 5 sabit yatik alcalmayi sinar ve GECER. Ortamda olculen derin
    # negatif g ise GECICI: dis dongu 10 Hz'de komut yeniler ve slew siniri
    # gamma komutunun adim basina ~15 derece degismesine izin verir. Bu test
    # o gecici durumu yeniden uretir -- once tirmanis, sonra ani alcalma,
    # hepsi yuksek bankta.
    if verbose:
        print()
        print("=" * 74)
        print("6) ANI TERS DONUS  phi=70 deg, gamma +10 -> -20 (t=8 s)   [SAKIN HAVA]")
        print(f"   (kriter: gerceklesen nz > {ac.NZ_MIN:.1f} g)")
        print("=" * 74)
        print(f"{'alt':>6} {'M':>5} {'nz_min':>8} {'t_dip s':>8} {'gam_ess':>8} "
              f"{'a_max':>6} {'PASS':>5}")

    def _reversal(t, m):
        phi = np.radians(70.0)
        gam = np.radians(10.0) if t < 8.0 else np.radians(-20.0)
        return InnerLoopCommand(phi, gam, m)

    for alt, m in COND_ENV:
        sim, il = make(alt, m, gains)
        log = roll_sim(sim, il, lambda t: _reversal(t, m), 20.0)
        after = log[:, 0] >= 8.0
        nz_min = log[after][:, 7].min()
        t_dip = log[after][np.argmin(log[after][:, 7]), 0]
        gam_ess = log[-1, 3] - (-20.0)
        amax = log[:, 5].max()
        ok = nz_min > ac.NZ_MIN
        results["reversal"].append((alt, m, nz_min, ok))
        if verbose:
            print(f"{alt:6d} {m:5.2f} {nz_min:8.3f} {t_dip:8.2f} {gam_ess:8.2f} "
                  f"{amax:6.2f} {'OK' if ok else 'FAIL':>5}")

    n_ok = sum(1 for k in results for *_, ok in results[k] if ok)
    n_tot = sum(len(v) for v in results.values())
    if verbose:
        print()
        print(f"TOPLAM: {n_ok}/{n_tot} test gecti")
    return results, n_ok, n_tot


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.parse_args()
    run_all()
