# 四維八德 C++ 架構設計與遷移計畫

建立日期：2026-10-15。狀態：Phase 0 完成、Phase 1 第一刀完成並通過等價測試。

---

## 1. 為什麼不是「一次翻掉」

現在是 **C＋Python 混合**架構：

| 元件 | 語言 | 負責 |
|---|---|---|
| `四維八德.exe` | C（`_build/shell/main.c`、`api.c`、`engine.c`、`plat.c`、`json.c`） | Win32／WebView2 視窗、原生拖放、對話框、影音轉檔引擎、工作佇列 |
| `swbd-core.exe` | Python（PyInstaller，`_build/src/*.py` ＋ `_internal/` 155.7 MB） | 圖片、PDF、3D、工具箱（82 個表單）、AI、工作流程、下載、監看、磁碟／系統工具 |

前端與兩個後端之間是一條**行導向 JSON 協議**（`Q`／`R`／`S`／`A`／`E`），而 `api.c` 的
`api_request()` 已經是**方法級闸門**：

```c
if (!in(NATIVE, m)) { json_free(req); return 0; }   /* 0 = 這一條轉給 Python */
```

`in(NATIVE, m)` 是「C 自己回答」的方法清單，其餘全部轉給 Python。這代表**不需要旗艦日**
（no flag day）：任何一個方法都可以獨立搬到 C++，前端、協議、測試都不必改。
遷移的正確單位是**方法**，不是檔案、不是模組、更不是整個程式。

## 2. 目標架構

```
_build/cpp/                        ← 新的 C++ 核心（本文件的主角）
  CMakeLists.txt                   C++20／MSVC／CMake，與既有 build_shell.ps1 並存
  include/swbd/
    json.hpp                       RAII 包裝既有 jval，保證線路格式與 C 版位元組相同
    registry.hpp                   方法註冊表、Context、Handler、Register
    sys.hpp                        Windows 原語，語意對齊 Python 的 os／os.path／tempfile
    bridge.hpp                     C ABI：api.c 唯一需要認識的四個函式
  src/
    registry.cpp                   Context::tool、arg_string(s)、Registry
    sys.cpp                        abspath／realpath／normcase／stat／lstat／list_dir／temp_dir…
    bridge.cpp                     swbd_cpp_init／has／call／method_count／method_at
    modules/system_tools.cpp       ← Phase 1：cleanup_scan、cleanup_execute
  tests/
    probe_main.cpp                 探針（單一方法呼叫，人工檢查用）
    equivalence_main.cpp           同一行程內掃描→執行並輸出前後清單
    python_ref.py                  Python 參考實作（產生對照 JSON）
    equivalence.ps1                建 fixture、跑兩邊、逐欄比對
    equivalence.json               最近一次等價報告
```

分層原則：

1. **`sys` 是可測試的系統層，不是散落的 Win32 呼叫。** 每個函式的語意刻意對齊 Python 的
   `os`／`os.path`／`tempfile`（`abspath` 不解析連結、`realpath` 解析、`normcase` 轉小寫並把
   `/` 換成 `\`、`commonpath` 的包含判斷…），這樣「移植」才是**邏輯翻譯**而不是重新發明行為。
2. **`Registry` 是唯一的接手介面。** 一個方法名只能有一個擁有者（C 的 `NATIVE`、C++ 的註冊表、
   其餘 Python）。模組以靜態初始化自我註冊。
3. **協議不變。** C++ 回覆物件與 `core.py` 完全一致：`{"ok":true,"r":...}` 或
   `{"ok":false,"e":"..."}`；錯誤訊息沿用 Python 的字串（例如 `不支援的清理項目`）。
4. **第三方引擎不重寫。** FFmpeg／LibreOffice／Calibre／Ghostscript／Pandoc／MuPDF／qpdf／
   pdfium／whisper.cpp／llama.cpp 本來就是 C/C++，C++ 只是把它們的呼叫權從 Python 拿回來
   （省掉一層解譯器與 wrapper，不是省掉引擎）。

## 3. 已完成並驗證的部分

### Phase 0：骨架與縫

- CMake 專案可建置（Visual Studio 2026 Community ＋ CMake 4.4.3，`/MT` 靜態執行階段、
  `/utf-8 /W4 /permissive- /guard:cf /GS`，與現有 shell 相同不含可轉散發套件需求）。
- `shell/json.cpp`、`shell/plat.cpp` **原封不動**編成 `swbd_c` 靜態庫並被 C++ 連結使用
  （2026-10-15 這兩個檔已由 `.c` 改名為 `.cpp`，因此 `json.hpp` 不再包 `extern "C"`）。
- C ABI 縫已定：`swbd_cpp_init` / `swbd_cpp_has` / `swbd_cpp_call` / `swbd_cpp_free`
  （只有這四個；未連結 C++ 核心時 api.c 行為完全不變）。

### Phase 1：`system_tools` 的清理三方法

移植 `scan_cleanup`（併入 `cleanup_preview` 成為 `cleanup_scan`）與 `execute_cleanup`，
逐項對齊 Python：四個類別的掃描範圍、7 天／1 天門檻、10000 筆上限、
**首次插入順序＋最後一次值**的去重語意、`examples` 只取前 20 筆 basename、
token 為 32 位十六進位、600 秒到期、三種錯誤訊息、以及「路徑上每一層都不能是 reparse point」
的安全檢查。

**等價測試結果：PASS（0 項差異）**

```
preview  count=6 bytes=384
         app_temp 2/128、download_parts 1/64、logs 2/128、user_temp 1/64
         examples = old.bin, deep_old.bin, old_part.part, zdgc.log, zdgc.log.1, litter_old.tmp
execute  removed=6 skipped=0 bytes=384
before／after 逐項相同；junction（temp\zdgc_link）未被跟隨，連結目標 outside\keep.bin 倖存
```

重跑方式（`.ps1` **必須保持 UTF-8 BOM**，見第 6 節）：

```powershell
cmake -S E:\四維八德\_build\cpp -B E:\四維八德\_build\cpp\build -A x64
cmake --build E:\四維八德\_build\cpp\build --config Release
& E:\四維八德\_build\cpp\tests\equivalence.ps1        # PASS／FAIL，報告在 tests\equivalence.json
```

## 4. 早期整合步驟（歷史紀錄：第 2 批已完成）

> 這一節是當初的整合清單。**這些改動早已套用並驗證**（見第 10 節之後的成果紀錄），
> 保留在此只為了說明當初的順序與理由。原本「另一個工作階段正在改同一個檔案」的說法
> 已經不成立，特此更正。


**`_build/shell/api.cpp`**（約 10 行）：

```c
#include "swbd/bridge.hpp"                     /* 檔案開頭 */

/* api_request()：方法不屬於 NATIVE、也不屬於 C++ 核心時才轉給 Python */
if (!in(NATIVE, m) && !swbd_cpp_has(m)) { json_free(req); return 0; }

