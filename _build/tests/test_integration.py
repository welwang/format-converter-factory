import sys, os, unittest, tempfile, json, io, time, hashlib, threading
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
(ROOT/'scratch').mkdir(exist_ok=True); tempfile.tempdir=str(ROOT/'scratch')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, 'E:/四維八德/_build/vendor')
import engine as E
import workflows as W
import capture as C
BASE = str(ROOT / 'release')
E.base_dir = lambda: BASE
E.FFMPEG = E.find_tool('ffmpeg'); E.SEVENZIP = E.find_tool('7z')
E.PANDOC = E.find_tool('pandoc'); E.SOFFICE = E.find_soffice(); E.CALIBRE = E._calibre()
E.detect_hw = lambda: []

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        cls.d = Path(cls.tmp.name); E._DATA = str(cls.d)
        cls.eng = E.Engine(2, 4)
        from PIL import Image
        Image.new('RGB', (480, 300), 'navy').save(cls.d / 'image.jpg')
        Image.new('RGBA', (64, 32), (255, 100, 0, 160)).save(cls.d / 'logo.png')
        from pypdf import PdfWriter
        w=PdfWriter(); w.add_blank_page(300,400); w.add_blank_page(300,400); w.write(cls.d / 'sample.pdf')
        (cls.d/'captions.srt').write_bytes('1\n00:00:00,000 --> 00:00:00,800\n中文測試\n'.encode('cp950'))
        for name,size,audio in [('land','320x180',True),('portrait','180x320',True),('silent','320x180',False)]:
            cmd=[E.FFMPEG,'-hide_banner','-v','error','-y','-f','lavfi','-i',f'testsrc2=s={size}:r=15:d=1']
            if audio: cmd+=['-f','lavfi','-i','sine=f=440:d=1']
            cmd+=['-c:v','libx264','-preset','ultrafast']
            if audio:cmd+=['-c:a','aac']
            r=E.run(cmd+[str(cls.d/(name+'.mp4'))],timeout=30)
            if r.returncode:raise RuntimeError(r.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.eng.pool.shutdown(wait=True); cls.eng.light.shutdown(wait=True)
        cls.tmp.cleanup()

    def job(self, files, target, **opt):
        return E.Job([str(self.d/f) for f in files],target,dict(out_dir=str(self.d/'out'),hwaccel=False,**opt))
    def run_ok(self,j):
        self.eng._run(j);self.assertEqual(j.state,'done',j.msg);self.assertTrue(j.validation);return j

    def test_01_merge_mixed_ratio(self):
        j=self.job(['land.mp4','portrait.mp4'],'mp4',height=180);j.merge=True
        self.run_ok(j);self.assertGreater(E.probe_duration(j.output),1.7)
    def test_02_merge_missing_audio(self):
        j=self.job(['land.mp4','silent.mp4'],'mp4',height=180);j.merge=True
        self.run_ok(j);self.assertTrue(any(t=='audio' for t,_ in E.probe_info(j.output)['streams']))
    def test_03_size_failure_keeps_output(self):
        j=self.job(['land.mp4'],'mp4',target_mb=.001,fastcopy=False);self.eng._run(j)
        self.assertEqual(j.state,'error');self.assertIn('未達目標',j.msg);self.assertTrue(os.path.isfile(j.output))
    def test_04_repack_archive(self):
        src=self.d/'source.zip';E.run([E.SEVENZIP,'a','-y',str(src),str(self.d/'image.jpg')])
        j=self.run_ok(self.job(['source.zip'],'7z'))
        listing=E.run([E.SEVENZIP,'l','-slt',j.output]).stdout
        self.assertIn('Path = image.jpg',listing);self.assertNotIn('Path = source.zip',listing)
    def test_05_pdf_parallel_render(self):
        ids=self.eng.submit([str(self.d/'sample.pdf')]*4,'png',dict(out_dir=str(self.d/'pdfout')))
        end=time.time()+30
        while any(self.eng.jobs[i].state in ('queued','running') for i in ids) and time.time()<end:time.sleep(.05)
        self.assertTrue(all(self.eng.jobs[i].state=='done' for i in ids))
    def test_06_pdf_lock_serializes(self):
        running=0;maximum=0;lock=threading.Lock()
        @E.pdfium_serial
        def fn():
            nonlocal running,maximum
            with lock:running+=1;maximum=max(maximum,running)
            time.sleep(.01)
            with lock:running-=1
        ts=[threading.Thread(target=fn) for _ in range(6)]
        [t.start() for t in ts];[t.join() for t in ts];self.assertEqual(maximum,1)
    def test_07_product_pack(self):
        j=self.job(['image.jpg'],'workflow',recipe='product',size=200,prefix='品牌',logo=str(self.d/'logo.png'),watermark='© 100% 測試',zip=True);j.tool='workflow';j.cat='tool'
        self.run_ok(j);manifest=json.loads((Path(j.output)/'交付報告.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['records']),3);self.assertTrue(all(r['state']=='done' for r in manifest['records']))
        self.assertTrue((Path(j.output)/'交付檔案.zip').is_file())
    def test_08_video_pack_subtitles_logo(self):
        j=self.job(['land.mp4'],'workflow',recipe='video',watermark='© 中文 100% : test',logo=str(self.d/'logo.png'),sub_file=str(self.d/'captions.srt'),verify_full=True);j.tool='workflow';j.cat='tool'
        self.run_ok(j);records=json.loads((Path(j.output)/'交付報告.json').read_text(encoding='utf-8'))['records']
        self.assertEqual(len(records),5)
        vertical=next(r for r in records if r['output'].startswith('直式分享'))
        i=E.probe_info(os.path.join(j.output,vertical['output']));self.assertEqual((i['width'],i['height']),(720,1280))
    def test_09_pipeline_and_source_unchanged(self):
        src=self.d/'image.jpg';digest=hashlib.sha256(src.read_bytes()).hexdigest()
        steps=[dict(tool='i_resize',params={'mode':'long','val':240}),dict(tool='i_rotate',params={'op':'cw','crop':'none','fmt':'same'})]
        j=self.job(['image.jpg'],'workflow',recipe='pipeline',steps=steps);j.tool='workflow';j.cat='tool'
        self.run_ok(j);self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),digest)
        from PIL import Image
        with Image.open(next(Path(j.output).glob('*.jpg'))) as im:self.assertEqual(im.size,(150,240))
    def test_10_share_mixed_pack_partial(self):
        j=self.job(['image.jpg','sample.pdf','source.zip'],'workflow',recipe='share',max_mb=20,zip=True);j.tool='workflow';j.cat='tool'
        self.eng._run(j);self.assertEqual(j.state,'partial');self.assertTrue((Path(j.output)/'交付報告.txt').is_file())
    def test_11_profile_secrets_and_validation(self):
        p=W.valid_profile(dict(name='客戶',recipe='pipeline',options={'steps':[{'tool':'p_encrypt','params':{'pw':'example-password'}}]}))
        self.assertNotIn('pw',p['options']['steps'][0]['params'])
        with self.assertRaises(ValueError):W.valid_profile(dict(name='壞配方',recipe='pipeline',options={'steps':[{'tool':'nonexistent'}]}))
    def test_12_options_log_redaction(self):
        self.assertNotIn('secret',str(E.public_options({'pw':'secret','_secret':'secret','preset':'high'})))
    def test_13_cancel_recording_routes_to_stop(self):
        import app
        a=app.Api.__new__(app.Api);a._rec=SimpleNamespace(job=SimpleNamespace(id='rec-id'));a._eng=SimpleNamespace(cancel=lambda _:self.fail('generic cancel called'))
        with patch.object(a,'rec_stop',return_value='rec-id') as stop:a.cancel('rec-id');stop.assert_called_once()
    def test_14_partial_playlist(self):
        fake=SimpleNamespace(stdout=io.StringIO('ZDGCFILE '+str(self.d/'image.jpg')+'\n'),stderr=io.StringIO('ERROR: second failed\n'),returncode=1,wait=lambda:1)
        j=self.job(['land.mp4'],'download');j.tool='dl';j.state='running'
        with patch.object(C.subprocess,'Popen',return_value=fake):C.Downloader(self.eng)._dl(j,'https://example.invalid/a',{'out_dir':str(self.d)},'fake')
        self.assertEqual(j.state,'partial')
    def test_15_failed_batch_does_not_shutdown(self):
        j=self.job(['land.mp4'],'mp4');j.state='cancelled';self.eng.add_external(j)
        f=C.Finisher.__new__(C.Finisher);f.api=SimpleNamespace(_s={'finish':'shutdown'},_eng=self.eng);f.batch={j.id}
        with patch.object(C.subprocess,'Popen') as popen:f._fire();popen.assert_not_called()
    def test_16_clear_history_releases_jobs(self):
        e=E.Engine(1,1);j=self.job(['image.jpg'],'jpg');j.state='done';e.add_external(j);e.clear_done()
        self.assertEqual(e.jobs,{});e.shutdown()
    def test_17_hevc_codec(self):
        j=self.run_ok(self.job(['land.mp4'],'mp4',codec='hevc',fastcopy=True));self.assertIn(('video','hevc'),E.probe_info(j.output)['streams'])
    def test_18_av1_codec(self):
        j=self.run_ok(self.job(['land.mp4'],'mp4',codec='av1',fastcopy=True));self.assertIn(('video','av1'),E.probe_info(j.output)['streams'])
    def test_19_profile_save_not_overwritten_by_ui_settings(self):
        import app
        a=app.Api.__new__(app.Api);a._s={};a._settings_lock=threading.RLock()
        with patch.object(app,'SETTINGS',str(self.d/'settings.json')):
            schema=a.workflow_save(dict(name='測試',recipe='product',options={'size':240}))
            a.save_settings({'flow_profiles':[],'theme':'dark'})
            self.assertEqual(len(a.workflow_schema()['profiles']),1)
            payload=json.loads((self.d/'settings.json').read_text(encoding='utf-8'));self.assertEqual(payload['theme'],'dark')

    def test_20_watch_tracks_changed_file_and_cleared_completion(self):
        w=C.Watcher.__new__(C.Watcher);w.lock=threading.RLock();w.rules=[dict(folder=str(self.d),target='png',out_dir=str(self.d/'watched'))];w.seen={str(self.d):{}};w.sizes={};w.state_file=str(self.d/'watch-test.json')
        api=SimpleNamespace(_eng=self.eng,base_opt=lambda:{'preset':'balanced'});w.api=api
        def image_list(rule,stats):
            image=str(self.d/'image.jpg');st=os.stat(image);stats[image]=(st.st_size,st.st_mtime);return [image]
        with patch.object(w,'_list',side_effect=image_list):
            w._tick();w._tick()
            entry=w.seen[str(self.d)][str(self.d/'image.jpg')];jid=entry['job'];end=time.time()+10
            while self.eng.jobs[jid].state in ('queued','running') and time.time()<end:time.sleep(.02)
            self.eng.clear_done();w._tick();self.assertEqual(entry['state'],'done')
            os.utime(self.d/'image.jpg',(time.time()+2,time.time()+2));w._tick();w._tick()
            self.assertNotEqual(w.seen[str(self.d)][str(self.d/'image.jpg')]['job'],jid)
    def test_21_watch_exclusion_uses_path_boundaries(self):
        parent=os.path.normcase(os.path.abspath(str(self.d/'out')))
        self.assertTrue(C.Watcher._inside(str(self.d/'out'/'file'),parent))
        self.assertFalse(C.Watcher._inside(str(self.d/'outside'),parent))
    def test_22_cancel_running_owned_process(self):
        import tools as T
        def slow(eng,j,o):eng._exec(j,[E.FFMPEG,'-hide_banner','-v','error','-nostdin','-re','-i',j.files[0],'-f','null','-'],1)
        with patch.dict(T.RUN,{'test_slow':slow}):
            ids=self.eng.submit_tool('test_slow',[str(self.d/'land.mp4')],{},'取消測試');j=self.eng.jobs[ids[0]]
            end=time.time()+5
            while j.proc is None and time.time()<end:time.sleep(.01)
            self.eng.cancel(j.id)
            while j.state in ('queued','running') and time.time()<end:time.sleep(.01)
            self.assertEqual(j.state,'cancelled');self.assertIsNotNone(j.proc.poll())
    def test_23_compare_preview(self):
        import app
        j=self.run_ok(self.job(['image.jpg'],'webp'));self.eng.add_external(j)
        a=app.Api.__new__(app.Api);a._eng=self.eng
        r=a.compare_job(j.id);self.assertEqual((r['before']['w'],r['after']['w']),(480,480));self.assertTrue(r['after']['src'].startswith('data:image/jpeg;base64,'))

    def test_24_low_memory_limits_and_nested_workflow(self):
        with patch.object(E,'mem_gb',return_value=4):
            self.assertEqual(E.work_slots(),1);self.assertEqual(E.light_workers(),1)
            eng=E.Engine(2,2);j=self.job(['image.jpg'],'workflow',recipe='share',max_mb=20);j.tool='workflow';j.cat='tool'
            eng._run(j);self.assertEqual(j.state,'done',j.msg);eng.shutdown()
    def test_25_aes_pdf_roundtrip(self):
        j=self.job(['sample.pdf'],'p_encrypt',pw='fixture-secret');j.tool='p_encrypt';j.cat='tool';self.run_ok(j)
        from pypdf import PdfReader
        r=PdfReader(j.output);self.assertTrue(r.is_encrypted);self.assertTrue(r.decrypt('fixture-secret'));self.assertEqual(len(r.pages),2);self.assertIn('AES-256',j.encoder)
    def test_26_cleanup_only_old_selected_owned_files(self):
        import system_tools as ST
        tmp=self.d/'cleanup-temp';tmp.mkdir(exist_ok=True);owned=tmp/'zdgc_example';owned.mkdir(exist_ok=True)
        old=owned/'old.tmp';old.write_bytes(b'old');recent=owned/'recent.tmp';recent.write_bytes(b'new');unrelated=tmp/'private.txt';unrelated.write_bytes(b'personal')
        os.utime(old,(time.time()-10*86400,time.time()-10*86400));os.utime(unrelated,(time.time()-10*86400,time.time()-10*86400))
        with patch.object(ST.tempfile,'gettempdir',return_value=str(tmp)):
            plan=ST.scan_cleanup(['app_temp']);self.assertEqual(len(plan['items']),1)
            r=ST.execute_cleanup(plan,plan['token']);self.assertEqual(r['removed'],1)
        self.assertFalse(old.exists());self.assertTrue(recent.exists());self.assertTrue(unrelated.exists())
    def test_27_cleanup_modified_files_are_skipped(self):
        import system_tools as ST
        tmp=self.d/'cleanup-mod';tmp.mkdir(exist_ok=True);f=tmp/'old.tmp';f.write_bytes(b'a');os.utime(f,(time.time()-10*86400,time.time()-10*86400))
        with patch.object(ST.tempfile,'gettempdir',return_value=str(tmp)):
            plan=ST.scan_cleanup(['user_temp']);f.write_bytes(b'changed')
            r=ST.execute_cleanup(plan,plan['token']);self.assertEqual(r['skipped'],1);self.assertTrue(f.exists())
    def test_28_cleanup_expired_or_wrong_token_rejected(self):
        import system_tools as ST
        plan=dict(token='fixture',created=time.time()-601,items=[])
        with self.assertRaises(ValueError):ST.execute_cleanup(plan,'fixture')
        plan['created']=time.time()
        with self.assertRaises(ValueError):ST.execute_cleanup(plan,'wrong')
    def test_29_cleanup_path_boundary(self):
        import system_tools as ST
        self.assertFalse(ST._safe_root(str(self.d/'outside'/'f'),str(self.d/'out')))
        self.assertFalse(ST._safe_root(str(self.d/'out'),str(self.d/'out')))
    def test_30_hardware_short_test(self):
        j=self.job(['land.mp4'],'hardware_test');j.tool='hardware_test';j.cat='tool';self.run_ok(j)
        self.assertEqual(Path(j.output).suffix,'.txt');self.assertIn('CPU',Path(j.output).read_text(encoding='utf-8-sig'))
        data=json.loads(Path(j.output).with_suffix('.json').read_text(encoding='utf-8'));self.assertEqual(len(data['tests']),4);self.assertTrue(all(t['state']=='done' for t in data['tests']))
        self.assertEqual(list(Path(j.output).parent.glob('zdgc_disk_*.tmp')),[])

    def test_31_disk_check_and_repair_removed(self):
        import importlib.util, app
        self.assertIsNone(importlib.util.find_spec('disk_tools'))
        for name in ('disk_info','disk_preview','disk_launch','disk_help'):self.assertFalse(hasattr(app.Api,name),name)
    def test_32_health_check_never_pretends(self):
        import health_check as HC
        r=HC.evaluate({},{},dict(network=False))
        self.assertEqual(r['counts']['ok'],0)
        self.assertTrue(all(i['state'] in ('untested','partial') for i in r['items']))
        bad=HC.evaluate({},dict(threads=4,cpu=dict(single_rps=10,multi_rps=30,threads=4,scaling=3,errors=2)),dict(network=False))
        cpu=next(i for i in bad['items'] if i['id']=='cpu');self.assertEqual(cpu['state'],'bad');self.assertTrue(cpu['advice'])
        self.assertEqual(HC.options(dict(mode='pro',stress=99999,mem_mb=7))['stress'],180)

if __name__=='__main__':unittest.main(verbosity=2)
