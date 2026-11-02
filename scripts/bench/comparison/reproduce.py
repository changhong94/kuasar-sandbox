"""Run the single-node plan, then rebuild charts from saved measurements."""
import argparse
import subprocess
import sys
import time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("--config",required=True)
p.add_argument("--output-root",required=True)
p.add_argument("--stages",default="storage,fixtures,memory,cache,density")
p.add_argument("--counts",default="1,2,4,8,12")
args=p.parse_args()
base=Path(args.output_root)/time.strftime("comparison-%Y%m%d_%H%M")
base.mkdir(parents=True,exist_ok=False)
here=Path(__file__).parent
for stage in args.stages.split(","):
    out=base/stage
    if stage in ("storage","fixtures"):
        cmd=[sys.executable,str(here/"prepare.py"),stage,"--config",args.config,"--output",str(out)]
    elif stage in ("memory","cache","density"):
        cmd=[sys.executable,str(here/"run.py"),"--config",args.config,"--output",str(out),
             "--stage",stage,"--repeats","3" if stage=="cache" else "2"]
        if stage=="density":cmd+=["--counts",args.counts]
    else:
        raise SystemExit("Unknown stage "+stage)
    subprocess.run(cmd,check=True)
    if stage!="fixtures":
        subprocess.run([sys.executable,str(here/("storage_report.py" if stage=="storage" else "report.py")),str(out)],check=True)
print("COMPLETE",base)
