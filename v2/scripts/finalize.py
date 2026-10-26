#!/usr/bin/env python3
"""Review inventory; no staging/commits. Parent may rehash exact staged blobs."""
import pathlib,subprocess,hashlib,json,sys,stat
ROOT=pathlib.Path(__file__).resolve().parents[2];INV='v2/evidence/inventory.json';REV='f52afb19ac55199fa4ecbe2c3d94f82a831cb2ca'
def git(*args,input=None):return subprocess.check_output(['git','-C',str(ROOT),*args],input=input)
def sha(b):return hashlib.sha256(b).hexdigest()
assert git('rev-parse','--show-toplevel').decode().strip()==str(ROOT)
assert git('branch','--show-current').decode().strip()=='feat/native-v2-rust'
assert git('rev-parse','HEAD').decode().strip()==REV
if '--check-staged'in sys.argv:
 inventory=json.loads((ROOT/INV).read_text());expected={r['path']for r in inventory['files']}|{INV};actual=set(git('diff','--cached','--name-only','-z').decode().strip('\0').split('\0'));assert actual==expected,(actual^expected)
 for r in inventory['files']:assert sha(git('show',':'+r['path']))==r['sha256'],r['path']
 print('Parent staged blobs match inventory:',len(inventory['files']),'files (inventory self excluded)');sys.exit()
assert not git('diff','--cached','--name-only').strip(),'This implementation must leave the index empty'
originals=git('ls-tree','-r','--name-only',REV).decode().splitlines();source=[]
for name in originals:
 data=git('show',REV+':'+name);actual=(ROOT/name).read_bytes()
 if name=='README.md':assert actual==data+b'\n\n[Rust v2 development port and verification](v2/README.md).\n'
 else:assert actual==data,'V1 tracked bytes changed: '+name
 source.append({'path':name,'sha256':sha(data)})
visible=git('ls-files','--cached','--others','--exclude-standard','-z').decode().strip('\0').split('\0');files=[]
for name in sorted(set(visible)):
 if name==INV:continue
 if name!='README.md'and not name.startswith('v2/'):continue
 assert not any(part in ['.qa','target','dist','node_modules','__pycache__']for part in name.split('/')),name
 assert not name.endswith(('.zip','.pyc')),name
 p=ROOT/name;assert p.is_file()and not p.is_symlink(),name;data=p.read_bytes()
 files.append({'path':name,'sha256':sha(data),'gitBlob':git('hash-object','--stdin',input=data).decode().strip(),'bytes':len(data),'mode':'100755'if p.stat().st_mode&stat.S_IXUSR else'100644'})
report={'root':str(ROOT),'branch':'feat/native-v2-rust','sourceCommit':REV,'index':'empty at finalization','selfExcluded':INV,'v1Originals':source,'files':files}
(ROOT/INV).write_text(json.dumps(report,indent=2)+'\n')
print('Inventory:',len(files),'files;',sum(f['bytes']for f in files),'bytes; V1 intact except authorized README; index empty')
