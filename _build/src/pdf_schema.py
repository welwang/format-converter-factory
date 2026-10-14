# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Wel Wang
"""Independent, offline PDF tool catalogue; no remote document API."""
def field(k, label, type='text', default='', **kw):
    return dict(k=k, label=label, type=type, default=default, **kw)

F=field
PAGE=F('pages','頁碼（空白＝全部）')
PASSWORD=F('pw','文件密碼（選填）','password')
OCR=F('ocr','辨識掃描頁面的文字','check',False)
LANG=F('lang','OCR 語言','select','chi_tra+eng',options=[['chi_tra+eng','繁體中文＋英文'],['chi_sim+eng','簡體中文＋英文'],['eng','英文'],['jpn+eng','日文＋英文'],['kor+eng','韓文＋英文'],['deu','德文'],['fra','法文'],['spa','西班牙文']])
POINT=F('rect','位置／範圍','rect','')
TOOLS=[]
def add(id,name,desc,section,fields=(),accept=('pdf',),**kw):
    TOOLS.append(dict(id=id,name=name,desc=desc,group='pdf',icon=kw.pop('icon','pdf'),accept=list(accept),fields=list(fields),section=section,**kw))

add('p_merge','合併 PDF','按清單順序合併，保留可讀取的頁面與書籤','整理', [PASSWORD],together=True)
add('p_remove','移除頁面','刪除指定頁碼，原檔保留','整理',[F('pages','要移除的頁碼，例如 2,4-6'),PASSWORD])
add('p_extract','提取頁面','依輸入順序提取頁面，可重複或重排','整理',[F('pages','要提取的頁碼，例如 3,1-2'),PASSWORD])
add('p_organize','整理／重新排列 PDF','依頁碼排列，或反轉、插入空白頁','整理',[F('mode','方式','select','order',options=[['order','依輸入順序'],['reverse','反轉順序'],['blank','指定頁後插入空白頁']]),PAGE,PASSWORD])
add('p_scan','掃描為 PDF','匯入相機／掃描器圖片，校正、去背與加入可搜尋文字','整理',[F('paper','紙張','select','a4',options=[['a4','A4'],['letter','Letter'],['original','原始圖片比例']]),F('clean','黑白文件增強','check',True),F('deskew','自動校正傾斜','check',True),F('ocr','加入 OCR 搜尋文字','check',True),LANG],accept=('image',),together=True,min_files=1)
add('p_compress','壓縮 PDF','無損整理，或重壓圖片；保留文字與向量內容','優化',[F('level','壓縮方式','select','balanced',options=[['lossless','無損整理'],['balanced','均衡圖片壓縮'],['small','小檔案圖片壓縮']]),PASSWORD])
add('p_repair','修復 PDF','重建損壞結構，逐頁驗證並輸出修復報告','優化',[PASSWORD])
add('p_ocr','OCR PDF','離線辨識掃描頁面，輸出可搜尋的 PDF 與文字','優化',[LANG,F('dpi','辨識解析度','select','200',options=[['150','150 DPI（省資源）'],['200','200 DPI（均衡）'],['300','300 DPI（較細緻）']]),F('force','重新辨識所有頁面','check',False),PASSWORD])
add('p_images_pdf','圖片轉 PDF','可設定紙張、方向、邊距並依清單合併圖片','轉成 PDF',[F('paper','紙張','select','a4',options=[['a4','A4'],['letter','Letter'],['original','原始圖片比例']]),F('landscape','橫向紙張','check',False),F('margin','邊距（毫米）','number',10,min=0,max=50)],accept=('image',),together=True,min_files=1)
for id,name,accept in [('p_word_pdf','Word 轉 PDF',('doc','office')),('p_ppt_pdf','PowerPoint 轉 PDF',('sheet','office')),('p_excel_pdf','Excel 轉 PDF',('sheet','office')),('p_office_pdf','Office 轉 PDF',('doc','sheet','office'))]:
    add(id,name,'使用隨附的本機 Office 引擎轉換，不需帳號','轉成 PDF',[],accept=accept)
