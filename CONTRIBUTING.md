# 參與貢獻

謝謝你願意改善四維八德！這份文件說明回報問題、提出建議與送出程式碼的方式。

## 回報錯誤

到 [Issues](https://github.com/welwang/format-converter-factory/issues/new/choose) 選「錯誤回報」，並提供：

- 四維八德版本（「關於」視窗）與 Windows 版本。
- 重現步驟、預期結果與實際結果。
- 側邊欄「開啟記錄檔」中 `logs\zdgc.log` 的相關內容。
- 如果與特定檔案有關，盡量提供能重現的小檔案（請先移除個人或機密資料）。

安全性問題請**不要**公開回報，改依 [SECURITY.md](SECURITY.md) 處理。

## 提出功能建議

選「功能建議」，描述你想解決的問題、目前的做法，以及希望的結果。說明使用情境比指定實作方式更有幫助。

## 送出程式碼

1. Fork 本儲存庫，從 `main` 建立分支（例如 `fix/pdf-merge-bookmarks`）。
2. 依 README 的[從原始碼建置](README.md#從原始碼建置)準備環境。
3. 修改後執行完整建置：`powershell -ExecutionPolicy Bypass -File _build\建置安裝包.ps1`。建置會跑內建自我檢測與 PDF 自我檢測，全部通過才算完成。
4. 在 [CHANGELOG.md](CHANGELOG.md) 的最上方記下使用者看得到的變更。
5. 送出 Pull Request，說明改了什麼、為什麼改，以及你怎麼驗證。

### 撰寫原則

- **完全本機**：不新增需要雲端服務、帳號或 API 金鑰的功能；網路只用在使用者明確要求的下載。
- **自帶相依**：新的引擎或套件必須能放進 `tools\` 或 PyInstaller 封裝，並在 `engine.COMPONENTS`、`授權說明.md` 與 `source/來源清單.json` 記錄版本、來源與授權。
- **不覆蓋原檔**：所有輸出寫到新檔；會刪除或永久修改資料的操作必須先預覽、再確認。
- **不假裝成功**：輸出要經過檢查；量不到的資料要明說，不可推定為正常。
- **白話的介面文字**：介面使用繁體中文與台灣用語，錯誤訊息要說明原因與處理方式。
- **C++ 移植**：把 Python 方法搬到 C++ 時，輸出必須與 Python 版相同。
- **檔案編碼**：原始碼使用 UTF-8；PowerShell 腳本使用 UTF-8（含 BOM）以相容 Windows PowerShell 5.1。

### Commit 訊息

用一句話說明變更，必要時在下方補充原因，例如：

```text
修正 PDF 合併時書籤遺失

pypdf 合併時未帶入外部書籤，改為逐檔複製 outline。
```

## 授權

送出貢獻即表示你同意以本專案的授權（GPL-3.0；PDF 模組為 AGPL-3.0）釋出該貢獻。

## 行為準則

參與本專案請遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
