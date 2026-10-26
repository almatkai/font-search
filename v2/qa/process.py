"""Real SDK JSONL pipes. Only owned fixture providers or a normal seeded V1-style
persistent cache in production smoke. Never invoke production Reload/discovery.
"""
import json,pathlib,subprocess,uuid,select,os,time,tempfile,sys,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]; QA=ROOT/'.qa';BIN=ROOT/'target/debug/font-search-qa';FONTS=QA/'fonts';MAX=16*1024*1024
checks=0
HOLD=object()
def check(v,msg='assertion'):
 global checks
 assert v,msg;checks+=1
class Pipe:
 def __init__(self,cmd,platform='macOS',seed=None):
  self.dir=pathlib.Path(tempfile.mkdtemp(prefix='pipes-',dir=QA));self.data=self.dir/'data';self.data.mkdir();self.temp=self.dir/'temp';self.temp.mkdir();self.buf=b'';self.err=b'';self.responses={};self.reverse=[]
  if seed is not None:
   cache=self.data/'font-search/installed-fonts.json';cache.parent.mkdir();cache.write_text(json.dumps(seed));check(cache.is_file(),'production requires owned seeded cache')
  self.p=subprocess.Popen([str(x) for x in cmd],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,env=dict(os.environ))
  hello=self.next();check(hello['type']=='hello' and hello['protocol']==1 and hello['sdkVersion']=='0.1.1' and hello['id']=='com.tezbar.native.font-search')
  r=self.rpc('initialize',{'protocol':1,'extensionId':'com.tezbar.native.font-search','platform':platform,'packageDir':str(ROOT),'dataDir':str(self.data),'tempDir':str(self.temp),'grantedCapabilities':['clipboard.write','shell.reveal']});check(r['result']['ready'])
 def send(self,m):self.p.stdin.write(json.dumps(m,separators=(',',':'),ensure_ascii=False).encode()+b'\n');self.p.stdin.flush()
 def request(self,m,p):
  i='h:'+str(uuid.uuid4());self.send({'type':'request','id':i,'method':m,'params':p});return i
 def next(self,timeout=10):
  deadline=time.monotonic()+timeout
  while b'\n' not in self.buf:
   remaining=deadline-time.monotonic();assert remaining>0,'protocol timeout'
   r,_,_=select.select([self.p.stdout],[],[],remaining);assert r,'protocol timeout';chunk=os.read(self.p.stdout.fileno(),65536)
   if not chunk:raise AssertionError('unexpected child EOF: '+self.p.stderr.read().decode())
   self.buf+=chunk
  line,self.buf=self.buf.split(b'\n',1);check(len(line)<=MAX,'outbound MAX_FRAME');return json.loads(line)
 def wait(self,i,reply={'ok':True}):
  while i not in self.responses:
   m=self.next()
   if m['type']=='response':self.responses[m['id']]=m
   elif m['type']=='request':
    self.reverse.append(m)
    if reply is not HOLD:self.send({'type':'response','id':m['id'],'result':reply})
   elif m['type']=='cancel':pass
   else:check(m['type']=='event')
  return self.responses.pop(i)
 def rpc(self,m,p,reply={'ok':True}):return self.wait(self.request(m,p),reply)
 def open(self,s='a',prefs=None,**extra):return self.rpc('session.open',{'sessionId':s,'commandName':'search-fonts','preferences':{} if prefs is None else prefs,'argumentValues':{},**extra})
 def call(self,s,op,p={},reply={'ok':True}):return self.rpc('session.call',{'sessionId':s,'operation':'extension:'+op,'payload':p},reply)
 def log_started(self):
  deadline=time.monotonic()+5
  while b'qa:discovery-start\n' not in self.err:
   r,_,_=select.select([self.p.stderr],[],[],max(0,deadline-time.monotonic()));assert r,'missing fixture discovery marker';self.err+=os.read(self.p.stderr.fileno(),8192)
  _,self.err=self.err.split(b'qa:discovery-start\n',1)
 def close(self):
  if self.p.poll() is None:
   self.p.stdin.close();self.p.wait(timeout=5)
  check(self.p.returncode==0,'clean process EOF')
def action(v,title):return next(a['id'] for a in v['actions'] if a['title']==title)
def result(r):check('result'in r,str(r));return r['result']
def rows(v):
 out=[]
 def walk(n):
  if n['type']=='List.Item':out.append(n)
  for c in n.get('children',[]):walk(c)
 walk(v['root']);return out
