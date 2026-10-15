# 四維八德 2.3.3 測試報告

![四維八德藍寶石 Logo](assets/logo.png)

測試日期：2026-10-15（Asia/Taipei）。以下為 2.3.3 實際候選重新執行的結果，各組全部通過。不同層的檢查可涵蓋相同功能，不將重複檢查宣稱為不重複的功能數。


## 本版結果

| 案例／驗證組 | 結果 |
|---|---|
| 既有回歸 | 11 套件，0 失敗 |
| 打包後完整離線自我測試 | 81／81 |
| 打包後 PDF | 12／12 |
| 原生 PDF 工具與轉交 | 23／23 |
| 驗收防護 | 13／13 |
| 外殼接受／拒絕測試 | 4／4 |
| C 重跑、C 對 C++ 引擎及外殼 | 三組正規化後皆 0 差異 |


## 架構與判定標準

本版為 C++／Python 混合架構。已註冊 10 個 C++ 方法；python_calls=0 的探針直接驗證 cleanup_scan，不能推論所有方法都不呼叫 Python。七項原生 PDF 工具仍可向 Python 取得設定；其餘功能繼續在本機 Python 元件執行。

缺少報告、兩版共同失敗、零通知、非零結束碼或無效輸出都拒絕通過。比對只正規化測試路徑、工作代號、工作物件的時間／速度欄位；取消競態的 encoder／output 可不同。通知數可不同，但各自必須大於零。

完整驗收條件見公開儲存庫的 _build/docs/架構與驗證.md。安裝及解除安裝在產生安裝包後另行驗證；結果見發布頁 PACKAGE_VALIDATION.md 與 PUBLIC_VALIDATION.json。


## 既有回歸詳細案例


### 影音與工作控制

| 案例／驗證組 | 結果 |
|---|---|
| video_mp4 | 通過 |
| video_mkv | 通過 |
| video_webm | 通過 |
| video_mov | 通過 |
| video_avi | 通過 |
| video_gif | 通過 |
| video_mp3 | 通過 |
| video_m4a | 通過 |
| video_wav | 通過 |
| video_flac | 通過 |
| video_ogg | 通過 |
| video_opus | 通過 |
| trim | 通過 |
| size_cap | 通過 |
| merge | 通過 |
| hdr | 通過 |
| big5_vtt | 通過 |
| big5_ass | 通過 |
| markdown_docx | 通過 |
| markdown_html | 通過 |
| markdown_txt | 通過 |
| markdown_rtf | 通過 |
| office_word_pdf | 通過 |
| office_sheet_pdf | 通過 |
| office_ppt_pdf | 通過 |
| archive_7z | 通過 |
| archive_extract | 通過 |
| ebook | 通過 |
| error_retry | 通過 |
| cancel_running | 通過 |


### C++／Python 內容比對

| 案例／驗證組 | 結果 |
|---|---|
| video_mp4 | 通過 |
| video_mkv | 通過 |
| video_webm | 通過 |
| video_mov | 通過 |
| video_avi | 通過 |
| video_gif | 通過 |
| video_mp3 | 通過 |
| video_m4a | 通過 |
| video_wav | 通過 |
| video_flac | 通過 |
| video_ogg | 通過 |
| video_opus | 通過 |
| trim | 通過 |
| size_cap | 通過 |
| merge | 通過 |
| hdr | 通過 |
| big5_vtt | 通過 |
| big5_ass | 通過 |
| markdown_docx | 通過 |
| markdown_html | 通過 |
| markdown_txt | 通過 |
| markdown_rtf | 通過 |
| office_word_pdf | 通過 |
| office_sheet_pdf | 通過 |
| office_ppt_pdf | 通過 |
| archive_7z | 通過 |
| archive_extract | 通過 |
| ebook | 通過 |


### 編碼與加速選項

| 案例／驗證組 | 結果 |
|---|---|
| hevc | 通過 |
| av1 | 通過 |
| gpu_or_cpu_fallback | 通過 |
| lossless_container_copy | 通過 |
| audio_copy | 通過 |
| full_decode_validation | 通過 |


### 介面與表單

