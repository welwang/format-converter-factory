# 轉檔工廠（Format Converter Factory）

> 一個**免安裝環境、離線執行**的 Windows 全能轉檔工具。把檔案拖進去，自動判斷類型、建議格式、一鍵轉好。
> 目標：比「格式工廠」更快、更好用、看起來更現代。

- 介面：繁體中文，白色／深色主題，圓角玻璃質感按鈕，低調的任務控制台風格
- 執行：雙擊 `轉檔工廠.exe`，不需要 Python、瀏覽器分頁或命令列；所有轉檔引擎都放在 `tools\` 資料夾裡
- 系統：Windows 10／11 x64（使用系統內建的 Microsoft Edge WebView2）
- 授權：GPLv3（見 [LICENSE](LICENSE) 與 [授權說明.md](授權說明.md)）

---

## 目錄
1. [主要功能](#主要功能)
2. [支援格式](#支援格式)
3. [工具箱](#工具箱)
4. [架構](#架構)
5. [資料夾結構](#資料夾結構)
6. [從原始碼建置](#從原始碼建置)
7. [大小](#大小)
8. [測試結果](#測試結果)
9. [已知限制與尚未驗證](#已知限制與尚未驗證)
10. [參考的開源專案](#參考的開源專案)
11. [授權](#授權)

---

## 主要功能

**轉檔核心**
- 拖放多個檔案或整個資料夾（會遞迴掃描），也可以把檔案拖到 exe 圖示上，或用檔案總管右鍵「傳送到」
- 自動判斷類型並建議目標格式；「全部轉成」一次套用到所有檔案
- 品質三段：**高品質／均衡／小檔案**；可指定**目標大小（MB）**，影片自動算位元率，JPG／WebP／AVIF 自動調整品質
- 裁剪（開始／結束秒數）、縮放（高度）、合併（影片接續、多圖合成 PDF、多份 PDF 合併）
- **盡量不重新編碼**（預設開啟）：例如 MKV→MP4 且編碼相容時直接換封裝，19 MB 檔案 0.14 秒完成、畫質零損失
- **音量標準化**：EBU R128 響度（-16 LUFS）
- **硬體加速**：自動偵測 NVIDIA NVENC／Intel QSV／AMD AMF，失敗時自動改用 CPU
- 平行佇列：依 CPU 核心數自動決定同時轉幾個（2～4），即時顯示進度、速度、剩餘時間，可單一或全部取消
- 輸出到原資料夾或指定資料夾；**永遠不覆蓋原檔**，重名自動加 ` (1)`、` (2)`
- 記住上次設定（主題、品質、輸出位置、各開關）
- 搜尋框可直接查格式支援；「支援格式」表格列出每一類的輸入、輸出、使用引擎與限制

**延伸功能**（`capture.py`）
- 螢幕錄影（可選螢幕與音訊裝置，快捷鍵開始／停止，支援硬體編碼）
- 網址下載影片／音訊（yt-dlp）
- 監看資料夾：新檔案出現就自動依規則轉檔
- 佇列完成後動作（例如自動關機，可取消）

## 支援格式

| 類別 | 可讀取 | 可輸出 | 引擎 |
|---|---|---|---|
| 影片 | mp4 mkv webm mov avi flv wmv m4v ts mts 3gp mpg mpeg gif | mp4 mkv webm mov avi gif，以及所有音訊格式、srt（抽出字幕軌） | FFmpeg |
| 音訊 | mp3 aac m4a wav flac ogg opus wma amr aiff | mp3 aac m4a wav flac ogg opus | FFmpeg |
| 圖片 | jpg jpeg png webp avif heic heif ico bmp tif tiff psd svg tga jp2 jfif pcx dds qoi，相機 RAW（cr2 cr3 nef arw dng orf rw2 raf pef srw） | jpg png webp avif ico bmp tiff pdf | Pillow／pillow-heif／LibRaw（rawpy）／psd-tools／resvg |
| PDF | pdf | png jpg（每頁一張）、txt、pdf（合併）、docx、epub | PDFium／pypdf／Calibre |
| 文件 | doc docx odt rtf txt md html htm tex rst org | pdf docx odt html md txt epub rtf | Pandoc（輕量文字格式）／LibreOffice（Office 與轉 PDF） |
| 試算表／簡報 | xls xlsx ods csv ppt pptx odp | pdf xlsx ods csv pptx odp | LibreOffice |
| 電子書 | epub mobi azw3 fb2 | epub mobi azw3 pdf docx txt | Calibre |
| 壓縮檔 | zip 7z rar tar gz tgz bz2 xz zst cab iso | 解壓縮、zip、7z | 7-Zip |
| 字幕 | srt ass ssa vtt sub lrc | srt ass vtt | FFmpeg |
| 3D 模型 | obj stl ply glb gltf off 3mf | glb obj stl ply | trimesh |

**明確不支援**（介面會直接標示原因）：有 DRM 的 Kindle KFX／舊 AZW、Apple Keynote／Numbers 專有格式、有防拷的 DVD／藍光。

## 工具箱

除了轉檔，`tools.py` 以「一個描述 + 一個函式」的方式註冊了 43 個常用工具，介面依描述自動產生表單，並共用同一個佇列（進度、取消都一樣）：

| 分類 | 工具 |
|---|---|
| 影片 | 社群一鍵規格（直式短影音、方形、壓到 10／20 MB）、改比例（模糊背景）、裁切、旋轉／翻轉、變速、文字浮水印、圖片浮水印、去除浮水印、加字幕（燒入或內嵌）、**AI 自動字幕**（whisper.cpp 離線辨識，可轉繁體）、配樂／換音軌、去除聲音、分割、防手震、畫面調整、淡入淡出、倒轉、擷取畫面／縮圖總覽、多支影片並排 |
| 音訊 | 音量／淡入淡出、變速／變調、去人聲、降噪、去除靜音、混音、鈴聲製作（M4R）、歌曲資訊／封面 |
| 圖片 | 批次縮放、旋轉／翻轉／裁切、圖片浮水印（可斜向平鋪）、拼長圖／九宮格、圖片轉影片、圖片轉 GIF |
| PDF | 分割、頁面整理、旋轉、加密、解除密碼 |
| 其他 | 隱私清除（移除照片 GPS／拍攝資訊、影片位置、PDF 作者；JPG／PNG 無損） |
| 光碟 | DVD 轉影片、藍光轉影片、音樂 CD 轉檔、光碟轉 ISO（僅限無防拷光碟） |

AI 字幕第一次使用時會從 Hugging Face 下載 whisper.cpp 模型；簡轉繁使用內附的 OpenCC 詞庫（`_build/src/zhdict`）。

## 架構

```
┌──────────── 轉檔工廠.exe（PyInstaller onedir）────────────┐
│ app.py      pywebview 視窗（Edge WebView2）＋ JS API       │
│ ui/         單一 HTML/CSS/JS 介面（白／深色主題）          │
│ engine.py   檔案分類、格式表、佇列（ThreadPool）、進度解析 │
│ tools.py    工具箱註冊表與實作                              │
│ capture.py  螢幕錄影、網址下載、監看資料夾、完成後動作      │
│ zhconv.py   OpenCC 詞庫簡轉繁（台灣用語）                    │
└───────────────┬────────────────────────────────────────────┘
                │ subprocess（隱藏視窗）
   tools\ffmpeg.exe   tools\libreoffice\   tools\calibre\
   tools\pandoc.exe   tools\7z.exe         tools\yt-dlp.exe
