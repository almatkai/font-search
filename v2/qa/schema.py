import json,copy,pathlib,sys,zipfile
from jsonschema import Draft202012Validator,FormatChecker
ROOT=pathlib.Path(__file__).resolve().parents[1];schema=json.loads((ROOT/'.qa/pinned/host/schemas/extension-v3.schema.json').read_text());v=Draft202012Validator(schema,format_checker=FormatChecker());m=json.loads((ROOT/'extension.json').read_text());v.validate(m)
negative=[]
for key,value in [('schemaVersion',2),('execution','in-process'),('runtime','javascript'),('protocolVersion',2),('id','com.tezbar.font-search'),('id','com.tezbar.native../font-search'),('artifacts',{'Linux':{}}),('artifacts',{'aarch64-apple-darwin':{'url':'file:///tmp/fake','sha256':'0'*64,'executable':'../bin/font-search','executableSha256':'0'*64}}),('capabilities',['process.exec']),('capabilities',['clipboard.write','clipboard.write']),('files',{'../outside':'0'*64}),('files',{'bin/file':'bad'}),('surprise',True),('verification',[{'platform':'macOS','state':'accepted'}])]:
 x=copy.deepcopy(m);x[key]=value;assert list(v.iter_errors(x)),(key,value);negative.append(key)
for key in schema['required']:
 x=copy.deepcopy(m);del x[key];assert list(v.iter_errors(x));negative.append('missing '+key)
x=copy.deepcopy(m);x['commands'][0]['refreshMs']=100;assert list(v.iter_errors(x));negative.append('refreshMs')
assert m['artifacts']=={} and all(x['state']=='not-run'for x in m['verification']);assert len(m['commands'])==1 and m['commands'][0]['name']=='search-fonts';assert m['preferences'][0]['default']=='Sphinx of black quartz, judge my vow.'
positives=1
if len(sys.argv)>1:
 with zipfile.ZipFile(sys.argv[1])as z:v.validate(json.loads(z.read('extension.json')));positives+=1
(ROOT/'evidence/schema.json').write_text(json.dumps({'draft':'2020-12 full pinned schema','hostRevision':'ea100cee3f69711de12485ba061950c5fc65258f','positive':positives,'negative':len(negative),'negativeCases':negative},indent=2)+'\n');print('Full pinned schema:',positives,'positive,',len(negative),'negatives')
