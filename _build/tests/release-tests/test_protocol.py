import sys,os,unittest,json,subprocess,threading,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'src'),'E:/四維八德/_build/vendor'];import core,engine as E
class Protocol(unittest.TestCase):
 def test_filter_names_and_extensions(self):
  self.assertEqual(core.Window._filters(['圖片 (*.png;*.jpg)']),'圖片 (*.png;*.jpg)\x1f*.png;*.jpg')
 def test_open_folder_save_dialog_roundtrips(self):
  frames=[];window=None
  def send(line):
   frames.append(line);rid=int(line.split('\t',1)[0].split()[1]);window.answer(rid,['C:/中文 路徑/檔案.txt'])
  window=core.Window(send)
  for kind in ['open','folder','save']:
   result=window.create_file_dialog(kind,allow_multiple=True,file_types=['文字 (*.txt)'],save_filename='中文檔名.txt');self.assertEqual(result,['C:/中文 路徑/檔案.txt'])
  self.assertIn('\topen\t1\t',frames[0]);self.assertIn('\tfolder',frames[1]);self.assertIn('\tsave\t中文檔名.txt\t',frames[2])
 def test_cancelled_dialog(self):
  win=None
  def send(line):win.answer(int(line.split('\t')[0].split()[1]),None)
  win=core.Window(send);self.assertIsNone(win.create_file_dialog('open',file_types=['PDF (*.pdf)']))
 def test_window_operations_are_framed(self):
  frames=[];win=core.Window(frames.append);win.set_title('中文\n標題');win.minimize();win.restore();win.flash();win.quit();self.assertEqual(len(frames),5);self.assertTrue(all('\n' not in f for f in frames))
 def test_doc_routing_and_missing_report(self):
  import app
  api=object.__new__(app.Api)
  with patch('app.E.base_dir',return_value=str(ROOT/'release')),patch('app.FA.open_file',return_value=True) as opened:
   self.assertTrue(api.open_doc('tests'));self.assertEqual(Path(opened.call_args.args[0]).name,'測試報告.html')
   with self.assertRaises(ValueError):api.open_doc('unknown')
 def test_native_and_child_stdout_do_not_corrupt_pipe(self):
  script="""import sys,os,subprocess,ctypes
sys.path.insert(0,sys.argv[1]);import core
pin,pout=core._protocol_streams()
print('PYTHON_LIBRARY_LOG',flush=True)
k=ctypes.WinDLL('kernel32');k.GetStdHandle.argtypes=(ctypes.c_uint32,);k.GetStdHandle.restype=ctypes.c_void_p
k.WriteFile.argtypes=(ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32),ctypes.c_void_p)
count=ctypes.c_uint32();k.WriteFile(k.GetStdHandle((-11)&0xffffffff),b'NATIVE_LIBRARY_LOG\\n',19,ctypes.byref(count),None)
subprocess.run([sys.executable,'-c',"print('DEFAULT_CHILD_LOG')"],creationflags=0x08000000)
subprocess.run([sys.executable,'-c',"print('CHILD_LOG')"],stdout=sys.stderr,stderr=sys.stderr,creationflags=0x08000000)
pout.write(b'R {"ok":true}\\n')
"""
  r=subprocess.run([sys.executable,'-c',script,str(ROOT/'src')],capture_output=True,creationflags=E.NOWIN,timeout=20)
  self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'));self.assertEqual(r.stdout,b'R {"ok":true}\n');self.assertIn(b'CHILD_LOG',r.stderr);self.assertIn(b'NATIVE_LIBRARY_LOG',r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