add('p_html_pdf','HTML／網頁轉 PDF','處理本機 HTML 檔；可貼上 HTML，無需連網','轉成 PDF',[],accept=('doc',))
add('p_pdf_images','PDF 轉 JPG／圖片','逐頁轉 JPG 或 PNG，也可提取內嵌圖片','從 PDF 轉換',[F('mode','內容','select','pages',options=[['pages','每頁轉成圖片'],['embedded','提取內嵌圖片']]),F('fmt','格式','select','jpg',options=[['jpg','JPG'],['png','PNG']]),F('dpi','解析度','select','150',options=[['100','100 DPI'],['150','150 DPI'],['300','300 DPI']]),PAGE,PASSWORD])
add('p_pdf_word','PDF 轉 Word','輸出可編輯文字、圖片與表格；複雜版面需人工檢查','從 PDF 轉換',[OCR,LANG,PASSWORD])
add('p_pdf_word_ocr','PDF 轉 Word（OCR）','將掃描文件辨識為可編輯的 Word 文件','從 PDF 轉換',[LANG,PASSWORD])
add('p_pdf_ppt','PDF 轉 PowerPoint','可選保留頁面外觀，或建立可編輯文字方塊','從 PDF 轉換',[F('mode','方式','select','editable',options=[['editable','可編輯文字＋圖片'],['visual','保留外觀（整頁圖片）']]),OCR,LANG,PASSWORD])
add('p_pdf_excel','PDF 轉 Excel','擷取文字表格；找不到表格時附上逐行文字表','從 PDF 轉換',[OCR,LANG,PASSWORD])
add('p_pdf_excel_ocr','PDF 轉 Excel（OCR）','辨識掃描表格後按欄位位置重建試算表','從 PDF 轉換',[LANG,PASSWORD])
add('p_pdfa','PDF 轉 PDF/A','本機產生 PDF/A-2b，輸出檢查報告；數位簽章會失效','從 PDF 轉換',[PASSWORD])
add('p_numbers','添加頁碼','位置、字級、起始頁碼與頁碼範圍可調整','編輯',[PAGE,F('start','起始號碼','number',1,min=1),F('format','顯示方式','select','total',options=[['total','第 n / N 頁'],['number','只有號碼']]),F('pos','位置','select','bc',options=[['bc','下方置中'],['br','右下'],['bl','左下'],['tc','上方置中'],['tr','右上'],['tl','左上']]),F('size','字級','number',11,min=6,max=72),F('color','顏色','color','#333333'),PASSWORD])
add('p_watermark','添加浮水印','文字或圖片，支援透明度、位置與斜向平鋪','編輯',[F('kind','種類','select','text',options=[['text','文字'],['image','圖片']]),F('text','浮水印文字','text','僅供參考',show={'kind':'text'}),F('image','圖片','file','',filter='圖片 (*.png;*.jpg;*.webp)',show={'kind':'image'}),F('opacity','不透明度 %','number',25,min=1,max=100),F('size','大小（頁面寬度 %）','number',35,min=5,max=90),F('tile','斜向平鋪','check',False),F('color','文字顏色','color','#808080'),PAGE,PASSWORD])
add('p_crop','裁剪 PDF','預覽框選或設定邊距；裁剪後內容仍可透過修改裁切框恢復','編輯',[F('mode','方式','select','margin',options=[['margin','設定四邊邊距'],['rect','預覽框選']]),F('margin','各邊邊距（毫米）','number',10,min=0,max=100,show={'mode':'margin'}),F('rect','保留範圍','rect','',show={'mode':'rect'}),F('preview_page','框選頁碼','number',1,min=1),PAGE,PASSWORD])
add('p_edit','編輯 PDF 文件','在 PDF 工作台加字、圖片、形狀與自由手繪；存成新檔','編輯',[F('actions','編輯項目（由工作台建立）','json','[]'),PASSWORD])
add('p_forms','PDF 表單','建立、填寫、偵測既有欄位，或將表單壓平','編輯',[F('mode','方式','select','fill',options=[['fill','填寫既有欄位'],['create','建立欄位'],['detect','偵測底線／方框並建立候選欄位'],['flatten','壓平表單與註記']]),F('actions','欄位內容（由工作台建立）','json','[]'),F('flatten','填寫後壓平','check',False),PASSWORD])
add('p_sign','PDF 簽名','在頁面放置手寫簽名、姓名、日期或公司章','安全',[F('actions','簽名項目（由工作台建立）','json','[]'),PASSWORD])
add('p_certificate','PDF 數位簽章','使用自己的 PFX／P12 憑證離線簽署；沒有線上時間戳','安全',[F('pfx','簽署憑證','file','',filter='憑證 (*.pfx;*.p12)'),F('pfx_pw','憑證密碼','password',''),F('name','簽章欄位名稱','text','Signature1'),F('reason','簽署原因','text','文件確認')])
add('p_redact','PDF 標記密文／永久遮蔽','永久移除選取的文字、圖片與繪圖，再清除隱藏資料','安全',[F('text','搜尋並移除的文字（選填）'),F('rect','遮蔽區域（選填）','rect',''),F('preview_page','框選頁碼','number',1,min=1),F('actions','多個遮蔽範圍（由工作台建立）','json','[]'),PAGE,F('confirmed','已確認遮蔽範圍，永久移除內容','check',False),PASSWORD])
add('p_compare','比較 PDF','逐頁比較文字與畫面，產生並排差異報告','安全',[F('visual','包含畫面差異','check',True),PASSWORD],together=True,max_files=2)
add('p_summary','AI 摘要產生器','本機文字模型產生摘要，亦提供快速重點摘錄','智慧',[F('mode','方式','select','ai',options=[['ai','離線 AI 摘要'],['extract','快速摘錄（保留原文句子）']]),F('language','摘要語言','select','繁體中文',options=[['繁體中文','繁體中文'],['English','English'],['原文','原文']]),F('length','每節重點數','number',5,min=2,max=15),OCR,LANG,PASSWORD])
add('p_translate','PDF 翻譯','離線模型逐段翻譯，輸出譯文及雙語對照；版面重新排版','智慧',[F('language','翻譯成','select','繁體中文',options=[['繁體中文','繁體中文'],['简体中文','簡體中文'],['English','英文'],['日本語','日文'],['한국어','韓文'],['Deutsch','德文'],['Français','法文'],['Español','西班牙文']]),OCR,LANG,PASSWORD])
add('p_markdown','PDF 轉 Markdown','擷取標題、文字、表格、圖片與連結；支援 OCR','智慧',[OCR,LANG,PASSWORD])
add('p_copy','複製 PDF','建立独立副本，保留原始位元內容','更多',[])
add('p_content','PDF 擷取','擷取文字、內嵌圖片、附件、書籤與頁面資訊','更多',[PASSWORD])
add('p_flatten','PDF 壓平','將表單及註記轉為頁面內容','更多',[PASSWORD])
add('p_workflow','掃描文件交付流程','OCR、Word 副本與 PDF/A 平行產出；憑證簽章安排在最後','更多',[LANG,F('word','另外輸出可編輯 Word','check',True),F('archive','產生 PDF/A 歸檔版本','check',True),F('sign','最後使用憑證簽署 PDF','check',False),F('pfx','簽署憑證','file','',filter='憑證 (*.pfx;*.p12)',show={'sign':True}),F('pfx_pw','憑證密碼','password','',show={'sign':True}),PASSWORD])

SECTIONS=['整理','優化','轉成 PDF','從 PDF 轉換','編輯','安全','智慧','更多']
CATALOG=[dict(id=t['id'],name=t['name'],section=t['section'],description=t['desc']) for t in TOOLS]
CATALOG += [dict(id=id,name=name,section=section,description=description) for id,name,section,description in [
 ('p_split','拆分 PDF','整理','逐頁、指定頁數或頁碼範圍拆分'),('p_rotate','旋轉 PDF','編輯','選擇頁碼與旋轉角度'),('p_decrypt','PDF 解鎖','安全','使用已知密碼解除加密'),('p_encrypt','PDF 加密','安全','AES-256 加密'),('workflow','PDF 工作流程','更多','可保存、重用並依序串接本機工具')]]
