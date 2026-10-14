# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Wel Wang
"""Local-only OCR/AI/archival engines. No document network requests or API keys."""
import os, re, json, tempfile, threading, subprocess, time, html, hashlib
from collections import Counter
import engine as E
import pdf_tools as P
AI_SLOT=threading.Semaphore(1)

@P.local
def extract_pages(j,o):
    pages=[]
    with P.open_pdf(j.files[0],o.get('pw')) as doc:
        for n,page in enumerate(doc):
            P.cancelled(j);pages.append(P.page_text(page,o));j.progress=.15*(n+1)/len(doc)
    if not any(text.strip() for text in pages):raise ValueError('文件沒有可讀取的文字，請啟用 OCR')
    return pages

def chunks(text,limit=1100):
    result=[];pending=''
    for paragraph in re.split(r'(?<=[。！？.!?])\s*|\n\s*\n',text):
        if not paragraph.strip():continue
        while len(paragraph)>limit:
            if pending:result.append(pending);pending=''
            result.append(paragraph[:limit]);paragraph=paragraph[limit:]
        if pending and len(pending)+len(paragraph)>limit:result.append(pending);pending=''
        pending+=paragraph+'\n'
    if pending.strip():result.append(pending)
    return result

def generate(j,instruction,text,max_tokens=512):
    exe=P.asset('pdf-ai/llama-completion.exe');model=P.asset('pdf-ai/model.gguf')
    if not os.path.isfile(exe) or not os.path.isfile(model):raise ValueError('離線文字模型未包含在此版本，請使用完整離線版')
    with AI_SLOT:
        P.cancelled(j)
        with tempfile.TemporaryDirectory(prefix='zdgc_pdf_ai_') as tmp:
            prompt=os.path.join(tmp,'prompt.txt');answer=os.path.join(tmp,'answer.txt')
            content='<|im_start|>system\n你是文件助理。只依照提供的文件處理，不增加原文沒有的事實。'+instruction+' /no_think<|im_end|>\n<|im_start|>user\n'+text+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
            with open(prompt,'w',encoding='utf-8') as f:f.write(content)
            command=[exe,'-m',model,'-f',prompt,'-n',str(max_tokens),'-c','2048','-t',str(min(4,E.encoder_threads(j.opt))),'-ngl','0','--no-warmup','--no-display-prompt','--log-verbosity','0','--color','off','--simple-io','--no-conversation','--temp','0.2','--seed','42']
            j.proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=E.LOWPRI,env=dict(os.environ,LLAMA_ARG_OFFLINE='1'))
            try:stdout,stderr=j.proc.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                E.kill_process(j.proc);raise ValueError('這段文字推論超過三分鐘，請使用快速摘錄或縮短每頁內容')
            if j.cancelled:raise InterruptedError
            if j.proc.returncode:raise ValueError('本機文字引擎失敗：'+stderr.decode('utf-8',errors='replace')[-250:])
            result=open(answer,encoding='utf-8',errors='replace').read() if os.path.isfile(answer) else stdout.decode('utf-8',errors='replace')
            result=re.sub(r'\x1b\[[0-9;]*m','',result)
            result=re.sub(r'<think>.*?</think>','',result,flags=re.S).replace('<|im_end|>','').replace('<|endoftext|>','').replace('[end of text]','').strip()
            if not result:raise ValueError('模型沒有產生文字，請改用快速摘錄或縮短文件')
            return result

def extractive(text,count):
    sentences=[s.strip() for s in re.split(r'(?<=[。！？.!?])\s*|\n',text) if len(s.strip())>8]
    if not sentences:return text[:600]
    frequencies=Counter(re.findall(r'[A-Za-z]{3,}|[\u4e00-\u9fff]{2}',text.lower()))
    scored=[]
    for i,sentence in enumerate(sentences):
        terms=re.findall(r'[A-Za-z]{3,}|[\u4e00-\u9fff]{2}',sentence.lower());score=sum(frequencies[t] for t in terms)/max(1,len(terms))
        scored.append((score,i,sentence))
    chosen=sorted(sorted(scored,reverse=True)[:count],key=lambda item:item[1])
    return '\n'.join('• '+item[2] for item in chosen)

