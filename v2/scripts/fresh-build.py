#!/usr/bin/env python3
"""Fresh empty Cargo home/target + copied production source, immutable HTTPS SDK.
Never reuse downloaded Cargo sources or invoke any font-discovery command.
"""
import pathlib,tempfile,shutil,os,subprocess,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'.qa';run=pathlib.Path(tempfile.mkdtemp(prefix='fresh-',dir=QA));source=run/'source';source.mkdir();home=run/'cargo-home';target=run/'target';home.mkdir();target.mkdir()
assert not list(home.iterdir())and not list(target.iterdir())
for name in ['Cargo.toml','Cargo.lock'] :shutil.copyfile(ROOT/name,source/name)
shutil.copytree(ROOT/'src',source/'src')
env={**os.environ,'CARGO_HOME':str(home),'CARGO_TARGET_DIR':str(target),'CARGO_NET_GIT_FETCH_WITH_CLI':'true','GIT_CONFIG_NOSYSTEM':'1'}
cmd=['cargo','+1.85.0','build','--manifest-path',str(source/'Cargo.toml'),'--locked','--release','--bin','font-search','--target','aarch64-apple-darwin']
log=run/'build.log'
with log.open('w')as out:subprocess.run(cmd,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
text=log.read_text();assert 'https://github.com/almatkai/tezbar-extension-sdk-rust'in text
binary=target/'aarch64-apple-darwin/release/font-search';assert binary.is_file()
# Protocol introspection is source/discovery-free.
p=subprocess.run([binary,'--protocol-info'],env=env,capture_output=True,text=True,check=True);info=json.loads(p.stdout);assert info['id']=='com.tezbar.native.font-search'and info['commands']==['search-fonts']and info['sdkVersion']=='0.1.1'
(ROOT/'evidence/fresh-build.json').write_text(json.dumps({'toolchain':'1.85.0','target':'aarch64-apple-darwin','emptyCargoHome':True,'emptyTarget':True,'sourceCopy':str(source.relative_to(ROOT)),'httpsSdkRev':'e955911f0bf5b558f9d3eb5183df0adc95c22af2','binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'protocolInfo':info},indent=2)+'\n')
(QA/'fresh-binary.txt').write_text(str(binary)+'\n');print('Fresh empty-Cargo/target HTTPS source build passed:',binary)
