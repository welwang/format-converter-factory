/*
 * 原生 PDF 層的探針：對每個 PDF 輸出一行 JSON（頁數、頁面尺寸、中繼資料）。
 * 用途是與 Python（pymupdf）逐欄比對，證明原生層與現行實作等價。
 *
 * 用法：swbd-cpp-pdf-probe <base_dir> <pdf> [pdf...]
 * 一律使用 wmain 取得寬字元參數，再轉 UTF-8 交給 PDFium，避免非 ASCII 路徑問題。
 */
#include <windows.h>
#include <stdio.h>
#include <string>

#include "swbd/json.hpp"
#include "swbd/pdfium.hpp"

namespace {

std::string utf8_from_wide(const wchar_t *w) {
    if (!w || !*w) return std::string();
    const int need = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string out(static_cast<size_t>(need ? need : 1), '\0');
    if (need) WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), need, nullptr, nullptr);
    out.resize(need ? static_cast<size_t>(need - 1) : 0);
    return out;
}

std::string base_name(const std::string &path) {
    const size_t slash = path.find_last_of("\\/");
    return slash == std::string::npos ? path : path.substr(slash + 1);
}

}  // namespace

int wmain(int argc, wchar_t **argv) {
    if (argc < 3) {
        fputs("usage: swbd-cpp-pdf-probe <base_dir> <pdf> [pdf...]\n", stderr);
        return 2;
    }
    const std::string base = utf8_from_wide(argv[1]);
    swbd::pdf::Pdfium &pdfium = swbd::pdf::Pdfium::instance();
    if (!pdfium.load(base)) {
        printf("{\"error\":\"PDFium 未載入\"}\n");
        return 3;
    }
    int failures = 0;
    for (int i = 2; i < argc; i++) {
        const std::string path = utf8_from_wide(argv[i]);
        swbd::Json object = swbd::Json::parse(swbd::pdf::describe_document(pdfium, path));
        object.set("file", swbd::Json::of(base_name(path)));
        const std::string line = object.dump();
        printf("%s\n", line.c_str());
        if (object.get("error")) failures++;
    }
    fflush(stdout);
    return failures ? 1 : 0;
}