/* handle()：C++ 核心接手的方法在 C++ 這邊回答 */
static void answer_cpp(const jval *id, const char *method, const jval *args)
{
    char *reply = swbd_cpp_call(method, args);          /* {"ok":..,"r"|"e":..} */
    if (!reply) { reply = str_dup("{\"ok\":false,\"e\":\"C++ 核心沒有回應\"}"); }
    H.post_page(reply);                                  /* 取走所有權 */
}
```

**`_build/shell/main.cpp`**：啟動時（`api_init` 之後）呼叫一次
`swbd_cpp_init(base_dir, data_dir)`；若回傳 0 就照舊全部交給 Python（安全降級）。

**`_build/shell/build_shell.ps1`**：目前仍寫死

```
cl … /std:c11 main.c api.c engine.c plat.c json.c …
```

而 `_build/shell` 裡的檔案**已經被改名為 `.cpp`**（`git status` 顯示 9 個 rename 已暫存），
所以**現在的官方建置路徑已經壞了**：下一次跑 `build_shell.ps1` 會找不到 `main.c`。
必須改成 `.cpp`，並把 C++ 核心的原始檔加進同一行 `cl`（單一編譯命令下，靜態初始化不會被丟掉）、
把 `/std:c11` 換成 `/std:c++20`，並加上 `_build/cpp` 的 include 路徑。

## 5. 分期計畫

| 期 | 範圍 | 為什麼是這個順序 | 驗收 |
|---|---|---|---|
| ~~0~~ | ~~CMake 骨架、sys、registry、bridge~~ | 已完成 | 可建置、探針可用 |
| ~~1~~ | ~~`system_tools`：cleanup_scan／cleanup_execute~~ | 自成一體、無第三方引擎、安全邏輯值得用 C++ 重寫 | ✅ 等價測試 PASS |
| 1b | `system_tools`：`hardware_info`（`system_info`）＋硬體短測 | 需要 `platform_info`／`detect_hw`／worker 政策，屬協調層 | 同一顆 probe／equivalence 模式 |
| 2 | `zhconv.py` ＋ `zhdict`（1 MB 對照表） | 純資料轉換、無引擎；可直接讀 OpenCC 表，省掉 Python 端資料 | 轉換結果逐字元比對 |
| 3 | `disk_tools.py`、`file_actions.py` | 檔案系統操作，`sys` 層已具備 | 邊界案例（連結、權限、長路徑） |
| 4 | `capture.py`（螢幕錄影、yt-dlp／deno 驅動） | 程序驅動正是 `plat` 的強項 | 與 Python 相同輸出檔 |
| 5 | `workflows.py`、`validation.py`、`selftest.py` | 協調層，需先有工作佇列 | 既有 374 項測試 |
| 6 | `tools.py`（99 KB、82 個表單）分群搬 | 最大塊；PDF 群直接綁 MuPDF／qpdf／pdfium 的 C API，可去掉 pypdf／pikepdf／pypdfium2 三層 | 每個表單逐一等價 |
| 7 | `engine.py`（69 KB）與既有 `engine.c` 合併 | 影音／Office 引擎的協調層 | C／Python 雙跑比對 |
| 8 | `app.py`、`core.py` | 最後才動 API 表面 | 關掉 Python：`_internal` 155.7 MB 與 PyInstaller 退場 |

**每一期的驗收都必須是「與 Python 逐欄等價」**，不是「看起來會動」。
`test_equivalence.py` 已有的方法論（解碼後的畫格、算繪後的 PDF、文件文字、壓縮檔內容）
就是這個標準。

## 6. 已踩過的坑（會再犯，請記住）

1. **靜態註冊會被連結器丟掉。** 模組靠靜態初始化註冊，若編成**靜態程式庫**且沒有任何符號被引用，
   整個 `.obj` 會被丟棄 → 註冊表是空的、方法「沒有人接手」。已改用 CMake **OBJECT 程式庫**。
   若日後改回靜態庫，必須用 `/WHOLEARCHIVE` 或顯式 anchor 符號。
2. **`main(char**)` 拿到的是 ANSI（本機 CP950）位元組，不是 UTF-8。**
   專案路徑含「四維八德」，用 `main` ＋ UTF-8 假設會把路徑弄爛（甚至崩潰 `0xC0000409`）。
   兩個測試執行檔都已改用 **`wmain`**。
3. **PowerShell 5.1 以 ANSI 讀取沒有 BOM 的 `.ps1`**，中文會被吃掉並造成語法錯誤。
   `equivalence.ps1` 必須存成 **UTF-8 with BOM**。
4. **PS 5.1 會把原生程式的 stderr 當成終止錯誤**（`$ErrorActionPreference='Stop'`）。
   測試執行檔不要往 stderr 寫偵錯訊息。
5. **命令列上的 JSON 引號會被 CRT 吃掉**（`[["app_temp"]]` → `[[app_temp]]`）。
   探針因此提供 `--args <file>`。
6. **非 ASCII 路徑是這個專案的反覆病灶**：whisper.cpp 因為窄字元開檔，在 `E:\四維八德`
   之下 AI 語音會失敗（掛到 ASCII 路徑即 81/81 通過）。C++ 這一側請一律用 `w` 系列 API。

## 7. 對體積的誠實說明

C++ 化**不是**縮小安裝包的手段。實測（LZMA2、64 MB 字典，與安裝包同等設定）：
整個 Python 層（`_internal` ＋ `swbd-core.exe`，169 MiB）壓縮後是 **53.4 MB**，
佔 1,469,948,812 bytes 安裝包的 **3.6%**；而 `_internal` 的 155.7 MB 裡有 132.6 MB
是 MuPDF／OpenBLAS／qpdf／pdfium／libcrypto 這類**第三方原生程式庫**，改寫 Python 動不了它們。
真正的體積在 `tools/`（2.8 GB，壓縮後約 1.36 GB）。

C++ 化的正當理由：**啟動時間**（少一次解譯器與 import）、**記憶體**、
**去除重複的 PDF 堆疊**（pypdf＋PyMuPDF＋pikepdf＋pypdfium2 四層收斂為一至兩層）、
以及**單一語言的可除錯性**。若要縮安裝包，該做的是元件分拆與按需下載（WebView2 204 MB、
deno 93 MB、calibre 573 MB、LibreOffice 520 MB、模型 752 MB）。

## 8. 與平行工作階段的關係（2026-10-15 01:37 更新）

同一個 repo 有另一個工作階段**同時**在做 C++ 化，而且做得完整、品質高。兩邊的現況：

| | 平行工作階段（`_build/shell/`） | 本文件的成果（`_build/cpp/`） |
|---|---|---|
| 範圍 | 原生 shell：`swbd_core`（engine／api／plat／json）＋ `swbd-shell`（Win32／WebView2）＋ POSIX 測試驅動 | 方法級接手層：`sys`／`registry`／`bridge`／`modules`／等價測試 |
| 建置 | `shell/CMakeLists.txt`（C++20、`/MT`、`/guard:cf`、Windows 與 POSIX 皆可）；`build_shell.ps1` 已於 01:32 改為驅動 CMake | `cpp/CMakeLists.txt`（C++20、同旗標）＋ OBJECT 程式庫 |
| 狀態 | `.c`→`.cpp` 改名已暫存；`api.h`／`engine.h`／`plat.h` 註解改為 C++ 用語；正在編輯中 | 已建置、已通過等價測試 |

**這兩者不是競爭，而是上下兩層。** 平行工作階段解決的是「原生層用 C++ 編譯與建置」，
本文件的成果解決的是「**Python 的方法如何一個一個被 C++ 接手**」——後者才是把
`swbd-core.exe` 送走的機制。建議的合併方式（三件小事，但都不要在對方還在編輯時做）：

1. **合併成一個 CMake 專案。** 讓 `_build/cpp` 被 `shell/CMakeLists.txt` 以
   `add_subdirectory` 納入，或把 `shell/CMakeLists.txt` 當上層；**不要並存兩個 CMake 專案**。
2. **不要重複編譯 `json.cpp`／`plat.cpp`。** 本文件的 `cpp/CMakeLists.txt` 目前自己建
   `swbd_c`（json＋plat）；合併後要改成直接連結對方的 `swbd_core`，否則同一個 exe 會出現
   重複符號。
3. **模組程式庫必須是 OBJECT（或 `/WHOLEARCHIVE`）。** 對方的 `swbd_core` 是 STATIC；
   本文件的 `modules/*.cpp` 靠靜態初始化自我註冊，若編成 STATIC 且無人引用，連結器會把整個
   `.obj` 丟掉，方法就「沒有人接手」。這是第 6 節第 1 點，合併時最容易踩到。

早期的整合步驟（第 4 節，已完成）當初也建議由**單一工作階段**一次做完，避免兩個工作階段同時寫
`api.cpp`／`main.cpp` 互相覆蓋。

## 9. 其他待決事項

1. **`.gitignore` 是白名單制**，`_build/cpp/` 與 `_build/docs/` 目前都不會被納入版本控管。
   建議加入 `!/_build/cpp/`（並排除 `/build/`、`/out/`）與 `!/_build/docs/`——尚未代為修改，
   避免與平行工作階段衝突。
2. **介面重複**：`sys.hpp` 與 `plat.h` 有部分重疊（路徑、檔案狀態、時間）。
   合併方向應是讓其中一套逐步吸收另一套（建議保留 `plat` 的跨平臺版本，
   `swbd::sys` 改為薄層或直接併入），不要長期並存兩套。
3. **`_build/shell/cpp-probe*`、`out/`、`sdk/`** 是建置產物，`shell/CMakeLists.txt` 已把
   `out\cmake` 當輸出目錄；這些應列入 `.gitignore`。

---

## 10. 第二批成果（2026-10-15 上午）：PDF 原生層與第一次真正的功能接手

### 10.1 原生 PDF 層（`_build/cpp/src/pdf/`）

- `pdfium_api.cpp`：以 `LoadLibraryW` 動態載入 `pdfium.dll`（`_internal\pypdfium2_raw\`），
  手寫最小 C API 宣告。**為什麼不是 MuPDF**：MuPDF 的 C API 用 `setjmp/longjmp`（`fz_try`）
  傳遞錯誤，而 `fz_try` 需要 `fz_context` 的內部佈局，PyMuPDF 又只隨附 DLL、沒有標頭；
  實測 `mupdfcpp64.dll` 確實匯出 26/30 個 C 符號（版本字串 `1.28.2` 也能建 context），
  但缺標頭就無法安全使用。PDFium 與 qpdf 是回傳碼制、握把是 opaque 指標，
  手寫宣告即可安全使用；qpdf 的 C API 也已在 `qpdf30-*.dll` 上實測可用（後續加密／線性化用）。
- `png_writer.cpp`：`stb_image_write v1.16`（public domain，`third_party/stb/`）
  ＋ `STBI_WRITE_NO_STDIO` ＋ `CreateFileW` 回呼寫入。**stb 內建輸出用窄字元 `fopen`，
  遇到 `E:\四維八德` 這種非 ASCII 路徑會直接失敗**（與 whisper 同一個病灶）。
- 兩個入口：`describe_document()`（頁數／頁面尺寸／中繼資料）與
  `render_all_pages()`（整份文件 → `001.png`、`002.png`…，可回報進度與取消）。
- 渲染參數逐項對齊 `engine.py` 的 `pypdfium2 page.render(scale=dpi/72)`：
  `FPDFBitmap_BGR`（alpha=0）、白底、`FPDF_ANNOT`，以及**像素尺寸用 `ceil`**
  （實測 842 pt @150 dpi = 1754.17 → **1755**；用 `round` 會差 1 像素，閘門第一次執行就抓到）。

### 10.2 第一次真正的功能接手：PDF → 每頁 PNG（已上線，且比 Python 快）

`engine.cpp` 新增 `conv_pdf_pages()`，`eng_handles()` 讓 `cat == "pdf" && target == "png"` 走 C 引擎。
**不需要改 `api.cpp`**：`eng_handles` 就是唯一的分派點。輸出規則與 Python 版完全相同
（資料夾＝`out_dir\檔名`、`001.png`…、`encoder` 標示 PDFium、RGB PNG），`validate()` 既有的
資料夾逐檔驗證直接適用；PDFium 不是執行緒安全的，因此整份文件渲染期間持有 `e->pdf_lock`，
而 PNG 編碼（純 CPU）交給最多 4 個執行緒與下一頁的渲染重疊 —— 與 `engine.py` 的做法一致。

**這條路是量出來的，不是猜的。** 24 頁 A4 @150 dpi 的實測（`bench_pdf_render.py`）：

| 階段 | 每頁 | 說明 |
|---|---|---|
| 起點：stb 內建 deflate ＋ 逐像素重排 ＋ 逐列試 5 種濾波器 | 94 ms | 比 Python 慢 6 倍，**當時刻意不接上線** |
| 改 zlib（`STBIW_ZLIB_COMPRESS`）＋ `FPDF_REVERSE_BYTE_ORDER` 去掉重排 | 82 ms | 只進步 13% → 證明瓶頸不在壓縮器 |
| 固定 PNG 濾波器（`stbi_write_force_png_filter = 1`） | 46 ms | **真正的元凶**：stb 預設每列試完 5 種濾波器 |
| 編碼平行化（4 執行緒）＋ 輸出改回 RGB | **10.4 ms** | 比 Python 引擎工作（14.6 ms）快 1.4 倍 |
| （對照）純 PDFium 渲染 | 3.9 ms | 渲染本來就快，問題一直在編碼 |
| （對照）Python 引擎工作（pypdfium2 + Pillow） | 14.6 ms | |
| （對照）Python 存 PNG | 24.0 ms | |

輸出檔案 6.60 MB vs Python 的 7.62 MB（小 13%），而且第 1、5、24 頁**逐像素相同、同為 RGB**。

**PDF → JPG 仍留在 Python**：JPEG 編碼器不同（Pillow 的 libjpeg-turbo vs stb），
接手會讓輸出不再是位元等價。

**新的執行期相依**：C 引擎現在需要 `_internal\pypdfium2_raw\pdfium.dll`（路徑找不到時會以
「找不到原生 PDF 引擎」失敗，不會自動退回 Python）。這個 DLL 本來就在 payload 裡，
但**未來若要精簡 `_internal`，不能把 `pypdfium2_raw` 拿掉**。

### 10.3 等價閘門（都在 `_build/tests/release-tests/`）

| 閘門 | 證明 |
|---|---|
| `gate_pdf.ps1` | 原生層的頁數／頁面尺寸／中繼資料與 pymupdf 逐欄相同（含中文檔名與中文中繼資料） |
| `gate_pdf_render.ps1` | 單頁渲染與 pypdfium2 **逐像素相同**（150／200 dpi 兩案例） |
| `gate_pdf_native.ps1` | C 引擎的 PDF→PNG **工作**：`encoder=PDFium`、資料夾與檔名規則、逐頁逐像素相同 |
| `bench_pdf_render.py` | PDF→PNG 效能基準（Python 純渲染／多執行緒／引擎工作 vs C++ 引擎工作） |
| `check_whisper_unicode.py` | whisper 非 ASCII 路徑缺陷重現 ＋ 修法有效 |
| `test_cpp_migration.ps1` | C 基準線（git HEAD）vs C++ 現況：引擎 JSON、外殼煙霧、整合閘門、cleanup 等價 |

探針 `swbd-cpp-pdf-render` 另外提供兩個量測模式：`--bench`（渲染＋編碼全部頁面）
與 `--bench-render`（只渲染），用來把渲染成本與編碼成本分開。

### 10.4 非 ASCII 路徑缺陷（已修並實證）

`tools.py` 新增 `ascii_model_path()`：模型目錄若在非 ASCII 路徑，於
`%LOCALAPPDATA%\SiWeiBaDe\models-link` 建立 ASCII 目錄連結指向 `tools\models`（零複製），
把連結路徑交給 ffmpeg 的 whisper 濾鏡。**8.3 短路徑在本機不可用**
（`GetShortPathNameW` 對 `E:\四維八德\tools\models\ggml-base.bin` 回傳原長路徑）。
移除連結只能用 `os.rmdir`；`shutil.rmtree` 會遞迴進連結目標，把 147 MB 模型真的刪掉。

### 10.5 發布與安裝驗證（2026-10-15）

- `_build/build.ps1` 補 UTF-8 BOM，並以 `Invoke-Native` 包裝 8 個原生呼叫點：
  PowerShell 5.1 在 `$ErrorActionPreference='Stop'` 下會把原生 stderr 變成終止錯誤
  （`2>&1`、`2>$null`、`cmd /c` 包裝實測皆無效，只有暫時切 `Continue` 有效）。
- 完整發布建置（含 Inno Setup）成功：安裝程式 1,469,756,466 bytes，
  SHA-256 `7EEA3E1284045DBEFEF532757F67B2A9523A819954B5BAD9027697D54905E236`；
  候選版自我測試 81/81、PDF 12/12；候選版 `四維八德.exe` 雜湊與 `_build/shell/out/swbd-shell.exe` 一致。
- **必須從 ASCII 路徑建置**：這是在 whisper 修法之前的事實。修法之後（見 §10.4 與 §11.4），
  已能直接從 `E:\四維八德` 這個非 ASCII 路徑完成整個建置，AI 自測在非 ASCII 的候選目錄下通過。
- 安裝後驗證（實際安裝 2.3.2 後）：自我測試 80/80（1 項 SKIP＝安裝檔不含 `i.heic` 範例）、
  PDF 12/12、原生視窗煙霧 `ok=True`。
- **完整安裝驗證（`test_installer.ps1` 從頭到尾）**：2026-10-15 中午通過 ——
  靜默安裝到含中文與空白的測試路徑、逐檔雜湊比對、登錄記錄與捷徑、內嵌圖示、
  安裝後原生視窗煙霧、安裝後 12 項 PDF、解除安裝後檔案／記錄／捷徑清理全部通過。
  在此之前這項驗證一定會在 `test_logo_resources.py` 崩潰（見 §11.4）。

### 10.6 尚未完成

1. `test_installer.ps1` 會在 `test_logo_resources.py` 崩潰（PS 5.1 把它的 stderr 當終止錯誤），
   導致安裝驗證中斷——這是專案測試腳本的既有缺陷。
2. PDF→JPG 的接手（需相容的 JPEG 編碼器）。
3. PDF 結構操作（合併／拆分／移除頁／加密／線性化）——qpdf 的 C API 已確認可連結。
4. 低風險 Python 模組遷移（`validation`／`disk_tools`／`file_actions`／`zhconv`／`workflows`）。
5. 效能基準（冷啟動、記憶體、每頁渲染吞吐），作為後續是否繼續原生化的依據。

---

## 11. 第三批成果（2026-10-15 中午）：UI 動作接手與既有缺陷修復

### 11.1 新接手的三個頁面方法（`_build/cpp/src/modules/shell_actions.cpp`）

| 方法 | 來源 | 內容 |
|---|---|---|
| `drives` | `tools.list_drives()` | 只列光碟機（`DRIVE_CDROM`），label 的三段邏輯照抄 |
| `open_file` | `file_actions.open_file()` | `os.startfile` → `ShellExecuteW` 的 `open`；失敗時先 reveal 再擲出相同訊息 |
| `reveal` | `file_actions.reveal()` | 目錄開資料夾；檔案用 `explorer /select,"路徑"` |

`normalized()`／`existing()` 的驗證與錯誤字串刻意與 `file_actions.py` 一字不差
（橋接層把例外轉成 `{"ok":false,"e":...}`，字串不同就不算等價）。註冊表因此由 2 個方法增為 5 個。

### 11.2 `cpp_or_core`：接手範圍擴大到「C 自己發起」的呼叫

`api.cpp` 新增 `cpp_or_core()`：monitor 要顯示成品時（`reveal`）先問 C++ 核心，沒有接手才轉 Python。
在此之前註冊表只能接手**頁面送進來**的方法；有了這一層，任何經過 `core_call` 的方法都能逐步搬過來
（`monitor_state`／`job_states`／`save_settings` 等），這是後續要動每秒熱路徑的前提。

### 11.3 閘門

| 閘門 | 證明 |
|---|---|
| `gate_shell_actions.ps1` ＋ `check_shell_actions.py` | `drives` 與 Python 逐欄相同，並以 **WMI `Win32_LogicalDisk`（DriveType=5）** 獨立交叉驗證；`open_file`／`reveal` 的錯誤字串（含正規化後的絕對路徑）與 Python 一字不差；非字串參數以相同訊息拒絕 |

### 11.4 修好的既有缺陷

1. **`test_logo_resources.py` 讀錯路徑**：它讀 `release-tests\logo.ico`，但發行用的 ICO 在
   `_build\logo.ico`，所以 `test_installer.ps1` 一定在這一行崩潰（第一次安裝驗證就是這樣中斷的）。
   已改成兩處都找；實測主程式與外殼都通過（7 個 ICO 項目、payload 雜湊相符）。
2. **發布建置可直接從真實路徑執行**：`build.ps1` 補了 BOM 與 `Invoke-Native` 之後，
   本輪直接從 `E:\四維八德`（非 ASCII）跑完整建置成功（Inno 壓縮 598 秒），
   而且**候選版本的 AI 自測全部通過**：
   `AI 自動字幕 4.90s OK`、`音檔轉文字 4.22s OK`、`會議總結（快速摘錄）4.21s OK`、
   `會議總結（離線 AI）12.39s OK` —— 這在 whisper 修法之前是不可能的（會出現
   `failed to open 'E:/四維八德/tools/models/ggml-base.bin'`）。
3. **完整安裝驗證跑完**（見 §10.5）：安裝、中文含空白路徑、C 視窗、12 項 PDF、雜湊、
   圖示與解除安裝全部通過。

### 11.5 目前的接手狀態

| 來源 | 已由 C++ 接手 |
|---|---|
| `system_tools.py` | `cleanup_scan`、`cleanup_execute`、`system_info` |
| `disk_tools.py` | `disk_info`、`disk_preview`、`disk_launch`（`disk_help` 留在 Python：只是開說明網址） |
| `tools.py` | `drives` |
| `file_actions.py` | `open_file`、`reveal`（monitor 經 `cpp_or_core` 也會走這裡） |
| `engine.py` 的 PDF 工作 | PDF→PNG（PDFium）、PDF→PDF 含合併（PDFium 組頁＋qpdf），由 `eng_handles` 分派 |

註冊表（`swbd_cpp_method_count()`）目前是 **9 個方法**。另外兩個注入點讓 C++ 看得到引擎狀態：
`swbd_cpp_set_busy_probe`（Python 引擎忙碌中）與 `swbd_cpp_set_system_facts`
（記憶體、核心數、工作者政策、硬體編碼器）。

---

## 12. 第四批成果（2026-10-15 下午）：PDF → PDF 由 qpdf 接手

### 12.1 為什麼不是用 PDFium

PDFium 有 `FPDF_ImportPages`／`FPDF_SaveAsCopy`，合併組頁沒問題，但它**不會重新壓縮內容串流**。
現行 Python 路徑（`engine.py` 的 pypdf 分支：`compress_content_streams(level=9)` ＋
`compress_identical_objects`）正是靠重壓縮把檔案變小，交給 PDFium 會讓「PDF 壓縮」的成品變大
——那不算等價。所以改成：**組頁用 PDFium（尚未做）、重寫用 qpdf**。

### 12.2 qpdf 層（`_build/cpp/src/pdf/qpdf_api.cpp`）

- 只用 C API 子集，以 `LoadLibraryExW(..., LOAD_WITH_ALTERED_SEARCH_PATH)` 動態解析
  （`qpdf30-<hash>.dll` 相依的 MSVC 執行檔也在 `_internal`，預設搜尋路徑找不到）。
- **全程走記憶體**：輸入由我們用 `CreateFileW` 讀進來交給 `qpdf_read_memory`，輸出用
  `qpdf_init_write_memory` ＋ `qpdf_get_buffer` 取回再自己寫出。qpdf 永遠看不到路徑，
  所以非 ASCII 路徑（`E:\四維八德`）不會重演 stb／whisper 那類窄字元開檔的毛病。
- 設定對齊 pypdf 的意圖：`compress_streams` ＋ `object_streams=generate` ＋
  `decode_level=generalized` ＋ 丟棄未引用物件。
- **踩到的坑**：qpdf 的 setter 會寫入 writer，而 writer 由 `qpdf_init_write_*` 建立；
  先呼叫 setter 會解引用空的 writer → **存取違規 0xC0000005**（用 `SWBD_QPDF_TRACE=1` 逐步
  定位，最後以 ctypes 逐一呼叫確認正確順序）。

### 12.3 分派政策（`eng_handles(cat, target, merge, opt)`）

簽章增加了 `merge` 與 `opt`：同一個 `(cat,target)` 在不同預設下可能需要不同引擎。

| 情況 | 引擎 | 理由 |
|---|---|---|
| `pdf → png` | C（PDFium） | 逐像素等價且更快（§10.2） |
| `pdf → pdf`（單檔、high／balanced） | C（qpdf） | 內容等價、檔案大幅變小（見下） |
| `pdf → pdf`（`preset=small`） | Python | small 會先降採樣過大的圖片（`_shrink_pdf_images`），qpdf 不做 |
| `pdf → pdf`（merge） | Python | 合併需要組頁；qpdf 沒有組頁 API，要用 PDFium 匯入頁面（待做） |
| `pdf → jpg` | Python | JPEG 編碼器不同，接手就不是位元等價 |

### 12.4 實測（`gate_pdf_rewrite.ps1`／`gate_pdf_rewrite_job.ps1`）

素材：8 頁、每頁一段文字 ＋ 一張 900×700 內嵌圖，共 1,934,374 bytes。

| 引擎 | 大小 | 比例 | 頁數 | 逐頁文字 | 逐頁圖片像素 |
|---|---|---|---|---|---|
| pypdf（現行） | 1,901,605 | 98% | 8 | ✓ | ✓ |
| **qpdf（C++）** | **68,450** | **4%** | 8 | ✓ | ✓ |

原因是素材的圖片是**未壓縮的 Flate 串流**：qpdf 連圖片一起重壓，pypdf 只壓內容串流。
換句話說，這一項不只是等價，而是**大幅改善**。

工作層級另外驗證了兩件事：`encoder=qpdf`、輸出檔名與位置符合 Python 的 `out_path` 規則；
以及**原檔已經最小時走 Python 的退路**——encoder 標示「qpdf（原檔已是最小，直接複製）」，
輸出與來源**位元相同**。

### 12.5 閘門設計上的教訓

第一次跑 `gate_pdf_rewrite.ps1` 時 C++ 的輸出只有原檔的 4%，看起來「太好了」。因為那個閘門
當時只比對**文字**，我在結果頁數與文字都相同的情況下仍然懷疑圖片被丟掉，於是補上
「逐頁圖片的尺寸、通道、像素雜湊」比對才確認是真的——**等價閘門的觀察面不足時，寧可先懷疑
再補齊**。

---

## 13. 第五批成果：PDF 合併（PDFium 組頁 ＋ qpdf 重寫）

### 13.1 作法

`pdfium_api.cpp` 新增 `merge_documents()`：`FPDF_CreateNewDocument()` 開新文件，逐檔
`FPDF_ImportPages(dest, src, NULL, 已累積頁數)` 依序附加，再用 `FPDF_SaveAsCopy` 寫進
**記憶體**（自訂 `FPDF_FILEWRITE` 回呼，`version = 1`）。結果位元組接著交給
`qpdf.rewrite_memory()` 重新壓縮，最後由引擎用 `write_file()` 落地。

組頁用的三個符號（`CreateNewDocument`／`ImportPages`／`SaveAsCopy`）刻意是**選用**的：
萬一未來的 PDFium 少了它們，渲染照舊可用，只有合併會以「這一版 PDFium 沒有組頁 API」降級。
PDFium 不是執行緒安全的，所以組頁整段仍在 `pdf_lock` 之內。

### 13.2 實測（`gate_pdf_rewrite_job.ps1` 第 5 段）

三份素材（A 2 頁、B 3 頁、C 4 頁，每頁都有可辨識的文字與一張 900×700 內嵌圖）：

| | 頁數 | 逐頁文字 | 逐頁圖片像素 | 大小 |
|---|---|---|---|---|
| pypdf（現行） | 9 | ✓ | ✓ | 5,683,357（來源合計的 99%） |
| **PDFium+qpdf（C++）** | 9 | 與 pypdf 相同 | 與 pypdf 相同 | **136,272（來源合計的 2%）** |

輸出檔名沿用 `out_path` 的規則（`<第一個來源的檔名>_合併.pdf`），與 Python 完全一致
（`_合併` 後綴本來就是 Python `out_path` 在 merge 時加的，C 引擎早就照抄）。

### 13.3 分派政策（更新）

| 情況 | 引擎 |
|---|---|
| `pdf → png` | C（PDFium 渲染） |
| `pdf → pdf`（單檔或合併、high／balanced） | C（qpdf；合併時 PDFium 先組頁） |
| `pdf → pdf`（`preset=small`，含合併） | Python（需要 `_shrink_pdf_images` 降採樣） |
| `pdf → jpg` | Python（JPEG 編碼器不同） |

政策矩陣 7 項全部由 `check_pdf_rewrite_job.py` 斷言。

### 13.4 出貨版本也要驗證：把 PDF→PDF 加進外殼煙霧測試

`main.cpp` 的 `SMOKE_JS` 是在 WebView 頁面裡執行的**真正的 UI 路徑**（呼叫 `pywebview.api` 的
`start`／`status`），所以在這裡加一個 PDF→PDF 工作就等於驗證了**出貨版本的分派**。新增的檢查：

- 工作 id 必須是 `x` 開頭（＝由 C 引擎接手，不是 Python 的 job id）；
- 狀態必須是 `done`；
- `encoder` 必須以 `qpdf` 開頭。

任何一項不符就讓整個煙霧測試失敗（`ok=false`）。**刻意不新增報告欄位**：`gate_compare.py` 是
全結構比對，而 C 版基準線（git HEAD 的 `main.c`）用的是舊的 `SMOKE_JS`，多一個欄位就會被判成
「只有 C++ 版有」而失敗。用既有的 `ok` 欄位承載這個斷言，C 版與 C++ 版的報告就仍然逐欄相同。

素材是固定的 `_build\samples\smoke.pdf`（3 頁文字＋一張內嵌圖，1,445,569 bytes），
`build.ps1` 與 `gate_shell.ps1` 都只複製它，不依賴建置機的額外套件。

順帶修掉一個會擋住發布建置的問題：**`.ps1` 少了 UTF-8 BOM**。PowerShell 5.1 會把中文當成
目前 ANSI 代碼頁而解析失敗（錯誤訊息本身也變亂碼）。本輪掃描所有含非 ASCII 位元組的 `.ps1`
並補上 BOM（`build.ps1`、`gate_shell.ps1`、`test_installer.ps1` 等 7 個）。C++ 原始檔不需要 BOM，
因為兩個 CMake 專案都已經指定 `/utf-8`。

### 13.5 出貨驗證結果（2026-10-15 下午）
| 項目 | 結果 |
|---|---|
| 完整發布建置（自 `E:\四維八德` 這個非 ASCII 路徑） | 成功，Inno 壓縮 587 秒 |
| 候選版本外殼煙霧（含新的 PDF→PDF 斷言） | `ok=true`、`completion_notifications=2` |
| 候選版本實際產出 | `smoke-output\smoke.pdf` = **13,273 bytes**（素材 1,445,569，0.9%） |
| 自我測試（含 AI，在非 ASCII 候選目錄下） | **81 / 81** |
| PDF 打包測試 | 12 / 12 |
| 安裝程式 | 1,469,796,723 bytes，SHA-256 `D75EEA0AB4BEF81FC88FE3C8DE196B164AC954664DEDA991ED6430807B923B98` |
| 完整安裝驗證（靜默安裝／中文含空白路徑／C 視窗／12 項 PDF／雜湊／解除安裝） | 通過 |
| 已安裝副本再驗一次原生 PDF | `smoke-output\smoke.pdf` = 13,273 bytes，`ok=true` |
| 已安裝副本的接手數 | `logs\shell.log`：`C++ core ready: 5 method(s) taken over` |

安裝驗證過程中發現一個**測試腳本**的缺口：`test_installer.ps1` 只用目錄複製把
`release\smoke-fixtures` 帶進安裝目錄，實測那次漏掉了 `smoke.pdf`，於是安裝後的煙霧測試
沒有真的跑到 PDF 工作。已改成明確複製該檔並立刻驗證（找不到就讓驗證失敗），
以免「看起來通過、其實沒測到」。

---

## 14. 第六批成果：磁碟工具模組（`disk_tools.py`）

### 14.1 接了哪些、為什麼留一個

| 方法 | 接手 | 說明 |
|---|---|---|
| `disk_info` | ✓ | 磁碟清單：磁碟編號走 PowerShell `Get-Partition`（Win32 沒有等價的公開 API），其餘用 `GetDriveTypeW`／`GetVolumeInformationW`／`GetDiskFreeSpaceExW`。`free` 對應 `shutil.disk_usage().free`＝「可用給呼叫者的位元組」。 |
| `disk_preview` | ✓ | `disk_tools.plan()` 的等價實作：模式／磁碟機代號驗證、`chkdsk` 指令、兩種警告文字、`description`。預覽結果與 Python 一樣**不含 `command`**。 |
| `disk_launch` | ✓ | token／確認／10 分鐘時限的驗證，重新組指令、參數字元檢查、`ShellExecuteW("runas")` 啟動。 |
| `disk_help` | ✗（留 Python） | 只是開啟一個說明網址，沒有可驗證的輸出面；硬搬過來只增加表面積。 |

### 14.2 補上的架構缺口：`Context::busy()`

`disk_preview`／`disk_launch` 在 Python 版會先問 `self._eng.busy()`。這個「忙碌」的定義住在
Python 那一側，C++ 不該自己猜，所以新增了注入點：

```c
void swbd_cpp_set_busy_probe(int (*probe)(void));   /* bridge.hpp；main.cpp 在初始化後注入 */
```

`api.cpp` 注入的實作只問 Python 的 `status.busy`。C 引擎自己的忙碌則由 `api_request` 既有的
**IDLE_ONLY** 守門負責（`disk_preview`／`disk_launch` 本來就在那份清單裡），兩者合起來與原行為
完全相同——包含兩種不同的拒絕訊息。沒有注入時 `busy()` 一律回 false，行為與沒有這個機制時相同。

### 14.3 閘門（`gate_disk_tools.ps1` ＋ `check_disk_tools.py`）

| 段落 | 證明 |
|---|---|
| `disk_info` | 逐欄與 `disk_tools.inventory()` 相同（`free` 是會變動的值，允許 256 MB 誤差並印出實際差異），另以 **WMI `Win32_LogicalDisk`** 獨立交叉驗證 |
| `disk_preview` | 成功案例逐欄相同（含 `warnings`／`description`）、`token` 是 32 個十六進位字元；三個錯誤案例的訊息一字不差（不支援的操作／磁碟代號格式／不存在的磁碟） |
| `disk_launch` | 三條**拒絕**路徑的訊息一字不差（沒有預覽／token 不對／未確認）。成功的啟動會跳 UAC 並開 chkdsk 視窗，自動測試刻意不執行 |

為了測有狀態的方法，探針多了 `--calls <file>`：在同一個行程內連續呼叫
（`disk_preview` → `disk_launch`），參數寫 `"@token"` 會代換成前一次回覆的 token。
沒有這個，token 檢查根本測不到。

### 14.4 閘門抓到的錯（在測試腳本裡，不在實作裡）

「尚未預覽就啟動」那一項，我原本拿 `disk_tools.launch(None, …)` 當參考，結果得到
`AttributeError`——因為那道檢查其實住在 **app.py 的 `disk_launch`**，不在 `disk_tools.launch`。
C++ 的實作（`請先預覽磁碟操作`）才是對的，修的是閘門的預期來源。

---

## 15. 第七批成果：把既有回歸套件（374 項）跑起來

目標要求「每階段都以既有自我測試與 374 項回歸案例驗證」。前六輪用的都是**新增的閘門**，
這一輪把專案原本那套（`TEST_RESULTS.md` 列的 374 項）實際重跑一次。

### 15.1 結果（全部在 2026-10-15 下午重跑）

| 套件 | 案例 | 結果 |
|---|---:|---|
| `test_engine_windows.py`（C 轉檔與工作控制，C 引擎 vs Python 引擎逐位元組比對） | 30 | **30 / 30** |
| `test_equivalence.py`（C／Python 內容比對：解碼媒體、渲染 PDF、文件文字、壓縮內容） | 28 | **28 / 28** |
| `test_native_options.py`（C 編碼與加速選項：NVENC、無損封裝、完整解碼驗證） | 6 | **6 / 6** |
| `test_ui.cjs`（介面與表單，82 個工具／446 種表單狀態） | 96 | **96 / 96** |
| `test_uri_paths.ps1`（Unicode 與來源網址限制） | 8 | **8 / 8** |
| `test_logo_resources.py`（新版圖示資源） | 2 | **2 / 2** |
| `test_pdf_suite.py`（PDF 功能與內容） | 46 | **46 / 46** |
| `test_additional.py`（工作流程與電腦工具） | 5 | **5 / 5** |
| `test_feature_edges.py`（特殊格式與設備邊界） | 14 | **14 / 14** |
| `test_protocol.py`（視窗管線與對話框） | 6 | **6 / 6** |
| 既有套件小計 | **241** | **241 / 241** |
| 發布建置：完整離線自我測試（含 AI，非 ASCII 候選目錄） | 81 | **81 / 81** |
| 發布建置：PDF 打包元件 | 12 | **12 / 12** |
| **合計** | **334** | **334 / 334** |

其餘列在報告裡的項目是**同一批功能在不同層的重複計數**（報告自己註明「相同功能在不同層的檢查
分別計數」），或是需要外部資源的檢查（模型內容、下載站台）。這一輪重跑的是**腳本本身**，
所以以腳本的結果為準。

### 15.2 讓套件能重跑的兩個環境條件（不是產品問題）

1. **測試工作區必須在 ASCII 路徑**。`test_pdf_suite.py` 把 `tempfile.tempdir` 設在
   `ROOT/scratch`；`pdf_tools._tessdata()` 只有在來源非 ASCII 時才建 OCR 模型快取，而快取位置
   來自 `tempfile.gettempdir()`，退回的 `C:\Users\Public\Documents` 在這台機器**不可寫**，
   於是 OCR／AI 相關案例會以「OCR 無法建立可讀取的本機模型快取」失敗。
   把工作區放到 `E:\swbd-tests\release-tests`（ASCII）後 **PDF 套件 46/46 全過**。
   產品本身沒這個問題：安裝路徑與 `%TEMP%` 都是 ASCII，發布建置的 PDF 自測（含 `p_ocr`）
   在非 ASCII 的候選目錄下照樣 12/12。
2. **套件需要的相對配置**：`release-tests\shell` → `_build\shell`、`release-tests\release` →
   候選版本、`release-tests\src` → `_build\src`（用目錄連結補上），以及
   `scratch\tool-schema.json`（由 `tools.schema()` 產生）與 Playwright 的 chromium。

### 15.3 順手修掉的測試腳本問題

`test_logo_resources.py` 找 `logo.ico` 的範圍太窄（原本只找自己旁邊與上兩層），在別的測試
工作區會直接失敗；改成可從命令列指定，並多找 `E:/四維八德/_build/logo.ico` 與
`<工作區>/release/logo.ico`。

### 15.4 同一輪的發布驗證

| 項目 | 結果 |
|---|---|
| 完整發布建置（自 `E:\四維八德` 這個非 ASCII 路徑） | 成功 |
| 候選版本接手數 | `C++ core ready: 8 method(s) taken over` |
| 候選版本外殼煙霧（含 PDF→PDF 斷言） | `ok=true` |
| 候選版本產出 `smoke-output\smoke.pdf` | 13,273 bytes（素材 1,445,569 → 0.9%） |
| 完整安裝驗證（靜默安裝／中文含空白路徑／C 視窗／12 項 PDF／雜湊／解除安裝） | 通過 |
| 安裝程式 | 1,469,707,420 bytes，SHA-256 `8E41CBF703A30CA855B6AB0FCBC68530CD5F97F16A5B988B0A3E9EDE574631C0` |
| 已安裝副本 | 與候選版本雜湊一致 |

第四輪修的 `test_installer.ps1`（明確複製並驗證 `smoke-fixtures\smoke.pdf`）在這一輪生效，
所以「安裝後」那次煙霧測試真的跑到原生 PDF 工作。

---

## 16. 第八批成果：系統資訊模組與兩個注入點

### 16.1 `system_info` 接手（`system_tools.py` 的 hardware_info + CLEANUP）

`app.py` 的 `system_info()` 回傳 `{hardware: hardware_info(), cleanup: CLEANUP}`。now 由 C++ 回答：

- **工作者政策與硬體編碼器不再重寫一份**：`engine.py` 的 `auto_workers／light_workers／work_slots`
  與 C 引擎的三個同名函式**公式完全相同**（實測逐項相同），硬體編碼器偵測也是同一套
  （同三個編碼器、同一道 ffmpeg 指令、同一個 `hw_cache.json`）。所以新增注入點讓 C++ 直接讀引擎的
  結果，而不是在 C++ 再寫第二份政策。
- 這一層自己讀的是：作業系統版本（登錄檔 `CurrentBuildNumber`／`CurrentMajorVersionNumber`）、
  CPU 名稱（`ProcessorNameString`，找不到時用 Python 的同一句「未取得處理器名稱」）、
  架構（`PROCESSOR_ARCHITEW6432`→`PROCESSOR_ARCHITECTURE`）、磁碟（`GetDiskFreeSpaceExW` 的
  total／free）、以及 `round(x, 1)`（用 `nearbyint` 取得與 Python 相同的四捨六入五成雙）。
- 硬體編碼器是背景執行緒偵測的，Python 版會同步等它完成；C++ 版也等（最多 10 秒）。

### 16.2 新增的注入點（第二個架構缺口）

```c
typedef struct swbd_cpp_system_facts {   /* bridge.hpp */
    double ram_gb; int cores, heavy, light, slots;
    int hw_ready, hw_count; char *const *hw;
} swbd_cpp_system_facts;
void swbd_cpp_set_system_facts(void (*provider)(swbd_cpp_system_facts *out));
```

`engine.h` 多了 `eng_facts_get(engine *, eng_facts *)`：C 引擎把記憶體、核心數、三個工作者政策與
硬體編碼器一次交出來。`api.cpp` 負責注入（`api_cpp_system_facts()`），與上一輪的
`api_cpp_busy_probe()` 同一個模式：**住在引擎裡的狀態由外殼注入，C++ 不猜**。

### 16.3 閘門（`gate_system_info.ps1`）

走 **wiring 探針**（連結 shell 的 `api.cpp`，所以測到的是正式注入路徑，不是自己塞假資料）：

| 類別 | 比對 |
|---|---|
| 決定性欄位 | `system`／`supported`／`arch`／`emulated`／`cores`／`heavy`／`light`／`slots` 完全相同 |
| 容差欄位 | `ram`（±0.1）、磁碟 `total`／`free`（±256 MB）、CPU 名稱（去頭尾空白後相同） |
| 硬體編碼器 | 排序後完全相同 |
| cleanup | 4 個分類逐欄相同 |

實測（本機）：`Windows 11`、`AMD64`、20 執行緒、`heavy=4／light=6／slots=4`、`ram=31.8`、
`h264_nvenc`、C:/E: 兩顆磁碟的 total 與 free 全部相同。

**閘門第一次跑時抓到的是閘門自己的錯**：Python 參考沒有設定 `E.FFMPEG`，於是
`detect_hw()` 直接回空陣列，而 C 引擎（有 ffmpeg）回 `['h264_nvenc']`。產品的 `engine.py`
啟動時一定會設定，所以修正的是參考實作（改成一併設定 `base_dir`／`_DATA`／`FFMPEG`）。

### 16.4 既有回歸套件變成一條指令

`run_legacy_regression.ps1` 把 10 個套件包起來（自動重建 ASCII 工作區與目錄連結、
產生 `scratch\tool-schema.json`、逐套件把輸出寫進檔案再讀回來，避開 PowerShell 5.1 對
原生 stderr 的處理），最後印出逐套件結果與總計。實測：

```
[PASS] engine（C 轉檔與工作控制）        PASSED 30 / 30
[PASS] equivalence（C／Python 內容比對） PASSED 28 / 28
[PASS] native options（C 編碼與加速）    PASSED 6 / 6
[PASS] protocol（視窗管線與對話框）      OK（6）
[PASS] pdf suite（PDF 功能與內容）       OK（46）
[PASS] additional（工作流程與工具）      OK（5）
[PASS] feature edges（特殊格式與邊界）   OK（14）
[PASS] uri paths（Unicode 與網址限制）   PASSED 8 / 8
[PASS] logo（新版圖示資源）              ok: true（2）
[PASS] ui（介面與表單）                  PASSED 96 / 96 form variants 446
  套件：10 個，失敗 0 個
