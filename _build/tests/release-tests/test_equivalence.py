import sys,json,hashlib,zipfile,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'src'),'E:/四維八德/_build/vendor']
import engine as E,pymupdf
E.FFMPEG='E:/四維八德/tools/ffmpeg.exe'
DATA=ROOT/'windows-engine-checks';results=[]
def media(path):
 r=E.run([E.FFMPEG,'-hide_banner','-v','error','-i',str(path),'-map','0:v:0?','-map','0:a:0?','-f','framemd5','-'],timeout=120)
 assert not r.returncode,r.stderr
 return '\n'.join(l for l in r.stdout.splitlines() if not l.startswith('#'))
def pdf(path):
 with pymupdf.open(path) as d:return [(p.rect,hashlib.sha256(p.get_pixmap().samples).hexdigest(),p.get_text()) for p in d]
def textzip(path):
 with zipfile.ZipFile(path) as z:
  return sorted((n,re.sub(r'\s+',' ',z.read(n).decode('utf-8'))) for n in z.namelist() if n.endswith(('.xhtml','html')) or n=='word/document.xml')
for record in json.loads((DATA/'results.json').read_text(encoding='utf-8')):
 if 'target' not in record:continue
 name=record['name'];t=record['target'];a=sorted((DATA/'C'/name).iterdir());b=sorted((DATA/'Python'/name).iterdir())
 try:
  assert record['ok'] and a and b,record
  c,p=max(a,key=lambda f:f.stat().st_mtime_ns),max(b,key=lambda f:f.stat().st_mtime_ns)
  if name=='size_cap':
   assert c.stat().st_size <= .15*1048576 and p.stat().st_size <= .15*1048576,'Capacity cap exceeded'
   ca,pa=media(c),media(p)
   assert [l.rsplit(',',1)[0] for l in ca.splitlines()]==[l.rsplit(',',1)[0] for l in pa.splitlines()],'Frame count/timing differs'
  elif t in ('mp4','mkv','webm','mov','avi','gif','mp3','m4a','wav','flac','ogg','opus'):assert media(c)==media(p),'Decoded frames/audio differ'
  elif t=='pdf':assert pdf(c)==pdf(p),'PDF pixels/text differ'
  elif t in ('epub','docx'):assert textzip(c)==textzip(p),'Document content differs'
  elif t=='7z':
   from tempfile import TemporaryDirectory
   with TemporaryDirectory() as ca,TemporaryDirectory() as pb:
    for src,dest in [(c,ca),(p,pb)]:
     rr=E.run(['E:/四維八德/tools/7z.exe','x','-y','-o'+dest,str(src)]);assert not rr.returncode,rr.stderr
    def contents(folder):return sorted((str(f.relative_to(folder)),f.read_bytes()) for f in Path(folder).rglob('*') if f.is_file())
    assert contents(ca)==contents(pb),'Extracted archive payload differs'
  elif t=='extract':assert record['equal_bytes'],'Extracted content differs'
  else:assert c.read_bytes()==p.read_bytes(),'Text differs'
  results.append(dict(name=name,ok=True,check='decoded media / rendered PDF / document text / archive content'))
 except Exception as ex:results.append(dict(name=name,ok=False,error=str(ex)))
 print(json.dumps(results[-1],ensure_ascii=False),flush=True)
(DATA/'equivalence.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASSED',sum(r['ok'] for r in results),'/',len(results));sys.exit(not all(r['ok'] for r in results))
