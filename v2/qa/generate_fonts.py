"""Entirely new geometric test outlines. Output inherits this repository's MIT grant.
No input system/commercial fonts or third-party outlines. Stable head timestamps.
"""
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont, TTCollection
import hashlib, json, shutil
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'.qa/generated-fonts';OUT.mkdir(parents=True,exist_ok=True)
CHARS=list(range(32,127))+[0x00e9,0x212b,0x4e00]
GLYPHS=['.notdef']+['u%04X'%c for c in CHARS]
def outline(p, c):
 if c==32:return
 # Rectilinear, original asymmetric shapes; shape differs per character.
 w=180+(c%9)*36
 p.moveTo((60,0));p.lineTo((60,600));p.lineTo((w,600));p.lineTo((w,500));p.lineTo((140,500));p.lineTo((140,0));p.closePath()
 if c%2:p.moveTo((180,0));p.lineTo((w,0));p.lineTo((w,200));p.lineTo((180,200));p.closePath()
def build(ttf):
 fb=FontBuilder(1000,isTTF=ttf);fb.setupGlyphOrder(GLYPHS);fb.setupCharacterMap({c:g for c,g in zip(CHARS,GLYPHS[1:])})
 if ttf:
  glyphs={}
  for i,g in enumerate(GLYPHS):
   pen=TTGlyphPen(None);outline(pen,CHARS[i-1] if i else 0);glyphs[g]=pen.glyph()
  fb.setupGlyf(glyphs)
 else:
  strings={}
  for i,g in enumerate(GLYPHS):
   pen=T2CharStringPen(600,None);outline(pen,CHARS[i-1] if i else 0);strings[g]=pen.getCharString()
  fb.setupCFF('QASpecimen-Regular',{'FullName':'QA Specimen Regular','FamilyName':'QA Specimen','Weight':'Regular'},strings,{})
 fb.setupHorizontalMetrics({g:(600,0) for g in GLYPHS});fb.setupHorizontalHeader(ascent=800,descent=-200)
 fb.setupNameTable({'familyName':'QA Specimen','styleName':'Regular','uniqueFontIdentifier':'font-search-generated-geometric-v1','fullName':'QA Specimen Regular','psName':'QASpecimen-Regular','version':'Version 1.000','licenseDescription':'Generated from original geometric test outlines under the repository MIT license.'})
 fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp()
 fb.font['head'].created=fb.font['head'].modified=3406620154;fb.font.recalcTimestamp=False
 fb.save(OUT/('fixture.ttf' if ttf else 'fixture.otf'))
build(True);build(False)
for flavor in ['woff','woff2']:
 font=TTFont(OUT/'fixture.ttf',recalcTimestamp=False);font.flavor=flavor;font.save(OUT/('fixture.'+flavor))
coll=TTCollection();coll.fonts=[TTFont(OUT/'fixture.ttf',recalcTimestamp=False),TTFont(OUT/'fixture.otf',recalcTimestamp=False)];coll.save(OUT/'fixture.ttc')
# Genuine WOFF/WOFF2 decoded back to SFNT for the independent native parser.
for flavor in ['woff','woff2']:
 font=TTFont(OUT/('fixture.'+flavor),recalcTimestamp=False);font.flavor=None;font.save(OUT/('decoded-'+flavor+'.ttf'))
files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file()}
(ROOT/'evidence/generated-fonts.json').write_text(json.dumps({'generator':'qa/generate_fonts.py','grant':'Repository MIT LICENSE; wholly new geometric outlines, no source fonts','files':files},indent=2)+'\n')
TREE=ROOT/'.qa/fonts'
for d in ['system-a','system-b','user','user/nested-a','user/nested-z']:(TREE/d).mkdir(parents=True,exist_ok=True)
layout={'system-a':['Alpha_Regular.ttf','QA-Specimen.ttf','Éclair.otf','.Hidden.ttf','digits-10.TTF','Digits-2.ttf','A---__B.ttf'],'system-b':['Alpha_Regular.ttf','Beta.woff'],'user':['Alpha_Regular.ttf','user_font.woff2','Collection.ttc','bad.ttf','NoFont.txt','日本語.ttf','éclair.ttf'],'user/nested-a':['Nested-A.ttf'],'user/nested-z':['Nested-Z.ttf']}
for d,files in layout.items():
 for f in files:
  ext=f.rsplit('.',1)[-1].lower();p=TREE/d/f
  p.write_bytes((OUT/('fixture.'+ext)).read_bytes() if ext in ['ttf','otf','woff','woff2','ttc'] else b'not a font')
(TREE/'user/bad.ttf').write_bytes(b'malformed font: V1 lists this filename without parsing')
print(json.dumps({'formats':list(files),'fontTree':str(TREE)}))
