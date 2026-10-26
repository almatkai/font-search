#!/usr/bin/env python3
"""Run from the clone via scripts/qa-run.sh. No live font producers/GUI/services.
No root/sibling/SDK changes; all dependency installs ignore lifecycle scripts.
"""
import os,pathlib,subprocess,json,shutil,sys,hashlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1];REPO=ROOT.parent;QA=ROOT/'.qa';QA.mkdir(exist_ok=True);gates=[]
for variable in ['HOME','TMPDIR','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','CARGO_HOME']:
 assert str(pathlib.Path(os.environ[variable]).resolve()).startswith(str(QA)+os.sep),variable
def run(name,cmd,required=True,cwd=REPO):
 log=QA/(name+'.log')
 with log.open('w')as out:p=subprocess.run([str(x)for x in cmd],cwd=cwd,stdout=out,stderr=subprocess.STDOUT)
 gates.append({'name':name,'state':'passed'if p.returncode==0 else'failed','exitCode':p.returncode,'log':str(log.relative_to(ROOT))})
 print(name,':',gates[-1]['state'],flush=True)
 if p.returncode and required:print(log.read_text()[-6000:]);raise SystemExit(p.returncode)
 return p.returncode
py=QA/'venv/bin/python';node='node';cargo=['cargo'];manifest=['--manifest-path',ROOT/'Cargo.toml','--locked']
run('prepare',[sys.executable,ROOT/'scripts/prepare.py'])
run('npm-v1',['npm','--prefix',QA/'v1','ci','--ignore-scripts','--no-audit','--no-fund'])
run('v1-test',['npm','--prefix',QA/'v1','test']);run('v1-typecheck',['npm','--prefix',QA/'v1','run','typecheck'])
assert (QA/'v1/package-lock.json').read_bytes()==(REPO/'package-lock.json').read_bytes()
(QA/'tools').mkdir(exist_ok=True)
for name in ['package.json','package-lock.json']:shutil.copyfile(ROOT/'qa'/name,QA/'tools'/name)
run('npm-qa',['npm','--prefix',QA/'tools','ci','--ignore-scripts','--no-audit','--no-fund'])
if not py.exists():run('qa-venv',[sys.executable,'-m','venv',QA/'venv'])
run('pip-qa',[py,'-m','pip','install','--require-hashes','-r',ROOT/'qa/requirements.lock'])
run('generate-fonts',[py,ROOT/'qa/generate_fonts.py']);run('oracle',[node,ROOT/'qa/oracle.cjs'])
run('host-contracts',[sys.executable,ROOT/'qa/host_contracts.py']);run('host-patch',[sys.executable,ROOT/'qa/host_patch.py'])
run('host-patch-check',['git','apply','--check','--directory=v2/.qa/pinned/host',ROOT/'host-prerequisites/input-ownership.patch'])
run('renderer',[node,ROOT/'qa/renderer.cjs']);run('schema',[py,ROOT/'qa/schema.py'])
for tool in ['stable','1.85.0']:
 run(tool+'-fmt',['cargo','+'+tool,'fmt','--manifest-path',ROOT/'Cargo.toml','--check'])
 run(tool+'-test',['cargo','+'+tool,'test',*manifest,'--all-targets','--all-features'])
 run(tool+'-clippy',['cargo','+'+tool,'clippy',*manifest,'--all-targets','--all-features','--','-D','warnings'])
for tool in ['stable','1.85.0']:
 run('windows-'+tool+'-check',['cargo','+'+tool,'check',*manifest,'--all-targets','--all-features','--target','x86_64-pc-windows-gnu'])
 run('windows-'+tool+'-clippy',['cargo','+'+tool,'clippy',*manifest,'--all-targets','--all-features','--target','x86_64-pc-windows-gnu','--','-D','warnings'])
run('build-debug',['cargo','+stable','build',*manifest,'--all-features','--bins'])
run('previews',[sys.executable,ROOT/'qa/previews.py'])
for features,suffix,platform in [(['--all-features'],'',''),([], '-macos','aarch64-apple-darwin'),([], '-windows','x86_64-pc-windows-msvc')]:
 cmd=['cargo','+stable','metadata',*manifest,'--format-version','1',*features]
 if platform:cmd+=['--filter-platform',platform]
 p=subprocess.run([str(x)for x in cmd],capture_output=True,check=True);(QA/('metadata'+suffix+'.json')).write_bytes(p.stdout)
run('notices',[sys.executable,ROOT/'scripts/notices.py'])
run('fresh-build',[sys.executable,ROOT/'scripts/fresh-build.py'])
run('package',[sys.executable,ROOT/'scripts/package.py'])
prod=(QA/'extracted-binary.txt').read_text().strip();run('process',[sys.executable,ROOT/'qa/process.py','--production',prod])
report={'sourceCommit':'f52afb19ac55199fa4ecbe2c3d94f82a831cb2ca','sdkCommit':'e955911f0bf5b558f9d3eb5183df0adc95c22af2','hostCommit':'ea100cee3f69711de12485ba061950c5fc65258f','gates':gates,'passed':sum(g['state']=='passed'for g in gates),'nativeFontDiscovery':'not-run','macOSGUI':'not-run','WindowsGUI':'not-run','WindowsGNUCheckAndClippy':'passed on stable and 1.85.0','WindowsMSVC':'not-run (target not installed)','WindowsLink':'not-run (MinGW C compiler/dlltool not installed)','acceptedRelease':False}
(ROOT/'evidence/verification.json').write_text(json.dumps(report,indent=2)+'\n');print('ALL',report['passed'],'automated gates passed; OS/GUI acceptance remains not-run')