@P.local
def text_pdf(sections,path,j,title):
    doc=P.fitz.open()
    try:
        page=doc.new_page(width=595,height=842);y=40
        for label,text in sections:
            lines=[label]+text.splitlines()+['']
            for line in lines:
                P.cancelled(j)
                # Line splitting by character count avoids clipping CJK paragraphs.
                parts=[line[i:i+42] for i in range(0,len(line),42)] or ['']
                for part in parts:
                    if y>790:page=doc.new_page(width=595,height=842);y=40
                    page.insert_text((40,y),part,fontname='china-ts',fontsize=11,color=(0,0,0));y+=18
        P.save(doc,path,j)
    finally:doc.close()

def intelligence(eng,j,o):
    pages=extract_pages(j,o);root=P.folder(j);sections=[];records=[]
    if j.tool=='p_summary':
        mode=o.get('mode','ai');pieces=[(n,part) for n,text in enumerate(pages,1) for part in chunks(text)]
        for index,(n,part) in enumerate(pieces):
            P.cancelled(j);j.msg=f'整理第 {n} 頁 · 區段 {index+1}/{len(pieces)}'
            result=extractive(part,int(o.get('length',5))) if mode=='extract' else generate(j,f'請用{o.get("language","繁體中文")}列出最多 {int(o.get("length",5))} 點摘要。請勿輸出思考過程，直接輸出摘要。',part,384)
            sections.append((f'第 {n} 頁 · 區段 {index+1}',result));records.append(dict(page=n,original=part,result=result));j.progress=.15+.7*(index+1)/max(1,len(pieces))
        title='快速原文摘錄' if mode=='extract' else '離線 AI 摘要'
    else:
        pieces=[(n,part) for n,text in enumerate(pages,1) for part in chunks(text,700)]
        for index,(n,part) in enumerate(pieces):
            P.cancelled(j);j.msg=f'翻譯第 {n} 頁 · 區段 {index+1}/{len(pieces)}'
            result=generate(j,f'將使用者提供的全文翻譯為{o.get("language","繁體中文")}。保持數字、專有名詞與原意。只輸出譯文，不加解釋。',part,700)
            sections.append((f'第 {n} 頁 · 原文',part));sections.append((f'第 {n} 頁 · 譯文',result));records.append(dict(page=n,original=part,result=result));j.progress=.15+.7*(index+1)/max(1,len(pieces))
        title='離線雙語翻譯'
    with open(os.path.join(root,title+'.md'),'w',encoding='utf-8') as f:f.write('# '+title+'\n\n'+'\n\n'.join('## '+label+'\n\n'+text for label,text in sections))
    text_pdf(sections,os.path.join(root,title+'.pdf'),j,title)
    report=dict(engine='快速摘錄' if o.get('mode')=='extract' and j.tool=='p_summary' else 'llama.cpp / Qwen3-0.6B-Q8_0',offline=True,sections=records,
                notice='小型離線模型可能遺漏或誤譯；請核對原文。譯文重新排版，不保證保留原有字型、版面與表格。')
    with open(os.path.join(root,'處理報告.json'),'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    j.output=root;j.encoder=title;P.warn(j,report['notice'])

@P.local
def basic_pdfa_check(path):
    import pikepdf
    with pikepdf.open(path) as pdf:
        metadata=pdf.open_metadata();part=str(metadata.get('pdfaid:part',''));level=str(metadata.get('pdfaid:conformance',''))
        if part!='2' or level.upper()!='B' or '/OutputIntents' not in pdf.Root:raise ValueError('PDF/A 基本標記與色彩設定檢查失敗')
        return dict(part=part,conformance=level,output_intents=True,pages=len(pdf.pages),validation='基本結構檢查；不等於完整 ISO 合規驗證')

def pdfa(eng,j,o):
    exe=P.asset('ghostscript/bin/gswin64c.exe');profile=P.asset('ghostscript/iccprofiles/srgb.icc')
    if not os.path.isfile(exe) or not os.path.isfile(profile):raise ValueError('此版本缺少離線 PDF/A 引擎，請使用完整离線版')
    out=P.output(j)
    with tempfile.TemporaryDirectory(prefix='zdgc_pdfa_') as tmp:
        prefix=os.path.join(tmp,'archive.ps');temporary=os.path.join(tmp,'archive.pdf')
        # PostScript paths must quote parentheses and backslashes; prefer an ASCII temporary ICC path.
        import shutil
        icc=os.path.join(tmp,'srgb.icc');shutil.copyfile(profile,icc)
        ps_path=icc.replace('\\','/').replace('(','\\(').replace(')','\\)')
        with open(prefix,'w',encoding='utf-8') as f:f.write('%!\n/ICCProfile ('+ps_path+') def\n[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark\n[{icc_PDFA} << /N 3 >> /PUT pdfmark\n[{icc_PDFA} ICCProfile (r) file /PUT pdfmark\n[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark\n[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1 /DestOutputProfile {icc_PDFA} /OutputConditionIdentifier (sRGB) >> /PUT pdfmark\n[{Catalog} << /OutputIntents [ {OutputIntent_PDFA} ] >> /PUT pdfmark\n')
        source=j.files[0]
        if o.get('pw'):
            @P.local
            def decrypt():
                with P.open_pdf(source,o['pw']) as doc:doc.save(os.path.join(tmp,'source.pdf'),encryption=P.fitz.PDF_ENCRYPT_NONE)
            decrypt();source=os.path.join(tmp,'source.pdf')
        cmd=[exe,'-dSAFER','-dBATCH','-dNOPAUSE','-dPDFA=2','-dPDFACompatibilityPolicy=2','-sDEVICE=pdfwrite','-sColorConversionStrategy=RGB','-dEmbedAllFonts=true','-dSubsetFonts=true','--permit-file-read='+icc,'-sOutputFile='+temporary,prefix,source]
        j.encoder='Ghostscript PDF/A-2b';eng._proc(j,cmd,'PDF/A 轉換');report=basic_pdfa_check(temporary);shutil.copyfile(temporary,out)
    j.output=out;j.validation=report['validation']
    with open(out+'.report.json','w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    P.warn(j,'PDF/A 轉換會改寫文件，表單、互動內容或原有簽章可能改變；目前附基本結構檢查，正式歸檔前可使用 veraPDF 等標準驗證工具檢查')

def workflow(eng,j,o):
    root=P.folder(j);records=[];current=j.files[0]
    steps=[('p_ocr',dict(lang=o.get('lang','chi_tra+eng'),force=False))]
    if o.get('word',True):steps.append(('p_pdf_word',dict(ocr=False)))
    if o.get('archive',True):steps.append(('p_pdfa',{}))
    if o.get('sign'):steps.append(('p_certificate',dict(pfx=o.get('pfx'),pfx_pw=o.get('pfx_pw'),name='Signature1')))
    for n,(id,options) in enumerate(steps):
        P.cancelled(j);params=dict(o,**options);params['out_dir']=root
        child=E.Job([current],id,params,tool=id);child._nested=True;j.child=child;j._child_base=n/len(steps);j._child_span=1/len(steps);j.msg='正在處理'+id
        eng._run(child)
        if child.state not in ('done','partial'):raise ValueError('交付流程未完成：'+child.msg)
        records.append(dict(tool=id,output=os.path.relpath(child.output,root),check=child.validation,notes=child.notes))
        if id=='p_ocr':
            current=os.path.join(child.output,'可搜尋文件.pdf')
        elif id!='p_pdf_word':current=child.output
        j.progress=(n+1)/len(steps)*.95
    with open(os.path.join(root,'交付流程報告.json'),'w',encoding='utf-8') as f:json.dump(dict(offline=True,steps=records,final_pdf=os.path.relpath(current,root),notice='Word 是可編輯副本；PDF/A 在憑證簽章之前產生，避免簽署後轉檔破壞簽章。'),f,ensure_ascii=False,indent=2)
    j.output=root;j.encoder='離線文件交付流程';j.child=None
