/*
 * qpdf 重寫探針：把輸入 PDF 重新寫出（重新壓縮串流＋物件串流），輸出 JSON 供等價比對。
 *
 * 用法：swbd-cpp-pdf-rewrite <base_dir> <in.pdf> <out.pdf>
 * 全程使用寬字元參數與 UTF-8 轉換，非 ASCII 路徑不會出問題（qpdf 本身只看到記憶體）。
 */
#include <windows.h>
#include <stdio.h>
#include <string>

#include "swbd/qpdf.hpp"

namespace {

std::string utf8_from_wide(const wchar_t *w) {
    if (!w || !*w) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

/* JSON 字串轉義（錯誤訊息可能含引號與反斜線）。 */
std::string escape(const std::string &text) {
    std::string out;
    out.reserve(text.size() + 8);
    for (char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else out += c;
    }
    return out;
}

long long file_size(const std::string &path) {
    const int need = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
    std::wstring wide(static_cast<size_t>(need ? need : 1), L'\0');
    if (need) MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide.data(), need);
    wide.resize(need ? static_cast<size_t>(need - 1) : 0);
    WIN32_FILE_ATTRIBUTE_DATA data{};
    if (!GetFileAttributesExW(wide.c_str(), GetFileExInfoStandard, &data)) return -1;
    return (static_cast<long long>(data.nFileSizeHigh) << 32) | data.nFileSizeLow;
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
    if (argc < 4) {
        fputs("usage: swbd-cpp-pdf-rewrite <base_dir> <in.pdf> <out.pdf>\n", stderr);
        return 2;
    }
    const std::string base = utf8_from_wide(argv[1]);
    const std::string input = utf8_from_wide(argv[2]);
    const std::string output = utf8_from_wide(argv[3]);

    swbd::pdf::Qpdf &qpdf = swbd::pdf::Qpdf::instance();
    if (!qpdf.load(base)) {
        printf("{\"ok\":false,\"error\":\"qpdf 未載入\",\"module\":\"%s\",\"win32\":%lu}\n",
               escape(qpdf.module_path()).c_str(), qpdf.last_load_error());
        return 3;
    }
    std::string error;
    const bool ok = qpdf.rewrite_file(input, output, error);
    printf("{\"ok\":%s,\"version\":\"%s\",\"in_bytes\":%lld,\"out_bytes\":%lld,\"error\":\"%s\"}\n",
           ok ? "true" : "false", escape(qpdf.version()).c_str(), file_size(input), file_size(output),
           escape(error).c_str());
    fflush(stdout);
    return ok ? 0 : 1;
}
