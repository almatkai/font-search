"""Extract actual pinned Rust producer arms. Stub OS calls before executing them.
Compile platform branches as independent owned-function tests on this machine.
"""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];PIN=ROOT/'.qa/pinned/host/src-tauri/src/native_core';checks={}
def source(p):return(PIN/p).read_text()
def part(s,a,b):
 x=s[s.index(a):s.index(b,s.index(a))];checks[a.strip()]={'sha256':hashlib.sha256(x.encode()).hexdigest()};return x
native=source(Path('extensions/native.rs'))
forward=re.search(r'json!\(\{"sessionId":id,"operation":channel,"payload":body\}\)',native).group(0)
checks['native payload forwarding']={'sha256':hashlib.sha256(forward.encode()).hexdigest()}
host=source(Path('extensions/process_host.rs'));clipboard=source(Path('launcher/clipboard.rs'));platform=source(Path('platform.rs'))
write=part(host,'            "host.clipboard.write"=>{','            "host.clipboard.writeImage"=>')
reveal=part(host,'            "host.shell.reveal"=>','            "host.selection.read"=>')
helper=part(host,"fn string<'a>", 'fn background_path')
clip=part(clipboard,'            "clipboard:write" => {','            "clipboard:write-png" => {')
rev=part(platform,'            "core:platform:reveal-file" => {','            _ => Err(format!("Unknown platform operation: {channel}")),')
# Platform source deliberately compiled twice; only terminal OS edges are stubs.
rev=rev.replace('#[cfg(target_os = "macos")]','#[cfg(feature = "qa-host-macos")]').replace('#[cfg(target_os = "windows")]','#[cfg(feature = "qa-host-windows")]').replace('#[cfg(not(any(target_os = "macos", target_os = "windows")))]','#[cfg(any())]').replace('tokio::process::Command','OwnedCommand')
code='''use serde_json::{json,Value};
use std::sync::{Arc,Mutex};
type CoreResult=Result<Value,String>;
type Calls=Arc<Mutex<Vec<(String,Vec<Value>)>>>;
#[derive(Default,Clone)]struct Core { calls:Calls }
impl Core {async fn request(&self,c:&str,a:Vec<Value>)->CoreResult { self.calls.lock().unwrap().push((c.into(),a));Ok(json!({"ok":true})) }}
struct Host {ctx:Core}
impl Host {async fn request(&self,method:&str,params:Value)->CoreResult {match method {
'''+write+reveal+'''_=>Err("unsupported".into())}}}
'''+helper+'''
struct Clipboard {text:String}
impl Clipboard {fn write_text(&mut self,text:String)->Result<(),String>{self.text=text;Ok(())}
fn handle(&mut self,c:&str,a:&[Value])->CoreResult{match c {
'''+clip+'''_=>Err("unsupported".into())}}}
fn text_arg(a:&[Value],i:usize)->Result<&str,String>{a.get(i).and_then(Value::as_str).ok_or("invalid text".into())}
#[cfg(feature="qa-host-macos")]
async fn output(program:&str,args:&[&str],timeout:u64)->Result<(),String>{assert_eq!(program,"/usr/bin/open");assert_eq!(args,["-R","/owned/QA Font.ttf"]);assert_eq!(timeout,10);Ok(())}
#[cfg(feature="qa-host-windows")]
struct OwnedCommand{program:String,args:Vec<String>,flags:u32}
#[cfg(feature="qa-host-windows")]
impl OwnedCommand{fn new(p:&str)->Self{Self{program:p.into(),args:Vec::new(),flags:0}}fn arg(&mut self,a:String)->&mut Self{self.args.push(a);self}fn creation_flags(&mut self,f:u32)->&mut Self{self.flags=f;self}fn spawn(&self)->std::io::Result<()>{assert_eq!(self.program,"explorer.exe");assert_eq!(self.args,["/select,/owned/QA Font.ttf"]);assert_eq!(self.flags,0x08000000);Ok(())}}
#[cfg(any(feature="qa-host-macos",feature="qa-host-windows"))]
async fn platform_reveal(text:&str)->CoreResult{match "core:platform:reveal-file" {
'''+rev+'''_=>unreachable!()}}
#[tokio::test]async fn actual_host_dispatch_and_clipboard_ack(){let h=Host{ctx:Core::default()};
assert_eq!(h.request("host.clipboard.write",json!({"text":"Frozen A"})).await.unwrap(),json!({"ok":true}));
assert_eq!(h.ctx.calls.lock().unwrap()[0],("clipboard:write".into(),vec![json!("Frozen A")]));
assert_eq!(h.request("host.shell.reveal",json!({"path":"/owned/QA Font.ttf"})).await.unwrap(),json!({"ok":true}));
assert_eq!(h.ctx.calls.lock().unwrap()[1],("core:platform:reveal-file".into(),vec![json!("/owned/QA Font.ttf")]));
assert!(h.request("host.clipboard.write",json!({"text":false})).await.is_err());
let mut c=Clipboard{text:String::new()};assert_eq!(c.handle("clipboard:write",&[json!("Frozen A")]).unwrap(),json!({"ok":true}));assert_eq!(c.text,"Frozen A");}
#[cfg(any(feature="qa-host-macos",feature="qa-host-windows"))]
#[tokio::test]async fn actual_reveal_producer_ack(){assert_eq!(platform_reveal("/owned/QA Font.ttf").await.unwrap(),json!({"ok":true}));}
'''
code+='\n#[test]fn actual_native_payload_forwarding(){let id="owned-session";let channel="extension:search-text-changed";let body=json!({"searchText":"A","__draft":{"revision":3,"searchText":"A","filter":"user","previewText":"Owned"}});let routed=' +forward+';assert_eq!(routed["payload"],body);assert_eq!(routed["sessionId"],id);assert_eq!(routed["operation"],channel); }\n'
(ROOT/'.qa/generated-host-contracts.rs').write_text(code)
(ROOT/'evidence/host-producers.json').write_text(json.dumps({'hostRevision':'ea100cee3f69711de12485ba061950c5fc65258f','extractedArms':checks,'OSCalls':'stubbed before execution; actual macOS/Windows producers not run','usedCapabilities':['clipboard.write','shell.reveal']},indent=2)+'\n')