| 案例／驗證組 | 結果 |
|---|---|
| v_social | 通過 |
| v_fill | 通過 |
| v_crop | 通過 |
| v_rotate | 通過 |
| v_speed | 通過 |
| v_wm_text | 通過 |
| v_wm_img | 通過 |
| v_delogo | 通過 |
| v_subs | 通過 |
| v_autosub | 通過 |
| v_audio | 通過 |
| v_mute | 通過 |
| v_split | 通過 |
| v_stab | 通過 |
| v_enhance | 通過 |
| v_fade | 通過 |
| v_reverse | 通過 |
| v_frames | 通過 |
| v_grid | 通過 |
| a_volume | 通過 |
| a_pitch | 通過 |
| a_vocal | 通過 |
| a_denoise | 通過 |
| a_silence | 通過 |
| a_mix | 通過 |
| a_ringtone | 通過 |
| a_tags | 通過 |
| a_transcribe | 通過 |
| a_meeting | 通過 |
| i_resize | 通過 |
| i_rotate | 通過 |
| i_watermark | 通過 |
| i_collage | 通過 |
| i_slideshow | 通過 |
| i_gif | 通過 |
| p_split | 通過 |
| p_pages | 通過 |
| p_rotate | 通過 |
| p_encrypt | 通過 |
| p_decrypt | 通過 |
| x_privacy | 通過 |
| d_dvd | 通過 |
| d_bluray | 通過 |
| d_cd | 通過 |
| d_iso | 通過 |
| p_merge | 通過 |
| p_remove | 通過 |
| p_extract | 通過 |
| p_organize | 通過 |
| p_scan | 通過 |
| p_compress | 通過 |
| p_repair | 通過 |
| p_ocr | 通過 |
| p_images_pdf | 通過 |
| p_word_pdf | 通過 |
| p_ppt_pdf | 通過 |
| p_excel_pdf | 通過 |
| p_office_pdf | 通過 |
| p_html_pdf | 通過 |
| p_pdf_images | 通過 |
| p_pdf_word | 通過 |
| p_pdf_word_ocr | 通過 |
| p_pdf_ppt | 通過 |
| p_pdf_excel | 通過 |
| p_pdf_excel_ocr | 通過 |
| p_pdfa | 通過 |
| p_numbers | 通過 |
| p_watermark | 通過 |
| p_crop | 通過 |
| p_edit | 通過 |
| p_forms | 通過 |
| p_sign | 通過 |
| p_certificate | 通過 |
| p_redact | 通過 |
| p_compare | 通過 |
| p_summary | 通過 |
| p_translate | 通過 |
| p_markdown | 通過 |
| p_copy | 通過 |
| p_content | 通過 |
| p_flatten | 通過 |
| p_workflow | 通過 |
| keyboard_search_escape | 通過 |
| open_and_reveal_buttons | 通過 |
| offline_report_button | 通過 |
| pdf_drag_text_action | 通過 |
| viewport_1024 | 通過 |
| viewport_1366 | 通過 |
| viewport_1920 | 通過 |
| theme_dark | 通過 |
| theme_light | 通過 |
| logo_loaded | 通過 |
| sidebar_small_logo | 通過 |
| drop_small_logo | 通過 |
| about_full_logo | 通過 |
| javascript_no_errors | 通過 |


### 視窗通訊

| 案例／驗證組 | 結果 |
|---|---|
| test_cancelled_dialog | 通過 |
| test_doc_routing_and_missing_report | 通過 |
| test_filter_names_and_extensions | 通過 |
| test_native_and_child_stdout_do_not_corrupt_pipe | 通過 |
| test_open_folder_save_dialog_roundtrips | 通過 |
| test_window_operations_are_framed | 通過 |


### PDF 功能

| 案例／驗證組 | 結果 |
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

| 案例／驗證組 | 結果 |
|---|---|
| test_47_workflow | 通過 |
| test_48_word_to_pdf | 通過 |
| test_49_html_local | 通過 |
| test_50_html_remote_rejected | 通過 |
| test_51_download_paths | 通過 |


### 特殊格式與設備邊界

| 案例／驗證組 | 結果 |
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


### 交付工作流程與電腦工具

| 案例／驗證組 | 結果 |
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


### Unicode 與網址來源限制

| 案例／驗證組 | 結果 |
|---|---|
| ASCII 路徑 | 通過 |
| 繁體中文路徑 | 通過 |
| 中文含空白 | 通過 |
| 百分比與特殊符號 | 通過 |
| 混合 Unicode | 通過 |
| 拒絕 HTTPS 頁面來源 | 通過 |
| 拒絕其他本機頁面 | 通過 |
| 拒絕外部伺服器來源 | 通過 |


### 圖示資源

主程式的 ICO 資源與來源雜湊一致；背景元件與安裝程式另在安裝驗證時再次核對。


## 打包後完整離線自我測試

