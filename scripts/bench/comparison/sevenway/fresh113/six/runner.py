import datetime, hashlib, json, os, pathlib, subprocess, tempfile, threading, time
R=pathlib.Path(__file__).resolve().parent
S=R.parent/'sandbox_fork'
now=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(p):
    with p.open('rb') as f:
        h=hashlib.sha256()
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
        return h.hexdigest()
def save(p,d):
    with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False) as f:
        json.dump(d,f,indent=2)
    os.replace(f.name,p)
os.environ.update(CARGO_HOME=str(S/'tools/rust/cargo'),CARGO_TARGET_DIR=str(R/'target'),PATH=str(S/'tools/rust/stable/bin')+':'+os.environ['PATH'])
for repo,rev,package,bins in [
 ('cloud-hypervisor/cloud-hypervisor','6a63506ad005189c5cd9af75f928a3d988bdf28f','cloud-hypervisor',['cloud-hypervisor','ch-remote']),
 ('kuasar-io/kuasar','efe7cbcdf698d6ab86ad4e0ccce0dd0d83f1e1d2','vmm-sandboxer',['cloud_hypervisor'])]:
    path=S/repo
    for cmd,expected in [(['rev-parse','HEAD'],rev),(['branch','--show-current'],'sandbox_fork_staging'),(['status','--porcelain'],'')]:
        assert subprocess.check_output(['git',*cmd],cwd=path,text=True).strip()==expected
    stamp=R/(package+'.json')
    if stamp.exists():
        prior=json.loads(stamp.read_text())
        if prior['source']==rev and all(digest(R/'bin'/b)==prior['hashes'][b] for b in bins): continue
    a=R/'attempts'/(package+'-'+str(time.time_ns()))
    a.mkdir()
    args=['cargo','build','--manifest-path',str(path/'Cargo.toml'),'--locked','--offline','--release','-j','6','-p',package]
    # ch-remote is a binary of the top-level cloud-hypervisor package.
    for b in bins: args.extend(['--bin',b])
    d=dict(section='build',batch=package,source=rev,attempt=a.name,start=now(),command=args)
    save(a/'status.json',d)
    with (a/'build.log').open('w') as f:
        process=subprocess.Popen(args,cwd='/tmp',stdout=f,stderr=subprocess.STDOUT)
        while process.poll() is None:
            save(R/'status.json',dict(d,heartbeat=now(),log_bytes=f.tell()))
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: pass
    d.update(end=now(),exit=process.returncode)
    if process.returncode: d['error']=str(a/'build.log')
    else:
        import shutil
        for b in bins: shutil.copy2(R/'target/release'/b,R/'bin'/b)
        d['hashes']={b:digest(R/'bin'/b) for b in bins}
        save(stamp,d)
    save(a/'status.json',d)
    save(R/'status.json',d)
    if process.returncode: raise SystemExit(process.returncode)
save(R/'status.json',dict(section='deployment',state='builds_complete',time=now()))
