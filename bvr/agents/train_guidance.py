"""
DIS DONGU SAC EGITIMI (Stable-Baselines3).

=============================================================================
NEDEN KENDI SAC'IMIZI YAZMIYORUZ
=============================================================================
Bu projenin katkisi kademeli mimari + Koopman-CBF'dir; SAC uygulamasi
degildir. Elle yazilmis bir SAC'ta su hatalarin hepsi eski kodda vardi:
  - durumdan bagimsiz tek bir log_std  -> entropi cokmuyor
  - sabit alpha (otomatik sicaklik yok) -> kesif hic kapanmiyor
  - gradyan kirpma yok
  - odul normalizasyonu ile terminal ceza etkilesimi
SB3 bunlarin hepsini dogru yapar. Kazanilan zaman, asil katkiya harcanir.

=============================================================================
KRITIK HIPERPARAMETRE: GAMMA (indirim carpani)
=============================================================================
Bolum 1800 adim (180 s @ 10 Hz). Bir hedefe varmak ~30-60 s = 300-600 adim
surebilir. gamma=0.99 -> etkin ufuk ~100 adim (10 s): ajan hedefe varis
bonusunu neredeyse hic GORMEZ. gamma=0.995 -> ~200 adim (20 s).
Yogun "ilerleme" odulu kredi atamasini yerellestirdigi icin 0.995 yeterli;
yine de taranmasi gereken ilk parametre budur.

=============================================================================
KALKAN YOK
=============================================================================
Bu asamada CBF KAPALIDIR ve bu bilerek yapilmistir. Once RL + ic dongu +
zarf kirpmasi ile gorevin cozulebildigini gormemiz gerekir. Cozulemezse
kalkan eklemek sorunu cozmez, sadece teshisi imkansizlastirir -- eski
projenin basina gelen tam olarak buydu (uc zor bilesen ayni anda devreye
alindi, hangisinin bozuk oldugu hic ayristirilamadi).
"""
from __future__ import annotations

import os
from collections import deque, Counter
from typing import Optional

import numpy as np
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv

from ..envs.guidance_env import GuidanceEnv, GuidanceConfig


def make_env(rank: int, seed: int = 0, cfg: Optional[GuidanceConfig] = None):
    def _init():
        # TOHUM AYRISMASI: "seed + rank" kullanilirsa tohumlar arasi ortam
        # akislari BUYUK OLCUDE ORTAK olur (tohum 0 -> 0..11, tohum 1 -> 1..12;
        # 12 ortamin 11'i ayni). Uc kosuyu koşturmamizin TEK sebebi varyansi
        # durustce olcmek oldugu icin bu, varyansi OLDUGUNDAN AZ gosterir --
        # yani bizi olmamiz gerekenden emin yapar.
        # 100000 ofseti, sysid (0..599, 900000+) ve degerlendirme (10000+)
        # tohumlariyla cakismayi da onler: egitim ile test ayni bolumleri
        # gormemeli.
        env = GuidanceEnv(cfg=cfg or GuidanceConfig(), seed=100000 + seed * 1000 + rank)
        return Monitor(env, info_keywords=("is_success",))
    return _init


