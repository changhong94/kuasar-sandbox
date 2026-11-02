"""Optional publication plots from report.py JSON; no connection to deployment."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

p=argparse.ArgumentParser()
p.add_argument("summary")
p.add_argument("--output",required=True)
args=p.parse_args()
r=json.loads(Path(args.summary).read_text())
stage=r["plan"]["stage"]
groups=r["groups"]
colors={"kuasar/off":"#b40000","kuasar/memory":"#e18020","cube/off":"#247ba0"}
plt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})
if stage=="memory":
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    labels=[g["product"]+"/"+g["prefetch"] for g in groups]
    xx=np.arange(len(groups))
    axes[0].bar(xx-.18,[g["before_touch_pss_mib"]["median"] for g in groups],.36,label="Before full read",color="#aeb9c4")
    axes[0].bar(xx+.18,[g["sandbox_pss_mib"]["median"] for g in groups],.36,label="After full read",color="#b40000")
    axes[0].set_xticks(xx,labels);axes[0].set_ylabel("Sandbox PSS (MiB)");axes[0].legend()
    axes[1].bar(labels,[g["platform_pss_mib"]["median"] for g in groups],color=[colors[x] for x in labels])
    axes[1].set_ylabel("Selected platform processes: PSS (MiB)")
    fig.suptitle("Nominal 2 GiB per sandbox; actual memory depends on working-set access")
elif stage=="cache":
    fig,axes=plt.subplots(1,2,figsize=(13,6))
    variants=list(colors)
    labels=[f"C{c}\n{cache}" for c in (1,4) for cache in ("warm","file-advised-cold")]
    for ax,metric,title in zip(axes,("ready_ms","full_touch_ms"),("First simple command","Full memory + file verification")):
        for i,variant in enumerate(variants):
            product,mode=variant.split("/")
            selected=[next(g for g in groups if g["product"]==product and g["prefetch"]==mode and g["count"]==c and g["cache"]==cache) for c in (1,4) for cache in ("warm","file-advised-cold")]
            vals=[g[metric]["median"] for g in selected]
            ax.bar(np.arange(4)+(i-1)*.24,vals,.24,label=variant,color=colors[variant])
        ax.set_xticks(np.arange(4),labels,fontsize=9);ax.set_ylabel("Median milliseconds");ax.set_title(title)
    handles,legend_labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc="upper center",bbox_to_anchor=(.5,.91),ncol=3,fontsize=10)
    fig.suptitle("Cache / prefetch comparison — three measured batches per condition")
else:
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    for variant,color in colors.items():
        product,mode=variant.split("/")
        selected=sorted([g for g in groups if g["product"]==product and g["prefetch"]==mode],key=lambda g:g["count"])
        xx=[g["count"] for g in selected]
        axes[0,0].plot(xx,[g["readonly_pss_mib"]["median"] for g in selected],"o--",color=color,label=variant+" read-only")
        axes[0,0].plot(xx,[g["sandbox_pss_mib"]["median"] for g in selected],"o-",color=color,label=variant+" modified")
        axes[0,1].plot(xx,[g["ready_ms"]["p95"] for g in selected],"o-",color=color,label=variant)
        axes[1,0].plot(xx,[g["repeated_touch_ms"]["p95"] for g in selected],"o-",color=color,label=variant)
        axes[1,1].plot(xx,[g["platform_pss_mib"]["median"] for g in selected],"o-",color=color,label=variant)
    for ax,title,unit in zip(axes.flat,("Memory: read-only vs per-page writes","Restore: first-command sample p95","Running instances: full verification sample p95","Selected platform process memory"),("Sandbox PSS (MiB)","Milliseconds","Milliseconds","PSS (MiB)")):
        ax.set_title(title);ax.set_xlabel("Simultaneous instances");ax.set_ylabel(unit);ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle("Observed density under one workload — not a production capacity guarantee")
fig.text(.01,.015,"Single host, XFS loop over ext4. Advisory file-cache eviction retains application caches. API/SDK overhead included.",fontsize=9)
fig.tight_layout(rect=(0,.05,1,.94))
out=Path(args.output)
out.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(str(out)+".png",dpi=170)
fig.savefig(str(out)+".svg")
