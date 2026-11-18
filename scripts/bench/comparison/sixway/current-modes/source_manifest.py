from pathlib import Path
import hashlib,json,subprocess as sp
B=Path('/home/hong/src/research/report-revision-113')
repos={'kuasar':Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar'),'accelerator':B/'accelerator','bench':B/'bench'}
out={}
for name,repo in repos.items():
 def git(*args):return sp.check_output(['git','-C',str(repo),*args],text=True)
 assert git('branch','--show-current').strip()=='sandbox_fork_staging'
 paths=git('ls-files','--modified','--others','--exclude-standard').splitlines()
 out[name]={'head':git('rev-parse','HEAD').strip(),'branch':'sandbox_fork_staging','modified_files':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths if (repo/p).is_file()}}
 (B/(name+'-revision.patch')).write_text(git('diff'))
out['binaries']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (B/'bin').iterdir() if p.is_file()}
out['benchmark_scripts']={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'mode_worker.py',B/'cache_state.py',B/'run_matrix.py',B/'tools/startup.py',B/'tools/pool_gate.py',B/'tools/languages.py']}
(B/'source-provenance-startup.json').write_text(json.dumps(out,indent=2))
