# 四維八德 2.3.2 測試報告

![四維八德藍寶石 Logo](assets/logo.png)

測試日期：2026-10-15（Asia/Taipei）。最終已執行測試 **374／374 通過，0 項失敗**。介面涵蓋 82 個工具、446 種表單狀態。相同功能在不同層的檢查分別計數；數字不是不重複的功能數，也不表示所有電腦、所有文件或 AI 輸出都沒有錯誤。

## 測試環境與方法

Windows AMD64，系統版本 10.0.26300，20 個 CPU 執行緒，已偵測 NVIDIA NVENC；Python 3.12.10、MSVC、WebView2。C 程式實際在 Windows 編譯並執行。使用自行產生的影音、圖片、文件、壓縮檔、RAW／PSD、OCR 圖片及測試憑證。未錄製使用者螢幕、麥克風或實際修復使用者磁碟。

| 測試組 | 通過 | 失敗 |
|---|---:|---:|
| C 轉檔與工作控制 | 30/30 | 0 |
| C／Python 內容比對 | 28/28 | 0 |
| C 編碼與加速選項 | 6/6 | 0 |
| PDF 打包元件 | 12/12 | 0 |
| 介面與表單 | 96/96 | 0 |
| Unicode 與來源網址限制 | 8/8 | 0 |
| 精簡資源與模型內容 | 4/4 | 0 |
| 新版圖示資源 | 2/2 | 0 |
| 完整離線自我測試 | 81/81 | 0 |
| PDF 功能與內容 | 46/46 | 0 |
| OCR 交付與下載 | 5/5 | 0 |
| 工作流程與電腦工具 | 35/35 | 0 |
| 視窗管線與對話框 | 6/6 | 0 |
| 特殊格式與設備邊界 | 14/14 | 0 |
| Windows 原生視窗整合 | 1/1 | 0 |

## 2.3.2 Logo 更新與回歸驗證

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

### C 轉檔與工作控制

| 項目 | 結果 | 補充 |
|---|---|---|
| video_mp4 | 通過 | 影音串流可讀取（未做全片解碼） |
| video_mkv | 通過 | 影音串流可讀取（未做全片解碼） |
| video_webm | 通過 | 影音串流可讀取（未做全片解碼） |
| video_mov | 通過 | 影音串流可讀取（未做全片解碼） |
| video_avi | 通過 | 影音串流可讀取（未做全片解碼） |
| video_gif | 通過 | 影音串流可讀取（未做全片解碼） |
| video_mp3 | 通過 | 影音串流可讀取（未做全片解碼） |
| video_m4a | 通過 | 影音串流可讀取（未做全片解碼） |
| video_wav | 通過 | 影音串流可讀取（未做全片解碼） |
| video_flac | 通過 | 影音串流可讀取（未做全片解碼） |
| video_ogg | 通過 | 影音串流可讀取（未做全片解碼） |
| video_opus | 通過 | 影音串流可讀取（未做全片解碼） |
| trim | 通過 | 影音串流可讀取（未做全片解碼） |
| size_cap | 通過 | 影音串流可讀取（未做全片解碼） · 容量符合上限 |
| merge | 通過 | 影音串流可讀取（未做全片解碼） |
| hdr | 通過 | 影音串流可讀取（未做全片解碼） |
| big5_vtt | 通過 | 檔案已產生 |
| big5_ass | 通過 | 檔案已產生 |
| markdown_docx | 通過 | 檔案已產生 |
| markdown_html | 通過 | 檔案已產生 |
| markdown_txt | 通過 | 檔案已產生 |
| markdown_rtf | 通過 | 檔案已產生 |
| office_word_pdf | 通過 | PDF 結構可讀取 |
| office_sheet_pdf | 通過 | PDF 結構可讀取 |
| office_ppt_pdf | 通過 | PDF 結構可讀取 |
| archive_7z | 通過 | 壓縮檔完整性檢查通過 |
| archive_extract | 通過 | 已檢查 1 個輸出檔案 |
| ebook | 通過 | 檔案已產生 |
| error_retry | 通過 |  |
| cancel_running | 通過 |  |

