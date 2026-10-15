/* PNG 輸出：唯一的 stb_image_write 實作單元，並以 zlib 取代它內建的 deflate。
 *
 * 兩個踩過的坑：
 *   1. stb 內建的檔案輸出用窄字元 fopen，遇到非 ASCII 路徑（例如 E:\四維八德）會失敗；
 *      因此以 STBI_WRITE_NO_STDIO 關掉它，改用 Win32 寬字元開檔 + 回呼寫入（並自行緩衝，
 *      stb 逐掃描線呼叫，不緩衝會產生數萬次系統呼叫）。
 *   2. stb 內建的 deflate 明顯較慢：實測 24 頁 A4 @150 dpi，純 PDFium 渲染只要 3.3 ms/頁，
 *      但 stb 的編碼讓整體變成 94 ms/頁，而 Pillow（libpng + zlib）只要 24 ms/頁。
 *      掛勾 STBIW_ZLIB_COMPRESS 是「整張圖一次呼叫」，所以直接接 zlib 1.3.1——
 *      正是 libpng 底下用的同一套，速度與輸出大小都可預期。
 *      zlib 為 Jean-loup Gailly / Mark Adler 版權（zlib license），見 third_party/zlib/README.zlib。
 *   stb_image_write v1.16（public domain，Sean Barrett）。
 */
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STBI_WRITE_NO_STDIO

#include <windows.h>

#include <cstdlib>
#include <string>
#include <vector>

#include "zlib.h"

namespace {

/* stb 會用 free() 釋放回傳緩衝。 */
unsigned char *zlib_compress(unsigned char *data, int data_len, int *out_len, int quality) {
    if (!data || data_len <= 0) return nullptr;
    const uLong source_len = static_cast<uLong>(data_len);
    uLong bound = compressBound(source_len);
    if (bound == 0) bound = source_len + source_len / 100 + 64;
    unsigned char *out = static_cast<unsigned char *>(std::malloc(static_cast<size_t>(bound)));
    if (!out) return nullptr;
    uLongf produced = bound;
    const int level = (quality < 0 || quality > 9) ? 6 : quality;
    if (compress2(out, &produced, data, source_len, level) != Z_OK) {
        std::free(out);
        return nullptr;
    }
    *out_len = static_cast<int>(produced);
    return out;
}

constexpr size_t kFlushBytes = 256 * 1024;

struct Sink {
    HANDLE file = INVALID_HANDLE_VALUE;
    bool failed = false;
    std::vector<unsigned char> buffer;

    Sink() { buffer.reserve(kFlushBytes); }
};

void flush(Sink *sink) {
    if (!sink || sink->failed || sink->buffer.empty()) return;
    size_t offset = 0;
    while (offset < sink->buffer.size()) {
        DWORD written = 0;
        const DWORD chunk = static_cast<DWORD>(sink->buffer.size() - offset);
        if (!WriteFile(sink->file, sink->buffer.data() + offset, chunk, &written, nullptr) || written == 0) {
            sink->failed = true;
            return;
        }
        offset += written;
    }
    sink->buffer.clear();
}

void write_callback(void *context, void *data, int size) {
    Sink *sink = static_cast<Sink *>(context);
    if (!sink || sink->failed || size <= 0) return;
    const unsigned char *cursor = static_cast<const unsigned char *>(data);
    size_t left = static_cast<size_t>(size);
    while (left > 0) {
        const size_t room = kFlushBytes - sink->buffer.size();
        const size_t take = left < room ? left : room;
        sink->buffer.insert(sink->buffer.end(), cursor, cursor + take);
        cursor += take;
        left -= take;
        if (sink->buffer.size() >= kFlushBytes) {
            flush(sink);
            if (sink->failed) return;
        }
    }
}

std::wstring widen(const std::string &utf8) {
    if (utf8.empty()) return std::wstring();
    const int need = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    std::wstring out(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, out.data(), need);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

}  // namespace

#define STBIW_ZLIB_COMPRESS(a, b, c, d) zlib_compress(a, b, c, d)
#include "stb_image_write.h"

/* UTF-8 路徑的 PNG 寫入；成功回傳非零。
   兩個關鍵設定（都有實測依據）：
     - stbi_write_force_png_filter：stb 預設對**每一列**都試完 5 種濾波器再估熵挑一個，
       那相當於每張圖多掃 5 遍，是真正的成本來源（換 zlib、調壓縮等級都只影響幾個百分點）。
       固定的 Paeth 濾波器對「文字＋向量圖形」的頁面壓縮率也不錯，只掃一遍。
     - 壓縮等級 6：與 Pillow／libpng 的預設一致。 */
extern "C" int swbd_write_png_utf8(const char *utf8_path, int width, int height, int channels,
                                   const void *pixels, int stride) {
    if (!pixels || width <= 0 || height <= 0 || channels <= 0) return 0;
    stbi_write_png_compression_level = 6;
    stbi_write_force_png_filter = 1;   /* Sub：實測最快且檔案最小 */   /* Paeth */
    Sink sink;
    sink.file = CreateFileW(widen(utf8_path ? utf8_path : "").c_str(), GENERIC_WRITE, 0, nullptr,
                            CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (sink.file == INVALID_HANDLE_VALUE) return 0;
    const int ok = stbi_write_png_to_func(write_callback, &sink, width, height, channels, pixels, stride);
    flush(&sink);
    CloseHandle(sink.file);
    if (!ok || sink.failed) {
        DeleteFileW(widen(utf8_path).c_str());   /* 不留半個檔案 */
        return 0;
    }
    return 1;
}
