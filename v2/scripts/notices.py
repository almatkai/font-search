#!/usr/bin/env python3
"""Copy authentic grants from the exact locked Cargo source, never substitute one.
The package includes only default runtime dependency grants; source also records QA.
"""
import pathlib,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'.qa'
allmeta=json.loads((QA/'metadata.json').read_text());members={}
for platform in ['macos','windows']:
 m=json.loads((QA/f'metadata-{platform}.json').read_text());nodes={n['id']:n for n in m['resolve']['nodes']};todo=[m['resolve']['root']];seen=set()
 while todo:
  i=todo.pop()
  if i in seen:continue
  seen.add(i);todo.extend(d['pkg']for d in nodes[i]['deps'])
 members[platform]=seen
records=[];missing=[]
for p in sorted(allmeta['packages'],key=lambda p:(p['name'],p['version'])):
 if p['name']=='tezbar-font-search':continue
 src=pathlib.Path(p['manifest_path']).parent;label=p['name']+'-'+p['version'];grants=[]
 for file in sorted(src.rglob('*')):
  if not file.is_file() or not any(k in file.name.upper()for k in ['LICENSE','LICENCE','COPYING','AUTHORS','NOTICE','COPYRIGHT']):continue
  if any(x in ['tests','test','target','.git']for x in file.relative_to(src).parts):continue
  data=file.read_bytes();rel=pathlib.Path('licenses/cargo')/label/file.relative_to(src);out=ROOT/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data);grants.append({'path':str(rel),'sha256':hashlib.sha256(data).hexdigest()})
 if not grants:missing.append(label)
 records.append({'name':p['name'],'version':p['version'],'source':p['source'],'licenseExpression':p.get('license'),'runtimePlatforms':[k for k,v in members.items()if p['id']in v],'grants':grants})
(ROOT/'licenses/dependencies.json').write_text(json.dumps({'packages':records,'missingGrantText':missing,'note':'r-efi AUTHORS includes its actual license grant; no missing-license inference from filename.'},indent=2)+'\n')
assert not missing,missing
notice='''Font Search external Rust development package
Source: https://github.com/almatkai/font-search
Portable V1 source: f52afb19ac55199fa4ecbe2c3d94f82a831cb2ca (MIT).
The original LICENSE bytes, including literal backslash-n sequences, are preserved
at licenses/portable-v1-LICENSE.original.txt. Package LICENSE expands those escapes
to line breaks without changing the grant wording.

The original icon is from Raycast/extensions at
6734d85992290066fd31a7f5bee3cca3d3545a1a, extensions/font-search/assets/extension-icon.png.
SHA256 729724bc2c33449f14680faf1a38268eea1b5053d335186a9c94366bfc8ac263
Its authentic repository MIT license is included at licenses/raycast-extensions-MIT.txt.

tezbar-extension-sdk 0.1.1 is pinned to HTTPS git revision
e955911f0bf5b558f9d3eb5183df0adc95c22af2 (Apache-2.0); its NOTICE is included.
Authentic runtime dependency grants are under licenses/cargo/.
Source-only QA dependencies and target-inapplicable dependencies are identified in
licenses/dependencies.json; they are not bundled into the production executable.
Generated QA fonts use new geometric outlines and inherit the repository MIT grant.
No installed system/user/commercial font files are distributed.
'''
(ROOT/'NOTICE').write_text(notice)
print('Authentic Cargo grants:',len(records),'packages; missing:',missing)