```

設計原則：
- **一個工作只用一個最合適的引擎**，不重疊：影音字幕＝FFmpeg、圖片＝Pillow 系列、PDF＝PDFium／pypdf、輕量文件＝Pandoc、Office＝LibreOffice、電子書＝Calibre、壓縮＝7-Zip、3D＝trimesh
- **一律優先使用 `tools\` 內建引擎**，找不到才退回系統已安裝版本，所以整個資料夾可以直接複製到別台電腦
- 進度：FFmpeg 用 `-progress pipe:1` 解析時間碼與速度；其他引擎依頁數／檔案數估算
- 不需要 ffprobe：長度與串流資訊直接解析 `ffmpeg -i`（省 210 MB）
- LibreOffice 每次用獨立的暫存設定檔（`-env:UserInstallation`），可平行執行、不影響使用者自己的 LibreOffice
- 硬體編碼器在背景偵測（實際試編 0.2 秒），不拖慢開啟速度
- 設定存在 exe 旁的 `settings.json`

## 資料夾結構

```
轉檔工廠\
├─ 轉檔工廠.exe              主程式（建置產物，不在 repo）
├─ _internal\                Python 執行環境與套件（建置產物，不在 repo）
├─ tools\                    內建引擎（不在 repo，見「從原始碼建置」）
├─ 輸出\                     安裝程式輸出（不在 repo）
├─ 使用說明.md               使用者說明
├─ 授權說明.md               第三方元件授權
├─ README.md / LICENSE
├─ autosync\                 自動同步到 GitHub 的腳本（install.ps1 安裝排程工作）
└─ _build\
   ├─ src\                   原始碼（app.py engine.py tools.py capture.py zhconv.py ui\ zhdict\）
   ├─ build.ps1              PyInstaller 建置並放到根目錄
   ├─ ZDGC.spec              PyInstaller 設定
   ├─ setup.iss              Inno Setup 安裝程式腳本
   ├─ 精簡tools.ps1          把 tools 裡用不到的元件移出（可還原）
   ├─ shot.ps1               截圖（白／深色）
   └─ logo.ico / logo_512.png
