/* qpdf 重寫層的介面（只用 C API 子集，動態載入）。
 *
 * 用途：把既有 PDF 重新寫出——重新壓縮串流、產生物件串流、丟掉未引用物件。
 * 這正是現行 pypdf 路徑（`page.compress_content_streams(level=9)` +
 * `compress_identical_objects`）在做的事，也是單檔「PDF → PDF」能等價的前提。
 *
 * 全程記憶體操作：qpdf 的檔案 API 是窄字元 fopen，非 ASCII 路徑會失敗，
 * 所以輸入輸出都由呼叫端用 Win32 寬字元 API 處理。
 */
#ifndef SWBD_CPP_QPDF_HPP
#define SWBD_CPP_QPDF_HPP

#include <string>
#include <vector>

namespace swbd::pdf {

class Qpdf {
public:
    static Qpdf &instance();

    /* 在 base_dir\_internal 底下找 qpdf*.dll（檔名帶雜湊）。找不到就維持未就緒，呼叫端降級。 */
    bool load(const std::string &base_dir);
    bool ready() const { return ready_; }
    const std::string &version() const { return version_; }
    /* 載入失敗時的診斷：模組路徑與 LoadLibrary 的 GetLastError。 */
    const std::string &module_path() const { return module_path_; }
    unsigned long last_load_error() const { return last_load_error_; }

    /* 讀檔 → 重寫 → 寫檔。兩邊都是 UTF-8 路徑，由我們自己以寬字元 API 進出。 */
    /* recover = true 時開啟 qpdf 的結構復原（pikepdf 的 attempt_recovery=True，p_repair 用）。 */
    bool rewrite_file(const std::string &input_utf8, const std::string &output_utf8, std::string &error,
                      bool recover = false);

    /* 純記憶體版本：合併等流程會先由 PDFium 在記憶體組頁，再交給這裡重寫。 */
    bool rewrite_memory(const std::vector<unsigned char> &input, std::vector<unsigned char> &output, std::string &error);

private:
    Qpdf() = default;
    std::string last_error(void *q) const;

    bool ready_ = false;
    void *module_ = nullptr;
    std::string version_;
    std::string module_path_;
    unsigned long last_load_error_ = 0;

    /* qpdf C API 子集 */
    void *(*Init)() = nullptr;
    int (*ReadMemory)(void *, const char *, const char *, unsigned long long, const char *) = nullptr;
    int (*InitWriteMemory)(void *) = nullptr;
    int (*Write)(void *) = nullptr;
    const unsigned char *(*GetBuffer)(void *) = nullptr;
    size_t (*GetBufferLength)(void *) = nullptr;
    int (*HasError)(void *) = nullptr;
    void *(*GetError)(void *) = nullptr;
    const char *(*GetErrorText)(void *, void *) = nullptr;
    void (*SetCompressStreams)(void *, int) = nullptr;
    void (*SetObjectStreamMode)(void *, int) = nullptr;
    void (*SetDecodeLevel)(void *, int) = nullptr;
    void (*SetPreserveUnreferenced)(void *, int) = nullptr;
    void (*SetAttemptRecovery)(void *, int) = nullptr;
    void (*Cleanup)(void **) = nullptr;
    const char *(*GetVersion)() = nullptr;
};

}  // namespace swbd::pdf

#endif