### C／Python 內容比對

| 項目 | 結果 | 補充 |
|---|---|---|
| video_mp4 | 通過 |  |
| video_mkv | 通過 |  |
| video_webm | 通過 |  |
| video_mov | 通過 |  |
| video_avi | 通過 |  |
| video_gif | 通過 |  |
| video_mp3 | 通過 |  |
| video_m4a | 通過 |  |
| video_wav | 通過 |  |
| video_flac | 通過 |  |
| video_ogg | 通過 |  |
| video_opus | 通過 |  |
| trim | 通過 |  |
| size_cap | 通過 |  |
| merge | 通過 |  |
| hdr | 通過 |  |
| big5_vtt | 通過 |  |
| big5_ass | 通過 |  |
| markdown_docx | 通過 |  |
| markdown_html | 通過 |  |
| markdown_txt | 通過 |  |
| markdown_rtf | 通過 |  |
| office_word_pdf | 通過 |  |
| office_sheet_pdf | 通過 |  |
| office_ppt_pdf | 通過 |  |
| archive_7z | 通過 |  |
| archive_extract | 通過 |  |
| ebook | 通過 |  |

### C 編碼與加速選項

| 項目 | 結果 | 補充 |
|---|---|---|
| hevc | 通過 | libx265 |
| av1 | 通過 | libsvtav1 |
| gpu_or_cpu_fallback | 通過 | h264_nvenc |
| lossless_container_copy | 通過 | 直接封裝（不重新編碼） |
| audio_copy | 通過 | aac |
| full_decode_validation | 通過 | libx264 |

### PDF 打包元件

| 項目 | 結果 | 補充 |
|---|---|---|
| p_merge | 通過 |  |
| p_pdf_word | 通過 |  |
| p_pdf_excel | 通過 |  |
| p_pdf_ppt | 通過 |  |
| p_markdown | 通過 |  |
| p_redact | 通過 |  |
| p_pdfa | 通過 |  |
| p_ocr | 通過 |  |
| p_summary | 通過 |  |
| p_translate | 通過 |  |
| p_workflow | 通過 |  |
| p_certificate | 通過 |  |

### 介面與表單

