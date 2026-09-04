"""
Egitim giris noktasi: TEK bir YAML konfigurasyonu alir.

    python scripts/train.py configs/guidance_shield.yaml

Kaynak kodda ayar yoktur; kosu dizinine cozumlenmis konfigurasyon yazilir,
boylece bir kosunun hangi ayarlarla uretildigi kalici olarak izlenebilir.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bvr.config import load_experiment
from bvr.agents.train_guidance import train_from_config

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--steps", type=int, default=None, help="YAML'i gecersiz kil")
    ap.add_argument("--resume", type=str, default=None)
    ap.add_argument("--save-buffer", action="store_true",
                    help="replay buffer'i da kaydet (gercek resume icin)")
    a = ap.parse_args()
    cfg = load_experiment(a.config)
    if a.steps:
        cfg.sac.total_steps = a.steps
    print(f"[{cfg.name}] {cfg.notes.strip()}")
    train_from_config(cfg, resume=a.resume, save_buffer=a.save_buffer)