class GuidanceMetrics(BaseCallback):
    """Gorev metriklerini TensorBoard'a yazar.

    Odul egrisi tek basina yaniltici olabilir (ajan hedefe gitmeden
    irtifa/hiz bonusu toplayarak da odul biriktirebilir). Bu yuzden ASIL
    gorev metriklerini ayrica izleriz: bolum basina hedef sayisi, erken
    sonlanma sebepleri, basari orani.
    """

    #: Tani alani -> TensorBoard yolu. Gruplama onemli: TensorBoard'da ayni
    #: on eke sahip metrikler tek panelde toplanir, karsilastirmak kolaylasir.
    DIAG_MAP = {
        "alt_err_mean":       "izleme/irtifa_hatasi_ft",
        "mach_err_mean":      "izleme/mach_hatasi",
        "action_rate_rms":    "komut/degisim_rms",
        "alpha_max":          "zarf/alpha_max_deg",
        "beta_max":           "zarf/beta_max_deg",
        "nz_max":             "zarf/nz_max_g",
        "nz_min":             "zarf/nz_min_g",
        "mach_margin_min":    "zarf/mach_payi_bariyer",
        "stall_margin_min":   "zarf/stall_payi_gercek",
        "shield_mudahale_orani": "kalkan/mudahale_orani",
        "shield_slack_orani":    "kalkan/slack_orani",
        "shield_ort_sapma":      "kalkan/ortalama_sapma",
    }

    def __init__(self, window: int = 100, verbose: int = 0):
        super().__init__(verbose)
        self.wpts = deque(maxlen=window)
        self.success = deque(maxlen=window)
        self.terms = deque(maxlen=window)
        self.diag = {k: deque(maxlen=window) for k in self.DIAG_MAP}

    def _on_step(self) -> bool:
        ended = False
        for info in self.locals.get("infos", []):
            if "episode_waypoints" not in info:
                continue
            ended = True
            self.wpts.append(info["episode_waypoints"])
            self.success.append(info.get("is_success", 0.0))
            self.terms.append(info.get("termination", "timeout"))
            for k, v in info.get("diag", {}).items():
                if k in self.diag:
                    self.diag[k].append(v)

        # Kayit BOLUM BITISINE baglanir, sabit bir adim araligina degil.
        # Sebep: butun paralel ortamlar ayni anda baslayip ayni anda bittigi
        # icin bolumler senkron tamamlanir ve SB3 log'u tam o anda bosaltir.
        # Sabit aralikla kayit yapinca degerler bosaltmadan SONRA yazilip
        # hicbir zaman diske dusmuyordu (olculdu: 9 metrik yerine 21).
        if ended and self.wpts:
            self.logger.record("gorev/hedef_sayisi", float(np.mean(self.wpts)))
            self.logger.record("gorev/basari_orani", float(np.mean(self.success)))
            for k, path in self.DIAG_MAP.items():
                if self.diag[k]:
                    self.logger.record(path, float(np.mean(self.diag[k])))
            c = Counter(self.terms)
            n = max(len(self.terms), 1)
            for k in ("timeout", "hard_deck", "alpha", "beta", "nz",
                      "low_mach", "ceiling", "nan"):
                self.logger.record(f"sonlanma/{k}", c.get(k, 0) / n)
        return True



class BestByCaptureQuality(BaseCallback):
    """Kabul kriterine gore EN IYI modeli saklar.

    =========================================================================
    NEDEN GEREKLI -- PAHALIYA OGRENILEN DERS
    =========================================================================
    8M x 3 tohum nihai egitimde SON model alindi ve yakalama kalitesi
    2M'deki degerin ALTINA dustu:

        adim   s0     s1     s2     ortalama
        2M     0.541  0.571  0.507  0.540
        3M     0.560  0.479  0.239  0.426
        8M     0.245  0.457  0.246  0.316

    Sebep odul-kriter uyumsuzlugu: bolum getirisinin yalnizca %0.26'si
    varis KALITESINE bagli (hedef bonusu 16.8 puan / 2374, ustelik 10.6'si
    kosulsuz). ep_rew_mean 1.5M'de doyuyor; kalan 6.5M adim, kriteri
    kisitlamayan %99.7'lik yogun sekillendirmeyi optimize ediyor ve kalite
    suruklenip gidiyor.

    Odul duzeltilse bile SON modeli almak yanlistir: dogru olan, kabul
    kriterini periyodik olcup en iyisini saklamaktir. Bu callback tam
    olarak bunu yapar.

    Degerlendirme tohumlari 30000 blogundadir: egitim (100000+), rapor
    (10000/20000) ve sysid (0..599) bloklariyla cakismaz -- yani model
    secimi, raporlanan sayilarin uzerinde olcum kirlenmesi yaratmaz.
    """

    def __init__(self, cfg, every: int = 250_000, n_ep: int = 24,
                 save_path: str = ".", seed0: int = 30_000,
                 min_legs: int = 25, verbose: int = 0):
        super().__init__(verbose)
        self.cfg, self.every, self.n_ep = cfg, every, n_ep
        self.save_path, self.seed0 = save_path, seed0
        self.min_legs = min_legs
        self.best = -1.0
        self._next = every
        self.history = []

    def _quality(self):
        """(kalite, bacak sayisi) dondurur. Bacak sayisi KRITIKTIR --
        asagiya bak."""
        env = GuidanceEnv(cfg=self.cfg, seed=self.seed0)
        ok = tot = 0
        for ep in range(self.n_ep):
            obs, _ = env.reset(seed=self.seed0 + ep)
            done = False
            while not done:
                a, _ = self.model.predict(obs, deterministic=True)
                obs, _, term, trunc, info = env.step(a)
                if "waypoint" in info:
                    tot += 1
                    ok += int(info["waypoint"]["alt_ok"] and info["waypoint"]["mach_ok"])
                done = term or trunc
        env.close()
        return (ok / tot if tot else 0.0), tot

    def _on_step(self) -> bool:
        if self.num_timesteps < self._next:
            return True
        self._next += self.every
        q, n_legs = self._quality()
        self.history.append((int(self.num_timesteps), q, n_legs))
        self.logger.record("gorev/yakalama_kalitesi", q)
        self.logger.record("gorev/degerlendirme_bacak", float(n_legs))
        # KUCUK PAYDA TUZAGI (olculdu, bedeli odendi):
        # ilk surumde n_ep=12 ve payda korumasi yoktu. Egitimin basinda ajan
        # cok az hedefe variyor; 250k adimda oran 1/1 = 1.000 cikti ve
        # `sac_best.zip` orada DONDU -- 2M adimlik kosunun geri kalani
        # hicbir zaman "en iyi"yi guncelleyemedi. Oran metrikleri kucuk
        # paydada anlamsizdir; asgari bacak sayisi sarti olmadan
        # kullanilamazlar.
        if n_legs < self.min_legs:
            if self.verbose:
                print(f"[best] {self.num_timesteps} adim: yalnizca {n_legs} "
                      f"bacak (< {self.min_legs}) -- secim icin YETERSIZ, atlandi")
            return True
        if q > self.best:
            self.best = q
            path = os.path.join(self.save_path, "sac_best.zip")
            self.model.save(path)
            if self.verbose:
                print(f"[best] {self.num_timesteps} adim, kalite {q:.3f} -> {path}")
        return True