| 項目 | 結果 | 補充 |
|---|---|---|
| v_social | 通過 | 6 種表單狀態 |
| v_fill | 通過 | 11 種表單狀態 |
| v_crop | 通過 | 8 種表單狀態 |
| v_rotate | 通過 | 6 種表單狀態 |
| v_speed | 通過 | 1 種表單狀態 |
| v_wm_text | 通過 | 8 種表單狀態 |
| v_wm_img | 通過 | 8 種表單狀態 |
| v_delogo | 通過 | 1 種表單狀態 |
| v_subs | 通過 | 3 種表單狀態 |
| v_autosub | 通過 | 17 種表單狀態 |
| v_audio | 通過 | 3 種表單狀態 |
| v_mute | 通過 | 1 種表單狀態 |
| v_split | 通過 | 3 種表單狀態 |
| v_stab | 通過 | 4 種表單狀態 |
| v_enhance | 通過 | 4 種表單狀態 |
| v_fade | 通過 | 1 種表單狀態 |
| v_reverse | 通過 | 1 種表單狀態 |
| v_frames | 通過 | 3 種表單狀態 |
| v_grid | 通過 | 7 種表單狀態 |
| a_volume | 通過 | 7 種表單狀態 |
| a_pitch | 通過 | 7 種表單狀態 |
| a_vocal | 通過 | 7 種表單狀態 |
| a_denoise | 通過 | 10 種表單狀態 |
| a_silence | 通過 | 7 種表單狀態 |
| a_mix | 通過 | 9 種表單狀態 |
| a_ringtone | 通過 | 3 種表單狀態 |
| a_tags | 通過 | 1 種表單狀態 |
| a_transcribe | 通過 | 18 種表單狀態 |
| a_meeting | 通過 | 16 種表單狀態 |
| i_resize | 通過 | 9 種表單狀態 |
| i_rotate | 通過 | 19 種表單狀態 |
| i_watermark | 通過 | 15 種表單狀態 |
| i_collage | 通過 | 7 種表單狀態 |
| i_slideshow | 通過 | 10 種表單狀態 |
| i_gif | 通過 | 1 種表單狀態 |
| p_split | 通過 | 4 種表單狀態 |
| p_pages | 通過 | 3 種表單狀態 |
| p_rotate | 通過 | 4 種表單狀態 |
| p_encrypt | 通過 | 1 種表單狀態 |
| p_decrypt | 通過 | 1 種表單狀態 |
| x_privacy | 通過 | 1 種表單狀態 |
| d_dvd | 通過 | 3 種表單狀態 |
| d_bluray | 通過 | 3 種表單狀態 |
| d_cd | 通過 | 5 種表單狀態 |
| d_iso | 通過 | 1 種表單狀態 |
| p_merge | 通過 | 1 種表單狀態 |
| p_remove | 通過 | 1 種表單狀態 |
| p_extract | 通過 | 1 種表單狀態 |
| p_organize | 通過 | 4 種表單狀態 |
| p_scan | 通過 | 12 種表單狀態 |
| p_compress | 通過 | 4 種表單狀態 |
| p_repair | 通過 | 1 種表單狀態 |
| p_ocr | 通過 | 12 種表單狀態 |
| p_images_pdf | 通過 | 4 種表單狀態 |
| p_word_pdf | 通過 | 1 種表單狀態 |
| p_ppt_pdf | 通過 | 1 種表單狀態 |
| p_excel_pdf | 通過 | 1 種表單狀態 |
| p_office_pdf | 通過 | 1 種表單狀態 |
| p_html_pdf | 通過 | 1 種表單狀態 |
| p_pdf_images | 通過 | 8 種表單狀態 |
| p_pdf_word | 通過 | 9 種表單狀態 |
| p_pdf_word_ocr | 通過 | 9 種表單狀態 |
| p_pdf_ppt | 通過 | 11 種表單狀態 |
| p_pdf_excel | 通過 | 9 種表單狀態 |
| p_pdf_excel_ocr | 通過 | 9 種表單狀態 |
| p_pdfa | 通過 | 1 種表單狀態 |
| p_numbers | 通過 | 9 種表單狀態 |
| p_watermark | 通過 | 3 種表單狀態 |
| p_crop | 通過 | 3 種表單狀態 |
| p_edit | 通過 | 1 種表單狀態 |
| p_forms | 通過 | 5 種表單狀態 |
| p_sign | 通過 | 1 種表單狀態 |
| p_certificate | 通過 | 1 種表單狀態 |
| p_redact | 通過 | 1 種表單狀態 |
| p_compare | 通過 | 1 種表單狀態 |
| p_summary | 通過 | 14 種表單狀態 |
| p_translate | 通過 | 17 種表單狀態 |
| p_markdown | 通過 | 9 種表單狀態 |
| p_copy | 通過 | 1 種表單狀態 |
| p_content | 通過 | 1 種表單狀態 |
| p_flatten | 通過 | 1 種表單狀態 |
| p_workflow | 通過 | 9 種表單狀態 |
| keyboard_search_escape | 通過 |  |
| open_and_reveal_buttons | 通過 |  |
| offline_report_button | 通過 |  |
| pdf_drag_text_action | 通過 |  |
| viewport_1024 | 通過 |  |
| viewport_1366 | 通過 |  |
| viewport_1920 | 通過 |  |
| theme_dark | 通過 |  |
| theme_light | 通過 |  |
| logo_loaded | 通過 |  |
| sidebar_small_logo | 通過 |  |
| drop_small_logo | 通過 |  |
| about_full_logo | 通過 |  |
| javascript_no_errors | 通過 |  |

### Unicode 與來源網址限制

