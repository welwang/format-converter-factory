import sys,os,json,subprocess,threading,queue,time
from pathlib import Path
R=Path(__file__).resolve().parent;sys.path[:0]=[str(R/'src'),'E:/四維八德/_build/vendor'];import engine as E
B='E:/四維八德';E.FFMPEG=B+'/tools/ffmpeg.exe';D=R/'native-option-checks';D.mkdir(exist_ok=True)
p=subprocess.Popen([str(R/'shell/out/engine-test.exe'),B,str(D)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=E.NOWIN)
p.stdin.write(json.dumps(dict(base=B,data=str(D)),ensure_ascii=False)+'\n');p.stdin.flush();q=queue.Queue()
def read():
 for line in p.stdout:q.put(json.loads(line))
threading.Thread(target=read,daemon=True).start()
def call(m,**kw):p.stdin.write(json.dumps(dict(m=m,**kw),ensure_ascii=False)+'\n');p.stdin.flush();return q.get(timeout=40)
def wait(ids):
 end=time.monotonic()+120
 while time.monotonic()<end:
  jobs=[j for j in call('status') if j['id'] in ids]
  if len(jobs)==len(ids) and all(j['state'] not in ('queued','running') for j in jobs):return jobs[0]
  time.sleep(.04)
 raise TimeoutError(ids)
records=[];video=R/'windows-engine-checks/中文 素材/影片 測試.mp4'
for name,target,opt,expected in [('hevc','mp4',{'codec':'hevc'},'hevc'),('av1','mp4',{'codec':'av1'},'av1'),('gpu_or_cpu_fallback','mp4',{'hwaccel':True},'h264'),('lossless_container_copy','mkv',{'fastcopy':True},'h264'),('audio_copy','m4a',{},'aac'),('full_decode_validation','mp4',{'verify_full':True},'h264')]:
 try:
  out=D/name;out.mkdir(exist_ok=True);opts=dict(out_dir=str(out),preset='balanced',hwaccel=False,fastcopy=False,resource_mode='quiet');opts.update(opt)
  j=wait(call('start',files=[str(video)],target=target,opt=opts));assert j['state']=='done',j
  info=E.probe_info(j['output']);assert expected in [s[1] for s in info['streams']],info
  ff=E.run([E.FFMPEG,'-hide_banner','-v','error','-i',j['output'],'-f','null','-'],timeout=120);assert not ff.returncode,ff.stderr
  records.append(dict(name=name,ok=True,encoder=j['encoder'],validation=j['validation']))
 except Exception as ex:records.append(dict(name=name,ok=False,error=str(ex)))
 print(json.dumps(records[-1],ensure_ascii=False),flush=True)
call('quit');p.stdin.close();p.wait(timeout=10);p.stdout.close()
(D/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print('PASSED',sum(r['ok'] for r in records),'/',len(records));sys.exit(not all(r['ok'] for r in records))
