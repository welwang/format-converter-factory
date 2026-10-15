/*
 * 原生 PDF 渲染探針：把第 N 頁以指定 dpi 渲染成 PNG，供與 Python（pypdfium2 + Pillow）逐像素比對。
 *
 * 用法：swbd-cpp-pdf-render <base_dir> <pdf> <page> <dpi> <out.png>
 * 一律用 wmain 取寬字元參數再轉 UTF-8，避免非 ASCII 路徑問題。
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>

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

}  // namespace

int wmain(int argc, wchar_t **argv) {
    if (argc < 5) {
        fputs("usage: swbd-cpp-pdf-render <base_dir> <pdf> <page> <dpi> <out.png>\n"
              "       swbd-cpp-pdf-render --bench <base_dir> <pdf> <dpi> <out_dir>          (全部頁面，渲染＋編碼計時)\n"
              "       swbd-cpp-pdf-render --bench-render <base_dir> <pdf> <dpi>              (只渲染，不編碼)\n",
              stderr);
        return 2;
    }
    /* 只渲染、不編碼：把 PDFium 的渲染成本與 PNG 編碼成本分開量。 */
    if (wcscmp(argv[1], L"--bench-render") == 0 && argc >= 5) {
        const std::string base = utf8_from_wide(argv[2]);
        const std::string pdf = utf8_from_wide(argv[3]);
        const double dpi = _wtof(argv[4]);
        swbd::pdf::Pdfium &pdfium = swbd::pdf::Pdfium::instance();
        if (!pdfium.load(base)) { printf("{\"ok\":false,\"error\":\"PDFium 未載入\"}\n"); return 3; }
        swbd::pdf::FPDF_DOCUMENT doc = pdfium.LoadDocument(pdf.c_str(), nullptr);
        if (!doc) { printf("{\"ok\":false,\"error\":\"無法開啟\"}\n"); return 3; }
        const int pages = pdfium.GetPageCount(doc);
        const double scale = dpi / 72.0;
        const ULONGLONG begin = GetTickCount64();
        long long pixels = 0;
        for (int i = 0; i < pages; i++) {
            swbd::pdf::FPDF_PAGE page = pdfium.LoadPage(doc, i);
            if (!page) continue;
            const int w = static_cast<int>(std::ceil(static_cast<double>(pdfium.GetPageWidthF(page)) * scale));
            const int h = static_cast<int>(std::ceil(static_cast<double>(pdfium.GetPageHeightF(page)) * scale));
            swbd::pdf::FPDF_BITMAP bitmap = pdfium.Bitmap_Create(w, h, 0);
            if (bitmap) {
                pdfium.Bitmap_FillRect(bitmap, 0, 0, w, h, 0xFFFFFFFFu);
                pdfium.RenderPageBitmap(bitmap, page, 0, 0, w, h, 0, 0x01);
                pixels += static_cast<long long>(w) * h;
                pdfium.Bitmap_Destroy(bitmap);
            }
            pdfium.ClosePage(page);
        }
        const ULONGLONG elapsed = GetTickCount64() - begin;
        pdfium.CloseDocument(doc);
        printf("{\"ok\":true,\"pages\":%d,\"pixels\":%lld,\"ms\":%llu,\"ms_per_page\":%.1f}\n",
               pages, pixels, static_cast<unsigned long long>(elapsed),
               pages ? static_cast<double>(elapsed) / pages : 0.0);
        fflush(stdout);
        return 0;
    }
    /* 效能基準模式：不經過引擎工作流程，量測純渲染＋編碼的成本。 */
    if (wcscmp(argv[1], L"--bench") == 0) {
        const std::string base = utf8_from_wide(argv[2]);
        const std::string pdf = utf8_from_wide(argv[3]);
        const double dpi = _wtof(argv[4]);
        const std::string out = utf8_from_wide(argv[5]);
        swbd::pdf::Pdfium &pdfium = swbd::pdf::Pdfium::instance();
        if (!pdfium.load(base)) {
            printf("{\"ok\":false,\"error\":\"PDFium 未載入\"}\n");
            return 3;
        }
        CreateDirectoryW(std::wstring(argv[5]).c_str(), nullptr);
        const ULONGLONG begin = GetTickCount64();
        const swbd::pdf::RenderAll r = swbd::pdf::render_all_pages(pdfium, pdf, dpi, out, "png", nullptr, 4);
        const ULONGLONG elapsed = GetTickCount64() - begin;
        printf("{\"ok\":%s,\"pages\":%d,\"rendered\":%d,\"ms\":%llu,\"ms_per_page\":%.1f,\"error\":\"%s\"}\n",
               r.ok ? "true" : "false", r.pages, r.rendered, static_cast<unsigned long long>(elapsed),
               r.rendered ? static_cast<double>(elapsed) / r.rendered : 0.0, r.error.c_str());
        fflush(stdout);
        return r.ok ? 0 : 1;
    }
    const std::string base = utf8_from_wide(argv[1]);
    const std::string pdf = utf8_from_wide(argv[2]);
    const int page = _wtoi(argv[3]);
    const double dpi = _wtof(argv[4]);
    const std::string out = utf8_from_wide(argv[5]);

    swbd::pdf::Pdfium &pdfium = swbd::pdf::Pdfium::instance();
    if (!pdfium.load(base)) {
        printf("{\"ok\":false,\"error\":\"PDFium 未載入\"}\n");
        return 3;
    }
    const swbd::pdf::RenderOutcome r = swbd::pdf::render_page_to_png(pdfium, pdf, page, dpi, out);
    printf("{\"ok\":%s,\"width\":%d,\"height\":%d,\"error\":\"%s\"}\n",
           r.ok ? "true" : "false", r.width, r.height, r.error.c_str());
    fflush(stdout);
    return r.ok ? 0 : 1;
}
