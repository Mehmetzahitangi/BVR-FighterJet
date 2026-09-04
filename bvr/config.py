"""
DENEY KONFIGURASYONU: her kosu bir YAML dosyasi.

=============================================================================
NEDEN
=============================================================================
Bu proje bir noktada 9 egitim kosusuna ulasti ve konfigurasyonlar komut
satiri bayraklariyla + kaynak kodda elle yapilan degisikliklerle
belirleniyordu. Sonuc: bir kosunun HANGI ayarlarla uretildigi kodun o
andaki haline bagliydi ve geri izlenemiyordu. Ayrica `model_best.pkl`
her karsilastirmada uzerine yaziliyordu -- yani bir politikanin hangi
modele karsi egitildigi zamanla degisebiliyordu.

Bu modul iki seyi garanti eder:
  1. Her kosu TEK bir YAML ile tanimlanir; kaynak kodda ayar yoktur.
  2. Kosu dizinine COZUMLENMIS (resolved) konfigurasyon yazilir -- yani
     varsayilanlar dahil, o kosunun TAM ayarlari kalici olarak saklanir.

Kullanim:
    cfg = load_experiment("configs/guidance_final.yaml")
    cfg.save(run_dir)
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import yaml

from .envs.guidance_env import GuidanceConfig


@dataclass
class SACConfig:
    """SB3 SAC hiperparametreleri."""
    total_steps: int = 1_000_000
    n_envs: int = 12
    seed: int = 0
    gamma: float = 0.995
    learning_rate: float = 3e-4
    batch_size: int = 512
    buffer_size: int = 1_000_000
    learning_starts: int = 10_000
    tau: float = 0.005
    net_arch: List[int] = field(default_factory=lambda: [256, 256])
    ent_coef: str = "auto"
    device: str = "auto"
    #: Kabul kriterine gore en iyi modeli saklayan degerlendirmenin sikligi.
    #: Kucuk deger = daha ince secim ama daha cok simulasyon maliyeti.
    #: 12 bolum x 1800 adim ~ 20 s; 250k'da bir -> 8M kosuda ~11 dk toplam.
    eval_every: int = 250_000
    eval_n_ep: int = 12


@dataclass
class ExperimentConfig:
    """Bir egitim kosusunun TAM tanimi."""
    name: str = "unnamed"
    notes: str = ""
    env: GuidanceConfig = field(default_factory=GuidanceConfig)
    sac: SACConfig = field(default_factory=SACConfig)

    # ---------------------------------------------------------------
    @property
    def run_dir(self) -> str:
        return os.path.join("runs", self.name)

    def save(self, path: Optional[str] = None) -> str:
        """Cozumlenmis konfigurasyonu kosu dizinine yaz."""
        d = path or self.run_dir
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "config.resolved.yaml")
        with open(out, "w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(self), f, allow_unicode=True, sort_keys=False)
        return out


def _apply(dc: Any, patch: Dict[str, Any], where: str) -> Any:
    """Sozlukteki alanlari dataclass uzerine uygula; BILINMEYEN ALANDA HATA VER.

    Sessizce yok saymak, yazim hatasi yapilan bir ayarin fark edilmeden
    varsayilan degerle calismasina yol acar -- deney sonuclarini sessizce
    gecersiz kilan turden bir hata. Bu yuzden bilinmeyen anahtar hatadir.
    """
    if patch is None:
        return dc
    valid = {f.name for f in dataclasses.fields(dc)}
    unknown = set(patch) - valid
    if unknown:
        raise KeyError(f"{where}: bilinmeyen ayar(lar) {sorted(unknown)}. "
                       f"Gecerli alanlar: {sorted(valid)}")
    for k, v in patch.items():
        cur = getattr(dc, k)
        # YAML listeleri tuple alanlara cevrilir (orn. shield_horizons)
        if isinstance(cur, tuple) and isinstance(v, list):
            v = tuple(v)
        setattr(dc, k, v)
    return dc


def load_experiment(path: str) -> ExperimentConfig:
    """YAML -> ExperimentConfig (varsayilanlarin uzerine uygulanir)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = ExperimentConfig()
    top = {k: v for k, v in raw.items() if k not in ("env", "sac")}
    _apply(cfg, top, path)
    _apply(cfg.env, raw.get("env"), f"{path}:env")
    _apply(cfg.sac, raw.get("sac"), f"{path}:sac")
    if cfg.name == "unnamed":
        cfg.name = os.path.splitext(os.path.basename(path))[0]
    return cfg
