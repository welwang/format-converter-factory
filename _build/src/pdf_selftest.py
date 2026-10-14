# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Wel Wang
"""Offline frozen-package verification; creates only its own test fixtures."""
import os,json,traceback
from pathlib import Path
import engine as E,tools as T
def main(directory):
 root=Path(directory);root.mkdir(parents=True,exist_ok=True);results=[]
 def check(name,fn):
  try:fn();results.append(dict(name=name,ok=True))
  except Exception:results.append(dict(name=name,ok=False,error=traceback.format_exc()))
 try:
  import pymupdf as fitz
  doc=fitz.open();page=doc.new_page(width=400,height=600);page.insert_text((40,80),'Offline PDF package test. SECRET',fontsize=14);page.insert_text((40,110),'Hello, this file needs offline processing.',fontsize=12);source=root/'source.pdf';doc.save(source);doc.close()
  eng=E.Engine(1,light=1)
  def run(id,**kw):
   opt={f['k']:f['default'] for f in T.TOOL[id]['fields']};opt.update(out_dir=str(root/id),resource_mode='quiet');opt.update(kw);j=E.Job([str(source)],id,opt,tool=id);j.state='running';T.run(eng,j);eng.validate(j);assert Path(j.output).exists();return j
  for id,kw in [('p_merge',{}),('p_pdf_word',{}),('p_pdf_excel',{}),('p_pdf_ppt',{}),('p_markdown',{}),('p_redact',dict(text='SECRET',confirmed=True)),('p_pdfa',{}),('p_ocr',dict(force=True,lang='eng')),('p_summary',dict(mode='ai',language='English',length=2)),('p_translate',dict(language='繁體中文')),('p_workflow',dict(lang='eng',archive=True,word=True))]:
   check(id,lambda id=id,kw=kw:run(id,**kw))
  def signature():
   from cryptography import x509
   from cryptography.x509.oid import NameOID
   from cryptography.hazmat.primitives import hashes,serialization
   from cryptography.hazmat.primitives.asymmetric import rsa
   from cryptography.hazmat.primitives.serialization import pkcs12
   from pyhanko.pdf_utils.reader import PdfFileReader
   import datetime
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Offline self-test only')]);now=datetime.datetime.now(datetime.timezone.utc)
   cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(123).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1)).sign(key,hashes.SHA256())
   path=root/'self-test-only.pfx';path.write_bytes(pkcs12.serialize_key_and_certificates(b'test',key,cert,None,serialization.BestAvailableEncryption(b'test')))
   try:
    j=run('p_certificate',pfx=str(path),pfx_pw='test')
    with open(j.output,'rb') as f:assert len(PdfFileReader(f).embedded_signatures)==1
   finally:path.unlink(missing_ok=True)
  check('p_certificate',signature)
  eng.shutdown()
 except Exception:results.append(dict(name='runtime',ok=False,error=traceback.format_exc()))
 (root/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 return int(not results or not all(r['ok'] for r in results))
