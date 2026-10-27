#!/usr/bin/env python3
"""Maintainer helper: lock exact QA versions to authentic PyPI release hashes.
Ordinary verify uses the resulting lock, never resolves new package versions.
"""
import json,pathlib,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1];lines=['# Exact QA dependencies; authentic published PyPI artifact SHA256 values.'];records=[]
for line in (ROOT/'qa/requirements.txt').read_text().splitlines():
 if not line or line.startswith('#'):continue
 name,version=line.split('==');url=f'https://pypi.org/pypi/{name}/{version}/json'
 with urllib.request.urlopen(url,timeout=30)as r:data=json.load(r)
 files=sorted(data['urls'],key=lambda f:f['filename']);assert files
 lines.append(f'{name}=={version} \\')
 for i,file in enumerate(files):lines.append('    --hash=sha256:'+file['digests']['sha256']+(' \\'if i+1<len(files)else''))
 records.append({'name':name,'version':version,'metadataURL':url,'artifacts':[{'filename':f['filename'],'url':f['url'],'sha256':f['digests']['sha256']}for f in files]})
(ROOT/'qa/requirements.lock').write_text('\n'.join(lines)+'\n');(ROOT/'evidence/python-dependencies.json').write_text(json.dumps({'purpose':'QA-only; not packaged','packages':records},indent=2)+'\n');print('Hash-locked',len(records),'QA Python packages')
