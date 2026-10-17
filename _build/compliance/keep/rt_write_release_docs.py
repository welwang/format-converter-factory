import json,re,html,shutil,platform,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;stage=R/'release';assets=stage/'assets';assets.mkdir(exist_ok=True)
# 版本單一來源：_build/setup.iss 的 AppVer（實際出貨版本）。文件不得再自己寫死版本。
_iss=(R/'../../setup.iss').resolve()
_m=re.search(r'AppVer\s+"([^"]+)"',_iss.read_text(encoding='utf-8'))
VER=_m.group(1) if _m else 'UNKNOWN'
assert VER!='UNKNOWN',f'setup.iss 找不到 AppVer：{_iss}'
shutil.copy2(R/'assets/logo.png',assets/'logo.png')
for name in ['ui-pdf-catalogue.png','ui-pdf-editor.png']:shutil.copy2(R/name,assets/name)
def read(name):return (R/name).read_text(encoding='utf-8-sig')
sets=[('C 轉檔與工作控制','windows-engine-checks/results.json',30),('C／Python 內容比對','windows-engine-checks/equivalence.json',28),('C 編碼與加速選項','native-option-checks/results.json',6),('PDF 打包元件','pdf-frozen/results.json',12),('介面與表單','ui-results.json',96),('Unicode 與來源網址限制','uri-results.json',8),('精簡資源與模型內容','size-content-tests.json',4),('新版圖示資源','logo-resource-results.json',2)]
for title,filename,n in sets:
 data=json.loads(read(filename));assert len(data)==n and all(r['ok'] for r in data),(filename,data)
logs=[('完整離線自我測試','selftest-final/selftest.log',81),('PDF 功能與內容','pdf-tests.log',46),('OCR 交付與下載','additional-tests.log',5),('工作流程與電腦工具','integration-tests.log',35),('視窗管線與對話框','protocol-tests.log',6),('特殊格式與設備邊界','feature-tests.log',14)]
for title,f,n in logs:
 s=read(f);assert 'FAILED (' not in s and not re.search(r'^FAIL\s',s,re.M),f
 assert (f'結果：{n} / {n} 通過' in s if n==81 else f'Ran {n} tests' in s and '\nOK' in s),f