| 案例／驗證組 | 結果 |
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
| 圖片浮水印／Logo {'logo': 'E:\\四維八德\\_bu | 通過 |
| 去除浮水印 {'rect': '1000,40,200,80'} | 通過 |
| 加字幕 {'sub': 'E:\\四維八德\\_build\\rel | 通過 |
| 加字幕 {'sub': 'E:\\四維八德\\_build\\rel | 通過 |
| 配樂／換音軌 {'music': 'E:\\四維八德\\_build | 通過 |
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


## 打包後 PDF

| 案例／驗證組 | 結果 |
|---|---|
| p_merge | 通過 |
| p_pdf_word | 通過 |
| p_pdf_excel | 通過 |
| p_pdf_ppt | 通過 |
| p_markdown | 通過 |
| p_redact | 通過 |
| p_pdfa | 通過 |
| p_ocr | 通過 |
| p_summary | 通過 |
| p_translate | 通過 |
| p_workflow | 通過 |
| p_certificate | 通過 |


## 原生 PDF 與轉交

| 案例／驗證組 | 結果 |
|---|---|
| p_copy／複製 PDF（須逐位元相同） | 通過 |
| p_flatten／壓平註記與表單 | 通過 |
| p_repair／修復有效 PDF（交回 Python） | 通過 |
| p_repair／修復損壞 PDF（交回 Python） | 通過 |
| p_pdf_images／每頁轉 PNG（交回 Python） | 通過 |
| p_pdf_images／每頁轉 JPG（交回 Python） | 通過 |
| p_compress／無損壓縮（原生） | 通過 |
| p_compress／重壓圖片（交回 Python） | 通過 |
| p_merge／合併兩份（順序 A,B） | 通過 |
| p_merge／合併三份（順序 C,A,B） | 通過 |
| p_merge／只有一份（應拒絕） | 通過 |
| p_remove／移除單頁（走反向呼叫 Python） | 通過 |
| p_remove／移除 2,4-5 | 通過 |
| p_remove／移除單頁 | 通過 |
| p_remove／全部移除（應拒絕） | 通過 |
| p_remove／頁碼格式錯誤 | 通過 |
| p_remove／頁碼超出範圍 | 通過 |
| p_remove／空白＝全部（應拒絕） | 通過 |
| p_extract／提取 3,1-2 | 通過 |
| p_extract／提取並重複 2,2,5 | 通過 |
| p_organize／整理：依輸入順序 | 通過 |
| p_organize／整理：反轉 | 通過 |
| p_organize／整理：插入空白頁 | 通過 |

工具探針的轉交案例驗證路由邊界；真正 Python 轉交並完成工作另由候選外殼煙霧測試驗證。


## 驗收防護

| 案例／驗證組 | 結果 |
|---|---|
| test_arbitrary_token_not_ignored | 通過 |
| test_both_missing_fail | 通過 |
| test_cancel_race_fields_allowed | 通過 |
| test_conversion_output_must_exist_and_match_size | 通過 |
| test_dynamic_job_time_and_id_allowed | 通過 |
| test_matching_engine_failures_fail | 通過 |
| test_matching_shell_failures_fail | 通過 |
| test_missing_case_fails | 通過 |
| test_missing_report_fails | 通過 |
| test_no_notification_fails | 通過 |
| test_non_job_elapsed_not_ignored | 通過 |
| test_nonzero_exit_fails | 通過 |
| test_positive_notification_counts_allowed | 通過 |

| 案例／驗證組 | 結果 |
|---|---|
| 外殼 pass | 預期接受，通過 |
| 外殼 reported-failure | 預期拒絕，通過 |
| 外殼 zero-notifications | 預期拒絕，通過 |
| 外殼 nonzero-exit | 預期拒絕，通過 |


## 模型與效能

三個離線模型的 SHA-256 與上一個已驗證候選相同，未更換模型或降低品質。指定 24 頁素材曾量得原生渲染相對 Python 正式工作路徑快 1.11×；本次未重跑效能基準，不將該數字推論為所有 PDF 或電腦的固定加速比。


## 測試範圍限制

通過不代表所有硬體、特殊文件、競態或 AI 語意結果均無錯誤。AI 測試驗證本機程序與輸出存在；辨識、翻譯及摘要仍需人工校對。PDF/A 未經獨立 veraPDF 認證，測試簽章不代表公開信任或特定法律效力。

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



## 來源與散布狀態

應用程式原始碼保留在公開儲存庫，完整安裝包包含本版應用程式來源與授權記錄；發布頁不另附來源 ZIP。第三方完整對應來源核實仍有未完成項目，詳見 source/來源清單.json 及開源與散布說明.md。