| 項目 | 結果 | 補充 |
|---|---|---|
| ascii_path | 通過 |  |
| chinese_path | 通過 |  |
| space_path | 通過 |  |
| literal_percent_hash_path | 通過 |  |
| mixed_unicode_path | 通過 |  |
| reject_https | 通過 |  |
| reject_other_page | 通過 |  |
| reject_remote_host | 通過 |  |

### 精簡資源與模型內容

| 項目 | 結果 | 補充 |
|---|---|---|
| ebook_pdf_same_text_and_pixels | 通過 |  |
| pdf-ai/model.gguf | 通過 |  |
| models/ggml-base.bin | 通過 |  |
| models/ggml-silero-v5.1.2.bin | 通過 |  |

### 新版圖示資源

| 項目 | 結果 | 補充 |
|---|---|---|
| 四維八德.exe_new_icon_resources | 通過 | 7 ICO entries embedded; payload SHA-256 matches |
| swbd-core.exe_new_icon_resources | 通過 | 7 ICO entries embedded; payload SHA-256 matches |

### 完整離線自我測試

| 項目 | 結果 |
|---|---|
| v.mp4 → mkv | 通過 |
| v.mp4 → mp4 {'height': 480} | 通過 |
| v.mp4 → webm | 通過 |
| v.mp4 → gif {'trim_end': 3} | 通過 |
| v.mp4 → mp3 | 通過 |
| v.mp4 → mp4 {'target_mb': 1} | 通過 |
| v.mkv → mp4 | 通過 |
| hdr.mov → mp4 {'fastcopy': False} | 通過 |
| a.wav → flac | 通過 |
| a.wav → opus | 通過 |
| a.wav → mp3 {'loudnorm': True} | 通過 |
| a96.m4a → mp3 | 通過 |
| i.heic → jpg | 通過 |
| alpha.png → jpg | 通過 |
| alpha.png → webp | 通過 |
| alpha.png → avif | 通過 |
| alpha.png → ico | 通過 |
| img0.jpg → jpg {'target_mb': 0.05} | 通過 |
| img0.jpg → pdf | 通過 |
| multi.pdf → png | 通過 |
| multi.pdf → pdf {'preset': 'small'} | 通過 |
| multi.pdf → txt | 通過 |
| d.md → docx | 通過 |
| d.md → html | 通過 |
| d.md → pdf | 通過 |
| t.txt → pdf | 通過 |
| d.docx → pdf | 通過 |
| s.csv → xlsx | 通過 |
| b.epub → azw3 | 通過 |
| b.epub → docx | 通過 |
| x.zip → extract | 通過 |
| x.zip → 7z | 通過 |
| sub.srt → vtt | 通過 |
| m.stl → obj | 通過 |
| 社群一鍵規格 {'mode': 'vertical'} | 通過 |
| 社群一鍵規格 {'mode': 'mb10'} | 通過 |
| 裁切畫面 {'mode': '1:1'} | 通過 |
| 裁切畫面 {'mode': '9:16'} | 通過 |
| 旋轉／翻轉 {'op': 'cw'} | 通過 |
| 旋轉／翻轉 {'op': 'ccw', 'fast': True} | 通過 |
| 變速 {'speed': 2} | 通過 |
| 文字浮水印 {'text': '© 測試 100% test:1'} | 通過 |
| 圖片浮水印／Logo {'logo': '[測試資料夾] | 通過 |
| 去除浮水印 {'rect': '1000,40,200,80'} | 通過 |
| 加字幕 {'sub': '[測試資料夾] | 通過 |
| 加字幕 {'sub': '[測試資料夾] | 通過 |
| 配樂／換音軌 {'music': '[測試資料夾] | 通過 |
| 去除聲音 | 通過 |
| 分割影片 {'mode': 'every', 'sec': 3} | 通過 |
| 防手震 | 通過 |
| 畫面調整 {'bright': 10, 'denoise': '1' | 通過 |
| 淡入淡出 | 通過 |
| 倒轉播放 | 通過 |
| 擷取畫面／縮圖總覽 {'mode': 'sheet'} | 通過 |
| 多支影片並排 {'layout': 'h', 'size': '48 | 通過 |
| 音量／淡入淡出 {'gain': 3, 'fout': 2} | 通過 |
| 變速／變調 {'semi': 2} | 通過 |
| 去人聲（伴奏） | 通過 |
| 降噪 | 通過 |
| 去除靜音 | 通過 |
| 混音 | 通過 |
| 鈴聲製作 {'len': 5} | 通過 |
| 歌曲資訊／封面 {'title': '測試', 'cover': ' | 通過 |
| 批次縮放 {'val': 800} | 通過 |
| 旋轉／翻轉／裁切 {'op': 'cw', 'crop': '1:1 | 通過 |
| 圖片浮水印 {'pos': 'tile'} | 通過 |
| 拼長圖／拼圖 | 通過 |
| 圖片轉影片 {'sec': 2, 'size': '1280x720 | 通過 |
| 圖片轉 GIF 動畫 | 通過 |
| PDF 分割 | 通過 |
| 頁面整理 {'pages': '5,1-2'} | 通過 |
| PDF 旋轉 | 通過 |
| PDF 加密 {'pw': '1234'} | 通過 |
| 隱私清除 | 通過 |
| 隱私清除 | 通過 |
| 隱私清除 | 通過 |
| AI 自動字幕（base 模型） | 通過 |
| 音檔轉文字（Word） | 通過 |
| 會議總結（快速摘錄） | 通過 |
| 會議總結（離線 AI） | 通過 |
| 取消工作 | 通過 |

### PDF 功能與內容

| 項目 | 結果 |
|---|---|
| test_01_inventory | 通過 |
| test_02_merge | 通過 |
| test_03_remove | 通過 |
| test_04_extract_reorder | 通過 |
| test_05_reorder_reverse | 通過 |
| test_06_blank_page | 通過 |
| test_07_remove_all_rejected | 通過 |
| test_08_compress | 通過 |
| test_09_repair | 通過 |
| test_10_ocr_searchable | 通過 |
| test_11_images | 通過 |
| test_12_scan | 通過 |
| test_13_render | 通過 |
| test_14_extract_images | 通過 |
| test_15_word | 通過 |
| test_16_word_ocr | 通過 |
| test_17_ppt | 通過 |
| test_18_excel | 通過 |
| test_19_excel_ocr | 通過 |
| test_20_pdfa | 通過 |
| test_21_numbers | 通過 |
| test_22_watermark | 通過 |
| test_23_crop | 通過 |
| test_24_edit | 通過 |
| test_25_form_fill | 通過 |
| test_26_form_create | 通過 |
| test_27_sign_drawing | 通過 |
| test_28_redact | 通過 |
| test_29_redact_confirmation | 通過 |
| test_30_compare | 通過 |
| test_31_markdown | 通過 |
| test_32_content | 通過 |
| test_33_flatten | 通過 |
| test_34_copy | 通過 |
| test_35_summary_extract | 通過 |
| test_36_preview | 通過 |
| test_37_password_fail | 通過 |
| test_38_sanitized_secrets | 通過 |
| test_39_paths | 通過 |
| test_40_open_missing | 通過 |
| test_41_reveal | 通過 |
| test_42_open | 通過 |
| test_43_certificate | 通過 |
| test_44_cancel | 通過 |
| test_45_offline_ai | 通過 |
| test_46_translation | 通過 |

### OCR 交付與下載

| 項目 | 結果 |
|---|---|
| test_47_workflow | 通過 |
| test_48_word_to_pdf | 通過 |
| test_49_html_local | 通過 |
| test_50_html_remote_rejected | 通過 |
| test_51_download_paths | 通過 |

### 工作流程與電腦工具

| 項目 | 結果 |
|---|---|
| test_01_merge_mixed_ratio | 通過 |
| test_02_merge_missing_audio | 通過 |
| test_03_size_failure_keeps_output | 通過 |
| test_04_repack_archive | 通過 |
| test_05_pdf_parallel_render | 通過 |
| test_06_pdf_lock_serializes | 通過 |
| test_07_product_pack | 通過 |
| test_08_video_pack_subtitles_logo | 通過 |
| test_09_pipeline_and_source_unchanged | 通過 |
| test_10_share_mixed_pack_partial | 通過 |
| test_11_profile_secrets_and_validation | 通過 |
| test_12_options_log_redaction | 通過 |
| test_13_cancel_recording_routes_to_stop | 通過 |
| test_14_partial_playlist | 通過 |
| test_15_failed_batch_does_not_shutdown | 通過 |
| test_16_clear_history_releases_jobs | 通過 |
| test_17_hevc_codec | 通過 |
| test_18_av1_codec | 通過 |
| test_19_profile_save_not_overwritten_by_ui_settings | 通過 |
| test_20_watch_tracks_changed_file_and_cleared_completion | 通過 |
| test_21_watch_exclusion_uses_path_boundaries | 通過 |
| test_22_cancel_running_owned_process | 通過 |
| test_23_compare_preview | 通過 |
| test_24_low_memory_limits_and_nested_workflow | 通過 |
| test_25_aes_pdf_roundtrip | 通過 |
| test_26_cleanup_only_old_selected_owned_files | 通過 |
| test_27_cleanup_modified_files_are_skipped | 通過 |
| test_28_cleanup_expired_or_wrong_token_rejected | 通過 |
| test_29_cleanup_path_boundary | 通過 |
| test_30_hardware_short_test | 通過 |
| test_31_disk_check_plan_has_no_repair_switch | 通過 |
| test_32_removed_recovery_mode_is_rejected | 通過 |
| test_33_repair_plan_requires_confirmation_and_fixed_switch | 通過 |
| test_34_disk_launch_requires_confirmation | 通過 |
| test_35_disk_rejects_shell_input | 通過 |

### 視窗管線與對話框

| 項目 | 結果 |
|---|---|
| test_cancelled_dialog | 通過 |
| test_doc_routing_and_missing_report | 通過 |
| test_filter_names_and_extensions | 通過 |
| test_native_and_child_stdout_do_not_corrupt_pipe | 通過 |
| test_open_folder_save_dialog_roundtrips | 通過 |
| test_window_operations_are_framed | 通過 |

### 特殊格式與設備邊界

| 項目 | 結果 |
|---|---|
| test_bluray_missing_and_protected_media | 通過 |
| test_cd_64bit_handle_and_drive_guard | 通過 |
| test_cd_read_and_unreadable_sector_warning | 通過 |
| test_dvd_vob_conversion | 通過 |
| test_invalid_file_open_does_not_report_success | 通過 |
| test_iso_raw_read_from_simulated_optical_device | 通過 |
| test_office_tool_excel | 通過 |
| test_office_tool_ppt | 通過 |
| test_pdf_chinese_ocr | 通過 |
| test_pdf_unlock_roundtrip | 通過 |
| test_psd_and_svg | 通過 |
| test_recording_pipeline_with_synthetic_source | 通過 |
| test_synthetic_dng_raw | 通過 |
| test_video_blurred_background | 通過 |

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
| 磁碟 | 預覽、命令參數與確認機制、拒絕注入測試 | 實際磁碟修復和資料救援；本版沒有 Windows File Recovery 救援功能 |
| 檔案 | 列出的自製標準與邊界文件 | 所有損毀、超大、特殊字型及惡意檔案；PDF 轉 Office 的複雜版面仍需人工檢查 |

## 發布狀態

安裝包、應用程式來源與文件在 GitHub 公開發布；FFmpeg full build 的所有間接程式庫與精確建置來源、部分既有引擎的完整對應來源仍待核實。不得將此狀態寫成「已排除所有法律風險」。GNU GPL 的二進位散布條件需提供相應來源，見 [GPLv3 第 6 條](https://www.gnu.org/licenses/gpl-3.0.html#section6) 與 [GNU 授權常見問題](https://www.gnu.org/licenses/gpl-faq.html#SourceAndBinaryOnDifferentSites)。詳細清單見 source/來源清單.json 與「開源與散布說明.md」。
