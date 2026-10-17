import os,sys,unittest,tempfile,io,ctypes,subprocess,json,shutil,struct,time
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'src'),'E:/四維八德/_build/vendor'];import engine as E,tools as T,pdf_tools as P
E.base_dir=lambda:str(ROOT/'release');E.FFMPEG=E.find_tool('ffmpeg');E.SOFFICE=E.find_soffice();E.PANDOC=E.find_tool('pandoc');E.CALIBRE=E._calibre();E.SEVENZIP=E.find_tool('7z');E.detect_hw=lambda:[]
from PIL import Image
class FeatureEdges(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=ROOT/'feature-edge-checks';cls.root.mkdir(exist_ok=True);E._DATA=str(cls.root);cls.eng=E.Engine(1,light=1)
  cls.video=ROOT/'windows-engine-checks/中文 素材/影片 測試.mp4';cls.image=cls.root/'圖片.png';Image.new('RGB',(128,96),'orange').save(cls.image)
 @classmethod
 def tearDownClass(cls):cls.eng.shutdown()
 def tool(self,id,files,**kw):
  opts={f['k']:f['default'] for f in T.TOOL[id]['fields']};opts.update(out_dir=str(self.root/id),hwaccel=False,resource_mode='quiet');opts.update(kw);Path(opts['out_dir']).mkdir(exist_ok=True);j=E.Job(list(map(str,files)),id,opts,tool=id);j.state='running';T.run(self.eng,j);self.eng.validate(j);self.assertTrue(Path(j.output).exists());return j
 def test_video_blurred_background(self):
  j=self.tool('v_fill',[self.video],height='720',ratio='1:1');self.assertGreater(Path(j.output).stat().st_size,0)
 def test_pdf_unlock_roundtrip(self):
  import pymupdf as fitz
  src=self.root/'原稿.pdf';d=fitz.open();d.new_page().insert_text((30,50),'Secret known-password test');d.save(src);d.close();encrypted=self.tool('p_encrypt',[src],pw='abc');decrypted=self.tool('p_decrypt',[encrypted.output],pw='abc');self.assertFalse(fitz.open(decrypted.output).needs_pass)
 def test_pdf_chinese_ocr(self):
  import pymupdf as fitz
  doc=fitz.open();p=doc.new_page(width=400,height=300);p.insert_text((30,70),'資料測試 文件內容',fontname='china-ts',fontsize=24);pix=p.get_pixmap(dpi=180);img=self.root/'中文掃描.png';pix.save(img);doc.close();source=self.tool('p_images_pdf',[img]);j=self.tool('p_ocr',[source.output],lang='chi_tra+eng',force=True)
  with fitz.open(Path(j.output)/'可搜尋文件.pdf') as d:text=''.join(p.get_text() for p in d)
  self.assertTrue(any('\u4e00'<=ch<='\u9fff' for ch in text),text)
 def test_office_tool_ppt(self):self.tool('p_ppt_pdf',[ROOT/'windows-engine-checks/中文 素材/簡報.pptx'])
 def test_office_tool_excel(self):self.tool('p_excel_pdf',[ROOT/'windows-engine-checks/中文 素材/表格.xlsx'])
 def test_psd_and_svg(self):
  from psd_tools import PSDImage
  psd=self.root/'合成.psd';PSDImage.new('RGB',(64,48),color=(255,0,0)).save(psd);svg=self.root/'向量.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48"><rect width="64" height="48" fill="blue"/></svg>')
  for source in [psd,svg]:
   j=E.Job([str(source)],'png',dict(out_dir=str(self.root),resource_mode='quiet'));self.eng._run(j);self.assertEqual(j.state,'done',j.msg);self.assertEqual(Image.open(j.output).size,(64,48))
 def test_synthetic_dng_raw(self):
  import numpy as np
  width=64;height=48;raw=np.arange(width*height,dtype='<u2').reshape(height,width)*20
  # A generated, uncompressed CFA DNG; it contains no personal photograph.
  entries={256:(4,1,struct.pack('<I',width)),257:(4,1,struct.pack('<I',height)),258:(3,1,struct.pack('<H',16)),259:(3,1,struct.pack('<H',1)),262:(3,1,struct.pack('<H',32803)),273:(4,1,b'\0'*4),277:(3,1,struct.pack('<H',1)),278:(4,1,struct.pack('<I',height)),279:(4,1,struct.pack('<I',raw.nbytes)),284:(3,1,struct.pack('<H',1)),33421:(3,2,struct.pack('<HH',2,2)),33422:(1,4,bytes([0,1,1,2])),50706:(1,4,bytes([1,4,0,0])),50707:(1,4,bytes([1,1,0,0])),50708:(2,17,b'Synthetic Camera\0'),50714:(3,1,struct.pack('<H',0)),50717:(4,1,struct.pack('<I',65535)),50721:(10,9,b''.join(struct.pack('<ii',1 if i%4==0 else 0,1) for i in range(9))),50728:(5,3,struct.pack('<IIIIII',1,1,1,1,1,1)),50778:(3,1,struct.pack('<H',21))}
  base=8+2+12*len(entries)+4;extra=bytearray();ifd=bytearray(struct.pack('<H',len(entries)))
  for tag,(kind,count,data) in sorted(entries.items()):
   if len(data)>4:field=struct.pack('<I',base+len(extra));extra+=data;extra+=b'\0'*(len(extra)%2)
   else:field=data.ljust(4,b'\0')
   ifd+=struct.pack('<HHI',tag,kind,count)+field
  strip=base+len(extra);idx=list(sorted(entries)).index(273);struct.pack_into('<I',ifd,2+idx*12+8,strip);ifd+=b'\0'*4;source=self.root/'合成相機.dng';source.write_bytes(b'II'+struct.pack('<HI',42,8)+ifd+extra+raw.tobytes())
  j=E.Job([str(source)],'png',dict(out_dir=str(self.root),resource_mode='quiet'));self.eng._run(j);self.assertEqual(j.state,'done',j.msg);self.assertGreater(Image.open(j.output).width,10)
 def test_dvd_vob_conversion(self):
  folder=self.root/'DVD/VIDEO_TS';folder.mkdir(parents=True,exist_ok=True);vob=folder/'VTS_01_1.VOB';r=E.run([E.FFMPEG,'-hide_banner','-v','error','-y','-i',str(self.video),'-target','ntsc-dvd',str(vob)]);self.assertEqual(r.returncode,0,r.stderr);self.tool('d_dvd',[folder.parent],fmt='mp4')
 def test_bluray_missing_and_protected_media(self):
  with self.assertRaises(RuntimeError):self.tool('d_bluray',[self.root/'missing'])
  folder=self.root/'BluRay';(folder/'BDMV').mkdir(parents=True,exist_ok=True)
  with patch.object(E,'run',return_value=subprocess.CompletedProcess([],1,'','encrypted AACS')):
   with self.assertRaisesRegex(RuntimeError,'防拷'):self.tool('d_bluray',[folder])
 def test_cd_read_and_unreadable_sector_warning(self):
  from ctypes import wintypes
  for unreadable in [False,True]:
   fake=MagicMock();fake.GetDriveTypeW.return_value=5;fake.CloseHandle.return_value=1
   def ioctl(handle,code,request,size,buf,capacity,result,overlap):
    if unreadable:return False
    n=int(capacity)//2352;ctypes.memset(buf,0,2352*n);ctypes.cast(result,ctypes.POINTER(wintypes.DWORD)).contents.value=2352*n;return True
   fake.DeviceIoControl.side_effect=ioctl
   with patch.object(T,'cd_toc',return_value=(0x123456789,[(1,0,0),(170,20,0)])),patch.object(ctypes.windll,'kernel32',fake):
    j=self.tool('d_cd',['Z:'],fmt='wav');self.assertEqual(bool(j.warnings),unreadable)
 def test_cd_64bit_handle_and_drive_guard(self):
  fake=MagicMock();fake.GetDriveTypeW.return_value=5;fake.CreateFileW.return_value=0x123456789
  def toc(handle,code,request,size,buf,capacity,result,overlap):
   buf[2]=1;buf[3]=1;buf[6]=1;buf[9]=0;buf[10]=2;buf[11]=0;buf[14]=170;buf[17]=0;buf[18]=3;buf[19]=0;return True
  fake.DeviceIoControl.side_effect=toc
  with patch.object(ctypes.windll,'kernel32',fake):
   handle,tracks=T.cd_toc('Z:');self.assertEqual(handle,0x123456789);self.assertIs(fake.CreateFileW.restype,ctypes.c_void_p);self.assertEqual(len(tracks),2)
   fake.GetDriveTypeW.return_value=3
   with self.assertRaises(RuntimeError):T.cd_toc('C:')
 def test_iso_raw_read_from_simulated_optical_device(self):
  content=b'ISO_TEST_SECTOR'.ljust(2048,b'\0')*20;real_open=open;fake=MagicMock();fake.GetDriveTypeW.return_value=5
  def free(root,available,total,free):ctypes.cast(total,ctypes.POINTER(ctypes.c_ulonglong)).contents.value=len(content);return True
  fake.GetDiskFreeSpaceExW.side_effect=free
  def opened(path,*args,**kw):return io.BytesIO(content) if str(path).startswith('\\\\.\\Z:') else real_open(path,*args,**kw)
  opts=dict(out_dir=str(self.root),resource_mode='quiet');j=E.Job(['Z:'],'d_iso',opts,tool='d_iso')
  with patch.object(ctypes.windll,'kernel32',fake),patch('builtins.open',side_effect=opened):T.t_iso(self.eng,j,opts)
  self.assertEqual(Path(j.output).read_bytes(),content)
 def test_recording_pipeline_with_synthetic_source(self):
  import capture as C
  recorder=C.Recorder(self.eng)
  def command(opts,path,mode,hw):return [E.FFMPEG,'-hide_banner','-y','-re','-f','lavfi','-i','testsrc2=size=160x120:rate=10','-c:v','libx264','-preset','ultrafast',path],'controlled synthetic source'
  with patch.object(recorder,'_cmd',side_effect=command):
   id=recorder.start(dict(out_dir=str(self.root/'record'),hwaccel=False,fps=10));time.sleep(.3);recorder.stop();j=self.eng.jobs[id];self.assertEqual(j.state,'done',j.msg);self.assertGreater(Path(j.output).stat().st_size,0)
 def test_invalid_file_open_does_not_report_success(self):
  import file_actions as FA
  with self.assertRaises(FileNotFoundError):FA.reveal(str(self.root/'not-found.mp4'))
if __name__=='__main__':unittest.main(verbosity=2)