def train_from_config(cfg, resume=None, save_buffer=False):
    """ExperimentConfig ile egitim. Cozumlenmis konfigurasyon kosu dizinine yazilir."""
    import os
    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv

    s, e = cfg.sac, cfg.env
    models_dir = cfg.run_dir
    os.makedirs(models_dir, exist_ok=True)
    saved = cfg.save()
    print(f"[config] {saved}")

    venv_cls = SubprocVecEnv if s.n_envs > 1 else DummyVecEnv
    venv = venv_cls([make_env(i, s.seed, e) for i in range(s.n_envs)])

    if resume and os.path.exists(resume):
        print(f"[RESUME] {resume}")
        model = SAC.load(resume, env=venv, device=s.device)
    else:
        model = SAC(
            "MlpPolicy", venv,
            learning_rate=s.learning_rate, buffer_size=s.buffer_size,
            learning_starts=s.learning_starts, batch_size=s.batch_size,
            tau=s.tau, gamma=s.gamma,
            train_freq=(s.n_envs, "step"), gradient_steps=s.n_envs,
            ent_coef=s.ent_coef, target_entropy="auto",
            policy_kwargs=dict(net_arch=list(s.net_arch)),
            tensorboard_log=os.path.join("runs", "tb"),
            seed=s.seed, device=s.device, verbose=1,
        )

    # CheckpointCallback: SB3 .zip icinde aktor + iki kritik + hedef aglar +
    # log_ent_coef + optimizer durumlari birlikte saklanir; ayri ayri
    # kaydetmeye gerek yok. VecNormalize KULLANMIYORUZ (sabit olcekleme
    # karari), o yuzden kaydedilecek normalizasyon istatistigi de yok.
    #
    # save_replay_buffer=True: SAC off-policy oldugu icin GERCEK devam
    # ancak replay buffer ile mumkundur. Onsuz resume, bos tampondan
    # yeniden kesif demektir. ~1M gecis x 41 float ~ 165 MB.
    # REPLAY BUFFER EGITIM SIRASINDA KAYDEDILMEZ.
    # Olcum: her checkpoint'te buffer kaydedince s0 dizini 650k adimda
    # 1.6 GB'a ulasti (~264 MB x 6 kayit). 8M adim x 3 tohum ~ 60 GB ve
    # surekli disk I/O duraklamasi demekti. Model checkpoint'i 3.2 MB;
    # cokme durumunda ondan devam edilir (buffer yeniden dolar, bir miktar
    # ornek verimliligi kaybi olur ama dogruluk etkilenmez).
    # Buffer YALNIZCA egitim sonunda, istenirse bir kez yazilir.
    cbs = [GuidanceMetrics(),
           CheckpointCallback(save_freq=max(500_000 // s.n_envs, 1),
                              save_path=models_dir, name_prefix="sac"),
           BestByCaptureQuality(e, every=s.eval_every, n_ep=s.eval_n_ep,
                                save_path=models_dir, verbose=1)]
    model.learn(total_timesteps=s.total_steps, callback=cbs,
                tb_log_name=cfg.name, reset_num_timesteps=resume is None,
                progress_bar=False)
    final = os.path.join(models_dir, "sac_final.zip")
    model.save(final)
    if save_buffer:
        model.save_replay_buffer(os.path.join(models_dir, "replay_buffer.pkl"))
    venv.close()
    print(f"Kaydedildi: {final}")
    return final