smoke=json.loads(read('native-window-smoke.json'));assert smoke['ok'] and smoke['completion_notifications']>=1,smoke
rows=[(t,n) for t,_,n in sets]+[(t,n) for t,_,n in logs]+[('Windows 原生視窗整合',1)];total=sum(n for _,n in rows)
report=f'''# 四維八德 {VER} 測試報告

![四維八德藍寶石 Logo](assets/logo.png)

測試日期：2026-10-15（Asia/Taipei）。最終已執行測試 **{total}／{total} 通過，0 項失敗**。介面涵蓋 82 個工具、446 種表單狀態。相同功能在不同層的檢查分別計數；數字不是不重複的功能數，也不表示所有電腦、所有文件或 AI 輸出都沒有錯誤。

## 測試環境與方法

Windows AMD64，系統版本 10.0.26300，20 個 CPU 執行緒，已偵測 NVIDIA NVENC；Python 3.12.10、MSVC、WebView2。C 程式實際在 Windows 編譯並執行。使用自行產生的影音、圖片、文件、壓縮檔、RAW／PSD、OCR 圖片及測試憑證。未錄製使用者螢幕、麥克風或實際修復使用者磁碟。

| 測試組 | 通過 | 失敗 |
|---|---:|---:|
'''+''.join(f'| {t} | {n}/{n} | 0 |\n' for t,n in rows)+'''
## {VER} Logo 更新與回歸驗證

側邊欄 34 px 與拖放區 44 px 使用無節點小圖，關於視窗 84 px 保留完整版。新增三項介面位置／尺寸／載入檢查及兩個程式的 ICO 資源雜湊比對。小尺寸高度配置仍依既有響應式樣式調整。本輪完整重跑原有測試，沒有把前版結果當作本版新測試。安裝包圖示與實際安装另在打包後驗證。

首次在沙箱執行時，暫存路徑权限阻擋部分外部引擎，已改在正常 Windows 環境重新執行；受阻結果未計為通過。一次共用測試暫存狀態下 CSV 轉 XLSX 未完成，最終完整離線測試使用獨立乾淨資料夾重跑。

## 既有修正與回歸驗證

- C 建置腳本的路徑引號錯誤，已修正並完成 Windows 編譯。
- 安裝在中文路徑時，WebView2 的 UTF-8 網址被誤判為其他頁面；已修正單次解碼並通過中文、空白、百分比、特殊字元與混合 Unicode 的檢查。
- 有格式篩選條件的檔案對話框引用錯誤，已修正；開檔、另存與選資料夾往返測試均通過。
- 短於監看間隔的工作可能漏掉完成通知；改為依工作建立時間記錄新完成工作，實際混合 C／Python 工作已收到一次完成通知。
- JSON 數值精度不足可能影響時間判斷，改為保留雙精度數值。
- C 与 Python 的 Office 引擎原先共用暫存設定資料夾，已拆開避免彼此佔用。
- CD 裝置的 64 位元控制代碼型別與一般磁碟防誤選；讀取失敗的磁區會明示警告。
- 錄影子程序結束後關閉管線；原生引擎加入程序群組結束時清理，避免引擎殘留。
- 背景通訊隔離標準輸出，避免第三方元件輸出混入呼叫結果；秘密參數不寫入例外記錄。
- 介面只接受自己的本機頁面呼叫，其他頁面的導覽會被拒絕；測試說明入口會回報找不到檔案等問題。

## 實際內容驗證

C 与 Python 的 28 組相同轉檔比對影音解碼影格與音訊、PDF 頁面像素與文字、Word／EPUB 文字、解壓縮內容與字幕文字。容量限制轉檔採用容量、影格數與時間一致檢查：受有損編碼與位元率控制影響，兩邊畫面雜湊可能不同。封裝時間戳、隨機識別碼與 ZIP 中繼資料不作為内容不同的判斷。

PDF 測試檢查合併後頁數與文字、刪除／抽取順序、OCR 可搜尋文字、Office 輸出、表單填值與新增欄位、永久遮蔽後秘密文字不存在、簽章欄位存在及原始文件保留。PDF/A 測試使用本機 Ghostscript 產生並檢查輸出；尚未經獨立 veraPDF 認證。自簽憑證用於功能測試，不代表公開信任、法定效力或時間戳。

AI 測試包含本機字幕、Word 逐字稿、快速摘錄與離線模型會議摘要、PDF 摘要及翻譯。檢查程序完成、檔案與文字存在，**不代表語音辨識逐字正確或翻譯、摘要的語意品質達到 100%**。實測辨識會將「四維八德」寫為同音字，仍需人工校對。

## 各項測試詳細結果
'''
for title,f,n in sets:
 report+='\n### '+title+'\n\n| 項目 | 結果 | 補充 |\n|---|---|---|\n'
 for item in json.loads(read(f)):
  detail=item.get('encoder') or item.get('validation') or (str(item['variants'])+' 種表單狀態' if 'variants' in item else '')
  report+=f"| {item['name']} | 通過 | {str(detail).replace('|','／')} |\n"
for title,f,n in logs:
 report+='\n### '+title+'\n\n| 項目 | 結果 |\n|---|---|\n'
 s=read(f)
 if n==81:
  names=[re.sub(r'\s+\d+\.\d+s.*$','',line[5:].strip()) for line in s.splitlines() if line.startswith('OK  ')]
 else:names=re.findall(r'^(test\S+)\s+\([^\n]+\)\s+\.\.\.',s,re.M)
 for name in names:
  name=re.sub(r"[A-Za-z]:\\[^'}\n]+",'[測試資料夾]',name)
  report+=f'| {name.replace("|","／")} | 通過 |\n'
