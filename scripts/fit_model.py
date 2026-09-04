"""
Dinamik modeli uydur ve dogrula.

Kullanim:
  python scripts/fit_model.py --model dmd
  python scripts/fit_model.py --model dmd --no-affine
"""
import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from bvr.models.dmd import DMDModel
from bvr.models.edmd import EDMDModel
from bvr.sysid.evaluate import load_dataset, report, select_ridge

REGISTRY = {
    "edmd": EDMDModel,
    "edmd_poly2": EDMDModel,
    "edmd_full": EDMDModel,
    "dmd": DMDModel,
}


LIBRARIES = {
    "edmd": "physics",
    "edmd_poly2": "poly2",
    "edmd_full": "physics+poly2",
}


def build(name, args):
    aff = not args.no_affine
    if name == "dmd":
        return lambda: DMDModel(affine=aff)
    if name in LIBRARIES:
        lib = LIBRARIES[name]
        return lambda: EDMDModel(library=lib, affine=aff)
    raise ValueError(name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dmd", choices=list(REGISTRY))
    ap.add_argument("--train", default="data/sysid_train.npz")
    ap.add_argument("--val", default="data/sysid_val.npz")
    ap.add_argument("--out", default=None)
    ap.add_argument("--ridge", type=float, default=None,
                    help="verilmezse dogrulama setinde secilir")
    ap.add_argument("--no-affine", action="store_true")
    args = ap.parse_args()

    train = load_dataset(args.train)
    val = load_dataset(args.val)
    print(f"egitim: {len(train['X']):,} gecis   dogrulama: {len(val['X']):,} gecis")
    print(f"dis dongu adimi dt = {train['dt']:.3f} s")
    print()

    factory = build(args.model, args)

    lam = args.ridge
    if lam is None:
        print("RIDGE SECIMI (dogrulama seti, 20 adim ufku)")
        lam = select_ridge(factory, train, val)
        print()

    t0 = time.time()
    model = factory()
    model.fit(train["X"], train["U"], train["Xn"], ridge=lam)
    print(f"fit suresi: {time.time()-t0:.2f} s")
    print()

    report(model, val)

    out = args.out or f"data/model_{args.model}.pkl"
    model.save(out)
    print()
    print(f"Model kaydedildi: {out}")

    # --- A matrisinin kararliligi (coklu adim yuvarlanmasi icin kritik) ---
    # Birim cember DISINDAKI ozdeger, uzun ufukta ustel patlama demektir.
    # |lambda| = 1 olan modlar BEKLENIR ve saglikli: irtifa, h_dot'un
    # integralidir (saf integrator -> lambda = 1); affine sabit terim de
    # tanim geregi 1'dir. Kritik esik bu yuzden 1 + kucuk tolerans.
    r = np.abs(np.linalg.eigvals(model.A))
    n_unstable = int((r > 1.0 + 1e-6).sum())
    n_marginal = int((np.abs(r - 1.0) <= 1e-6).sum())
    print()
    print("A matrisi ozdegerleri")
    print(f"  max |lambda|      = {r.max():.6f}")
    # Alarmci olmamak icin buyumeyi SAYIYLA ifade et: 1.0002 gibi bir
    # ozdeger 20 adimda %0.3 buyume demektir, pratikte zararsizdir.
    growth20 = r.max() ** 20
    print(f"  birim cember disi = {n_unstable}"
          f"   (20 adimda buyume carpani = {growth20:.4f})")
    print(f"  |lambda| = 1 (integrator/affine, beklenen) = {n_marginal}")
    print(f"  |lambda| ilk 6: {np.array2string(np.sort(r)[::-1][:6], precision=4)}")