oracle=json.loads((ROOT/'evidence/v1-oracle.json').read_text())
# Full producer differential; both actual source root contracts and native shared scan.
for platform,flag,key in [('macOS','--catalog','darwin'),('Windows','--catalog-windows','win32')]:
 native=json.loads(subprocess.check_output([BIN,FONTS,flag]));check(native==oracle[key]['fonts'],'all fields/order/dedup paths differ from source '+platform)
 p=Pipe([BIN,FONTS],platform);v=result(p.open());check([r['props']['title'] for r in rows(v)]==[f['name'] for f in native]);check(v['refreshMs'] is None)
 detail=rows(v)[0]['children'][0];check(detail['metadata']['children'][2]['props']['text']=='Regular');check(detail['props']['markdown'].startswith('![Font preview](data:image/svg+xml;base64,'))
 # Native callback actions preserve exact copy/reveal payload and explicit ack.
 copy=action(v,'Copy Font Name');v=result(p.call('a','invoke-action',{'actionId':copy}));check(p.reverse[-1]['method']=='host.clipboard.write');check(p.reverse[-1]['params']=={'text':native[0]['name']});check(v['message']=='Font name copied')
 n=len(p.reverse);check(result(p.call('a','invoke-action',{'actionId':copy}))['mode']=='unchanged');check(len(p.reverse)==n)
 reveal=action(v,'Show in Finder');v=result(p.call('a','invoke-action',{'actionId':reveal}));check(p.reverse[-1]['method']=='host.shell.reveal' and p.reverse[-1]['params']=={'path':native[0]['path']})
 for bad in [None,True,False,{}, {'ok':False},{'ok':True,'message':False},{'ok':True,'error':'contradiction'},{'ok':True,'unknown':True}]:
  v=result(p.call('a','invoke-action',{'actionId':action(v,'Copy Font Name')},reply=bad));check('may duplicate'in v.get('message',''))
  v=result(p.call('a','invoke-action',{'actionId':action(v,'Dismiss Unknown Result')}))
 # Pin / nested names / search / back / persistent dropdown / deliberate Reload.
 v=result(p.call('a','invoke-action',{'actionId':action(v,'Pin Font')}));check(v['root']['children'][0]['props']['title']=='Pinned')
 v=result(p.call('a','invoke-action',{'actionId':action(v,'Show PostScript Names')}));check(v['title'].startswith('PostScript Names for '));v=result(p.call('a','invoke-action',{'actionId':action(v,'Copy PostScript Name')}));check(v['message']=='PostScript name copied')
 v=result(p.call('a','search-text-changed',{'searchText':'no match'}));check(v['root']['children'][0]['props']['title']=='No matching PostScript names');v=result(p.call('a','invoke-action',{'actionId':action(v,'Back')}))
 filt=v['root']['props']['searchBarAccessory']['props']['actionId'];v=result(p.call('a','invoke-action',{'actionId':filt,'formValues':{'value':'user'}}));check(all(not next(f for f in native if f['name']==r['props']['title'])['isSystem'] for r in rows(v)))
 v=result(p.call('a','invoke-action',{'actionId':action(v,'Reload Font List')}));check(v['root']['props']['fontCount']>0)
 # Ordinary refresh/search are effect free and the current draft fences old actions.
 before=len(p.reverse);v=result(p.call('a','search-text-changed',{'searchText':'A','__draft':{'revision':10,'searchText':'A','filter':'all','previewText':'immutable'}}));
 for rev,q,f in [(11,'B','all'),(12,'A','user'),(13,'A','invalid')]:v=result(p.call('a','search-text-changed',{'searchText':q,'__draft':{'revision':rev,'searchText':q,'filter':f}}))
 check(result(p.call('a','search-text-changed',{'searchText':'B','__draft':{'revision':11,'searchText':'B','filter':'all'}}))['mode']=='unchanged');v=result(p.call('a','refresh-session'));check(v['root']['props']['draftRevision']==13 and v['root']['props']['searchText']=='A');check(len(p.reverse)==before)
 p.rpc('session.dispose',{'sessionId':'a'});check('error'in p.call('a','refresh-session'));p.close()
# Cancellation/late response/queued old IDs/unknown retry, real SDK rollback.
p=Pipe([BIN,FONTS]);v=result(p.open());copy=action(v,'Copy Font Name');original=rows(v)[0]['props']['title']
i=p.request('session.call',{'sessionId':'a','operation':'extension:invoke-action','payload':{'actionId':copy}})
while True:
 m=p.next()
 if m['type']=='request':p.reverse.append(m);reverse=m;break