report+='''
## 設備與相容性的未驗證範圍

| 範圍 | 本次完成 | 尚未驗證 |
|---|---|---|
| Windows | 本機 Windows AMD64 編譯、執行與 WebView2 實測 | Windows 10 乾淨安裝、所有 Windows 11 更新版本、ARM x64 模擬、32 位元 |
| 低規格 | 記憶體／CPU 限制邏輯與省資源模式 | 實體 4 GB RAM、慢速硬碟與無顯示卡電腦的完整壓力測試 |
| GPU | 本機 NVENC 與 CPU 編码實際轉檔 | Intel QSV、AMD AMF 與不同驅動；本機通過不推論其他顯示卡也通過 |
| 錄影 | 自製影像來源的 FFmpeg 錄製、停止與 MKV→MP4 流程 | 真實桌面擷取、多螢幕、麥克風、熱鍵的實體操作 |
| 掃描器 | 匯入掃描圖片、OCR、Word 與 PDF/A 輸出 | 實際 WIA 掃描器及驅動 |
| 光碟 | 自製 DVD VOB 轉檔；CD／ISO 控制代碼與資料流模擬 | 真實 CD、ISO 檔案系統、Blu-ray 成功讀片；不提供繞過防拷能力 |
| 下載 | 本機 HTTP 伺服器實際下載與轉 MP3，Unicode 檔名；開啟、顯示位置路由 | 未提供失敗的 YouTube 網址；未逐站檢查網路服務，網站改版會影響下載 |
| 檔案 | 列出的自製標準與邊界文件 | 所有損毀、超大、特殊字型及惡意檔案；PDF 轉 Office 的複雜版面仍需人工檢查 |

## 發布狀態

安裝包、應用程式來源與文件在 GitHub 公開發布；FFmpeg full build 的所有間接程式庫與精確建置來源、部分既有引擎的完整對應來源仍待核實。不得將此狀態寫成「已排除所有法律風險」。GNU GPL 的二進位散布條件需提供相應來源，見 [GPLv3 第 6 條](https://www.gnu.org/licenses/gpl-3.0.html#section6) 與 [GNU 授權常見問題](https://www.gnu.org/licenses/gpl-faq.html#SourceAndBinaryOnDifferentSites)。詳細清單見 source/來源清單.json 與「開源與散布說明.md」。
'''
(stage/'TEST_RESULTS.md').write_text(report,encoding='utf-8')
css='''body{margin:0;background:#f3f6fb;color:#192b44;font:16px/1.75 "Segoe UI","Microsoft JhengHei",sans-serif}main{max-width:1080px;margin:36px auto;padding:32px;background:white;border-radius:20px;box-shadow:0 12px 42px #143d5d12}h1{font-size:32px}h2{margin-top:36px;border-top:1px solid #e0e8f2;padding-top:24px}h3{margin-top:28px}table{width:100%;border-collapse:collapse;font-size:14px;margin:20px 0}td,th{padding:10px 12px;text-align:left;border-bottom:1px solid #e4eaf2}th{background:#eef5ff;color:#164985}a{color:#006ad3}img{width:120px;height:120px;object-fit:contain;border-radius:24px}li{margin:8px 0}.lead{color:#376c91;background:#eaf4ff;padding:20px;border-radius:12px}@media(max-width:750px){main{margin:0;padding:18px;border-radius:0}table{font-size:12px;display:block;overflow:auto}}'''
lines=report.splitlines();parts=[];in_table=False;in_list=False
def inline(s):
 s=html.escape(s);s=re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',s);s=re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s);return s
for line in lines:
 if not line.startswith('|') and in_table:parts.append('</tbody></table>');in_table=False
 if not line.startswith('- ') and in_list:parts.append('</ul>');in_list=False
 if line.startswith('|'):
  if re.fullmatch(r'[| :\-]+',line):continue
  cells=[inline(c.strip()) for c in line.strip('|').split('|')]
  tag='td'
  if not in_table:parts.append('<table><tbody>');in_table=True;tag='th'
  parts.append('<tr>'+''.join(f'<{tag}>{c}</{tag}>' for c in cells)+'</tr>');continue
 if line.startswith('#'):
  n=len(line)-len(line.lstrip('#'));parts.append(f'<h{n}>{inline(line[n:].strip())}</h{n}>')
 elif line.startswith('!['):parts.append('<img src="assets/logo.png" alt="四維八德藍寶石 Logo">')
 elif line.startswith('- '):
  if not in_list:parts.append('<ul>');in_list=True
  parts.append('<li>'+inline(line[2:])+'</li>')
 elif line:parts.append('<p>'+inline(line)+'</p>')
