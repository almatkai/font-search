'use strict';
// Execute actual V1 TSX/helpers in a closed VM. All effects are installed before
// loading the first module or invoking hooks/callbacks. No module fallback.
const rawAssert=require('node:assert/strict');let assertions=0;const assert=new Proxy(rawAssert,{apply:(t,c,a)=>{assertions++;return Reflect.apply(t,c,a)},get:(t,k)=>typeof t[k]==='function'?(...a)=>{assertions++;return t[k](...a)}:t[k]});
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..'), QA=path.join(ROOT,'.qa'), ts=require(path.join(QA,'tools/node_modules/typescript'));
const tree=path.join(QA,'fonts');
function readOwned(p){const c=fs.realpathSync(p);assert(c.startsWith(QA+path.sep));return fs.readFileSync(c,'utf8');}
const deny=()=>{throw Error('VM OS/fs/network/effect denied')};
const report={};
function make(platform){
 const logs=[],cache=new Map(),storage=new Map();let states=[],cursor=0,promiseSlot=null,callback=null,reads=0;
 const roots=platform==='win32'?[['C:\\OwnedWindows\\Fonts','system-a'],['C:\\OwnedLocal\\Microsoft\\Windows\\Fonts','user']]:[['/System/Library/Fonts','system-a'],['/Library/Fonts','system-b'],[path.join(QA,'owned-home/Library/Fonts'),'user']];
 const pth=platform==='win32'?path.win32:path.posix;
 const snapshot={};
 function collect(actual,virtual){
  snapshot[virtual]=fs.readdirSync(actual,{withFileTypes:true}).map(e=>Object.freeze({name:e.name,isDirectory:()=>e.isDirectory()}));
  for(const e of snapshot[virtual])if(e.isDirectory())collect(path.join(actual,e.name),pth.join(virtual,e.name));
 }
 for(const [v,r]of roots)collect(path.join(tree,r),v);
 const guardedFs=Object.freeze({promises:Object.freeze({readdir:async(p,opts)=>{assert(opts.withFileTypes);reads++;if(!(p in snapshot))throw Error('Missing owned directory');return snapshot[p];},readFile:deny,writeFile:deny,open:deny,stat:deny,realpath:deny,rm:deny,mkdir:deny}),readFileSync:deny,writeFileSync:deny,readdirSync:deny,createReadStream:deny,createWriteStream:deny,open:deny,openSync:deny});
 const token=(name)=>new Proxy(function(){deny()},{get:(_,key)=>key==='name'?name:token(name+'.'+String(key))});
 const react={useState:(initial)=>{const i=cursor++;if(!(i in states))states[i]=initial;return[states[i],v=>{states[i]=typeof v==='function'?v(states[i]):v}]},useRef:v=>({current:v}),useEffect:cb=>cb()};
 const api={ActionPanel:token('ActionPanel'),List:token('List'),Action:token('Action'),Icon:token('Icon'),Color:{PrimaryText:'#eeeeee'},Cache:class{get(k){return cache.get(k)}set(k,v){cache.set(k,v)}remove(k){cache.delete(k)}},LocalStorage:{getItem:async k=>storage.get(k),setItem:async(k,v)=>storage.set(k,v)},getPreferenceValues:()=>({previewText:'Sphinx of black quartz, judge my vow.'}),showToast:v=>logs.push(v),Toast:{Style:{Success:'success',Failure:'failure'}},Keyboard:{Shortcut:{Common:{New:{modifiers:['cmd'],key:'n'},Pin:{modifiers:['cmd','shift'],key:'p'}}}}};
 const utils={useCachedPromise:fn=>{callback=fn;if(!promiseSlot){promiseSlot={isLoading:true,data:undefined,revalidate:async()=>{promiseSlot.data=await callback()}};promiseSlot.pending=fn().then(v=>{promiseSlot.data=v;promiseSlot.isLoading=false})}return promiseSlot}};
 const loaded={};
 function load(name){if(loaded[name])return loaded[name];const source=readOwned(path.join(QA,'v1/src',name));const extra=name==='search-fonts.tsx'?'\nexport { getFonts, collectFontFiles, FontListItem, PostScriptNamesList };':'';
  const exports={};const context=vm.createContext({exports,module:{exports},Buffer,AbortController,console:{error:(...a)=>logs.push(a)},process:Object.freeze({platform,env:Object.freeze({WINDIR:'C:\\OwnedWindows',LOCALAPPDATA:'C:\\OwnedLocal'})}),require:id=>{
   if(id==='react')return react;if(id==='react/jsx-runtime')return {jsx:(type,props,key)=>({type,props:props||{},key}),jsxs:(type,props,key)=>({type,props:props||{},key})};
   if(id==='@raycast/api')return api;if(id==='@raycast/utils')return utils;
   if(id==='node:fs')return guardedFs;if(id==='node:os')return {homedir:()=>path.join(QA,'owned-home')};if(id==='node:path')return pth;
   if(id==='./fontPreview')return load('fontPreview.ts');if(id==='./utils')return load('utils.ts');throw Error('VM module denied: '+id);
  }},{codeGeneration:{strings:false,wasm:false}});
  vm.runInContext(ts.transpileModule(source+extra,{compilerOptions:{esModuleInterop:true,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText,context,{timeout:3000});loaded[name]=exports;return exports;
 }
 const main=load('search-fonts.tsx');
 const children=n=>[].concat(n?.props?.children||[]).flat().filter(Boolean);
 const named=n=>typeof n?.type==='function'?n.type.name:String(n?.type);
 const walk=n=>[n,...children(n).flatMap(walk)];
 const render=fn=>{cursor=0;return fn()};
 const plain=x=>JSON.parse(JSON.stringify(x));
 const normalize=fonts=>plain(fonts).map(f=>{const [v,r]=roots.find(([v])=>f.path===v||f.path.startsWith(v+pth.sep));return {...f,path:path.join(tree,r,...pth.relative(v,f.path).split(pth.sep))}});
 return {main,cache,storage,logs,react,load,plain,normalize,render,walk,named,children,get reads(){return reads},async settled(){await promiseSlot.pending;}};
}
(async()=>{
 for(const platform of ['darwin','win32']){
  const baseline=assertions;const o=make(platform);const fonts=await o.main.getFonts();report[platform]={fonts:o.normalize(fonts)};
  const reads=o.reads;assert.deepEqual(o.plain(await o.main.getFonts()),o.plain(fonts));assert.equal(o.reads,reads,'cache must avoid source enumeration');
  let screen=o.render(o.main.default);await o.settled();screen=o.render(o.main.default);
  const find=(type)=>o.walk(screen).find(n=>o.named(n)===type);
  assert.equal(screen.props.searchBarPlaceholder,'Search fonts...');assert.equal(screen.props.isShowingDetail,true);
  const dropdown=screen.props.searchBarAccessory;assert.equal(o.named(dropdown),'List.Dropdown');assert.equal(dropdown.props.storeValue,true);
  assert.deepEqual(o.children(dropdown).map(n=>[n.props.title,n.props.value]),[['All Fonts','all'],['User Fonts Only','user']]);
  const itemProps=o.walk(screen).filter(n=>typeof n.type==='function'&&n.type===o.main.FontListItem).map(n=>n.props);
  assert.equal(itemProps.length,fonts.length);assert(itemProps.every(p=>p.previewText==='Sphinx of black quartz, judge my vow.'));
  // Each item gets its own isolated hook slots, as React does. Effects are local.
  let row=o.render(()=>o.main.FontListItem(itemProps[0]));row=o.render(()=>o.main.FontListItem(itemProps[0]));
  const actionNodes=o.walk(row.props.actions);const actions=actionNodes.filter(n=>/^Action\./.test(o.named(n))||o.named(n)==='Action').map(n=>({type:o.named(n),title:n.props.title,content:n.props.content,path:n.props.path,shortcut:n.props.shortcut}));
  assert.deepEqual(actions.map(a=>a.title||a.type),['Copy Font Name','Action.ShowInFinder','Show PostScript Names','Pin Font','Reload Font List']);
  const labels=o.walk(row.props.detail.props.metadata).filter(n=>o.named(n)==='List.Item.Detail.Metadata.Label').map(n=>[n.props.title,n.props.text]);
  assert.deepEqual(labels.map(x=>x[0]),['Type','Path','Styles','Pinned']);assert.equal(labels[2][1],'Regular');
  const md=row.props.detail.props.markdown;assert(md.startsWith('![Font preview](data:image/svg+xml;base64,'));const svg=Buffer.from(md.split(',')[1].slice(0,-1),'base64').toString();
  assert(svg.includes('width="600" height="300"'));assert.equal((svg.match(/<text /g)||[]).length,4);
  for(const y of [70,120,170,220])assert(svg.includes(`y="${y}"`));assert(svg.includes('font-size: 24px'));
  actionNodes.find(n=>n.props.title==='Copy Font Name').props.onCopy();assert.equal(o.logs.at(-1).title,'Font name copied');
  await itemProps[0].onTogglePin();assert(JSON.parse(o.storage.get('pinnedFonts')).includes(itemProps[0].font.name));
  // Fresh independent Command oracle for search/filter/pins, without row hook slots.
  const f=make(platform);let c=f.render(f.main.default);await f.settled();c=f.render(f.main.default);
  c.props.onSearchTextChange('USER');c=f.render(f.main.default);let matches=f.walk(c).filter(n=>n.type===f.main.FontListItem);assert(matches.every(n=>n.props.font.name.toLowerCase().includes('user')));
  c.props.onSearchTextChange('');c.props.searchBarAccessory.props.onChange('user');c=f.render(f.main.default);matches=f.walk(c).filter(n=>n.type===f.main.FontListItem);assert(matches.every(n=>!n.props.font.isSystem));
  const names=make(platform);let ns=names.render(()=>names.main.PostScriptNamesList({fontName:'Alpha',postScriptNames:['One','Two']}));ns.props.onSearchTextChange('absent');ns=names.render(()=>names.main.PostScriptNamesList({fontName:'Alpha',postScriptNames:['One','Two']}));assert.equal(names.children(ns)[0].props.title,'No matching PostScript names');
  const util=o.load('utils.ts');assert.deepEqual(o.plain(util.sortWeights(['bold','italic','thin','regular italic','Regular'])),['Thin','Regular','Bold','Italic','Regular Italic']);
  o.cache.set('installedFonts','not-json');await assert.rejects(()=>o.main.getFonts());
  report[platform].actions=actions;report[platform].labels=labels.map(([k,v])=>[k,k==='Path'?'[scoped font path]':v]);report[platform].svg=svg;report[platform].previews=['Sphinx of black quartz, judge my vow.','Unicode é Å 一','Different specimen'].map(text=>({text,markdown:o.load('fontPreview.ts').createFontPreviewSVG('QA Specimen',text)}));report[platform].checks=assertions-baseline;
 }
 fs.writeFileSync(path.join(ROOT,'evidence/v1-oracle.json'),JSON.stringify(report,null,2)+'\n');console.log('V1 closed VM:',assertions,'assertions across actual macOS/Windows source paths; effects denied/stubbed before callbacks');
})().catch(e=>{console.error(e);process.exitCode=1});
