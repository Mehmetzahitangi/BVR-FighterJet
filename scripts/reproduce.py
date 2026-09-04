"""
TUM SONUCLARI SIFIRDAN URET.

    python scripts/reproduce.py            # tam boru hatti
    python scripts/reproduce.py --from 3   # 3. adimdan devam
    python scripts/reproduce.py --list     # adimlari listele

Amac: reponun "bende calisiyordu" durumundan cikmasi. Her adim kendi
ciktisini `data/` veya `runs/` altina yazar ve bir sonraki adim onu okur;
adimlar tek tek de calistirilabilir.

Uzun adimlar (egitim) saatler surer; --skip-training ile yalnizca veri +
model + degerlendirme kismi kosturulabilir.
"""
import sys
import os
import time
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PY = sys.executable

STEPS = [
    # (isim, komut, uretilen dosya(lar), egitim mi)
    ("Ic dongu kabul testi (16 test)",
     [PY, "scripts/test_inner_loop.py"], [], False),
    ("Sistem tanimlama verisi - egitim",
     [PY, "scripts/collect_sysid.py", "--episodes", "600",
      "--out", "data/sysid_train.npz"], ["data/sysid_train.npz"], False),
    ("Sistem tanimlama verisi - dogrulama",
     [PY, "scripts/collect_sysid.py", "--episodes", "200", "--seed0", "900000",
      "--out", "data/sysid_val.npz"], ["data/sysid_val.npz"], False),
    ("Model karsilastirmasi (DMD / EDMD / Deep-Koopman)",
     [PY, "scripts/compare_models.py"],
     ["runs/model_comparison.csv", "runs/model_comparison.png"], False),
    ("Guidance egitimi - kalkansiz taban",
     [PY, "scripts/train.py", "configs/guidance_noshield.yaml"],
     ["runs/guidance_noshield/sac_final.zip"], True),
    ("Guidance egitimi - CBF kalkanli",
     [PY, "scripts/train.py", "configs/guidance_shield.yaml"],
     ["runs/guidance_shield/sac_final.zip"], True),
    ("Guvenlik degerlendirmesi (100 bolum, %95 GA)",
     [PY, "scripts/safety_eval.py", "-n", "100"], [], False),
    ("Tacview demo kaydi",
     [PY, "scripts/demo_inner_loop.py"],
     ["runs/demo_inner_loop.acmi"], False),
]


def main(args):
    if args.list:
        for i, (name, _, out, tr) in enumerate(STEPS, 1):
            tag = " [EGITIM]" if tr else ""
            print(f"{i:2d}. {name}{tag}")
            for o in out:
                print(f"      -> {o}")
        return

    t_all = time.time()
    for i, (name, cmd, outs, is_train) in enumerate(STEPS, 1):
        if i < args.start:
            print(f"[{i}/{len(STEPS)}] ATLANDI: {name}")
            continue
        if is_train and args.skip_training:
            print(f"[{i}/{len(STEPS)}] ATLANDI (--skip-training): {name}")
            continue
        if outs and args.reuse and all(os.path.exists(o) for o in outs):
            print(f"[{i}/{len(STEPS)}] MEVCUT, yeniden uretilmiyor: {name}")
            continue

        print(f"\n{'='*70}\n[{i}/{len(STEPS)}] {name}\n{'='*70}", flush=True)
        t0 = time.time()
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"\nHATA: adim {i} basarisiz (kod {r.returncode}). Durduruluyor.")
            return 1
        print(f"[{i}] tamam ({time.time()-t0:.0f} s)")
    print(f"\nTUM BORU HATTI TAMAM ({(time.time()-t_all)/60:.1f} dk)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--skip-training", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="ciktisi zaten olan adimlari atla")
    sys.exit(main(ap.parse_args()) or 0)
