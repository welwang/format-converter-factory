# 版本更新

本專案的重要變更都記錄在這裡。格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [語意化版本](https://semver.org/lang/zh-TW/)。

## [2.3.4] - 2026-10-15

### 新增
- **電腦健康檢查**（電腦工具）：五個階段實際量測處理器、顯示卡、記憶體、硬碟、散熱、網路、裝置驅動、系統穩定性與電池，結果分「電腦總覽／問題解釋／專業資料」三層。
  - 沒有量到的項目一律標「未測試」；可能原因只在量測有證據時才標「有證據」。
  - 一般模式（快速／標準）與專業模式（自訂負載時間與記憶體測試量、時間軸圖表、原始資料匯出）。
  - 狀態：正常、需注意、異常、部分檢查、需要確認、已停用、未測試。
- 背景元件是舊版時，健康檢查會直接說明原因與更新方式。
- 一鍵腳本 `重新建置安裝包到桌面.cmd`：建置與測試、安裝程式與免安裝版放到桌面、換上新版程式、刪除舊版本。
- `_build\部署最新候選版.ps1`：把全部測試通過的建置換到專案資料夾，失敗自動還原。

### 變更
- Logo 統一為單一圖形（四個互扣鏈環），所有尺寸的圖示、介面與文件圖片都由 `_build\logo\make_logo.py` 同一份向量圖產生。
- 說明文件整合成 `README.md` 與本檔；程式「關於」視窗的「使用說明」改開 README，新增「版本更新」。
- 儲存庫依 GitHub 慣例補上 `CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md` 與 Issue／PR 範本。

### 移除
- 「磁碟檢查與修復」頁面及 Python／C++ 兩邊的 `disk_*` 方法；C++ 註冊方法由 10 個減為 7 個。
- 小尺寸 Logo `logo-sm.png` 與其他 Logo 變體。
- 測試程式與測試報告（`_build\tests`、C++ 測試驅動、`TEST_RESULTS.md`、`測試報告.html`、`PACKAGE_VALIDATION.md`），以及舊說明文件（`使用說明.md`、`PDF功能清單.md`、`版本更新.md`、`工程技術說明書.md`）。建置時的內建自我檢測保留。

## [2.3.3] - 2026-10-15

### 變更
- 主程式與原生工作引擎改用 C++20；維持 C++／Python 混合架構與完整離線引擎、模型。
- 原生 PDF→PNG、PDF→PDF（含合併），以及複製、壓平、無損壓縮、合併、移除、抽取、重排七項 PDF 工具。
- 圖片、OCR、非無損壓縮與損壞檔修復維持既有 Python 處理與相同輸出。

### 修正
- Python 轉交路徑的堆疊溢位。
- 並行複製驗證的共享緩衝競態。
- PDF 頁數驗證訊息。

## [2.3.2] - 2026-10-15

### 變更
- 重建 C 主程式、Python 背景元件與安裝程式，內嵌新版多解析度圖示。
- 發布頁不再提供來源 ZIP；應用程式原始碼保留在公開儲存庫。

### 修正
- 關於視窗開啟文件失敗時的提示。

## [2.3.1] - 2026-10-14

### 變更
- 安裝包精簡：移除約 69 MB 未使用的 Office 巨集／資料庫與電子書介面資源、重複的 25 MB MuPDF DLL 與開發標頭。
- 改用單一壓縮區塊，解壓字典維持 64 MB。
- 保留完整離線功能與三個原始模型（模型雜湊與 2.3.0 相同，未降低量化等級）。

## [2.3.0] - 2026-10-14

### 新增
- **音檔轉文字**：錄音、影片離線轉成逐字稿（Word 附時間、純文字、SRT），依停頓分段，可轉繁體。
- **會議總結**：會議錄音離線轉逐字稿，整理摘要、重點、決議與待辦，輸出 Word、Markdown 與 SRT。
- C 原生 Windows／WebView2 主視窗與一般轉檔引擎：真實路徑拖放、原生選檔、單一視窗與位置記憶；不再需要 pywebview／.NET。
- 所有相依都包在程式內，包含 LibreOffice、Ghostscript 與離線文字模型需要的 Visual C++ 執行庫；元件不齊時不打包。

### 變更
- 硬體短測改成產生中文報告，結果直接顯示在「電腦工具」頁。
- 效能：單支影片轉檔可用全部 CPU 執行緒；PDF 轉圖片平行存檔；多張圖片合成 PDF 改成逐張寫入；大張 JPEG 縮放加速；啟動更快。

### 移除
- 需要另外從 Microsoft Store 安裝的「檔案救援」。
- EPUB 轉 MOBI、STL 轉 GLB。

### 修正
- 格式篩選對話框、快速工作完成通知、通訊隔離、CD 64 位元控制代碼與錄影管線清理。

## [2.2.0]

### 新增
- PDF 工作台與本機工具清單：OCR、文件重建、PDF/A、表單、永久遮蔽、比較、簽章、摘要、翻譯與 Markdown。
- 八種語言 OCR 與 CPU 文字模型，不需要登入或 API 金鑰。
- 掃描文件交付流程，簽章放在最終 PDF 產出之後。

### 修正
- yt-dlp UTF-8 完成路徑解析、既有下載檔案路徑、Windows 開啟檔案與顯示位置。

## [2.1.0]

### 新增
- 交付工作台、可保存的工具流程、成品檢查、HEVC／AV1、轉檔前後預覽。
- 電腦硬體短測與暫存清理預覽。

[2.3.4]: https://github.com/welwang/format-converter-factory/compare/v2.3.3...main
[2.3.3]: https://github.com/welwang/format-converter-factory/releases/tag/v2.3.3
[2.3.2]: https://github.com/welwang/format-converter-factory/releases/tag/v2.3.2
[2.3.1]: https://github.com/welwang/format-converter-factory/releases/tag/v2.3.1
[2.3.0]: https://github.com/welwang/format-converter-factory/releases/tag/v2.3.0
[2.2.0]: https://github.com/welwang/format-converter-factory/releases
[2.1.0]: https://github.com/welwang/format-converter-factory/releases