(stage/'測試報告.html').write_text('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>四維八德 ' + VER + ' 測試報告</title><style>'+css+'</style><main>'+''.join(parts)+'</main></html>',encoding='utf-8')
readme='''<p align="center"><img src="assets/logo.png" width="160" alt="四維八德藍寶石 Logo"></p>

# 四維八德

開源的 Windows 本機轉檔與文件工具。影音、圖片、Office、電子書、壓縮檔、字幕與 PDF 在自己的電腦處理；OCR、字幕辨識、摘要與翻譯的離線模型隨完整安裝包附帶。無需 iLovePDF 帳號或 API，PDF 功能自行實作。

**{VER} 狀態：已公開發布。完整安裝包與來源封裝可從版本發布頁下載；第三方對應來源散布審核仍未完成。**

[版本發布頁](https://github.com/welwang/format-converter-factory/releases) · [詳細使用說明](使用說明.md) · [完整測試結果](TEST_RESULTS.md) · [PDF 功能清單](PDF功能清單.md) · [開源與散布條件](開源與散布說明.md)

## 安裝與系統需求

執行 `四維八德_{VER}_離線安裝程式.exe`，選擇位置與捷徑，完成後開啟四維八德。預設裝到目前使用者的程式資料夾；不需要安裝 Python、Microsoft Office 或獨立轉檔工具。缺少 WebView2 時可使用隨附的離線安裝程式；系統元件安裝依 Windows 權限決定。

- 目標平台：Windows 10／11，x64；32 位元與 Windows 7／8 不在本版支援範圍。
- 建議至少 4 GB RAM；8 GB 以上較合適，AI 與大檔案可能需要更多記憶體。本版尚未在實體 4 GB 電腦完成全功能驗證。
- 完整離線版安裝約需 5 GB，另預留安裝暫存及輸出空間；實際以安裝程式顯示為準。
- CPU 可執行基本轉檔與離線模型；GPU 可加速影音。本機已測 NVIDIA NVENC，Intel／AMD 與其他驅動仍需驗證。
- 網址下載、下載元件更新與外部文件連結需要網路。其餘列出的本機處理功能附引擎與模型，沒有 API 金鑰或雲端 PDF 依賴。

## 使用方式

1. 將素材拖進視窗，或按「加入檔案」。選擇一般轉檔、PDF 工作台或工具箱。
2. 指定格式、品質、目標容量與輸出資料夾，或在 PDF 頁面上框選加入文字、簽名與遮蔽。
3. 按「開始」，在工作進度中查看結果；「開啟」使用 Windows 預設程式，「資料夾」按鈕在檔案總管中定位成品。

程式保留原始素材，輸出名稱重複會另取名稱。錯誤工作可查看原因與重試。永久遮蔽與暫存清理必須預覽並確認。

## 功能

| 類型 | 內容 |
|---|---|
| 一般轉檔 | MP4、MKV、WebM、MOV、AVI、GIF，常見音訊；HEVC／AV1、容量限制、裁剪、合併與免重編碼 |
| 影音工具 | 影片改比例、字幕、浮水印、速度、防手震、配樂、截圖；音量、降噪、混音、鈴聲、歌曲資訊 |
| 圖片 | 常見圖片、HEIC、RAW、PSD、SVG；縮放、拼圖、浮水印、GIF、圖片轉影片 |
| PDF | 合併、拆分、移除／抽取／重排、壓縮、修復、OCR、掃描圖片轉 PDF、Office／HTML 轉 PDF、PDF 轉 Office／圖片／Markdown／PDF/A |
| PDF 編輯安全 | 頁碼、浮水印、裁剪、加字／圖片／圖形／手繪、表單、手寫及本機 PFX 簽章、AES 加密、已知密碼解鎖、永久遮蔽與比較 |
| 離線 AI | 自動字幕、逐字稿、會議摘要、PDF 摘要與翻譯；結果需人工校對 |
| 工作與電腦工具 | 可保存的交付流程、監看資料夾、排程控制；硬體資訊與小型測試、暫存掃描清理 |
| 更多 | 電子書、壓縮檔、字幕、3D 格式；錄影與合法授權內容下載、未加密光碟處理 |

![PDF 工作台](assets/ui-pdf-catalogue.png)

![PDF 視覺編輯](assets/ui-pdf-editor.png)

## 安裝包精簡

完整離線功能與三個模型位元內容保留。已測試的非執行資源與重複 DLL 移除，壓縮字典維持 64 MB，來源封裝在相同版本發布頁獨立下載；執行程式不需要來源封裝。

## {VER} 架構

| 元件 | 負責範圍 |
|---|---|
| `四維八德.exe`（C） | Win32／WebView2 視窗、真實檔案路徑拖放、原生對話框、單一實例、視窗位置記憶 |
| `engine.c`（C） | 一般影音、字幕、壓縮、Office／文件、電子書；組指令、呼叫隨附引擎、進度、工作取消／重試與輸出檢查 |
| `api.c`（C） | C／Python 工作分派與列表合併、完成通知與執行時電源管理 |
| `swbd-core.exe`（Python） | 圖片、PDF、3D、影音工具箱、AI、工作流程、錄影、下載、監看資料夾、電腦工具 |

這是 C 與 Python 的混合版本。FFmpeg、LibreOffice 等是隨附的第三方引擎；功能自行組合實作，不表示把第三方引擎全部重寫成 C。

## 測試

完整報告：[TEST_RESULTS.md](TEST_RESULTS.md)。程式「關於 → 測試結果」亦可離線開啟報告。

最終 374／374 個已執行案例通過、0 失敗；82 個工具表單、446 種狀態已檢查。涵蓋實際 C／Python 轉檔比對、Windows 原生視窗橋接、打包後 OCR／AI／簽章、下載完成檔案、硬體小型測試、清理邊界與命令注入防護。這不等於所有硬體、特殊文件或 AI 語意結果都已驗證；完整未驗證範圍列於報告。

## 原始碼建置

需 Windows x64、Visual Studio Build Tools 的 C++ 桌面開發元件、Python 3.12 與 Inno Setup。C 建置首次取得指定 WebView2 SDK，需要網路；日常本機處理不需要下載 SDK。

```powershell
python -m venv _build/venv
_build/venv/Scripts/python -m pip install -r _build/requirements-lock.txt
powershell -File _build/shell/build_shell.ps1
powershell -File _build/build.ps1 -SkipPackages
```

完整二進位建置另需 `tools` 的匹配版本、模型與授權來源；Git 不儲存數 GB 的引擎或私人設定。`_build/tests/release-tests` 保留此次測試工具；執行環境與測試資料夾需依各腳本設定。自我測試自行產生素材：

```powershell
.\\四維八德.exe --selftest .\\selftest --ai --no-open
.\\四維八德.exe --pdf-selftest .\\pdf-selftest
```

自我測試會測試 Python 元件；C 引擎另以 `engine_test_cli.c` 驗證。`--rec` 會擷取真實螢幕，本次未使用該選項。

## 授權與隱私

既有應用程式使用 GPLv3，新增 PDF 模組使用 AGPLv3。請閱讀 [LICENSE](LICENSE)、[COPYING.AGPL-3.0](COPYING.AGPL-3.0)、[第三方聲明](授權說明.md) 與 [散布說明](開源與散布說明.md)。Microsoft 元件、模型及其他依賴保留原授權；開源不自動免除第三方來源與著作權義務。

本機文件處理不對接 iLovePDF，也未使用其介面素材、商標或程式碼。Logo 使用使用者提供的四維八德藍寶石圖檔。來源、設定與日誌分開；發布不包含下載歷史、私人文件、憑證私鑰或個人設定。
'''
(stage/'README.md').write_text(readme,encoding='utf-8')
(R/'report-summary.json').write_text(json.dumps(dict(version=VER,passed=total,failed=0,groups=[dict(name=t,passed=n) for t,n in rows],ui_forms=82,ui_variants=446,physical_validation_complete=False,distribution_audit_complete=False),ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified report cases:',total)
