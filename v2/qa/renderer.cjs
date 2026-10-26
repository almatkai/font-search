'use strict';
// Actual pinned ListRuntime/Markdown/ExtensionRuntimeView and patched index.
// Only unrelated components and all desktop services are stubbed BEFORE render.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),QA=path.join(ROOT,'.qa'),mods=path.join(QA,'tools/node_modules');
const esbuild=require(path.join(mods,'esbuild'));const {JSDOM}=require(path.join(mods,'jsdom'));
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'https://owned.invalid/',pretendToBeVisual:true});
// JSDOM has no resource loader: no fonts, images, network or OS APIs are loaded.
Object.assign(global,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,Element:dom.window.Element,DOMParser:dom.window.DOMParser,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true});
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});dom.window.HTMLElement.prototype.scrollIntoView=function(){};
const React=require(path.join(mods,'react')), {act}=React, {createRoot}=require(path.join(mods,'react-dom/client'));
let checks=0;const ck=(condition,msg)=>{assert(condition,msg);checks++};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve}};
const stubs={
 primitives:`const React=require('react');const c=({children})=>React.createElement('div',null,children);export const Button=c,Message=c,Hint=c,HintBar=c,Kbd=c;export const cx=(...s)=>s.filter(Boolean).join(' ');export const ViewHeader=({title,onBack})=>React.createElement('header',null,title,React.createElement('button',{onClick:onBack},'Back'));`,
 detail:`const React=require('react');export const DetailRuntime=()=>null;export const MetadataItem=({node})=>React.createElement('p',null,node.props?.title+': '+node.props?.text);export const MetadataSidebar=({root})=>React.createElement('aside',null,root.children?.map((node,i)=>React.createElement(MetadataItem,{key:i,node})));`,
 action:`export const Action=()=>null,ActionPanel=()=>null,ActionPanelOverlay=()=>null;`,
 registry:`const React=require('react');export const ActionRegistryContext=React.createContext({actions:[]});`,
 hooks:`const React=require('react');export const NavigationContext=React.createContext({});export const setRuntimeContext=()=>{};export const Clipboard={},environment={},getPreferenceValues=()=>({}),open=()=>{throw Error('OS denied')},showHUD=()=>{},showToast=()=>{},useCachedPromise=()=>{},useFetch=()=>{},useNavigation=()=>{},usePromise=()=>{};`,
 form:`export const FormRuntime=()=>null;`,grid:`export const GridRuntime=()=>null;`,
 refresh:`export const startSessionRefresh=(options)=>{globalThis.__qaRefresh=options.refresh;return()=>{}};`,
};
const mapping=[[/ui\/primitives$/,'primitives'],[/\/detail-runtime$/,'detail'],[/\/action-runtime$/,'action'],[/\/action-runtime-registry$/,'registry'],[/\/hooks$/,'hooks'],[/\/form-runtime$/,'form'],[/\/grid-runtime$/,'grid'],[/extensionSessionRefresh$/,'refresh']];
(async()=>{
 const patchRoot=path.join(QA,'host-patched');
 // Build in memory; only QA source and package dependencies can be resolved.
 const built=await esbuild.build({stdin:{contents:`import View from './src/renderer/ExtensionRuntimeView';export {View};`,resolveDir:patchRoot,sourcefile:'owned-entry.tsx',loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',nodePaths:[mods],external:['react','react-dom','react/jsx-runtime'],plugins:[{name:'closed-host-harness',setup(b){b.onResolve({filter:/.*/},args=>{const m=mapping.find(([re])=>re.test(args.path));if(m)return{path:m[1],namespace:'stub'};if(args.path==='./src/raycast-api')return{path:path.join(patchRoot,'src/renderer/src/raycast-api/index.tsx')};return null});b.onLoad({filter:/.*/,namespace:'stub'},a=>({contents:stubs[a.path],loader:'tsx'}));}}]});
 const bundle=path.join(QA,'tools/renderer-bundle.cjs');fs.writeFileSync(bundle,built.outputFiles[0].contents);const {View}=require(bundle);
 const specimen=JSON.parse(fs.readFileSync(path.join(ROOT,'evidence/v1-oracle.json'))).darwin.previews[0].markdown;
 function view(search='',filter='all',revision=0,owner='s:g'){
  const [sessionId,generation]=owner.split(':');return{ok:true,mode:'view',sessionId,generation,extensionId:'com.tezbar.native.font-search',commandName:'search-fonts',title:'Search Fonts',refreshMs:null,
   actions:[{id:'copy-'+revision,title:'Copy Font Name',kind:'copy'},{id:'filter',title:'Filter',kind:'action'}],root:{type:'List',props:{__hasServerSearch:true,searchText:search,searchBarPlaceholder:'Search fonts...',inputDraft:{revision,searchText:search,filter,previewText:'Sphinx of black quartz, judge my vow.'},searchBarAccessory:{type:'List.Dropdown',props:{actionId:'filter',value:filter},children:[{type:'List.Dropdown.Item',props:{title:'All Fonts',value:'all'}},{type:'List.Dropdown.Item',props:{title:'User Fonts Only',value:'user'}}]}},children:[{type:'List.Section',props:{title:'All'},children:[{type:'List.Item',props:{id:'qa-font',title:'QA Specimen',actionIds:['copy-'+revision]},children:[{type:'List.Item.Detail',props:{markdown:specimen},metadata:{type:'List.Item.Detail.Metadata',children:[{type:'List.Item.Detail.Metadata.Label',props:{title:'Styles',text:'Regular'}}]}}]}]}]}};
 }
 const searches=[],actions=[],refreshes=[];let disposed=0;
 window.tezbar={extensionSearchTextChanged:p=>{const d=deferred();searches.push({p,...d});return d.promise},extensionInvokeAction:p=>{const d=deferred();actions.push({p,...d});return d.promise},extensionRefreshSession:p=>{const d=deferred();refreshes.push({p,...d});return d.promise},extensionDisposeSession:async()=>{disposed++},onExtensionSessionInvalidated:()=>()=>{},onWindowVisibility:()=>()=>{},getAssetIconDataUrl:async()=>null,getAppIconDataUrl:async()=>null,clipboardWriteText:()=>{throw Error('clipboard denied')}};
 const root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(View,{initial:view(),onBack:()=>{}})));
 const input=()=>document.querySelector('input[placeholder="Search fonts..."]');
 const edit=async text=>{await act(async()=>{Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(input(),text);input().dispatchEvent(new window.Event('input',{bubbles:true}));input().dispatchEvent(new window.Event('change',{bubbles:true}));});};
 const tick=async()=>{await act(async()=>{await new Promise(r=>setTimeout(r,230))})};
 const click=async title=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent===title);assert(b,'missing '+title);await act(async()=>b.click())};
 ck(document.querySelector('img')?.getAttribute('src')===specimen.split('](')[1].slice(0,-1),'actual Markdown retains preview data URI');ck(document.body.textContent.includes('Styles: Regular'),'actual List detail metadata reaches sidebar');
 // A response outstanding, then B->A before debounce: old A cannot own edit A.
 await edit('A');await tick();ck(searches.length===1,'A dispatch');const old=searches[0];
 await edit('B');await edit('A');await act(async()=>old.resolve(view('OLD','all',old.p.__draft.revision)));ck(input().value==='A','A/B/A old result rejected before debounce');
 await tick();ck(searches.length===2,'new revision dispatch even equal string');ck(searches[1].p.__draft.revision>old.p.__draft.revision,'monotonic complete drafts');
 await act(async()=>searches[1].resolve(view('A','all',searches[1].p.__draft.revision)));
 // Pending refresh and action must lose ownership to any local edit.
 let refreshPromise;await act(async()=>{refreshPromise=global.__qaRefresh()});
 const row=()=>document.querySelector('[data-idx="0"]');await act(async()=>row().click());ck(actions.length===1,'actual index forwarded action');
 await edit('invalid\u0000draft');await act(async()=>{refreshes[0].resolve(view('stale refresh'));actions[0].resolve(view('stale action'))});await refreshPromise;ck(input().value==='invalid\u0000draft','invalid intermediate fences refresh and action');
 // Dropdown transmits a complete current search and preserves pending edits.
 await click('User Fonts Only');ck(actions.at(-1).p.formValues.__draft.searchText==='invalid\u0000draft','dropdown current query');ck(actions.at(-1).p.formValues.__draft.filter==='user','dropdown current filter');ck(actions.at(-1).p.formValues.__draft.previewText==='Sphinx of black quartz, judge my vow.','immutable preview preference retained');
 await act(async()=>actions.at(-1).resolve(view('invalid\u0000draft','user',actions.at(-1).p.formValues.__draft.revision)));
 await edit('');await tick();let latest=searches.at(-1);await act(async()=>latest.resolve(view('','user',latest.p.__draft.revision)));
 ck([...document.querySelectorAll('button')].find(b=>b.textContent==='User Fonts Only').className.includes('bg-white/[0.14]'),'controlled saved dropdown value');
 // Stale action unchanged must not create a fallback Copied notice or corrupt root.
 await act(async()=>row().click());await act(async()=>actions.at(-1).resolve({ok:true,mode:'unchanged'}));ck(!document.body.textContent.includes('Copied to clipboard'),'unchanged is effect-free');ck(input()!==null,'unchanged keeps current view');
 // Changing process/session owner makes late callbacks inert.
 await edit('late');await tick();latest=searches.at(-1);await act(async()=>root.render(React.createElement(View,{initial:view('new','all',0,'next:g2'),onBack:()=>{}})));await act(async()=>latest.resolve(view('wrong session')));ck(input().value==='new','cross-session old response ignored');
 await act(async()=>root.unmount());await new Promise(r=>setTimeout(r,10));ck(disposed>=1,'unmount disposes owned session');
 fs.writeFileSync(path.join(ROOT,'evidence/renderer.json'),JSON.stringify({checks,pin:'ea100cee3f69711de12485ba061950c5fc65258f',patchAppliedTo:'owned .qa copies only',actual:['ListRuntime','Markdown (marked + DOMPurify)','ExtensionRuntimeView','ExtensionRuntimeSurface'],stubs:['unrelated Form/Grid/Detail components','desktop services','refresh scheduler','decorative primitives'],fontOrImageOSAPIs:'not invoked; JSDOM resource loading disabled'},null,2)+'\n');console.log('Actual pinned/patched renderer:',checks,'checks');
})().catch(e=>{console.error(e);process.exitCode=1});
