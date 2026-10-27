#!/usr/bin/env python3
"""Deterministic ARM64 *development* ZIP. No release/acquisition URLs or install.
Closed map, fixed metadata, SHA256 per member; extraction stays inside .qa.
"""
import pathlib,json,hashlib,zipfile,io,stat,subprocess,copy
ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'.qa';DIST=ROOT/'dist';DIST.mkdir(exist_ok=True)
binary=pathlib.Path((QA/'fresh-binary.txt').read_text().strip());assert binary.is_file()
manifest=json.loads((ROOT/'extension.json').read_text());assert manifest['artifacts']=={}and all(v['state']=='not-run'for v in manifest['verification'])
raw={ 'bin/font-search':binary.read_bytes(),'resources/extension-icon.png':(ROOT/'resources/extension-icon.png').read_bytes(),'LICENSE':(ROOT/'LICENSE').read_bytes(),'NOTICE':(ROOT/'NOTICE').read_bytes(),'licenses/raycast-extensions-MIT.txt':(ROOT/'licenses/raycast-extensions-MIT.txt').read_bytes(),'licenses/portable-v1-LICENSE.original.txt':(ROOT/'licenses/portable-v1-LICENSE.original.txt').read_bytes() }
notices=json.loads((ROOT/'licenses/dependencies.json').read_text());runtime=[p for p in notices['packages']if 'macos'in p['runtimePlatforms']]
for p in runtime:
 for f in p['grants']:
  data=(ROOT/f['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==f['sha256'];raw[f['path']]=data
raw['licenses/dependencies.json']=(json.dumps({'packages':runtime,'missingGrantText':[]},indent=2)+'\n').encode()
manifest['files']={n:hashlib.sha256(d).hexdigest()for n,d in sorted(raw.items())};raw['extension.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
def archive():
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
  for name,data in sorted(raw.items()):
   info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3;info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=((stat.S_IFREG|0o755)if name.startswith('bin/')else(stat.S_IFREG|0o644))<<16;z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 return out.getvalue()
data=archive();assert data==archive(),'non-deterministic archive bytes for identical inputs'
zip_path=DIST/'font-search-aarch64-apple-darwin-dev.zip';zip_path.write_bytes(data)
def validate(blob,extract=False):
 with zipfile.ZipFile(io.BytesIO(blob))as z:
  names=z.namelist();assert len(names)==len(set(names))and set(names)==set(raw),'closed ZIP members'
  for name in names:
   assert not name.startswith('/')and '\\'not in name and all(c not in ('','.','..')for c in name.split('/'))
   assert stat.S_ISREG(z.getinfo(name).external_attr>>16)
   assert z.read(name)==raw[name]
  m=json.loads(z.read('extension.json'));assert set(m['files'])==set(names)-{'extension.json'}
  for name,digest in m['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
  if extract:
   out=QA/('extracted-'+hashlib.sha256(blob).hexdigest()[:16]);out.mkdir(exist_ok=True)
   for name in names:
    dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name));dest.chmod(0o755 if name.startswith('bin/')else 0o644)
   return out
out=validate(data,True)
# Malformed archive/modified-member negatives exercise the same closed validator.
negative=0
for name,value in [('extra.txt',b'not inventoried'),('resources/extension-icon.png',b'bad digest')]:
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w')as z:
  with zipfile.ZipFile(io.BytesIO(data))as original:
   for n,d in raw.items():z.writestr(original.getinfo(n),value if n==name else d)
  if name not in raw:z.writestr(name,value)
 try:validate(buf.getvalue())
 except AssertionError:negative+=1
 else:raise AssertionError('damaged ZIP accepted')
subprocess.run([QA/'venv/bin/python',ROOT/'qa/schema.py',zip_path],check=True)
info=json.loads(subprocess.check_output([out/'bin/font-search','--protocol-info']));assert info['commands']==['search-fonts']and info['id']==manifest['id']
(QA/'extracted-binary.txt').write_text(str(out/'bin/font-search')+'\n')
report={'type':'development only; no accepted release','target':'aarch64-apple-darwin','zip':str(zip_path.relative_to(ROOT)),'sha256':hashlib.sha256(data).hexdigest(),'executableSha256':hashlib.sha256(raw['bin/font-search']).hexdigest(),'members':{n:hashlib.sha256(d).hexdigest()for n,d in sorted(raw.items())},'closedInventory':True,'deterministicIdenticalInputRebuild':True,'negativeArchives':negative,'productionProtocolInfo':info,'GUIAcceptance':'not-run'}
(ROOT/'evidence/package.json').write_text(json.dumps(report,indent=2)+'\n');print('Closed deterministic development ZIP:',len(raw),'members, SHA256',report['sha256'])
