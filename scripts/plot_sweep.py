"""Tarama sonuclarini gorsellestir: metrik karsilastirmasi + ogrenme egrileri."""
import sys
import os
import re
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

# runs/sweep.log icindeki ozet tablosunu ayristir
ROW = re.compile(r"^(s\d_\w+)\s+([\d.]+)\s+(\d+)\s+\[\s*(\d+),\s*(\d+)\]\s+([\d.]+)\s+(\d+)")
rows = []
for line in open("runs/sweep.log", encoding="utf-8", errors="ignore"):
    m = ROW.match(line.strip())
    if m:
        rows.append(dict(name=m.group(1), wpts=float(m.group(2)),
                         reward=int(m.group(3)), lo=int(m.group(4)),
                         hi=int(m.group(5)), viol=float(m.group(6)),
                         term=int(m.group(7))))
rows.sort(key=lambda r: -r["wpts"])
names = [r["name"] for r in rows]
best = names[0]
col = ["#2a9d8f" if n == best else "#adb5bd" for n in names]

fig = plt.figure(figsize=(15, 8.5))
gs = fig.add_gridspec(2, 4, height_ratios=[1, 1.15], hspace=0.42, wspace=0.32)

def bar(ax, vals, title, ylabel, err=None, invert=False):
    x = np.arange(len(names))
    ax.bar(x, vals, color=col, yerr=err, capsize=3, error_kw=dict(lw=1, alpha=.6))
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=7.5)
    ax.set_title(title, fontsize=10.5)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(alpha=.25, axis="y")
    if invert:
        ax.invert_yaxis()

bar(fig.add_subplot(gs[0, 0]), [r["wpts"] for r in rows],
    "Hedef / bolum  (BIRINCIL OLCUT)", "hedef")
err = np.array([[r["reward"] - r["lo"] for r in rows],
                [r["hi"] - r["reward"] for r in rows]])
bar(fig.add_subplot(gs[0, 1]), [r["reward"] for r in rows],
    "Bolum odulu  (%95 GA)", "odul", err=err)
bar(fig.add_subplot(gs[0, 2]), [r["viol"] for r in rows],
    "Zarf ihlal orani  (kucuk = iyi)", "%")
bar(fig.add_subplot(gs[0, 3]), [r["term"] for r in rows],
    "Erken sonlanma  (kucuk = iyi)", "bolum / 40")

# Ogrenme egrileri (TensorBoard)
ax1 = fig.add_subplot(gs[1, :2])
ax2 = fig.add_subplot(gs[1, 2:])
for r in rows:
    dirs = sorted(glob.glob(f"runs/tb/sweep_{r['name']}*"))
    if not dirs:
        continue
    ea = EventAccumulator(dirs[-1]); ea.Reload()
    tags = ea.Tags()["scalars"]
    lw = 2.2 if r["name"] == best else 1.0
    al = 1.0 if r["name"] == best else 0.55
    if "gorev/hedef_sayisi" in tags:
        e = ea.Scalars("gorev/hedef_sayisi")
        ax1.plot([s.step for s in e], [s.value for s in e],
                 lw=lw, alpha=al, label=r["name"])
    if "komut/degisim_rms" in tags:
        e = ea.Scalars("komut/degisim_rms")
        ax2.plot([s.step for s in e], [s.value for s in e], lw=lw, alpha=al)
ax1.set_title("Ogrenme egrisi: hedef / bolum", fontsize=10.5)
ax1.set_xlabel("adim"); ax1.set_ylabel("hedef"); ax1.grid(alpha=.25)
ax1.legend(fontsize=8, ncol=2)
ax2.set_title("Komut degisim RMS  (titreme gostergesi)", fontsize=10.5)
ax2.set_xlabel("adim"); ax2.set_ylabel("RMS"); ax2.grid(alpha=.25)

fig.suptitle(f"Guidance hiperparametre taramasi -- 7 konfigurasyon x 2M adim "
             f"(kazanan: {best})", fontsize=13)
fig.savefig("runs/sweep_comparison.png", dpi=115, bbox_inches="tight")
print("runs/sweep_comparison.png")
for r in rows:
    print(f"  {r['name']:<14} hedef {r['wpts']:.2f}  odul {r['reward']:5d} "
          f"[{r['lo']},{r['hi']}]  ihlal %{r['viol']:.3f}  erken-son {r['term']}")
