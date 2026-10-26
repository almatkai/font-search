#!/usr/bin/env python3
"""Read pinned Git objects only; all mutable source copies stay inside .qa."""
import hashlib,json,pathlib,subprocess,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]; V2=ROOT/'v2'; QA=V2/'.qa'; PIN=QA/'pinned'
HOST=ROOT.parents[1]/'Tezbar'; SDK=ROOT.parent/'tezbar-extension-sdk-rust'
HREV='ea100cee3f69711de12485ba061950c5fc65258f'; SREV='e955911f0bf5b558f9d3eb5183df0adc95c22af2'; VREV='f52afb19ac55199fa4ecbe2c3d94f82a831cb2ca'
def obj(repo, rev, path): return subprocess.check_output(['git','-C',str(repo),'show',rev+':'+path])
def write(path,data): path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
records={}
for repo,rev,kind,paths in [(HOST,HREV,'host',['schemas/extension-v3.schema.json','docs/EXTERNAL_RUST_EXTENSIONS.md','src/renderer/src/raycast-api/list-runtime.tsx','src/renderer/src/raycast-api/index.tsx','src/renderer/ExtensionRuntimeView.tsx','src/renderer/ui/Markdown.tsx','src/renderer/src/raycast-api/detail-runtime.tsx','src/renderer/ui/primitives.tsx','src/renderer/colorConverter.ts','src/renderer/tauri-bridge.ts','src/shared/extensionRuntime.ts','src-tauri/src/native_core/extensions/process_host.rs','src-tauri/src/native_core/extensions/process.rs','src-tauri/src/native_core/extensions/mod.rs','src-tauri/src/native_core/extensions/native.rs','src-tauri/src/native_core/extensions/registry.rs','src-tauri/src/native_core/platform.rs','src-tauri/src/native_core/launcher/clipboard.rs']), (SDK,SREV,'sdk',['SDK_API.md','PROTOCOL.md','HOST_INTEGRATION.md','src/runner.rs','src/context.rs','src/lib.rs','src/storage.rs','Cargo.toml','LICENSE','NOTICE'])]:
 for p in paths:
  data=obj(repo,rev,p);write(PIN/kind/p,data);records[kind+'/'+p]={'revision':rev,'sha256':hashlib.sha256(data).hexdigest()}
for p in subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',VREV],text=True).splitlines():write(QA/'v1'/p,obj(ROOT,VREV,p))
url='https://raw.githubusercontent.com/raycast/extensions/6734d85992290066fd31a7f5bee3cca3d3545a1a/extensions/font-search/assets/extension-icon.png'
with urllib.request.urlopen(url,timeout=30) as r: icon=r.read()
assert icon==(ROOT/'assets/extension-icon.png').read_bytes(), 'Original icon bytes mismatch'
write(V2/'resources/extension-icon.png',icon)
with urllib.request.urlopen('https://raw.githubusercontent.com/raycast/extensions/6734d85992290066fd31a7f5bee3cca3d3545a1a/LICENSE',timeout=30) as r: grant=r.read()
write(V2/'licenses/raycast-extensions-MIT.txt',grant)
original_license=obj(ROOT,VREV,'LICENSE')
write(V2/'licenses/portable-v1-LICENSE.original.txt',original_license)
write(V2/'LICENSE',original_license.replace(b'\\n',b'\n'))
records['icon']={'url':url,'sha256':hashlib.sha256(icon).hexdigest(),'bytes':len(icon)}
write(V2/'evidence/pinned-sources.json',(json.dumps(records,indent=2,sort_keys=True)+'\n').encode())
print(json.dumps(records['icon']))