```

## 從原始碼建置

建置工具只在建置時需要，執行時完全不需要。

1. 安裝 Python 3.12，在 `_build` 建立虛擬環境：
   ```powershell
   cd E:\轉檔工廠\_build
   python -m venv venv
   .\venv\Scripts\python -m pip install pywebview pyinstaller pillow pillow-heif pypdf pypdfium2 rawpy psd-tools resvg-py trimesh
   ```
2. 準備 `tools\`（放在專案根目錄）：
   - `ffmpeg.exe`：gyan.dev full build（含 NVENC／QSV／AMF、libvpx、libopus、whisper 濾鏡）
   - `7z.exe`、`7z.dll`：7-Zip
   - `pandoc.exe`：Pandoc 官方 Windows zip
   - `yt-dlp.exe`：yt-dlp 官方 release
   - `libreoffice\`：LibreOffice 完整程式資料夾（可刪除 help、gallery、template、wizards、extensions、Java classes、多餘語言與圖示主題）
   - `calibre\`：用 `msiexec /a calibre-64bit-<版本>.msi /qn TARGETDIR=...` 解開（不會安裝到系統），複製 `Calibre2` 內容
   - 可執行 `_build\精簡tools.ps1` 再縮小體積（移到 `_build\pruned`，可用 `-Restore` 還原）
3. 建置主程式：`powershell -ExecutionPolicy Bypass -File _build\build.ps1`
4. 建置安裝程式：用 Inno Setup 7（可用 `/PORTABLE=1` 解到 `_build\inno`，不安裝到系統）
   ```powershell
   _build\inno\ISCC.exe _build\setup.iss
   ```
   產出 `輸出\轉檔工廠安裝程式.exe`：繁體中文介面、可選安裝位置、免系統管理員（安裝到 `%LOCALAPPDATA%\Programs`）、桌面與開始功能表捷徑、右鍵「傳送到」、解除安裝程式。
5. 自我測試（不開視窗，結果寫到 `selftest.log`）：
   ```powershell
   $env:PATH='C:\Windows\System32;C:\Windows'   # 模擬乾淨電腦
   .\轉檔工廠.exe --selftest <放測試檔的資料夾>
   ```

## 大小

| 項目 | 大小 |
|---|---|
| 免安裝版整個資料夾 | 約 1.66 GB |
| └ Calibre | 573 MB |
| └ LibreOffice | 519 MB |
| └ Pandoc | 225 MB |
| └ FFmpeg | 212 MB |
| └ yt-dlp | 17 MB |
| └ 7-Zip | 2 MB |
| └ 主程式＋Python 環境（`_internal`） | 約 60 MB |
| 安裝程式（LZMA2 壓縮） | 381 MB |

## 測試結果

在 Windows 11（RTX 4060）上，以 `--selftest` 搭配產生的樣本檔、**PATH 移除 Python 與 FFmpeg** 執行，44 項轉換全部成功；KFX 依設計被拒絕（DRM）；取消功能正常。執行期間監看程序路徑，確認 LibreOffice、Calibre、Pandoc 都是從 `tools\` 執行，而不是系統已安裝的版本。

| 類別 | 已測試 |
|---|---|
| 影片 | MP4→MKV（直接封裝 0.12 秒）、MP4→MP4 720p（CPU 0.94 秒／NVENC 1.20 秒）、→WebM、→GIF（裁剪 3 秒）、→MP3、目標 2 MB、MKV→MP4 不重新編碼、兩段合併、取消 |
| 音訊 | WAV→FLAC／Opus／M4A、WAV→MP3＋音量標準化 |
| 圖片 | PNG→WebP／AVIF／ICO／JPG（目標 0.1 MB）、HEIC→JPG、SVG→PNG、多圖→PDF |
| PDF | PDF→PNG、PDF→TXT |
| 文件 | MD→DOCX／HTML／EPUB、DOCX→MD（Pandoc）；TXT／DOCX／DOC／PPT→PDF、CSV→XLSX／PDF、XLS→XLSX（LibreOffice） |
| 電子書 | EPUB→DOCX／MOBI／AZW3（Calibre）、MOBI→EPUB |
| 壓縮 | ZIP、TAR.GZ 解壓縮、ZIP→7Z |
| 字幕／3D | SRT→VTT／ASS、STL→GLB／OBJ |
| 安裝程式 | 靜默安裝→捷徑與解除安裝項目建立→開啟→靜默解除安裝並清乾淨 |

> 速度數據使用合成測試影片（對 CPU 很輕鬆），不代表實際影片上 GPU 的優勢。

## 已知限制與尚未驗證

- 尚未在**完全乾淨的第二台電腦**上測試（目前以 PATH 隔離與程序路徑檢查驗證）
- 相機 RAW、PSD 沒有樣本檔，尚未實測
- 真正用滑鼠拖放、檔案選擇視窗尚未自動化測試
- Intel QSV／AMD AMF 只在程式邏輯上支援，測試機只有 NVIDIA
- 目標大小為單次編碼估算，可能有約 ±20% 誤差；JPG 目標大小可能略超出 1%
- 精簡過的 LibreOffice／Calibre 只測過上表格式，較罕見的格式可能需要被移除的元件
- 工具箱、螢幕錄影、網址下載、監看資料夾等延伸功能為後續加入，尚未納入上表的自我測試
- AI 自動字幕第一次使用需要連網下載模型
- 需要系統有 Edge WebView2（Windows 11 與更新過的 Windows 10 皆內建）

## 參考的開源專案

研究了下列專案，挑出最實用的功能，去掉重複、整合成「預設一鍵、進階收合」的介面：

| 專案 | 借用的概念 | 來源 |
|---|---|---|
| Shutter Encoder | 不重新編碼直接換封裝／剪輯、響度標準化、依功能分類的工具 | https://www.shutterencoder.com/ |
| FFmpeg Batch AV Converter | 依 CPU 平行處理多檔、固定目標大小、裁剪與串接、監看資料夾、完成後關機 | https://ffmpeg-batch.sourceforge.io/index.html 、 https://github.com/eibol/ffmpeg_batch |
| HandBrake | 硬體編碼器搭配品質預設、失敗退回 CPU | https://handbrake.fr/docs/en/latest/technical/video-qsv.html |
| File Converter | 檔案總管右鍵轉檔、拖到圖示即轉 | https://github.com/Tichau/FileConverter 、 https://github.com/Tichau/FileConverter/wiki |
| ConvertX | 每類格式對應一個最適合的引擎（FFmpeg、LibreOffice、Calibre、Pandoc、resvg…） | https://github.com/C4illin/ConvertX |
| VERT | 完全本機處理、不上傳、無檔案大小限制 | https://github.com/VERT-sh/VERT |
| Cove | 每檔一個目標格式下拉選單、資料夾遞迴、自動重新命名 | https://github.com/Sin213/cove-universal-converter |
| XnConvert | 批次圖片處理（縮放、浮水印、隱私資訊）；80 種串接動作則刻意不做，保持簡單 | https://www.xnview.com/en/xnconvert/ |

## 授權

本專案原始碼以 **GNU GPLv3** 釋出（因內附的 FFmpeg 完整版為 GPLv3）。內附的第三方引擎各自依其授權散布：FFmpeg（GPLv3）、LibreOffice（MPL 2.0）、Calibre（GPLv3）、Pandoc（GPLv2+）、7-Zip（LGPL＋unRAR 限制）、yt-dlp（Unlicense）、OpenCC 詞庫（Apache-2.0）以及多個 Python 套件。完整清單與原始碼連結見 [授權說明.md](授權說明.md)。

安裝程式與免安裝版請到 [Releases](../../releases) 下載。

> 本專案已設定自動同步：在 welsPC 修改原始碼後約 2～3 分鐘內會自動上傳到 GitHub（要暫停或恢復，請在「工作排程器」停用／啟用 ZDGC-AutoSync，或使用本機自備的暫停／恢復腳本）。
