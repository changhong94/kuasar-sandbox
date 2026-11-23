#!/usr/bin/env python3
"""Build an isolated ext4 Linux host for hard-reset verification (no host mounts)."""
import argparse,json,os,pathlib,re,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);a=p.parse_args()
w=pathlib.Path(a.workspace);out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=False);root=out/'root';root.mkdir();ram=out/'ram';ram.mkdir()
def copy(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);shutil.copymode(src,dest)
def binary(src,dest):
 copy(src,dest)
 scan=subprocess.run(['ldd',str(src)],capture_output=True,text=True).stdout
 for path in re.findall(r'(/[^\s()]+)',scan):
  if path.endswith('libachk.so'):continue # host monitoring preload is not part of this VM
  if pathlib.Path(path).is_file():copy(path,root/path.lstrip('/'))
for d in ('bin','dev','proc','sys','run','tmp','etc','data','tools'): (root/d).mkdir(exist_ok=True)
copy('/usr/bin/busybox',root/'bin/busybox')
for name in ('sh','mount','umount','mkdir','sleep','modprobe','ip','cat','sync','poweroff','uname','dmesg'):(root/'bin'/name).symlink_to('busybox')
binary('/usr/bin/python3.10',root/'usr/bin/python3.10');(root/'usr/bin/python3').symlink_to('python3.10')
shutil.copytree('/usr/lib/python3.10',root/'usr/lib/python3.10',ignore=shutil.ignore_patterns('__pycache__','test','tests'))
for lib in (root/'usr/lib/python3.10/lib-dynload').glob('*.so'):
 for dep in re.findall(r'(/[^\s()]+)',subprocess.run(['ldd',str(lib)],capture_output=True,text=True).stdout):
  if dep.endswith('libachk.so'):continue
  if pathlib.Path(dep).is_file():copy(dep,root/dep.lstrip('/'))
for name in ('sandbox-ctl','store-ctl','cloud-hypervisor'):binary(w/'compat-api-bin'/name,root/'tools'/name)
for src,name in ((w/'fork-bin/vmlinux','vmlinux'),(w/'compat-api-bin/sandbox-runtime.bundle','sandbox-runtime.bundle'),(w/'evidence/fork-loopback-local-01/root.image','root.image'),(w/'evidence/fork-loopback-local-01/disk-template.raw','disk-template.raw')):copy(src,root/'tools'/name)
cfg=json.loads((w/'evidence/native-balloon-config.json').read_text());cfg['boot']['kernel']='file:///tools/vmlinux';cfg['boot']['runtime']='file:///tools/sandbox-runtime.bundle';cfg['boot']['root']['base']='file:///tools/root.image@digest:'+cfg['boot']['root']['base'].split('@digest:')[1];cfg['boot']['root']['overlay']['diff_template']='file:///tools/disk-template.raw'
(root/'parent.json').write_text(json.dumps(cfg));(root/'child.json').write_text(json.dumps({'resources':cfg['resources'],'boot':{'runtime':cfg['boot']['runtime']}}))
(root/'manifest-key').write_text(os.urandom(32).hex());os.chmod(root/'manifest-key',0o600)
(root/'manifest.json').write_text(json.dumps({'manifest':{'verify_content':True,'write_generation':'G1'},'store':{'endpoint':'127.0.0.1:19331','pool':4,'timeout':'30s'},'cache':{'endpoint':''},'chunker':{'mode':'cdc'},'crypto':{'chunk':'aes','manifest':'aes'}}))
(root/'store.json').write_text(json.dumps({'listen':'127.0.0.1:19331','backend':'fs','fs':{'root':'/data/store','verify_content_key':True}}))
copy(pathlib.Path(__file__).with_name('nested_reboot_guest.py'),root/'test.py');(root/'native-nested-host').touch()
version=os.uname().release
mods=[]
for name in ('virtio_pci','virtio_blk','ext4','kvm_intel'):
 for line in subprocess.check_output(['modprobe','--show-depends',name],text=True).splitlines():
  if line.startswith('insmod '):mods.append(line.split()[1])
for mod in dict.fromkeys(mods):copy(mod,root/mod.lstrip('/'));copy(mod,ram/mod.lstrip('/'))
for tree in (root,ram):
 for name in ('modules.dep','modules.alias','modules.builtin','modules.builtin.modinfo'):
  src=pathlib.Path('/lib/modules')/version/name
  if src.exists():copy(src,tree/str(src).lstrip('/'))
(root/'init').write_text('#!/bin/sh\nmount -t devtmpfs devtmpfs /dev\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nmount -t tmpfs tmpfs /run\nmount -t tmpfs tmpfs /tmp\nip link set lo up\nmodprobe kvm_intel\nexport PATH=/tools:/bin:/usr/bin\nexport HOME=/root\nmkdir -p /root\npython3 -u /test.py\nwhile true; do sleep 60; done\n');os.chmod(root/'init',0o755)
(ram/'bin').mkdir();copy('/usr/bin/busybox',ram/'bin/busybox');(ram/'bin/sh').symlink_to('busybox')
(ram/'init').write_text('#!/bin/sh\n/bin/busybox --install -s /bin\nmkdir -p /dev /proc /sys /newroot\nmount -t devtmpfs devtmpfs /dev\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nmodprobe virtio_blk\nmodprobe ext4\nfor x in 1 2 3 4 5; do test -e /dev/vda && break; sleep 1; done\nmount /dev/vda /newroot || exec sh\numount /proc; umount /sys; umount /dev\nexec switch_root /newroot /init\n');os.chmod(ram/'init',0o755)
copy('/boot/vmlinuz-'+version,out/'kernel')
with (out/'initramfs').open('wb') as f:
 find=subprocess.Popen(['find','.','-print0'],cwd=ram,stdout=subprocess.PIPE)
 subprocess.run(['cpio','--null','-o','--format=newc'],cwd=ram,stdin=find.stdout,stdout=f,check=True);find.stdout.close();assert find.wait()==0
with (out/'disk.raw').open('wb') as f:f.truncate(8*1024**3)
subprocess.run(['mkfs.ext4','-q','-F','-d',str(root),str(out/'disk.raw')],check=True)
print(out,flush=True)
