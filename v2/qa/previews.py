import pathlib,json,base64,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'.qa';BIN=ROOT/'target/debug/font-search-qa';OUT=QA/'previews';OUT.mkdir(exist_ok=True)
source=json.loads((ROOT/'evidence/v1-oracle.json').read_text())['darwin']['previews'];results=[]
for i,case in enumerate(source):
 v1=base64.b64decode(case['markdown'].split(',')[1][:-1]);v2=subprocess.check_output([BIN,QA/'fonts','--svg','QA Specimen',case['text']]).strip()
 images=[]
 for name,svg in [('v1',v1),('v2',v2)]:
  p=OUT/f'{name}-{i}.svg';p.write_bytes(svg);png=OUT/f'{name}-{i}.png'
  result=json.loads(subprocess.check_output([BIN,QA/'generated-fonts/fixture.ttf','--render',p,png]));assert result['fonts']==1 and result['systemFontsLoaded'] is False;images.append(png.read_bytes())
 assert images[0]==images[1],'Native renderer specimen pixels differ from actual V1 source'
 results.append({'text':case['text'],'sha256':hashlib.sha256(images[1]).hexdigest(),'rasterBytes':len(images[1]),**result})
assert len({r['sha256'] for r in results})==3,'Text variations must alter actual rendered outlines'
(ROOT/'evidence/previews.json').write_text(json.dumps({'renderer':'resvg 0.45.1; fontdb initially empty; owned generated TTF loaded only','comparisons':results,'nativeInstalledFontGUI':'not-run'},indent=2)+'\n');print('Preview QA: 3 actual V1/native SVG pairs render pixel-identically with owned glyphs; 0 system fonts loaded')
