# 第三方元件聲明

> 這是舊版（轉檔工廠時期）第三方聲明的封存副本，只供比對；**現行有效的版本是專案根目錄的《授權說明.md》**。

四維八德（原名轉檔工廠）既有程式碼依 **GPLv3** 提供，新增 PDF 模組依 **AGPLv3** 提供，不是專有軟體。授權全文見專案根目錄的 `LICENSE` 與 `COPYING.AGPL-3.0`。

轉檔工廠另外附帶下列第三方元件。這些元件都是**獨立的執行檔或可替換的動態函式庫**，轉檔工廠以命令列呼叫（例如 FFmpeg、LibreOffice、Calibre、Pandoc、7-Zip）或動態載入的方式使用，**沒有修改任何元件的程式碼**（只刪除用不到的檔案），各元件依其原本的授權條款散布，你依各該授權享有的權利不受《使用授權條款》限制。

GPL／LGPL 元件的上游原始碼可由下表連結取得；與各發行版本對應的原始碼取得方式，以根目錄《開源與散布說明.md》與 `source/來源清單.json` 為準。

| 元件 | 用途 | 授權 | 原始碼 |
|---|---|---|---|
| FFmpeg 9.0.1（gyan.dev full build，只附 ffmpeg.exe，獨立程式） | 影片、音訊、字幕、HEIC 照片解碼 | GPLv3（含 x264、x265 等 GPL 元件） | https://ffmpeg.org 、 https://www.gyan.dev/ffmpeg/builds/ |
| 7-Zip（7z.exe、7z.dll） | 壓縮與解壓縮 | GNU LGPL＋BSD 3-clause；RAR 解壓縮受 unRAR 授權限制（不得用來重建 RAR 壓縮演算法） | https://www.7-zip.org |
| Pandoc 3.12.1 | 文件、EPUB 互轉 | GPLv2 或更新版本 | https://github.com/jgm/pandoc |
| LibreOffice 26.8（tools\libreoffice，已移除說明檔、多餘語言、圖庫、範本、Java 元件） | Office、ODF、舊版 doc/xls/ppt、轉 PDF | MPL 2.0（部分元件 LGPLv3／Apache-2.0，詳見 tools\libreoffice\LICENSE.html） | https://www.libreoffice.org/download/source-code/ |
| Calibre 9.16.0（tools\calibre，已移除開發者工具資源、多餘介面語言、AI 語音元件） | EPUB、MOBI、AZW3、PDF 電子書互轉 | GPLv3 | https://github.com/kovidgoyal/calibre 、 https://download.calibre-ebook.com/9.16.0/ |
| pywebview | 視窗介面（使用系統 Edge WebView2） | BSD 3-clause | https://github.com/r0x0r/pywebview |
| Pillow | 圖片 | MIT-CMU（HPND） | https://github.com/python-pillow/Pillow |
| rawpy（LibRaw） | 相機 RAW | MIT；LibRaw 為 LGPL 2.1／CDDL 1.0 | https://github.com/letmaik/rawpy |
| psd-tools | PSD 讀取 | MIT | https://github.com/psd-tools/psd-tools |
| resvg-py（resvg） | SVG 讀取 | MIT；resvg 為 Apache-2.0／MIT | https://github.com/baseplate-admin/resvg-py |
| pypdfium2（PDFium） | PDF 轉圖片、文字 | Apache-2.0／BSD 3-clause | https://github.com/pypdfium2-team/pypdfium2 |
| PDFium 的 C API（`_internal\pypdfium2_raw\pdfium.dll`，C++ 主程式以 LoadLibrary／GetProcAddress 動態載入） | C++ 主程式原生 PDF 渲染（PDF→每頁圖片） | BSD 3-clause（PDFium） | https://pdfium.googlesource.com/pdfium |
| pikepdf 10.17.0／qpdf 12.4.2（`_internal\qpdf30-*.dll`，C++ 主程式以 LoadLibrary／GetProcAddress 動態載入其 C API） | PDF 結構處理、C++ 主程式原生 PDF 重新壓縮（PDF→PDF） | MPL 2.0／Apache-2.0 | https://github.com/pikepdf/pikepdf 、 https://github.com/qpdf/qpdf |
| zlib 1.3.1（`_build\cpp\third_party\zlib`，隨 C++ 主程式編入，未修改原始碼） | 原生 PDF→PNG 的 deflate 壓縮 | zlib License（原文見 `_build\cpp\third_party\zlib\README.zlib`） | https://zlib.net |
| stb_image_write 1.16（`_build\cpp\third_party\stb`，隨 C++ 主程式編入，未修改原始碼） | 原生 PDF→PNG 的 PNG 容器與濾波器 | 公眾領域（MIT 雙軌授權） | https://github.com/nothings/stb |
| pypdf | PDF 合併 | BSD 3-clause | https://github.com/py-pdf/pypdf |
| trimesh | 3D 模型 | MIT | https://github.com/mikedh/trimesh |
| yt-dlp（tools\yt-dlp.exe） | 網路影片下載 | The Unlicense（公眾領域） | https://github.com/yt-dlp/yt-dlp |
| Deno（tools\deno.exe） | YouTube 網址解析 | MIT | https://github.com/denoland/deno |
| whisper.cpp 模型（ggml-base 內建於 tools\models；small／medium 第一次選用時才下載） | AI 語音辨識 | MIT（OpenAI Whisper 權重） | https://huggingface.co/ggerganov/whisper.cpp |
| Silero VAD（tools\models\ggml-silero-v5.1.2.bin） | 偵測語音段落 | MIT | https://github.com/snakers4/silero-vad |
| 思源黑體 Noto Sans TC（tools\fonts） | 浮水印、字幕（沒有微軟正黑體的電腦也能正常顯示中文） | SIL Open Font License 1.1（原文見 tools\fonts\OFL.txt） | https://github.com/notofonts/noto-cjk |
| Microsoft Visual C++ 執行庫（tools\libreoffice\program 內的 msvcp140*.dll、vcruntime140*.dll、concrt140.dll） | LibreOffice 執行所需，放在程式資料夾內，不需另外安裝 | Microsoft Visual Studio 可散布程式碼授權 | https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files |
| Microsoft Edge WebView2 安裝程式（tools\MicrosoftEdgeWebview2Setup.exe） | 只在缺少 WebView2 的舊版 Windows 10 上安裝視窗元件 | Microsoft 可散布元件 | https://developer.microsoft.com/microsoft-edge/webview2/ |
| OpenCC 詞庫（_internal\zhdict） | AI 字幕簡轉繁（台灣用語） | Apache-2.0（原文見 zhdict\OpenCC-LICENSE.txt） | https://github.com/BYVoid/OpenCC |
| Python 3.12 執行環境 | 程式執行 | PSF License | https://www.python.org |
| PyInstaller（僅開機程式） | 封裝 | GPLv2＋例外條款（允許封裝任意授權程式） | https://pyinstaller.org |
| Inno Setup 7（僅安裝程式） | 安裝與解除安裝 | Inno Setup License（允許散布） | https://jrsoftware.org/isinfo.php |

上表所有引擎皆內附且優先使用，不依賴電腦上已安裝的版本。

各元件的授權原文放在 `tools` 資料夾（FFmpeg-LICENSE.txt、7-Zip-License.txt、Pandoc-COPYRIGHT.txt、libreoffice\LICENSE.html、calibre\app\resources 內的授權檔），以及 `_internal` 中各 Python 套件的 `*.dist-info\LICENSE*`。
