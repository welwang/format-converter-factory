import unittest,json,threading,http.server,functools
from pathlib import Path
from test_pdf_suite import PDFSuite,E,C,T,fitz
class Additional(PDFSuite):
 def test_47_workflow(self):
  j=self.execute('p_workflow',[self.scan],lang='eng',archive=True,word=True)
  report=json.loads((Path(j.output)/'交付流程報告.json').read_text(encoding='utf-8'));self.assertEqual([s['tool'] for s in report['steps']],['p_ocr','p_pdf_word','p_pdfa']);self.assertTrue((Path(j.output)/report['final_pdf']).exists())
 def test_48_word_to_pdf(self):
  from docx import Document
  path=self.root/'Office.docx';doc=Document();doc.add_paragraph('Offline Office conversion');doc.save(path);j=self.execute('p_word_pdf',[path]);self.assertIn('Offline',fitz.open(j.output)[0].get_text())
 def test_49_html_local(self):
  path=self.root/'local.html';path.write_text('<html><body><h1>Offline HTML</h1><p>Local document.</p></body></html>');j=self.execute('p_html_pdf',[path]);self.assertIn('Offline',fitz.open(j.output)[0].get_text())
 def test_50_html_remote_rejected(self):
  path=self.root/'remote.html';path.write_text('<style>@import "https://example.com/style.css";</style>')
  with self.assertRaises(ValueError):self.execute('p_html_pdf',[path])
 def test_51_download_paths(self):
  # Synthetic local media only, with Unicode and spaces in the target path.
  video=self.root/'local.mp4';result=E.run([E.FFMPEG,'-hide_banner','-v','error','-y','-f','lavfi','-i','color=c=blue:s=128x96:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac',str(video)]);self.assertEqual(result.returncode,0)
  handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(self.root));server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();out=self.root/'中文 下載資料夾';out.mkdir();previous=E.base_dir
  try:
   for _ in range(2):
    job=E.Job(['local'],'download',{},tool='dl');C.Downloader(self.eng)._dl(job,f'http://127.0.0.1:{server.server_port}/local.mp4',dict(out_dir=str(out),quality='mp3'),C.ytdlp());self.assertEqual(job.state,'done');self.assertTrue(Path(job.output).exists());self.assertEqual(Path(job.output).suffix,'.mp3');self.assertIn('中文',job.output)
  finally:server.shutdown();server.server_close()
if __name__=='__main__':
 # Run new coverage once; the inherited suite has already passed.
 names=[n for n in unittest.defaultTestLoader.getTestCaseNames(Additional) if int(n.split('_')[1])>=47]
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Additional(n) for n in names));raise SystemExit(not result.wasSuccessful())
