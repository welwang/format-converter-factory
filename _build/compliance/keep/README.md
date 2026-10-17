# 四維八德 開源發布合規工程（交付索引與驗收紀錄）

這一目錄是**發布合規閘門**。它不判斷法律問題，只做工程上能證明的事：
從**實際建置產物**掃出 SBOM、與來源清單逐項比對、檢查來源途徑，並在證據不足時**阻止發布**。

## 一、檔案

| 檔案 | 用途 |
|---|---|
| `compliance_audit.py` | 稽核引擎（scan／diff／sources／gate／all） |
| `gate_release.ps1` | 發布閘門（fail-closed；公開發行前必須回傳 0） |
| `out/sbom.cdx.json` | CycloneDX 1.5 SBOM（機器可讀，含路徑、SHA-256、授權證據） |
| `out/scan.json` | 原始掃描結果（元件、證據檔、PE 版本、雜湊） |
| `out/inventory-diff.json` | SBOM ↔ `source/來源清單.json` 的 8 類差異 |
| `out/source-offer.json` | `source_download` 與上游封裝的可存取性與對應性 |
| `out/gate-result.json` | 閘門逐項結果（PASS／FAIL＋blocking 清單） |
| `out/audit-report.md` | 人可讀稽核報告 |
| `out/needs-legal-review.md` | 給法律專業人員的待確認清單 |

## 二、怎麼跑

```powershell
# 對最新 release-stage 的 payload 稽核並產生全部報告
_build\compliance\gate_release.ps1

# 只輸出機器可讀結果（CI 用）
_build\compliance\gate_release.ps1 -Json

# 指定 payload
_build\compliance\gate_release.ps1 -Payload 'E:\...\dist\swbd-core'
```

`_build\build.ps1` 結尾已接上同一支閘門：**開發與測試建置不受影響**（只印出 BLOCKED 提示），
設 `SWBD_REQUIRE_COMPLIANCE=1` 時建置會在閘門未通過時失敗（CI／發布流程用）。

## 三、閘門的 7 項檢查與目前狀態（2026-10-15 實測）

| 檢查 | 目前 | 說明 |
|---|---|---|
| `audit_flag_complete` | **FAIL** | `public_distribution_audit_complete` 為 `false` |
| `no_unconfirmed_components` | **FAIL** | 仍有 3 個元件無法從隨附證據判定授權：`pdfium.dll`、`libdeflate`、`zlib` |
| `license_documents_present` | PASS | LICENSE、COPYING.AGPL-3.0、授權說明.md、開源與散布說明.md、WebView2 聲明齊備 |
| `source_offer_reachable` | PASS | `source_download` 與 4 個上游封裝網址皆可存取 |
| `version_consistent` | **FAIL** | **來源清單 2.3.3，但實際安裝在使用者機器上的版本是 2.3.2** |
| `no_unlisted_binaries` | **FAIL** | 2 個未記載且無授權證據的元件（`pdfium.dll`、`libdeflate`） |
| `indirect_dependencies_confirmed` | **FAIL** | 來源清單自述的 4 項未完成 |

**閘門結果：BLOCKED（不得公開發行）**，離開碼 1。

## 四、掃描涵蓋

- 104 個元件、代表性檔案雜湊（SHA-256）、PE 版本資源讀出的真實版本。
- 授權宣告 101 / 104 來自**隨附證據**：`BUNDLED_LICENSE_FILE`（授權檔內容比對）、
  `.dist-info/METADATA`、來源清單明確記載（標示為 `INVENTORY_CLAIM`，不是獨立查證）。
- 整合方式也記錄下來：`qpdf30-*.dll`、`pdfium.dll` 為 **`LoadLibrary` 動態載入**；
  `zlib`、`stb_image_write` 為**靜態編入**；`ffmpeg`、`7z`、LibreOffice 等為**獨立程式**。

## 五、驗收與未完成事項（不掩飾）

**已驗證**

- 產品程式碼**完全未被改動**：`git status --short` 於非 `_build` 路徑的變更數 = **0**。
  （因此「不破壞轉檔／PDF／AI／UI／安裝功能」是結構性成立，不是靠測試推論。）
- `build.ps1` 在加入檢查後以 PS 5.1 剖析器檢查：**0 個剖析錯誤**。
- 閘門可重現執行，回傳 1；報告與 SBOM 由實際 payload 產生。

**未完成（保留阻擋狀態，不假裝通過）**

1. **3 個 UNKNOWN 未解決**：`pdfium.dll`（授權應在 `pypdfium2` 套件內，本次查找未命中）、
   `libdeflate`、`zlib`（授權文字在標頭檔內，本次比對未命中）。這是**真實缺口**，不是誤判。
2. **實際安裝包內容未拆解核對**：SBOM 掃的是 staged payload；尚未從打包完成的
   `四維八德_*.exe` 反解內容比對（Inno 安裝包需要對應工具）。
3. **未在乾淨 Windows 環境做安裝驗收**。
4. **優先清單的逐項授權核實未完成**：FFmpeg 間接相依、LibreOffice、Calibre、Pandoc、7-Zip、
   qpdf、LibRaw、Python 擴充模組。這些大多是「授權檔存在但上游條款未逐條核對」，
   仍有 `UNKNOWN`／`NEEDS_LEGAL_REVIEW` 的部分。
5. **版本不一致只被偵測，沒有被修正**：2.3.2（已安裝）vs 2.3.3（來源清單／文件）。
   修正需要重新建置並重新安裝，屬於發布決策，工具不代替決定。
6. **`source_download` 只指向儲存庫首頁**，沒有指向與發行版對應的版本／標籤：列為
   `missing_source_download`（high）。是否滿足 GPLv3 第 6 條／AGPLv3 第 13 條 → `NEEDS_LEGAL_REVIEW`。

## 六、給後續維護者的兩個提醒

1. **不要靠改布林值讓閘門通過。** 所有判斷都從檔案、雜湊與實際產物重新計算
   （`audit_flag_complete` 只是其中一項，其餘六項與它無關）。
2. **我自己在這件事上犯過一次錯，值得記下來**：我一度把 `.dist-info/METADATA` 排到證據清單
   最前面，結果真正的 LICENSE 檔被擠掉，UNKNOWN 由 3 個暴增到 58 個。是工具**如實回報數字**
   才讓我當下發現並回退。這就是為什麼報告要印數量，而不是只印結論。