queued=p.request('session.call',{'sessionId':'a','operation':'extension:invoke-action','payload':{'actionId':copy}})
p.send({'type':'cancel','requestId':i,'reason':'owned QA cancel'});check('error'in p.wait(i,reply=HOLD));check(result(p.wait(queued,reply=HOLD))['mode']=='unchanged')
p.send({'type':'response','id':reverse['id'],'result':{'ok':True}})
v=result(p.call('a','refresh-session'));check('may duplicate'in v.get('message',''))
v=result(p.call('a','search-text-changed',{'searchText':'changed'}));v=result(p.call('a','invoke-action',{'actionId':action(v,'Retry Frozen Action (may duplicate)')}));check(p.reverse[-1]['params']=={'text':original})
v=result(p.call('a','search-text-changed',{'searchText':''}));new=action(v,'Copy Font Name');check(new!=copy)
other=result(p.open('other'));count=len(p.reverse);check(result(p.call('other','invoke-action',{'actionId':new}))['mode']=='unchanged');check(len(p.reverse)==count)
p.close()
# 140 cancelled opens entered the real adapter/provider, without dispose. Then
# the full 128-session SDK/adapter capacity must remain available.
p=Pipe([BIN,FONTS,'--slow'])
for n in range(140):
 i=p.request('session.open',{'sessionId':'cancel-'+str(n),'commandName':'search-fonts','preferences':{},'argumentValues':{}});p.log_started();p.send({'type':'cancel','requestId':i});check('error'in p.wait(i))
for n in range(128):check(result(p.open('live-'+str(n)))['mode']=='view')
check('error'in p.open('overflow'))
for n in range(128):result(p.rpc('session.dispose',{'sessionId':'live-'+str(n)}))
check(result(p.open('after-capacity'))['mode']=='view');p.close()
# Incoming exact 16 MiB event accepted; 16 MiB + 1 rejected by actual SDK reader.
p=Pipe([BIN,FONTS]);base=json.dumps({'type':'event','event':'qa','data':''},separators=(',',':')).encode();frame=base[:-2]+b'x'*(MAX-len(base))+base[-2:];check(len(frame)==MAX);p.p.stdin.write(frame+b'\n');p.p.stdin.flush();check(result(p.open())['mode']=='view');p.close()
p=Pipe([BIN,FONTS]);p.p.stdin.write(frame+b' '+b'\n');p.p.stdin.flush();p.p.stdin.close();p.p.wait(timeout=5);check(p.p.returncode!=0,'oversize frame must fail')
# Independent genuine font parsing: TTF, CFF OTF, TTC, decoded WOFF and WOFF2.
for f in ['fixture.ttf','fixture.otf','fixture.ttc','decoded-woff.ttf','decoded-woff2.ttf']:
 parsed=[json.loads(l) for l in subprocess.check_output([BIN,QA/'generated-fonts'/f,'--parse'],text=True).splitlines()];check(all(x['hasA']and x['unitsPerEm']==1000 and x['glyphs']>90 for x in parsed));check(len(parsed)==(2 if f.endswith('ttc')else 1))
bad=subprocess.run([BIN,FONTS/'user/bad.ttf','--parse'],capture_output=True);check(bad.returncode!=0)
# Production/extracted process smoke via the normal persisted catalog, no provider
# hooks/endpoints/environment overrides. Reload remains restricted to QA binary.
if '--production' in sys.argv:
 prod=pathlib.Path(sys.argv[sys.argv.index('--production')+1]);seed=oracle['darwin']['fonts'];p=Pipe([prod],seed=seed);v=result(p.open(prefs={'previewText':'Owned production cache specimen'}));check(len(rows(v))==len(seed));v=result(p.call('a','invoke-action',{'actionId':action(v,'Copy Font Name')}));check(v['message']=='Font name copied');p.close()
(ROOT/'evidence/process.json').write_text(json.dumps({'checks':checks,'canceledOpens':140,'simultaneousSessions':128,'frameBytes':MAX,'nativeOSFontEnumeration':'not-run','realHostGUI':'not-run','productionSmoke':'normal owned seeded cache'if '--production'in sys.argv else 'pending release smoke'},indent=2)+'\n');print('Real SDK pipes:',checks,'checks; 140 cancelled opens; full 128-session capacity')