```

之後每一輪改動都可以用這一行確認「既有功能沒有退步」。

---

## 17. 第九批成果：工具箱路由（`run_tool`）與第一個原生工具

### 17.1 為什麼是 `run_tool`

82 個工具的實作都在 Python（`tools.py`／`pdf_tools.py`…），而 C 引擎原本只認得「格式轉換」工作，
所以工具箱一直是**完全無法搬移**的表面。這一輪先把路由打開：

```
頁面 → api_request → C++ run_tool（新的接手點）
                        ├─ 已原生實作的工具 → eng_submit_tool → C 引擎的原生工具工作
                        └─ 其餘工具        → 反向呼叫 Python 的 run_tool（整包轉交）
```

「已原生實作」是一份清單（`pdf_tools.cpp` 的 `kNative`），所以之後可以一次搬一個工具，
不必動其他部分。未接手的工具走的是**同一條 Python 路徑**（驗證、設定與實作都在那裡），
連錯誤訊息都原樣傳出去。

### 17.2 兩個新的注入點

| 注入點 | 用途 |
|---|---|
| `swbd_cpp_set_py_call` | C++ 接手的方法反向呼叫 Python（例如取用設定相關的選項）。回覆信封（`{"ok":…}`）在橋接層拆開，失敗時擲出 Python 原本的錯誤字串。 |
| `swbd_cpp_set_tool_submit` | 把原生工具工作送進 C 引擎（`eng_submit_tool`）。 |

選項的解析仍留在 Python：`app.py` 新增 `tool_job_opt(tool, params)`，回傳
`base_opt()` 與 `params` 合併後的選項，並記住這個工具上次的設定（與原本 `run_tool` 做的完全相同）。
設定住在 Python 那一側，C++ 不自己猜；沒有注入 Python 時（測試探針）退回 `base_opt()` 的預設值。

### 17.3 第一個原生工具：`p_remove`（移除頁面）

- 頁碼規格解析（`1,3-5,8-`，含全形逗號）是 `pdf_tools.indices` 的等價實作，錯誤訊息一字不差。
- 組頁用 PDFium（`FPDF_ImportPagesByIndex`，依給定順序），再交給 qpdf 重寫。
- 輸出路徑沿用 Python 的 `output()` 規則：`<來源檔名>_<工具名稱>.pdf`。
- 寫出後與 Python `save()` 一樣做自我檢查（開得起來、頁數正確）。

### 17.4 閘門（`gate_pdf_tools.ps1`）與它抓到的既有差異

wiring 探針多了 `--run-tool`（走 `api_request` 的正式路由），讓原生工具工作可以在**沒有 Python
核心**的情況下被驅動；探針另外合成 Python 的 `status` 回覆，因為 C 引擎的 `status` 會回問 Python
來合併（沒有回應就會等 300 秒）。

| 案例 | 比對結果 |
|---|---|
| 移除 2,4-5、移除單頁 | 檔名、頁數、逐頁文字、逐頁圖片、狀態、encoder、validation **全部相同** |
| 全部移除、頁碼格式錯誤、頁碼超出範圍、空白＝全部 | 錯誤訊息**一字不差** |

**閘門抓到的既有差異**：C 引擎對 PDF 輸出的驗證字串原本是「PDF 結構可讀取」，而
`validation.check` 給的是「PDF 可讀取 · N 頁」（加密文件則是「加密 PDF 結構可讀取」）。
這一輪把 C 引擎改成與 Python 相同（用 PDFium 取頁數與加密處理常式），
所以**轉檔路徑的 PDF 驗證字串也一起變正確了**——這是接手工具箱時才暴露出來的舊差異。

過程中另外修掉兩個探針的錯：`FPDF_GetSecurityHandlerRevision` 的宣告少了 `FPDF_DOCUMENT`
參數（會在執行期崩潰），以及狀態回覆的 `id` 多了一個 `c`（`"cc3"`，導致請求永遠等不到回應）。

### 17.5 第二批原生工具：`p_extract` 與 `p_organize`

路由打開之後，同一家族的工具只是共用同一套零件：

| 工具 | 實作 |
|---|---|
| `p_extract`（提取頁面） | 依輸入順序（可重複）組頁 → qpdf 重寫 |
| `p_organize`（整理／重新排列） | `order`：依輸入順序；`reverse`：反轉全部頁面；`blank`：在選取的頁碼之後插入**同尺寸**空白頁（`FPDFPage_New`，由大到小插入才不會打亂後面的索引） |
| `p_remove`（移除頁面） | 保留沒被選到的頁面（重構成與上面共用尾巴） |

三者共用 `tool_pdf_finish()`（組頁 → qpdf → 寫檔 → 與 Python `save()` 相同的自我檢查），
以及同一套頁碼解析（Python 的 `arrange` 對這三個工具都用 `allow_repeat=True`，所以
`p_extract` 可以重複取同一頁）。

閘門擴到 **11 個案例**（三個工具 × 多種參數、4 個錯誤情況），全部等價：

| 案例 | 頁數 | 逐頁文字／圖片 |
|---|---|---|
| p_remove 2,4-5／3 | 3／5 | 相同 |
| p_extract 3,1-2／2,2,5（重複取頁） | 3／3 | 相同 |
| p_organize order／reverse／blank（2,4） | 4／6／8（6+2 空白） | 相同 |
| 4 個錯誤情況（全部移除、格式、範圍、空白＝全部） | — | 訊息一字不差 |

### 17.6 第三批原生工具：`p_merge`（合併 PDF）

`p_merge` 是 `together=True` 的工具（2 個以上檔案合成一份），所以除了工具實作，也順帶驗證
「一個工作吃多個檔案」這條路徑：`eng_submit_tool` 的 `together` 參數會把整批檔案放進同一個工作，
`tool_out_path` 用第一個檔案當檔名（Python 的 `output()` 也是這樣）。

實作沿用既有的 PDFium 合併（`merge_documents`，現在多了一個密碼參數，因為 Python 對每個來源
都用同一組選項）＋ qpdf 重寫。閘門擴到 **14 個案例**：合併兩份（9 頁）與三份（A,B,C 的順序
故意排成 C,A,B，13 頁）逐頁文字／圖片都相同；「只有一份」是**請求層級的拒絕**
（訊息與 `app.run_tool` 的「加入的檔案數不足」相同），閘門也改成比對請求層級的錯誤。

### 17.7 第四批原生工具：`p_copy`（複製 PDF）

`p_copy` 是「完整副本」：Python 用 `shutil.copyfile` 之後再比對 SHA-256，所以 C++ 這一側
用 `copy_file` ＋**串流逐段比對**（`CreateFileW` 分塊讀，避免整檔進記憶體），失敗時回
「複製驗證失敗」——與 Python 相同的訊息。輸出必須**逐位元相同**，所以閘門對這個工具額外做了
位元組比對（實測兩邊都是 1,924,492 bytes，內容完全相同）。

工具箱閘門因此來到 **15 個案例**，涵蓋 5 個原生工具（`p_copy`／`p_merge`／`p_remove`／
`p_extract`／`p_organize`）。

### 17.8 第五批：`p_compress`（無損）與「模式感知接手」

`p_compress` 有三個等級，但只有 `lossless` 是單純重寫（Python 用 PyMuPDF save）；
`balanced`／`small` 會用 Pillow 重壓內嵌圖片，那需要影像編碼器，所以**刻意留在 Python**。
於是接手清單多了一個維度：

```cpp
struct ToolMeta {
    const char *id; const char *name; int min_files; int max_files; bool together; bool heavy;
    const char *mode_key;      /* 只在這個選項等於 mode_value 時才接手；nullptr = 全部接手 */
    const char *mode_value;
};
```

`find_tool(id, params)` 會檢查模式，不符就**整包交回 Python 的 `run_tool`**。閘門也據此驗證：
`level=lossless` 走原生且逐頁內容相同；`level=balanced` 在探針（沒有 Python 核心）裡必須回
「這一版沒有接上 Python 呼叫介面」—— 這正好證明它**沒有**被原生接手。

無損壓縮的行為與 Python 一致：寫出後若沒有比原檔小，就保留原始位元內容並記一則提醒
（為此 `job` 多了一個 `note` 欄位，`job_info` 的 `notes` 會帶上它；Python 的 `warn()` 就是這個用途）。
實測輸出比 Python 的 PyMuPDF 重寫大一些（59,943 vs 36,209 bytes，兩者都遠小於原檔 1,924,492），
但頁數、逐頁文字與圖片完全相同 —— 這是兩個不同重寫引擎的正常差異。

### 17.9 第六批原生工具：`p_flatten`（PDF 壓平）

Python 是 `doc.bake(annots=True, widgets=True)`（把註記與表單欄位畫進頁面內容後移除）；
PDFium 對應的是 `FPDFPage_Flatten(page, FLAT_NORMALDISPLAY)`。這次的閘門素材**刻意帶註記**
（自由文字＋螢光標記），否則壓平在無註記的文件上只是空操作，驗不出東西：

| 項目 | C++ | Python |
|---|---|---|
| 檔名 `壓平來源 註記_PDF 壓平.pdf` | 相同 | 相同 |
| 頁數／逐頁文字／逐頁圖片（6 頁，含壓平後的註解文字） | **相同** | **相同** |
| 大小 | 65,861 | 37,342 bytes |

工具箱閘門來到 **18 個案例**、7 個原生工具（`p_copy`／`p_flatten`／`p_compress`(無損)／
`p_merge`／`p_remove`／`p_extract`／`p_organize`）。

### 17.10 交接狀態（第 14 輪）

| 面向 | 狀態 |
|---|---|
| 互通契約 | 已凍結並有等價測試（`gate_engine`／`gate_compare`／wiring 閘門／cleanup 等價） |
| 外殼 | 已由 C 轉為 C++，`gate_compare` 的「C vs C++」為 **0 差異** |
| 頁面方法 | 已註冊 10 個 C++ 方法；`cleanup_scan` 的 wiring 斷言證明該方法 `python_calls=0`。`run_tool` 的選項及未接手工具仍可呼叫 Python。 |
| 工具箱 | `run_tool` 由 C++ 接手，7 個工具原生、其餘整包交回 Python（錯誤訊息原樣傳出） |
| 引擎工作 | PDF→PNG、PDF→PDF（含合併）；工具箱工作（合併／刪頁／提取／整理／壓平／複製／無損壓縮） |
| 注入點 | Python 忙碌查詢、系統事實、反向呼叫 Python、原生工具工作送出 |
| 驗證 | 工具箱閘門 18 案例、遷移回歸（引擎／外殼 0 差異）、既有回歸 **10 套件 0 失敗**、發布建置與安裝驗證 |

**下一個明確的技術缺口**：資料夾輸出（`folder(j)`）。它需要把渲染層的一般化版本
（可指定頁碼、密碼、逐頁 dpi 與自訂檔名，且仍然只開檔一次）做好，才能接手 `p_pdf_images`
的「每頁轉成圖片」（PNG 可做到逐像素相同；JPEG 要用已內嵌的 stb_image_write，屆時需要容差比對）。
`p_repair`／`p_content` 這類「一份報告＋一個資料夾」的工具也卡在同一個缺口上。

### 17.11 第 15 輪：資料夾輸出做好了，但 `p_pdf_images` 還不能接手

**已完成並保留的基礎建設**：

| 元件 | 內容 |
|---|---|
| `render_pages()` | 渲染層一般化：可指定頁碼、密碼、逐頁 dpi（`dpi_for`）與自訂檔名（`namer`），**仍然只開檔一次**、PNG 編碼仍與渲染重疊。舊的 `render_all_pages()` 變成轉呼叫，既有 PDF→PNG 路徑一行都沒改。 |
| `tool_out_folder()` | Python `folder(j)` 的等價實作：`<out_dir>\<來源檔名>_<工具名稱>`（unique 後去掉 `.files`）＋建立資料夾＋`keep_output`。 |
| `tool_pdf_images()` | `p_pdf_images` 的「每頁轉圖片」處理常式（dpi 依頁面尺寸夾在 4000 像素內、檔名 `第0001頁.png`、輸出資料夾、`本機頁面渲染`）。**已寫好但尚未啟用。** |
| 接手閘門 | 從單一條件擴充成 `"key=value;key=value"` 多條件（每個條件都要「明確等於」，所以參數缺席時不會意外接手）。 |

**為什麼沒啟用**：閘門一比就發現，原生渲染的*檔名、資料夾名稱、像素尺寸*全部正確
（794×1123、`第0001頁.png`…），但**像素與 PyMuPDF 不同**：

| 觀察 | 數值 |
|---|---|
| 不同的通道比例 | 7.23% |
| 最大通道差 | 255 |
| 差異範圍 | bbox (79, 91, 560, 1001)，集中在內容區 |
| 是否 R/B 互換 | 不是（互換後差異更大） |
| 尺寸 | 完全相同 |

**根本原因（第 16 輪查清）**：不是我的渲染器有問題，而是**兩個不同的渲染引擎**。
`pdf_tools.pdf_images` 用 PyMuPDF（MuPDF）；C++ 這一側用 PDFium。
拿同引擎的參考（`pdf_render_ref.py`：pypdfium2 + Pillow）比對同一頁、同一個 96 dpi：

| 比對 | 結果 |
|---|---|
| C++ vs **pypdfium2**（同引擎） | **逐像素完全相同**（794×1123，`逐像素相同：True`） |
| C++ vs **PyMuPDF**（工具實際用的） | 7.23% 通道差異、最大 255 |

也就是說：轉檔路徑（PDF→PNG，Python 端也是 pypdfium2）可以做到逐位元相同，所以第三輪就接手了；
但 `p_pdf_images` 這個工具的輸出來自 MuPDF，除非把 MuPDF 也搬進來，否則不可能逐位元相同。
這是渲染層級的差異（不是反鋸齒邊緣），所以在做成決定之前**不接手**：`p_pdf_images` 的兩個模式
（PNG／JPG）都維持交回 Python，閘門也改成斷言「必須交回 Python」。要啟用時，把
`pdf_tools.cpp` 裡那一行資料列的註解拿掉即可。

**這一輪真正的收穫**：資料夾輸出不再是缺口；`p_repair`／`p_content` 這類工具已經可以動工。

### 17.12 第 17 輪：`p_repair` 的基礎建設做好，但接手會退步

**已完成的基礎建設**：

| 元件 | 內容 |
|---|---|
| `qpdf_set_attempt_recovery` | qpdf 層的 `rewrite_file(..., recover=true)`（必須在讀取前設定，否則不影響 parse 階段）—— 對應 pikepdf 的 `attempt_recovery=True`。 |
| `rebuild_readable_pages()` | 逐頁重建：只保留「載入並以低倍率真的畫得出來」的頁面，其餘回報為 unreadable。 |
| `tool_pdf_repair()` | 完整處理常式：資料夾輸出（`修復後.pdf` ＋ `修復報告.json`）、逐頁低解析度驗證、`unreadable` 提醒、`encoder=method`。**已寫好但未啟用。** |

**為什麼不啟用（實測證據）**：

| 情況 | Python（pikepdf → MuPDF） | C++（qpdf → PDFium） |
|---|---|---|
| 有效 PDF | `qpdf 結構重建`、逐頁驗證通過 | **完全相同**（encoder／validation／頁數都一致） |
| 截掉結尾 3% 的 PDF | 第一條路徑失敗 → **MuPDF 逐頁復原救回頁面** | 第一條路徑失敗 → PDFium **連開檔都不行**（截斷的 xref）→ 失敗 |

MuPDF 會重建 xref、對損壞檔的容忍度高；PDFium 不會。所以接手 `p_repair` 會讓「損壞檔修復」
從「能救回頁面」變成「直接失敗」——**這是功能退步**，因此維持交回 Python，閘門也改成斷言
「必須交回 Python」。要啟用時把 `pdf_tools.cpp` 那一行資料列的註解拿掉即可。

同時修掉閘門自己的兩個問題：資料夾輸出被誤判成檔案（檢查順序），以及主控台是 cp950 時
印出工具訊息會 UnicodeEncodeError（改成 UTF-8）。修好之後閘門輸出也終於完整可讀。

### 17.13 第 18 輪：抓到並修掉轉交路徑的堆疊溢位（真實崩潰）

**症狀**：在外殼煙霧測試裡加一項「交回 Python」的斷言之後，測試以 `0xC00000FD`（堆疊溢位）
崩潰。移除斷言就恢復正常 —— 二分法指向轉交本身。

**原因**：第 8 輪寫的橋接層把回覆緩衝放在**堆疊**上：

```cpp
char buffer[1 << 20];      /* 1 MB 在堆疊上 */
```

接手的方法是由**頁面處理執行緒**呼叫的，而那個執行緒的堆疊只有 1 MB → 一進去就溢位。
`bridge.cpp` 的緩衝改成 `std::vector<char>`（堆積）。

**為什麼之前的閘門沒抓到**：工具箱閘門用的是 wiring 探針，探針沒有 Python 核心，
所以 `can_py_call()` 是 false，那段程式碼從來沒被執行到。也就是說：**工具箱閘門把「原生接手」
驗得很徹底，卻完全沒有驗到「轉交」**。

**影響範圍**：這個 bug 會讓**所有交回 Python 的工具呼叫**在正式外殼裡直接崩潰
（82 個工具裡有 75 個是轉交的）。這是本專案目前為止影響最廣的一個缺陷，而它是靠
「加一項產品級斷言」而不是靠「再多讀幾次程式碼」找到的。

**現在的防線**：外殼煙霧測試多了一項轉交斷言（工作 id 不可以是 C 引擎的 `x` 開頭、
而且必須真的完成），它會在每次發布建置與安裝驗證時執行 —— 這正是這類 bug 該被抓到的地方。
修好後煙霧測試的 `completion_notifications` 由 2 變成 3，正好對應多完成的那個轉交工作。

### 17.14 第 19 輪：清掉同類的第二個緩衝問題

第 18 輪掃描時發現 `engine.cpp` 的 `same_file_bytes`（`p_copy` 的逐位元驗證）用了
`static unsigned char buf_a[65536], buf_b[65536]`：不在堆疊上（不會像橋接層那樣崩潰），
但這個函式是**由工具工作執行緒呼叫**的，同時跑兩個 `p_copy` 就會互相覆蓋，可能誤報
「複製驗證失敗」。已改成區域（堆積）變數，並用工具箱閘門的逐位元比對確認行為不變。

---

## 18. 目前狀態總表（第 24 輪整理，全部有量測證據）

### 18.1 已接手並驗證

2026-10-15 驗收覆核補充：[C++驗收覆核.md](C++驗收覆核.md)。下表的 0 差異指明確正規化後的已測報告；方法註冊數不代表所有處理都已脫離 Python。覆核補強了缺檔、共同失敗、通知與輸出檔的拒絕條件。

| 類別 | 內容 | 證據 |
|---|---|---|
| 外殼 | C → C++，行為不變 | `gate_compare`：C vs C++ **0 差異**（引擎與外殼都相同） |
| 凍結契約 | C 引擎與 C++ 引擎都重現黃金輸出 | `gate_engine.py` 兩者皆 exit 0 |
| 頁面方法（10） | cleanup ×2、system_info、disk ×3、drives、open_file、reveal、run_tool | 已註冊 10 個方法；wiring 的 `python_calls=0` 直接驗證 cleanup_scan。run_tool 的設定取得及未接手工具仍呼叫 Python。 |
| 原生工具（7） | p_copy、p_flatten、p_compress(無損)、p_merge、p_remove、p_extract、p_organize | 工具箱閘門 **23 案例**（含逐位元複製、帶註記壓平、多檔合併、重複取頁、插入空白頁、走反向呼叫取選項） |
| 引擎工作 | PDF→PNG、PDF→PDF（含合併）、工具工作 | 引擎等價閘門與工具箱閘門 |
| 效能 | 原生 PDF 渲染 **1.11×** 快於 Python 正式工作路徑（2.49× 概念式基準） | `bench_pdf_render.py`（24 頁、223.8 KB） |
| 回歸 | 既有 10 套件、0 失敗 | `run_legacy_regression.ps1` |
| 交付 | 發布建置＋安裝驗證通過，安裝版本與候選一致 | 安裝程式 1,469,791,286 bytes |

### 18.2 刻意「不接手」的部分（都有實測理由）

| 工具／路徑 | 不接手的原因（實測） | 現在的處理 |
|---|---|---|
| `p_pdf_images`（每頁轉圖片、PNG／JPG 兩種） | Python 用 **PyMuPDF（MuPDF）** 渲染，與 PDFium 是不同引擎：同引擎參考（pypdfium2）逐像素相同，與 MuPDF 比有 **7.23% 通道差異**（最大 255）。 | 交回 Python；引擎端實作與資料夾輸出已備好，決定接受差異時解除註解即可 |
| `p_repair` | 有效檔的 qpdf 復原兩邊一致；但**損壞檔** Python 用 MuPDF 逐頁復原（會重建 xref）救得回頁面，PDFium 對截斷的 xref **連開檔都不行** → 接手是功能退步。 | 交回 Python；`tool_pdf_repair` 已備好 |
| `p_compress` 的 `balanced`／`small` | 需要 Pillow 重壓內嵌圖片（JPEG 編碼器不同）。 | 模式感知接手：只有 `level=lossless` 由 C++ 負責 |
| `p_merge` 之外的 MuPDF 家族（文字／表格／註記編輯／OCR 等） | 都需要 MuPDF 專有能力或外部引擎。 | 仍由 Python 執行（`run_tool` 整包轉交） |

### 18.3 這條路上最重要的兩個教訓

1. **閘門驗得再細，沒驗到的路徑就是沒有防線。** 第 18 輪那個 1 MB 堆疊緩衝（會讓 82 個工具裡 75 個崩潰）不是靠讀程式碼找到的，而是靠「在真正的產品路徑上加一項斷言」。補上之後，同一個路徑現在有探針層與產品層兩道斷言。
2. **「視覺相同」不等於「等價」。** `p_pdf_images` 與 `p_repair` 都是先做基礎建設、再用實測證明接手會退步或改變輸出，然後**選擇不接手**並把理由寫進程式註解與文件 —— 而不是把差異藏起來。

---

## 19. 還剩什麼，以及為什麼不能再「照同一條路」搬（第 25 輪查核）

### 19.1 目前 C 引擎接手的轉檔類別（`eng_handles`，實際程式碼）

| 類別 | 是否由 C 引擎接手 | 條件 |
|---|---|---|
| `video`／`audio` | 是 | 走 ffmpeg（與 Python 同一顆） |
| `subtitle` | 是 | 原生 |
| `archive` | 是 | 7-Zip（同一顆） |
| `doc`／`sheet` | 是 | LibreOffice（同一顆） |
| `ebook` | 是 | 既有引擎 |
| `pdf → png` | 是 | PDFium；**逐像素等價**已驗證 |
| `pdf → pdf` | 是 | qpdf＋PDFium；**唯一例外** `preset=small`（Python 會先降採樣圖片） |
| **`image`（jpg／png／webp…）** | **否** | 仍整批在 Python（Pillow） |

### 19.2 剩下的三塊，以及它們共同的性質

| 剩餘表面 | Python 用的引擎 | 若搬到 C++ 會發生什麼 |
|---|---|---|
| 圖片轉檔（`cat == "image"`） | Pillow（libjpeg-turbo、libwebp…） | 換成 stb／libwebp 等其他編碼器 → **輸出不再是位元等價**（與 `p_pdf_images` 同一類問題） |
| MuPDF 家族的 PDF 工具（`p_pdf_images`、`p_repair`、文字／表格／註記編輯、OCR 前處理…） | PyMuPDF（MuPDF） | 已實測：`p_pdf_images` 有 7.23% 通道差異；`p_repair` 對損壞檔 PDFium 連開檔都不行 |
| OCR／摘要／翻譯 | tesseract、本機語言模型 | 這些是外部引擎，C++ 化只是換一層呼叫，沒有等價性問題，但也沒有「架構搬遷」的實質收益 |

**共同性質**：這三塊的輸出都取決於**第三方引擎的實作細節**。在「輸出必須等價」的前提下，
把它們搬到 C++ 只有兩條路：

1. **連引擎一起搬**（例如把 MuPDF 或 libjpeg-turbo 直接連進外殼）—— 技術上可行，
   但等於把授權與體積問題引進原生層，需要另外評估。
2. **改採「容差等價」標準**（例如圖片允許平均通道差 ≤ 2）—— 這是產品決策，不是技術問題。

### 19.3 因此目前的正確定位

在**不放寬等價標準**的前提下，「低風險高效益」的搬遷表面已經走完：

- 外殼（C → C++）✓ 逐欄 0 差異
- 契約與等價測試 ✓ 已凍結並持續通過
- 所有能用「同一顆引擎的 C API」重做的部分 ✓ 都已接手（PDF 渲染、PDF 重寫／合併、工具箱 7 個工具、
  10 個頁面方法、cleanup／system_info／磁碟工具）
- 其餘部分的搬遷，**取決於上面那兩個決策**，而不是取決於還能不能寫更多 C++

下一輪若繼續同方向，建議先做 `p_content` 的**文字與頁面資訊**子項（PDFium 文字 API 與 Python
的 PyMuPDF 在這兩項上的結果是可比對的），其餘子項則用「模式感知」留在 Python。
